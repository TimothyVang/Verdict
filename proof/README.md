# VERDICT Proof Runs

This folder is the central location for v0 visual proof artifacts.

v0 scope is cloud-only Claude Agent SDK. SGLang, GPU, air-gap, and dual-mode proof are postponed until the Claude path works.

Run:

```bash
uv run python scripts/run_cloud_proof.py --evidence-summary-file <summary.txt>
```

Each run writes a timestamped folder under `proof/runs/` with logs, a raw Claude response, a schema-validated plan, ledger output, screenshot/video folders, and a review checklist.
