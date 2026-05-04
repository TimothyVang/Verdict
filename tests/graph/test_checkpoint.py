from __future__ import annotations

from typing import TYPE_CHECKING

from verdict.graph.checkpoint import open_checkpoint_connection

if TYPE_CHECKING:
    from pathlib import Path


def test_pragma_journal_mode_wal(tmp_path: Path) -> None:
    connection = open_checkpoint_connection(tmp_path / "checkpoint.sqlite3")

    try:
        journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
    finally:
        connection.close()

    assert journal_mode == "wal"


def test_pragma_synchronous_full(tmp_path: Path) -> None:
    connection = open_checkpoint_connection(tmp_path / "checkpoint.sqlite3")

    try:
        synchronous = connection.execute("PRAGMA synchronous").fetchone()[0]
    finally:
        connection.close()

    assert synchronous == 2
