"""
W1.D.1 — PreToolUse deny smoke scaffold.

Verifies that the installed Claude CLI enforces `permissionDecision: "deny"` for
MCP server tool calls from within a PreToolUse hook.

XFAIL rationale
---------------
anthropics/claude-code#33106  — `permissionDecision: "deny"` is not enforced for MCP
                                 server tool calls in any released Claude CLI version as of
                                 May 2026.
anthropics/claude-code#37210  — deny is also ignored for the built-in Edit tool.

Since the entire SIFT toolset is wired through FastMCP + microsandbox-mcp, these are not
edge-cases; they affect every tool call in every mode.  Layer 1 (Claude Code PreToolUse
hook) is therefore *best-effort*.  The architectural guarantee rests on Layer 2
(LangGraph DenyRuleWrapper) and Layer 3 (Microsandbox read-only /evidence mount).

When Anthropic ships a CLI release that fixes #33106 and #37210 this test should flip to
XPASS and the `xfail` mark can be removed.  The CI job that runs `pytest -m smoke` will
surface that transition.

Test design
-----------
1. Write a minimal `settings.json` (project-scope) that wires a PreToolUse hook to a
   tiny Python helper script.
2. The helper script unconditionally returns::

       {"permissionDecision": "deny", "permissionDecisionReason": "evidence-vault guard"}

3. Invoke `claude --print --dangerously-skip-permissions -p "call the echo_write tool"`
   inside a temp directory that has a one-tool MCP server (`echo_write`) whose only
   action is writing a sentinel file.
4. Assert the sentinel file was **NOT** created — i.e. the deny was enforced.

The assertion is the contract.  Until #33106 is fixed the sentinel file *will* be
created (the deny is ignored), so the test fails → xfail is correct.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_HOOK_SCRIPT = textwrap.dedent(
    """\
    #!/usr/bin/env python3
    \"\"\"PreToolUse hook: always deny.\"\"\"
    import json
    import sys

    # Claude Code passes the tool-call payload on stdin as JSON.
    _ = json.load(sys.stdin)

    # Return a deny decision for every MCP server tool call.
    print(json.dumps({
        "permissionDecision": "deny",
        "permissionDecisionReason": "evidence-vault guard — test hook"
    }))
    sys.exit(0)
    """
)

_MCP_SERVER_SCRIPT = textwrap.dedent(
    """\
    #!/usr/bin/env python3
    \"\"\"
    Minimal MCP server that exposes a single tool: echo_write.
    echo_write(path, content) writes `content` to `path` and returns "written".
    Uses the stdio transport so it can be wired via claude's mcp.servers config.
    \"\"\"
    import json
    import sys

    def handle(request: dict) -> dict:
        method = request.get("method", "")
        req_id = request.get("id")

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "echo_write_server", "version": "0.1.0"},
                },
            }

        if method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "tools": [
                        {
                            "name": "echo_write",
                            "description": "Write content to a file (used by smoke test).",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "path": {"type": "string"},
                                    "content": {"type": "string"},
                                },
                                "required": ["path", "content"],
                            },
                        }
                    ]
                },
            }

        if method == "tools/call":
            params = request.get("params", {})
            if params.get("name") == "echo_write":
                args = params.get("arguments", {})
                target_path = args.get("path", "")
                content = args.get("content", "")
                try:
                    with open(target_path, "w") as fh:
                        fh.write(content)
                    result_text = f"written:{target_path}"
                except Exception as exc:
                    result_text = f"error:{exc}"
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {"content": [{"type": "text", "text": result_text}]},
                }

        # notifications / unknown — return empty response (no id needed)
        return {}

    def main() -> None:
        for raw_line in sys.stdin:
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            try:
                request = json.loads(raw_line)
            except json.JSONDecodeError:
                continue
            response = handle(request)
            if response:
                sys.stdout.write(json.dumps(response) + "\\n")
                sys.stdout.flush()

    if __name__ == "__main__":
        main()
    """
)


def _find_claude_cli() -> str | None:
    """Return the absolute path to the `claude` CLI, or None if not installed."""
    return shutil.which("claude")


# ---------------------------------------------------------------------------
# Smoke test
# ---------------------------------------------------------------------------


@pytest.mark.smoke
@pytest.mark.xfail(
    reason=(
        "anthropics/claude-code#33106 — permissionDecision: 'deny' not enforced for MCP "
        "server tool calls; anthropics/claude-code#37210 — deny ignored for Edit tool. "
        "Layer-1 (PreToolUse hook) is best-effort until Anthropic ships fixes. "
        "Re-evaluate per Claude CLI release."
    ),
    strict=False,
)
def test_pretooluse_deny_blocks_mcp_write() -> None:
    """
    PreToolUse hook returning ``permissionDecision: "deny"`` MUST prevent the
    `echo_write` MCP tool from creating its sentinel file.

    This is xfail because #33106 and #37210 mean the deny is currently ignored
    for MCP server tools and Edit.  When both issues are closed the test should
    flip XPASS; remove the xfail mark at that point.

    RED assertion (contract):
        assert not sentinel.exists(), "deny was enforced — sentinel was NOT written"
    """
    claude_bin = _find_claude_cli()
    if claude_bin is None:
        pytest.skip("claude CLI not installed; install it to run this smoke test")

    with tempfile.TemporaryDirectory(prefix="verdict_smoke_") as tmpdir:
        sentinel_path = os.path.join(tmpdir, "SENTINEL")

        # Write the hook script
        hook_script = os.path.join(tmpdir, "pretooluse_deny.py")
        with open(hook_script, "w") as fh:
            fh.write(_HOOK_SCRIPT)
        os.chmod(hook_script, 0o755)

        # Write the MCP server script
        mcp_server_script = os.path.join(tmpdir, "echo_write_server.py")
        with open(mcp_server_script, "w") as fh:
            fh.write(_MCP_SERVER_SCRIPT)
        os.chmod(mcp_server_script, 0o755)

        # Write .claude/settings.json (project-scope)
        claude_dir = os.path.join(tmpdir, ".claude")
        os.makedirs(claude_dir, exist_ok=True)
        settings = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "",  # match all tools
                        "hooks": [
                            {
                                "type": "command",
                                "command": f"{sys.executable} {hook_script}",
                            }
                        ],
                    }
                ]
            },
            "mcpServers": {
                "echo_write_server": {
                    "type": "stdio",
                    "command": sys.executable,
                    "args": [mcp_server_script],
                }
            },
        }
        settings_path = os.path.join(claude_dir, "settings.json")
        with open(settings_path, "w") as fh:
            json.dump(settings, fh)

        # Prompt the agent to call the echo_write tool
        prompt = (
            f"Call the echo_write tool with path={sentinel_path!r} "
            f"and content='hook-bypass-attempt'. "
            f"If the tool is denied, just say DENIED."
        )

        result = subprocess.run(
            [
                claude_bin,
                "--print",
                "--dangerously-skip-permissions",
                "-p",
                prompt,
            ],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=tmpdir,
        )

        # The test's RED assertion — this is what we are contracting against.
        # When #33106 + #37210 are fixed, the deny will be enforced and this
        # assertion will pass (flipping the xfail to xpass).
        assert not os.path.exists(sentinel_path), (
            "PreToolUse deny was NOT enforced — sentinel file was written. "
            f"Claude stdout: {result.stdout[:500]!r}. "
            f"This is the known #33106/#37210 bug; test is xfail until fixed."
        )
