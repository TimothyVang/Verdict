"""SQLite-backed task state for the engineering swarm.

Schema and discipline mirror docs/AGENT_SWARM.md §6.1. WAL + fsync per
CLAUDE.md §9 (same durability posture as the runtime ledger). Atomic claim
via UPDATE-WHERE so two workers cannot grab the same task.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
  task_id           TEXT PRIMARY KEY,
  phase             TEXT NOT NULL,
  specialization    TEXT NOT NULL,
  status            TEXT NOT NULL,
  owner             TEXT,
  branch            TEXT,
  worktree_path     TEXT,
  pr_url            TEXT,
  attempts          INTEGER NOT NULL DEFAULT 0,
  last_event_ts     TEXT NOT NULL,
  blocked_reason    TEXT,
  token_spend_usd   REAL NOT NULL DEFAULT 0.0,
  langfuse_trace_id TEXT
) STRICT;

CREATE TABLE IF NOT EXISTS events (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  task_id       TEXT NOT NULL REFERENCES tasks(task_id),
  ts            TEXT NOT NULL,
  event_type    TEXT NOT NULL,
  details_json  TEXT NOT NULL
) STRICT;

CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_events_task  ON events(task_id);
"""

VALID_STATUSES = {
    "pending",
    "claimed",
    "red",
    "green",
    "review",
    "audit",
    "human_review",
    "merged",
    "blocked",
    "requires_human",
}


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, isolation_level=None)  # autocommit; we manage txns
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init(db_path: Path) -> None:
    """Create schema. Idempotent."""
    conn = connect(db_path)
    try:
        conn.executescript(SCHEMA)
    finally:
        conn.close()


def upsert_task(
    conn: sqlite3.Connection,
    task_id: str,
    phase: str,
    specialization: str,
    status: str = "pending",
) -> None:
    if status not in VALID_STATUSES:
        raise ValueError(f"invalid status: {status}")
    conn.execute(
        """INSERT INTO tasks (task_id, phase, specialization, status, last_event_ts)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(task_id) DO UPDATE SET
             phase=excluded.phase,
             specialization=excluded.specialization""",
        (task_id, phase, specialization, status, now_utc()),
    )


def claim(conn: sqlite3.Connection, task_id: str, worker: str) -> bool:
    """Atomic claim: returns True iff this caller won the row."""
    cur = conn.execute(
        """UPDATE tasks
              SET status='claimed', owner=?, last_event_ts=?
            WHERE task_id=? AND status='pending' AND owner IS NULL""",
        (worker, now_utc(), task_id),
    )
    won = cur.rowcount == 1
    if won:
        record_event(conn, task_id, "claim", {"worker": worker})
    return won


def transition(
    conn: sqlite3.Connection,
    task_id: str,
    new_status: str,
    *,
    expect_status: str | None = None,
    **fields: object,
) -> bool:
    """Move task to new_status. If expect_status is set, only succeeds when current matches."""
    if new_status not in VALID_STATUSES:
        raise ValueError(f"invalid status: {new_status}")
    sets = ["status=?", "last_event_ts=?"]
    args: list[object] = [new_status, now_utc()]
    for k, v in fields.items():
        sets.append(f"{k}=?")
        args.append(v)
    where = ["task_id=?"]
    args.append(task_id)
    if expect_status is not None:
        where.append("status=?")
        args.append(expect_status)
    cur = conn.execute(
        f"UPDATE tasks SET {', '.join(sets)} WHERE {' AND '.join(where)}",
        args,
    )
    moved = cur.rowcount == 1
    if moved:
        record_event(conn, task_id, f"transition:{new_status}", {"from": expect_status, "fields": list(fields)})
    return moved


def record_event(
    conn: sqlite3.Connection,
    task_id: str,
    event_type: str,
    details: dict[str, object],
) -> None:
    import json as _json

    conn.execute(
        "INSERT INTO events (task_id, ts, event_type, details_json) VALUES (?, ?, ?, ?)",
        (task_id, now_utc(), event_type, _json.dumps(details, sort_keys=True)),
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="swarm.state")
    sub = p.add_subparsers(dest="cmd", required=True)
    p_init = sub.add_parser("init", help="create schema")
    p_init.add_argument("--db", required=True, type=Path)
    args = p.parse_args(argv)

    if args.cmd == "init":
        init(args.db)
        print(f"initialized schema at {args.db}")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
