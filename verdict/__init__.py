"""VERDICT — autonomous Windows DFIR / incident-response agent.

Top-level namespace. Subpackages:

  * verdict.planning   — Planner Protocol + CloudPlanner + LocalPlanner (W1.G.5 / W2.A)
  * verdict.schemas    — Pydantic v2 schema bundle (W1.B; lands across multiple branches)
  * verdict.verification — VerifierStrategy implementations (W1.C / W3.A)
  * verdict.tools      — SIFT tool wrappers (W2.A SIFT-side)
  * verdict.graph      — LangGraph topology (W2.B / W3.D)
  * verdict.ledger     — Append-only HMAC-signed ledger (W2.G / W1.G.6)

See `docs/ARCHITECTURE.md` for the authoritative architecture and
`docs/BUILD_PLAN.md` for the per-task sequencing.
"""
