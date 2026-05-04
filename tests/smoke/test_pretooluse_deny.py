from __future__ import annotations

import subprocess
from shutil import which

import pytest


@pytest.mark.smoke
@pytest.mark.xfail(reason="anthropics/claude-code#33106 + #37210", strict=False)
def test_pretooluse_deny_blocks_mcp_write() -> None:
    claude = which("claude")
    assert claude is not None

    result = subprocess.run(  # noqa: S603 - smoke test intentionally runs the real Claude CLI.
        [
            claude,
            "--print",
            "Attempt an MCP write that must be blocked by a PreToolUse deny hook.",
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )

    combined_output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "deny" in combined_output.lower() or "blocked" in combined_output.lower()
