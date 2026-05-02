"""Plan schemas — W1.B.5 + W2.D.2.

Four classes that form the planning layer's schema contract:

- ``Hypothesis`` — a claim the investigation is testing (positive OR negative).
  Validators enforce MITRE shape, negative-hypothesis quality (§3.5, §3.6).
- ``InvestigationPlan`` — the planner's structured output: a list of
  hypotheses (≥1 positive, ≥1 negative), a tool budget, and measurable
  success criteria for each hypothesis.
- ``PlanComprehensionEcho`` — produced by each executor branch to confirm
  it has parsed the plan correctly (comprehension_gate input, W2.B.2).
- ``PlannerCritiqueVerdict`` — produced by ``planner_critique_node`` (W2.D.1).
  Encodes the CoVe pass outcome: route to ``comprehension_gate`` or loop back
  to ``planner_node`` with a hint. When ``route == "planner"`` the
  ``failed_questions`` list MUST be non-empty (§3 load-bearing: a loopback
  without any reason is an infinite loop waiting to happen).

CLAUDE.md §3.5 — MITRE regex ``^T\\d{4}(\\.\\d{3})?$``.
CLAUDE.md §3.6 — negative hypothesis quality deny-list.
ARCHITECTURE.md §2 — planner → planner_critique → comprehension_gate flow.
"""

from __future__ import annotations

import hashlib
import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from verdict.schemas.artifact_class import ArtifactClass

# ---------------------------------------------------------------------------
# §3.5 — MITRE technique regex. Shape only; sub-technique-required policy
# lives in the Inspect AI `mitre_subtechnique_precision` scorer.
# ---------------------------------------------------------------------------
_MITRE_RE = re.compile(r"^T\d{4}(\.\d{3})?$")

# §3.6 deny-list tokens (substring, case-insensitive) for negative hypothesis
# success_criteria.
_DENY_TOKENS: tuple[str, ...] = (
    "cosmic",
    "alien",
    "nothing",
    "not-relevant",
    "not relevant",
    "n-a",
    "n/a",
)


# ---------------------------------------------------------------------------
# Hypothesis
# ---------------------------------------------------------------------------


class Hypothesis(BaseModel):
    """A claim the investigation is testing — positive OR negative.

    Positive hypotheses posit that a specific technique was used and
    name the artifacts expected to confirm it.

    Negative hypotheses assert that a specific technique was NOT used;
    they are required to be specific (MITRE technique + artifact families)
    so the investigation can rule out alternatives, not just assert absence.
    """

    id: str = Field(min_length=1)
    polarity: Literal["positive", "negative"]
    mitre_technique: str | None = None
    artifact_families: list[ArtifactClass] = Field(default_factory=list)
    success_criteria: str = Field(min_length=1)

    @field_validator("mitre_technique", mode="before")
    @classmethod
    def _validate_mitre_format(cls, v: object) -> object:
        """Enforce ^T\\d{4}(\\.\\d{3})?$ shape per §3.5."""
        if v is None:
            return v
        if not isinstance(v, str) or not _MITRE_RE.match(v):
            raise ValueError(
                f"MITRE technique must match T#### or T####.### (e.g. T1055.012); got {v!r}"
            )
        return v

    @model_validator(mode="after")
    def _negative_hypothesis_quality(self) -> Hypothesis:
        """Enforce non-degenerate negative hypotheses per §3.6."""
        if self.polarity != "negative":
            return self

        if self.mitre_technique is None:
            raise ValueError(
                "negative hypothesis must name a MITRE technique it is ruling out"
            )

        if not self.artifact_families:
            raise ValueError(
                "negative hypothesis must name artifact families that would refute it"
            )

        criteria_lower = self.success_criteria.lower()
        for token in _DENY_TOKENS:
            if token in criteria_lower:
                raise ValueError(
                    f"negative hypothesis success_criteria looks degenerate "
                    f"(denied token: {token!r})"
                )

        return self


