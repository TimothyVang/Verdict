from __future__ import annotations

from pathlib import Path

from yaml import safe_load


PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def render_executor_prompt(role: str) -> str:
    caveats = (PACKAGE_ROOT / "planning/prompts/examiner_caveats.md").read_text()
    hunt_evil = safe_load((PACKAGE_ROOT / "knowledge/hunt_evil.yml").read_text())
    process_names = ", ".join(
        baseline["process_name"] for baseline in hunt_evil["process_baselines"]
    )

    return "\n\n".join(
        [
            f"Executor role: {role}",
            caveats,
            "Hunt Evil process baselines:",
            process_names,
            "Baseline deviations map to MITRE T1036.005.",
        ],
    )
