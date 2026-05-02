"""Finding schema validators — CLAUDE.md §3.1–§3.6 contract enforcement.

Every test in this file is the contract for one rule from §3.1–§3.6. The
validator is the contract; if a contributor can construct a Finding that
violates §3, the validator is broken.

§3.2 — multi-artifact corroboration: artifact_paths AND artifact_classes
       both have min_length=2. Execution-class techniques (T1059, T1106,
       T1204, T1218, T1543, T1547) require >=2 distinct ArtifactClass
       values, not just two paths in the same class.
§3.3 — Tier-1 caveat acknowledgment: citing AMCACHE without
       AMCACHE_LASTMODIFIED_NOT_EXEC is rejected.
§3.5 — MITRE regex: ^T\\d{4}(\\.\\d{3})?$ on Finding.mitre_technique.
§3.6 — VerdictStatus enum is exactly the canonical six values; review_state
       is orthogonal (DRAFT / APPROVED / REJECTED).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from verdict.schemas.artifact_class import ArtifactClass
from verdict.schemas.caveat_id import CaveatID
from verdict.schemas.finding import Finding, VerdictStatus


# ---------------------------------------------------------------------------
# Helper — minimal valid Finding kwargs. Every test starts from this and
# mutates one field to drive the validator under test.
# ---------------------------------------------------------------------------

def _valid_kwargs() -> dict:
    """A Finding that satisfies every validator. Tests mutate one field."""
    return {
        "finding_id": "F-001",
        "title": "evidence consistent with PowerShell encoded execution",
        "description": "psscan + sysmon_1 corroborate encoded -enc invocation",
        "mitre_technique": "T1059.001",
        "artifact_paths": [
            "/evidence/case_001/memory.raw::pid=4112",
            "/evidence/case_001/sysmon.evtx::record=8842",
        ],
        "artifact_classes": [
            ArtifactClass.PROCESS_MEMORY,
            ArtifactClass.SYSMON_1,
        ],
        "caveats_acknowledged": [],
        "status": VerdictStatus.VETTED_CLOUD,
        "review_state": "DRAFT",
    }


# ---------------------------------------------------------------------------
# §3.6 — VerdictStatus enum has exactly the six canonical values.
# ---------------------------------------------------------------------------


def test_verdict_status_enum_has_exactly_six_canonical_values() -> None:
    """§3.6 — Verdict statuses are exactly:
    VETTED_CLOUD, VETTED_AIRGAP, VETTED_DUAL, CONTESTED, UNVERIFIABLE,
    EXHAUSTED_REPLAN. No others."""
    expected = {
        "VETTED_CLOUD",
        "VETTED_AIRGAP",
        "VETTED_DUAL",
        "CONTESTED",
        "UNVERIFIABLE",
        "EXHAUSTED_REPLAN",
    }
    actual = {member.name for member in VerdictStatus}
    assert actual == expected, (
        f"VerdictStatus must be exactly {expected}; "
        f"got missing={expected - actual}, extra={actual - expected}"
    )
    assert len(VerdictStatus) == 6


def test_finding_accepts_every_canonical_verdict_status() -> None:
    for status in VerdictStatus:
        kw = _valid_kwargs()
        kw["status"] = status
        # All caveats should be present where the artifact_class triggers them.
        # _valid_kwargs uses PROCESS_MEMORY + SYSMON_1, neither of which
        # triggers a tier-1 caveat in the validator under test.
        Finding(**kw)


def test_finding_rejects_unknown_verdict_status_string() -> None:
    kw = _valid_kwargs()
    kw["status"] = "VETTED_QUANTUM"  # not in the canonical six
    with pytest.raises(ValidationError):
        Finding(**kw)


# ---------------------------------------------------------------------------
# §3.6 — review_state is a separate, orthogonal Literal field.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("review_state", ["DRAFT", "APPROVED", "REJECTED"])
def test_review_state_accepts_three_canonical_values(review_state: str) -> None:
    kw = _valid_kwargs()
    kw["review_state"] = review_state
    Finding(**kw)


def test_review_state_rejects_unknown_value() -> None:
    kw = _valid_kwargs()
    kw["review_state"] = "PENDING"
    with pytest.raises(ValidationError):
        Finding(**kw)


def test_review_state_is_separate_field_from_status() -> None:
    """A finding can have status=UNVERIFIABLE while review_state=APPROVED.
    The two enums are orthogonal per §3.6."""
    kw = _valid_kwargs()
    kw["status"] = VerdictStatus.UNVERIFIABLE
    kw["review_state"] = "APPROVED"
    f = Finding(**kw)
    assert f.status == VerdictStatus.UNVERIFIABLE
    assert f.review_state == "APPROVED"


# ---------------------------------------------------------------------------
# §3.2 — min_length=2 on BOTH artifact_paths AND artifact_classes.
# Both must be enforced; neither field by itself is sufficient.
# ---------------------------------------------------------------------------


def test_artifact_paths_min_length_2_rejects_single_path() -> None:
    kw = _valid_kwargs()
    kw["artifact_paths"] = ["/evidence/case_001/memory.raw::pid=4112"]
    with pytest.raises(ValidationError) as exc:
        Finding(**kw)
    assert "artifact_paths" in str(exc.value)


def test_artifact_paths_min_length_2_rejects_empty_list() -> None:
    kw = _valid_kwargs()
    kw["artifact_paths"] = []
    with pytest.raises(ValidationError):
        Finding(**kw)


def test_artifact_classes_min_length_2_rejects_single_class() -> None:
    kw = _valid_kwargs()
    kw["artifact_classes"] = [ArtifactClass.SYSMON_1]
    with pytest.raises(ValidationError) as exc:
        Finding(**kw)
    assert "artifact_classes" in str(exc.value)


def test_artifact_classes_min_length_2_rejects_empty_list() -> None:
    kw = _valid_kwargs()
    kw["artifact_classes"] = []
    with pytest.raises(ValidationError):
        Finding(**kw)


def test_finding_accepts_two_paths_and_two_classes() -> None:
    """Boundary — exactly two of each is the minimum permitted."""
    Finding(**_valid_kwargs())


# ---------------------------------------------------------------------------
# §3.2 — execution-class techniques require >=2 *distinct* ArtifactClass
# values (not just two paths in the same class).
# Validator: Finding._execution_requires_two_classes
# Triggers: T1059, T1106, T1204, T1218, T1543, T1547 (incl. sub-techniques).
# ---------------------------------------------------------------------------

EXECUTION_PARENT_TECHNIQUES = ("T1059", "T1106", "T1204", "T1218", "T1543", "T1547")


@pytest.mark.parametrize("parent", EXECUTION_PARENT_TECHNIQUES)
def test_execution_claim_with_duplicate_class_is_rejected(parent: str) -> None:
    """Two paths in PROCESS_MEMORY class is one class — rejected for
    execution-class techniques."""
    kw = _valid_kwargs()
    kw["mitre_technique"] = f"{parent}.001"
    kw["artifact_paths"] = [
        "/evidence/case_001/memory.raw::pid=4112",
        "/evidence/case_001/memory.raw::pid=4113",
    ]
    kw["artifact_classes"] = [
        ArtifactClass.PROCESS_MEMORY,
        ArtifactClass.PROCESS_MEMORY,
    ]
    with pytest.raises(ValidationError) as exc:
        Finding(**kw)
    msg = str(exc.value)
    assert "execution" in msg.lower() or "distinct" in msg.lower() or "classes" in msg.lower()


@pytest.mark.parametrize("parent", EXECUTION_PARENT_TECHNIQUES)
def test_execution_claim_with_two_distinct_classes_is_accepted(parent: str) -> None:
    kw = _valid_kwargs()
    kw["mitre_technique"] = f"{parent}.001"
    # PROCESS_MEMORY + SYSMON_1 — two distinct classes.
    Finding(**kw)


def test_execution_claim_bare_parent_technique_is_validated() -> None:
    """T1106 with no sub-technique is shape-valid (§3.5) and the
    execution-class validator must still apply: two classes required."""
    kw = _valid_kwargs()
    kw["mitre_technique"] = "T1106"
    kw["artifact_classes"] = [ArtifactClass.SYSMON_1, ArtifactClass.SYSMON_1]
    kw["artifact_paths"] = [
        "/evidence/case_001/sysmon.evtx::record=1",
        "/evidence/case_001/sysmon.evtx::record=2",
    ]
    with pytest.raises(ValidationError):
        Finding(**kw)


def test_non_execution_technique_with_duplicate_class_is_accepted() -> None:
    """T1014 (Rootkit) is not in the execution allowlist — duplicate
    artifact_class is permitted there (still subject to min_length=2)."""
    kw = _valid_kwargs()
    kw["mitre_technique"] = "T1014"
    kw["artifact_classes"] = [
        ArtifactClass.PROCESS_MEMORY,
        ArtifactClass.PROCESS_MEMORY,
    ]
    Finding(**kw)


# ---------------------------------------------------------------------------
# §3.3 — Tier-1 caveat acknowledgment.
# Citing AMCACHE in artifact_classes requires AMCACHE_LASTMODIFIED_NOT_EXEC
# in caveats_acknowledged. CaveatID is enforced at the schema layer.
# ---------------------------------------------------------------------------


def test_amcache_citation_without_caveat_is_rejected() -> None:
    """§3.3 — citing Amcache without AMCACHE_LASTMODIFIED_NOT_EXEC raises."""
    kw = _valid_kwargs()
    # Use a non-execution technique so we don't fail on §3.2 first. Pair
    # AMCACHE with EVTX_4688 (not PREFETCH — that would also need its own
    # caveat ack and obscure which validator failed).
    kw["mitre_technique"] = "T1014"
    kw["artifact_classes"] = [ArtifactClass.AMCACHE, ArtifactClass.EVTX_4688]
    kw["caveats_acknowledged"] = []  # forgot the caveat
    with pytest.raises(ValidationError) as exc:
        Finding(**kw)
    assert "amcache" in str(exc.value).lower() or "caveat" in str(exc.value).lower()


def test_amcache_citation_with_caveat_is_accepted() -> None:
    kw = _valid_kwargs()
    kw["mitre_technique"] = "T1014"
    kw["artifact_classes"] = [ArtifactClass.AMCACHE, ArtifactClass.EVTX_4688]
    kw["caveats_acknowledged"] = [CaveatID.AMCACHE_LASTMODIFIED_NOT_EXEC]
    Finding(**kw)


def test_prefetch_citation_without_caveat_is_rejected() -> None:
    """§3.3 — Prefetch citation requires PREFETCH_SSD_DISABLED ack."""
    kw = _valid_kwargs()
    kw["mitre_technique"] = "T1014"
    kw["artifact_classes"] = [ArtifactClass.PREFETCH, ArtifactClass.EVTX_4688]
    kw["caveats_acknowledged"] = []
    with pytest.raises(ValidationError):
        Finding(**kw)


def test_shimcache_citation_without_caveat_is_rejected() -> None:
    """§3.3 — ShimCache citation requires SHIMCACHE_ORDER_CHANGED_WIN81 ack."""
    kw = _valid_kwargs()
    kw["mitre_technique"] = "T1014"
    kw["artifact_classes"] = [ArtifactClass.SHIMCACHE, ArtifactClass.EVTX_4688]
    kw["caveats_acknowledged"] = []
    with pytest.raises(ValidationError):
        Finding(**kw)


def test_mft_citation_without_either_caveat_is_rejected() -> None:
    """§3.3 — MFT citation requires MFT_SI_STOMPABLE *or* USNJRNL_WRAPS.
    Either caveat satisfies the trigger because the existing ArtifactClass
    enum's MFT member covers both $MFT and $J/UsnJrnl."""
    kw = _valid_kwargs()
    kw["mitre_technique"] = "T1014"
    kw["artifact_classes"] = [ArtifactClass.MFT, ArtifactClass.EVTX_4688]
    kw["caveats_acknowledged"] = []
    with pytest.raises(ValidationError):
        Finding(**kw)


