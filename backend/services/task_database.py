# Import SQLite so tasks can be stored permanently.
import sqlite3

# Import JSON so task results can be stored in the database.
import json

# Import Path to manage the database file path.
from backend.services.storage_paths import DATABASE_PATH

def get_connection():
    """Create a database connection with dictionary-like rows."""

    connection = sqlite3.connect(
        str(DATABASE_PATH),
        timeout=30,
    )

    # Allow database rows to be accessed by column name.
    connection.row_factory = sqlite3.Row

    return connection


def initialize_task_database():
    """Create the task table and add columns required by newer versions."""

    with get_connection() as connection:

        # Create the table if it does not already exist.
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS research_tasks (
                task_id TEXT PRIMARY KEY,
                research_question TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                started_at TEXT,
                finished_at TEXT,
                error TEXT,
                report_filename TEXT,
                quality_score INTEGER,
                result_json TEXT,
                retry_count INTEGER NOT NULL DEFAULT 0
            )
            """
        )

        # Read the existing table columns.
        existing_columns = {
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(research_tasks)"
            ).fetchall()
        }

        # Add retry_count to databases created by the earlier version.
        if "retry_count" not in existing_columns:
            connection.execute(
                """
                ALTER TABLE research_tasks
                ADD COLUMN retry_count INTEGER NOT NULL DEFAULT 0
                """
            )

        connection.commit()


def save_task(task):
    """Insert a task or update an existing task."""

    initialize_task_database()

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
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)

            ON CONFLICT(task_id) DO UPDATE SET
                research_question = excluded.research_question,
                status = excluded.status,
                started_at = excluded.started_at,
                finished_at = excluded.finished_at,
                error = excluded.error,
                report_filename = excluded.report_filename,
                quality_score = excluded.quality_score,
                result_json = excluded.result_json,
                retry_count = excluded.retry_count
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
                json.dumps(
                    task.get("result"),
                    ensure_ascii=False,
                ),
                task.get("retry_count", 0),
            ),
        )

        connection.commit()


def get_saved_task(task_id):
    """Retrieve one task using its ID."""

    initialize_task_database()

    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT *
            FROM research_tasks
            WHERE task_id = ?
            """,
            (task_id,),
        ).fetchone()

    if row is None:
        return None

    task = dict(row)

    # Convert stored JSON back into a Python object.
    task["result"] = (
        json.loads(task["result_json"])
        if task.get("result_json")
        else None
    )

    # Do not expose the database's internal JSON column.
    task.pop("result_json", None)

    return task


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

    tasks = []

    for row in rows:
        task = dict(row)

        task["result"] = (
            json.loads(task["result_json"])
            if task.get("result_json")
            else None
        )

        task.pop("result_json", None)

        tasks.append(task)

    return tasks


def recover_interrupted_tasks():
    """
    Mark tasks left in 'running' status as failed.

    This function is intended to run when the backend starts.
    """

    initialize_task_database()

    with get_connection() as connection:
        cursor = connection.execute(
            """
            UPDATE research_tasks
            SET
                status = 'failed',
                finished_at = CURRENT_TIMESTAMP,
                error = ?
            WHERE status = 'running'
            """,
            (
                "The backend stopped before this task finished. "
                "You can retry the task.",
            ),
        )

        connection.commit()

        return cursor.rowcount
