# ============================================================
# POSTGRESQL AGENT EXECUTION MONITOR
# ============================================================

from uuid import uuid4
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from backend.services.database import get_connection


def get_timestamp() -> str:
    """Return the current UTC timestamp."""

    return datetime.now(timezone.utc).isoformat(
        timespec="milliseconds"
    )


def initialize_agent_logs():
    """Initialize PostgreSQL agent execution logs."""

    with get_connection() as connection:

        connection.execute("""
            CREATE TABLE IF NOT EXISTS agent_execution_logs (
                log_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                agent_name TEXT NOT NULL,
                status TEXT NOT NULL,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                duration_seconds DOUBLE PRECISION,
                input_summary TEXT,
                output_summary TEXT,
                error_message TEXT
            )
        """)

        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_agent_logs_task_id
            ON agent_execution_logs(task_id)
        """)

        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_agent_logs_started_at
            ON agent_execution_logs(started_at)
        """)


def start_agent_log(
    task_id: str,
    agent_name: str,
    input_summary: Optional[str] = None,
) -> str:
    """Record the start of an agent execution."""

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
            VALUES (%s, %s, %s, %s, %s, %s)
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

    return log_id


def finish_agent_log(
    log_id: str,
    status: str,
    output_summary: Optional[str] = None,
    error_message: Optional[str] = None,
):
    """Record agent completion or failure."""

    if status not in {"completed", "failed"}:
        raise ValueError(
            "Final status must be 'completed' or 'failed'."
        )

    initialize_agent_logs()

    with get_connection() as connection:

        row = connection.execute(
            """
            SELECT started_at
            FROM agent_execution_logs
            WHERE log_id = %s
            """,
            (log_id,),
        ).fetchone()

        if row is None:
            raise ValueError(
                f"Agent log not found: {log_id}"
            )

        started_at = row["started_at"]

        if isinstance(started_at, str):
            started_at = datetime.fromisoformat(started_at)

        finished_at = datetime.now(timezone.utc)

        if started_at.tzinfo is None:
            started_at = started_at.replace(
                tzinfo=timezone.utc
            )

        duration_seconds = max(
            0.0,
            (finished_at - started_at).total_seconds(),
        )

        connection.execute(
            """
            UPDATE agent_execution_logs
            SET
                status = %s,
                finished_at = %s,
                duration_seconds = %s,
                output_summary = %s,
                error_message = %s
            WHERE log_id = %s
            """,
            (
                status,
                finished_at.isoformat(timespec="milliseconds"),
                round(duration_seconds, 3),
                output_summary,
                error_message,
                log_id,
            ),
        )


def get_agent_logs(task_id: str) -> Dict[str, Any]:
    """Return execution logs for a specific research task."""

    initialize_agent_logs()

    with get_connection() as connection:

        rows = connection.execute(
            """
            SELECT *
            FROM agent_execution_logs
            WHERE task_id = %s
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
            total_duration,
            3,
        ),
        "logs": logs,
    }


def get_recent_agent_logs(
    limit: int = 100,
) -> Dict[str, Any]:
    """Return recent executions across all research tasks."""

    initialize_agent_logs()

    limit = max(1, min(limit, 500))

    with get_connection() as connection:

        rows = connection.execute(
            """
            SELECT *
            FROM agent_execution_logs
            ORDER BY started_at DESC
            LIMIT %s
            """,
            (limit,),
        ).fetchall()

    logs = [dict(row) for row in rows]

    return {
        "total_logs": len(logs),
        "logs": logs,
    }