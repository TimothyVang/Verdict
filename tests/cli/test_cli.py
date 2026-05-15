from __future__ import annotations

import json
from pathlib import Path

from verdict.cli.__main__ import main
from verdict.ledger.writer import LedgerWriter

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
    "submission/reports/case_001.pdf",
    "submission/reports/case_002.pdf",
    "submission/reports/case_003.pdf",
)


def _write_required_devpost_artifacts(root: Path, *, invalid_pdf: bool = False) -> None:
    for rel_path in REQUIRED_DEVPOST_PATHS:
        path = root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        if rel_path.endswith(".jsonl"):
            path.write_text(
                json.dumps(
                    {
                        "event_type": "case_init",
                        "langfuse_trace_id": "local-cli",
                        "langgraph_checkpoint_id": "case_init",
                        "ts_utc": "2026-05-09T00:00:00Z",
                    },
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
        elif rel_path.endswith(".pdf"):
            path.write_bytes(
                b"not a pdf\n" if invalid_pdf else b"%PDF-1.4\nxref\ntrailer\n%%EOF\n"
            )
        else:
            path.write_text(f"artifact: {rel_path}\n", encoding="utf-8")


def _append_finding_event(cases_dir: Path, case_id: str, key_hex: str) -> dict:
    return LedgerWriter(cases_dir / case_id / "ledger.jsonl", hmac_key=bytes.fromhex(key_hex)).write(
        {
            "entry_id": f"{case_id}:finding:finding-1:2026-05-13T00:00:00Z",
            "case_id": case_id,
            "finding_id": "finding-1",
            "event_type": "finding",
            "timestamp_utc": "2026-05-13T00:00:00Z",
            "mode_at_case_init": "CLOUD",
            "verifier_strategy_used": "local_parser_contested",
            "langfuse_session_id": case_id,
            "langfuse_trace_id": "local-cli",
            "langfuse_root_span_id": "local-cli-root",
            "langfuse_leaf_span_ids": [],
            "langgraph_thread_id": case_id,
            "langgraph_checkpoint_id": "finding:finding-1",
            "microsandbox_version": "not_invoked",
            "rootfs_sha256": "not_invoked",
            "tool_version": "verdict-cli",
            "kernel_version": "test-kernel",
            "output_files_sha256": {},
            "payload": {"finding_id": "finding-1", "status": "CONTESTED"},
        }
    )


def _append_case_conclusion_event(
    cases_dir: Path,
    case_id: str,
    key_hex: str,
    timestamp_utc: str,
) -> dict:
    return LedgerWriter(cases_dir / case_id / "ledger.jsonl", hmac_key=bytes.fromhex(key_hex)).write(
        {
            "entry_id": f"{case_id}:case_conclusion:{timestamp_utc}",
            "case_id": case_id,
            "finding_id": None,
            "event_type": "case_conclusion",
            "timestamp_utc": timestamp_utc,
            "mode_at_case_init": "CLOUD",
            "verifier_strategy_used": "local_parser_contested",
            "langfuse_session_id": case_id,
            "langfuse_trace_id": "local-cli",
            "langfuse_root_span_id": "local-cli-root",
            "langfuse_leaf_span_ids": [],
            "langgraph_thread_id": case_id,
            "langgraph_checkpoint_id": "case_conclusion",
            "microsandbox_version": "not_invoked",
            "rootfs_sha256": "not_invoked",
            "tool_version": "verdict-cli",
            "kernel_version": "test-kernel",
            "output_files_sha256": {},
            "payload": {"status": "UNVERIFIABLE"},
        }
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


def test_export_pdf_writes_analyst_report_file(tmp_path: Path, monkeypatch, capsys) -> None:
    evidence = tmp_path / "event.evtx"
    evidence.write_bytes(b"event bytes")
    cases_dir = tmp_path / "cases"
    output = tmp_path / "case-export.pdf"
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "mode-detection-token")
    monkeypatch.setenv("VERDICT_HMAC_KEY_HEX", "ce" * 32)
    assert main(
        [
            "init",
            str(evidence),
            "--case-id",
            "case-export-pdf",
            "--cases-dir",
            str(cases_dir),
        ]
    ) == 0
    capsys.readouterr()

    assert main(
        [
            "export",
            "case-export-pdf",
            "--cases-dir",
            str(cases_dir),
            "--format",
            "pdf",
            "--output",
            str(output),
        ]
    ) == 0

    assert output.read_bytes().startswith(b"%PDF-1.4")
    assert b"VERDICT Analyst Report" in output.read_bytes()


def test_export_rejects_case_id_path_traversal(tmp_path: Path, monkeypatch) -> None:
    cases_dir = tmp_path / "cases"
    monkeypatch.setenv("VERDICT_HMAC_KEY_HEX", "ce" * 32)

    assert main(["export", "../escape", "--cases-dir", str(cases_dir)]) == 2


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
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
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


def test_case_id_commands_reject_path_traversal_before_case_access(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    evidence = tmp_path / "evidence.evtx"
    evidence.write_bytes(b"event bytes")
    cases_dir = tmp_path / "cases"
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "mode-detection-token")
    monkeypatch.setenv("VERDICT_HMAC_KEY_HEX", "33" * 32)
    assert main(
        [
            "init",
            str(evidence),
            "--case-id",
            "escape",
            "--cases-dir",
            str(tmp_path),
            "--mode",
            "cloud",
        ]
    ) == 0
    capsys.readouterr()

    commands = [
        ["status", "../escape", "--cases-dir", str(cases_dir)],
        ["show", "../escape", "--cases-dir", str(cases_dir)],
        ["validate", "../escape", "--cases-dir", str(cases_dir)],
        ["resume", "../escape", "--cases-dir", str(cases_dir)],
        ["reverify", "../escape", "--cases-dir", str(cases_dir), "--mode", "cloud"],
        [
            "approve",
            "../escape",
            "finding-1",
            "--approver",
            "analyst",
            "--cases-dir",
            str(cases_dir),
        ],
        ["run-case", "../escape", "--cases-dir", str(cases_dir)],
        ["run-tool", "../escape", "mmls", "--cases-dir", str(cases_dir)],
    ]

    for command in commands:
        assert main(command) == 2
        assert "case_id" in capsys.readouterr().err


def test_resume_reverify_approve_and_gc_lifecycle(tmp_path: Path, monkeypatch, capsys) -> None:
    evidence = tmp_path / "evidence.mem"
    evidence.write_bytes(b"memory bytes")
    cases_dir = tmp_path / "cases"
    key_hex = "34" * 32
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "mode-detection-token")
    monkeypatch.setenv("VERDICT_HMAC_KEY_HEX", key_hex)
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

    finding_entry = _append_finding_event(cases_dir, "case-control", key_hex)
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
    approval = json.loads(capsys.readouterr().out)
    approval_entry = json.loads((cases_dir / "case-control" / "ledger.jsonl").read_text().splitlines()[-1])
    assert approval["approved"] is True
    assert approval_entry["payload"]["finding_entry_hash"] == finding_entry["entry_hash"]
    assert approval_entry["payload"]["finding_hmac_sig"] == finding_entry["hmac_sig"]

    assert main(["gc", "--cases-dir", str(cases_dir)]) == 0
    gc = json.loads(capsys.readouterr().out)
    assert "case-control" in gc["cases"]


def test_approve_rejects_nonexistent_finding(tmp_path: Path, monkeypatch, capsys) -> None:
    evidence = tmp_path / "evidence.mem"
    evidence.write_bytes(b"memory bytes")
    cases_dir = tmp_path / "cases"
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "mode-detection-token")
    monkeypatch.setenv("VERDICT_HMAC_KEY_HEX", "35" * 32)
    assert main(
        [
            "init",
            str(evidence),
            "--case-id",
            "case-no-finding",
            "--cases-dir",
            str(cases_dir),
            "--mode",
            "cloud",
        ]
    ) == 0
    capsys.readouterr()

    assert main(
        [
            "approve",
            "case-no-finding",
            "missing-finding",
            "--approver",
            "analyst",
            "--cases-dir",
            str(cases_dir),
        ]
    ) == 2
    ledger_events = [
        json.loads(line)["event_type"]
        for line in (cases_dir / "case-no-finding" / "ledger.jsonl").read_text().splitlines()
    ]

    assert ledger_events == ["case_init"]


