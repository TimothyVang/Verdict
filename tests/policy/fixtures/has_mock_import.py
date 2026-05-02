"""Intentional violation fixture for tests/policy/test_no_mocks_hook.py.

This file is excluded from the no-mocks AST walker's default sweep
(see scripts/check_no_mocks.py EXCLUDED_DIRS) and is loaded explicitly
by the test to confirm the scanner flags `import unittest.mock`.

DO NOT import this module from production code or any non-policy test.
"""

from __future__ import annotations

import unittest.mock  # noqa: F401  -- intentional violation under test
