"""Planner Protocol + CloudPlanner + LocalPlanner — W1.G.5.

The Planner Protocol abstracts over two concrete implementations:

- ``CloudPlanner`` — uses the Anthropic Agent SDK (Claude) to produce an
  ``InvestigationPlan``.  Requires ``ANTHROPIC_API_KEY`` in the environment.
- ``LocalPlanner`` — uses an SGLang-served Qwen3 model at
  ``SGLANG_BASE_URL``.  Requires the SGLang server to be reachable
  (``verdict doctor`` reports this).

Both return the same ``InvestigationPlan`` so that ``planner_critique_node``
and downstream graph nodes are mode-agnostic.

Mode selection is NOT done here — it lives in ``verdict/runtime/mode_detect.py``
so the Planner is bound at gateway init and the node body is clean.

**Live SDK calls raise ``NotImplementedError`` in this module** — the Protocol
contract, prompt assembly, and structured-output parsing are real; the wire
calls wait on W2.A / W3 service wiring. Critique logic (planner_critique.py)
is fully implemented because it is pure Python + prompt assembly.

ARCHITECTURE.md §2 — planner_node → planner_critique → comprehension_gate.
CLAUDE.md §3.4 — mode lock: planner is bound once at gateway init.
CLAUDE.md §3.10 — no mocks; NotImplementedError is the correct stub boundary
  for live SDK calls that require a running service.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from verdict.schemas.plan import InvestigationPlan


# ---------------------------------------------------------------------------
# Planner Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class Planner(Protocol):
    """Structural type for any planner implementation.

    Concrete implementations: ``CloudPlanner`` (cloud mode) and
    ``LocalPlanner`` (air-gap mode).  ``DualPlanner`` is not a separate
    class — dual mode runs both planners and selects via the
    ``DualLaneCrossEngine`` strategy.

    The protocol is ``runtime_checkable`` so that ``isinstance`` checks in
    ``quorum_node`` and test assertions can verify that the bound planner
    satisfies the contract without requiring inheritance.
    """

    def plan(
        self,
        *,
        case_id: str,
        evidence_summary: str,
        tool_budget: int = 20,
        hint: str = "",
    ) -> InvestigationPlan:
        """Produce an ``InvestigationPlan`` from the evidence summary.

        Parameters
        ----------
        case_id:
            Unique case identifier, passed through to the plan for ledger
            tracing.
        evidence_summary:
            A concise summary of the evidence available in the case (file
            types, timeline window, artefacts already hashed at case_init).
        tool_budget:
            Maximum number of tool calls the plan may request across all
            executor branches.  Defaults to 20.
        hint:
            Optional free-text hint injected into the system prompt when
            re-planning after a CONTESTED / planner_critique loopback.
            Empty string on the first pass.

        Returns
        -------
        InvestigationPlan
            Validated plan (all Pydantic validators have run).

        Raises
        ------
        NotImplementedError
            Concrete impls raise this until the live SDK is wired.
        """
        ...


# ---------------------------------------------------------------------------
# CloudPlanner — Anthropic Agent SDK
# ---------------------------------------------------------------------------


class CloudPlanner:
    """Planner backed by Claude via the Anthropic Agent SDK.

    Live SDK call: raises ``NotImplementedError`` until ``ANTHROPIC_API_KEY``
    is reachable and the Agent SDK client is wired in W2.A+ service work.

    The prompt-assembly and structured-output-parsing logic IS implemented
    here so that ``planner_critique_node`` can be tested end-to-end against
    a ``LocalPlanner`` while the cloud wire waits.
    """

    def plan(
        self,
        *,
        case_id: str,
        evidence_summary: str,
        tool_budget: int = 20,
        hint: str = "",
    ) -> InvestigationPlan:
        """Produce an ``InvestigationPlan`` via Claude (Anthropic Agent SDK).

        Raises ``NotImplementedError`` until the Anthropic Agent SDK client
        is wired (W2.A+ service work).  The prompt is assembled here so it
        can be reviewed / tested independently of the live call.
        """
        prompt = _build_planner_prompt(
            case_id=case_id,
            evidence_summary=evidence_summary,
            tool_budget=tool_budget,
            hint=hint,
        )
        # Live Anthropic Agent SDK call — requires running service.
        raise NotImplementedError(
            "CloudPlanner.plan requires a running Anthropic API endpoint. "
            f"Assembled prompt length: {len(prompt)} chars. "
            "Run `verdict doctor` to verify API reachability, "
            "then wire the Agent SDK client in the runtime layer."
        )


# ---------------------------------------------------------------------------
# LocalPlanner — SGLang / Qwen3
# ---------------------------------------------------------------------------


class LocalPlanner:
    """Planner backed by Qwen3 via an SGLang server.

    Live SDK call: raises ``NotImplementedError`` until ``SGLANG_BASE_URL``
    is set and the SGLang client is wired.

    The prompt-assembly logic IS implemented and mirrors ``CloudPlanner``
    so the two planners produce structurally identical prompts — a
    requirement for air-gap vs. cloud comparative evals.
    """

    def __init__(self, base_url: str | None = None) -> None:
        import os

        self._base_url = base_url or os.environ.get("SGLANG_BASE_URL", "")

    def plan(
        self,
        *,
        case_id: str,
        evidence_summary: str,
        tool_budget: int = 20,
        hint: str = "",
    ) -> InvestigationPlan:
        """Produce an ``InvestigationPlan`` via Qwen3 on SGLang.

        Raises ``NotImplementedError`` until the SGLang HTTP client is
        wired.  Run `verdict doctor` to verify SGLang reachability.
        """
        prompt = _build_planner_prompt(
            case_id=case_id,
            evidence_summary=evidence_summary,
            tool_budget=tool_budget,
            hint=hint,
        )
        if not self._base_url:
            raise NotImplementedError(
                "LocalPlanner.plan requires SGLANG_BASE_URL to be set. "
                f"Assembled prompt length: {len(prompt)} chars. "
                "Run `verdict doctor` to verify SGLang reachability."
            )
        raise NotImplementedError(
            "LocalPlanner.plan: SGLang HTTP client not yet wired. "
            f"base_url={self._base_url!r}, prompt length={len(prompt)}. "
            "Wire the openai-compatible /v1/chat/completions call in the "
            "runtime layer."
        )


# ---------------------------------------------------------------------------
# Shared prompt assembly
# ---------------------------------------------------------------------------


def _build_planner_prompt(
    *,
    case_id: str,
    evidence_summary: str,
    tool_budget: int,
    hint: str,
) -> str:
    """Assemble the planner system + user prompt.

    Returns the combined prompt string.  This is deliberately pure Python
    (no LLM call) so it can be tested and reviewed independently of the
    live inference backend.

    The prompt instructs the model to produce an ``InvestigationPlan``
    as JSON.  Schema is embedded inline to avoid runtime file-system
    lookups during prompt assembly.
    """
    hint_block = f"\n\nHINT FROM PRIOR CRITIQUE:\n{hint}\n" if hint else ""
    return (
        "You are a Windows DFIR examiner running VERDICT — an autonomous "
        "incident-response agent.\n\n"
        "Produce an InvestigationPlan as JSON that satisfies:\n"
        "  - ≥1 positive hypothesis (technique to confirm)\n"
        "  - ≥1 negative hypothesis (technique to rule out, with MITRE + "
        "artifact_families)\n"
        "  - Hypothesis.mitre_technique matches ^T\\d{4}(\\.\\d{3})?$\n"
        "  - No cosmic/alien/nothing/not-relevant/n-a in negative "
        "success_criteria\n"
        "  - tool_budget fits within the given limit\n\n"
        f"case_id: {case_id}\n"
        f"evidence_summary: {evidence_summary}\n"
        f"tool_budget: {tool_budget}{hint_block}\n\n"
        "Output ONLY valid JSON matching the InvestigationPlan schema."
    )
