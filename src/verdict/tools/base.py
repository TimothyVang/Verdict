from __future__ import annotations

from abc import ABC, abstractmethod

from verdict.schemas.tool_output import ToolOutput, compute_invocation_hash


class ToolWrapper(ABC):
    """Base class for wrappers that emit the shared ToolOutput contract."""

    tool_name: str
    tool_version: str

    def execute(self, *, invocation_args: list[str], evidence_hash: str) -> ToolOutput:
        invocation_hash = self.pre_run(invocation_args=invocation_args, evidence_hash=evidence_hash)
        output = self.run(invocation_args=invocation_args, evidence_hash=evidence_hash)
        if output.invocation_hash != invocation_hash:
            raise ValueError("ToolOutput invocation_hash does not match wrapper pre_run hash")
        return output

    def pre_run(self, *, invocation_args: list[str], evidence_hash: str) -> str:
        return compute_invocation_hash(
            tool_name=self.tool_name,
            tool_version=self.tool_version,
            invocation_args=invocation_args,
            evidence_hash=evidence_hash,
        )

    @abstractmethod
    def run(self, *, invocation_args: list[str], evidence_hash: str) -> ToolOutput:
        """Execute the concrete tool wrapper and return a ToolOutput."""
