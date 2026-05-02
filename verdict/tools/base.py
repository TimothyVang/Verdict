"""ToolWrapper abstract base class — W1.E.2.

Every SIFT tool wrapper extends this class. It enforces:

  1. §3.1 evidence integrity: invocation_hash = blake3(tool_name + tool_version
     + args_json + evidence_hash) computed in pre_run() before any execution.
  2. NIST SP 800-86 §5.1.2/§5.1.4 metadata recorded in every ToolOutput:
     tool_version, (microsandbox_version, rootfs_sha256, kernel_version in W2.B).
  3. Tool execution MUST go through the microsandbox provider, never directly on
     the host (§3.1 + §3.9). The _execute() method receives work_dir from the
     sandbox allocation; wrappers must write outputs there, never to /evidence/.

Subclass contract:
  - Override `tool_name` (property) → dotted name, e.g. "vol3.windows.psscan".
  - Override `_get_tool_version()` → read version from running binary. Mismatch
    with the rootfs-pinned version halts the wrapper (W2.B gate).
  - Override `_execute(args, evidence_path, work_dir)` → runs the tool inside
    the microsandbox and returns a fully-populated ToolOutput.

In W1.E the _execute() bodies raise NotImplementedError; the external CLI call
lands in W2.B when microsandbox integration is wired.  Raising NotImplementedError
is not a mock — it is the correct contract for an unimplemented real method.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path

from blake3 import blake3 as _blake3

from verdict.schemas.tool_output import ToolOutput


class ToolWrapper(ABC):
    """Abstract base for every SIFT forensic tool wrapper.

    Subclasses implement `tool_name`, `_get_tool_version`, and `_execute`.
    The framework provides `pre_run` (invocation hash) and the scaffolding
    for `post_run` (ledger write hook — wired in W2.C.2).
    """

    # ------------------------------------------------------------------
    # Abstract interface — every concrete wrapper must provide these
    # ------------------------------------------------------------------

    @property
    @abstractmethod
    def tool_name(self) -> str:
        """Dotted tool identifier, e.g. 'vol3.windows.psscan'.

        Used as the canonical tool_name in ToolOutput and the invocation hash.
        """

    @abstractmethod
    def _get_tool_version(self) -> str:
        """Return the version string of the tool binary.

        Example: "vol3 2.10.0"

        In production (W2.B) this runs `vol3 --version` inside the microsandbox
        and returns the parsed string. Version mismatch with the rootfs pin halts
        the wrapper. In W1.E stubs this may return a constant.
        """

    @abstractmethod
    def _execute(self, args: dict, evidence_path: Path, work_dir: Path) -> ToolOutput:
        """Run the tool inside the microsandbox and return a ToolOutput.

        Args:
            args:           Validated invocation arguments (Pydantic-typed in W2.E.1).
            evidence_path:  Read-only evidence file path inside the microsandbox
                            (/evidence/... mount). MUST NOT be written to (§3.1).
            work_dir:       Writable work directory inside the microsandbox
                            (/work/... mount). All output files go here.

        Returns:
            A fully-populated ToolOutput with invocation_hash pre-set to the
            value returned by pre_run().

        Raises:
            NotImplementedError: Until W2.B wires the real microsandbox call.
        """

    # ------------------------------------------------------------------
    # Framework hooks — called by the executor, not by subclasses
    # ------------------------------------------------------------------

    def pre_run(self, *, args: dict, evidence_hash: str) -> str:
        """Compute and return the canonical invocation_hash (§3.1).

        invocation_hash = blake3(tool_name + tool_version + args_json + evidence_hash)

        The hash is computed over UTF-8 bytes.  args_json uses sort_keys=True for
        deterministic serialisation regardless of dict insertion order.

        This method does NOT mutate state; callers pass the returned hash to the
        ToolOutput constructor.

        Args:
            args:           Raw invocation arguments dict (same value passed to
                            _execute).
            evidence_hash:  SHA-256 hex of the evidence file(s), as recorded in
                            EvidenceManifest at case_init.

        Returns:
            blake3 hex-digest string of the canonical invocation hash.
        """
        tool_version = self._get_tool_version()
        args_json = json.dumps(args, sort_keys=True)
        raw = (self.tool_name + tool_version + args_json + evidence_hash).encode()
        return _blake3(raw).hexdigest()

    def post_run(self, output: ToolOutput) -> None:
        """Post-execution hook: ledger write + sandbox teardown (wired in W2.C.2).

        In W1.E this is a no-op scaffold.  In W2.C the LedgerEmitter calls
        this after every successful _execute() to append the chain-of-custody
        entry with fsync + verify-readback.

        Args:
            output: The ToolOutput returned by _execute().
        """
