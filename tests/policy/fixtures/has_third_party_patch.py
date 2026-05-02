"""Allowed-pattern fixture for tests/policy/test_no_mocks_hook.py.

Patching a third-party library at the system boundary in a single
targeted test is explicitly permitted by CLAUDE.md §3.10. The scanner
must NOT flag this file solely on the presence of `from unittest.mock
import patch` when the patch target is a third-party module (httpx).

The scanner only flags imports of `unittest.mock` / `unittest -> mock`
themselves — third-party boundary patching shows up as a permitted
``@patch("httpx.get")`` decoration site in tests. CLAUDE.md §3.10
forbids patching `verdict.*` internals; httpx is a third-party HTTP
client and is therefore allowed.

DO NOT import this module outside the policy test suite.
"""

from __future__ import annotations

from unittest.mock import patch  # third-party boundary patching is allowed


@patch("httpx.get")
def fake_test_function(mock_get: object) -> None:
    """Stand-in for a single targeted test that patches httpx at the boundary."""
    del mock_get
