"""verdict/planning/executor_prompt.py — executor system prompt composer.

render_executor_prompt(role) -> str composes the full executor system prompt by
combining:
1. The Tier-1 examiner caveats (verdict/planning/prompts/examiner_caveats.md)
2. The Hunt Evil baseline table (verdict/knowledge/hunt_evil.yml)
3. Role-specific guidance (vol_exec gets DKOM hint; all roles get attribution rules)

The returned string is injected verbatim into the executor's system prompt at
case_init. It ensures every executor — regardless of which LLM backs it — has
the mandatory SANS forensic discipline encoded in its context window.

Roles: "vol_exec", "hay_exec", "pls_exec", "mft_exec"
"""
from __future__ import annotations

from pathlib import Path

import yaml

_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
_KNOWLEDGE_DIR = Path(__file__).resolve().parents[1] / "knowledge"

_CAVEATS_MD = _PROMPTS_DIR / "examiner_caveats.md"
_HUNT_EVIL_YML = _KNOWLEDGE_DIR / "hunt_evil.yml"

# Role-specific forensic hints injected after the shared header
_ROLE_HINTS: dict[str, str] = {
    "vol_exec": (
        "## Volatility 3 Executor Notes\n\n"
        "- Always run BOTH `vol3.windows.pslist` AND `vol3.windows.psscan`.\n"
        "- After both complete, compute `set(psscan_pids) - set(pslist_pids)`.\n"
        "  If non-empty → emit Hypothesis(T1014, high, [PROCESS_MEMORY]) — **DKOM divergence**.\n"
        "- `vol3.windows.cmdline` output: match each cmdline against lolbins.yml patterns.\n"
        "- `vol3.windows.malfind`: RWX+no-PE-header → T1055.002; hollowed PE → T1055.012; "
        "reflective DLL → T1055.001.\n"
    ),
    "hay_exec": (
        "## Hayabusa Executor Notes\n\n"
        "- Always use the split tool-pair: `hayabusa.csv_timeline` first, then `hayabusa.filter`.\n"
        "- Never run a monolithic hayabusa invocation — the filter must be analyst-driven via pivot.\n"
        "- Filter by `sigma_level` and `time_range` derived from prior findings.\n"
    ),
    "pls_exec": (
        "## Plaso Executor Notes\n\n"
        "- Always use the split tool-pair: `plaso.extract` (log2timeline.py) first, "
        "then `psort.filter` (psort.py + filter expression).\n"
        "- Plaso is the heaviest tool — run it after lighter tools (Hayabusa, MFTECmd) have "
        "narrowed the time window of interest.\n"
    ),
    "mft_exec": (
        "## MFT / EZ-Tools Executor Notes\n\n"
        "- Use `$FILE_NAME` timestamps for evidentiary claims; `$STANDARD_INFORMATION` is "
        "stompable. See MFT_SI_STOMPABLE caveat.\n"
        "- `recmd` → check Run/RunOnce/IFEO/Services hives first (T1547 persistence).\n"
        "- `pecmd` → Prefetch run-count + last_run timestamp corroborates execution claims.\n"
    ),
}

_UNKNOWN_ROLE_HINT = (
    "## Executor Notes\n\n"
    "Apply SANS canonical tool sequencing per the loaded playbook.\n"
)


def _load_caveats() -> str:
    return _CAVEATS_MD.read_text(encoding="utf-8")


def _render_hunt_evil_table() -> str:
    """Render hunt_evil.yml as a human-readable baseline table for the prompt."""
    data: list[dict] = yaml.safe_load(_HUNT_EVIL_YML.read_text(encoding="utf-8"))

    lines = [
        "## Hunt Evil — Canonical Windows Process Baselines\n",
        "Deviation from any baseline → emit ProcessBaselineAnomaly → T1036.005.\n",
        "",
        "| Process | Expected Parent | Expected Path | Instances |",
        "|---------|----------------|---------------|-----------|",
    ]
    for entry in data:
        lines.append(
            f"| {entry['process_name']} "
            f"| {entry.get('expected_parent', '?')} "
            f"| {entry.get('expected_path', '?')} "
            f"| {entry.get('expected_instance_count', '?')} |"
        )

    # Append notes for processes with forensic commentary
    lines.append("")
    for entry in data:
        if entry.get("notes"):
            note_text = str(entry["notes"]).strip()
            lines.append(f"**{entry['process_name']}:** {note_text}\n")

    return "\n".join(lines)


def render_executor_prompt(role: str) -> str:
    """Compose and return the executor system prompt for the given role.

    Args:
        role: One of "vol_exec", "hay_exec", "pls_exec", "mft_exec".
              Unknown roles receive generic guidance (not an error — the
              executor may be a future extension).

    Returns:
        A non-empty string containing:
        1. Role identity header
        2. Attribution rule (evidence consistent with X, not "X did this")
        3. Tier-1 examiner caveats
        4. Hunt Evil baseline table
        5. Role-specific forensic hints
    """
    role_hint = _ROLE_HINTS.get(role, _UNKNOWN_ROLE_HINT)
    caveats = _load_caveats()
    hunt_evil_table = _render_hunt_evil_table()

    return (
        f"# Executor System Prompt — Role: {role}\n\n"
        "## Attribution Rule\n\n"
        'Phrase all findings as **"evidence consistent with X"** — never "X did this".\n'
        "Attribution is for the human IR lead, not the agent.\n\n"
        "---\n\n"
        f"{caveats}\n\n"
        "---\n\n"
        f"{hunt_evil_table}\n\n"
        "---\n\n"
        f"{role_hint}"
    )
