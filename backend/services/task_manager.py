# Generate unique IDs for research tasks.
from uuid import uuid4

# Generate UTC timestamps.
from datetime import datetime, timezone

# Provide type hints.
from typing import Any, Dict, Optional

# Protect task updates against concurrent operations.
import asyncio

# Import database functions.
from backend.services.task_database import (
    initialize_task_database,
    save_task,
    get_saved_task,
    get_saved_tasks,
    recover_interrupted_tasks,
)


# Lock concurrent task-manager operations.
_TASK_LOCK = asyncio.Lock()

# Track task IDs currently executing in this process.
_ACTIVE_TASKS = set()


def current_timestamp() -> str:
    """Return the current UTC time in ISO format."""

    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def initialize_tasks():
    """Initialize storage and recover interrupted tasks."""

    initialize_task_database()

    # Tasks still running from a previous process cannot continue.
    recovered_count = recover_interrupted_tasks()

    return {
        "success": True,
        "recovered_tasks": recovered_count,
    }


async def create_task(
    research_question: str,
) -> Dict[str, Any]:
    """Create and persist a new research task."""

    initialize_task_database()

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

    async with _TASK_LOCK:
        save_task(task)

    return task.copy()


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
        task = get_saved_task(task_id)

        if task is None:
            return None

        task["status"] = status

        if status == "running" and task.get("started_at") is None:
            task["started_at"] = current_timestamp()

        if status in {"completed", "failed"}:
            task["finished_at"] = current_timestamp()

        # Clear a previous error when the task starts again.
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

        save_task(task)

        return task.copy()


async def get_task(task_id: str):
    """Retrieve a task by ID."""

    async with _TASK_LOCK:
        return get_saved_task(task_id)


async def get_all_tasks():
    """Retrieve all stored tasks."""

    async with _TASK_LOCK:
        tasks = get_saved_tasks()

    return {
        "success": True,
        "total_tasks": len(tasks),
        "tasks": tasks,
    }


async def reserve_task_for_execution(task_id: str):
    """
    Reserve a pending or failed task for execution.

    A task cannot be executed twice simultaneously in this process.
    """

    async with _TASK_LOCK:

        if task_id in _ACTIVE_TASKS:
            return {
                "success": False,
                "message": "This task is already executing.",
            }

        task = get_saved_task(task_id)

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

        # Reserve the task before releasing the lock.
        _ACTIVE_TASKS.add(task_id)

        # Increase retry_count only when retrying a failed task.
        if task["status"] == "failed":
            task["retry_count"] = task.get("retry_count", 0) + 1

        task["status"] = "running"
        task["started_at"] = current_timestamp()
        task["finished_at"] = None
        task["error"] = None

        save_task(task)

        return {
            "success": True,
            "task": task.copy(),
        }


async def release_task_execution(task_id: str):
    """Release the execution reservation."""

    async with _TASK_LOCK:
        _ACTIVE_TASKS.discard(task_id)
