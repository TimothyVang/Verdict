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
