from __future__ import annotations

from pathlib import Path

from verdict.cli import __main__ as cli
from verdict.cli.__main__ import (
    _build_case_conclusion,
    _filesystem_partition_offsets,
    _powershell_transcript_metadata_addresses,
)
from verdict.schemas.artifact_class import ArtifactClass
from verdict.schemas.caveat_id import CaveatID
from verdict.schemas.tool_output import ToolOutput
from verdict.tools.parsers import parse_tool_stdout


def test_disk_offsets_are_derived_from_supported_mmls_partitions(tmp_path: Path) -> None:
    evidence = tmp_path / "disk.E01"
    stdout = (
        b"DOS Partition Table\n"
        b"001:  -------   0000000000   0000002047   0000002048   Unallocated\n"
        b"002:  000:000   0000002048   0001023999   0001021952   NTFS / exFAT (0x07)\n"
    )
    parsed = parse_tool_stdout("mmls", evidence_path=evidence, stdout=stdout)
    output = ToolOutput.from_invocation(
        tool_name="mmls",
        tool_version="mmls",
        invocation_args=[str(evidence)],
        evidence_hash="a" * 64,
        stdout=stdout,
        stderr=b"",
        exit_code=0,
        parsed_artifacts=parsed.artifacts,
    )

    assert _filesystem_partition_offsets(output) == [2048]


def test_missing_supported_mmls_partition_marks_offset_unverifiable(
    tmp_path: Path,
) -> None:
    evidence = tmp_path / "disk.E01"
    stdout = (
        b"DOS Partition Table\n"
        b"001:  -------   0000000000   0000002047   0000002048   Unallocated\n"
    )
    parsed = parse_tool_stdout("mmls", evidence_path=evidence, stdout=stdout)
    output = ToolOutput.from_invocation(
        tool_name="mmls",
        tool_version="mmls",
        invocation_args=[str(evidence)],
        evidence_hash="a" * 64,
        stdout=stdout,
        stderr=b"",
        exit_code=0,
        parsed_artifacts=parsed.artifacts,
    )

    offsets, missing_step = cli._disk_partition_offsets_or_missing_step(output)

    assert offsets == []
    assert missing_step == "disk_partition_offset_not_found"


def test_transcript_candidates_preserve_fls_order_and_cap_search(tmp_path: Path) -> None:
    evidence = tmp_path / "disk.E01"
    stdout = b"".join(
        f"++++ r/r {metadata}-128-4:\tPowerShell_transcript.BASE-WKSTN-01.x.txt\n".encode()
        for metadata in [68042, 61060, 128986, 29155, 68054, 130449, 61754, 28091, 27931, 28195, 10883]
    )
    parsed = parse_tool_stdout("fls", evidence_path=evidence, stdout=stdout)
    output = ToolOutput.from_invocation(
        tool_name="fls",
        tool_version="fls",
        invocation_args=[str(evidence)],
        evidence_hash="a" * 64,
        stdout=stdout,
        stderr=b"",
        exit_code=0,
        parsed_artifacts=parsed.artifacts,
    )

    assert _powershell_transcript_metadata_addresses(output) == [
        "68042-128-4",
        "61060-128-4",
        "128986-128-4",
        "29155-128-4",
        "68054-128-4",
        "130449-128-4",
        "61754-128-4",
        "28091-128-4",
        "27931-128-4",
        "28195-128-4",
    ]


def test_non_divergent_memory_triage_remains_unverifiable_without_verifier(
    tmp_path: Path,
) -> None:
    evidence = tmp_path / "memory.raw"
    stdout = b"PID\tPPID\tImageFileName\n4\t0\tSystem\n612\t500\tlsass.exe\n"
    pslist = parse_tool_stdout("vol3.pslist", evidence_path=evidence, stdout=stdout)
    psscan = parse_tool_stdout("vol3.psscan", evidence_path=evidence, stdout=stdout)
    outputs = [
        ToolOutput.from_invocation(
            tool_name="vol3.windows.pslist",
            tool_version="vol3",
            invocation_args=["-f", str(evidence), "windows.pslist"],
            evidence_hash="b" * 64,
            stdout=stdout,
            stderr=b"",
            exit_code=0,
            parsed_artifacts=pslist.artifacts,
        ),
        ToolOutput.from_invocation(
            tool_name="vol3.windows.psscan",
            tool_version="vol3",
            invocation_args=["-f", str(evidence), "windows.psscan"],
            evidence_hash="b" * 64,
            stdout=stdout,
            stderr=b"",
            exit_code=0,
            parsed_artifacts=psscan.artifacts,
        ),
    ]

    conclusion = _build_case_conclusion(
        manifest={"items": [{"path": str(evidence), "sha256_at_init": "b" * 64}]},
        outputs=outputs,
        playbook_steps=["vol3.pslist", "vol3.psscan"],
        unsupported_types=set(),
    )

    assert conclusion.status == "UNVERIFIABLE"
    assert "verifier/finding workflow" in conclusion.rationale


