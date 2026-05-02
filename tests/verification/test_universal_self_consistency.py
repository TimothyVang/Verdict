"""W3.A.3 — `UniversalSelfConsistency` (Chen et al. 2023) full implementation.

Chen et al. 2023 Universal Self-Consistency (arXiv:2311.17311) addresses the
case where Wang 2022 Self-Consistency (the n=3 majority-vote behind
``CloudSelfConsistency``) returns no clear majority, OR cross-engine quorum
returns ``CONTESTED``. USC is the **judge of last resort before declaring
CONTESTED** (CLAUDE.md §8 / ARCHITECTURE.md §1).

The W1.C.3 placeholder returned a hardcoded ``VETTED_CLOUD`` from
``verify(...)``. W3.A.3 lands the real strategy:

1. ``judge(candidates)`` clusters candidates by *substance*
   (artifact-set + mitre-technique tuple). When a clear majority cluster
   exists (e.g. 2-of-3), USC selects the first member of that cluster and
   returns a ``USCJudgement`` with ``selected_index`` and ``status`` set
   to a vetted state. Substance-clustering is the **deterministic**
   fallback Chen 2023 §3 prescribes; it is unit-testable without an LLM.
2. ``judge(candidates)`` falls back to an LLM-as-judge prompt when no
   substance majority exists. The LLM call lands in W2.B; until then
   ``judge()`` returns ``CONTESTED`` for the no-majority case (USC
   correctly admits "no winner" rather than invent one).
3. ``verify(...)`` (the Protocol method) raises ``NotImplementedError``
   until the W2.B transport plumbing arrives — USC is dispatched after
   another strategy returned CONTESTED, with that strategy's candidate
   outputs in hand; standalone ``verify()`` has no candidates to judge
   over and must refuse rather than silently mislabel a verdict.

The deterministic substance-majority behaviour is the load-bearing
testable surface here. Per BUILD_PLAN W3.A.3.a:

    given three Findings with rationale strings differing in structure
    but agreeing in substance on two of three,
    UniversalSelfConsistency.judge(findings).selected_index in {0, 1}
    (the two-of-three majority) and result.status == VerdictStatus.CONTESTED
    is NOT returned (USC is the judge of last resort before CONTESTED).
"""
from __future__ import annotations

import pytest

from verdict.schemas.verdict_status import VerdictStatus
from verdict.verification.engine_output import EngineOutput
from verdict.verification.strategy import (
    UniversalSelfConsistency,
    USCJudgement,
    VerdictResult,
)

# ---------------------------------------------------------------------------
# Fixture helpers — build candidates with the same surface shape USC sees
# from a CloudSelfConsistency n=3 trio or a CrossEngine pair
# ---------------------------------------------------------------------------


def _candidate(engine: str, paths: list[str], mitre: str = "T1003.001") -> EngineOutput:
    return EngineOutput(engine=engine, artifact_paths=paths, mitre_technique=mitre)


# ---------------------------------------------------------------------------
# W3.A.3.a load-bearing test — substance-majority pick
# ---------------------------------------------------------------------------


def test_judge_picks_most_consistent_rationale_among_n3() -> None:
    """W3.A.3.a — three candidates, two-of-three substance-majority.

    Two candidates cite the same artifact set + mitre_technique; the
    third dissents. USC must pick a majority member (index 0 or 1) and
    must NOT return CONTESTED — that is the literal definition of
    "judge of last resort before CONTESTED".
    """
    common_paths = ["C:/MFT", "C:/Amcache.hve", "C:/UsrClass.dat"]
    candidates = [
        _candidate("claude-opus-4-5-seed-a", common_paths, mitre="T1003.001"),
        _candidate("claude-opus-4-5-seed-b", common_paths, mitre="T1003.001"),
        _candidate("claude-opus-4-5-seed-c", ["C:/Different"], mitre="T1059.001"),
    ]

    result = UniversalSelfConsistency().judge(candidates)

    assert isinstance(result, USCJudgement)
    assert result.selected_index in {0, 1}, (
        f"USC must pick from the 2-of-3 substance majority "
        f"(indices 0,1 cite the same artifacts + mitre). got "
        f"selected_index={result.selected_index!r}"
    )
    assert result.status != VerdictStatus.CONTESTED, (
        "USC is the judge of last resort BEFORE declaring CONTESTED. "
        "When a substance-majority exists, USC must NOT return CONTESTED."
    )


