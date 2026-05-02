"""vol3 windows.psscan ToolWrapper — W1.E.1.

`vol_psscan` is the signature-scan counterpart to `vol_pslist`. Where pslist
walks the Windows active process doubly-linked list (_EPROCESS.ActiveProcessLinks),
psscan pool-scans memory for EPROCESS pool-tags.  The divergence

    set(psscan_pids) - set(pslist_pids) ≠ ∅

is the textbook DKOM / T1014 (Rootkit) signature per CLAUDE.md §7 and
BUILD_PLAN W1.E.1.  The DKOM check is encoded in playbooks/memory.yml (W1.F.2);
this wrapper provides the PID surface (pid_set()) required for that check.

Tool-pair split:
    vol_pslist  — walks active process list (may miss DKOM-hidden processes)
    vol_psscan  — pool-scan over full physical memory (catches DKOM-hidden)

The _execute() body raises NotImplementedError until W2.B wires the
microsandbox provider.  Raising NotImplementedError is the correct contract
for an unimplemented real method — not a mock (§3.10).

NIST SP 800-86 §5.1.2/§5.1.4 metadata (microsandbox_version, rootfs_sha256,
kernel_version) is populated by the LedgerEmitter post_run hook wired in W2.C.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field, field_validator

from verdict.schemas.tool_output import ToolOutput
from verdict.tools.base import ToolWrapper

# Rootfs-pinned version; wrappers halt on mismatch in W2.B (tool-pinning check).
# Updated when the SIFT rootfs is rebuilt (W1.A.3.c).
_PINNED_VOL3_VERSION = "vol3 2.10.0"


class VolPsscanArgs(BaseModel):
    """Typed arguments for vol3 windows.psscan.

    The `plugin` field is intentionally locked to "windows.psscan" so it is
    always included in the invocation_hash computation (§3.1) and cannot be
    accidentally substituted by the planner.

    evidence_path: Path to the memory image inside the microsandbox.
                   MUST be under /evidence/; validated at construction.
                   Read-only; never written to (§3.1).
    plugin:        Canonical Volatility 3 plugin name. Not user-configurable.
    """

    evidence_path: Path
    plugin: str = Field(default="windows.psscan", frozen=True)

    @field_validator("plugin")
    @classmethod
    def _plugin_is_locked(cls, v: str) -> str:
        if v != "windows.psscan":
            raise ValueError(
                f"plugin must be 'windows.psscan', got {v!r}. "
                "Use the appropriate wrapper class for other Volatility plugins."
            )
        return v


class VolPsscanWrapper(ToolWrapper):
    """Wrapper for `vol3 windows.psscan`.

    Implements the ToolWrapper ABC (W1.E.2) for the Volatility 3 psscan plugin.
    Exposes pid_set() for DKOM cross-validation against pslist.

    _execute() raises NotImplementedError until W2.B wires the microsandbox
    provider.  This is an unimplemented real method, NOT a mock (§3.10).
    """

    @property
    def tool_name(self) -> str:
        """Canonical dotted identifier used in ToolOutput and invocation_hash."""
        return "vol3.windows.psscan"

    def _get_tool_version(self) -> str:
        """Return the pinned vol3 version string.

        In W2.B this runs `vol3 --version` inside the microsandbox and compares
        the output against _PINNED_VOL3_VERSION; mismatch halts the wrapper.
        In W1.E this returns the constant directly.
        """
        return _PINNED_VOL3_VERSION

    def _execute(self, args: dict, evidence_path: Path, work_dir: Path) -> ToolOutput:
        """Run vol3 windows.psscan inside the microsandbox.

        Args:
            args:           Validated invocation arguments dict (must include
                            'plugin' key so invocation_hash covers it).
            evidence_path:  Read-only path inside the microsandbox (/evidence/…).
                            MUST NOT be written to (§3.1).
            work_dir:       Writable output directory (/work/…). All output
                            files (CSV, JSON) land here.

        Returns:
            ToolOutput with parsed_artifacts populated with Artifact objects
            of artifact_type="process", each carrying PID, ImageFileName, and
            PPID in raw_fields.

        Raises:
            NotImplementedError: Until W2.B wires the real microsandbox call.
        """
        raise NotImplementedError(
            "vol_psscan real microsandbox execution lands in W2.B. "
            "Bring up the microsandbox provider before implementing this method."
        )

    # ------------------------------------------------------------------
    # DKOM cross-validation surface (§7 / BUILD_PLAN W1.E.1)
    # ------------------------------------------------------------------

    def pid_set(self, output: ToolOutput) -> frozenset[int]:
        """Extract the set of PIDs from a psscan ToolOutput.

        Filters parsed_artifacts to artifact_type="process" and reads the
        "PID" field from raw_fields.  Non-process artifacts (network
        connections, etc.) are excluded.

        This is the left-hand side of the DKOM divergence check:
            set(psscan_pids) - set(pslist_pids) ≠ ∅  →  T1014 hypothesis

        The check itself lives in playbooks/memory.yml (W1.F.2); this method
        provides the contract surface the playbook evaluator calls.

        Args:
            output: ToolOutput returned by a successful psscan execution.

        Returns:
            frozenset of integer PIDs found by pool-scanning.
        """
        pids: set[int] = set()
        for artifact in output.parsed_artifacts:
            if artifact.artifact_type == "process":
                pid = artifact.raw_fields.get("PID")
                if pid is not None:
                    pids.add(int(pid))
        return frozenset(pids)