def test_approve_rejects_superseded_finding(tmp_path: Path, monkeypatch, capsys) -> None:
    evidence = tmp_path / "evidence.mem"
    evidence.write_bytes(b"memory bytes")
    cases_dir = tmp_path / "cases"
    key_hex = "36" * 32
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "mode-detection-token")
    monkeypatch.setenv("VERDICT_HMAC_KEY_HEX", key_hex)
    assert main(
        [
            "init",
            str(evidence),
            "--case-id",
            "case-superseded",
            "--cases-dir",
            str(cases_dir),
            "--mode",
            "cloud",
        ]
    ) == 0
    capsys.readouterr()
    _append_finding_event(cases_dir, "case-superseded", key_hex)
    _append_case_conclusion_event(
        cases_dir,
        "case-superseded",
        key_hex,
        "2026-05-13T00:01:00Z",
    )
    _append_case_conclusion_event(
        cases_dir,
        "case-superseded",
        key_hex,
        "2026-05-13T00:02:00Z",
    )

    assert main(
        [
            "approve",
            "case-superseded",
            "finding-1",
            "--approver",
            "analyst",
            "--cases-dir",
            str(cases_dir),
        ]
    ) == 2
    captured = capsys.readouterr()
    ledger_events = [
        json.loads(line)["event_type"]
        for line in (cases_dir / "case-superseded" / "ledger.jsonl").read_text().splitlines()
    ]

    assert "cannot approve superseded finding: finding-1" in captured.err
    assert ledger_events == ["case_init", "finding", "case_conclusion", "case_conclusion"]