def test_judge_picks_majority_when_majority_is_three_of_three() -> None:
    """Trivial unanimous case — all three candidates agree on substance.

    USC must select the first candidate (deterministic tie-breaker:
    earliest index) and return a vetted status.
    """
    common_paths = ["a", "b", "c"]
    candidates = [
        _candidate("eng-a", common_paths),
        _candidate("eng-b", common_paths),
        _candidate("eng-c", common_paths),
    ]
    result = UniversalSelfConsistency().judge(candidates)
    assert result.selected_index == 0
    assert result.status != VerdictStatus.CONTESTED


def test_judge_returns_contested_when_no_majority_exists() -> None:
    """Three candidates, three different substance clusters → no majority
    → USC has nothing to anchor on without an LLM-judge call → CONTESTED.

    Until W2.B wires the LLM-judge fallback, USC must correctly admit
    "no winner" rather than invent one. Returning a stub VETTED_*
    here would silently ship verdicts that aren't actually consistent.
    """
    candidates = [
        _candidate("eng-a", ["a", "b"], mitre="T1003.001"),
        _candidate("eng-b", ["c", "d"], mitre="T1059.001"),
        _candidate("eng-c", ["e", "f"], mitre="T1218.001"),
    ]
    result = UniversalSelfConsistency().judge(candidates)
    assert result.status == VerdictStatus.CONTESTED, (
        "Three pairwise-disagreeing candidates → no substance majority → "
        "CONTESTED until W2.B wires the LLM-judge fallback."
    )
    assert result.selected_index is None


def test_judge_uses_artifact_set_semantics_not_list_order() -> None:
    """Substance-clustering must compare artifact PATHS as sets, not
    ordered lists. Two candidates that cite the same artifacts in
    different orders must cluster as agreeing.
    """
    a = _candidate("eng-a", ["x", "y", "z"], mitre="T1003.001")
    b = _candidate("eng-b", ["z", "x", "y"], mitre="T1003.001")  # reordered
    c = _candidate("eng-c", ["q"], mitre="T1218.001")
    result = UniversalSelfConsistency().judge([a, b, c])
    assert result.selected_index in {0, 1}
    assert result.status != VerdictStatus.CONTESTED


def test_judge_clusters_require_identical_mitre_technique() -> None:
    """Substance-clustering uses BOTH artifact set AND mitre_technique.
    Same artifacts with different techniques are NOT in the same cluster
    (they disagree on interpretation, not corroboration).
    """
    common_paths = ["a", "b"]
    candidates = [
        _candidate("eng-a", common_paths, mitre="T1003.001"),
        _candidate("eng-b", common_paths, mitre="T1055.012"),
        _candidate("eng-c", common_paths, mitre="T1218.011"),
    ]
    # Three different singleton clusters — no majority.
    result = UniversalSelfConsistency().judge(candidates)
    assert result.status == VerdictStatus.CONTESTED


def test_judge_accepts_caller_specified_vetted_status() -> None:
    """USC is mode-agnostic — the dispatching ``quorum_node`` knows the
    locked mode and passes the appropriate ``vetted_status`` so USC's
    output carries the right VETTED_* discriminator.

    Default is ``VETTED_CLOUD`` (matches the W1.C.3 stub behaviour
    so callers that don't pass an explicit status get the same
    surface shape). Air-gap dispatch passes ``VETTED_AIRGAP``; dual
    passes ``VETTED_DUAL``.
    """
    common_paths = ["a", "b"]
    candidates = [
        _candidate("eng-a", common_paths),
        _candidate("eng-b", common_paths),
        _candidate("eng-c", ["x"]),
    ]
    usc = UniversalSelfConsistency()

    default_result = usc.judge(candidates)
    assert default_result.status == VerdictStatus.VETTED_CLOUD

    airgap_result = usc.judge(candidates, vetted_status=VerdictStatus.VETTED_AIRGAP)
    assert airgap_result.status == VerdictStatus.VETTED_AIRGAP

    dual_result = usc.judge(candidates, vetted_status=VerdictStatus.VETTED_DUAL)
    assert dual_result.status == VerdictStatus.VETTED_DUAL


