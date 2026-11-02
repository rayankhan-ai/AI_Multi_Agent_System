# ============================================================
# - AI MULTI-AGENT RESEARCH & AUTOMATION SYSTEM
#  - UNIFIED SYSTEM MONITORING
# ============================================================

import sqlite3

from pathlib import Path
from typing import Any, Dict, List

from backend.services.agent_analytics import (
    get_agent_performance_analytics,
)

from backend.services.agent_monitor import (
    get_recent_agent_logs,
)

from backend.services.task_manager import (
    get_all_tasks,
)


# Reuse the existing database.
DATABASE_PATH = (
    Path(__file__).resolve().parents[2] / "research_tasks.db"
)


def get_database_connection():
    """Create a connection to the existing SQLite database."""

    connection = sqlite3.connect(str(DATABASE_PATH))
    connection.row_factory = sqlite3.Row

    return connection


def get_workflow_statistics() -> Dict[str, Any]:
    """
    Calculate workflow execution statistics from the
    workflow_traces table.
    """

    connection = get_database_connection()

    try:
        # Count workflows and summarize their statuses.
        query = """
            SELECT
                COUNT(*) AS total_workflows,

                SUM(
                    CASE
                        WHEN workflow_status = 'completed'
                        THEN 1 ELSE 0
                    END
                ) AS completed_workflows,

                SUM(
                    CASE
                        WHEN workflow_status = 'failed'
                        THEN 1 ELSE 0
                    END
                ) AS failed_workflows,

                SUM(
                    CASE
                        WHEN workflow_status = 'running'
                        THEN 1 ELSE 0
                    END
                ) AS running_workflows,

                AVG(duration_seconds) AS average_duration_seconds

            FROM workflow_traces
        """

        row = connection.execute(query).fetchone()

        total = row["total_workflows"] or 0
        completed = row["completed_workflows"] or 0
        failed = row["failed_workflows"] or 0
        running = row["running_workflows"] or 0

        average_duration = (
            row["average_duration_seconds"] or 0
        )

        # Calculate the workflow success percentage.
        if total > 0:
            success_rate = completed / total * 100
        else:
            success_rate = 0.0

        return {
            "total_workflows": total,
            "completed_workflows": completed,
            "failed_workflows": failed,
            "running_workflows": running,
            "success_rate": round(success_rate, 2),
            "average_duration_seconds": round(
                average_duration, 2
            ),
        }

    finally:
        connection.close()


def get_system_overview() -> Dict[str, Any]:
    """
    Combine task, agent, and workflow statistics
    into one system overview.
    """

    # Retrieve agent execution analytics.
    agent_analytics = get_agent_performance_analytics()

    # Retrieve workflow execution statistics.
    workflow_analytics = get_workflow_statistics()

    # Retrieve the existing task records.
    tasks = get_all_tasks()

    # Count tasks by their current status.
    task_status_counts = {
        "total": 0,
        "pending": 0,
        "running": 0,
        "completed": 0,
        "failed": 0,
    }

    # Task manager results may be a list or a dictionary
    # containing a list, depending on its implementation.
    if isinstance(tasks, dict):
        task_list = tasks.get("tasks", [])
    elif isinstance(tasks, list):
        task_list = tasks
    else:
        task_list = []

    for task in task_list:
        if not isinstance(task, dict):
            continue

        status = str(task.get("status", "unknown")).lower()

        task_status_counts["total"] += 1

        if status in task_status_counts:
            task_status_counts[status] += 1

    # Return a unified response.
    return {
        "system_status": (
            "operational"
            if workflow_analytics["failed_workflows"] == 0
            else "operational_with_failures"
        ),
        "tasks": task_status_counts,
        "agents": {
            "total_executions": agent_analytics[
                "total_executions"
            ],
            "successful_executions": agent_analytics[
                "successful_executions"
            ],
            "failed_executions": agent_analytics[
                "failed_executions"
            ],
            "success_rate": agent_analytics["success_rate"],
            "average_duration_seconds": agent_analytics[
                "average_duration_seconds"
            ],
            "agent_details": agent_analytics["agents"],
        },
        "workflows": workflow_analytics,
    }


def get_recent_system_activity(
    limit: int = 20,
) -> Dict[str, Any]:
    """
    Return the latest agent execution records.
    """

    # Keep the requested result size within reasonable bounds.
    safe_limit = max(1, min(limit, 100))

    # Reuse the existing monitoring implementation.
    activity = get_recent_agent_logs(limit=safe_limit)

    return {
        "limit": safe_limit,
        "activity": activity,
    }


def get_task_diagnostics(
    task_id: str,
) -> Dict[str, Any]:
    """
    Retrieve monitoring information for one task.
    """

    connection = get_database_connection()

    try:
        # Fetch all traces linked to this task.
        trace_rows = connection.execute(
            """
            SELECT *
            FROM workflow_traces
            WHERE task_id = ?
            ORDER BY started_at DESC
            """,
            (task_id,),
        ).fetchall()

        traces: List[Dict[str, Any]] = []

        for row in trace_rows:
            trace = dict(row)

            # Decode the stored workflow event timeline.
            import json

            trace["trace_events"] = json.loads(
                trace.get("trace_events") or "[]"
            )

            traces.append(trace)

        # Fetch agent logs for the same task.
        log_rows = connection.execute(
            """
            SELECT
                log_id,
                task_id,
                agent_name,
                status,
                started_at,
                finished_at,
                duration_seconds,
                input_summary,
                output_summary,
                error_message
            FROM agent_execution_logs
            WHERE task_id = ?
            ORDER BY started_at ASC
            """,
            (task_id,),
        ).fetchall()

        agent_logs = [dict(row) for row in log_rows]

        # Return one combined diagnostic response.
        return {
            "task_id": task_id,
            "trace_count": len(traces),
            "agent_execution_count": len(agent_logs),
            "traces": traces,
            "agent_logs": agent_logs,
        }

    finally:
        connection.close()

