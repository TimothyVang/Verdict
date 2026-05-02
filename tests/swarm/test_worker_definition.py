"""worker.load_agent_definition contract.

Returns a typed AgentDef per swarm role; system_prompt = _prefix.md +
role.md so the live SDK invocation can pass it straight through.
"""
from __future__ import annotations

import pytest

from swarm.worker import AgentDef, load_agent_definition

ALL_ROLES: tuple[str, ...] = (
    "conductor",
    "reviewer",
    "auditor",
    "schema-engineer",
    "planning-engineer",
    "sandbox-engineer",
    "tool-wrapper-engineer",
    "eval-engineer",
)

WORKER_ALIASES: dict[str, str] = {
    "schema": "schema-engineer",
    "planning": "planning-engineer",
    "sandbox": "sandbox-engineer",
    "tool-wrapper": "tool-wrapper-engineer",
    "eval": "eval-engineer",
}


@pytest.mark.parametrize("role", ALL_ROLES)
def test_load_agent_definition_returns_agentdef(role: str) -> None:
    defn = load_agent_definition(role)
    assert isinstance(defn, AgentDef)
    assert defn.name == role
    assert defn.description and isinstance(defn.description, str)
    assert defn.model
    assert defn.allowed_tools
    assert defn.skills
    assert isinstance(defn.mcp_servers, tuple)


@pytest.mark.parametrize("role", ALL_ROLES)
def test_system_prompt_concatenates_prefix_and_role(role: str) -> None:
    defn = load_agent_definition(role)
    # Prefix comes first.
    assert "SHARED SYSTEM PROMPT" in defn.system_prompt, (
        f"{role}: prefix not found at start of system_prompt"
    )
    # Role-specific marker.
    role_heading = {
        "conductor": "ROLE — Conductor",
        "reviewer": "ROLE — Reviewer",
        "auditor": "ROLE — Auditor",
        "schema-engineer": "ROLE — Schema engineer",
        "planning-engineer": "ROLE — Planning engineer",
        "sandbox-engineer": "ROLE — Sandbox engineer",
        "tool-wrapper-engineer": "ROLE — Tool-wrapper engineer",
        "eval-engineer": "ROLE — Eval engineer",
    }[role]
    assert role_heading in defn.system_prompt, (
        f"{role}: role heading {role_heading!r} not in system_prompt"
    )
    # Frontmatter must NOT leak into the prompt.
    assert defn.system_prompt.lstrip()[:3] != "---", (
        f"{role}: frontmatter delimiter leaked into system_prompt"
    )


def test_house_rules_overlay_present_in_skills() -> None:
    for role in ALL_ROLES:
        defn = load_agent_definition(role)
        assert "verdict-house-rules" in defn.skills, role


def test_unknown_role_raises() -> None:
    with pytest.raises((ValueError, KeyError)):
        load_agent_definition("nonexistent-role")


@pytest.mark.parametrize("alias,canonical", list(WORKER_ALIASES.items()))
def test_short_aliases_resolve_to_canonical(alias: str, canonical: str) -> None:
    """The legacy 'schema'/'planning'/... aliases used by load_prompt() still work."""
    defn = load_agent_definition(alias)
    assert defn.name == canonical


def test_read_only_roles_omit_write_tools() -> None:
    for role in ("conductor", "reviewer", "auditor"):
        defn = load_agent_definition(role)
        forbidden = set(defn.allowed_tools) & {"Write", "Edit"}
        assert not forbidden, f"{role} declared {forbidden}"
