# ============================================================
# POSTGRESQL ATOMIC TASK CLAIMING
# ============================================================

from psycopg import Error as PostgreSQLError

from backend.services.task_database import (
    get_connection,
    initialize_task_database,
)

from backend.services.task_priority import (
    initialize_priority_support,
    PRIORITY_SCORES,
)


# ============================================================
# INITIALIZE TASK CLAIMING
# ============================================================

def initialize_task_claiming():
    """Initialize the database structures for task claiming."""

    initialize_task_database()
    initialize_priority_support()

    return {
        "success": True,
        "message": "Atomic task claiming initialized successfully.",
    }


# ============================================================
# CLAIM NEXT HIGHEST-PRIORITY TASK
# ============================================================

def claim_next_pending_task():
    """
    Atomically claim the highest-priority eligible task.

    FOR UPDATE SKIP LOCKED prevents multiple workers
    from claiming the same task.
    """

    initialize_task_claiming()

    try:

        with get_connection() as connection:

            # Lock one pending task while selecting it.
            row = connection.execute(
                """
                SELECT
                    task_id,
                    research_question,
                    status,
                    priority,
                    created_at,
                    retry_count

                FROM research_tasks

                WHERE status = 'pending'

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

                LIMIT 1

                FOR UPDATE SKIP LOCKED
                """
            ).fetchone()

            if row is None:
                return {
                    "success": True,
                    "message": "No pending tasks are available.",
                    "task": None,
                }

            task_id = row["task_id"]

            # Change the task status inside the same transaction.
            updated_row = connection.execute(
                """
                UPDATE research_tasks

                SET
                    status = 'running',
                    started_at = COALESCE(
                        started_at,
                        CURRENT_TIMESTAMP
                    )

                WHERE task_id = %s
                  AND status = 'pending'

                RETURNING started_at
                """,
                (task_id,),
            ).fetchone()

            if updated_row is None:
                return {
                    "success": False,
                    "message": "The task could not be claimed.",
                    "task": None,
                }

            task = dict(row)

            task["status"] = "running"
            task["started_at"] = updated_row["started_at"]

            task["priority_score"] = PRIORITY_SCORES.get(
                task["priority"],
                50,
            )

            return {
                "success": True,
                "message": "Task claimed successfully.",
                "task": task,
            }

    except PostgreSQLError:
        raise