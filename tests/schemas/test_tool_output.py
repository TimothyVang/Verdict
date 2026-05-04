from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from blake3 import blake3

from verdict.schemas.tool_output import Artifact, ToolOutput


def test_invocation_hash_combines_name_version_args_evidence() -> None:
    artifact = Artifact(
        artifact_id="01HX0000000000000000000000",
        evidence_path=Path("/evidence/memory.raw"),
        artifact_type="process",
        raw_fields={"pid": 4},
    )
    evidence_hash = "e" * 64
    expected = blake3(
        b"vol3.windows.pslist\x00vol3 2.10.0\x00--pid\x004\x00" + evidence_hash.encode(),
    ).hexdigest()

    output = ToolOutput.from_invocation(
        tool_name="vol3.windows.pslist",
        tool_version="vol3 2.10.0",
        invocation_args=["--pid", "4"],
        evidence_hash=evidence_hash,
        stdout=b"process table",
        stderr=b"",
        exit_code=0,
        parsed_artifacts=[artifact],
    )

    assert output.invocation_hash == expected
    assert output.stdout_hash == sha256(b"process table").hexdigest()
    assert output.stderr_hash == sha256(b"").hexdigest()
    assert output.schema_version == 1