def test_header_only_pslist_still_supports_psscan_divergence(
    tmp_path: Path,
) -> None:
    evidence = tmp_path / "memory.raw"
    pslist_stdout = (
        b"Volatility 3 Framework 2.28.0\n\n"
        b"PID\tPPID\tImageFileName\tOffset(V)\tThreads\tHandles\tSessionId\tWow64\t"
        b"CreateTime\tExitTime\tFile output\n"
    )
    psscan_stdout = (
        b"PID\tPPID\tImageFileName\tOffset(V)\tThreads\n"
        b"4\t0\tSystem\t0xfffff800\t160\n"
    )
    pslist = parse_tool_stdout("vol3.pslist", evidence_path=evidence, stdout=pslist_stdout)
    psscan = parse_tool_stdout("vol3.psscan", evidence_path=evidence, stdout=psscan_stdout)
    outputs = [
        ToolOutput.from_invocation(
            tool_name="vol3.windows.pslist",
            tool_version="vol3",
            invocation_args=["-f", str(evidence), "windows.pslist"],
            evidence_hash="b" * 64,
            stdout=pslist_stdout,
            stderr=b"",
            exit_code=0,
            parsed_artifacts=pslist.artifacts,
        ),
        ToolOutput.from_invocation(
            tool_name="vol3.windows.psscan",
            tool_version="vol3",
            invocation_args=["-f", str(evidence), "windows.psscan"],
            evidence_hash="b" * 64,
            stdout=psscan_stdout,
            stderr=b"",
            exit_code=0,
            parsed_artifacts=psscan.artifacts,
        ),
    ]

    conclusion = _build_case_conclusion(
        manifest={"items": [{"path": str(evidence), "sha256_at_init": "b" * 64}]},
        outputs=outputs,
        playbook_steps=["vol3.pslist", "vol3.psscan"],
        unsupported_types=set(),
    )

    assert conclusion.status == "EVIL_FOUND"
    assert "psscan PID(s) absent from pslist: 4" in conclusion.rationale


def test_case_level_indicator_detects_psscan_divergence(
    tmp_path: Path,
) -> None:
    evidence = tmp_path / "memory.raw"
    pslist_stdout = b"PID\tPPID\tImageFileName\n4\t0\tSystem\n"
    psscan_stdout = b"PID\tPPID\tImageFileName\n4\t0\tSystem\n612\t500\tlsass.exe\n"
    pslist = parse_tool_stdout("vol3.pslist", evidence_path=evidence, stdout=pslist_stdout)
    psscan = parse_tool_stdout("vol3.psscan", evidence_path=evidence, stdout=psscan_stdout)
    outputs = [
        ToolOutput.from_invocation(
            tool_name="vol3.windows.pslist",
            tool_version="vol3",
            invocation_args=["-f", str(evidence), "windows.pslist"],
            evidence_hash="b" * 64,
            stdout=pslist_stdout,
            stderr=b"",
            exit_code=0,
            parsed_artifacts=pslist.artifacts,
        ),
        ToolOutput.from_invocation(
            tool_name="vol3.windows.psscan",
            tool_version="vol3",
            invocation_args=["-f", str(evidence), "windows.psscan"],
            evidence_hash="b" * 64,
            stdout=psscan_stdout,
            stderr=b"",
            exit_code=0,
            parsed_artifacts=psscan.artifacts,
        ),
    ]

    assert cli._has_case_level_indicator(outputs) is True


def test_autonomous_blocker_classification_does_not_downgrade_evidence_integrity() -> None:
    assert cli._is_autonomous_local_tooling_blocker(
        cli.CliError("microsandbox is required for forensic tool execution")
    ) is True
    assert cli._is_autonomous_local_tooling_blocker(
        cli.CliError("VERDICT_MICROSANDBOX_IMAGE must be pinned as IMAGE@sha256:<digest>")
    ) is True
    assert cli._is_autonomous_local_tooling_blocker(
        cli.CliError("evidence hash mismatch before tool execution: /evidence/memory.mem")
    ) is False


