"""Contract for the project-root .mcp.json.

The swarm dispatches MCP servers per-agent via frontmatter
mcp_servers: lists. Every name referenced in any swarm/agents/<role>.md
must resolve to a server entry in .mcp.json.
"""
from __future__ import annotations

import json
from pathlib import Path

import frontmatter
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MCP_CONFIG = REPO_ROOT / ".mcp.json"
AGENTS_DIR = REPO_ROOT / "swarm" / "agents"

REQUIRED_SERVERS: frozenset[str] = frozenset(
    {"github", "filesystem", "sequential-thinking", "context7"}
)


@pytest.fixture(scope="module")
def mcp_config() -> dict:
    assert MCP_CONFIG.exists(), f"{MCP_CONFIG} is missing"
    return json.loads(MCP_CONFIG.read_text(encoding="utf-8"))


def test_mcp_config_exists() -> None:
    assert MCP_CONFIG.exists(), f"{MCP_CONFIG} is missing"


def test_top_level_mcpservers_key(mcp_config: dict) -> None:
    assert "mcpServers" in mcp_config, ".mcp.json must have a top-level mcpServers object"
    assert isinstance(mcp_config["mcpServers"], dict)


def test_required_servers_present(mcp_config: dict) -> None:
    declared = set(mcp_config["mcpServers"].keys())
    missing = REQUIRED_SERVERS - declared
    assert not missing, f".mcp.json missing servers: {sorted(missing)}"


@pytest.mark.parametrize("server_name", sorted(REQUIRED_SERVERS))
def test_server_entry_shape(mcp_config: dict, server_name: str) -> None:
    server = mcp_config["mcpServers"][server_name]
    assert "command" in server, f"{server_name} missing command"
    assert isinstance(server["command"], str) and server["command"], (
        f"{server_name}.command must be a non-empty string"
    )
    if "args" in server:
        assert isinstance(server["args"], list)
    if "env" in server:
        assert isinstance(server["env"], dict)


def test_filesystem_server_takes_path_argument(mcp_config: dict) -> None:
    """The filesystem MCP must take a root-path argument.

    The swarm worker `cd`s into the per-task worktree before dispatch,
    so ${PWD} naturally resolves to the worktree at spawn time.
    """
    fs = mcp_config["mcpServers"]["filesystem"]
    args = fs.get("args", [])
    flat = " ".join(args)
    assert any(tok in flat for tok in ("${PWD}", "$PWD", "${VERDICT_WORKTREE_PATH}")), (
        "filesystem MCP must root the model to a path arg; got "
        f"args={args!r}"
    )


def test_github_server_reads_token_from_env(mcp_config: dict) -> None:
    """The GitHub MCP token comes from the swarm-instance env, not the file."""
    gh = mcp_config["mcpServers"]["github"]
    env = gh.get("env", {})
    flat_env = " ".join(f"{k}={v}" for k, v in env.items())
    args = " ".join(gh.get("args", []))
    accepted = ("GH_TOKEN", "GITHUB_PERSONAL_ACCESS_TOKEN", "GITHUB_TOKEN")
    assert any(name in flat_env or name in args for name in accepted), (
        "github MCP must source token from env; got "
        f"env={env!r} args={gh.get('args')!r}"
    )


def test_every_agent_mcp_reference_resolves(mcp_config: dict) -> None:
    """Every mcp_server in any agent frontmatter must resolve to .mcp.json."""
    declared = set(mcp_config["mcpServers"].keys())
    referenced: set[str] = set()
    for role_path in sorted(AGENTS_DIR.glob("*.md")):
        if role_path.name == "_prefix.md":
            continue
        post = frontmatter.load(role_path)
        for server in post.metadata.get("mcp_servers", []) or []:
            referenced.add(server)
    unresolved = referenced - declared
    assert not unresolved, (
        f"agent frontmatter references MCP servers not in .mcp.json: {sorted(unresolved)}"
    )
