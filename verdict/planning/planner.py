"""Planner Protocol + CloudPlanner + LocalPlanner implementations.

Per CLAUDE.md §3.4 (mode lock) and ARCHITECTURE.md §2:
- CloudPlanner uses Claude Code / Claude Agent SDK (Python).
  Used in cloud-only and dual modes.
- LocalPlanner uses SGLang serving Qwen3-30B-A3B-Thinking-2507.
  Used in air-gap and dual modes.

The Planner Protocol defines a single method:
  plan(evidence_manifest: EvidenceManifest) -> InvestigationPlan

Mode selection happens at gateway_init via detect_mode() in
verdict/runtime/mode_detect.py. The planner is instantiated once
and immutable thereafter (per mode-lock rule §3.4).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from verdict.schemas.evidence import EvidenceManifest
from verdict.schemas.plan import InvestigationPlan


@runtime_checkable
class Planner(Protocol):
    """Protocol for investigation planning engines.

    A Planner receives a manifest of evidence and produces an
    InvestigationPlan with hypotheses, tool budget, and success criteria.

    Implementing classes:
    - CloudPlanner: Uses Claude Code + Claude Agent SDK.
    - LocalPlanner: Uses SGLang + Qwen3-30B-A3B-Thinking.
    """

    def plan(self, evidence_manifest: EvidenceManifest) -> InvestigationPlan:
        """Produce an InvestigationPlan for a case.

        Args:
            evidence_manifest: Inventory of evidence files + chain-of-custody hashes.

        Returns:
            InvestigationPlan with positive hypotheses, negative hypotheses,
            tool budget, and success criteria.
        """
        ...


class CloudPlanner:
    """Claude Code + Claude Agent SDK planner (cloud-only + dual modes).

    Per ARCHITECTURE.md §1 and CLAUDE.md stack lock-in:
    - Uses Claude Code interactive auth or ANTHROPIC_API_KEY env var.
    - Three credential paths: CLAUDE_CODE_OAUTH_TOKEN, ~/.claude/, ANTHROPIC_API_KEY.
    - OAuth tokens NOT redistributable per Anthropic commercial terms.

    W1.G.5 stub: method signature defined, full LLM integration deferred to W2.
    """

    def __init__(self):
        """Initialize CloudPlanner. Full credential injection in W2.A."""
        pass

    def plan(self, evidence_manifest: EvidenceManifest) -> InvestigationPlan:
        """Produce an investigation plan using Claude.

        Args:
            evidence_manifest: Case evidence inventory.

        Returns:
            InvestigationPlan with hypotheses and strategy.
        """
        # W1.G.5 stub: returns empty plan. Full planner logic in W2.A.
        return InvestigationPlan(
            case_id=evidence_manifest.case_id,
            hypotheses=[],
            tool_budget=30,
            success_criteria=None,
        )


class LocalPlanner:
    """SGLang + Qwen3-30B-A3B-Thinking planner (air-gap + dual modes).

    Per ARCHITECTURE.md §1 and CLAUDE.md stack lock-in:
    - Serves via SGLang (Apache-2.0) with RadixAttention prefix cache.
    - Model: Qwen3-30B-A3B-Thinking-2507 (Apache-2.0).
    - Tool-call parser: qwen3_xml (native SGLang support).

    W1.G.5 stub: method signature defined, full LLM integration deferred to W2.
    """

    def __init__(self, sglang_base_url: str = "http://localhost:30000"):
        """Initialize LocalPlanner.

        Args:
            sglang_base_url: SGLang server endpoint. Defaults to localhost:30000
                (dev rig); production endpoint configured at gateway init.
        """
        self.sglang_base_url = sglang_base_url

    def plan(self, evidence_manifest: EvidenceManifest) -> InvestigationPlan:
        """Produce an investigation plan using SGLang + Qwen3.

        Args:
            evidence_manifest: Case evidence inventory.

        Returns:
            InvestigationPlan with hypotheses and strategy.
        """
        # W1.G.5 stub: returns empty plan. Full planner logic in W2.B.
        return InvestigationPlan(
            case_id=evidence_manifest.case_id,
            hypotheses=[],
            tool_budget=30,
            success_criteria=None,
        )
