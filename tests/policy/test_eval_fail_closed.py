from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_per_mode_eval_tasks_exist_and_fail_closed_without_ground_truth() -> None:
    for mode in ("cloud", "airgap", "dual"):
        task_path = REPO_ROOT / "inspect_ai" / "tasks" / f"verdict_eval_{mode}.py"

        assert task_path.is_file(), f"missing Inspect AI task for {mode} mode"
        task = task_path.read_text(encoding="utf-8")
        assert "GroundTruthMissingError" in task
        assert "inspect_ai/ground_truth" in task
        assert "real evidence" in task
        assert "Sample(" not in task, "per-mode evals must not use fake inline samples"


def test_airgap_and_dual_eval_require_real_evidence_per_required_case() -> None:
    for mode in ("airgap", "dual"):
        task = (REPO_ROOT / "inspect_ai" / "tasks" / f"verdict_eval_{mode}.py").read_text(
            encoding="utf-8"
        )

        assert "_case_evidence_files(GROUND_TRUTH_ROOT / case)" in task
        assert "inspect_ai/ground_truth/{case}" in task


def test_inspect_tasks_do_not_use_inline_sample_fixtures() -> None:
    for path in (REPO_ROOT / "inspect_ai" / "tasks").glob("*.py"):
        assert "Sample(" not in path.read_text(encoding="utf-8"), path


def test_hallucination_gate_does_not_allow_fake_success_without_real_scorer() -> None:
    workflow = (REPO_ROOT / ".github/workflows/eval-hallucination-gate.yml").read_text(
        encoding="utf-8"
    )
    scorer_path = REPO_ROOT / "inspect_ai" / "scorers" / "hallucination_rate.py"

    if not scorer_path.is_file():
        assert "scorer_not_implemented" in workflow
        assert "exit 1" in workflow
        assert "continue-on-error" not in workflow
        assert "|| true" not in workflow


def test_cloud_eval_is_wired_to_real_verdict_execution() -> None:
    task = (REPO_ROOT / "inspect_ai" / "tasks" / "verdict_eval_cloud.py").read_text(
        encoding="utf-8"
    )

    assert "run_cloud_proof" in task
    assert "MemoryDataset" in task
    assert "hallucination_rate" in task
    assert "not wired" not in task


def test_real_hallucination_scorer_validates_proof_artifacts() -> None:
    scorer_path = REPO_ROOT / "inspect_ai" / "scorers" / "hallucination_rate.py"

    assert scorer_path.is_file()
    scorer = scorer_path.read_text(encoding="utf-8")
    assert "InvestigationPlan.model_validate_json" in scorer
    assert "run-summary.md" in scorer
    assert "ledger.jsonl" in scorer
    assert "validation.log" in scorer
    assert "cloud-agent-response.raw.txt" in scorer
    assert "return 0.0" not in scorer


def test_hallucination_gate_requires_real_scorer_file_before_eval() -> None:
    workflow = (REPO_ROOT / ".github/workflows/eval-hallucination-gate.yml").read_text(
        encoding="utf-8"
    )

    assert "inspect_ai/scorers/hallucination_rate.py" in workflow
    assert workflow.index("inspect_ai/scorers/hallucination_rate.py") < workflow.index(
        "uv run inspect eval inspect_ai/tasks/verdict_eval_cloud.py"
    )


def test_hallucination_gate_text_reflects_landed_scorer() -> None:
    assert (REPO_ROOT / "inspect_ai" / "scorers" / "hallucination_rate.py").is_file()
    release = (REPO_ROOT / "docs" / "RELEASE.md").read_text(encoding="utf-8")
    workflow = (REPO_ROOT / ".github/workflows/eval-hallucination-gate.yml").read_text(
        encoding="utf-8"
    )

    assert "until `inspect_ai/scorers/hallucination_rate.py` lands" not in release
    assert "Fail closed until hallucination scorer lands" not in workflow
    assert "Verify evaluator and scorer files exist" in workflow


def test_hallucination_gate_checks_all_per_mode_eval_tasks() -> None:
    workflow = (REPO_ROOT / ".github/workflows/eval-hallucination-gate.yml").read_text(
        encoding="utf-8"
    )

    for mode in ("cloud", "airgap", "dual"):
        assert f"inspect_ai/tasks/verdict_eval_{mode}.py" in workflow


def test_no_canned_hallucination_scores_in_eval_scaffolding() -> None:
    for path in (REPO_ROOT / "inspect_ai").glob("**/*.py"):
        content = path.read_text(encoding="utf-8")
        assert "hallucination_rate = 0" not in content
        assert "return 0.0" not in content
        assert "CORRECT" not in content or "hallucination" not in content.lower()
