# ============================================================
#  - AI MULTI-AGENT RESEARCH & AUTOMATION SYSTEM
# - WORKFLOW EXECUTION TRACING
# ============================================================

import json
import sqlite3
import uuid

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


# Reuse the existing project database.
DATABASE_PATH = (
    Path(__file__).resolve().parents[2] / "research_tasks.db"
)


def get_timestamp() -> str:
    """Return the current UTC timestamp in ISO format."""

    return datetime.now(timezone.utc).isoformat()


def get_connection():
    """Create a SQLite connection with named-column access."""

    connection = sqlite3.connect(str(DATABASE_PATH))
    connection.row_factory = sqlite3.Row

    return connection


def initialize_workflow_tracing() -> None:
    """Create the workflow trace table if it does not exist."""

    connection = get_connection()

    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS workflow_traces (
                trace_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                research_question TEXT,
                workflow_status TEXT NOT NULL,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                duration_seconds REAL,
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

        connection.commit()

    finally:
        connection.close()


def start_workflow_trace(
    task_id: str,
    research_question: str,
) -> str:
    """
    Create a trace record when a workflow begins.
    Return the unique trace ID.
    """

    initialize_workflow_tracing()

    # Generate a unique ID for this workflow execution.
    trace_id = str(uuid.uuid4())

    # Record the workflow start time.
    started_at = get_timestamp()

    # Store the initial workflow event.
    initial_events = [
        {
            "event": "workflow_started",
            "timestamp": started_at,
            "status": "running",
            "details": "Research workflow execution started.",
        }
    ]

    connection = get_connection()

    try:
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
            VALUES (?, ?, ?, ?, ?, ?, ?)
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

        connection.commit()

    finally:
        connection.close()

    return trace_id


def add_workflow_trace_event(
    trace_id: str,
    event_name: str,
    status: str = "completed",
    details: str = "",
) -> Dict[str, Any]:
    """Append a timestamped event to an existing workflow trace."""

    connection = get_connection()

    try:
        # Retrieve the existing trace record.
        row = connection.execute(
            """
            SELECT trace_events, event_count
            FROM workflow_traces
            WHERE trace_id = ?
            """,
            (trace_id,),
        ).fetchone()

        if row is None:
            raise ValueError(
                f"Workflow trace not found: {trace_id}"
            )

        # Decode the events already stored in SQLite.
        events = json.loads(row["trace_events"] or "[]")

        # Construct the new event.
        event = {
            "event": event_name,
            "timestamp": get_timestamp(),
            "status": status,
            "details": details,
        }

        # Append the new event to the timeline.
        events.append(event)

        # Update the stored timeline and event count.
        connection.execute(
            """
            UPDATE workflow_traces
            SET trace_events = ?,
                event_count = ?
            WHERE trace_id = ?
            """,
            (
                json.dumps(events),
                len(events),
                trace_id,
            ),
        )

        connection.commit()

        return event

    finally:
        connection.close()


def finish_workflow_trace(
    trace_id: str,
    workflow_status: str,
    error_message: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Mark a workflow trace as completed or failed.
    Calculate the total execution duration.
    """

    finished_at = get_timestamp()

    connection = get_connection()

    try:
        # Find the original start time and existing timeline.
        row = connection.execute(
            """
            SELECT started_at, trace_events
            FROM workflow_traces
            WHERE trace_id = ?
            """,
            (trace_id,),
        ).fetchone()

        if row is None:
            raise ValueError(
                f"Workflow trace not found: {trace_id}"
            )

        # Convert both timestamps to datetime objects.
        started_at = datetime.fromisoformat(row["started_at"])
        finished_datetime = datetime.fromisoformat(finished_at)

        # Calculate the complete workflow duration in seconds.
        duration_seconds = (
            finished_datetime - started_at
        ).total_seconds()

        # Load the previous events.
        events = json.loads(row["trace_events"] or "[]")

        # Append the final event.
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

        # Save the final status, timing, and event timeline.
        connection.execute(
            """
            UPDATE workflow_traces
            SET workflow_status = ?,
                finished_at = ?,
                duration_seconds = ?,
                event_count = ?,
                error_message = ?,
                trace_events = ?
            WHERE trace_id = ?
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

        connection.commit()

        return {
            "trace_id": trace_id,
            "workflow_status": workflow_status,
            "started_at": started_at.isoformat(),
            "finished_at": finished_at,
            "duration_seconds": round(
                duration_seconds, 3
            ),
            "event_count": len(events),
        }

    finally:
        connection.close()


def get_workflow_trace(
    trace_id: str,
) -> Optional[Dict[str, Any]]:
    """Retrieve one workflow trace by its unique trace ID."""

    connection = get_connection()

    try:
        row = connection.execute(
            """
            SELECT *
            FROM workflow_traces
            WHERE trace_id = ?
            """,
            (trace_id,),
        ).fetchone()

        # Return None when the requested trace does not exist.
        if row is None:
            return None

        # Convert the database row to a normal dictionary.
        result = dict(row)

        # Decode the event timeline into a JSON list.
        result["trace_events"] = json.loads(
            result["trace_events"] or "[]"
        )

        return result

    finally:
        connection.close()


def get_task_workflow_traces(
    task_id: str,
) -> Dict[str, Any]:
    """Retrieve all workflow traces associated with one task."""

    connection = get_connection()

    try:
        rows = connection.execute(
            """
            SELECT *
            FROM workflow_traces
            WHERE task_id = ?
            ORDER BY started_at DESC
            """,
            (task_id,),
        ).fetchall()

        # Convert each database row into a response dictionary.
        traces = []

        for row in rows:
            trace = dict(row)

            trace["trace_events"] = json.loads(
                trace["trace_events"] or "[]"
            )

            traces.append(trace)

        return {
            "task_id": task_id,
            "total_traces": len(traces),
            "traces": traces,
        }

    finally:
        connection.close()
