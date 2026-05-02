"""W1.B.10 — Finding validators: execution-claim two-class rule + caveat triggers.

Tests the §3.2 execution-class validator and the §3.3 Tier-1 caveat
acknowledgment validators. Each test drives exactly one validator rule.

§3.2 execution-class validator (_execution_claims_need_two_classes):
  T1059, T1106, T1204, T1218, T1543, T1547 (and their sub-techniques)
  require >=2 *distinct* ArtifactClass values, not just two paths in the
  same class.

§3.3 caveat triggers (one validator per CaveatID where the trigger is
  pure artifact_class membership):
  AMCACHE    → AMCACHE_LASTMODIFIED_NOT_EXEC
  SHIMCACHE  → SHIMCACHE_ORDER_CHANGED_WIN81
  PREFETCH   → PREFETCH_SSD_DISABLED
  MFT        → MFT_SI_STOMPABLE  OR  USNJRNL_WRAPS  (either satisfies)

  Not encoded here (see finding.py docstring):
  LOGON_TYPE_3_VS_10 — triggered by EVTX_4624 class AND LogonType field.
  SYSMON_PROCESSGUID_OVER_PID — triggered by a correlation step, not class.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from verdict.schemas.artifact_class import ArtifactClass
from verdict.schemas.caveat_id import CaveatID
from verdict.schemas.finding import Finding, VerdictStatus


# ---------------------------------------------------------------------------
# Helper — minimal valid Finding kwargs for tests that only care about
# §3.2/§3.3 validators, not earlier field constraints.
# ---------------------------------------------------------------------------


def _base_kwargs() -> dict:
    """A Finding that satisfies every validator once they are implemented.

    Uses T1014 (Rootkit, not in execution class) + PROCESS_MEMORY + SYSMON_1
    so that we can test execution-class validators by substituting techniques
    without tripping on §3.2 field-level min_length=2.
    """
    return {
        "finding_id": "F-W1B10-001",
        "title": "evidence consistent with rootkit hiding",
        "description": "psscan vs pslist divergence indicates DKOM",
        "mitre_technique": "T1014",
        "artifact_paths": [
            "/evidence/case_001/memory.raw::pid=4112",
            "/evidence/case_001/memory.raw::pid=4200",
        ],
        "artifact_classes": [
            ArtifactClass.PROCESS_MEMORY,
            ArtifactClass.SYSMON_1,
        ],
        "caveats_acknowledged": [],
        "status": VerdictStatus.VETTED_CLOUD,
    }


# ---------------------------------------------------------------------------
# §3.2 — execution-class techniques require >=2 *distinct* ArtifactClass
# values. Validator name: _execution_claims_need_two_classes.
# ---------------------------------------------------------------------------

EXECUTION_PARENTS = ("T1059", "T1106", "T1204", "T1218", "T1543", "T1547")


@pytest.mark.parametrize("parent", EXECUTION_PARENTS)
def test_execution_claim_requires_two_classes_bare_parent(parent: str) -> None:
    """§3.2 — bare parent technique with duplicate artifact_class rejected."""
    kw = _base_kwargs()
    kw["mitre_technique"] = parent
    kw["artifact_classes"] = [
        ArtifactClass.PROCESS_MEMORY,
        ArtifactClass.PROCESS_MEMORY,
    ]
    with pytest.raises(ValidationError) as exc_info:
        Finding(**kw)
    msg = str(exc_info.value).lower()
    assert any(
        word in msg for word in ("execution", "distinct", "classes", "class")
    ), f"Expected validator message for {parent}; got: {exc_info.value}"


@pytest.mark.parametrize("parent", EXECUTION_PARENTS)
def test_execution_claim_requires_two_classes_sub_technique(parent: str) -> None:
    """§3.2 — sub-technique (T1059.001 etc.) with duplicate class also rejected."""
    kw = _base_kwargs()
    kw["mitre_technique"] = f"{parent}.001"
    kw["artifact_classes"] = [
        ArtifactClass.SYSMON_1,
        ArtifactClass.SYSMON_1,
    ]
    with pytest.raises(ValidationError):
        Finding(**kw)


@pytest.mark.parametrize("parent", EXECUTION_PARENTS)
def test_execution_claim_with_two_distinct_classes_accepted(parent: str) -> None:
    """§3.2 — two distinct artifact classes satisfies the execution validator."""
    kw = _base_kwargs()
    kw["mitre_technique"] = f"{parent}.001"
    # _base_kwargs already has PROCESS_MEMORY + SYSMON_1 (distinct).
    Finding(**kw)


def test_non_execution_technique_duplicate_class_accepted() -> None:
    """T1014 (Rootkit) is not an execution-class technique.
    Duplicate artifact_class is permitted (still subject to min_length=2)."""
    kw = _base_kwargs()
    kw["mitre_technique"] = "T1014"
    kw["artifact_classes"] = [
        ArtifactClass.PROCESS_MEMORY,
        ArtifactClass.PROCESS_MEMORY,
    ]
    Finding(**kw)


def test_non_execution_subtechnique_duplicate_class_accepted() -> None:
    """Regression guard — §3.2 split(".", 1)[0] correctly isolates parent.

    T1055.012 (Process Injection: Process Hollowing) has parent T1055, which
    is NOT in _EXECUTION_PARENTS. A Finding with two identical ArtifactClass
    values must be accepted; if the parent-extraction logic were broken
    (e.g. comparing the full "T1055.012" string against the frozenset instead
    of extracting "T1055" first) the validator would silently skip the check
    even when it should fire — or, if the set were keyed on full strings, it
    would fail to fire. This test guards that split(".", 1)[0] is the correct
    isolation mechanism for sub-techniques outside _EXECUTION_PARENTS.
    """
    kw = _base_kwargs()
    kw["mitre_technique"] = "T1055.012"
    kw["artifact_classes"] = [
        ArtifactClass.PROCESS_MEMORY,
        ArtifactClass.PROCESS_MEMORY,
    ]
    # Must not raise — T1055.012's parent T1055 is outside _EXECUTION_PARENTS.
    Finding(**kw)


# ---------------------------------------------------------------------------
# §3.3 — AMCACHE_LASTMODIFIED_NOT_EXEC (validator: _amcache_caveat_required)
# ---------------------------------------------------------------------------


def test_amcache_requires_caveat() -> None:
    """§3.3 — citing ArtifactClass.AMCACHE without
    CaveatID.AMCACHE_LASTMODIFIED_NOT_EXEC must be rejected."""
    kw = _base_kwargs()
    kw["mitre_technique"] = "T1014"
    kw["artifact_classes"] = [ArtifactClass.AMCACHE, ArtifactClass.EVTX_4688]
    kw["caveats_acknowledged"] = []
    with pytest.raises(ValidationError) as exc_info:
        Finding(**kw)
    msg = str(exc_info.value).lower()
    assert "amcache" in msg or "caveat" in msg


def test_amcache_with_caveat_accepted() -> None:
    kw = _base_kwargs()
    kw["mitre_technique"] = "T1014"
    kw["artifact_classes"] = [ArtifactClass.AMCACHE, ArtifactClass.EVTX_4688]
    kw["caveats_acknowledged"] = [CaveatID.AMCACHE_LASTMODIFIED_NOT_EXEC]
    Finding(**kw)


# ---------------------------------------------------------------------------
# §3.3 — SHIMCACHE_ORDER_CHANGED_WIN81
# ---------------------------------------------------------------------------


def test_shimcache_caveat_required_when_shimcache_cited() -> None:
    """§3.3 — citing ArtifactClass.SHIMCACHE without
    CaveatID.SHIMCACHE_ORDER_CHANGED_WIN81 must be rejected."""
    kw = _base_kwargs()
    kw["mitre_technique"] = "T1014"
    kw["artifact_classes"] = [ArtifactClass.SHIMCACHE, ArtifactClass.EVTX_4688]
    kw["caveats_acknowledged"] = []
    with pytest.raises(ValidationError) as exc_info:
        Finding(**kw)
    msg = str(exc_info.value).lower()
    assert "shimcache" in msg or "caveat" in msg


def test_shimcache_with_caveat_accepted() -> None:
    kw = _base_kwargs()
    kw["mitre_technique"] = "T1014"
    kw["artifact_classes"] = [ArtifactClass.SHIMCACHE, ArtifactClass.EVTX_4688]
    kw["caveats_acknowledged"] = [CaveatID.SHIMCACHE_ORDER_CHANGED_WIN81]
    Finding(**kw)


# ---------------------------------------------------------------------------
# §3.3 — PREFETCH_SSD_DISABLED
# ---------------------------------------------------------------------------


def test_prefetch_caveat_required_when_prefetch_cited() -> None:
    """§3.3 — citing ArtifactClass.PREFETCH without
    CaveatID.PREFETCH_SSD_DISABLED must be rejected."""
    kw = _base_kwargs()
    kw["mitre_technique"] = "T1014"
    kw["artifact_classes"] = [ArtifactClass.PREFETCH, ArtifactClass.EVTX_4688]
    kw["caveats_acknowledged"] = []
    with pytest.raises(ValidationError) as exc_info:
        Finding(**kw)
    msg = str(exc_info.value).lower()
    assert "prefetch" in msg or "caveat" in msg


def test_prefetch_with_caveat_accepted() -> None:
    kw = _base_kwargs()
    kw["mitre_technique"] = "T1014"
    kw["artifact_classes"] = [ArtifactClass.PREFETCH, ArtifactClass.EVTX_4688]
    kw["caveats_acknowledged"] = [CaveatID.PREFETCH_SSD_DISABLED]
    Finding(**kw)


# ---------------------------------------------------------------------------
# §3.3 — MFT: MFT_SI_STOMPABLE or USNJRNL_WRAPS (either satisfies).
# The ArtifactClass.MFT member covers both $MFT and $J/UsnJrnl.
# ---------------------------------------------------------------------------


def test_mft_caveat_required_when_mft_cited_without_any() -> None:
    """§3.3 — citing ArtifactClass.MFT without either MFT_SI_STOMPABLE or
    USNJRNL_WRAPS must be rejected."""
    kw = _base_kwargs()
    kw["mitre_technique"] = "T1014"
    kw["artifact_classes"] = [ArtifactClass.MFT, ArtifactClass.EVTX_4688]
    kw["caveats_acknowledged"] = []
    with pytest.raises(ValidationError) as exc_info:
        Finding(**kw)
    msg = str(exc_info.value).lower()
    assert "mft" in msg or "caveat" in msg


@pytest.mark.parametrize(
    "caveat",
    [CaveatID.MFT_SI_STOMPABLE, CaveatID.USNJRNL_WRAPS],
)
def test_mft_with_either_caveat_accepted(caveat: CaveatID) -> None:
    """Either MFT_SI_STOMPABLE or USNJRNL_WRAPS satisfies the MFT trigger."""
    kw = _base_kwargs()
    kw["mitre_technique"] = "T1014"
    kw["artifact_classes"] = [ArtifactClass.MFT, ArtifactClass.EVTX_4688]
    kw["caveats_acknowledged"] = [caveat]
    Finding(**kw)


# ---------------------------------------------------------------------------
# §3.3 — artifact classes that do NOT trigger a pure-membership caveat.
# EVTX_4688, SYSMON_1, NETWORK, REGISTRY_RUN, TASK_SCHEDULER,
# WMI_SUBSCRIPTION, PROCESS_MEMORY, YARA_HIT, SIGMA_HIT — citing these
# without any caveat must be accepted (no relevant trigger defined).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "cls",
    [
        ArtifactClass.EVTX_4688,
        ArtifactClass.SYSMON_1,
        ArtifactClass.NETWORK,
        ArtifactClass.REGISTRY_RUN,
        ArtifactClass.TASK_SCHEDULER,
        ArtifactClass.WMI_SUBSCRIPTION,
        ArtifactClass.PROCESS_MEMORY,
        ArtifactClass.YARA_HIT,
        ArtifactClass.SIGMA_HIT,
    ],
)
def test_non_triggered_artifact_class_accepted_without_caveat(cls: ArtifactClass) -> None:
    """Artifact classes with no pure-membership caveat trigger are accepted
    without any caveat acknowledgment."""
    kw = _base_kwargs()
    kw["mitre_technique"] = "T1014"
    kw["artifact_classes"] = [
        cls,
        ArtifactClass.SYSMON_1 if cls != ArtifactClass.SYSMON_1 else ArtifactClass.EVTX_4688,
    ]
    kw["caveats_acknowledged"] = []
    Finding(**kw)


# ---------------------------------------------------------------------------
# §3.5 — MITRE technique regex constraint on Finding.mitre_technique.
# Field(pattern=r"^T\d{4}(\.\d{3})?$") enforces shape at the field layer
# before any model_validator runs.
# ---------------------------------------------------------------------------


def test_mitre_bare_technique_accepted() -> None:
    """§3.5 — a well-formed bare technique (T####) is accepted."""
    kw = _base_kwargs()
    kw["mitre_technique"] = "T1055"
    Finding(**kw)


def test_mitre_sub_technique_accepted() -> None:
    """§3.5 — a well-formed sub-technique (T####.###) is accepted."""
    kw = _base_kwargs()
    kw["mitre_technique"] = "T1055.012"
    kw["artifact_classes"] = [
        ArtifactClass.PROCESS_MEMORY,
        ArtifactClass.PROCESS_MEMORY,
    ]
    Finding(**kw)


@pytest.mark.parametrize(
    "bad_technique",
    [
        "T123",  # too few digits in technique number
        "T12345",  # too many digits in technique number
        "t1055",  # lowercase T
        "1055",  # missing T prefix
        "T1055.",  # trailing dot without sub-technique digits
        "T1055.12",  # sub-technique only two digits (must be three)
        "T1055.1234",  # sub-technique four digits (must be exactly three)
        "T1055.abc",  # sub-technique non-numeric
        "",  # empty string
    ],
)
def test_malformed_mitre_technique_rejected(bad_technique: str) -> None:
    """§3.5 — malformed MITRE technique strings are rejected by Field(pattern=...)."""
    kw = _base_kwargs()
    kw["mitre_technique"] = bad_technique
    with pytest.raises(ValidationError) as exc_info:
        Finding(**kw)
    # Pydantic v2 pattern validation surfaces "string_pattern_mismatch"
    errors = exc_info.value.errors()
    assert any(
        e.get("type") in ("string_pattern_mismatch", "string_too_short")
        or "pattern" in str(e).lower()
        or "mitre" in str(e).lower()
        for e in errors
    ), f"Expected pattern-mismatch error for {bad_technique!r}; got: {exc_info.value}"
