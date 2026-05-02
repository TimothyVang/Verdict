"""Planner Protocol + CloudPlanner + LocalPlanner skeleton — W2.A.1 / W1.G.5.

The `Planner` Protocol is the seam between the LangGraph topology
(`planner_node`) and whichever inference backend the locked operational
mode dictates:

  * CloudPlanner  → Anthropic / Claude Code via the Anthropic Python SDK
                    (used by mode == CLOUD and as one of the two lanes
                    in mode == DUAL).
  * LocalPlanner  → SGLang serving Qwen3-30B-A3B-Thinking-2507
                    (used by mode == AIRGAP and as the other lane in
                    mode == DUAL).

Mode-to-planner dispatch lives in `verdict/runtime/mode_detect.py`
(BUILD_PLAN W1.G.5.a). The Planner classes themselves only enforce
that they are not asked to plan in a mode they do not support.

This file is the *skeleton*: the constructor shape, configuration
validation (Pydantic v2), and the mode-rejection logic are all real.
The body of `plan()` raises `NotImplementedError` pointing at W2.A.2,
which lands the real Anthropic / SGLang inference call. This is the
§3.10-compliant skeleton pattern: contract is real, only the deferred
backend wiring raises — no mocks, no canned data, no MOCK env-vars.

Hard rules referenced:
  * §3.4  Mode lock — `verdict resume` re-uses the original mode.
  * §3.5  MITRE sub-technique precision (enforced on the schema).
  * §3.6  Negative-hypothesis quality (enforced on the schema).
  * §3.9  Credential isolation — API keys never enter a microsandbox.
  * §3.10 No mocks. NotImplementedError stubs are explicitly OK.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, field_validator

from verdict.planning.types import EvidenceManifest, InvestigationPlan, Mode

# ---------------------------------------------------------------------------
# Protocol — runtime_checkable so the gateway can isinstance-check at init.
# ---------------------------------------------------------------------------


@runtime_checkable
class Planner(Protocol):
    """Contract every concrete planner implementation must satisfy.

    The Protocol is intentionally minimal: a single `plan()` method that
    consumes a `case_id`, an `EvidenceManifest`, and the locked `Mode`,
    and returns a fully-validated `InvestigationPlan`. Schema validators
    on `InvestigationPlan` and `Hypothesis` enforce CLAUDE.md §3.5 + §3.6
    so any planner that returns a structurally-valid plan has implicitly
    satisfied the negative-hypothesis quality + MITRE-shape rules.
    """

    def plan(
        self,
        case_id: str,
        evidence_manifest: EvidenceManifest,
        mode: Mode,
    ) -> InvestigationPlan:
        """Produce an InvestigationPlan for the given case.

        Implementations MAY raise:
          * ValueError              — `mode` is not one this planner supports.
          * NotImplementedError     — backend wiring not yet landed (W2.A.2).
          * pydantic.ValidationError — returned plan failed §3.5 / §3.6.
        """
        ...


# ---------------------------------------------------------------------------
# CloudPlanner — Anthropic / Claude Code backend.
# ---------------------------------------------------------------------------


class CloudPlanner(BaseModel):
    """Cloud-mode planner driven by the Anthropic Python SDK.

    Used for mode == CLOUD (alone) and as the cloud lane of mode == DUAL.
    Refused for mode == AIRGAP — air-gap operators have no internet by
    definition and the Anthropic SDK call would fail closed.

    Configuration is Pydantic-validated at construction:
      * `api_key`  — non-empty string (real auth happens at first call;
                     §3.9 means this is host-side credential, never
                     injected into a microsandbox).
      * `model`    — pinned Anthropic model identifier.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    api_key: str = Field(min_length=1)
    model: str = Field(min_length=1)

    # Mode set this planner can serve. Mutating this at runtime is an
    # architecturally-rejected anti-pattern — see swarm/agents/planning-engineer.md
    # ("Don't add a 4th planner mode 'for testing'."). Tuple, not list, so
    # Pydantic frozen=True works.
    _supported_modes: tuple[Mode, ...] = (Mode.CLOUD, Mode.DUAL)

    @field_validator("api_key")
    @classmethod
    def _api_key_nonempty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("CloudPlanner.api_key must be a non-empty string")
        return v

    def plan(
        self,
        case_id: str,
        evidence_manifest: EvidenceManifest,
        mode: Mode,
    ) -> InvestigationPlan:
        if mode not in self._supported_modes:
            raise ValueError(
                f"CloudPlanner cannot plan in mode={mode.value}; "
                f"supported backends: {[m.value for m in self._supported_modes]}. "
                f"Mode dispatch is the responsibility of "
                f"verdict.runtime.mode_detect — see BUILD_PLAN W1.G.5.a."
            )
        # W2.A.2 lands the real Anthropic SDK call: messages.create with
        # the planner system prompt, a tool-call schema for InvestigationPlan,
        # and the case_id-derived seed. The contract above is the test
        # surface; the body is intentionally unimplemented per §3.10's
        # "skeleton OK, mock NOT OK" rule.
        del case_id, evidence_manifest  # silenced until W2.A.2 wires them
        raise NotImplementedError(
            "CloudPlanner.plan inference backend lands in W2.A.2 "
            "(Anthropic SDK + planner_system.md prompt + JSON-mode parse)."
        )


