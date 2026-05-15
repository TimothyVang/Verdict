from __future__ import annotations

import importlib.util
from pathlib import Path

from verdict.schemas.plan import Hypothesis, InvestigationPlan

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_hallucination_module():
    scorer_path = REPO_ROOT / "inspect_ai" / "scorers" / "hallucination_rate.py"
    assert scorer_path.is_file()
    spec = importlib.util.spec_from_file_location("verdict_hallucination_rate", scorer_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _valid_plan(case_id: str) -> InvestigationPlan:
    return InvestigationPlan(
        plan_id=f"plan-{case_id}",
        case_id=case_id,
        positive_hypotheses=[
            Hypothesis(
                id="h_positive_001",
                polarity="positive",
                mitre_technique="T1059.001",
                artifact_families=["process", "event_log"],
                success_criteria="Corroborate process execution across process and event artifacts.",
            )
        ],
        negative_hypotheses=[
            Hypothesis(
                id="h_negative_001",
                polarity="negative",
                mitre_technique="T1547.001",
                artifact_families=["registry", "scheduled_task"],
                success_criteria="Rule out Run key and scheduled task persistence.",
            )
        ],
        tool_budget=4,
        success_criteria="Return only claims supported by multiple artifact classes.",
        planner_cot_gzip_hash="cloud-v0-not-captured",
    )


def test_score_proof_artifacts_accepts_schema_valid_pass_run(tmp_path: Path) -> None:
    module = _load_hallucination_module()
    case_id = "case_001_lolbins"
    proof_run = tmp_path / "run"
    proof_run.mkdir()
    (proof_run / "run-summary.md").write_text("Status: PASS\n", encoding="utf-8")
    (proof_run / "ledger.jsonl").write_text('{"event_type":"cloud_proof_plan_validated"}\n', encoding="utf-8")
    (proof_run / "validation.log").write_text(
        "InvestigationPlan schema validation passed.\n",
        encoding="utf-8",
    )
    (proof_run / "cloud-agent-response.raw.txt").write_text(
        "Claude response containing InvestigationPlan JSON.\n",
        encoding="utf-8",
    )
    (proof_run / "investigation-plan.json").write_text(
        _valid_plan(case_id).model_dump_json(),
        encoding="utf-8",
    )

    result = module.score_proof_artifacts(proof_run, case_id=case_id)

    assert result.value == 0
    assert result.metadata["proof_valid"] is True


def test_score_proof_artifacts_fails_closed_without_plan(tmp_path: Path) -> None:
    module = _load_hallucination_module()
    proof_run = tmp_path / "run"
    proof_run.mkdir()
    (proof_run / "run-summary.md").write_text("Status: PASS\n", encoding="utf-8")

    result = module.score_proof_artifacts(proof_run, case_id="case_001_lolbins")

    assert result.value > 0
    assert result.metadata["proof_valid"] is False
    assert "investigation-plan.json missing" in result.explanation


def test_score_proof_artifacts_fails_closed_without_ledger(tmp_path: Path) -> None:
    module = _load_hallucination_module()
    case_id = "case_001_lolbins"
    proof_run = tmp_path / "run"
    proof_run.mkdir()
    (proof_run / "run-summary.md").write_text("Status: PASS\n", encoding="utf-8")
    (proof_run / "validation.log").write_text(
        "InvestigationPlan schema validation passed.\n",
        encoding="utf-8",
    )
    (proof_run / "cloud-agent-response.raw.txt").write_text(
        "Claude response containing InvestigationPlan JSON.\n",
        encoding="utf-8",
    )
    (proof_run / "investigation-plan.json").write_text(
        _valid_plan(case_id).model_dump_json(),
        encoding="utf-8",
    )

    result = module.score_proof_artifacts(proof_run, case_id=case_id)

    assert result.value > 0
    assert result.metadata["proof_valid"] is False
    assert "ledger.jsonl missing" in result.explanation


def test_score_proof_artifacts_fails_closed_without_validation_log(tmp_path: Path) -> None:
    module = _load_hallucination_module()
    case_id = "case_001_lolbins"
    proof_run = tmp_path / "run"
    proof_run.mkdir()
    (proof_run / "run-summary.md").write_text("Status: PASS\n", encoding="utf-8")
    (proof_run / "ledger.jsonl").write_text('{"event_type":"cloud_proof_plan_validated"}\n', encoding="utf-8")
    (proof_run / "cloud-agent-response.raw.txt").write_text(
        "Claude response containing InvestigationPlan JSON.\n",
        encoding="utf-8",
    )
    (proof_run / "investigation-plan.json").write_text(
        _valid_plan(case_id).model_dump_json(),
        encoding="utf-8",
    )

    result = module.score_proof_artifacts(proof_run, case_id=case_id)

    assert result.value > 0
    assert result.metadata["proof_valid"] is False
    assert "validation.log missing" in result.explanation


def test_score_proof_artifacts_fails_closed_without_raw_response(tmp_path: Path) -> None:
    module = _load_hallucination_module()
    case_id = "case_001_lolbins"
    proof_run = tmp_path / "run"
    proof_run.mkdir()
    (proof_run / "run-summary.md").write_text("Status: PASS\n", encoding="utf-8")
    (proof_run / "ledger.jsonl").write_text('{"event_type":"cloud_proof_plan_validated"}\n', encoding="utf-8")
    (proof_run / "validation.log").write_text(
        "InvestigationPlan schema validation passed.\n",
        encoding="utf-8",
    )
    (proof_run / "investigation-plan.json").write_text(
        _valid_plan(case_id).model_dump_json(),
        encoding="utf-8",
    )

    result = module.score_proof_artifacts(proof_run, case_id=case_id)

    assert result.value > 0
    assert result.metadata["proof_valid"] is False
    assert "cloud-agent-response.raw.txt missing" in result.explanation
