# Verdict engineering swarm

Phase-0 scaffolding for the Claude Agent SDK build swarm.

**Read the spec first:** [`../docs/AGENT_SWARM.md`](../docs/AGENT_SWARM.md). Authority chain, role definitions, coordination protocol, and verification gates live there. This directory is the executable skeleton; the doc is the contract.

Quickstart (Phase-0 dry-run):

```bash
python -m swarm.conductor dry-run --plan docs/build
python -m swarm.state init --db swarm/swarm.db
python -m swarm.conductor load --plan docs/build --db swarm/swarm.db
python -m swarm.doctor
```

Live SDK invocations are not wired in Phase-0 — see open questions in the spec §14.