# ---------------------------------------------------------------------------
# LocalPlanner — SGLang serving Qwen3.
# ---------------------------------------------------------------------------


_HTTP_URL_RE = (
    # Conservative URL shape check for SGLang base URL config. Real URL
    # parsing (and reachability probe) lives in `verdict doctor`; here we
    # only enforce that the operator passed a string that *looks* like a
    # URL, so misconfigurations fail at gateway init rather than at the
    # first plan() call.
    r"^https?://[A-Za-z0-9.\-]+(?::\d{1,5})?(?:/.*)?$"
)


class LocalPlanner(BaseModel):
    """Air-gap-mode planner driven by SGLang serving Qwen3-30B-A3B-Thinking.

    Used for mode == AIRGAP (alone) and as the air-gap lane of mode == DUAL.
    Refused for mode == CLOUD — cloud-only operators have no GPU by
    definition and the SGLang HTTP call would fail closed.

    Configuration is Pydantic-validated at construction:
      * `sglang_base_url`  — http(s) URL of the SGLang OpenAI-compatible
                             endpoint (default port 30000 per
                             CLAUDE.md §10.1).
      * `model_path`       — filesystem path the SGLang server was launched
                             with; recorded in the ledger for chain-of-custody.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    sglang_base_url: str = Field(min_length=1, pattern=_HTTP_URL_RE)
    model_path: str = Field(min_length=1)

    _supported_modes: tuple[Mode, ...] = (Mode.AIRGAP, Mode.DUAL)

    def plan(
        self,
        case_id: str,
        evidence_manifest: EvidenceManifest,
        mode: Mode,
    ) -> InvestigationPlan:
        if mode not in self._supported_modes:
            raise ValueError(
                f"LocalPlanner cannot plan in mode={mode.value}; "
                f"supported backends: {[m.value for m in self._supported_modes]}. "
                f"Cloud-only mode requires the Anthropic SDK lane "
                f"(CloudPlanner). Mode dispatch lives in "
                f"verdict.runtime.mode_detect."
            )
        # W2.A.2 lands the real SGLang HTTP call: POST to /v1/chat/completions
        # with the qwen3_xml tool-call parser, the planner system prompt,
        # and the case_id-derived seed. The contract above is the test
        # surface; the body is intentionally unimplemented per §3.10.
        del case_id, evidence_manifest  # silenced until W2.A.2 wires them
        raise NotImplementedError(
            "LocalPlanner.plan inference backend lands in W2.A.2 "
            "(SGLang OpenAI-compat client + planner_system.md prompt + "
            "qwen3_xml tool-call parse)."
        )