# ---------------------------------------------------------------------------
# InvestigationPlan
# ---------------------------------------------------------------------------


class InvestigationPlan(BaseModel):
    """The planner's structured output, consumed by planner_critique_node
    and comprehension_gate before executor_fanout runs.

    Invariants:
    - At least one positive hypothesis (something to confirm).
    - At least one negative hypothesis (something to rule out) per §3.6.
    - Tool budget > 0.
    - Success criteria hash is deterministic given the hypothesis list so
      comprehension_gate can verify executor echoes match.
    """

    schema_version: Literal["v1"] = "v1"
    plan_id: str = Field(min_length=1)
    case_id: str = Field(min_length=1)
    evidence_summary: str = Field(min_length=1)
    hypotheses: list[Hypothesis] = Field(min_length=2)
    tool_budget: int = Field(ge=1)

    @model_validator(mode="after")
    def _at_least_one_negative(self) -> InvestigationPlan:
        """§3.6 — ≥1 negative hypothesis per plan."""
        if not any(h.polarity == "negative" for h in self.hypotheses):
            raise ValueError(
                "InvestigationPlan must include ≥1 negative hypothesis (§3.6)"
            )
        return self

    @model_validator(mode="after")
    def _at_least_one_positive(self) -> InvestigationPlan:
        """At least one positive hypothesis to investigate."""
        if not any(h.polarity == "positive" for h in self.hypotheses):
            raise ValueError(
                "InvestigationPlan must include ≥1 positive hypothesis"
            )
        return self

    def success_criteria_hash(self) -> str:
        """SHA-256 over the sorted success-criteria strings.

        Used by comprehension_gate to verify all executor branches parsed
        the same success criteria from the plan.
        """
        sorted_criteria = sorted(h.success_criteria for h in self.hypotheses)
        payload = "\n".join(sorted_criteria).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    @property
    def positive_hypothesis_ids(self) -> list[str]:
        return [h.id for h in self.hypotheses if h.polarity == "positive"]

    @property
    def negative_hypothesis_ids(self) -> list[str]:
        return [h.id for h in self.hypotheses if h.polarity == "negative"]


# ---------------------------------------------------------------------------
# PlanComprehensionEcho
# ---------------------------------------------------------------------------


class PlanComprehensionEcho(BaseModel):
    """Executor echo for comprehension_gate validation (W2.B.2).

    Each of the four executor branches echoes back its parsed view of the
    plan. The gate validates consensus on hypothesis IDs and success-criteria
    hash before releasing to executor_fanout.
    """

    executor_id: str = Field(min_length=1)
    parsed_positive_hypothesis_ids: list[str]
    parsed_negative_hypothesis_ids: list[str]
    parsed_success_criteria_hash: str = Field(min_length=1)


# ---------------------------------------------------------------------------
# PlannerCritiqueVerdict — W2.D.2
# ---------------------------------------------------------------------------


class PlannerCritiqueVerdict(BaseModel):
    """Output of ``planner_critique_node`` (CoVe pass, W2.D.1).

    The critique node drafts verification questions about the plan and answers
    them against the ``InvestigationPlan.evidence_summary``. This schema
    encodes the routing decision and, when the decision is to loop back,
    the questions that failed.

    Invariant (W2.D.2): ``route == "planner"`` ⟹ ``failed_questions`` non-empty.
    A loopback with an empty list is a schema error — it would produce an
    infinite planner loop with no corrective signal.
    """

    route: Literal["comprehension_gate", "planner"]
    failed_questions: list[str] = Field(default_factory=list)
    hint: str = ""
    all_questions: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _failed_questions_required_on_loopback(self) -> PlannerCritiqueVerdict:
        """Loopback route MUST carry at least one failed question."""
        if self.route == "planner" and not self.failed_questions:
            raise ValueError(
                "PlannerCritiqueVerdict with route='planner' must have "
                "non-empty failed_questions — a loopback with no reason is "
                "an infinite loop (W2.D.2 invariant)"
            )
        return self
