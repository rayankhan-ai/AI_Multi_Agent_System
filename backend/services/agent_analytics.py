# ============================================================
#  - AI MULTI-AGENT RESEARCH & AUTOMATION SYSTEM
#  - AGENT PERFORMANCE ANALYTICS
# ============================================================

# sqlite3 allows us to query the existing SQLite database.
import sqlite3

# Path helps us locate the database independently of the
# directory from which the application is started.
from pathlib import Path

# Any allows the function to return dictionaries containing
# different types of analytics values.
from typing import Any, Dict, List


# Use the existing research task database.
# This is the same database used by agent_monitor.py.
DATABASE_PATH = (
    Path(__file__).resolve().parents[2] / "research_tasks.db"
)


def get_analytics_connection():
    """
    Open a connection to the existing SQLite database.
    Return rows in a format that supports column-name access.
    """

    connection = sqlite3.connect(str(DATABASE_PATH))

    # Allow queries such as row["agent_name"].
    connection.row_factory = sqlite3.Row

    return connection


def get_agent_performance_analytics() -> Dict[str, Any]:
    """
    Calculate overall and agent-wise execution statistics.
    """

    # Open the existing monitoring database.
    connection = get_analytics_connection()

    try:
        # Read the overall execution statistics.
        overall_query = """
            SELECT
                COUNT(*) AS total_executions,

                SUM(
                    CASE
                        WHEN status = 'completed' THEN 1
                        ELSE 0
                    END
                ) AS successful_executions,

                SUM(
                    CASE
                        WHEN status = 'failed' THEN 1
                        ELSE 0
                    END
                ) AS failed_executions,

                AVG(duration_seconds) AS average_duration_seconds

            FROM agent_execution_logs
        """

        overall_row = connection.execute(
            overall_query
        ).fetchone()

        # Convert database NULL values into useful defaults.
        total_executions = overall_row["total_executions"] or 0

        successful_executions = (
            overall_row["successful_executions"] or 0
        )

        failed_executions = (
            overall_row["failed_executions"] or 0
        )

        average_duration = (
            overall_row["average_duration_seconds"] or 0
        )

        # Avoid division by zero when there are no executions.
        if total_executions > 0:
            success_rate = (
                successful_executions / total_executions
            ) * 100
        else:
            success_rate = 0.0

        # Retrieve performance statistics for every agent.
        agent_query = """
            SELECT
                agent_name,

                COUNT(*) AS total_executions,

                SUM(
                    CASE
                        WHEN status = 'completed' THEN 1
                        ELSE 0
                    END
                ) AS successful_executions,

                SUM(
                    CASE
                        WHEN status = 'failed' THEN 1
                        ELSE 0
                    END
                ) AS failed_executions,

                AVG(duration_seconds) AS average_duration_seconds

            FROM agent_execution_logs

            GROUP BY agent_name

            ORDER BY total_executions DESC
        """

        agent_rows = connection.execute(
            agent_query
        ).fetchall()

        # Build a clean list of agent statistics.
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

            # Calculate the success rate for this agent.
            if agent_total > 0:
                agent_success_rate = (
                    agent_successful / agent_total
                ) * 100
            else:
                agent_success_rate = 0.0

            # Append this agent's metrics to the result.
            agents.append(
                {
                    "agent_name": row["agent_name"],
                    "total_executions": agent_total,
                    "successful_executions": agent_successful,
                    "failed_executions": agent_failed,
                    "success_rate": round(
                        agent_success_rate, 2
                    ),
                    "average_duration_seconds": round(
                        agent_average_duration, 2
                    ),
                }
            )

        # Return a structured analytics response.
        return {
            "total_executions": total_executions,
            "successful_executions": successful_executions,
            "failed_executions": failed_executions,
            "success_rate": round(success_rate, 2),
            "average_duration_seconds": round(
                average_duration, 2
            ),
            "agents": agents,
        }

    finally:
        # Always close the database connection.
        connection.close()


def get_task_execution_analytics(
    task_id: str,
) -> Dict[str, Any]:
    """
    Return monitoring statistics for one specific task.
    """

    # Connect to the monitoring database.
    connection = get_analytics_connection()

    try:
        # Select the execution records belonging to this task.
        query = """
            SELECT
                COUNT(*) AS total_executions,

                SUM(
                    CASE
                        WHEN status = 'completed' THEN 1
                        ELSE 0
                    END
                ) AS successful_executions,

                SUM(
                    CASE
                        WHEN status = 'failed' THEN 1
                        ELSE 0
                    END
                ) AS failed_executions,

                AVG(duration_seconds) AS average_duration_seconds

            FROM agent_execution_logs

            WHERE task_id = ?
        """

        row = connection.execute(
            query,
            (task_id,),
        ).fetchone()

        # Convert NULL values into numeric defaults.
        total = row["total_executions"] or 0
        successful = row["successful_executions"] or 0
        failed = row["failed_executions"] or 0

        average_duration = (
            row["average_duration_seconds"] or 0
        )

        # Calculate the task's agent success rate.
        if total > 0:
            success_rate = (successful / total) * 100
        else:
            success_rate = 0.0

        # Return task-specific metrics.
        return {
            "task_id": task_id,
            "total_executions": total,
            "successful_executions": successful,
            "failed_executions": failed,
            "success_rate": round(success_rate, 2),
            "average_duration_seconds": round(
                average_duration, 2
            ),
        }

    finally:
        # Close the database connection after querying.
        connection.close()
