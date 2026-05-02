"""Mode enum — three operational modes for VERDICT.

Modes are auto-detected at case_init and locked immutably thereafter.
See ARCHITECTURE.md §1 and CLAUDE.md §3.4.
"""

from enum import Enum


class Mode(str, Enum):
    """Three operational modes for VERDICT.

    CLOUD   — Internet reachable; no local GPU required.
              Planner: Claude (Agent SDK). Verifier: CloudSelfConsistency (n=3, temp=0.7).

    AIRGAP  — Internet unreachable; local GPU required.
              Planner+Executor: Qwen3 via SGLang.
              Verifier: AirGapCrossEngine (Qwen3 vs GLM-4.5-Air, Jaccard ≥ 0.80).

    DUAL    — Internet reachable AND local GPU available.
              Three-way verification: cloud + both locals must agree.
              Verifier: DualLaneCrossEngine.
    """

    CLOUD = "cloud"
    AIRGAP = "airgap"
    DUAL = "dual"