def test_partition_image_fallback_does_not_treat_mmls_probe_as_terminal_failure(
    tmp_path: Path,
) -> None:
    evidence = tmp_path / "cdrive.E01"
    fsstat_stdout = b"FILE SYSTEM INFORMATION\nFile System Type: NTFS\n"
    fls_stdout = b"r/r 42-128-1:\tWindows/System32/cmd.exe\n"
    fsstat = parse_tool_stdout("fsstat", evidence_path=evidence, stdout=fsstat_stdout)
    fls = parse_tool_stdout("fls", evidence_path=evidence, stdout=fls_stdout)
    outputs = [
        ToolOutput.from_invocation(
            tool_name="mmls",
            tool_version="mmls",
            invocation_args=[str(evidence)],
            evidence_hash="c" * 64,
            stdout=b"",
            stderr=b"",
            exit_code=1,
            parsed_artifacts=[],
        ),
        ToolOutput.from_invocation(
            tool_name="fsstat",
            tool_version="fsstat",
            invocation_args=[str(evidence)],
            evidence_hash="c" * 64,
            stdout=fsstat_stdout,
            stderr=b"",
            exit_code=0,
            parsed_artifacts=fsstat.artifacts,
        ),
        ToolOutput.from_invocation(
            tool_name="fls",
            tool_version="fls",
            invocation_args=[str(evidence)],
            evidence_hash="c" * 64,
            stdout=fls_stdout,
            stderr=b"",
            exit_code=0,
            parsed_artifacts=fls.artifacts,
        ),
    ]

    conclusion = _build_case_conclusion(
        manifest={"items": [{"path": str(evidence), "sha256_at_init": "c" * 64}]},
        outputs=outputs,
        playbook_steps=["mmls", "mmls_partition_table_unavailable", "fsstat", "fls"],
        unsupported_types=set(),
    )

    assert conclusion.status == "UNVERIFIABLE"
    assert "mmls exited" not in conclusion.rationale
    assert "first-pass SIFT triage completed" in conclusion.rationale


def test_lolbin_transcript_and_prefetch_outputs_build_schema_valid_finding(
    tmp_path: Path,
) -> None:
    evidence = tmp_path / "disk.E01"
    transcript_stdout = b'PS>CommandInvocation(rundll32.exe): "rundll32.exe"\n'
    prefetch_stdout = (
        b"C:\\WINDOWS\\Prefetch\\RUNDLL32.EXE-23EA2E5B.pf                  "
        b"2018-05-08T14:05:01.7096756Z 2018-05-08T14:05:01.7096756Z\n"
    )
    transcript = parse_tool_stdout("icat", evidence_path=evidence, stdout=transcript_stdout)
    prefetch = parse_tool_stdout("icat", evidence_path=evidence, stdout=prefetch_stdout)
    outputs = [
        ToolOutput.from_invocation(
            tool_name="icat",
            tool_version="icat",
            invocation_args=[str(evidence), "128986-128-4"],
            evidence_hash="d" * 64,
            stdout=transcript_stdout,
            stderr=b"",
            exit_code=0,
            parsed_artifacts=transcript.artifacts,
        ),
        ToolOutput.from_invocation(
            tool_name="icat",
            tool_version="icat",
            invocation_args=[str(evidence), "25320-128-4"],
            evidence_hash="d" * 64,
            stdout=prefetch_stdout,
            stderr=b"",
            exit_code=0,
            parsed_artifacts=prefetch.artifacts,
        ),
    ]

    findings = cli._build_lolbin_findings(
        case_id="case-001",
        manifest={"items": [{"path": str(evidence), "sha256_at_init": "d" * 64}]},
        outputs=outputs,
    )
    conclusion = _build_case_conclusion(
        manifest={"items": [{"path": str(evidence), "sha256_at_init": "d" * 64}]},
        outputs=outputs,
        playbook_steps=["icat:powershell_transcript:128986-128-4", "icat:powershell_transcript:25320-128-4"],
        unsupported_types=set(),
        findings=findings,
    )

    assert len(findings) == 1
    finding = findings[0]
    assert finding.mitre_technique == "T1218.011"
    assert finding.artifact_classes == [ArtifactClass.POWERSHELL_TRANSCRIPT, ArtifactClass.PREFETCH]
    assert finding.caveats_acknowledged == [CaveatID.PREFETCH_SSD_DISABLED]
    assert finding.status == "CONTESTED"
    assert conclusion.status == "EVIL_FOUND"
    assert "Evidence consistent with rundll32" in conclusion.rationale
