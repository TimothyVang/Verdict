from __future__ import annotations

import json
from pathlib import Path

from verdict.cli.__main__ import main

REQUIRED_DEVPOST_PATHS = (
    "README.md",
    "LICENSE",
    "docs/ARCHITECTURE.md",
    "docs/ARCHITECTURE_DIAGRAM.svg",
    "docs/DEVPOST_COMPLIANCE.md",
    "docs/FAILURE_MODES.md",
    "docs/CASE_ISOLATION.md",
    "docs/RELEASE.md",
    "submission/execution-logs/case_001.jsonl",
    "submission/execution-logs/case_002.jsonl",
    "submission/execution-logs/case_003.jsonl",
)


def test_init_hashes_evidence_and_writes_manifest_and_ledger(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    evidence = tmp_path / "evidence.mem"
    evidence.write_bytes(b"memory bytes")
    cases_dir = tmp_path / "cases"
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "mode-detection-token")
    monkeypatch.setenv("VERDICT_HMAC_KEY_HEX", "ab" * 32)

    exit_code = main(
        [
            "init",
            str(evidence),
            "--case-id",
            "case-test",
            "--cases-dir",
            str(cases_dir),
            "--mode",
            "cloud",
        ]
    )

    assert exit_code == 0
    assert "case-test" in capsys.readouterr().out

    manifest = json.loads((cases_dir / "case-test" / "manifest.json").read_text())
    ledger_lines = (cases_dir / "case-test" / "ledger.jsonl").read_text().splitlines()

    assert manifest["case_id"] == "case-test"
    assert manifest["items"][0]["sha256_at_init"]
    assert manifest["items"][0]["evidence_type"] == "memory"
    assert len(ledger_lines) == 1
    assert json.loads(ledger_lines[0])["event_type"] == "case_init"


def test_export_execution_logs_distills_ledger_fields(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    evidence = tmp_path / "event.evtx"
    evidence.write_bytes(b"event bytes")
    cases_dir = tmp_path / "cases"
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "mode-detection-token")
    monkeypatch.setenv("VERDICT_HMAC_KEY_HEX", "cd" * 32)
    assert main(
        [
            "init",
            str(evidence),
            "--case-id",
            "case-export",
            "--cases-dir",
            str(cases_dir),
        ]
    ) == 0
    capsys.readouterr()

    assert main(
        [
            "export",
            "case-export",
            "--cases-dir",
            str(cases_dir),
            "--format",
            "execution-logs",
        ]
    ) == 0

    exported = json.loads(capsys.readouterr().out)
    assert exported["event_type"] == "case_init"
    assert exported["ts_utc"].endswith("Z")
    assert exported["langgraph_checkpoint_id"] == "case_init"
    assert exported["langfuse_trace_id"] == "local-cli"


def test_ls_status_and_show_report_case_state(tmp_path: Path, monkeypatch, capsys) -> None:
    evidence = tmp_path / "disk.E01"
    evidence.write_bytes(b"disk bytes")
    cases_dir = tmp_path / "cases"
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "mode-detection-token")
    monkeypatch.setenv("VERDICT_HMAC_KEY_HEX", "12" * 32)
    assert main(
        [
            "init",
            str(evidence),
            "--case-id",
            "case-lifecycle",
            "--cases-dir",
            str(cases_dir),
        ]
    ) == 0
    capsys.readouterr()

    assert main(["ls", "--cases-dir", str(cases_dir)]) == 0
    listed = json.loads(capsys.readouterr().out)
    assert listed == [{"case_id": "case-lifecycle", "mode": "CLOUD", "events": 1}]

    assert main(["status", "case-lifecycle", "--cases-dir", str(cases_dir)]) == 0
    status = json.loads(capsys.readouterr().out)
    assert status["case_id"] == "case-lifecycle"
    assert status["manifest_items"] == 1
    assert status["ledger_valid"] is True

    assert main(["show", "case-lifecycle", "--cases-dir", str(cases_dir)]) == 0
    shown = capsys.readouterr().out
    assert "case-lifecycle" in shown
    assert "disk_image" in shown


def test_init_rejects_unavailable_cloud_mode(tmp_path: Path, monkeypatch) -> None:
    evidence = tmp_path / "evidence.mem"
    evidence.write_bytes(b"memory bytes")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    monkeypatch.setenv("VERDICT_HMAC_KEY_HEX", "ef" * 32)

    exit_code = main(
        [
            "init",
            str(evidence),
            "--case-id",
            "case-no-cloud",
            "--cases-dir",
            str(tmp_path / "cases"),
            "--mode",
            "cloud",
        ]
    )

    assert exit_code == 2
    assert not (tmp_path / "cases" / "case-no-cloud").exists()


def test_init_rejects_case_id_path_traversal(tmp_path: Path, monkeypatch) -> None:
    evidence = tmp_path / "evidence.mem"
    evidence.write_bytes(b"memory bytes")
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "mode-detection-token")
    monkeypatch.setenv("VERDICT_HMAC_KEY_HEX", "ef" * 32)

    exit_code = main(
        [
            "init",
            str(evidence),
            "--case-id",
            "../escape",
            "--cases-dir",
            str(tmp_path / "cases"),
            "--mode",
            "cloud",
        ]
    )

    assert exit_code == 2
    assert not (tmp_path / "escape").exists()


