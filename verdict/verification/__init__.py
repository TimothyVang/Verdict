"""Verifier strategies (W1.C, W3.A).

`VerifierStrategy` Protocol + per-mode implementations:

- `CloudSelfConsistency`  — n=3 at temp=0.7 with three blake3-keyed seeds
                             (Wang et al. 2022, arXiv:2203.11171).
- `AirGapCrossEngine`     — Qwen3 vs GLM-4.5-Air; Jaccard >=0.80.
- `DualLaneCrossEngine`   — cloud + both locals; cloud agrees with >=1 local
                             AND locals agree with each other.
- `UniversalSelfConsistency` — Chen et al. 2023, judge of last resort.

Quorum dispatch lives in the LangGraph `quorum_node` (W2.B); this package
just hosts the strategies + the seed-derivation helper.
"""
