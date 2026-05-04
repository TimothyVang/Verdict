from __future__ import annotations

import pytest

from verdict.planning.planner import parse_investigation_plan


def test_parse_investigation_plan_accepts_fenced_json() -> None:
    raw = """
    Claude explanation before JSON.

    ```json
    {
      "plan_id": "plan-cloud-v0",
      "case_id": "case-cloud-v0",
      "schema_version": 1,
      "positive_hypotheses": [
        {
          "id": "h1",
          "polarity": "positive",
          "mitre_technique": "T1059.001",
          "artifact_families": ["process", "event_log"],
          "success_criteria": "Corroborate PowerShell across process and event artifacts."
        }
      ],
      "negative_hypotheses": [
        {
          "id": "nh1",
          "polarity": "negative",
          "mitre_technique": "T1547.001",
          "artifact_families": ["registry", "scheduled_task"],
          "success_criteria": "Rule out common Run key persistence and scheduled task persistence."
        }
      ],
      "tool_budget": 4,
      "pivot_budget": 15,
      "replan_budget": 3,
      "success_criteria": "Return only claims supported by at least two artifact classes.",
      "planner_cot_gzip_hash": "cloud-v0-not-captured"
    }
    ```
    """

    plan = parse_investigation_plan(raw)

    assert plan.case_id == "case-cloud-v0"
    assert plan.positive_hypotheses[0].mitre_technique == "T1059.001"
    assert plan.negative_hypotheses[0].polarity == "negative"


def test_parse_investigation_plan_rejects_missing_negative_hypothesis() -> None:
    raw = """
    {
      "plan_id": "plan-cloud-v0",
      "case_id": "case-cloud-v0",
      "schema_version": 1,
      "positive_hypotheses": [],
      "negative_hypotheses": [],
      "tool_budget": 1,
      "success_criteria": "insufficient",
      "planner_cot_gzip_hash": "cloud-v0-not-captured"
    }
    """

    with pytest.raises(ValueError, match="at least one negative hypothesis"):
        parse_investigation_plan(raw)
