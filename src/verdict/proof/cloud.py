from __future__ import annotations

import argparse
import os
import platform
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from verdict.ledger.writer import LedgerWriter
from verdict.planning.planner import CloudPlanner, PlannerInput, parse_investigation_plan


@dataclass(frozen=True)
class ProofRun:
    path: Path
    timestamp: str


def create_proof_run(root: Path, *, timestamp: str | None = None) -> ProofRun:
    timestamp = timestamp or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_path = root / "runs" / timestamp
    (run_path / "screenshots").mkdir(parents=True, exist_ok=True)
    (run_path / "video").mkdir(parents=True, exist_ok=True)
    _write_if_missing(root / "README.md", _proof_readme())
    (run_path / "review.md").write_text(_review_checklist(), encoding="utf-8")
    return ProofRun(path=run_path, timestamp=timestamp)


def write_blocker_run(run: ProofRun, *, reason: str) -> None:
    _write_environment(run)
    (run.path / "service-checks.log").write_text(f"BLOCKED: {reason}\n", encoding="utf-8")
    (run.path / "run-summary.md").write_text(
        f"# Cloud Proof Run {run.timestamp}\n\nStatus: BLOCKED\n\nReason: {reason}\n",
        encoding="utf-8",
    )
    _write_ledger(run, event_type="cloud_proof_blocked", payload={"reason": reason})


def run_cloud_proof(
    *,
    proof_root: Path,
    evidence_summary_file: Path | None,
    case_id: str,
) -> int:
    _load_dotenv_if_present()
    run = create_proof_run(proof_root)
    _write_environment(run)

    readiness_error = _cloud_readiness_error(evidence_summary_file)
    if readiness_error is not None:
        write_blocker_run(run, reason=readiness_error)
        print(f"Cloud proof blocked. Artifacts: {run.path}")
        print(readiness_error)
        return 2

    assert evidence_summary_file is not None
    evidence_summary = evidence_summary_file.read_text(encoding="utf-8")
    request = PlannerInput(
        case_id=case_id,
        evidence_summary=evidence_summary,
        playbook_prompt="Cloud-only v0: create a plan from the operator evidence summary.",
    )

    planner = CloudPlanner()
    raw_response = planner.generate_plan_text(request)
    (run.path / "cloud-agent-response.raw.txt").write_text(raw_response, encoding="utf-8")
    plan = parse_investigation_plan(raw_response)
    plan_path = run.path / "investigation-plan.json"
    plan_path.write_text(plan.model_dump_json(indent=2), encoding="utf-8")
    (run.path / "validation.log").write_text(
        "InvestigationPlan schema validation passed.\n"
        f"Positive hypotheses: {len(plan.positive_hypotheses)}\n"
        f"Negative hypotheses: {len(plan.negative_hypotheses)}\n",
        encoding="utf-8",
    )
    _write_ledger(
        run,
        event_type="cloud_proof_plan_validated",
        payload={"case_id": case_id, "plan_id": plan.plan_id, "plan_path": str(plan_path)},
    )
    (run.path / "run-summary.md").write_text(
        f"# Cloud Proof Run {run.timestamp}\n\n"
        "Status: PASS\n\n"
        f"Case ID: {case_id}\n\n"
        f"Plan ID: {plan.plan_id}\n\n"
        f"Proof artifacts: `{run.path}`\n",
        encoding="utf-8",
    )
    print(f"Cloud proof passed. Artifacts: {run.path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run VERDICT cloud-only Claude proof harness.")
    parser.add_argument("--proof-root", default="proof", type=Path)
    parser.add_argument("--evidence-summary-file", type=Path)
    parser.add_argument("--case-id", default="cloud-v0-proof")
    args = parser.parse_args(argv)
    return run_cloud_proof(
        proof_root=args.proof_root,
        evidence_summary_file=args.evidence_summary_file,
        case_id=args.case_id,
    )


def _cloud_readiness_error(evidence_summary_file: Path | None) -> str | None:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return "ANTHROPIC_API_KEY is not configured"
    if evidence_summary_file is None:
        return "--evidence-summary-file is required for cloud proof runs"
    if not evidence_summary_file.is_file():
        return f"evidence summary file does not exist: {evidence_summary_file}"
    try:
        import claude_agent_sdk  # noqa: F401
    except ImportError:
        return "claude-agent-sdk is not installed"
    return None


def _write_environment(run: ProofRun) -> None:
    (run.path / "environment.txt").write_text(
        "\n".join(
            [
                f"timestamp={run.timestamp}",
                f"python={platform.python_version()}",
                f"platform={platform.platform()}",
                "mode=CLOUD",
                "sglang=postponed",
                "gpu=not_required_for_cloud_v0",
                f"anthropic_api_key_present={bool(os.environ.get('ANTHROPIC_API_KEY'))}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _write_ledger(run: ProofRun, *, event_type: str, payload: dict[str, str]) -> None:
    hmac_key = sha256(f"verdict-proof-{run.timestamp}".encode()).digest()
    LedgerWriter(run.path / "ledger.jsonl", hmac_key=hmac_key).write(
        {
            "entry_id": f"{run.timestamp}-{event_type}",
            "case_id": payload.get("case_id", "cloud-v0-proof"),
            "event_type": event_type,
            "timestamp_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "mode_at_case_init": "CLOUD",
            "payload": payload,
        }
    )


def _write_if_missing(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(text, encoding="utf-8")


def _load_dotenv_if_present(path: Path = Path(".env")) -> None:
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _proof_readme() -> str:
    return """# VERDICT Proof Runs

This folder contains visual and textual proof artifacts for v0 demo runs.

v0 scope is cloud-only Claude Agent SDK. SGLang, GPU, air-gap, and dual-mode proof are
postponed until the Claude path works.
"""


def _review_checklist() -> str:
    return """# Visual Proof Review

Confirm screenshots or video show:

- Claude Agent SDK cloud-only command launch.
- Cloud readiness result without exposing secrets.
- Claude response file created.
- `InvestigationPlan` schema validation passed.
- At least one negative hypothesis in `investigation-plan.json`.
- `ledger.jsonl`, `run-summary.md`, and proof folders visible.
- SGLang/GPU marked as postponed, not required for this v0 run.
"""
