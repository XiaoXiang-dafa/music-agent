"""SQLite-backed, privacy-conscious tracing for local Agent runs."""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any


_SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS agent_runs (
    trace_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    mode TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at INTEGER NOT NULL,
    finished_at INTEGER,
    duration_ms INTEGER,
    steps INTEGER NOT NULL DEFAULT 0,
    tool_call_count INTEGER NOT NULL DEFAULT 0,
    error_type TEXT
);

CREATE TABLE IF NOT EXISTS tool_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trace_id TEXT NOT NULL,
    sequence INTEGER NOT NULL,
    tool_call_id TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    status TEXT NOT NULL,
    duration_ms INTEGER NOT NULL,
    source TEXT,
    fallback_used INTEGER,
    attempted_sources_json TEXT,
    error_type TEXT,
    FOREIGN KEY (trace_id) REFERENCES agent_runs(trace_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_tool_events_trace_sequence
ON tool_events(trace_id, sequence, id);
"""


class TraceRecorder:
    """Persist run summaries and a strict allowlist of tool-result metadata."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def start_run(self, session_id: str, mode: str) -> str:
        trace_id = str(uuid.uuid4())
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO agent_runs (
                    trace_id, session_id, mode, status, started_at
                ) VALUES (?, ?, ?, 'running', ?)
                """,
                (trace_id, session_id, mode, self._now_ms()),
            )
        return trace_id

    def record_tool(
        self,
        trace_id: str,
        sequence: int,
        call_id: str,
        tool_name: str,
        status: str,
        duration_ms: int,
        result: Any,
    ) -> None:
        safe = self._safe_tool_result(result)
        attempted_sources = safe["attempted_sources"]
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO tool_events (
                    trace_id, sequence, tool_call_id, tool_name, status,
                    duration_ms, source, fallback_used,
                    attempted_sources_json, error_type
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    trace_id,
                    int(sequence),
                    call_id,
                    tool_name,
                    status,
                    max(0, int(duration_ms)),
                    safe["source"],
                    self._bool_to_db(safe["fallback_used"]),
                    json.dumps(attempted_sources, ensure_ascii=False)
                    if attempted_sources is not None
                    else None,
                    safe["error_type"],
                ),
            )

    def finish_run(
        self,
        trace_id: str,
        status: str,
        steps: int,
        tool_call_count: int,
        duration_ms: int,
        error_type: str | None = None,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE agent_runs
                SET status = ?, finished_at = ?, duration_ms = ?,
                    steps = ?, tool_call_count = ?, error_type = ?
                WHERE trace_id = ?
                """,
                (
                    status,
                    self._now_ms(),
                    max(0, int(duration_ms)),
                    max(0, int(steps)),
                    max(0, int(tool_call_count)),
                    str(error_type) if error_type is not None else None,
                    trace_id,
                ),
            )

    def list_runs(self, limit: int = 20) -> dict[str, Any]:
        bounded_limit = max(1, min(100, int(limit)))
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT rowid, *
                FROM agent_runs
                ORDER BY started_at DESC, rowid DESC
                LIMIT ?
                """,
                (bounded_limit,),
            ).fetchall()

            runs = [self._public_run(row) for row in rows]
            trace_ids = [row["trace_id"] for row in rows]
            fallback_count = self._fallback_count(connection, trace_ids)

        run_count = len(runs)
        success_count = sum(run["status"] == "success" for run in runs)
        durations = [
            run["duration_ms"]
            for run in runs
            if run["duration_ms"] is not None
        ]
        return {
            "runs": runs,
            "stats": {
                "run_count": run_count,
                "success_count": success_count,
                "success_rate": success_count / run_count if run_count else 0,
                "average_duration_ms": (
                    sum(durations) / len(durations) if durations else 0
                ),
                "tool_call_count": sum(run["tool_call_count"] for run in runs),
                "fallback_count": fallback_count,
            },
        }

    def get_run(self, trace_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            run = connection.execute(
                "SELECT * FROM agent_runs WHERE trace_id = ?", (trace_id,)
            ).fetchone()
            if run is None:
                return None
            event_rows = connection.execute(
                """
                SELECT sequence, tool_call_id, tool_name, status, duration_ms,
                       source, fallback_used, attempted_sources_json, error_type
                FROM tool_events
                WHERE trace_id = ?
                ORDER BY sequence ASC, id ASC
                """,
                (trace_id,),
            ).fetchall()

        return {
            "run": self._public_run(run),
            "events": [self._public_event(row) for row in event_rows],
        }

    @staticmethod
    def _now_ms() -> int:
        return time.time_ns() // 1_000_000

    @staticmethod
    def _bool_to_db(value: bool | None) -> int | None:
        if value is None:
            return None
        return int(value)

    @staticmethod
    def _safe_tool_result(result: Any) -> dict[str, Any]:
        if not isinstance(result, dict):
            return {
                "source": None,
                "fallback_used": None,
                "attempted_sources": None,
                "error_type": None,
            }

        attempted = result.get("attempted_sources")
        if isinstance(attempted, (list, tuple)):
            attempted = [str(source) for source in attempted]
        else:
            attempted = None

        error_type = result.get("error_type")
        error = result.get("error")
        if error_type is None and isinstance(error, dict):
            error_type = error.get("type") or error.get("error_type")

        source = result.get("source")
        return {
            "source": str(source) if source is not None else None,
            "fallback_used": (
                result.get("fallback_used")
                if isinstance(result.get("fallback_used"), bool)
                else None
            ),
            "attempted_sources": attempted,
            "error_type": str(error_type) if error_type is not None else None,
        }

    @staticmethod
    def _public_run(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "trace_id": row["trace_id"],
            "mode": row["mode"],
            "status": row["status"],
            "started_at": row["started_at"],
            "finished_at": row["finished_at"],
            "duration_ms": row["duration_ms"],
            "steps": row["steps"],
            "tool_call_count": row["tool_call_count"],
            "error_type": row["error_type"],
        }

    @staticmethod
    def _public_event(row: sqlite3.Row) -> dict[str, Any]:
        attempted_json = row["attempted_sources_json"]
        return {
            "sequence": row["sequence"],
            "call_id": row["tool_call_id"],
            "tool_name": row["tool_name"],
            "status": row["status"],
            "duration_ms": row["duration_ms"],
            "source": row["source"],
            "fallback_used": (
                bool(row["fallback_used"])
                if row["fallback_used"] is not None
                else None
            ),
            "attempted_sources": (
                json.loads(attempted_json) if attempted_json is not None else None
            ),
            "error_type": row["error_type"],
        }

    @staticmethod
    def _fallback_count(
        connection: sqlite3.Connection, trace_ids: list[str]
    ) -> int:
        if not trace_ids:
            return 0
        total = 0
        for trace_id in trace_ids:
            row = connection.execute(
                "SELECT COUNT(*) AS count FROM tool_events "
                "WHERE fallback_used = 1 AND trace_id = ?",
                (trace_id,),
            ).fetchone()
            total += int(row["count"])
        return total
