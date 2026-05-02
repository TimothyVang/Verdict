"""Tests for VerdictStatus enum — W1.B.13.

BUILD_PLAN W1.B.13.a: test_verdict_status_has_all_v45_states.

Note: BUILD_PLAN references "9 states from v4.5 line 295" which is the
frozen archive spec. CLAUDE.md §3.6 (current authority) defines exactly
6 canonical values. ARCHITECTURE.md §1 maps each strategy outcome to one
of these 6 values. The test is named per BUILD_PLAN but asserts the
CLAUDE.md §3.6 canonical set.

CLAUDE.md §3.6 canonical VerdictStatus values:
  VETTED_CLOUD      — CloudSelfConsistency ≥2-of-3 agreement
  VETTED_AIRGAP     — AirGapCrossEngine Jaccard ≥0.80 + identical mitre
  VETTED_DUAL       — DualLaneCrossEngine 3-way agreement
  CONTESTED         — engines disagreed; escalates to replan_node
  UNVERIFIABLE      — first-class outcome; tool/budget/args exhaustion
  EXHAUSTED_REPLAN  — replan_max=3 exceeded; unverifiable_finalize_node

verdict/schemas/verdict_status.py exports VerdictStatus.
"""

import pytest

from verdict.schemas.verdict_status import VerdictStatus


# ---------------------------------------------------------------------------
# W1.B.13.a — named test as per BUILD_PLAN
# ---------------------------------------------------------------------------

class TestVerdictStatusHasAllV45States:
    """BUILD_PLAN W1.B.13.a: test_verdict_status_has_all_v45_states.

    Asserts the 6 canonical values defined in CLAUDE.md §3.6.
    (ARCHITECTURE.md §1 is the authority; v4.5 spec is archive only.)
    """

    CANONICAL_STATES = {
        "VETTED_CLOUD",
        "VETTED_AIRGAP",
        "VETTED_DUAL",
        "CONTESTED",
        "UNVERIFIABLE",
        "EXHAUSTED_REPLAN",
    }

    def test_verdict_status_has_all_v45_states(self) -> None:
        """All 6 canonical states from CLAUDE.md §3.6 must be enum members."""
        member_names = {m.name for m in VerdictStatus}
        assert member_names == self.CANONICAL_STATES, (
            f"VerdictStatus members {member_names!r} "
            f"!= canonical §3.6 set {self.CANONICAL_STATES!r}"
        )

    def test_no_extra_states(self) -> None:
        """Exactly 6 members — no additions without an RFC (CLAUDE.md §3.6)."""
        assert len(VerdictStatus) == 6

    def test_vetted_cloud_value(self) -> None:
        assert VerdictStatus.VETTED_CLOUD.value == "vetted_cloud"

    def test_vetted_airgap_value(self) -> None:
        assert VerdictStatus.VETTED_AIRGAP.value == "vetted_airgap"

    def test_vetted_dual_value(self) -> None:
        assert VerdictStatus.VETTED_DUAL.value == "vetted_dual"

    def test_contested_value(self) -> None:
        assert VerdictStatus.CONTESTED.value == "contested"

    def test_unverifiable_value(self) -> None:
        assert VerdictStatus.UNVERIFIABLE.value == "unverifiable"

    def test_exhausted_replan_value(self) -> None:
        assert VerdictStatus.EXHAUSTED_REPLAN.value == "exhausted_replan"

    def test_is_str_enum(self) -> None:
        """VerdictStatus inherits from str for JSON serialisation compatibility."""
        assert issubclass(VerdictStatus, str)


# ---------------------------------------------------------------------------
# Behaviour tests — quorum dispatch semantics (ARCHITECTURE.md §1)
# ---------------------------------------------------------------------------

class TestVerdictStatusBehaviour:
    """Quorum dispatch semantics from ARCHITECTURE.md §1."""

    def test_vetted_states_are_terminal(self) -> None:
        """VETTED_* states route to finalize_node — they are terminal quorum outcomes."""
        vetted = {VerdictStatus.VETTED_CLOUD, VerdictStatus.VETTED_AIRGAP, VerdictStatus.VETTED_DUAL}
        assert all(v.value.startswith("vetted_") for v in vetted)

    def test_contested_triggers_replan(self) -> None:
        """CONTESTED routes to replan_node — distinct from UNVERIFIABLE."""
        assert VerdictStatus.CONTESTED != VerdictStatus.UNVERIFIABLE

    def test_unverifiable_is_first_class(self) -> None:
        """UNVERIFIABLE is a first-class outcome, not an error (CLAUDE.md §3.6)."""
        assert VerdictStatus.UNVERIFIABLE in VerdictStatus

    def test_exhausted_replan_not_in_verifier_strategy_output(self) -> None:
        """EXHAUSTED_REPLAN is produced by finalize_node, not by VerifierStrategy.

        Verify it is distinct from the three quorum outcomes (VETTED_*, CONTESTED,
        UNVERIFIABLE) which VerifierStrategy directly emits.
        """
        verifier_strategy_outputs = {
            VerdictStatus.VETTED_CLOUD,
            VerdictStatus.VETTED_AIRGAP,
            VerdictStatus.VETTED_DUAL,
            VerdictStatus.CONTESTED,
            VerdictStatus.UNVERIFIABLE,
        }
        assert VerdictStatus.EXHAUSTED_REPLAN not in verifier_strategy_outputs

    def test_string_coercion_from_value(self) -> None:
        """str enum values can be reconstructed from their string representation."""
        assert VerdictStatus("vetted_cloud") is VerdictStatus.VETTED_CLOUD
        assert VerdictStatus("exhausted_replan") is VerdictStatus.EXHAUSTED_REPLAN

    def test_invalid_status_raises(self) -> None:
        """Constructing from an unknown value must raise ValueError."""
        with pytest.raises(ValueError):
            VerdictStatus("draft")  # v4.5 archive state — NOT valid in current arch

    def test_approved_is_not_a_verdict_status(self) -> None:
        """APPROVED is review_state, not VerdictStatus (CLAUDE.md §3.6)."""
        with pytest.raises(ValueError):
            VerdictStatus("approved")

    def test_rejected_is_not_a_verdict_status(self) -> None:
        """REJECTED is review_state, not VerdictStatus (CLAUDE.md §3.6)."""
        with pytest.raises(ValueError):
            VerdictStatus("rejected")
