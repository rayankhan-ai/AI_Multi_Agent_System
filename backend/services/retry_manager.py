# ============================================================
#  - AI MULTI-AGENT RESEARCH & AUTOMATION SYSTEM
#  - INTELLIGENT FAILURE RECOVERY & RETRY MANAGEMENT
# ============================================================

import json
import sqlite3
import time
import uuid

from datetime import datetime, timezone
from pathlib import Path
from backend.services.storage_paths import DATABASE_PATH
from typing import Any, Callable, Dict, Optional, TypeVar


# Reuse the existing project database.
# Configure the retry policy.
MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 1.0
MAX_RETRY_DELAY = 8.0

# Generic return type for retryable functions.
T = TypeVar("T")


def get_timestamp() -> str:
    """Return the current UTC timestamp."""

    return datetime.now(timezone.utc).isoformat()


def get_connection():
    """Create a SQLite database connection."""

    connection = sqlite3.connect(str(DATABASE_PATH))
    connection.row_factory = sqlite3.Row

    return connection


def initialize_retry_database() -> None:
    """Create the retry log table if it does not exist."""

    connection = get_connection()

    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS agent_retry_logs (
                retry_id TEXT PRIMARY KEY,
                task_id TEXT,
                agent_name TEXT NOT NULL,
                attempt_number INTEGER NOT NULL,
                max_attempts INTEGER NOT NULL,
                status TEXT NOT NULL,
                error_message TEXT,
                delay_seconds REAL DEFAULT 0,
                created_at TEXT NOT NULL
            )
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_agent_retry_logs_task_id
            ON agent_retry_logs(task_id)
            """
        )

        connection.commit()

    finally:
        connection.close()


def is_retryable_error(error: Exception) -> bool:
    """
    Determine whether an error is likely temporary.

    This is a conservative heuristic, not a guarantee.
    """

    # Authentication, permission, and configuration errors
    # should not be retried automatically.
    permanent_error_terms = (
        "authentication",
        "unauthorized",
        "forbidden",
        "invalid api key",
        "invalid_api_key",
        "permission denied",
        "not found",
        "bad request",
        "configuration error",
    )

    message = str(error).lower()

    if any(term in message for term in permanent_error_terms):
        return False

    # Network and service availability errors are often temporary.
    retryable_error_terms = (
        "timeout",
        "timed out",
        "connection reset",
        "connection refused",
        "connection error",
        "temporary failure",
        "temporarily unavailable",
        "rate limit",
        "rate_limit",
        "429",
        "500",
        "502",
        "503",
        "504",
        "server error",
        "service unavailable",
    )

    if any(term in message for term in retryable_error_terms):
        return True

    # Avoid retrying unknown exceptions by default.
    return False


def record_retry_attempt(
    task_id: str,
    agent_name: str,
    attempt_number: int,
    max_attempts: int,
    status: str,
    error_message: Optional[str] = None,
    delay_seconds: float = 0,
) -> Dict[str, Any]:
    """Persist one retry attempt in SQLite."""

    initialize_retry_database()

    retry_record = {
        "retry_id": str(uuid.uuid4()),
        "task_id": task_id,
        "agent_name": agent_name,
        "attempt_number": attempt_number,
        "max_attempts": max_attempts,
        "status": status,
        "error_message": error_message,
        "delay_seconds": round(delay_seconds, 3),
        "created_at": get_timestamp(),
    }

    connection = get_connection()

    try:
        connection.execute(
            """
            INSERT INTO agent_retry_logs (
                retry_id,
                task_id,
                agent_name,
                attempt_number,
                max_attempts,
                status,
                error_message,
                delay_seconds,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                retry_record["retry_id"],
                retry_record["task_id"],
                retry_record["agent_name"],
                retry_record["attempt_number"],
                retry_record["max_attempts"],
                retry_record["status"],
                retry_record["error_message"],
                retry_record["delay_seconds"],
                retry_record["created_at"],
            ),
        )

        connection.commit()

    finally:
        connection.close()

    return retry_record