@pytest.mark.parametrize(
    "caveat",
    [CaveatID.MFT_SI_STOMPABLE, CaveatID.USNJRNL_WRAPS],
)
def test_mft_citation_with_either_caveat_is_accepted(caveat: CaveatID) -> None:
    kw = _valid_kwargs()
    kw["mitre_technique"] = "T1014"
    kw["artifact_classes"] = [ArtifactClass.MFT, ArtifactClass.EVTX_4688]
    kw["caveats_acknowledged"] = [caveat]
    Finding(**kw)


def test_caveats_acknowledged_only_accepts_caveat_ids() -> None:
    """The list is typed list[CaveatID], not list[str]. Bare strings that
    don't map to a CaveatID member must be rejected by Pydantic."""
    kw = _valid_kwargs()
    kw["caveats_acknowledged"] = ["not_a_real_caveat"]
    with pytest.raises(ValidationError):
        Finding(**kw)


def test_caveats_acknowledged_defaults_to_empty_list() -> None:
    kw = _valid_kwargs()
    kw.pop("caveats_acknowledged", None)
    f = Finding(**kw)
    assert f.caveats_acknowledged == []


# ---------------------------------------------------------------------------
# §3.5 — MITRE regex ^T\d{4}(\.\d{3})?$.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "good",
    [
        "T1055.012",  # canonical sub-technique example from §3.5
        "T1059.001",
        "T1218",      # bare technique permitted by regex shape
        "T1014",      # Rootkit — no sub upstream
        "T1106",      # Native API — no sub upstream
    ],
)
def test_mitre_regex_accepts_valid_shapes(good: str) -> None:
    kw = _valid_kwargs()
    kw["mitre_technique"] = good
    if good.startswith(EXECUTION_PARENT_TECHNIQUES):
        # Execution-class — keep two distinct classes (already in fixture).
        pass
    Finding(**kw)


