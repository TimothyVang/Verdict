from __future__ import annotations

from pathlib import Path

from scripts import check_no_mocks

FIXTURES = Path(__file__).parent / "fixtures"


def test_rejects_unittest_mock_import() -> None:
    violations = check_no_mocks.scan([FIXTURES / "has_mock_import.py"]).violations

    assert violations
    assert violations[0].path.name == "has_mock_import.py"
    assert violations[0].line_no == 1
    assert "unittest.mock" in violations[0].message


def test_reports_test_mode_branch() -> None:
    fixture = FIXTURES / "has_test_mode_branch.py"
    expected_line = next(
        line_no
        for line_no, line in enumerate(fixture.read_text(encoding="utf-8").splitlines(), start=1)
        if "TEST_MODE" in line
    )
    violations = check_no_mocks.scan([fixture]).violations

    assert violations
    assert violations[0].path.name == "has_test_mode_branch.py"
    assert violations[0].line_no == expected_line
    assert "TEST_MODE" in violations[0].message


def test_allows_third_party_boundary_patch() -> None:
    result = check_no_mocks.scan([FIXTURES / "third_party_boundary_patch.py"])

    assert result.violations == []


def test_cli_excludes_policy_fixtures() -> None:
    assert check_no_mocks.main(["--exclude-regex", r"tests/policy/fixtures/", str(FIXTURES)]) == 0


def test_default_scan_paths_cover_src_layout() -> None:
    paths = check_no_mocks.default_paths()

    assert Path("src/verdict") in paths
    assert Path("verdict") not in paths
