from __future__ import annotations

import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_pre_commit_config_enforces_commit_messages_and_no_mocks() -> None:
    config = (REPO_ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")

    assert "id: verdict-commit-msg" in config
    assert "id: check-no-mocks" in config
    assert r"\[W\d+\.[A-Z]\.\d+" in config


def test_cargo_fmt_hook_does_not_require_bash_to_skip_missing_rust_project() -> None:
    config = (REPO_ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")

    assert "id: cargo-fmt-check" in config
    assert "entry: python -c" in config
    assert "entry: bash" not in config


def test_hallucination_gate_fails_closed_until_scorer_exists() -> None:
    workflow = (REPO_ROOT / ".github/workflows/eval-hallucination-gate.yml").read_text(
        encoding="utf-8"
    )

    assert "verdict_eval_cloud.py" in workflow
    assert "hallucination_rate" in workflow
    assert "scorer_not_implemented" in workflow
    assert "verdict doctor --mode cloud" in workflow


def test_hallucination_gate_checks_scorer_before_cloud_preflight() -> None:
    workflow = (REPO_ROOT / ".github/workflows/eval-hallucination-gate.yml").read_text(
        encoding="utf-8"
    )

    assert workflow.index("scorer_not_implemented") < workflow.index(
        "verdict doctor --mode cloud"
    )


def test_contributing_installs_pre_commit_without_missing_config_guard() -> None:
    contributing = (REPO_ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")

    assert "uv run pre-commit install --install-hooks" in contributing
    assert "test -f .pre-commit-config.yaml &&" not in contributing


def test_pyproject_installs_pre_commit_tooling() -> None:
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    dev_deps = pyproject["dependency-groups"]["dev"]
    assert any(dep.startswith("pre-commit") for dep in dev_deps)


def test_pyproject_declares_gateway_and_eval_dependencies() -> None:
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    deps = pyproject["project"]["dependencies"]
    assert any(dep.startswith("fastmcp") for dep in deps)
    assert any(dep.startswith("inspect-ai") for dep in deps)