@pytest.mark.parametrize(
    "bad",
    [
        "T123",         # too few digits
        "T12345",       # too many digits
        "T1055.12",     # sub-technique too short
        "T1055.0123",   # sub-technique too long
        "1055.012",     # missing T prefix
        "t1055.012",    # lower-case t
        "T1055-012",    # wrong separator
        "T1055.001a",   # trailing junk
        "T1055.001 ",   # trailing whitespace
        "",             # empty
        "MITRE-T1055",  # narrative form
    ],
)
def test_mitre_regex_rejects_malformed(bad: str) -> None:
    kw = _valid_kwargs()
    kw["mitre_technique"] = bad
    with pytest.raises(ValidationError):
        Finding(**kw)


def test_mitre_technique_none_is_rejected() -> None:
    """A Finding without a MITRE technique cannot pass the execution-class
    validator deterministically. The schema requires it."""
    kw = _valid_kwargs()
    kw["mitre_technique"] = None
    with pytest.raises(ValidationError):
        Finding(**kw)


# ---------------------------------------------------------------------------
# Round-trip — Finding serialises and deserialises through JSON without
# losing any §3 invariant.
# ---------------------------------------------------------------------------


def test_finding_round_trips_through_json() -> None:
    f = Finding(**_valid_kwargs())
    payload = f.model_dump_json()
    restored = Finding.model_validate_json(payload)
    assert restored == f
    assert restored.status == VerdictStatus.VETTED_CLOUD
    assert restored.artifact_classes == [
        ArtifactClass.PROCESS_MEMORY,
        ArtifactClass.SYSMON_1,
    ]
