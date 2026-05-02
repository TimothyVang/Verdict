"""W3.A.1 / W3.A.2 — `EngineOutput` record for cross-engine quorum.

A single engine's verdict on a hypothesis, reduced to the two surfaces the
quorum strategies discriminate on:

- ``artifact_paths`` — the set of artifact citations the engine produced.
  ARCHITECTURE.md §1 quorum dispatch uses Jaccard over these.
- ``mitre_technique`` — the engine's MITRE ATT&CK technique label.
  Identity equality required for ``VETTED_AIRGAP`` (row 3 of the dispatch).

This is the **pure-data carrier** between the SGLang transport layer
(which lands in W2.B) and the consensus functions on
``AirGapCrossEngine`` / ``DualLaneCrossEngine``. Splitting transport from
consensus lets the consensus invariants be unit-tested without an HTTP
client (CLAUDE.md §3.10 — no mocks against verdict internals; this is a
pure dataclass, not a mock).

The ``engine`` field is a free-form string identifier (e.g.
``"qwen3-30b-a3b-thinking"``, ``"glm-4.5-air"``, ``"claude-opus-4-5"``)
used by the strategies' family-distinctness checks: air-gap mode requires
two CROSS-engine outputs (refusing two Qwen3 outputs, which would
collapse cross-engine to self-consistency and break the independence
guarantee that air-gap mode is paying for).

We deliberately do NOT make this a Pydantic model. The cross-engine
consensus path runs once per hypothesis under the quorum_node and must
not allocate Pydantic validators on the hot path; a frozen dataclass
gives us value-object semantics, structural equality, and ``Hypothesis``-
schema-independent testability without the validation overhead.

Versioning note: a future schema upgrade that adds ``confidence`` or
``rationale_hash`` fields to ``EngineOutput`` lands as a new optional
field with a default; the consensus functions read ``artifact_paths``
and ``mitre_technique`` only and remain forward-compatible.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class EngineOutput:
    """A single engine's verdict carrier.

    Parameters
    ----------
    engine:
        Free-form identifier for the engine that produced this output
        (e.g. ``"qwen3-30b-a3b-thinking"``, ``"glm-4.5-air"``).
        Air-gap mode uses the family prefix (``qwen3``, ``glm``) to
        refuse degenerate same-family pairs.
    artifact_paths:
        The artifact paths the engine cites. ``ArtifactClass``-typed
        elsewhere; here a plain ``list[str]`` to keep the consensus
        function decoupled from the schema layer. Empty list is a
        first-class value (engine produced no findings or crashed
        silently); the strategies treat empty as DISAGREEMENT
        (ARCHITECTURE.md §1 empty-set rule).
    mitre_technique:
        MITRE ATT&CK technique ID (``T\\d{4}(\\.\\d{3})?``). Format
        validated upstream by the ``Hypothesis`` / ``Finding`` schemas;
        this dataclass treats it as an opaque string so the consensus
        function can be tested without instantiating a full
        ``Finding``.

    The constructor freezes a copy of ``artifact_paths`` so the
    consensus functions can rely on the input being stable across
    set conversions.
    """

    engine: str
    artifact_paths: list[str] = field(default_factory=list)
    mitre_technique: str = ""

    def family(self) -> str:
        """Return the engine family prefix (everything before the first ``-``).

        ``"qwen3-30b-a3b-thinking"`` -> ``"qwen3"``,
        ``"glm-4.5-air"``           -> ``"glm"``,
        ``"claude-opus-4-5"``       -> ``"claude"``.

        Used by ``AirGapCrossEngine`` to refuse two outputs from the
        same family — that would collapse cross-engine quorum to
        (degenerate) self-consistency and break the independence
        guarantee that air-gap mode is paying for.
        """
        if "-" not in self.engine:
            return self.engine
        return self.engine.split("-", 1)[0]


__all__ = ["EngineOutput"]
