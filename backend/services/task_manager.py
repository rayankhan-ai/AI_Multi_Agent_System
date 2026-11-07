# Generate unique IDs for research tasks.
from uuid import uuid4

# Generate UTC timestamps.
from datetime import datetime, timezone

# Provide type hints.
from typing import Any, Dict, Optional

# Support asynchronous execution and background database operations.
import asyncio

# Import database functions.
from backend.services.task_database import (
    initialize_task_database,
    save_task,
    get_saved_task,
    get_saved_tasks,
    recover_interrupted_tasks,
)


# ============================================================
# TASK EXECUTION MANAGEMENT
# ============================================================

# Protect task-manager operations against concurrent operations.
_TASK_LOCK = asyncio.Lock()

# Track task IDs currently executing in this process.
_ACTIVE_TASKS = set()


# ============================================================
# TIMESTAMP MANAGEMENT
# ============================================================

def current_timestamp() -> str:
    """Return the current UTC time in ISO format."""

    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ============================================================
# INITIALIZE TASK MANAGEMENT
# ============================================================

def initialize_tasks():
    """Initialize storage and recover interrupted tasks."""

    initialize_task_database()

    # Recover tasks interrupted by a previous process shutdown.
    recovered_count = recover_interrupted_tasks()

    return {
        "success": True,
        "recovered_tasks": recovered_count,
    }


# ============================================================
# CREATE TASK
# ============================================================

async def create_task(
    research_question: str,
) -> Dict[str, Any]:
    """Create and persist a new research task."""

    # Run database initialization outside the event loop.
    await asyncio.to_thread(initialize_task_database)

    task = {
        "task_id": str(uuid4()),
        "research_question": research_question.strip(),
        "status": "pending",
        "created_at": current_timestamp(),
        "started_at": None,
        "finished_at": None,
        "error": None,
        "report_filename": None,
        "quality_score": None,
        "result": None,
        "retry_count": 0,
    }

    # Keep task creation synchronized.
    async with _TASK_LOCK:

        # Execute PostgreSQL operations in a worker thread.
        await asyncio.to_thread(save_task, task)

    return task.copy()


# ============================================================
# UPDATE TASK
# ============================================================

async def update_task(
    task_id: str,
    status: str,
    error: Optional[str] = None,
    report_filename: Optional[str] = None,
    quality_score: Optional[int] = None,
    result: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Update a task's status and available results."""

    allowed_statuses = {
        "pending",
        "running",
        "completed",
        "failed",
    }

    if status not in allowed_statuses:
        raise ValueError(f"Invalid task status: {status}")

    async with _TASK_LOCK:

        # Retrieve the task without blocking the event loop.
        task = await asyncio.to_thread(
            get_saved_task,
            task_id,
        )

        if task is None:
            return None

        task["status"] = status

        if status == "running" and task.get("started_at") is None:
            task["started_at"] = current_timestamp()

        if status in {"completed", "failed"}:
            task["finished_at"] = current_timestamp()

        # Clear a previous error when execution starts again.
        if status == "running":
            task["error"] = None

        if error is not None:
            task["error"] = error

        if report_filename is not None:
            task["report_filename"] = report_filename

        if quality_score is not None:
            task["quality_score"] = quality_score

        if result is not None:
            task["result"] = result

        # Persist the updated task outside the event loop.
        await asyncio.to_thread(
            save_task,
            task,
        )

        return task.copy()


# ============================================================
# GET TASK
# ============================================================

async def get_task(task_id: str):
    """Retrieve a task by ID."""

    async with _TASK_LOCK:

        return await asyncio.to_thread(
            get_saved_task,
            task_id,
        )


# ============================================================
# GET ALL TASKS
# ============================================================

async def get_all_tasks():
    """Retrieve all stored tasks."""

    async with _TASK_LOCK:

        tasks = await asyncio.to_thread(
            get_saved_tasks,
        )

    return {
        "success": True,
        "total_tasks": len(tasks),
        "tasks": tasks,
    }


# ============================================================
# RESERVE TASK FOR EXECUTION
# ============================================================

async def reserve_task_for_execution(task_id: str):
    """
    Reserve a pending or failed task for execution.

    Prevent simultaneous execution of the same task
    within this backend process.
    """

    async with _TASK_LOCK:

        if task_id in _ACTIVE_TASKS:
            return {
                "success": False,
                "message": "This task is already executing.",
            }

        # Retrieve the task without blocking the event loop.
        task = await asyncio.to_thread(
            get_saved_task,
            task_id,
        )

        if task is None:
            return {
                "success": False,
                "message": "Research task not found.",
            }

        if task["status"] not in {"pending", "failed"}:
            return {
                "success": False,
                "message": (
                    "Only pending or failed tasks can be executed. "
                    f"Current status: {task['status']}"
                ),
            }

        # Increase retry_count only when retrying a failed task.
        if task["status"] == "failed":
            task["retry_count"] = task.get("retry_count", 0) + 1

        task["status"] = "running"
        task["started_at"] = current_timestamp()
        task["finished_at"] = None
        task["error"] = None

        # Persist the reservation before marking it active.
        # If the database operation fails, the task is not
        # incorrectly left in the active-task set.
        await asyncio.to_thread(
            save_task,
            task,
        )

        # Reserve the task while still holding the lock.
        _ACTIVE_TASKS.add(task_id)

        return {
            "success": True,
            "task": task.copy(),
        }


# ============================================================
# RELEASE TASK EXECUTION
# ============================================================

async def release_task_execution(task_id: str):
    """Release the execution reservation."""

    async with _TASK_LOCK:

        _ACTIVE_TASKS.discard(task_id)