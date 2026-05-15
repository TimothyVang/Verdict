from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _credential_helper_env(**updates: str) -> dict[str, str]:
    keep = ("COMSPEC", "PATH", "PATHEXT", "SYSTEMROOT", "TEMP", "TMP", "WINDIR")
    env = {key: os.environ[key] for key in keep if key in os.environ}
    env["PYTHONPATH"] = str(REPO_ROOT / "src")
    env.update(updates)
    return env


def _run_credentials_helper(env: dict[str, str]) -> dict[str, object]:
    result = subprocess.run(
        [sys.executable, "-m", "verdict.cli.credentials", "--json"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        check=True,
        text=True,
        timeout=30,
    )
    assert "secret-token" not in result.stdout
    return json.loads(result.stdout)


def _run_credentials_helper_from(cwd: Path, env: dict[str, str]) -> tuple[str, dict[str, object]]:
    result = subprocess.run(
        [sys.executable, "-m", "verdict.cli.credentials", "--json"],
        cwd=cwd,
        env=env,
        capture_output=True,
        check=True,
        text=True,
        timeout=30,
    )
    return result.stdout, json.loads(result.stdout)


def test_detects_oauth_token_first() -> None:
    result = _run_credentials_helper(
        _credential_helper_env(
            CLAUDE_CODE_OAUTH_TOKEN="secret-token",
            ANTHROPIC_API_KEY="secret-anthropic",
            OPENROUTER_API_KEY="secret-openrouter",
        )
    )

    assert result == {
        "cloud_available": True,
        "mode": "oauth",
        "source": "CLAUDE_CODE_OAUTH_TOKEN",
    }


def test_detects_anthropic_when_oauth_absent() -> None:
    result = _run_credentials_helper(
        _credential_helper_env(ANTHROPIC_API_KEY="secret-token")
    )

    assert result == {
        "cloud_available": True,
        "mode": "anthropic",
        "source": "ANTHROPIC_API_KEY",
    }


def test_reports_unconfigured_without_cloud_credentials(tmp_path: Path) -> None:
    _, result = _run_credentials_helper_from(tmp_path, _credential_helper_env())

    assert result == {"cloud_available": False, "mode": "unconfigured", "source": None}


def test_credentials_helper_loads_local_env_without_printing_secret(tmp_path: Path) -> None:
    secret = "secret-token"
    (tmp_path / ".env").write_text(f"ANTHROPIC_API_KEY={secret}\n", encoding="utf-8")

    stdout, result = _run_credentials_helper_from(tmp_path, _credential_helper_env())

    assert result == {
        "cloud_available": True,
        "mode": "anthropic",
        "source": "ANTHROPIC_API_KEY",
    }
    assert secret not in stdout


def test_install_script_runs_credential_helper_and_hook_install() -> None:
    script = (REPO_ROOT / "scripts" / "install.sh").read_text(encoding="utf-8")

    assert "python -m verdict.cli.credentials --json" in script
    assert "uv sync --all-extras" in script
    assert "uv run pre-commit install --install-hooks" in script
