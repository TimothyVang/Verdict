"""ComprehensionMismatch — ledger payload for executor disagreement.

Emitted by `comprehension_gate_node` when the gate concedes after
`MAX_CLARIFY_ITERATIONS=2` rounds of persistent disagreement among the
4 executor branches. The downstream `LedgerEmitter` (W2.C.3) writes
this as a `LedgerEntry(event_type="comprehension_check")`.

The schema preserves each executor's full parsed echo so a SANS judge
or human IR lead can reconstruct exactly which branch disagreed on
which key — chain-of-custody discipline per CLAUDE.md §9.

References:
- ARCHITECTURE.md §2 (comprehension-gate clarify budget)
- ARCHITECTURE.md §5 (LedgerEntry contract)
- BUILD_PLAN W2.B.3 (ComprehensionMismatch event with per-executor diff)
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

from verdict.schemas.ulid import new_ulid


class ExecutorEchoDiff(BaseModel):
    """One executor branch's parsed plan-comprehension echo, captured
    verbatim for forensic audit. Field names mirror
    `verdict.graph.nodes.CONSENSUS_KEYS`.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    branch_name: str = Field(min_length=1)
    parsed_positive_hypothesis_ids: list[str]
    parsed_negative_hypothesis_ids: list[str]
    parsed_success_criteria_hash: str = Field(min_length=1)


class ComprehensionMismatch(BaseModel):
    """Structured per-executor diff written to the ledger when the
    comprehension_gate concedes.

    `event_type` is fixed at `comprehension_check` — the LedgerEntry
    `event_type` Literal that ARCHITECTURE.md §5 enumerates. The judge
    ledger walker uses this discriminator.
    """

    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(default_factory=new_ulid)
    event_type: Literal["comprehension_check"] = "comprehension_check"
    case_id: str = Field(min_length=1)
    timestamp_utc: datetime
    clarify_iterations_spent: int = Field(ge=0)
    disagreeing_keys: list[str] = Field(min_length=1)
    per_executor: list[ExecutorEchoDiff] = Field(min_length=1)

    @field_validator("timestamp_utc")
    @classmethod
    def _require_tz(cls, v: datetime) -> datetime:
        """Reject naive datetimes — CLAUDE.md §3 demands UTC Z forensic
        timestamps; a naive datetime would silently downcast and break
        chain-of-custody reconstruction."""
        if v.tzinfo is None:
            raise ValueError("timestamp_utc must be TZ-aware (UTC)")
        return v

    @field_serializer("timestamp_utc")
    def _serialize_ts(self, v: datetime) -> str:
        """Serialize as ISO-8601 with explicit `Z` suffix — required by
        CLAUDE.md §3 forensic-doctrine timestamp rule.
        """
        # `isoformat()` on a UTC dt produces `+00:00`; replace with `Z`
        # to match the canonical SANS examiner format.
        s = v.isoformat()
        if s.endswith("+00:00"):
            return s[:-6] + "Z"
        return s