def test_resume_reverify_approve_and_gc_lifecycle(tmp_path: Path, monkeypatch, capsys) -> None:
    evidence = tmp_path / "evidence.mem"
    evidence.write_bytes(b"memory bytes")
    cases_dir = tmp_path / "cases"
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "mode-detection-token")
    monkeypatch.setenv("VERDICT_HMAC_KEY_HEX", "34" * 32)
    assert main(
        [
            "init",
            str(evidence),
            "--case-id",
            "case-control",
            "--cases-dir",
            str(cases_dir),
            "--mode",
            "cloud",
        ]
    ) == 0
    capsys.readouterr()

    assert main(["resume", "case-control", "--cases-dir", str(cases_dir)]) == 0
    assert json.loads(capsys.readouterr().out)["resume"] == "ok"

    assert main(
        [
            "reverify",
            "case-control",
            "--cases-dir",
            str(cases_dir),
            "--mode",
            "cloud",
        ]
    ) == 0
    reverify = json.loads(capsys.readouterr().out)
    assert reverify["source_case_id"] == "case-control"
    assert (cases_dir / reverify["case_id"] / "ledger.jsonl").is_file()

    assert main(
        [
            "approve",
            "case-control",
            "finding-1",
            "--approver",
            "analyst",
            "--cases-dir",
            str(cases_dir),
        ]
    ) == 0
    assert json.loads(capsys.readouterr().out)["approved"] is True

    assert main(["gc", "--cases-dir", str(cases_dir)]) == 0
    gc = json.loads(capsys.readouterr().out)
    assert "case-control" in gc["cases"]


def test_package_check_reports_missing_and_writes_zip(tmp_path: Path, capsys) -> None:
    assert main(["package-check", "--root", str(tmp_path)]) == 1
    missing = json.loads(capsys.readouterr().out)
    assert "submission/execution-logs/case_001.jsonl" in missing["missing"]

    for rel_path in REQUIRED_DEVPOST_PATHS:
        path = tmp_path / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"artifact: {rel_path}\n", encoding="utf-8")
    output = tmp_path / "dist" / "verdict-devpost.zip"

    assert main(["package-check", "--root", str(tmp_path), "--output", str(output)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["ok"] is True
    assert output.is_file()


def test_run_case_records_unverifiable_conclusion_for_unsupported_evidence(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    evidence = tmp_path / "capture.pcap"
    evidence.write_bytes(b"pcap bytes")
    cases_dir = tmp_path / "cases"
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "mode-detection-token")
    monkeypatch.setenv("VERDICT_HMAC_KEY_HEX", "56" * 32)
    assert main(
        [
            "init",
            str(evidence),
            "--case-id",
            "case-unsupported",
            "--cases-dir",
            str(cases_dir),
            "--mode",
            "cloud",
        ]
    ) == 0
    capsys.readouterr()

    assert main(["run-case", "case-unsupported", "--cases-dir", str(cases_dir)]) == 0
    conclusion = json.loads(capsys.readouterr().out)
    ledger_lines = (cases_dir / "case-unsupported" / "ledger.jsonl").read_text().splitlines()

    assert conclusion["status"] == "UNVERIFIABLE"
    assert conclusion["playbook_steps_executed"] == ["unsupported_evidence_type"]
    assert json.loads(ledger_lines[-1])["event_type"] == "case_conclusion"


def test_run_case_memory_fails_closed_without_microsandbox_prerequisites(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    evidence = tmp_path / "memory.mem"
    evidence.write_bytes(b"memory bytes")
    cases_dir = tmp_path / "cases"
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "mode-detection-token")
    monkeypatch.setenv("VERDICT_HMAC_KEY_HEX", "78" * 32)
    monkeypatch.delenv("VERDICT_MICROSANDBOX_IMAGE", raising=False)
    assert main(
        [
            "init",
            str(evidence),
            "--case-id",
            "case-memory",
            "--cases-dir",
            str(cases_dir),
            "--mode",
            "cloud",
        ]
    ) == 0
    capsys.readouterr()

    assert main(["run-case", "case-memory", "--cases-dir", str(cases_dir)]) == 2
    ledger_lines = (cases_dir / "case-memory" / "ledger.jsonl").read_text().splitlines()

    assert len(ledger_lines) == 1


def test_doctor_reports_actionable_blockers(monkeypatch, capsys) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("SGLANG_BASE_URL", raising=False)
    monkeypatch.delenv("VERDICT_HMAC_KEY_HEX", raising=False)
    monkeypatch.delenv("VERDICT_HMAC_PASSPHRASE", raising=False)
    monkeypatch.delenv("VERDICT_MICROSANDBOX_IMAGE", raising=False)

    assert main(["doctor"]) == 1

    result = json.loads(capsys.readouterr().out)
    assert "mode_unconfigured" in result["blockers"]
    assert "hmac_key_unconfigured" in result["blockers"]
    assert "microsandbox_image_unpinned" in result["blockers"]


def test_doctor_accepts_explicit_cloud_mode(monkeypatch, capsys) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "mode-detection-token")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("SGLANG_BASE_URL", raising=False)

    assert main(["doctor", "--mode", "cloud"]) == 1

    result = json.loads(capsys.readouterr().out)
    assert result["mode"] == "CLOUD"
    assert "mode_unconfigured" not in result["blockers"]
