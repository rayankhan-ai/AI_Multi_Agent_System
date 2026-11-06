# ============================================================
# POSTGRESQL AGENT PERFORMANCE ANALYTICS
# ============================================================

from typing import Any, Dict, List

from backend.services.database import get_connection
from backend.services.agent_monitor import initialize_agent_logs


def get_analytics_connection():
    """Return the centralized PostgreSQL connection."""

    return get_connection()


def get_agent_performance_analytics() -> Dict[str, Any]:
    """Calculate overall and agent-wise execution statistics."""

    initialize_agent_logs()

    with get_connection() as connection:

        overall_row = connection.execute(
            """
            SELECT
                COUNT(*) AS total_executions,

                COUNT(*) FILTER (
                    WHERE status = 'completed'
                ) AS successful_executions,

                COUNT(*) FILTER (
                    WHERE status = 'failed'
                ) AS failed_executions,

                AVG(duration_seconds) AS average_duration_seconds

            FROM agent_execution_logs
            """
        ).fetchone()

        total_executions = (
            overall_row["total_executions"] or 0
        )

        successful_executions = (
            overall_row["successful_executions"] or 0
        )

        failed_executions = (
            overall_row["failed_executions"] or 0
        )

        average_duration = (
            overall_row["average_duration_seconds"] or 0
        )

        success_rate = (
            successful_executions / total_executions * 100
            if total_executions > 0
            else 0.0
        )

        agent_rows = connection.execute(
            """
            SELECT
                agent_name,
                COUNT(*) AS total_executions,

                COUNT(*) FILTER (
                    WHERE status = 'completed'
                ) AS successful_executions,

                COUNT(*) FILTER (
                    WHERE status = 'failed'
                ) AS failed_executions,

                AVG(duration_seconds) AS average_duration_seconds

            FROM agent_execution_logs

            GROUP BY agent_name

            ORDER BY total_executions DESC
            """
        ).fetchall()

    agents: List[Dict[str, Any]] = []

    for row in agent_rows:

        agent_total = row["total_executions"] or 0

        agent_successful = (
            row["successful_executions"] or 0
        )

        agent_failed = row["failed_executions"] or 0

        agent_average_duration = (
            row["average_duration_seconds"] or 0
        )

        agent_success_rate = (
            agent_successful / agent_total * 100
            if agent_total > 0
            else 0.0
        )

        agents.append({
            "agent_name": row["agent_name"],
            "total_executions": agent_total,
            "successful_executions": agent_successful,
            "failed_executions": agent_failed,
            "success_rate": round(agent_success_rate, 2),
            "average_duration_seconds": round(
                agent_average_duration,
                2,
            ),
        })

    return {
        "total_executions": total_executions,
        "successful_executions": successful_executions,
        "failed_executions": failed_executions,
        "success_rate": round(success_rate, 2),
        "average_duration_seconds": round(
            average_duration,
            2,
        ),
        "agents": agents,
    }


def get_task_execution_analytics(
    task_id: str,
) -> Dict[str, Any]:
    """Return agent execution statistics for one task."""

    initialize_agent_logs()

    with get_connection() as connection:

        row = connection.execute(
            """
            SELECT
                COUNT(*) AS total_executions,

                COUNT(*) FILTER (
                    WHERE status = 'completed'
                ) AS successful_executions,

                COUNT(*) FILTER (
                    WHERE status = 'failed'
                ) AS failed_executions,

                AVG(duration_seconds) AS average_duration_seconds

            FROM agent_execution_logs

            WHERE task_id = %s
            """,
            (task_id,),
        ).fetchone()

    total = row["total_executions"] or 0
    successful = row["successful_executions"] or 0
    failed = row["failed_executions"] or 0

    average_duration = (
        row["average_duration_seconds"] or 0
    )

    success_rate = (
        successful / total * 100
        if total > 0
        else 0.0
    )

    return {
        "task_id": task_id,
        "total_executions": total,
        "successful_executions": successful,
        "failed_executions": failed,
        "success_rate": round(success_rate, 2),
        "average_duration_seconds": round(
            average_duration,
            2,
        ),
    }