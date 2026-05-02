# ruff: noqa: S101
"""Tests for scripts/check_no_mocks.py -- the §3.10 mechanical hook.

The AST walker enforces CLAUDE.md §3.10 ("no mocks, no stubs, no
placeholders"). It rejects mock-style imports and conditional code
paths gated on test-mode env flags, while allowing third-party
boundary patching (e.g., ``from unittest.mock import patch`` to stub
``httpx`` in a single targeted test).

The scanner exposes a ``scan(paths)`` API returning an object with a
``violations`` list; each violation reports the offending file path
and line number. Tests below are RED until ``scripts/check_no_mocks.py``
is implemented (W1.A.9.b).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "check_no_mocks.py"
FIXTURES = REPO_ROOT / "tests" / "policy" / "fixtures"


@pytest.fixture(scope="module")
def check_no_mocks() -> ModuleType:
    """Load scripts/check_no_mocks.py as a module by file path.

    The script ships under scripts/ rather than as a package, so it
    cannot be imported by name. We load it via importlib.util once per
    module and cache it.
    """
    spec = importlib.util.spec_from_file_location("check_no_mocks", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        pytest.fail(f"cannot load {SCRIPT_PATH} -- implement W1.A.9.b")
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_no_mocks"] = module
    spec.loader.exec_module(module)
    return module


def test_rejects_unittest_mock_import(check_no_mocks: ModuleType) -> None:
    """`import unittest.mock` is a §3.10 violation.

    The fixture file contains a literal ``import unittest.mock`` on a
    known line. The scanner must report at least one violation, and
    the offending line number / file path must be present in the
    violation record so the operator can fix it.
    """
    target = FIXTURES / "has_mock_import.py"
    assert target.is_file(), f"fixture missing: {target}"

    report = check_no_mocks.scan([str(target)])
    assert report.violations, "scanner missed `import unittest.mock`"

    paths = {str(Path(v.path).resolve()) for v in report.violations}
    assert str(target.resolve()) in paths, f"violation file mismatch; got paths={paths!r}"
    # Offending line number is reported (>= 1) and refers to a real line.
    for violation in report.violations:
        assert violation.line >= 1, f"non-positive line in {violation!r}"


def test_allows_third_party_boundary_patch(check_no_mocks: ModuleType) -> None:
    """`from unittest.mock import patch` plus ``@patch("httpx.get")`` is allowed.

    CLAUDE.md §3.10 explicitly permits patching a third-party library
    at the system boundary in a single targeted test. The scanner
    rejects ``import unittest.mock`` and ``from unittest import mock``
    but must NOT flag ``from unittest.mock import patch`` since that
    is the canonical syntax for boundary patching.
    """
    target = FIXTURES / "has_third_party_patch.py"
    assert target.is_file(), f"fixture missing: {target}"

    report = check_no_mocks.scan([str(target)])
    assert (
        not report.violations
    ), f"scanner over-flagged third-party boundary patch: {report.violations!r}"
