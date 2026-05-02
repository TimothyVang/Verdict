"""Tests for verdict/schemas/hypothesis.py — W1.B.4.

TDD: these tests are written BEFORE the implementation.
Run → RED; implement → GREEN.
"""

import pytest
from pydantic import ValidationError

from verdict.schemas.artifact_class import ArtifactClass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _valid_positive(**overrides):
    """Minimal valid positive Hypothesis kwargs."""
    base = dict(
        id="h_lolbin_001",
        polarity="positive",
        mitre_technique="T1218.010",
        artifact_families=[ArtifactClass.PREFETCH, ArtifactClass.AMCACHE],
        success_criteria="regsvr32 invoked with /s /u /i: flags matching LOLBAS pattern",
    )
    base.update(overrides)
    return base


def _valid_negative(**overrides):
    """Minimal valid negative Hypothesis kwargs."""
    base = dict(
        id="h_no_inject_001",
        polarity="negative",
        mitre_technique="T1055.012",
        artifact_families=[ArtifactClass.PROCESS_MEMORY],
        success_criteria="no hollowed PE image found in malfind output",
    )
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# MITRE regex — §3.5
# ---------------------------------------------------------------------------

class TestMitreRegex:
    def test_valid_subtechnique_T1055_012_accepted(self):
        from verdict.schemas.hypothesis import Hypothesis
        h = Hypothesis(**_valid_positive(mitre_technique="T1055.012"))
        assert h.mitre_technique == "T1055.012"

    def test_valid_parent_T1014_accepted(self):
        """T1014 has no sub-technique; bare form must pass."""
        from verdict.schemas.hypothesis import Hypothesis
        h = Hypothesis(**_valid_positive(mitre_technique="T1014"))
        assert h.mitre_technique == "T1014"

    def test_valid_parent_T1106_accepted(self):
        from verdict.schemas.hypothesis import Hypothesis
        h = Hypothesis(**_valid_positive(mitre_technique="T1106"))
        assert h.mitre_technique == "T1106"

    def test_invalid_bare_Txxx_rejected(self):
        """Three-digit technique ID is not a valid MITRE ID."""
        from verdict.schemas.hypothesis import Hypothesis
        with pytest.raises(ValidationError, match=r"MITRE"):
            Hypothesis(**_valid_positive(mitre_technique="T123"))

    def test_invalid_format_no_T_prefix_rejected(self):
        from verdict.schemas.hypothesis import Hypothesis
        with pytest.raises(ValidationError, match=r"MITRE"):
            Hypothesis(**_valid_positive(mitre_technique="1055.012"))

    def test_invalid_subtechnique_two_digits_rejected(self):
        """Sub-technique must be exactly 3 digits."""
        from verdict.schemas.hypothesis import Hypothesis
        with pytest.raises(ValidationError, match=r"MITRE"):
            Hypothesis(**_valid_positive(mitre_technique="T1055.01"))

    def test_invalid_subtechnique_four_digits_rejected(self):
        from verdict.schemas.hypothesis import Hypothesis
        with pytest.raises(ValidationError, match=r"MITRE"):
            Hypothesis(**_valid_positive(mitre_technique="T1055.0123"))

    def test_invalid_extra_dot_rejected(self):
        from verdict.schemas.hypothesis import Hypothesis
        with pytest.raises(ValidationError, match=r"MITRE"):
            Hypothesis(**_valid_positive(mitre_technique="T1055.012.001"))

    def test_none_mitre_allowed_for_positive(self):
        """Positive hypotheses may omit mitre_technique."""
        from verdict.schemas.hypothesis import Hypothesis
        h = Hypothesis(**_valid_positive(mitre_technique=None))
        assert h.mitre_technique is None

    def test_valid_T1059_003_accepted(self):
        from verdict.schemas.hypothesis import Hypothesis
        h = Hypothesis(**_valid_positive(mitre_technique="T1059.003"))
        assert h.mitre_technique == "T1059.003"


# ---------------------------------------------------------------------------
# Negative hypothesis quality — §3.6
# ---------------------------------------------------------------------------

