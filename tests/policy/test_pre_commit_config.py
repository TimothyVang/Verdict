from __future__ import annotations

import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_pre_commit_config_enforces_commit_messages_and_no_mocks() -> None:
    config = (REPO_ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")

    assert "id: verdict-commit-msg" in config
    assert "id: check-no-mocks" in config
    assert r"\[W\d+\.[A-Z]\.\d+" in config


def test_pyproject_installs_pre_commit_tooling() -> None:
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    dev_deps = pyproject["dependency-groups"]["dev"]
    assert any(dep.startswith("pre-commit") for dep in dev_deps)
