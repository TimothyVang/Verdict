from __future__ import annotations

from pathlib import Path

from verdict.tools.parsers import parse_tool_stdout


def test_vol3_info_parser_extracts_memory_metadata(tmp_path: Path) -> None:
    evidence = tmp_path / "memory.raw"
    stdout = b"Volatility 3 Framework 2.28.0\nVariable\tValue\nIs64Bit\tTrue\nNtBuildLab\t19041\n"

    parsed = parse_tool_stdout("vol3.info", evidence_path=evidence, stdout=stdout)

    assert parsed.warnings == []
    assert len(parsed.artifacts) == 1
    artifact = parsed.artifacts[0]
    assert artifact.artifact_type == "memory_image_info"
    assert artifact.raw_fields["is64bit"] == "True"
    assert artifact.raw_fields["ntbuildlab"] == "19041"


def test_vol3_process_parsers_extract_pids(tmp_path: Path) -> None:
    evidence = tmp_path / "memory.raw"
    stdout = (
        b"PID\tPPID\tImageFileName\tOffset(V)\tThreads\n"
        b"4\t0\tSystem\t0xfffff800\t160\n"
        b"612\t500\tlsass.exe\t0xfffff900\t12\n"
    )

    pslist = parse_tool_stdout("vol3.pslist", evidence_path=evidence, stdout=stdout)
    psscan = parse_tool_stdout("vol3.psscan", evidence_path=evidence, stdout=stdout)

    assert [artifact.raw_fields["pid"] for artifact in pslist.artifacts] == [4, 612]
    assert pslist.artifacts[1].artifact_type == "process_listing"
    assert psscan.artifacts[1].artifact_type == "process_scan"
    assert psscan.artifacts[1].raw_fields["image_file_name"] == "lsass.exe"


def test_vol3_process_parser_records_header_only_table(tmp_path: Path) -> None:
    evidence = tmp_path / "memory.raw"
    stdout = (
        b"Volatility 3 Framework 2.28.0\n\n"
        b"PID\tPPID\tImageFileName\tOffset(V)\tThreads\tHandles\tSessionId\tWow64\t"
        b"CreateTime\tExitTime\tFile output\n"
    )

    parsed = parse_tool_stdout("vol3.pslist", evidence_path=evidence, stdout=stdout)

    assert parsed.warnings == []
    assert len(parsed.artifacts) == 1
    assert parsed.artifacts[0].artifact_type == "process_listing_summary"
    assert parsed.artifacts[0].raw_fields == {
        "headers": [
            "PID",
            "PPID",
            "ImageFileName",
            "Offset(V)",
            "Threads",
            "Handles",
            "SessionId",
            "Wow64",
            "CreateTime",
            "ExitTime",
            "File output",
        ],
        "row_count": 0,
    }


def test_sleuthkit_parsers_extract_disk_artifacts(tmp_path: Path) -> None:
    evidence = tmp_path / "disk.E01"

    mmls = parse_tool_stdout(
        "mmls",
        evidence_path=evidence,
        stdout=(
            b"DOS Partition Table\n"
            b"000:  Meta      0000000000   0000000000   0000000001   Primary Table (#0)\n"
            b"002:  000:000   0000002048   0001023999   0001021952   NTFS / exFAT (0x07)\n"
        ),
    )
    fsstat = parse_tool_stdout(
        "fsstat",
        evidence_path=evidence,
        stdout=b"FILE SYSTEM INFORMATION\nFile System Type: NTFS\nVolume Serial Number: 1234\n",
    )
    fls = parse_tool_stdout(
        "fls",
        evidence_path=evidence,
        stdout=b"r/r 4-128-1: $AttrDef\nd/d 256: Users\nr/r * 1024: deleted.exe\n",
    )

    assert mmls.artifacts[1].raw_fields["start_sector"] == 2048
    assert fsstat.artifacts[0].raw_fields["file_system_type"] == "NTFS"
    assert fls.artifacts[2].raw_fields == {
        "file_type": "r/r",
        "deleted": True,
        "metadata_address": "1024",
        "name": "deleted.exe",
    }


def test_fls_parser_accepts_sleuthkit_edge_entry_types(tmp_path: Path) -> None:
    evidence = tmp_path / "disk.E01"

    parsed = parse_tool_stdout(
        "fls",
        evidence_path=evidence,
        stdout=b"-/r 7: orphaned-name\nr/- 8: nameless-metadata\nV/V 9: $Virtual\n",
    )

    assert [artifact.raw_fields["file_type"] for artifact in parsed.artifacts] == [
        "-/r",
        "r/-",
        "V/V",
    ]


def test_fls_parser_accepts_recursive_indentation(tmp_path: Path) -> None:
    parsed = parse_tool_stdout(
        "fls",
        evidence_path=tmp_path / "disk.E01",
        stdout=b"++++ r/r 128986-128-4:\tPowerShell_transcript.BASE-WKSTN-01.hV5HIEeg.txt\n",
    )

    assert parsed.artifacts[0].raw_fields == {
        "file_type": "r/r",
        "deleted": False,
        "metadata_address": "128986-128-4",
        "name": "PowerShell_transcript.BASE-WKSTN-01.hV5HIEeg.txt",
    }


def test_fls_parser_extracts_lolbin_prefetch_entries(tmp_path: Path) -> None:
    parsed = parse_tool_stdout(
        "fls",
        evidence_path=tmp_path / "disk.E01",
        stdout=b"++++ r/r 18653-128-4:\tRUNDLL32.EXE-05989D94.pf\n",
    )

    prefetch = [
        artifact
        for artifact in parsed.artifacts
        if artifact.artifact_type == "prefetch_listing_entry"
    ]
    assert len(prefetch) == 1
    assert prefetch[0].raw_fields == {
        "executable": "rundll32.exe",
        "prefetch_name": "RUNDLL32.EXE-05989D94.pf",
        "metadata_address": "18653-128-4",
        "artifact_path": f"{tmp_path / 'disk.E01'}#fls_prefetch:18653-128-4",
    }


def test_vol3_unsatisfied_requirements_do_not_parse_as_artifacts(tmp_path: Path) -> None:
    parsed = parse_tool_stdout(
        "vol3.info",
        evidence_path=tmp_path / "memory.mem",
        stdout=(
            b"Volatility 3 Framework 2.28.0\n\n"
            b"Unsatisfied requirement plugins.Info.kernel.symbol_table_name: \n\n"
            b"A symbol table requirement was not fulfilled.\n"
        ),
    )

    assert parsed.artifacts == []
    assert "vol3 reported unsatisfied requirements" in parsed.warnings


def test_icat_parser_extracts_lolbin_transcript_and_prefetch_artifacts(tmp_path: Path) -> None:
    parsed = parse_tool_stdout(
        "icat",
        evidence_path=tmp_path / "disk.E01",
        stdout=(
            b"Windows PowerShell transcript start\n"
            b"Start time: 20191226104349\n"
            b"Username: shieldbase\\cbarton-a\n"
            b'PS>CommandInvocation(rundll32.exe): "rundll32.exe"\n'
            b"C:\\WINDOWS\\Prefetch\\RUNDLL32.EXE-23EA2E5B.pf                  "
            b"2018-05-08T14:05:01.7096756Z 2018-05-08T14:05:01.7096756Z\n"
        ),
    )

    assert [artifact.artifact_type for artifact in parsed.artifacts] == [
        "powershell_transcript_command",
        "prefetch_listing_entry",
    ]
    assert parsed.artifacts[0].raw_fields["executable"] == "rundll32.exe"
    assert parsed.artifacts[1].raw_fields["executable"] == "rundll32.exe"