def execute_with_retry(
    function: Callable[[], T],
    agent_name: str,
    task_id: str = "",
    max_retries: int = MAX_RETRIES,
    initial_delay: float = INITIAL_RETRY_DELAY,
    max_delay: float = MAX_RETRY_DELAY,
    should_retry: Optional[Callable[[Exception], bool]] = None,
) -> T:
    """
    Execute a function with bounded retries.

    max_retries means retries after the first attempt.

    Example:
        max_retries=3 permits at most four total attempts.
    """

    # Prevent invalid retry configuration.
    if max_retries < 0:
        raise ValueError("max_retries cannot be negative.")

    if initial_delay < 0 or max_delay < 0:
        raise ValueError("Retry delays cannot be negative.")

    # Use the default error classifier when none is supplied.
    retry_condition = should_retry or is_retryable_error

    # Calculate the maximum number of total attempts.
    max_attempts = max_retries + 1

    for attempt_number in range(1, max_attempts + 1):
        
        try:
            # Run the supplied agent operation.
            result = function()

            # Treat an explicitly failed agent result as an error.
            if (
                isinstance(result, dict)
                and result.get("status") == "failed"
            ):
                error_message = result.get(
                    "error",
                    f"{agent_name} reported failure.",
            )

                raise RuntimeError(str(error_message))

            # Record a successful attempt only after validation.
            record_retry_attempt(
                task_id=task_id,
                agent_name=agent_name,
                attempt_number=attempt_number,
                max_attempts=max_attempts,
                status="succeeded",
            )

            return result



        except Exception as error:
            # Stop if the error is permanent or no retries remain.
            retry_allowed = (
                attempt_number < max_attempts
                and retry_condition(error)
            )

            if not retry_allowed:
                record_retry_attempt(
                    task_id=task_id,
                    agent_name=agent_name,
                    attempt_number=attempt_number,
                    max_attempts=max_attempts,
                    status="failed",
                    error_message=(
                        f"{type(error).__name__}: {error}"
                    ),
                )

                # Preserve the original exception.
                raise

            # Exponential backoff: 1, 2, 4, 8 seconds, etc.
            delay_seconds = min(
                initial_delay * (2 ** (attempt_number - 1)),
                max_delay,
            )

            # Record the attempt and the planned retry delay.
            record_retry_attempt(
                task_id=task_id,
                agent_name=agent_name,
                attempt_number=attempt_number,
                max_attempts=max_attempts,
                status="retrying",
                error_message=(
                    f"{type(error).__name__}: {error}"
                ),
                delay_seconds=delay_seconds,
            )

            # Wait before attempting the operation again.
            time.sleep(delay_seconds)

    # The loop should always return or raise.
    raise RuntimeError(
        f"{agent_name} ended without a result."
    )


def get_retry_history(
    task_id: Optional[str] = None,
    limit: int = 100,
) -> Dict[str, Any]:
    """Retrieve retry records, optionally filtered by task."""

    safe_limit = max(1, min(limit, 500))

    connection = get_connection()

    try:
        if task_id:
            rows = connection.execute(
                """
                SELECT *
                FROM agent_retry_logs
                WHERE task_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (task_id, safe_limit),
            ).fetchall()

        else:
            rows = connection.execute(
                """
                SELECT *
                FROM agent_retry_logs
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (safe_limit,),
            ).fetchall()

        records = [dict(row) for row in rows]

        return {
            "task_id": task_id,
            "count": len(records),
            "retry_history": records,
        }

    finally:
        connection.close()


def get_retry_statistics() -> Dict[str, Any]:
    """Calculate overall retry statistics."""

    connection = get_connection()

    try:
        row = connection.execute(
            """
            SELECT
                COUNT(*) AS total_attempt_records,

                SUM(
                    CASE
                        WHEN status = 'retrying'
                        THEN 1 ELSE 0
                    END
                ) AS retry_events,

                SUM(
                    CASE
                        WHEN status = 'succeeded'
                        THEN 1 ELSE 0
                    END
                ) AS successful_attempts,

                SUM(
                    CASE
                        WHEN status = 'failed'
                        THEN 1 ELSE 0
                    END
                ) AS failed_attempts

            FROM agent_retry_logs
            """
        ).fetchone()

        return {
            "total_attempt_records": (
                row["total_attempt_records"] or 0
            ),
            "retry_events": row["retry_events"] or 0,
            "successful_attempts": (
                row["successful_attempts"] or 0
            ),
            "failed_attempts": row["failed_attempts"] or 0,
        }

    finally:
        connection.close()

