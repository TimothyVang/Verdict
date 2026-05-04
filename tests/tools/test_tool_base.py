from __future__ import annotations

from pathlib import Path

from blake3 import blake3

from verdict.schemas.tool_output import Artifact, ToolOutput
from verdict.tools.base import ToolWrapper


class ProcessListingWrapper(ToolWrapper):
    tool_name = "vol3.windows.pslist"
    tool_version = "vol3 2.10.0"

    def run(self, *, invocation_args: list[str], evidence_hash: str) -> ToolOutput:
        return ToolOutput.from_invocation(
            tool_name=self.tool_name,
            tool_version=self.tool_version,
            invocation_args=invocation_args,
            evidence_hash=evidence_hash,
            stdout=b"pid 4 System",
            stderr=b"",
            exit_code=0,
            parsed_artifacts=[
                Artifact(
                    artifact_id="01HX0000000000000000000000",
                    evidence_path=Path("/evidence/memory.raw"),
                    artifact_type="process",
                    raw_fields={"pid": 4, "name": "System"},
                ),
            ],
        )


def test_base_records_invocation_hash() -> None:
    evidence_hash = "e" * 64
    output = ProcessListingWrapper().execute(
        invocation_args=["--pid", "4"],
        evidence_hash=evidence_hash,
    )

    expected = blake3(
        b"vol3.windows.pslist\x00vol3 2.10.0\x00--pid\x004\x00" + evidence_hash.encode(),
    ).hexdigest()

    assert output.invocation_hash == expected
