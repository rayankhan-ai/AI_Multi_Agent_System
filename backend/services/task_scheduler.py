# ============================================================
# PRIORITY-BASED TASK SCHEDULER WITH DEPENDENCY SUPPORT
# ============================================================

from backend.services.task_database import (
    get_connection,
    initialize_task_database,
)

from backend.services.task_priority import (
    initialize_priority_support,
    PRIORITY_SCORES,
)

from backend.services.task_dependencies import (
    initialize_task_dependencies,
)


# ============================================================
# STEP 1 - INITIALIZE SCHEDULER SUPPORT
# ============================================================

def initialize_task_scheduler():
    """Initialize priority and dependency scheduling support."""

    initialize_task_database()
    initialize_priority_support()
    initialize_task_dependencies()

    return {
        "success": True,
        "message": (
            "Priority scheduler with dependency support initialized."
        ),
        "priority_order": [
            "critical",
            "high",
            "normal",
            "low",
        ],
    }


# ============================================================
# STEP 2 - FIND THE NEXT ELIGIBLE TASK
# ============================================================

def get_next_scheduled_task():
    """
    Find the highest-priority pending task whose prerequisites
    have all completed successfully.

    Tasks with unfinished dependencies are skipped.
    """

    initialize_priority_support()
    initialize_task_dependencies()

    with get_connection() as connection:

        row = connection.execute(
            """
            SELECT
                tasks.task_id,
                tasks.research_question,
                tasks.status,
                tasks.priority,
                tasks.created_at,
                tasks.retry_count

            FROM research_tasks AS tasks

            WHERE tasks.status = 'pending'

            AND NOT EXISTS (
                SELECT 1

                FROM task_dependencies AS dependencies

                JOIN research_tasks AS prerequisite
                    ON prerequisite.task_id =
                       dependencies.depends_on_task_id

                WHERE dependencies.task_id = tasks.task_id

                AND prerequisite.status != 'completed'
            )

            ORDER BY
                CASE tasks.priority
                    WHEN 'critical' THEN 4
                    WHEN 'high' THEN 3
                    WHEN 'normal' THEN 2
                    WHEN 'low' THEN 1
                    ELSE 0
                END DESC,

                tasks.created_at ASC,
                tasks.task_id ASC

            LIMIT 1
            """
        ).fetchone()

    if row is None:
        return {
            "success": True,
            "message": (
                "No eligible pending tasks are available. "
                "The queue may be empty or all pending tasks "
                "may have unfinished dependencies."
            ),
            "task": None,
        }

    task = dict(row)

    task["priority_score"] = PRIORITY_SCORES.get(
        task["priority"],
        50,
    )

    return {
        "success": True,
        "message": "Next eligible task selected successfully.",
        "task": task,
    }


# ============================================================
# STEP 3 - LIST ELIGIBLE TASKS IN PRIORITY ORDER
# ============================================================

def get_scheduled_task_queue(limit=100):
    """
    List pending tasks whose dependencies are satisfied,
    ordered by priority and creation time.
    """

    if limit < 1 or limit > 500:
        raise ValueError("Limit must be between 1 and 500.")

    initialize_priority_support()
    initialize_task_dependencies()

    with get_connection() as connection:

        rows = connection.execute(
            """
            SELECT
                tasks.task_id,
                tasks.research_question,
                tasks.status,
                tasks.priority,
                tasks.created_at,
                tasks.retry_count

            FROM research_tasks AS tasks

            WHERE tasks.status = 'pending'

            AND NOT EXISTS (
                SELECT 1

                FROM task_dependencies AS dependencies

                JOIN research_tasks AS prerequisite
                    ON prerequisite.task_id =
                       dependencies.depends_on_task_id

                WHERE dependencies.task_id = tasks.task_id

                AND prerequisite.status != 'completed'
            )

            ORDER BY
                CASE tasks.priority
                    WHEN 'critical' THEN 4
                    WHEN 'high' THEN 3
                    WHEN 'normal' THEN 2
                    WHEN 'low' THEN 1
                    ELSE 0
                END DESC,

                tasks.created_at ASC,
                tasks.task_id ASC

            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    tasks = [dict(row) for row in rows]

    for task in tasks:
        task["priority_score"] = PRIORITY_SCORES.get(
            task["priority"],
            50,
        )

    return {
        "success": True,
        "total_pending_tasks": len(tasks),
        "tasks": tasks,
    }


# ============================================================
# STEP 4 - CHECK SCHEDULER STATUS
# ============================================================

def get_scheduler_status():
    """
    Report pending task counts and the next eligible priority.
    """

    initialize_priority_support()
    initialize_task_dependencies()

    with get_connection() as connection:

        rows = connection.execute(
            """
            SELECT
                tasks.priority,
                COUNT(*) AS task_count

            FROM research_tasks AS tasks

            WHERE tasks.status = 'pending'

            AND NOT EXISTS (
                SELECT 1

                FROM task_dependencies AS dependencies

                JOIN research_tasks AS prerequisite
                    ON prerequisite.task_id =
                       dependencies.depends_on_task_id

                WHERE dependencies.task_id = tasks.task_id

                AND prerequisite.status != 'completed'
            )

            GROUP BY tasks.priority
            """
        ).fetchall()

    pending_counts = {
        priority: 0
        for priority in PRIORITY_SCORES
    }

    for row in rows:
        pending_counts[row["priority"]] = row["task_count"]

    total_pending = sum(pending_counts.values())

    next_priority = next(
        (
            priority
            for priority in ["critical", "high", "normal", "low"]
            if pending_counts.get(priority, 0) > 0
        ),
        None,
    )

    return {
        "success": True,
        "scheduler": "priority_and_dependency_based",
        "total_pending_tasks": total_pending,
        "pending_by_priority": pending_counts,
        "next_priority": next_priority,
    }