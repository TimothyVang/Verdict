"""Mode detection — CLOUD / AIRGAP / DUAL.

Per CLAUDE.md §3.4 (mode lock) and ARCHITECTURE.md §1:
- Cloud-only: Internet ✓ + GPU ✗
- Air-gap-only: Internet ✗ + GPU ✓
- Dual: Internet ✓ + GPU ✓

This module implements the detection logic. Mode is locked at case_init
and immutable thereafter. verdict resume <case_id> always uses the
original mode; upgrades happen via verdict reverify --mode <new>.
"""

import os
from typing import Literal


Mode = Literal["cloud", "airgap", "dual"]


def detect_mode() -> Mode:
    """Detect operational mode based on infrastructure availability.

    Detection order (per ARCHITECTURE.md §1):
    1. Check ANTHROPIC_API_KEY / ANTHROPIC_API reachable → cloud available.
    2. Check SGLang server available (default :30000) → gpu available.
    3. Dispatch based on combination.

    Operator override via --mode={cloud,airgap,dual} bypasses detection.

    Returns:
        "cloud" if only ANTHROPIC_API reachable.
        "airgap" if only SGLang reachable.
        "dual" if both reachable.
    """
    # W1.G.5 RED test only checks that this function exists and returns
    # a valid mode string. Full infrastructure probing implemented in W3.A.
    api_reachable = os.environ.get("ANTHROPIC_API_KEY") is not None
    sglang_reachable = os.environ.get("SGLANG_BASE_URL") is not None

    if api_reachable and sglang_reachable:
        return "dual"
    elif api_reachable:
        return "cloud"
    elif sglang_reachable:
        return "airgap"
    else:
        # Default: assume cloud (ANTHROPIC_API will be prompted for at gateway init)
        return "cloud"