class TestNegativeHypothesisQuality:
    def test_valid_negative_hypothesis_accepted(self):
        from verdict.schemas.hypothesis import Hypothesis
        h = Hypothesis(**_valid_negative())
        assert h.polarity == "negative"

    def test_negative_requires_non_none_mitre_technique(self):
        """§3.6: negative hypothesis must name a MITRE technique."""
        from verdict.schemas.hypothesis import Hypothesis
        with pytest.raises(ValidationError, match=r"[Mm][Ii][Tt][Rr][Ee]"):
            Hypothesis(**_valid_negative(mitre_technique=None))

    def test_negative_requires_non_empty_artifact_families(self):
        """§3.6: negative hypothesis must name artifact families."""
        from verdict.schemas.hypothesis import Hypothesis
        with pytest.raises(ValidationError, match=r"artifact"):
            Hypothesis(**_valid_negative(artifact_families=[]))

    def test_deny_list_cosmic(self):
        from verdict.schemas.hypothesis import Hypothesis
        with pytest.raises(ValidationError, match=r"[Dd]egenerate|deni"):
            Hypothesis(**_valid_negative(success_criteria="The attacker is not using cosmic ray interference"))

    def test_deny_list_alien(self):
        from verdict.schemas.hypothesis import Hypothesis
        with pytest.raises(ValidationError, match=r"[Dd]egenerate|deni"):
            Hypothesis(**_valid_negative(success_criteria="No alien artifacts found"))

    def test_deny_list_nothing(self):
        from verdict.schemas.hypothesis import Hypothesis
        with pytest.raises(ValidationError, match=r"[Dd]egenerate|deni"):
            Hypothesis(**_valid_negative(success_criteria="nothing found in prefetch"))

    def test_deny_list_not_relevant(self):
        from verdict.schemas.hypothesis import Hypothesis
        with pytest.raises(ValidationError, match=r"[Dd]egenerate|deni"):
            Hypothesis(**_valid_negative(success_criteria="not-relevant"))

    def test_deny_list_na(self):
        from verdict.schemas.hypothesis import Hypothesis
        with pytest.raises(ValidationError, match=r"[Dd]egenerate|deni"):
            Hypothesis(**_valid_negative(success_criteria="n-a"))

    def test_deny_list_not_relevant_spaced(self):
        """'not relevant' (space form) also rejected per §3.6."""
        from verdict.schemas.hypothesis import Hypothesis
        with pytest.raises(ValidationError, match=r"[Dd]egenerate|deni"):
            Hypothesis(**_valid_negative(success_criteria="This is not relevant to the case"))

    def test_deny_list_na_slash_form(self):
        """'n/a' form also rejected."""
        from verdict.schemas.hypothesis import Hypothesis
        with pytest.raises(ValidationError, match=r"[Dd]egenerate|deni"):
            Hypothesis(**_valid_negative(success_criteria="n/a"))

    def test_positive_polarity_does_not_enforce_negative_rules(self):
        """Positive hypotheses are not subject to negative-quality rules."""
        from verdict.schemas.hypothesis import Hypothesis
        # None mitre + empty artifact_families would fail for negative;
        # for positive they must pass independently.
        h = Hypothesis(**_valid_positive())
        assert h.polarity == "positive"


# ---------------------------------------------------------------------------
# Round-trip / schema basics
# ---------------------------------------------------------------------------

class TestHypothesisRoundTrip:
    def test_model_dump_and_model_validate_roundtrip(self):
        from verdict.schemas.hypothesis import Hypothesis
        h = Hypothesis(**_valid_positive())
        data = h.model_dump()
        h2 = Hypothesis.model_validate(data)
        assert h == h2

    def test_polarity_must_be_positive_or_negative(self):
        from verdict.schemas.hypothesis import Hypothesis
        with pytest.raises(ValidationError):
            Hypothesis(**_valid_positive(polarity="maybe"))

    def test_id_required(self):
        from verdict.schemas.hypothesis import Hypothesis
        kwargs = _valid_positive()
        del kwargs["id"]
        with pytest.raises(ValidationError):
            Hypothesis(**kwargs)

    def test_artifact_families_accepts_artifact_class_enum(self):
        from verdict.schemas.hypothesis import Hypothesis
        h = Hypothesis(**_valid_positive(artifact_families=[ArtifactClass.MFT, ArtifactClass.SYSMON_1]))
        assert ArtifactClass.MFT in h.artifact_families
