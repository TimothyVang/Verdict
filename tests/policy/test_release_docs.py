from pathlib import Path


def test_release_command_table_marks_exposed_local_commands_implemented() -> None:
    release = Path("docs/RELEASE.md").read_text(encoding="utf-8")
    implemented_commands = (
        "verdict init <evidence>",
        "verdict resume <case_id>",
        "verdict reverify <case_id> --mode <mode>",
        "verdict status <case_id>",
        "verdict ls",
        "verdict show <case_id>",
        "verdict mode",
        "verdict gc",
    )

    for command in implemented_commands:
        row = next(line for line in release.splitlines() if f"`{command}`" in line)
        assert "Implemented locally" in row
        assert "Roadmap" not in row
