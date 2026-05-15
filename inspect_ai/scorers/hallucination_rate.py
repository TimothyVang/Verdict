from dataclasses import dataclass
from pathlib import Path
from typing import Any

from inspect_ai.scorer import Score, Scorer, Target, mean, scorer
from inspect_ai.solver import TaskState

from verdict.schemas.plan import InvestigationPlan


@dataclass(frozen=True)
class ProofArtifactScore:
    value: float
    explanation: str
    metadata: dict[str, Any]


def score_proof_artifacts(proof_run_path: str | Path | None, *, case_id: str) -> ProofArtifactScore:
    failures: list[str] = []
    proof_path = Path(proof_run_path) if proof_run_path else None

    if proof_path is None or not proof_path.is_dir():
        failures.append("proof run path missing")
        return _artifact_score(failures, checks=7, proof_path=proof_path, plan=None)

    summary_path = proof_path / "run-summary.md"
    if not summary_path.is_file():
        failures.append("run-summary.md missing")
    elif "Status: PASS" not in summary_path.read_text(encoding="utf-8"):
        failures.append("proof run did not report Status: PASS")

    ledger_path = proof_path / "ledger.jsonl"
    if not ledger_path.is_file():
        failures.append("ledger.jsonl missing")
    elif not ledger_path.read_text(encoding="utf-8").strip():
        failures.append("ledger.jsonl empty")

    validation_path = proof_path / "validation.log"
    if not validation_path.is_file():
        failures.append("validation.log missing")
    elif "InvestigationPlan schema validation passed" not in validation_path.read_text(
        encoding="utf-8"
    ):
        failures.append("validation.log missing schema validation success")

    raw_response_path = proof_path / "cloud-agent-response.raw.txt"
    if not raw_response_path.is_file():
        failures.append("cloud-agent-response.raw.txt missing")
    elif not raw_response_path.read_text(encoding="utf-8").strip():
        failures.append("cloud-agent-response.raw.txt empty")

    plan_path = proof_path / "investigation-plan.json"
    plan: InvestigationPlan | None = None
    if not plan_path.is_file():
        failures.append("investigation-plan.json missing")
    else:
        try:
            plan = InvestigationPlan.model_validate_json(plan_path.read_text(encoding="utf-8"))
        except ValueError as exc:
            failures.append(f"investigation-plan.json schema invalid: {exc}")

    if plan is not None and plan.case_id != case_id:
        failures.append(f"plan case_id mismatch: expected {case_id}, got {plan.case_id}")
    if plan is not None and not plan.negative_hypotheses:
        failures.append("plan has no negative hypotheses")

    return _artifact_score(failures, checks=7, proof_path=proof_path, plan=plan)


@scorer(metrics=[mean()])
def hallucination_rate() -> Scorer:
    async def score(state: TaskState, target: Target) -> Score:
        metadata = state.metadata or {}
        result = score_proof_artifacts(
            metadata.get("proof_run_path"),
            case_id=target.text,
        )
        return Score(
            value=result.value,
            explanation=result.explanation,
            metadata=result.metadata,
        )

    return score


def _artifact_score(
    failures: list[str],
    *,
    checks: int,
    proof_path: Path | None,
    plan: InvestigationPlan | None,
) -> ProofArtifactScore:
    value = len(failures) / checks
    proof_valid = not failures
    explanation = "proof artifacts validated" if proof_valid else "; ".join(failures)
    return ProofArtifactScore(
        value=value,
        explanation=explanation,
        metadata={
            "proof_valid": proof_valid,
            "proof_run_path": str(proof_path) if proof_path else None,
            "plan_id": plan.plan_id if plan else None,
            "positive_hypotheses": len(plan.positive_hypotheses) if plan else 0,
            "negative_hypotheses": len(plan.negative_hypotheses) if plan else 0,
            "failed_checks": failures,
        },
    )
