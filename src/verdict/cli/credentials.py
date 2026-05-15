from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

from verdict.runtime.env import load_dotenv_if_present


@dataclass(frozen=True)
class CloudCredentialStatus:
    cloud_available: bool
    mode: str
    source: str | None


def detect_cloud_credential(
    *,
    env: dict[str, str] | None = None,
    claude_home: Path | None = None,
) -> CloudCredentialStatus:
    """Detect host-side cloud credential availability without exposing secret values."""
    source_env = os.environ if env is None else env
    if source_env.get("CLAUDE_CODE_OAUTH_TOKEN"):
        return CloudCredentialStatus(True, "oauth", "CLAUDE_CODE_OAUTH_TOKEN")

    if _interactive_claude_oauth_present(claude_home or _default_claude_home()):
        return CloudCredentialStatus(True, "oauth", "~/.claude")

    if source_env.get("ANTHROPIC_API_KEY"):
        return CloudCredentialStatus(True, "anthropic", "ANTHROPIC_API_KEY")

    if source_env.get("OPENROUTER_API_KEY"):
        return CloudCredentialStatus(True, "openrouter", "OPENROUTER_API_KEY")

    return CloudCredentialStatus(False, "unconfigured", None)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Detect VERDICT host-side cloud credentials.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable status.")
    args = parser.parse_args(argv)

    load_dotenv_if_present()
    status = detect_cloud_credential()
    if args.json:
        print(json.dumps(asdict(status), sort_keys=True))
    else:
        print(f"mode={status.mode} source={status.source or 'none'}")
    return 0


def _default_claude_home() -> Path:
    try:
        return Path.home() / ".claude"
    except RuntimeError:
        return Path(".claude")


def _interactive_claude_oauth_present(claude_home: Path) -> bool:
    for candidate in (
        claude_home / "credentials.json",
        claude_home / ".credentials.json",
    ):
        if not candidate.is_file():
            continue
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if _contains_oauth_marker(payload):
            return True
    return False


def _contains_oauth_marker(value: object) -> bool:
    if isinstance(value, dict):
        return any(
            key in value or _contains_oauth_marker(child)
            for key in ("access_token", "refresh_token", "oauth_token")
            for child in value.values()
        )
    if isinstance(value, list):
        return any(_contains_oauth_marker(item) for item in value)
    return False


if __name__ == "__main__":
    raise SystemExit(main())
