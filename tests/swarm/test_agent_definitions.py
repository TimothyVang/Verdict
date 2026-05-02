"""Frontmatter contract for swarm/agents/<role>.md.

Every swarm role MUST declare its name, description, pinned model,
allowed_tools, skills, and mcp_servers in YAML frontmatter so
swarm/worker.py (live mode, gated by VERDICT_SWARM_LIVE=1) can pass
them to the Claude Agent SDK without parsing prose.

_prefix.md is the shared system-prompt prefix and intentionally has
no frontmatter; it is appended verbatim to each role's prompt.
"""
from __future__ import annotations

from pathlib import Path

import frontmatter
import pytest

AGENTS_DIR = Path(__file__).resolve().parents[2] / "swarm" / "agents"

REQUIRED_KEYS: tuple[str, ...] = (
    "name",
    "description",
    "model",
    "allowed_tools",
    "skills",
    "mcp_servers",
)

ALLOWED_MODELS: frozenset[str] = frozenset(
    {
        "claude-opus-4-7",
        "claude-sonnet-4-6",
        "claude-haiku-4-5",
    }
)

ALLOWED_TOOL_NAMES: frozenset[str] = frozenset(
    {"Read", "Write", "Edit", "Bash"}
)

# Skills the swarm may load. Sourced from .claude/skills/ +
# protocol-sift/skills/. Keep in sync by-hand; CI surface for new
# skill drops is the failing-test signal here.
KNOWN_SKILLS: frozenset[str] = frozenset(
    {
        # Always-on charter overlay.
        "verdict-house-rules",
        "using-superpowers",
        # Worker / planning / review skills (vendored at .claude/skills/).
        "brainstorming",
        "dispatching-parallel-agents",
        "executing-plans",
        "finishing-a-development-branch",
        "grill-me",
        "grill-with-docs",
        "receiving-code-review",
        "requesting-code-review",
        "subagent-driven-development",
        "systematic-debugging",
        "test-driven-development",
        "using-git-worktrees",
        "verification-before-completion",
        "writing-plans",
        "writing-skills",
        # Anthropic SDK / API specialization.
        "claude-api",
        # Forensic skills surfaced from protocol-sift/skills/.
        "memory-analysis",
        "plaso-timeline",
        "sleuthkit",
        "windows-artifacts",
        "yara-hunting",
    }
)

KNOWN_MCP_SERVERS: frozenset[str] = frozenset(
    {"github", "filesystem", "sequential-thinking", "context7"}
)


def _role_files() -> list[Path]:
    return sorted(p for p in AGENTS_DIR.glob("*.md") if p.name != "_prefix.md")


@pytest.fixture(scope="module")
def role_paths() -> list[Path]:
    paths = _role_files()
    assert paths, f"no role files found under {AGENTS_DIR}"
    return paths


@pytest.mark.parametrize("role_path", _role_files(), ids=lambda p: p.stem)
def test_frontmatter_present_and_complete(role_path: Path) -> None:
    post = frontmatter.load(role_path)
    metadata = dict(post.metadata)
    assert metadata, f"{role_path.name} has no YAML frontmatter"
    missing = [k for k in REQUIRED_KEYS if k not in metadata]
    assert not missing, f"{role_path.name} missing keys: {missing}"


@pytest.mark.parametrize("role_path", _role_files(), ids=lambda p: p.stem)
def test_name_matches_filename(role_path: Path) -> None:
    post = frontmatter.load(role_path)
    assert post.metadata["name"] == role_path.stem, (
        f"frontmatter name={post.metadata.get('name')!r} "
        f"does not match filename stem {role_path.stem!r}"
    )


@pytest.mark.parametrize("role_path", _role_files(), ids=lambda p: p.stem)
def test_model_pinned_to_known(role_path: Path) -> None:
    post = frontmatter.load(role_path)
    model = post.metadata["model"]
    assert model in ALLOWED_MODELS, (
        f"{role_path.name} pins unknown model {model!r}; "
        f"allowed: {sorted(ALLOWED_MODELS)}"
    )


@pytest.mark.parametrize("role_path", _role_files(), ids=lambda p: p.stem)
def test_allowed_tools_subset(role_path: Path) -> None:
    post = frontmatter.load(role_path)
    tools = post.metadata["allowed_tools"]
    assert isinstance(tools, list) and tools, f"{role_path.name} allowed_tools must be non-empty list"
    unknown = [t for t in tools if t not in ALLOWED_TOOL_NAMES]
    assert not unknown, (
        f"{role_path.name} declares unknown tools {unknown}; "
        f"allowed: {sorted(ALLOWED_TOOL_NAMES)}"
    )


@pytest.mark.parametrize("role_path", _role_files(), ids=lambda p: p.stem)
def test_skills_known(role_path: Path) -> None:
    post = frontmatter.load(role_path)
    skills = post.metadata["skills"]
    assert isinstance(skills, list), f"{role_path.name} skills must be a list"
    unknown = [s for s in skills if s not in KNOWN_SKILLS]
    assert not unknown, (
        f"{role_path.name} references unknown skills {unknown}; "
        f"add them to KNOWN_SKILLS or fix the role file"
    )


@pytest.mark.parametrize("role_path", _role_files(), ids=lambda p: p.stem)
def test_mcp_servers_known(role_path: Path) -> None:
    post = frontmatter.load(role_path)
    servers = post.metadata["mcp_servers"]
    assert isinstance(servers, list), f"{role_path.name} mcp_servers must be a list"
    unknown = [s for s in servers if s not in KNOWN_MCP_SERVERS]
    assert not unknown, (
        f"{role_path.name} references unknown MCP servers {unknown}; "
        f"add them to .mcp.json (and KNOWN_MCP_SERVERS) or fix the role file"
    )


@pytest.mark.parametrize("role_path", _role_files(), ids=lambda p: p.stem)
def test_house_rules_overlay_loaded(role_path: Path) -> None:
    """Every swarm agent must load verdict-house-rules per CLAUDE.md §3."""
    post = frontmatter.load(role_path)
    assert "verdict-house-rules" in post.metadata["skills"], (
        f"{role_path.name} must load verdict-house-rules (CLAUDE.md §3 overlay)"
    )


def test_read_only_roles_have_no_write_tools() -> None:
    """conductor / reviewer / auditor are read-only per AGENT_SWARM.md §4."""
    for stem in ("conductor", "reviewer", "auditor"):
        role_path = AGENTS_DIR / f"{stem}.md"
        post = frontmatter.load(role_path)
        tools = set(post.metadata["allowed_tools"])
        forbidden = tools & {"Write", "Edit"}
        assert not forbidden, (
            f"{stem}.md is a read-only role but declares {forbidden}; "
            f"see docs/AGENT_SWARM.md §4"
        )


def test_tool_wrapper_engineer_loads_forensic_skills() -> None:
    """tool-wrapper-engineer.md surfaces protocol-sift forensic skills."""
    role_path = AGENTS_DIR / "tool-wrapper-engineer.md"
    post = frontmatter.load(role_path)
    skills = set(post.metadata["skills"])
    forensic = {"memory-analysis", "plaso-timeline", "sleuthkit", "windows-artifacts", "yara-hunting"}
    missing = forensic - skills
    assert not missing, f"tool-wrapper-engineer must load forensic skills; missing: {sorted(missing)}"
