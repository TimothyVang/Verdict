"""swarm doctor — green/red preflight, mirrors `verdict doctor` style.

Checks:
  - Anthropic API reachable (HEAD on /v1/messages with 401 expected; auth not required to verify reachability)
  - `gh` CLI installed + authenticated
  - `gh repo view TimothyVang/Verdict` returns WRITE+
  - SQLite WAL works on the repo's filesystem
  - Bootstrap toolchain present (delegates to scripts/bootstrap-dev.sh --check, when --check is wired)
"""

from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

from swarm.runtime import gh as gh_lib

GREEN = "\033[0;32m" if sys.stdout.isatty() else ""
RED   = "\033[0;31m" if sys.stdout.isatty() else ""
RESET = "\033[0m"   if sys.stdout.isatty() else ""


def check_credential_present() -> tuple[bool, str]:
    """Confirm at least one Anthropic credential path is configured.

    Precedence matches .env.example: ANTHROPIC_API_KEY > CLAUDE_CODE_OAUTH_TOKEN
    > ~/.claude/credentials.json > ANTHROPIC_API (legacy). Returns the path
    name on success — never the value (CLAUDE.md §3.9).
    """
    if os.environ.get("ANTHROPIC_API_KEY"):
        return True, "ANTHROPIC_API_KEY"
    if os.environ.get("CLAUDE_CODE_OAUTH_TOKEN"):
        return True, "CLAUDE_CODE_OAUTH_TOKEN"
    creds = Path.home() / ".claude" / "credentials.json"
    if creds.exists():
        return True, f"~/.claude/credentials.json ({creds})"
    if os.environ.get("ANTHROPIC_API"):
        return True, "ANTHROPIC_API"
    return False, "no credential (set ANTHROPIC_API_KEY or CLAUDE_CODE_OAUTH_TOKEN)"


def check_anthropic_reachable() -> tuple[bool, str]:
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", method="GET")
    try:
        urllib.request.urlopen(req, timeout=5)  # noqa: S310 — explicit URL
        return True, "200 (unexpected — should be 401/405 unauthenticated)"
    except urllib.error.HTTPError as e:
        # 401 / 405 / 404 all confirm reachability without valid auth.
        return e.code in (401, 404, 405), f"{e.code}"
    except (urllib.error.URLError, TimeoutError) as e:
        return False, str(e)


def check_gh_installed() -> tuple[bool, str]:
    path = shutil.which("gh")
    return (path is not None), (path or "missing")


def check_gh_auth() -> tuple[bool, str]:
    return gh_lib.auth_status(), "ok" if gh_lib.auth_status() else "not authenticated"


def check_repo_permission(slug: str) -> tuple[bool, str]:
    perm = gh_lib.repo_view_permission(slug)
    ok = perm in {"WRITE", "MAINTAIN", "ADMIN"}
    return ok, perm or "no access / not authenticated"


def check_sqlite_wal(repo: Path) -> tuple[bool, str]:
    with tempfile.NamedTemporaryFile(suffix=".db", dir=repo, delete=True) as tf:
        try:
            conn = sqlite3.connect(tf.name)
            conn.execute("PRAGMA journal_mode=WAL")
            mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
            conn.close()
            return mode.lower() == "wal", mode
        except sqlite3.Error as e:
            return False, str(e)


def check_bootstrap_script(repo: Path) -> tuple[bool, str]:
    script = repo / "scripts" / "bootstrap-dev.sh"
    if not script.exists():
        return False, "scripts/bootstrap-dev.sh missing"
    if not script.stat().st_mode & 0o111:
        return False, "scripts/bootstrap-dev.sh not executable"
    # We don't actually run it (would install things). Just confirm syntax.
    res = subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True)
    return res.returncode == 0, "syntax ok" if res.returncode == 0 else res.stderr.strip()


def repo_root() -> Path:
    res = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True, text=True,
    )
    return Path(res.stdout.strip()) if res.returncode == 0 else Path.cwd()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="swarm.doctor")
    p.add_argument("--repo-slug", default="TimothyVang/Verdict")
    args = p.parse_args(argv)

    repo = repo_root()
    checks: list[tuple[str, tuple[bool, str]]] = [
        ("anthropic api reachable",   check_anthropic_reachable()),
        ("anthropic credential",      check_credential_present()),
        ("gh CLI installed",          check_gh_installed()),
        ("gh authenticated",          check_gh_auth()),
        (f"repo write access ({args.repo_slug})", check_repo_permission(args.repo_slug)),
        ("sqlite WAL on FS",          check_sqlite_wal(repo)),
        ("bootstrap-dev.sh present",  check_bootstrap_script(repo)),
    ]

    all_ok = True
    for name, (ok, detail) in checks:
        marker = f"{GREEN}ok{RESET}" if ok else f"{RED}FAIL{RESET}"
        print(f"  {marker:<10} {name:<40} {detail}")
        all_ok = all_ok and ok

    print()
    print("ready" if all_ok else "NOT READY — fix the failures above")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
