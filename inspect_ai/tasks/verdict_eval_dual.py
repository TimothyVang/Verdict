from __future__ import annotations

from pathlib import Path

from inspect_ai import Task, task


class GroundTruthMissingError(RuntimeError):
    """Raised when VERDICT eval prerequisites are not present."""


REPO_ROOT = Path(__file__).resolve().parents[2]
GROUND_TRUTH_ROOT = REPO_ROOT / "inspect_ai" / "ground_truth"
REQUIRED_CASE_DIRS = ("case_001_lolbins", "case_002_credtheft", "case_003_ransomware")
REAL_EVIDENCE_SUFFIXES = {".e01", ".raw", ".mem", ".pcap", ".zip"}


def _require_real_ground_truth(mode: str) -> None:
    missing_dirs = [case for case in REQUIRED_CASE_DIRS if not (GROUND_TRUTH_ROOT / case).is_dir()]
    if missing_dirs:
        raise GroundTruthMissingError(
            f"{mode} eval requires real evidence under inspect_ai/ground_truth; "
            f"missing case directories: {', '.join(missing_dirs)}"
        )

    evidence_files = [
        path
        for path in GROUND_TRUTH_ROOT.rglob("*")
        if path.is_file() and path.suffix.lower() in REAL_EVIDENCE_SUFFIXES
    ]
    if not evidence_files:
        raise GroundTruthMissingError(
            f"{mode} eval requires real evidence under inspect_ai/ground_truth; "
            "no .E01, .raw, .mem, .pcap, or .zip files found"
        )


def _not_wired(mode: str) -> Task:
    _require_real_ground_truth(mode)
    raise GroundTruthMissingError(
        f"{mode} eval task is scaffolded but not wired to real VERDICT execution yet; "
        "refusing to construct an eval with fake evidence or canned scorer outputs"
    )


@task
def verdict_eval_dual() -> Task:
    return _not_wired("dual")
