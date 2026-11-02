# backend/services/agent_monitor.py

# Import SQLite for persistent agent logs.
import sqlite3

# Import JSON to serialize optional input/output information.
import json

# Import UUID generation for unique log IDs.
from uuid import uuid4

# Import UTC timestamps.
from datetime import datetime, timezone

# Import Path for reliable database location.
from pathlib import Path

# Import typing helpers.
from typing import Any, Dict, Optional


# Use the same database file as the task manager.
DATABASE_PATH = (
    Path(__file__).resolve().parents[2]
    / "research_tasks.db"
)


def get_timestamp() -> str:
    """Return the current UTC timestamp."""

    return datetime.now(timezone.utc).isoformat(
        timespec="milliseconds"
    )


def get_connection():
    """Create a connection to the SQLite database."""

    connection = sqlite3.connect(
        str(DATABASE_PATH),
        timeout=30,
    )

    # Return rows that can be accessed using column names.
    connection.row_factory = sqlite3.Row

    return connection


def initialize_agent_logs():
    """Create the agent execution log table."""

    with get_connection() as connection:

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS agent_execution_logs (
                log_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                agent_name TEXT NOT NULL,
                status TEXT NOT NULL,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                duration_seconds REAL,
                input_summary TEXT,
                output_summary TEXT,
                error_message TEXT
            )
            """
        )

        # Indexing makes task-specific log retrieval faster.
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_agent_logs_task_id
            ON agent_execution_logs(task_id)
            """
        )

        connection.commit()


def start_agent_log(
    task_id: str,
    agent_name: str,
    input_summary: Optional[str] = None,
) -> str:
    """
    Record that an agent has started.

    Returns the unique log ID used to finish the log later.
    """

    initialize_agent_logs()

    log_id = str(uuid4())

    with get_connection() as connection:

        connection.execute(
            """
            INSERT INTO agent_execution_logs (
                log_id,
                task_id,
                agent_name,
                status,
                started_at,
                input_summary
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                log_id,
                task_id,
                agent_name,
                "running",
                get_timestamp(),
                input_summary,
            ),
        )

        connection.commit()

    return log_id


def finish_agent_log(
    log_id: str,
    status: str,
    output_summary: Optional[str] = None,
    error_message: Optional[str] = None,
):
    """Record an agent's completion or failure."""

    if status not in {"completed", "failed"}:
        raise ValueError(
            "Final status must be 'completed' or 'failed'."
        )

    initialize_agent_logs()

    with get_connection() as connection:

        # Retrieve the agent's start time.
        row = connection.execute(
            """
            SELECT started_at
            FROM agent_execution_logs
            WHERE log_id = ?
            """,
            (log_id,),
        ).fetchone()

        # Reject an unknown log ID.
        if row is None:
            raise ValueError(
                f"Agent log not found: {log_id}"
            )

        started_at = datetime.fromisoformat(
            row["started_at"]
        )

        finished_at = datetime.now(timezone.utc)

        # Calculate how long the agent took.
        duration_seconds = max(
            0.0,
            (
                finished_at - started_at
            ).total_seconds(),
        )

        connection.execute(
            """
            UPDATE agent_execution_logs
            SET
                status = ?,
                finished_at = ?,
                duration_seconds = ?,
                output_summary = ?,
                error_message = ?
            WHERE log_id = ?
            """,
            (
                status,
                finished_at.isoformat(
                    timespec="milliseconds"
                ),
                round(duration_seconds, 3),
                output_summary,
                error_message,
                log_id,
            ),
        )

        connection.commit()


def get_agent_logs(
    task_id: str,
) -> Dict[str, Any]:
    """Return execution logs for a specific research task."""

    initialize_agent_logs()

    with get_connection() as connection:

        rows = connection.execute(
            """
            SELECT *
            FROM agent_execution_logs
            WHERE task_id = ?
            ORDER BY started_at ASC
            """,
            (task_id,),
        ).fetchall()

    logs = [dict(row) for row in rows]

    completed_count = sum(
        1 for log in logs
        if log["status"] == "completed"
    )

    failed_count = sum(
        1 for log in logs
        if log["status"] == "failed"
    )

    running_count = sum(
        1 for log in logs
        if log["status"] == "running"
    )

    total_duration = sum(
        log["duration_seconds"] or 0
        for log in logs
    )

    return {
        "success": True,
        "task_id": task_id,
        "total_agent_executions": len(logs),
        "completed": completed_count,
        "failed": failed_count,
        "running": running_count,
        "total_agent_duration_seconds": round(
            total_duration, 3
        ),
        "logs": logs,
    }


def get_recent_agent_logs(
    limit: int = 100,
) -> Dict[str, Any]:
    """Return recent agent executions across all tasks."""

    initialize_agent_logs()

    # Restrict the limit to a safe range.
    limit = max(1, min(limit, 500))

    with get_connection() as connection:

        rows = connection.execute(
            """
            SELECT *
            FROM agent_execution_logs
            ORDER BY started_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    logs = [dict(row) for row in rows]

    return {
        "success": True,
        "total_logs": len(logs),
        "logs": logs,
    }
