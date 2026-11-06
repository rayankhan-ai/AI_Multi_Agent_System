# ============================================================
# AI MULTI-AGENT RESEARCH & AUTOMATION SYSTEM
# POSTGRESQL WORKFLOW EXECUTION TRACING
# ============================================================

import json
import uuid

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from backend.services.database import get_connection


def get_timestamp() -> str:
    """Return the current UTC timestamp."""

    return datetime.now(timezone.utc).isoformat()


def initialize_workflow_tracing() -> None:
    """Initialize PostgreSQL workflow tracing."""

    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS workflow_traces (
                trace_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                research_question TEXT,
                workflow_status TEXT NOT NULL,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                duration_seconds DOUBLE PRECISION,
                event_count INTEGER DEFAULT 0,
                error_message TEXT,
                trace_events TEXT
            )
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_workflow_traces_task_id
            ON workflow_traces(task_id)
            """
        )


def start_workflow_trace(
    task_id: str,
    research_question: str,
) -> str:
    """Create a new workflow trace."""

    initialize_workflow_tracing()

    trace_id = str(uuid.uuid4())
    started_at = get_timestamp()

    initial_events = [
        {
            "event": "workflow_started",
            "timestamp": started_at,
            "status": "running",
            "details": "Research workflow execution started.",
        }
    ]

    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO workflow_traces (
                trace_id,
                task_id,
                research_question,
                workflow_status,
                started_at,
                event_count,
                trace_events
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                trace_id,
                task_id,
                research_question,
                "running",
                started_at,
                len(initial_events),
                json.dumps(initial_events),
            ),
        )

    return trace_id


def add_workflow_trace_event(
    trace_id: str,
    event_name: str,
    status: str = "completed",
    details: str = "",
) -> Dict[str, Any]:
    """Append an event to an existing workflow trace."""

    with get_connection() as connection:

        row = connection.execute(
            """
            SELECT trace_events, event_count
            FROM workflow_traces
            WHERE trace_id = %s
            """,
            (trace_id,),
        ).fetchone()

        if row is None:
            raise ValueError(
                f"Workflow trace not found: {trace_id}"
            )

        events = json.loads(row["trace_events"] or "[]")

        event = {
            "event": event_name,
            "timestamp": get_timestamp(),
            "status": status,
            "details": details,
        }

        events.append(event)

        connection.execute(
            """
            UPDATE workflow_traces
            SET trace_events = %s,
                event_count = %s
            WHERE trace_id = %s
            """,
            (
                json.dumps(events),
                len(events),
                trace_id,
            ),
        )

        return event


def finish_workflow_trace(
    trace_id: str,
    workflow_status: str,
    error_message: Optional[str] = None,
) -> Dict[str, Any]:
    """Finish a workflow trace and calculate execution duration."""

    finished_at = get_timestamp()

    with get_connection() as connection:

        row = connection.execute(
            """
            SELECT started_at, trace_events
            FROM workflow_traces
            WHERE trace_id = %s
            """,
            (trace_id,),
        ).fetchone()

        if row is None:
            raise ValueError(
                f"Workflow trace not found: {trace_id}"
            )

        started_at_value = row["started_at"]

        if isinstance(started_at_value, datetime):
            started_datetime = started_at_value
        else:
            started_datetime = datetime.fromisoformat(
                started_at_value
            )

        finished_datetime = datetime.fromisoformat(
            finished_at
        )

        duration_seconds = (
            finished_datetime - started_datetime
        ).total_seconds()

        events = json.loads(row["trace_events"] or "[]")

        events.append(
            {
                "event": "workflow_finished",
                "timestamp": finished_at,
                "status": workflow_status,
                "details": (
                    error_message
                    if error_message
                    else "Research workflow execution finished."
                ),
            }
        )

        connection.execute(
            """
            UPDATE workflow_traces
            SET workflow_status = %s,
                finished_at = %s,
                duration_seconds = %s,
                event_count = %s,
                error_message = %s,
                trace_events = %s
            WHERE trace_id = %s
            """,
            (
                workflow_status,
                finished_at,
                duration_seconds,
                len(events),
                error_message,
                json.dumps(events),
                trace_id,
            ),
        )

        return {
            "trace_id": trace_id,
            "workflow_status": workflow_status,
            "started_at": started_datetime.isoformat(),
            "finished_at": finished_at,
            "duration_seconds": round(
                duration_seconds, 3
            ),
            "event_count": len(events),
        }


def get_workflow_trace(
    trace_id: str,
) -> Optional[Dict[str, Any]]:
    """Retrieve one workflow trace."""

    with get_connection() as connection:

        row = connection.execute(
            """
            SELECT *
            FROM workflow_traces
            WHERE trace_id = %s
            """,
            (trace_id,),
        ).fetchone()

        if row is None:
            return None

        result = dict(row)

        result["trace_events"] = json.loads(
            result["trace_events"] or "[]"
        )

        return result


def get_task_workflow_traces(
    task_id: str,
) -> Dict[str, Any]:
    """Retrieve all workflow traces associated with a task."""

    with get_connection() as connection:

        rows = connection.execute(
            """
            SELECT *
            FROM workflow_traces
            WHERE task_id = %s
            ORDER BY started_at DESC
            """,
            (task_id,),
        ).fetchall()

        traces = []

        for row in rows:
            trace = dict(row)

            trace["trace_events"] = json.loads(
                trace["trace_events"] or "[]"
            )

            traces.append(trace)

        return {
            "total_traces": len(traces),
            "traces": traces,
        }