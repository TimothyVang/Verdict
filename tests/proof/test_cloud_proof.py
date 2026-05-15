from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from verdict.proof.cloud import create_proof_run, run_cloud_proof, write_blocker_run

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_create_proof_run_makes_visual_artifact_structure(tmp_path: Path) -> None:
    run = create_proof_run(tmp_path, timestamp="20260504T120000Z")

    assert run.path == tmp_path / "runs" / "20260504T120000Z"
    assert (run.path / "screenshots").is_dir()
    assert (run.path / "video").is_dir()
    assert (run.path / "review.md").is_file()
    assert "Claude Agent SDK" in (run.path / "review.md").read_text()


def test_create_proof_run_allocates_suffix_when_timestamp_exists(tmp_path: Path) -> None:
    first = create_proof_run(tmp_path, timestamp="20260504T120000Z")
    second = create_proof_run(tmp_path, timestamp="20260504T120000Z")

    assert first.path == tmp_path / "runs" / "20260504T120000Z"
    assert second.path == tmp_path / "runs" / "20260504T120000Z-2"
    assert second.timestamp == "20260504T120000Z-2"
    assert (second.path / "review.md").is_file()


def test_write_blocker_run_records_missing_cloud_readiness_without_secret(tmp_path: Path) -> None:
    run = create_proof_run(tmp_path, timestamp="20260504T120000Z")

    write_blocker_run(run, reason="ANTHROPIC_API_KEY is not configured")

    summary = (run.path / "run-summary.md").read_text()
    service_checks = (run.path / "service-checks.log").read_text()
    ledger = (run.path / "ledger.jsonl").read_text()
    assert "BLOCKED" in summary
    assert "ANTHROPIC_API_KEY is not configured" in service_checks
    assert "sk-ant" not in summary
    assert "cloud_proof_blocked" in ledger


def test_cloud_proof_module_entrypoint_records_blocker_without_secret(tmp_path: Path) -> None:
    secret = "secret-token"
    env = {key: os.environ[key] for key in ("COMSPEC", "PATH", "PATHEXT", "SYSTEMROOT") if key in os.environ}
    env["PYTHONPATH"] = str(REPO_ROOT / "src")
    env["ANTHROPIC_API_KEY"] = secret
    proof_root = tmp_path / "proof"

    result = subprocess.run(
        [sys.executable, "-m", "verdict.proof.cloud", "--proof-root", str(proof_root)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        check=False,
        text=True,
        timeout=30,
    )

    output = result.stdout + result.stderr
    assert result.returncode == 2
    assert "Cloud proof blocked" in output
    assert "--evidence-summary-file is required" in output
    assert secret not in output
    assert list((proof_root / "runs").glob("*/run-summary.md"))


def test_cloud_proof_blocker_ledger_preserves_requested_case_id(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    proof_root = tmp_path / "proof"

    exit_code = run_cloud_proof(
        proof_root=proof_root,
        evidence_summary_file=None,
        case_id="case-requested",
    )

    ledger_path = next((proof_root / "runs").glob("*/ledger.jsonl"))
    summary_path = ledger_path.parent / "run-summary.md"
    service_checks_path = ledger_path.parent / "service-checks.log"
    ledger_entry = json.loads(ledger_path.read_text(encoding="utf-8").splitlines()[0])
    assert exit_code == 2
    assert ledger_entry["case_id"] == "case-requested"
    assert "Case ID: case-requested" in summary_path.read_text(encoding="utf-8")
    assert "case_id=case-requested" in service_checks_path.read_text(encoding="utf-8")
