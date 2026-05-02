"""verdict.planning — Plan-then-Execute orchestration layer.

Exposes the `Planner` Protocol and its two implementations
(`CloudPlanner` + `LocalPlanner`). The actual graph nodes
(`planner_node`, `planner_critique_node`, `pivot_node`,
`unverifiable_finalize_node`, …) land in `verdict/graph/`
across W2.B, W2.D, W3.D.

See `docs/ARCHITECTURE.md` §1 (modes) + §2 (LangGraph topology).
"""

from verdict.planning.planner import CloudPlanner, LocalPlanner, Planner
from verdict.planning.types import (
    EvidenceManifest,
    Hypothesis,
    InvestigationPlan,
    Mode,
)

__all__ = [
    "CloudPlanner",
    "EvidenceManifest",
    "Hypothesis",
    "InvestigationPlan",
    "LocalPlanner",
    "Mode",
    "Planner",
]
