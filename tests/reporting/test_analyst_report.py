from __future__ import annotations

from verdict.reporting.analyst_report import (
    build_analyst_report_html,
    build_analyst_report_pdf,
)


def _report_entries() -> list[dict]:
    return [
        {
            "entry_hash": "case-init-hash",
            "event_type": "case_init",
            "hmac_sig": "hmac-case-init",
            "langgraph_checkpoint_id": "case_init",
            "payload": {
                "evidence_items": [
                    {
                        "path": "C:/evidence/disk.E01",
                        "sha256_at_init": "a" * 64,
                        "evidence_type": "disk_image",
                        "size_bytes": 4096,
                    }
                ]
            },
            "timestamp_utc": "2026-05-09T18:46:01Z",
        },
        {
            "entry_hash": "tool-hash",
            "event_type": "tool_call",
            "hmac_sig": "hmac-tool",
            "langgraph_checkpoint_id": "tool_call:icat",
            "output_files_sha256": {"outputs/icat.json": "b" * 64},
            "payload": {
                "artifact_ids": ["icat:artifact-1"],
                "exit_code": 0,
                "invocation_args": ["/evidence/disk.E01", "128986-128-4"],
                "parsed_artifacts": [
                    {
                        "artifact_id": "icat:artifact-1",
                        "artifact_type": "powershell_transcript_command",
                        "evidence_path": "C:/evidence/disk.E01",
                        "raw_fields": {
                            "artifact_path": "C:/evidence/disk.E01#powershell_transcript_command:0",
                            "executable": "rundll32.exe",
                            "username": "shieldbase\\cbarton-a",
                        },
                    }
                ],
                "stdout_hash": "c" * 64,
                "tool_name": "icat",
                "tool_output_path": "cases/case_001/outputs/icat.json",
            },
            "timestamp_utc": "2026-05-09T18:50:08Z",
        },
        {
            "entry_hash": "finding-hash",
            "event_type": "finding",
            "finding_id": "case_001:lolbin:rundll32",
            "hmac_sig": "hmac-finding",
            "langgraph_checkpoint_id": "finding:case_001_lolbin_rundll32",
            "payload": {
                "artifact_classes": ["POWERSHELL_TRANSCRIPT", "PREFETCH"],
                "artifact_paths": [
                    "C:/evidence/disk.E01#powershell_transcript_command:0",
                    "C:/evidence/disk.E01#prefetch_listing_entry:0",
                ],
                "caveats_acknowledged": ["PREFETCH_SSD_DISABLED"],
                "finding_id": "case_001:lolbin:rundll32",
                "mitre_technique": "T1218.011",
                "rationale": "Evidence consistent with rundll32 LOLBin execution.",
                "review_state": "DRAFT",
                "status": "CONTESTED",
                "supporting_tool_outputs": [
                    {
                        "artifact_ids": ["icat:artifact-1"],
                        "event_type": "tool_call",
                        "tool_name": "icat",
                    }
                ],
            },
            "timestamp_utc": "2026-05-09T18:51:42Z",
        },
        {
            "entry_hash": "conclusion-hash",
            "event_type": "case_conclusion",
            "hmac_sig": "hmac-conclusion",
            "langgraph_checkpoint_id": "case_conclusion",
            "payload": {
                "status": "EVIL_FOUND",
                "rationale": "Evidence consistent with rundll32 LOLBin execution.",
                "playbook_steps_executed": ["mmls", "fsstat", "fls", "icat"],
            },
            "timestamp_utc": "2026-05-09T18:51:49Z",
        },
    ]


def test_analyst_html_report_contains_review_citations_and_evidence_figures() -> None:
    html = build_analyst_report_html("case_001", _report_entries())

    assert "VERDICT Analyst Report" in html
    assert "Human Review Checklist" in html
    assert "Executive Summary" in html
    assert "CIT-0001" in html
    assert "Evidence Figure" in html
    assert "<svg" in html
    assert "icat:artifact-1" in html
    assert "PREFETCH_SSD_DISABLED" in html
    assert "Evidence consistent with rundll32 LOLBin execution." in html
    assert "C:/evidence/" not in html
    assert "disk.E01#powershell_transcript_command:0" in html


def test_analyst_pdf_report_is_valid_pdf_with_review_and_citation_text() -> None:
    pdf = build_analyst_report_pdf("case_001", _report_entries())

    assert pdf.startswith(b"%PDF-1.4")
    assert b"VERDICT Analyst Report" in pdf
    assert b"Human Review Checklist" in pdf
    assert b"CIT-0001" in pdf
    assert b"Evidence Figure" in pdf
    assert b"icat:artifact-1" in pdf


def test_professional_pdf_uses_writeup_sections_by_default() -> None:
    pdf = build_analyst_report_pdf("case_001", _report_entries())

    assert b"VERDICT DFIR Analyst Report" in pdf
    assert b"Executive Assessment" in pdf
    assert b"Key Findings" in pdf
    assert b"Evidence And Citation Summary" in pdf
    assert b"Ledger Evidence Appendix" in pdf
    assert b"Chain Of Custody Appendix" in pdf


def test_professional_pdf_abbreviates_large_pid_lists() -> None:
    entries = _report_entries()
    pids = ", ".join(str(pid) for pid in range(1000, 1060))
    entries[-1]["payload"]["rationale"] = (
        "Evidence is consistent with hidden process activity: "
        f"psscan PID(s) absent from pslist: {pids}."
    )

    pdf = build_analyst_report_pdf("case_pid", entries)

    assert pids.encode() not in pdf
    assert b"additional" in pdf
    assert b"PIDs omitted" in pdf


def test_professional_pdf_separates_superseded_run_history() -> None:
    entries = _report_entries()
    entries.insert(
        2,
        {
            "entry_hash": "old-conclusion-hash",
            "event_type": "case_conclusion",
            "hmac_sig": "old-hmac-conclusion",
            "langgraph_checkpoint_id": "case_conclusion",
            "payload": {
                "status": "UNVERIFIABLE",
                "rationale": "Parser produced no structured artifacts for required tool(s).",
            },
            "timestamp_utc": "2026-05-09T18:49:00Z",
        },
    )

    pdf = build_analyst_report_pdf("case_001", entries)

    assert b"Superseded Run History" in pdf
    assert b"Latest run evidence" in pdf
    assert b"UNVERIFIABLE" in pdf
