"""W1.C.3 / W1.B.13 — `VerdictStatus` canonical enum.

CLAUDE.md §3.6 hard rule: verdict statuses are exactly

    VETTED_CLOUD | VETTED_AIRGAP | VETTED_DUAL
    | CONTESTED | UNVERIFIABLE | EXHAUSTED_REPLAN

No others. This module is the single source of truth for the enum;
``Finding.status``, ``VerdictResult.status``, the ``quorum_node``
dispatch table, and the Inspect AI scorers all import from here.

Any future v4.7+ extension that adds states must (1) update CLAUDE.md
§3.6, (2) bump this module's ``__schema_version__``, and (3) add a
migration in ``verdict/schemas/version.py`` (W1.B.12).

The values are URL-safe slug strings rather than ``auto()`` ints so
the persisted ledger / Langfuse traces remain human-readable across
schema versions. NIST SP 800-86 §5.1.2 chain-of-custody auditors will
read these in the JSONL ledger.
"""
from __future__ import annotations

from enum import StrEnum

# Bumping this is a coordinated change with CLAUDE.md §3.6 and the
# ledger migration in W1.B.12.
__schema_version__: int = 1


class VerdictStatus(StrEnum):
    """Canonical verdict status (CLAUDE.md §3.6, ARCHITECTURE.md §1).

    Engine-quorum verdict (immediate output of a ``VerifierStrategy``)
    and case verdict (persisted ``Finding.status``) share this enum
    but live on different objects:

    - A ``VerifierStrategy`` returns one of
      ``{VETTED_CLOUD, VETTED_AIRGAP, VETTED_DUAL, CONTESTED, UNVERIFIABLE}``.
    - ``finalize_node`` additionally maps ``EXHAUSTED_REPLAN`` from the
      ``replan_max=3`` budget; that one is a graph-level outcome, not
      a strategy-level outcome.
    """

    VETTED_CLOUD = "vetted_cloud"
    VETTED_AIRGAP = "vetted_airgap"
    VETTED_DUAL = "vetted_dual"
    CONTESTED = "contested"
    UNVERIFIABLE = "unverifiable"
    EXHAUSTED_REPLAN = "exhausted_replan"
