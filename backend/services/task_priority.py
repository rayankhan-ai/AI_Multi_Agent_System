# ============================================================
# POSTGRESQL TASK PRIORITY MANAGEMENT
# ============================================================

from typing import Optional
import threading

from backend.services.task_database import (
    get_connection,
    initialize_task_database,
)


# ============================================================
# PRIORITY CONFIGURATION
# ============================================================

PRIORITY_SCORES = {
    "critical": 100,
    "high": 75,
    "normal": 50,
    "low": 25,
}


# ============================================================
# PRIORITY INITIALIZATION CACHE
# ============================================================

_PRIORITY_INITIALIZED = False
_PRIORITY_INITIALIZATION_LOCK = threading.Lock()
_PRIORITY_INITIALIZATION_RESULT = None



# ============================================================
# INITIALIZE PRIORITY SUPPORT
# ============================================================

# ============================================================
# INITIALIZE PRIORITY SUPPORT
# ============================================================

def initialize_priority_support():
    """Initialize priority support once per backend process."""

    global _PRIORITY_INITIALIZED
    global _PRIORITY_INITIALIZATION_RESULT

    # Return the cached result when already initialized.
    if _PRIORITY_INITIALIZED:
        result = _PRIORITY_INITIALIZATION_RESULT.copy()
        result["cached"] = True
        return result

    # Protect initialization against concurrent calls.
    with _PRIORITY_INITIALIZATION_LOCK:

        # Check again after acquiring the lock.
        if _PRIORITY_INITIALIZED:
            result = _PRIORITY_INITIALIZATION_RESULT.copy()
            result["cached"] = True
            return result

        # Initialize the central task database.
        initialize_task_database()

        # Ensure the priority column and index exist.
        with get_connection() as connection:

            connection.execute(
                """
                ALTER TABLE research_tasks
                ADD COLUMN IF NOT EXISTS
                priority TEXT NOT NULL DEFAULT 'normal'
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_tasks_priority_status
                ON research_tasks(status, priority, created_at)
                """
            )

        # Save the successful initialization result.
        _PRIORITY_INITIALIZATION_RESULT = {
            "success": True,
            "message": "Task priority support initialized.",
            "available_priorities": PRIORITY_SCORES,
        }

        # Mark initialization as complete.
        _PRIORITY_INITIALIZED = True

        result = _PRIORITY_INITIALIZATION_RESULT.copy()
        result["cached"] = False

        return result


# ============================================================
# VALIDATE PRIORITY
# ============================================================

def validate_priority(priority: str) -> str:
    """Validate and normalize a priority."""

    normalized_priority = priority.strip().lower()

    if normalized_priority not in PRIORITY_SCORES:
        raise ValueError(
            "Invalid priority. Choose critical, high, normal, or low."
        )

    return normalized_priority


# ============================================================
# UPDATE TASK PRIORITY
# ============================================================

def update_task_priority(task_id: str, priority: str):
    """Update the priority of an existing task."""

    initialize_priority_support()

    normalized_priority = validate_priority(priority)

    with get_connection() as connection:

        task = connection.execute(
            """
            SELECT task_id, status, priority
            FROM research_tasks
            WHERE task_id = %s
            """,
            (task_id,),
        ).fetchone()

        if task is None:
            return None

        connection.execute(
            """
            UPDATE research_tasks
            SET priority = %s
            WHERE task_id = %s
            """,
            (
                normalized_priority,
                task_id,
            ),
        )

    return {
        "task_id": task_id,
        "previous_priority": task["priority"],
        "priority": normalized_priority,
        "priority_score": PRIORITY_SCORES[normalized_priority],
    }


# ============================================================
# GET TASK PRIORITY
# ============================================================

def get_task_priority(task_id: str):
    """Retrieve a task's priority."""

    initialize_priority_support()

    with get_connection() as connection:

        task = connection.execute(
            """
            SELECT
                task_id,
                research_question,
                status,
                priority,
                created_at
            FROM research_tasks
            WHERE task_id = %s
            """,
            (task_id,),
        ).fetchone()

    if task is None:
        return None

    result = dict(task)

    result["priority_score"] = PRIORITY_SCORES.get(
        result["priority"],
        50,
    )

    return result


# ============================================================
# GET TASKS BY PRIORITY
# ============================================================

def get_tasks_by_priority(
    status: Optional[str] = "pending",
    limit: int = 100,
):
    """Retrieve tasks ordered by priority."""

    initialize_priority_support()

    if limit < 1 or limit > 500:
        raise ValueError("Limit must be between 1 and 500.")

    with get_connection() as connection:

        if status is None or status == "all":

            rows = connection.execute(
                """
                SELECT
                    task_id,
                    research_question,
                    status,
                    priority,
                    created_at,
                    started_at,
                    finished_at,
                    retry_count
                FROM research_tasks

                ORDER BY
                    CASE priority
                        WHEN 'critical' THEN 4
                        WHEN 'high' THEN 3
                        WHEN 'normal' THEN 2
                        WHEN 'low' THEN 1
                        ELSE 0
                    END DESC,

                    created_at ASC,
                    task_id ASC

                LIMIT %s
                """,
                (limit,),
            ).fetchall()

        else:

            rows = connection.execute(
                """
                SELECT
                    task_id,
                    research_question,
                    status,
                    priority,
                    created_at,
                    started_at,
                    finished_at,
                    retry_count
                FROM research_tasks

                WHERE status = %s

                ORDER BY
                    CASE priority
                        WHEN 'critical' THEN 4
                        WHEN 'high' THEN 3
                        WHEN 'normal' THEN 2
                        WHEN 'low' THEN 1
                        ELSE 0
                    END DESC,

                    created_at ASC,
                    task_id ASC

                LIMIT %s
                """,
                (
                    status,
                    limit,
                ),
            ).fetchall()

    tasks = [
        dict(row)
        for row in rows
    ]

    for task in tasks:
        task["priority_score"] = PRIORITY_SCORES.get(
            task["priority"],
            50,
        )

    return {
        "success": True,
        "total_tasks": len(tasks),
        "status_filter": status,
        "tasks": tasks,
    }


# ============================================================
# GET PRIORITY STATISTICS
# ============================================================

def get_priority_statistics():
    """Count tasks grouped by priority."""

    initialize_priority_support()

    with get_connection() as connection:

        rows = connection.execute(
            """
            SELECT
                priority,
                COUNT(*) AS task_count
            FROM research_tasks
            GROUP BY priority
            """
        ).fetchall()

    statistics = {
        priority: 0
        for priority in PRIORITY_SCORES
    }

    for row in rows:
        statistics[row["priority"]] = row["task_count"]

    return {
        "success": True,
        "priority_statistics": statistics,
        "total_tasks": sum(statistics.values()),
    }
