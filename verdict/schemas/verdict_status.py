"""VerdictStatus enum — §3.6 canonical six values.

ARCHITECTURE.md §1 and DEVPOST_COMPLIANCE.md derive from this list.
No other verdict strings are valid anywhere in the codebase.
"""
from enum import Enum


class VerdictStatus(str, Enum):
    """§3.6 — canonical verdict statuses. Exactly six values, no others.

    `VETTED_*` come out of a `VerifierStrategy` quorum; `EXHAUSTED_REPLAN`
    comes from `finalize_node` mapping the replan budget; `UNVERIFIABLE`
    is a first-class outcome rewarded by the SANS judge rubric.
    """

    VETTED_CLOUD = "vetted_cloud"
    VETTED_AIRGAP = "vetted_airgap"
    VETTED_DUAL = "vetted_dual"
    CONTESTED = "contested"
    UNVERIFIABLE = "unverifiable"
    EXHAUSTED_REPLAN = "exhausted_replan"
