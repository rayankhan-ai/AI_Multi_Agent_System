# ============================================================
# POSTGRESQL TASK DATABASE
# AI MULTI-AGENT RESEARCH & AUTOMATION SYSTEM
# ============================================================

import json

# Use the centralized PostgreSQL connection.
from backend.services.database import (
    get_connection as postgres_connection,
    initialize_database,
)


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_connection():
    """
    Return a centralized PostgreSQL connection.

    Kept as a separate function to preserve compatibility
    with existing services importing task_database.get_connection.
    """

    return postgres_connection()


# ============================================================
# INITIALIZE TASK DATABASE
# ============================================================

def initialize_task_database():
    """
    Initialize the PostgreSQL schema required by task management.

    The centralized initializer also ensures that priority,
    dependency, and other project tables exist.
    """

    return initialize_database()


# ============================================================
# SAVE TASK
# ============================================================

def save_task(task):
    """
    Insert a new task or update an existing task.

    Existing task priority is preserved when updating a task.
    """

    initialize_task_database()

    result_json = json.dumps(
        task.get("result"),
        ensure_ascii=False,
    )

    with get_connection() as connection:

        connection.execute(
            """
            INSERT INTO research_tasks (
                task_id,
                research_question,
                status,
                created_at,
                started_at,
                finished_at,
                error,
                report_filename,
                quality_score,
                result_json,
                retry_count
            )

            VALUES (
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s
            )

            ON CONFLICT (task_id)
            DO UPDATE SET

                research_question = EXCLUDED.research_question,
                status = EXCLUDED.status,
                started_at = EXCLUDED.started_at,
                finished_at = EXCLUDED.finished_at,
                error = EXCLUDED.error,
                report_filename = EXCLUDED.report_filename,
                quality_score = EXCLUDED.quality_score,
                result_json = EXCLUDED.result_json,
                retry_count = EXCLUDED.retry_count
            """,
            (
                task["task_id"],
                task["research_question"],
                task["status"],
                task["created_at"],
                task.get("started_at"),
                task.get("finished_at"),
                task.get("error"),
                task.get("report_filename"),
                task.get("quality_score"),
                result_json,
                task.get("retry_count", 0),
            ),
        )


# ============================================================
# CONVERT DATABASE ROW INTO TASK
# ============================================================

def convert_row_to_task(row):
    """Convert a PostgreSQL task record into an API-friendly dictionary."""

    if row is None:
        return None

    task = dict(row)

    task["result"] = (
        json.loads(task["result_json"])
        if task.get("result_json")
        else None
    )

    task.pop("result_json", None)

    return task


# ============================================================
# GET ONE SAVED TASK
# ============================================================

def get_saved_task(task_id):
    """Retrieve one task using its ID."""

    initialize_task_database()

    with get_connection() as connection:

        row = connection.execute(
            """
            SELECT *
            FROM research_tasks
            WHERE task_id = %s
            """,
            (task_id,),
        ).fetchone()

    return convert_row_to_task(row)


# ============================================================
# GET ALL SAVED TASKS
# ============================================================

def get_saved_tasks():
    """Retrieve all tasks, newest first."""

    initialize_task_database()

    with get_connection() as connection:

        rows = connection.execute(
            """
            SELECT *
            FROM research_tasks
            ORDER BY created_at DESC
            """
        ).fetchall()

    return [
        convert_row_to_task(row)
        for row in rows
    ]


# ============================================================
# RECOVER INTERRUPTED TASKS
# ============================================================

def recover_interrupted_tasks():
    """
    Mark tasks left in running status as failed.

    Intended to run when the backend starts.
    """

    initialize_task_database()

    with get_connection() as connection:

        cursor = connection.execute(
            """
            UPDATE research_tasks

            SET
                status = 'failed',
                finished_at = CURRENT_TIMESTAMP,
                error = %s

            WHERE status = 'running'
            """,
            (
                "The backend stopped before this task finished. "
                "You can retry the task.",
            ),
        )

        return cursor.rowcount