# ============================================================

#  — ATOMIC TASK CLAIMING

# File: backend/services/task_claiming.py

# ============================================================

import sqlite3

# Import the existing database functions.

from backend.services.task_database import (
get_connection,
initialize_task_database,
)

# Import priority management functions.

from backend.services.task_priority import (
initialize_priority_support,
PRIORITY_SCORES,
)

# ============================================================

# STEP 1: INITIALIZE TASK CLAIMING

# ============================================================

def initialize_task_claiming():
    """
    Initialize the database structures required for task claiming.
    """


# Initialize the existing research task database.
    initialize_task_database()

# Ensure the task priority column exists.
    initialize_priority_support()

# Return a success response.
    return {
    "success": True,
    "message": "Atomic task claiming initialized successfully.",
}


# ============================================================

# STEP 2: CLAIM THE NEXT HIGHEST-PRIORITY TASK

# ============================================================

def claim_next_pending_task():
    """
Atomically claim the highest-priority pending research task.


The function selects a pending task and changes its status
to running within the same database transaction.

If no pending task exists, it returns task=None.
    """

# Initialize the database and priority support.
    initialize_task_claiming()

# Open a connection to the existing SQLite database.
    with get_connection() as connection:

    # Begin a write transaction before selecting a task.
        connection.execute("BEGIN IMMEDIATE")

    try:
        # Select the highest-priority pending task.
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
            """
        ).fetchone()

        # If there are no pending tasks, finish the transaction.
        if row is None:
            connection.commit()

            return {
                "success": True,
                "message": "No pending tasks are available.",
                "task": None,
            }

        # Get the ID of the selected task.
        task_id = row["task_id"]

        # Update the task status from pending to running.
        cursor = connection.execute(
            """
            UPDATE research_tasks
            SET status = 'running',
                started_at = COALESCE(
                    started_at,
                    CURRENT_TIMESTAMP
                )
            WHERE task_id = ?
              AND status = 'pending'
            """,
            (task_id,),
        )

        # Confirm that exactly one task was updated.
        if cursor.rowcount != 1:
            connection.rollback()

            return {
                "success": False,
                "message": "The task could not be claimed.",
                "task": None,
            }

        # Save the task claim.
        connection.commit()

        # Convert the database row into a Python dictionary.
        task = dict(row)

        # Reflect the updated status in the returned task.
        task["status"] = "running"

        # Add the numeric priority score.
        task["priority_score"] = PRIORITY_SCORES.get(
            task["priority"],
            50,
        )

        # Return the successfully claimed task.
        return {
            "success": True,
            "message": "Task claimed successfully.",
            "task": task,
        }

    except sqlite3.Error:
        # Undo database changes if a database error occurs.
        connection.rollback()

        # Raise the error so it can be diagnosed.
        raise