def test_judge_rejects_non_vetted_vetted_status() -> None:
    """``vetted_status`` MUST be a VETTED_* member; passing CONTESTED
    or UNVERIFIABLE is a programming error at the dispatch site
    (the dispatcher would be asking USC to mislabel its own verdict).
    """
    common_paths = ["a", "b"]
    candidates = [
        _candidate("eng-a", common_paths),
        _candidate("eng-b", common_paths),
    ]
    usc = UniversalSelfConsistency()
    with pytest.raises(ValueError):
        usc.judge(candidates, vetted_status=VerdictStatus.CONTESTED)
    with pytest.raises(ValueError):
        usc.judge(candidates, vetted_status=VerdictStatus.UNVERIFIABLE)


def test_judge_requires_at_least_two_candidates() -> None:
    """USC needs at least two candidates to "pick the most consistent
    one". With one or zero candidates there is no judgement to make
    and USC raises rather than silently returning a vetted single.
    """
    usc = UniversalSelfConsistency()
    with pytest.raises(ValueError):
        usc.judge([])
    with pytest.raises(ValueError):
        usc.judge([_candidate("eng-a", ["a"])])


def test_judge_drops_empty_artifact_candidates_from_clustering() -> None:
    """Empty-set rule (ARCHITECTURE.md §1) carries: a candidate with
    empty ``artifact_paths`` is a silent-crash signal, not a vote.
    USC must NOT cluster empty-paths candidates with each other and
    declare a "majority of empties".
    """
    common = ["a", "b"]
    candidates = [
        _candidate("eng-a", common),
        _candidate("eng-b", []),  # silent crash
        _candidate("eng-c", []),  # silent crash
    ]
    # Two empties must NOT vet — they are not a substance majority.
    # eng-a is the only real candidate; with only one real candidate
    # there is no judgement to make → CONTESTED.
    result = UniversalSelfConsistency().judge(candidates)
    assert result.status == VerdictStatus.CONTESTED


# ---------------------------------------------------------------------------
# verify(...) Protocol method — transport-layer stub
# ---------------------------------------------------------------------------


def test_verify_raises_notimplemented_post_w3a3() -> None:
    """USC's Protocol-level ``verify(...)`` is the dispatch entry point.
    Standalone (without prior candidates) it has nothing to judge over
    and must raise — never silently return a fake VETTED_*.

    The W1.C.3 stub returned a hardcoded VETTED_CLOUD; W3.A.3 replaces
    that with NotImplementedError because the substantive USC entry
    point is ``judge(candidates)``, not standalone ``verify``.
    """
    with pytest.raises(NotImplementedError):
        UniversalSelfConsistency().verify(
            case_id="case_001_lolbins",
            hypothesis="Evidence consistent with rundll32 + comsvcs.MiniDump.",
            mitre_technique="T1003.001",
            evidence_summary="Sysmon ID 1; Prefetch RUNDLL32.EXE-...",
        )


def test_verify_returns_verdictresult_when_called_with_candidates() -> None:
    """USC's ``verify`` accepts an optional ``candidates`` kwarg; when
    provided it delegates to ``judge`` and returns a ``VerdictResult``
    so the Protocol contract is preserved on the dispatch path.

    This is the path ``quorum_node`` will take: invoke USC after
    another strategy returned CONTESTED, passing the prior candidate
    outputs.
    """
    common = ["a", "b"]
    candidates = [
        _candidate("eng-a", common),
        _candidate("eng-b", common),
        _candidate("eng-c", ["x"]),
    ]
    result = UniversalSelfConsistency().verify(
        case_id="case_001_lolbins",
        hypothesis="Evidence consistent with rundll32 + comsvcs.MiniDump.",
        mitre_technique="T1003.001",
        evidence_summary="Sysmon ID 1; Prefetch RUNDLL32.EXE-...",
        candidates=candidates,
    )
    assert isinstance(result, VerdictResult)
    assert result.status != VerdictStatus.CONTESTED


# ---------------------------------------------------------------------------
# Stub-marker upgrade — the W1.C.3 `STUB_FOR` must be cleared
# ---------------------------------------------------------------------------


def test_stub_for_marker_cleared_post_w3a3() -> None:
    """W1.C.3 left ``STUB_FOR`` populated as a regression-guard signal.
    W3.A.3 implements the real strategy; the marker must be empty.

    The corresponding regression-guard test in
    ``test_strategy_protocol.py`` (``test_usc_stub_does_not_pretend_
    to_implement_chen_2023``) is updated by this commit to assert the
    empty-string post-condition rather than the stub-warning text.
    """
    assert UniversalSelfConsistency.STUB_FOR == "", (
        "W3.A.3 lands the real Chen 2023 USC; STUB_FOR must be cleared "
        "to signal the stub-vs-real boundary moved."
    )
