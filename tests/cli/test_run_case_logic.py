from __future__ import annotations

from pathlib import Path

from verdict.cli.__main__ import _build_case_conclusion, _filesystem_partition_offsets
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
