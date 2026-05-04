from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

import anyio
from pydantic import BaseModel

from verdict.schemas.plan import InvestigationPlan


class PlannerInput(BaseModel):
    """Input contract for planner implementations."""

    case_id: str
    evidence_summary: str
    playbook_prompt: str


class Planner(Protocol):
    """Planner contract bound once at gateway initialization."""

    def plan(self, request: PlannerInput) -> InvestigationPlan: ...


@dataclass(frozen=True)
class CloudPlanner:
    """Cloud planner lane configuration; execution requires a real cloud client."""

    model_name: str = "claude-sonnet-4-5-20250929"

    def plan(self, request: PlannerInput) -> InvestigationPlan:
        return parse_investigation_plan(self.generate_plan_text(request))

    def generate_plan_text(self, request: PlannerInput) -> str:
        try:
            from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, TextBlock, query
        except ImportError as error:  # pragma: no cover - exercised only when dependency missing.
            raise RuntimeError("claude-agent-sdk is required for CloudPlanner") from error

        async def _query_claude() -> str:
            chunks: list[str] = []
            options = ClaudeAgentOptions(
                system_prompt=_cloud_system_prompt(),
                allowed_tools=[],
            )
            async for message in query(prompt=_cloud_user_prompt(request), options=options):
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            chunks.append(block.text)
            return "\n".join(chunks).strip()

        text = anyio.run(_query_claude)
        if not text:
            raise RuntimeError("Claude Agent SDK returned no assistant text")
        return text


@dataclass(frozen=True)
class LocalPlanner:
    """Air-gap planner lane configuration; execution requires a real SGLang client."""

    endpoint: str = "http://localhost:30000/v1"

    def plan(self, request: PlannerInput) -> InvestigationPlan:
        raise RuntimeError("LocalPlanner requires the real SGLang planner client at gateway init")


def parse_investigation_plan(raw_text: str) -> InvestigationPlan:
    payload = _extract_json_object(raw_text)
    plan = InvestigationPlan.model_validate(json.loads(payload))
    if not plan.negative_hypotheses:
        raise ValueError("plan requires at least one negative hypothesis")
    return plan


def _extract_json_object(raw_text: str) -> str:
    fenced_start = raw_text.find("```json")
    if fenced_start != -1:
        content_start = raw_text.find("\n", fenced_start)
        fenced_end = raw_text.find("```", content_start + 1)
        if content_start != -1 and fenced_end != -1:
            return raw_text[content_start:fenced_end].strip()

    start = raw_text.find("{")
    end = raw_text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("Claude response did not contain a JSON object")
    return raw_text[start : end + 1]


def _cloud_system_prompt() -> str:
    return (
        "You are VERDICT's cloud-only forensic planning lane. Return one JSON object and no "
        "Markdown except an optional ```json fence. Findings and plans must use epistemic "
        "language, include at least one meaningful negative hypothesis, and use MITRE "
        "sub-techniques when determinable."
    )


def _cloud_user_prompt(request: PlannerInput) -> str:
    requested_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    return f"""
Create a VERDICT InvestigationPlan JSON object for this cloud-only v0 proof run.

Requested at: {requested_at}
Case ID: {request.case_id}

Evidence summary supplied by operator:
{request.evidence_summary}

Playbook context:
{request.playbook_prompt}

Required JSON shape:
{{
  "plan_id": "stable id string",
  "case_id": "{request.case_id}",
  "schema_version": 1,
  "positive_hypotheses": [
    {{
      "id": "h1",
      "polarity": "positive",
      "mitre_technique": "T1059.001",
      "artifact_families": ["process", "event_log"],
      "success_criteria": "measurable forensic corroboration criteria"
    }}
  ],
  "negative_hypotheses": [
    {{
      "id": "nh1",
      "polarity": "negative",
      "mitre_technique": "T1547.001",
      "artifact_families": ["registry", "scheduled_task"],
      "success_criteria": "measurable criteria for ruling this out"
    }}
  ],
  "tool_budget": 4,
  "pivot_budget": 15,
  "replan_budget": 3,
  "success_criteria": "overall measurable success criteria",
  "planner_cot_gzip_hash": "cloud-v0-not-captured"
}}
""".strip()
