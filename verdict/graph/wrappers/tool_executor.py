"""ToolExecutor — second wrapper in the executor_work composition.

Position in the three-wrapper composition (ARCHITECTURE.md §2 + CLAUDE.md §4):

    DenyRuleWrapper → ToolExecutor → LedgerEmitter

Responsibilities (this module only):

  1. Typed dispatch: accept (tool_name, args) and route to the correct
     registered ToolWrapper subclass.
  2. Invoke ToolWrapper.pre_run() to compute the invocation_hash (§3.1).
  3. Call ToolWrapper._execute(args, evidence_path, work_dir) and return the
     resulting ToolOutput.

Explicitly NOT in scope:
  - Writing to /evidence/ (Layer 2 deny — DenyRuleWrapper's job).
  - Ledger writes / fsync / HMAC signing (LedgerEmitter's job).
  - Microsandbox spawn (the concrete _execute() implementations in
    verdict/tools/vol3/*.py own the spawn call; those land in W2.B).

Per CLAUDE.md §3.10: NotImplementedError from _execute() propagates; it is
the correct contract for tool wrappers whose W2.B microsandbox integration
has not yet landed.  Callers (quorum_node, pivot_node) must handle it.

Dispatch invariants:
  - Tool names are unique across registered wrappers; constructor raises
    ValueError on duplicate registration.
  - UnknownToolError is raised (not KeyError) for caller-friendly error
    messages that include the list of registered tools.
"""

from __future__ import annotations

from pathlib import Path

from verdict.schemas.tool_output import ToolOutput
from verdict.tools.base import ToolWrapper


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class UnknownToolError(Exception):
    """Raised when run() is called with a tool_name not in the registry.

    Attributes:
        tool_name:        The unregistered tool name that was requested.
        registered_names: Frozenset of all currently-registered tool names.
    """

    def __init__(self, *, tool_name: str, registered_names: frozenset[str]) -> None:
        self.tool_name = tool_name
        self.registered_names = registered_names
        super().__init__(
            f"ToolExecutor: no wrapper registered for tool_name={tool_name!r}. "
            f"Registered tools: {sorted(registered_names)}"
        )


# ---------------------------------------------------------------------------
# ToolExecutor
# ---------------------------------------------------------------------------


class ToolExecutor:
    """Dispatches (tool_name, args) to the correct ToolWrapper and returns ToolOutput.

    Args:
        wrappers:       List of concrete ToolWrapper subclasses to register.
                        Tool names must be unique; duplicate raises ValueError.
        evidence_path:  Read-only evidence file path inside the microsandbox.
                        Passed directly to ToolWrapper._execute().
        work_dir:       Writable work directory inside the microsandbox.
                        Passed directly to ToolWrapper._execute().

    Composition usage::

        executor = ToolExecutor(
            wrappers=[Pslist(), Psscan(), Malfind()],
            evidence_path=Path("/evidence/mem.raw"),
            work_dir=Path("/work/case-001/vol3"),
        )
        # Typically wrapped by DenyRuleWrapper:
        deny = DenyRuleWrapper(executor=executor, mode="cloud")
        result: ToolOutput = deny.run(tool_name="vol3.windows.pslist", args={...})

    The executor is also directly callable with the same signature as the
    executor arg expected by DenyRuleWrapper — ``(tool_name, args) -> ToolOutput``.
    This allows ToolExecutor to be composed without an adapter shim.
    """

    def __init__(
        self,
        *,
        wrappers: list[ToolWrapper],
        evidence_path: Path,
        work_dir: Path,
    ) -> None:
        self._evidence_path = evidence_path
        self._work_dir = work_dir
        self._registry: dict[str, ToolWrapper] = {}

        for wrapper in wrappers:
            name = wrapper.tool_name
            if name in self._registry:
                raise ValueError(
                    f"ToolExecutor: duplicate tool_name registration: {name!r}. "
                    "Each tool_name must be registered exactly once."
                )
            self._registry[name] = wrapper

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    @property
    def registered_tool_names(self) -> frozenset[str]:
        """Return the frozenset of all registered tool names."""
        return frozenset(self._registry)

    def run(self, tool_name: str, args: dict) -> ToolOutput:
        """Dispatch to the matching ToolWrapper and return the ToolOutput.

        Callable signature matches what DenyRuleWrapper expects as its
        ``executor`` argument — ``(tool_name, args) -> result``.

        Args:
            tool_name: Dotted tool identifier, e.g. "vol3.windows.pslist".
            args:       Validated tool invocation arguments.

        Returns:
            ToolOutput from the wrapper's _execute() method.

        Raises:
            UnknownToolError: If tool_name is not in the registry.
            NotImplementedError: If the wrapper's _execute() raises it
                (expected before W2.B microsandbox integration lands).
        """
        wrapper = self._registry.get(tool_name)
        if wrapper is None:
            raise UnknownToolError(
                tool_name=tool_name,
                registered_names=self.registered_tool_names,
            )

        return wrapper._execute(
            args=args,
            evidence_path=self._evidence_path,
            work_dir=self._work_dir,
        )

    # Make the instance directly callable so it satisfies the DenyRuleWrapper
    # ``executor: Callable[[str, dict], Any]`` contract without an adapter.
    def __call__(self, tool_name: str, args: dict) -> ToolOutput:
        return self.run(tool_name, args)
