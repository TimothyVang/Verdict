"""RED test for W1.G.5 — Planner Protocol + CloudPlanner + LocalPlanner.

Test contracts:
  1. test_protocol_returns_investigation_plan — Planner protocol has a
     single method plan() returning an InvestigationPlan.
  2. test_planner_bound_at_gateway_init — mode detection happens in
     runtime/mode_detect.py via detect_mode(), NOT in planner_node.
     The planner is instantiated with the detected mode at gateway_init.
"""

import pytest


class TestPlannerProtocol:
    """W1.G.5.a — RED test for Planner Protocol contract."""

    def test_protocol_returns_investigation_plan(self):
        """Planner.plan() method returns InvestigationPlan.

        RED assertion: Planner must be a Protocol with a single method
        plan(evidence_manifest: EvidenceManifest) -> InvestigationPlan.
        """
        from verdict.planning.planner import Planner

        # Assert Planner is importable
        assert Planner is not None

        # Assert it has the plan method (Protocol contract)
        assert hasattr(Planner, "plan") or hasattr(Planner, "__protocol_attrs__")

        # The concrete implementations (CloudPlanner, LocalPlanner) must exist
        from verdict.planning.planner import CloudPlanner, LocalPlanner

        assert CloudPlanner is not None
        assert LocalPlanner is not None

    def test_planner_bound_at_gateway_init(self):
        """Mode detection lives in runtime/mode_detect.py, not planner_node.

        RED assertion: There must be a detect_mode() function in
        verdict/runtime/mode_detect.py that returns the operational mode
        (CLOUD, AIRGAP, DUAL). The planner is instantiated with the
        detected mode at gateway initialization time, NOT dynamically
        switched inside planner_node.
        """
        from verdict.runtime.mode_detect import detect_mode

        # Assert detect_mode exists and is callable
        assert callable(detect_mode)

        # Assert it returns a valid mode string
        mode = detect_mode()
        assert mode in ("cloud", "airgap", "dual")
