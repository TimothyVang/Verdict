"""detect_mode() — infrastructure autodetection for VERDICT.

Probes the current environment and returns one of the three locked modes.
Operator may override via ``--mode`` flag; this module provides the
autodetection fallback.

Probe logic (ARCHITECTURE.md §1):
  - DUAL   if ANTHROPIC_API_KEY set *and* SGLANG_BASE_URL reachable.
  - CLOUD  if ANTHROPIC_API_KEY set *and* SGLANG_BASE_URL not reachable.
  - AIRGAP if ANTHROPIC_API_KEY not set *and* SGLANG_BASE_URL reachable.
  - Raises RuntimeError if neither service is reachable (``verdict doctor``
    should be run first to diagnose).

Full implementation is W5.A.1; the current version is the minimal real
implementation needed for mode-lock enforcement (W3.C).  It probes liveness
via a cheap HTTP GET rather than a full inference smoke test, so it is fast
enough to call on every ``verdict resume``.
"""

from __future__ import annotations

import os
import urllib.error
import urllib.request

from verdict.schemas.mode import Mode

# ---------------------------------------------------------------------------
# Internal probes
# ---------------------------------------------------------------------------

_ANTHROPIC_PROBE_URL = "https://api.anthropic.com"
_SGLANG_PROBE_TIMEOUT_S = 2.0


def _anthropic_api_key_present() -> bool:
    """Return True if ANTHROPIC_API_KEY is set to a non-empty value."""
    return bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())


def _sglang_reachable() -> bool:
    """Return True if the SGLang server at SGLANG_BASE_URL responds to /v1/models.

    SGLANG_BASE_URL defaults to ``http://localhost:30000`` if unset.
    A 200-series response (or any HTTP response including 4xx) is treated as
    "reachable" — the server is up even if the model list is empty.  A
    ``URLError`` (connection refused, timeout) means unreachable.
    """
    base_url = os.environ.get("SGLANG_BASE_URL", "http://localhost:30000").rstrip("/")
    probe_url = f"{base_url}/v1/models"
    try:
        req = urllib.request.Request(probe_url, method="GET")
        with urllib.request.urlopen(req, timeout=_SGLANG_PROBE_TIMEOUT_S):
            return True
    except urllib.error.HTTPError:
        # HTTP error (4xx/5xx) still means the server is up.
        return True
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def detect_mode() -> Mode:
    """Auto-detect the operational mode based on available infrastructure.

    Probe sequence (ARCHITECTURE.md §1):
      1. If ANTHROPIC_API_KEY present AND SGLang reachable → DUAL.
      2. If ANTHROPIC_API_KEY present only                 → CLOUD.
      3. If SGLang reachable only                          → AIRGAP.
      4. Neither reachable                                 → RuntimeError.

    Returns
    -------
    Mode
        The detected mode.

    Raises
    ------
    RuntimeError
        If neither Anthropic API key nor SGLang is reachable.  Run
        ``verdict doctor`` to diagnose.
    """
    has_api_key = _anthropic_api_key_present()
    has_sglang = _sglang_reachable()

    if has_api_key and has_sglang:
        return Mode.DUAL
    if has_api_key:
        return Mode.CLOUD
    if has_sglang:
        return Mode.AIRGAP

    raise RuntimeError(
        "No inference backend available: ANTHROPIC_API_KEY is not set and "
        "SGLang is not reachable at "
        f"{os.environ.get('SGLANG_BASE_URL', 'http://localhost:30000')}. "
        "Run 'verdict doctor' to diagnose."
    )
