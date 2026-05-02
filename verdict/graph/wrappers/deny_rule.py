"""DenyRuleWrapper — Layer 2 of three-layer immutability defense.

ARCHITECTURE.md §3 — three-layer defense:

    Layer 1: Claude PreToolUse hook (best-effort; cloud + dual modes only).
             Known-buggy for MCP/Edit tools per #33106/#37210.
    Layer 2: LangGraph DenyRuleWrapper  ← THIS MODULE
             Fires in ALL three modes (cloud, airgap, dual) regardless of model.
             The ARCHITECTURAL GUARANTEE.
    Layer 3: Microsandbox read-only /evidence mount (kernel-enforced).

This module owns the deny-rule list.  Every rule is data — a list of
(field_predicate, path_predicate) pairs — so CI can assert coverage without
touching the composition logic.

Composition pattern (CLAUDE.md §4 + ARCHITECTURE.md §2):

    DenyRuleWrapper(executor=ToolExecutor(...), mode=mode)

The wrapper intercepts `run(tool_name, args)`, evaluates all deny rules
against the args dict, and either:

  - Raises DenyRuleViolation (before the executor is called), or
  - Delegates to the wrapped executor and returns its result unchanged.

No state is mutated; DenyRuleWrapper is stateless between calls.

Why an explicit list of WRITE_FIELD_NAMES rather than "any arg containing
a path under /evidence/"?  Because the distinction matters:

  evidence_path=/evidence/disk.E01    ← READ (allowed — executor reads it)
  output_path=/evidence/out.txt       ← WRITE (forbidden — §3.1)
  write_path=/evidence/out.bin        ← WRITE (forbidden)
  output_dir=/evidence/               ← WRITE (forbidden)

The field-name contract is stable because every ToolWrapper must use typed
args (Pydantic-AI, W2.E.1); undocumented field names are rejected by the
validator before they reach DenyRuleWrapper.  Adding new write-capable field
names to WRITE_FIELD_NAMES is a coordinated change (§3.8 policy).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

# ---------------------------------------------------------------------------
# Sentinel prefix — the forbidden write target
# ---------------------------------------------------------------------------

_EVIDENCE_PREFIX = "/evidence"

# ---------------------------------------------------------------------------
# Field names that represent write targets (as opposed to read/input targets).
#
# Adding a name here is the ONLY supported way to declare a new write-capable
# tool arg.  Do NOT add input-side field names (memory_image, evidence_path,
# image_path) — those are reads and are explicitly allowed through.
# ---------------------------------------------------------------------------

WRITE_FIELD_NAMES: frozenset[str] = frozenset(
    {
        "output_path",
        "output_dir",
        "output_file",
        "output_csv",
        "output_json",
        "output_jsonl",
        "write_path",
        "write_dir",
        "dest_path",
        "dest_dir",
        "result_path",
        "result_dir",
        "report_path",
        "report_dir",
        "dump_path",
        "dump_dir",
    }
)


# ---------------------------------------------------------------------------
# DenyRuleViolation — structured exception for the ledger
# ---------------------------------------------------------------------------


class DenyRuleViolation(Exception):
    """Raised when a tool invocation arg violates a deny rule.

    Attributes:
        tool_name     — the tool that attempted the forbidden operation.
        violated_arg  — the arg key that triggered the rule.
        denied_value  — the string representation of the denied value.
        mode          — the operational mode (cloud | airgap | dual) at fire time.
        rule_id       — short identifier for the specific rule fired (default
                        "evidence_write_forbidden").
    """

    def __init__(
        self,
        *,
        tool_name: str,
        violated_arg: str,
        denied_value: str,
        mode: str,
        rule_id: str = "evidence_write_forbidden",
    ) -> None:
        self.tool_name = tool_name
        self.violated_arg = violated_arg
        self.denied_value = denied_value
        self.mode = mode
        self.rule_id = rule_id
        super().__init__(
            f"[DenyRule:{rule_id}] tool={tool_name!r} attempted to write to "
            f"/evidence/ via arg {violated_arg!r}={denied_value!r} "
            f"(mode={mode!r}). ARCHITECTURE.md §3 Layer-2 deny fired."
        )


# ---------------------------------------------------------------------------
# DenyRuleWrapper
# ---------------------------------------------------------------------------


class DenyRuleWrapper:
    """Layer-2 LangGraph wrapper that enforces the /evidence write-deny rule.

    Args:
        executor: Callable with signature ``(tool_name: str, args: dict) -> dict``.
                  Typically a ``ToolExecutor`` instance.  DenyRuleWrapper does
                  not depend on the concrete type — it treats the executor as a
                  pure callable so the three wrappers can be composed in order
                  without circular imports.
        mode:     Operational mode (one of "cloud" | "airgap" | "dual").
                  Stored for structured violation metadata only; the deny logic
                  is mode-invariant (fires in ALL modes — §3).

    Usage::

        deny = DenyRuleWrapper(executor=tool_executor, mode="cloud")
        result = deny.run(tool_name="vol3.windows.pslist", args={...})
    """

    def __init__(
        self,
        *,
        executor: Callable[[str, dict], Any],
        mode: str,
    ) -> None:
        if mode not in ("cloud", "airgap", "dual"):
            raise ValueError(
                f"mode must be 'cloud', 'airgap', or 'dual'; got {mode!r}"
            )
        self._executor = executor
        self._mode = mode

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def run(self, *, tool_name: str, args: dict) -> Any:
        """Evaluate deny rules against args; delegate to executor if all pass.

        Args:
            tool_name: Dotted tool identifier, e.g. "vol3.windows.pslist".
            args:       Validated tool invocation arguments.

        Returns:
            The result returned by the wrapped executor.

        Raises:
            DenyRuleViolation: If any arg matches a deny rule.
        """
        self._check_evidence_write_rules(tool_name=tool_name, args=args)
        return self._executor(tool_name, args)

    # ------------------------------------------------------------------
    # Private deny-rule evaluation
    # ------------------------------------------------------------------

    def _check_evidence_write_rules(self, *, tool_name: str, args: dict) -> None:
        """Raise DenyRuleViolation if any arg is a write target under /evidence/.

        Scans all (key, value) pairs in args.  For each key that is a known
        write-field name, resolves the value to a string path and checks
        whether it starts with the evidence prefix.

        Raises:
            DenyRuleViolation: On the first offending arg found.
        """
        for key, value in args.items():
            if key not in WRITE_FIELD_NAMES:
                # Not a write-capable field; skip without path resolution.
                continue

            path_str = _to_path_str(value)
            if path_str is None:
                # Value is not a path-like object; skip.
                continue

            if _is_under_evidence(path_str):
                raise DenyRuleViolation(
                    tool_name=tool_name,
                    violated_arg=key,
                    denied_value=path_str,
                    mode=self._mode,
                )


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------


def _to_path_str(value: Any) -> str | None:
    """Convert a tool-arg value to a normalised POSIX path string.

    Accepts str, Path, and pathlib.PurePath.  Returns None for non-path types
    (int, list, dict, …) so the deny-rule evaluator skips them safely.

    The returned string is normalised (redundant separators collapsed, ./ and
    ../ resolved as far as possible without filesystem access) so that
    "/evidence/../evidence/out.txt" is correctly caught.
    """
    if isinstance(value, Path):
        # pathlib resolves the path relative to cwd; for deny-rule purposes we
        # want the logical POSIX form without touching the filesystem.
        return value.as_posix()
    if isinstance(value, str):
        # Normalise the string path using PurePosixPath to collapse redundant
        # separators and resolve simple ./ components.
        try:
            from pathlib import PurePosixPath
            return str(PurePosixPath(value))
        except Exception:  # noqa: BLE001
            return value
    return None


def _is_under_evidence(path_str: str) -> bool:
    """Return True if path_str is /evidence or starts with /evidence/."""
    return path_str == _EVIDENCE_PREFIX or path_str.startswith(_EVIDENCE_PREFIX + "/")
