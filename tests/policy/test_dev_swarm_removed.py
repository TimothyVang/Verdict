from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_build_side_dev_swarm_files_are_removed() -> None:
    removed_paths = [
        "swarm",
        "tests/swarm",
        "scripts/swarm.ps1",
        "docs/AGENT_SWARM.md",
        ".claude/agents",
        ".claude/hooks/task-completed.sh",
    ]

    existing = [
        path
        for path in removed_paths
        if (REPO_ROOT / path).is_file()
        or ((REPO_ROOT / path).is_dir() and any(item.is_file() for item in (REPO_ROOT / path).rglob("*")))
    ]

    assert existing == []


def test_authority_docs_do_not_advertise_dev_swarm() -> None:
    docs = [
        REPO_ROOT / "CLAUDE.md",
        REPO_ROOT / "docs" / "README.md",
        REPO_ROOT / "docs" / "SKILLS_FRAMEWORK.md",
    ]
    forbidden = [
        "AGENT_SWARM.md",
        "build-side LLM swarm",
        "engineering swarm",
        "swarm/ topology",
        "swarm/",
        "scripts/swarm",
    ]

    violations = [
        f"{doc.relative_to(REPO_ROOT).as_posix()}: {phrase}"
        for doc in docs
        for phrase in forbidden
        if phrase in doc.read_text(encoding="utf-8")
    ]

    assert violations == []
