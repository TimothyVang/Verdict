"""verdict CLI — top-level Typer application.

Surface (CLAUDE.md §10.2):
    verdict doctor
    verdict mode
    verdict init  <evidence_path> [--mode]
    verdict resume   <case_id>
    verdict reverify <case_id> --mode <mode>
    verdict status
    verdict ls
    verdict show     <case_id>
    verdict export   <case_id>
    verdict validate <case_id>
    verdict approve  <finding_id>
    verdict gc
    verdict health

Commands marked (v2 roadmap) raise NotImplementedError until their
BUILD_PLAN task lands.
"""

from __future__ import annotations

import typer

from verdict.cli.resume import resume
from verdict.cli.reverify import reverify

app = typer.Typer(
    name="verdict",
    help="VERDICT — autonomous Windows DFIR agent.",
    add_completion=False,
)

# ---------------------------------------------------------------------------
# Registered commands
# ---------------------------------------------------------------------------

app.command("resume")(resume)
app.command("reverify")(reverify)


# ---------------------------------------------------------------------------
# Stub commands (v2 roadmap stubs that surface a clear error)
# ---------------------------------------------------------------------------

_V2_COMMANDS = [
    "doctor",
    "mode",
    "init",
    "status",
    "ls",
    "show",
    "export",
    "validate",
    "approve",
    "gc",
    "health",
]


def _make_stub(name: str):  # type: ignore[return]
    def _stub() -> None:  # type: ignore[return]
        typer.echo(
            f"'{name}' is not yet implemented (see BUILD_PLAN for the implementing task).",
            err=True,
        )
        raise typer.Exit(1)

    _stub.__name__ = name
    return _stub


for _cmd_name in _V2_COMMANDS:
    app.command(_cmd_name)(_make_stub(_cmd_name))


if __name__ == "__main__":
    app()
