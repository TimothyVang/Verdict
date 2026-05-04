"""SQLite-backed append-only memory store for DFIR workflows."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from verdict.schemas.memory import ApprovalState, MemoryEntry, MemoryUpdateProposal


class MemoryStore:
    """Persist memory entries and update proposals with immutable history."""

    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_versions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    memory_id TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    approval_state TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(memory_id, version)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_update_proposals (
                    proposal_id TEXT PRIMARY KEY,
                    memory_id TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    approval_state TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )

    def put_entry(self, entry: MemoryEntry) -> None:
        """Insert a new immutable memory version."""
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO memory_versions (memory_id, version, approval_state, payload_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    entry.memory_id,
                    entry.version,
                    entry.approval_state.value,
                    json.dumps(entry.model_dump(mode="json")),
                    entry.created_at.isoformat(),
                ),
            )

    def get_latest_entry(self, memory_id: str) -> MemoryEntry | None:
        """Return latest version for a memory_id."""
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT payload_json FROM memory_versions
                WHERE memory_id = ?
                ORDER BY version DESC
                LIMIT 1
                """,
                (memory_id,),
            ).fetchone()
        if row is None:
            return None
        return MemoryEntry(**json.loads(row["payload_json"]))

    def put_proposal(self, proposal: MemoryUpdateProposal) -> None:
        """Store proposal as proposed state before approval."""
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO memory_update_proposals (proposal_id, memory_id, operation, approval_state, payload_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    proposal.proposal_id,
                    proposal.memory_id,
                    proposal.operation.value,
                    ApprovalState.PROPOSED.value,
                    json.dumps(proposal.model_dump(mode="json")),
                ),
            )
