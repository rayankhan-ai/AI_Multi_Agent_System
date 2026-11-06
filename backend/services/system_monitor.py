# ============================================================
# AI MULTI-AGENT RESEARCH & AUTOMATION SYSTEM
# POSTGRESQL UNIFIED SYSTEM MONITORING
# ============================================================

import json

from typing import Any, Dict, List

from backend.services.database import get_connection

from backend.services.agent_analytics import (
    get_agent_performance_analytics,
)

from backend.services.agent_monitor import (
    get_recent_agent_logs,
)

from backend.services.task_manager import (
    get_all_tasks,
)


def get_database_connection():
    """Compatibility wrapper for the PostgreSQL connection."""

    return get_connection()


def get_workflow_statistics() -> Dict[str, Any]:
    """Calculate workflow execution statistics."""

    with get_connection() as connection:

        query = """
            SELECT
                COUNT(*) AS total_workflows,

                COUNT(*) FILTER (
                    WHERE workflow_status = 'completed'
                ) AS completed_workflows,

                COUNT(*) FILTER (
                    WHERE workflow_status = 'failed'
                ) AS failed_workflows,

                COUNT(*) FILTER (
                    WHERE workflow_status = 'running'
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
                float(average_duration), 2
            ),
        }


def get_system_overview() -> Dict[str, Any]:
    """Combine task, agent, and workflow statistics."""

    agent_analytics = get_agent_performance_analytics()

    workflow_analytics = get_workflow_statistics()

    tasks = get_all_tasks()

    task_status_counts = {
        "total": 0,
        "pending": 0,
        "running": 0,
        "completed": 0,
        "failed": 0,
    }

    if isinstance(tasks, dict):
        task_list = tasks.get("tasks", [])
    elif isinstance(tasks, list):
        task_list = tasks
    else:
        task_list = []

    for task in task_list:

        if not isinstance(task, dict):
            continue

        status = str(
            task.get("status", "unknown")
        ).lower()

        task_status_counts["total"] += 1

        if status in task_status_counts:
            task_status_counts[status] += 1

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
            "success_rate": agent_analytics[
                "success_rate"
            ],
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
    """Return recent agent execution records."""

    safe_limit = max(1, min(limit, 100))

    activity = get_recent_agent_logs(
        limit=safe_limit
    )

    return {
        "limit": safe_limit,
        "activity": activity,
    }


def get_task_diagnostics(
    task_id: str,
) -> Dict[str, Any]:
    """Retrieve monitoring information for one task."""

    with get_connection() as connection:

        trace_rows = connection.execute(
            """
            SELECT *
            FROM workflow_traces
            WHERE task_id = %s
            ORDER BY started_at DESC
            """,
            (task_id,),
        ).fetchall()

        traces: List[Dict[str, Any]] = []

        for row in trace_rows:

            trace = dict(row)

            trace["trace_events"] = json.loads(
                trace.get("trace_events") or "[]"
            )

            traces.append(trace)

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
            WHERE task_id = %s
            ORDER BY started_at ASC
            """,
            (task_id,),
        ).fetchall()

        agent_logs = [
            dict(row)
            for row in log_rows
        ]

        return {
            "task_id": task_id,
            "trace_count": len(traces),
            "traces": traces,
            "agent_execution_count": len(agent_logs),
            "agent_logs": agent_logs,
        }