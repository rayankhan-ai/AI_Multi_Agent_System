# backend/services/task_priority.py

# Import SQLite to store and retrieve task priorities.
import sqlite3

# Import type hints for clearer function definitions.
from typing import Optional

# Reuse the existing task database connection and location.
from backend.services.task_database import (
    get_connection,
    initialize_task_database,
)


# Define the priority levels and their numerical scores.
PRIORITY_SCORES = {
    "critical": 100,
    "high": 75,
    "normal": 50,
    "low": 25,
}


def initialize_priority_support():
    """Add priority support to the existing research task database."""

    # Ensure the original research_tasks table exists.
    initialize_task_database()

    # Connect to the existing SQLite database.
    with get_connection() as connection:

        # Inspect the columns currently available in the task table.
        existing_columns = {
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(research_tasks)"
            ).fetchall()
        }

        # Add a priority column only if it does not already exist.
        if "priority" not in existing_columns:
            connection.execute(
                """
                ALTER TABLE research_tasks
                ADD COLUMN priority TEXT NOT NULL DEFAULT 'normal'
                """
            )

        # Add an index to improve priority-based task queries.
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_tasks_priority_status
            ON research_tasks(status, priority, created_at)
            """
        )

        # Save the database changes.
        connection.commit()

    return {
        "success": True,
        "message": "Task priority support initialized.",
        "available_priorities": PRIORITY_SCORES,
    }


def validate_priority(priority: str) -> str:
    """Validate a priority and return its normalized value."""

    # Convert the provided value to lowercase.
    normalized_priority = priority.strip().lower()

    # Reject values outside the four supported levels.
    if normalized_priority not in PRIORITY_SCORES:
        raise ValueError(
            "Invalid priority. Choose critical, high, normal, or low."
        )

    return normalized_priority


def update_task_priority(
    task_id: str,
    priority: str,
):
    """Update the priority of an existing research task."""

    # Ensure the priority column exists before using it.
    initialize_priority_support()

    # Validate and normalize the requested priority.
    normalized_priority = validate_priority(priority)

    # Connect to the existing task database.
    with get_connection() as connection:

        # Check whether the requested task exists.
        task = connection.execute(
            """
            SELECT task_id, status, priority
            FROM research_tasks
            WHERE task_id = ?
            """,
            (task_id,),
        ).fetchone()

        # Return None if the task ID does not exist.
        if task is None:
            return None

        # Update only the priority field.
        connection.execute(
            """
            UPDATE research_tasks
            SET priority = ?
            WHERE task_id = ?
            """,
            (normalized_priority, task_id),
        )

        # Save the updated priority.
        connection.commit()

    return {
        "task_id": task_id,
        "previous_priority": task["priority"],
        "priority": normalized_priority,
        "priority_score": PRIORITY_SCORES[normalized_priority],
    }


def get_task_priority(task_id: str):
    """Retrieve the priority of a particular task."""

    # Ensure priority support has been initialized.
    initialize_priority_support()

    # Connect to the existing database.
    with get_connection() as connection:

        # Retrieve the requested task's priority.
        task = connection.execute(
            """
            SELECT task_id, research_question, status,
                   priority, created_at
            FROM research_tasks
            WHERE task_id = ?
            """,
            (task_id,),
        ).fetchone()

    # Return None when the task does not exist.
    if task is None:
        return None

    # Convert the database row into a regular dictionary.
    result = dict(task)

    # Attach a numerical score for easier comparisons.
    result["priority_score"] = PRIORITY_SCORES[
        result["priority"]
    ]

    return result


def get_tasks_by_priority(
    status: Optional[str] = "pending",
    limit: int = 100,
):
    """Retrieve research tasks ordered from highest to lowest priority."""

    # Ensure the priority column and index exist.
    initialize_priority_support()

    # Prevent invalid limits.
    if limit < 1 or limit > 500:
        raise ValueError("Limit must be between 1 and 500.")

    # Connect to the task database.
    with get_connection() as connection:

        # Retrieve all tasks or filter by their status.
        if status is None or status == "all":
            rows = connection.execute(
                """
                SELECT task_id, research_question, status,
                       priority, created_at, started_at,
                       finished_at, retry_count
                FROM research_tasks
                ORDER BY
                    CASE priority
                        WHEN 'critical' THEN 4
                        WHEN 'high' THEN 3
                        WHEN 'normal' THEN 2
                        WHEN 'low' THEN 1
                        ELSE 0
                    END DESC,
                    created_at ASC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        else:
            rows = connection.execute(
                """
                SELECT task_id, research_question, status,
                       priority, created_at, started_at,
                       finished_at, retry_count
                FROM research_tasks
                WHERE status = ?
                ORDER BY
                    CASE priority
                        WHEN 'critical' THEN 4
                        WHEN 'high' THEN 3
                        WHEN 'normal' THEN 2
                        WHEN 'low' THEN 1
                        ELSE 0
                    END DESC,
                    created_at ASC
                LIMIT ?
                """,
                (status, limit),
            ).fetchall()

    # Convert the returned rows into ordinary dictionaries.
    tasks = [dict(row) for row in rows]

    # Include a numerical score for every task.
    for task in tasks:
        task["priority_score"] = PRIORITY_SCORES.get(
            task["priority"],
            50,
        )

    # Return the ordered results and their total count.
    return {
        "success": True,
        "total_tasks": len(tasks),
        "status_filter": status,
        "tasks": tasks,
    }


def get_priority_statistics():
    """Count research tasks grouped by priority."""

    # Ensure priority support exists.
    initialize_priority_support()

    # Connect to the existing database.
    with get_connection() as connection:

        # Count tasks separately for each priority level.
        rows = connection.execute(
            """
            SELECT priority, COUNT(*) AS task_count
            FROM research_tasks
            GROUP BY priority
            """
        ).fetchall()

    # Include zero counts for priority levels not yet used.
    statistics = {
        priority: 0
        for priority in PRIORITY_SCORES
    }

    # Fill in the counts retrieved from SQLite.
    for row in rows:
        statistics[row["priority"]] = row["task_count"]

    return {
        "success": True,
        "priority_statistics": statistics,
        "total_tasks": sum(statistics.values()),
    }
