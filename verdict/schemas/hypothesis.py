"""Hypothesis schema — W1.B.4.

A Hypothesis is a claim the investigation is testing (positive OR negative).
Validators enforce:
  - MITRE technique shape: ^T\\d{4}(\\.\\d{3})?$  (§3.5)
  - Negative hypotheses must name a MITRE technique (§3.6)
  - Negative hypotheses must have non-empty artifact_families (§3.6)
  - Deny-list rejects degenerate negative success_criteria (§3.6):
      cosmic | alien | nothing | not-relevant | not relevant | n-a | n/a
"""

import re
from typing import Literal

from pydantic import BaseModel, field_validator, model_validator

from verdict.schemas.artifact_class import ArtifactClass

_MITRE_RE = re.compile(r"^T\d{4}(\.\d{3})?$")

# Deny-list tokens checked via substring match on lower-cased success_criteria.
# CLAUDE.md §3.6: cosmic, alien, nothing, not-relevant, n-a
# spec v4.4 adds: "not relevant", "n/a"
_DENY_TOKENS: tuple[str, ...] = (
    "cosmic",
    "alien",
    "nothing",
    "not-relevant",
    "not relevant",
    "n-a",
    "n/a",
)


class Hypothesis(BaseModel):
    """A claim the investigation is testing — positive OR negative.

    Positive hypotheses posit that a specific technique was used and
    name the artifacts expected to confirm it.

    Negative hypotheses assert that a specific technique was NOT used;
    they are required to be specific (MITRE technique + artifact families)
    so the investigation can rule out alternatives, not just assert absence.
    """

    id: str
    polarity: Literal["positive", "negative"]
    mitre_technique: str | None = None
    artifact_families: list[ArtifactClass] = []
    success_criteria: str

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
    def _negative_hypothesis_quality(self) -> "Hypothesis":
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