def test_package_check_reports_missing_and_writes_zip(tmp_path: Path, capsys) -> None:
    assert main(["package-check", "--root", str(tmp_path)]) == 1
    missing = json.loads(capsys.readouterr().out)
    assert "submission/execution-logs/case_001.jsonl" in missing["missing"]

    _write_required_devpost_artifacts(tmp_path)
    output = tmp_path / "dist" / "verdict-devpost.zip"

    assert main(["package-check", "--root", str(tmp_path), "--output", str(output)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["ok"] is True
    assert output.is_file()


def test_package_check_rejects_malformed_pdf_report(tmp_path: Path, capsys) -> None:
    _write_required_devpost_artifacts(tmp_path, invalid_pdf=True)

    assert main(["package-check", "--root", str(tmp_path)]) == 1

    result = json.loads(capsys.readouterr().out)
    assert "invalid_pdf:submission/reports/case_001.pdf" in result["invalid"]


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


def test_investigate_initializes_runs_validates_and_exports_without_mid_case_prompt(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    evidence = tmp_path / "capture.pcap"
    evidence.write_bytes(b"pcap bytes")
    cases_dir = tmp_path / "cases"
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "mode-detection-token")
    monkeypatch.setenv("VERDICT_HMAC_KEY_HEX", "57" * 32)

    exit_code = main(
        [
            "investigate",
            str(evidence),
            "--case-id",
            "case-autonomous",
            "--cases-dir",
            str(cases_dir),
            "--mode",
            "cloud",
        ]
    )

    assert exit_code == 0
    result = json.loads(capsys.readouterr().out)
    case_dir = cases_dir / "case-autonomous"
    ledger_lines = (case_dir / "ledger.jsonl").read_text().splitlines()

    assert result["case_id"] == "case-autonomous"
    assert result["status"] == "UNVERIFIABLE"
    assert result["ledger_valid"] is True
    assert result["human_approval_required"] is True
    assert result["approval_command"] == (
        "verdict approve case-autonomous <finding_id> --approver <name>"
    )
    assert result["exports"]["execution_logs"].endswith("execution-log.jsonl")
    assert result["exports"]["html_report"].endswith("analyst-report.html")
    assert len(result["export_sha256"]["execution_logs"]) == 64
    assert len(result["export_sha256"]["html_report"]) == 64
    assert (case_dir / "exports" / "execution-log.jsonl").is_file()
    assert (case_dir / "exports" / "analyst-report.html").is_file()
    assert [json.loads(line)["event_type"] for line in ledger_lines] == [
        "case_init",
        "case_conclusion",
    ]


def test_investigate_records_unverifiable_when_local_tooling_blocks_execution(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    evidence = tmp_path / "memory.mem"
    evidence.write_bytes(b"memory bytes")
    cases_dir = tmp_path / "cases"
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "mode-detection-token")
    monkeypatch.setenv("VERDICT_HMAC_KEY_HEX", "58" * 32)
    monkeypatch.delenv("VERDICT_MICROSANDBOX_IMAGE", raising=False)

    exit_code = main(
        [
            "investigate",
            str(evidence),
            "--case-id",
            "case-tooling-blocked",
            "--cases-dir",
            str(cases_dir),
            "--mode",
            "cloud",
        ]
    )

    assert exit_code == 0
    result = json.loads(capsys.readouterr().out)
    ledger_lines = (cases_dir / "case-tooling-blocked" / "ledger.jsonl").read_text().splitlines()
    conclusion = json.loads(ledger_lines[-1])["payload"]

    assert result["status"] == "UNVERIFIABLE"
    assert result["autonomy_blocker"] == "local_tooling"
    assert conclusion["status"] == "UNVERIFIABLE"
    assert conclusion["playbook_steps_executed"] == ["autonomous_driver_blocked"]
    assert "Autonomous investigation could not complete local execution" in conclusion["rationale"]
    assert (cases_dir / "case-tooling-blocked" / "exports" / "execution-log.jsonl").is_file()


def test_investigate_writes_exports_to_explicit_directory(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    evidence = tmp_path / "capture.pcap"
    evidence.write_bytes(b"pcap bytes")
    cases_dir = tmp_path / "cases"
    export_dir = tmp_path / "operator-exports"
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "mode-detection-token")
    monkeypatch.setenv("VERDICT_HMAC_KEY_HEX", "59" * 32)

    assert main(
        [
            "investigate",
            str(evidence),
            "--case-id",
            "case-export-dir",
            "--cases-dir",
            str(cases_dir),
            "--mode",
            "cloud",
            "--export-dir",
            str(export_dir),
        ]
    ) == 0

    result = json.loads(capsys.readouterr().out)

    assert result["exports"] == {
        "execution_logs": str(export_dir / "execution-log.jsonl"),
        "html_report": str(export_dir / "analyst-report.html"),
        "manifest": str(export_dir / "manifest.json"),
    }
    assert (export_dir / "execution-log.jsonl").is_file()
    assert (export_dir / "analyst-report.html").is_file()
    assert (export_dir / "manifest.json").is_file()

    manifest = json.loads((export_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["case_id"] == "case-export-dir"
    assert manifest["source_ledger"] == {
        "path": str(cases_dir / "case-export-dir" / "ledger.jsonl"),
        "sha256": result["export_manifest"]["source_ledger_sha256"],
    }
    assert manifest["artifacts"] == {
        "execution_logs": {
            "path": str(export_dir / "execution-log.jsonl"),
            "sha256": result["export_sha256"]["execution_logs"],
        },
        "html_report": {
            "path": str(export_dir / "analyst-report.html"),
            "sha256": result["export_sha256"]["html_report"],
        },
    }
    assert len(result["export_sha256"]["manifest"]) == 64


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


def test_doctor_reports_actionable_blockers(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
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


def test_doctor_accepts_explicit_cloud_mode(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "mode-detection-token")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("SGLANG_BASE_URL", raising=False)
    monkeypatch.delenv("VERDICT_HMAC_KEY_HEX", raising=False)
    monkeypatch.delenv("VERDICT_HMAC_PASSPHRASE", raising=False)
    monkeypatch.delenv("VERDICT_MICROSANDBOX_IMAGE", raising=False)

    assert main(["doctor", "--mode", "cloud"]) == 1

    result = json.loads(capsys.readouterr().out)
    assert result["mode"] == "CLOUD"
    assert "mode_unconfigured" not in result["blockers"]


def test_doctor_loads_local_env_without_printing_secret(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    secret = "secret-cloud-key"
    (tmp_path / ".env").write_text(
        f"ANTHROPIC_API_KEY={secret}\nVERDICT_HMAC_KEY_HEX={'ab' * 32}\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("VERDICT_HMAC_KEY_HEX", raising=False)
    monkeypatch.delenv("VERDICT_HMAC_PASSPHRASE", raising=False)
    monkeypatch.delenv("VERDICT_MICROSANDBOX_IMAGE", raising=False)

    assert main(["doctor", "--mode", "cloud"]) == 1

    output = capsys.readouterr().out
    result = json.loads(output)
    assert result["mode"] == "CLOUD"
    assert "mode_unconfigured" not in result["blockers"]
    assert "hmac_key_unconfigured" not in result["blockers"]
    assert secret not in output
