from __future__ import annotations

import importlib.util
from functools import partial
from pathlib import Path
from typing import Any

import anyio
from inspect_ai.dataset import MemoryDataset, Sample
from inspect_ai.model import ModelOutput
from inspect_ai.solver import Generate, TaskState, solver

from inspect_ai import Task, task
from verdict.proof.cloud import run_cloud_proof


class GroundTruthMissingError(RuntimeError):
    """Raised when VERDICT eval prerequisites are not present."""


REPO_ROOT = Path(__file__).resolve().parents[2]
GROUND_TRUTH_ROOT = REPO_ROOT / "inspect_ai" / "ground_truth"
PROOF_ROOT = REPO_ROOT / "build" / "inspect-ai" / "cloud"
REQUIRED_CASE_DIRS = ("case_001_lolbins", "case_002_credtheft", "case_003_ransomware")
REAL_EVIDENCE_SUFFIXES = {".e01", ".raw", ".mem", ".pcap", ".zip"}


def _require_real_ground_truth(mode: str) -> None:
    missing_dirs = [case for case in REQUIRED_CASE_DIRS if not (GROUND_TRUTH_ROOT / case).is_dir()]
    if missing_dirs:
        raise GroundTruthMissingError(
            f"{mode} eval requires real evidence under inspect_ai/ground_truth; "
            f"missing case directories: {', '.join(missing_dirs)}"
        )

    for case in REQUIRED_CASE_DIRS:
        if not _case_evidence_files(GROUND_TRUTH_ROOT / case):
            raise GroundTruthMissingError(
                f"{mode} eval requires real evidence under inspect_ai/ground_truth/{case}; "
                "no .E01, .raw, .mem, .pcap, or .zip files found"
            )


def _cloud_dataset() -> MemoryDataset:
    _require_real_ground_truth("cloud")
    sample_type = Sample
    samples = []
    for case in REQUIRED_CASE_DIRS:
        case_dir = GROUND_TRUTH_ROOT / case
        evidence_files = _case_evidence_files(case_dir)
        evidence_summary = _evidence_summary(case, evidence_files)
        samples.append(
            sample_type(
                id=case,
                input=evidence_summary,
                target=case,
                metadata={
                    "case_id": case,
                    "evidence_paths": [str(path) for path in evidence_files],
                    "evidence_summary": evidence_summary,
                },
            )
        )
    return MemoryDataset(
        samples=samples,
        name="verdict-cloud-ground-truth",
        location=str(GROUND_TRUTH_ROOT),
    )


@solver
def cloud_proof_solver():
    async def solve(state: TaskState, _generate: Generate) -> TaskState:
        metadata: dict[str, Any] = dict(state.metadata or {})
        case_id = str(metadata["case_id"])
        case_proof_root = PROOF_ROOT / case_id
        summary_file = case_proof_root / "evidence-summary.txt"
        summary_file.parent.mkdir(parents=True, exist_ok=True)
        summary_file.write_text(str(metadata["evidence_summary"]), encoding="utf-8")

        exit_code = await anyio.to_thread.run_sync(
            partial(
                run_cloud_proof,
                proof_root=case_proof_root,
                evidence_summary_file=summary_file,
                case_id=case_id,
            )
        )
        proof_run_path = _latest_proof_run(case_proof_root)
        metadata["proof_exit_code"] = exit_code
        metadata["proof_run_path"] = str(proof_run_path) if proof_run_path else None
        state.metadata = metadata
        state.output = ModelOutput(
            completion=f"VERDICT cloud proof exit_code={exit_code} proof_run={proof_run_path}"
        )
        state.completed = True
        return state

    return solve


@task
def verdict_eval_cloud() -> Task:
    return Task(
        dataset=_cloud_dataset(),
        solver=cloud_proof_solver(),
        scorer=_load_hallucination_rate()(),
        name="verdict_eval_cloud",
    )


def _case_evidence_files(case_dir: Path) -> list[Path]:
    return sorted(
        path
        for path in case_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in REAL_EVIDENCE_SUFFIXES
    )


def _evidence_summary(case_id: str, evidence_files: list[Path]) -> str:
    lines = [
        f"Case ID: {case_id}",
        "Mode: CLOUD",
        "Real evidence files staged under inspect_ai/ground_truth:",
    ]
    for path in evidence_files:
        lines.append(
            f"- path={path} suffix={path.suffix.lower()} size_bytes={path.stat().st_size}"
        )
    lines.extend(
        [
            "Required plan discipline:",
            "- Use VERDICT epistemic wording and measurable success criteria.",
            "- Include at least one meaningful negative hypothesis.",
            "- Use MITRE technique or sub-technique IDs when determinable.",
            "- Do not assert attribution; describe evidence consistency only.",
        ]
    )
    return "\n".join(lines) + "\n"


def _latest_proof_run(proof_root: Path) -> Path | None:
    runs_root = proof_root / "runs"
    if not runs_root.is_dir():
        return None
    runs = sorted(path for path in runs_root.iterdir() if path.is_dir())
    return runs[-1] if runs else None


def _load_hallucination_rate():
    scorer_path = REPO_ROOT / "inspect_ai" / "scorers" / "hallucination_rate.py"
    spec = importlib.util.spec_from_file_location("verdict_hallucination_rate", scorer_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load hallucination scorer: {scorer_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.hallucination_rate
