# ============================================================
# POSTGRESQL TASK DEPENDENCY MANAGEMENT
# ============================================================

from datetime import datetime
import threading

import psycopg

from backend.services.database import get_connection
from backend.services.task_database import initialize_task_database
from backend.services.task_priority import PRIORITY_SCORES

# Track whether dependency support has been initialized.
_DEPENDENCIES_INITIALIZED = False

# Prevent multiple threads from initializing dependencies simultaneously.
_DEPENDENCIES_INITIALIZATION_LOCK = threading.Lock()

# Store the initialization result.
_DEPENDENCIES_INITIALIZATION_RESULT = None

# ============================================================
# STEP 1 - INITIALIZE DEPENDENCY SUPPORT
# ============================================================

def initialize_task_dependencies():
    """Initialize PostgreSQL task dependency support only once."""

    global _DEPENDENCIES_INITIALIZED
    global _DEPENDENCIES_INITIALIZATION_RESULT

    # Return the cached result if initialization already succeeded.
    if _DEPENDENCIES_INITIALIZED:
        result = _DEPENDENCIES_INITIALIZATION_RESULT.copy()
        result["cached"] = True
        return result

    # Ensure only one thread initializes dependency support.
    with _DEPENDENCIES_INITIALIZATION_LOCK:

        # Check again after acquiring the lock.
        if _DEPENDENCIES_INITIALIZED:
            result = _DEPENDENCIES_INITIALIZATION_RESULT.copy()
            result["cached"] = True
            return result

        # Ensure the central database schema exists.
        initialize_task_database()

        # Create dependency support only during initialization.
        with get_connection() as connection:

            connection.execute("""
                CREATE TABLE IF NOT EXISTS task_dependencies (
                    task_id TEXT NOT NULL
                        REFERENCES research_tasks(task_id)
                        ON DELETE CASCADE,

                    depends_on_task_id TEXT NOT NULL
                        REFERENCES research_tasks(task_id)
                        ON DELETE CASCADE,

                    PRIMARY KEY (task_id, depends_on_task_id),

                    CHECK (task_id <> depends_on_task_id)
                )
            """)

            connection.execute("""
                CREATE INDEX IF NOT EXISTS idx_dependencies_task
                ON task_dependencies(task_id)
            """)

            connection.execute("""
                CREATE INDEX IF NOT EXISTS idx_dependencies_prerequisite
                ON task_dependencies(depends_on_task_id)
            """)

        # Store the successful initialization result.
        _DEPENDENCIES_INITIALIZATION_RESULT = {
            "success": True,
            "message": (
                "PostgreSQL task dependency support initialized."
            ),
        }

        _DEPENDENCIES_INITIALIZED = True

        result = _DEPENDENCIES_INITIALIZATION_RESULT.copy()
        result["cached"] = False

        return result


# ============================================================
# STEP 2 - VALIDATE TASK EXISTENCE
# ============================================================

def validate_task_exists(task_id):
    """Check whether a research task exists."""

    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT task_id
            FROM research_tasks
            WHERE task_id = %s
            """,
            (task_id,),
        ).fetchone()

    return row is not None


# ============================================================
# STEP 3 - DETECT DEPENDENCY CYCLES
# ============================================================

def dependency_would_create_cycle(task_id, depends_on_task_id):
    """Check whether adding a dependency would create a cycle."""

    visited = set()
    stack = [depends_on_task_id]

    with get_connection() as connection:

        while stack:

            current_task = stack.pop()

            if current_task == task_id:
                return True

            if current_task in visited:
                continue

            visited.add(current_task)

            rows = connection.execute(
                """
                SELECT depends_on_task_id
                FROM task_dependencies
                WHERE task_id = %s
                """,
                (current_task,),
            ).fetchall()

            for row in rows:
                stack.append(row["depends_on_task_id"])

    return False


# ============================================================
# STEP 4 - ADD A TASK DEPENDENCY
# ============================================================

def add_task_dependency(task_id, depends_on_task_id):
    """Add a prerequisite relationship between two tasks."""

    initialize_task_dependencies()

    if task_id == depends_on_task_id:
        return {
            "success": False,
            "message": "A task cannot depend on itself.",
        }

    if not validate_task_exists(task_id):
        return {
            "success": False,
            "message": f"Task '{task_id}' does not exist.",
        }

    if not validate_task_exists(depends_on_task_id):
        return {
            "success": False,
            "message": (
                f"Prerequisite task '{depends_on_task_id}' "
                "does not exist."
            ),
        }

    if dependency_would_create_cycle(task_id, depends_on_task_id):
        return {
            "success": False,
            "message": (
                "This dependency would create a cycle. "
                "The dependency was not added."
            ),
        }

    try:
        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO task_dependencies (
                    task_id,
                    depends_on_task_id
                )
                VALUES (%s, %s)
                """,
                (task_id, depends_on_task_id),
            )

        return {
            "success": True,
            "message": "Task dependency added successfully.",
            "task_id": task_id,
            "depends_on_task_id": depends_on_task_id,
        }

    except psycopg.IntegrityError:
        return {
            "success": False,
            "message": (
                "This dependency already exists or violates "
                "a database constraint."
            ),
        }


# ============================================================
# STEP 5 - GET TASK DEPENDENCIES
# ============================================================

def get_task_dependencies(task_id):
    """Return the prerequisites configured for a task."""

    if not validate_task_exists(task_id):
        return {
            "success": False,
            "message": f"Task '{task_id}' does not exist.",
        }

    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                dependencies.depends_on_task_id,
                tasks.status
            FROM task_dependencies AS dependencies
            JOIN research_tasks AS tasks
                ON tasks.task_id = dependencies.depends_on_task_id
            WHERE dependencies.task_id = %s
            ORDER BY dependencies.depends_on_task_id
            """,
            (task_id,),
        ).fetchall()

    dependencies = [
        {
            "task_id": row["depends_on_task_id"],
            "status": row["status"],
        }
        for row in rows
    ]

    return {
        "success": True,
        "task_id": task_id,
        "total_dependencies": len(dependencies),
        "dependencies": dependencies,
    }


# ============================================================
# STEP 6 - CHECK TASK READINESS
# ============================================================

def check_task_dependencies(task_id):
    """Check whether all prerequisite tasks are completed."""

    result = get_task_dependencies(task_id)

    if not result["success"]:
        return result

    dependencies = result["dependencies"]

    incomplete = [
        dependency
        for dependency in dependencies
        if dependency["status"] != "completed"
    ]

    ready = len(incomplete) == 0

    return {
        "success": True,
        "task_id": task_id,
        "ready": ready,
        "total_dependencies": len(dependencies),
        "incomplete_dependencies": incomplete,
        "message": (
            "All dependencies are satisfied."
            if ready
            else "One or more prerequisite tasks are incomplete."
        ),
    }


# ============================================================
# STEP 7 - GET READY TASKS
# ============================================================

def get_ready_tasks(limit=100):
    """Return pending tasks whose prerequisites are completed."""

    if limit < 1 or limit > 500:
        raise ValueError("Limit must be between 1 and 500.")

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
            LIMIT %s
            """,
            (limit,),
        ).fetchall()

    tasks = [dict(row) for row in rows]

    return {
        "success": True,
        "total_ready_tasks": len(tasks),
        "tasks": tasks,
    }


# ============================================================
# STEP 8 - WORKFLOW OVERVIEW
# ============================================================

def get_workflow_overview():
    """Return all tasks and their dependency information."""

    initialize_task_dependencies()

    with get_connection() as connection:

        task_rows = connection.execute("""
            SELECT
                task_id,
                research_question,
                status,
                priority,
                created_at,
                started_at,
                finished_at,
                error,
                retry_count
            FROM research_tasks
            ORDER BY created_at ASC, task_id ASC
        """).fetchall()

        dependency_rows = connection.execute("""
            SELECT
                dependencies.task_id,
                dependencies.depends_on_task_id,
                prerequisite.status AS prerequisite_status
            FROM task_dependencies AS dependencies
            JOIN research_tasks AS prerequisite
                ON prerequisite.task_id =
                   dependencies.depends_on_task_id
            ORDER BY
                dependencies.task_id,
                dependencies.depends_on_task_id
        """).fetchall()

    dependencies_by_task = {}

    for row in dependency_rows:
        task_id = row["task_id"]

        if task_id not in dependencies_by_task:
            dependencies_by_task[task_id] = []

        dependencies_by_task[task_id].append({
            "task_id": row["depends_on_task_id"],
            "status": row["prerequisite_status"],
        })

    workflow_tasks = []
    status_counts = {}
    total_ready_tasks = 0

    for row in task_rows:

        task = dict(row)

        dependencies = dependencies_by_task.get(
            task["task_id"],
            [],
        )

        incomplete = [
            dependency
            for dependency in dependencies
            if dependency["status"] != "completed"
        ]

        dependencies_satisfied = len(incomplete) == 0

        ready = (
            task["status"] == "pending"
            and dependencies_satisfied
        )

        if ready:
            total_ready_tasks += 1

        status = task["status"]

        status_counts[status] = (
            status_counts.get(status, 0) + 1
        )

        task["dependencies"] = dependencies
        task["dependencies_satisfied"] = dependencies_satisfied
        task["incomplete_dependencies"] = incomplete
        task["ready_to_execute"] = ready

        workflow_tasks.append(task)

    return {
        "success": True,
        "workflow_type": "priority_and_dependency_based",
        "total_tasks": len(workflow_tasks),
        "total_ready_tasks": total_ready_tasks,
        "status_counts": status_counts,
        "tasks": workflow_tasks,
    }


# ============================================================
# STEP 9 - WORKFLOW STATISTICS
# ============================================================

def get_workflow_statistics():
    """Calculate task, priority, and dependency statistics."""

    overview = get_workflow_overview()
    tasks = overview["tasks"]

    total_tasks = len(tasks)

    status_counts = {
        "pending": 0,
        "running": 0,
        "completed": 0,
        "failed": 0,
    }

    priority_counts = {
        "critical": 0,
        "high": 0,
        "normal": 0,
        "low": 0,
    }

    blocked_tasks = 0

    for task in tasks:

        status = task.get("status", "pending")

        if status in status_counts:
            status_counts[status] += 1

        priority = task.get("priority", "normal")

        if priority in priority_counts:
            priority_counts[priority] += 1

        if (
            status == "pending"
            and not task.get("dependencies_satisfied", True)
        ):
            blocked_tasks += 1

    completion_percentage = (
        round(
            status_counts["completed"] / total_tasks * 100,
            2,
        )
        if total_tasks > 0
        else 0.0
    )

    return {
        "success": True,
        "total_tasks": total_tasks,
        "status_counts": status_counts,
        "priority_counts": priority_counts,
        "total_ready_tasks": overview["total_ready_tasks"],
        "blocked_tasks": blocked_tasks,
        "completion_percentage": completion_percentage,
    }


# ============================================================
# STEP 10 - WORKFLOW HEALTH
# ============================================================

def get_workflow_health():
    """Identify failed, blocked, running, and ready tasks."""

    overview = get_workflow_overview()
    tasks = overview["tasks"]

    failed_tasks = []
    blocked_tasks = []
    running_tasks = []
    ready_tasks = []

    for task in tasks:

        if task.get("status") == "failed":
            failed_tasks.append({
                "task_id": task["task_id"],
                "research_question": task["research_question"],
                "error": task.get("error"),
            })

        if (
            task.get("status") == "pending"
            and not task.get("dependencies_satisfied", True)
        ):
            blocked_tasks.append({
                "task_id": task["task_id"],
                "research_question": task["research_question"],
                "incomplete_dependencies": task[
                    "incomplete_dependencies"
                ],
            })

        if task.get("status") == "running":
            running_tasks.append({
                "task_id": task["task_id"],
                "research_question": task["research_question"],
            })

        if task.get("ready_to_execute"):
            ready_tasks.append({
                "task_id": task["task_id"],
                "research_question": task["research_question"],
                "priority": task.get("priority", "normal"),
            })

    if failed_tasks:
        health_status = "attention_required"
    elif blocked_tasks:
        health_status = "blocked_tasks_present"
    else:
        health_status = "healthy"

    return {
        "success": True,
        "health_status": health_status,
        "summary": {
            "total_tasks": len(tasks),
            "failed_tasks": len(failed_tasks),
            "blocked_tasks": len(blocked_tasks),
            "running_tasks": len(running_tasks),
            "ready_tasks": len(ready_tasks),
        },
        "issues": {
            "failed_tasks": failed_tasks,
            "blocked_tasks": blocked_tasks,
        },
        "activity": {
            "running_tasks": running_tasks,
            "ready_tasks": ready_tasks,
        },
    }


# ============================================================
# STEP 11 - PAGINATED WORKFLOW AUDIT HISTORY
# ============================================================

def get_workflow_audit_history(
    limit=100,
    status=None,
    priority=None,
    search=None,
    page=1,
):
    """Retrieve filtered and paginated task history."""

    if limit < 1 or limit > 100:
        raise ValueError("Limit must be between 1 and 100.")

    if page < 1:
        raise ValueError(
            "Page must be greater than or equal to 1."
        )

    allowed_statuses = {
        "pending",
        "running",
        "completed",
        "failed",
    }

    if status is not None and status not in allowed_statuses:
        raise ValueError(
            "Status must be pending, running, completed, or failed."
        )

    allowed_priorities = {
        "critical",
        "high",
        "normal",
        "low",
    }

    if priority is not None and priority not in allowed_priorities:
        raise ValueError(
            "Priority must be critical, high, normal, or low."
        )

    conditions = []
    parameters = []

    if status is not None:
        conditions.append("status = %s")
        parameters.append(status)

    if priority is not None:
        conditions.append("priority = %s")
        parameters.append(priority)

    if search is not None and search.strip():
        conditions.append("research_question ILIKE %s")
        parameters.append(f"%{search.strip()}%")

    where_clause = ""

    if conditions:
        where_clause = " WHERE " + " AND ".join(conditions)

    initialize_task_dependencies()

    with get_connection() as connection:

        count_row = connection.execute(
            """
            SELECT COUNT(*) AS total
            FROM research_tasks
            """ + where_clause,
            tuple(parameters),
        ).fetchone()

        total_records = count_row["total"]

        total_pages = (
            (total_records + limit - 1) // limit
        )

        offset = (page - 1) * limit

        query = """
            SELECT
                task_id,
                research_question,
                status,
                priority,
                created_at,
                started_at,
                finished_at,
                error,
                retry_count
            FROM research_tasks
        """ + where_clause + """
            ORDER BY created_at DESC, task_id DESC
            LIMIT %s OFFSET %s
        """

        rows = connection.execute(
            query,
            tuple(parameters) + (limit, offset),
        ).fetchall()

    history = []

    for row in rows:

        task = dict(row)
        task["duration_seconds"] = None

        started_at = task.get("started_at")
        finished_at = task.get("finished_at")

        if started_at and finished_at:
            try:

                if isinstance(started_at, str):
                    started_at = datetime.fromisoformat(started_at)

                if isinstance(finished_at, str):
                    finished_at = datetime.fromisoformat(finished_at)

                task["duration_seconds"] = round(
                    max(
                        (finished_at - started_at).total_seconds(),
                        0,
                    ),
                    2,
                )

            except (ValueError, TypeError):
                task["duration_seconds"] = None

        history.append(task)

    return {
        "success": True,
        "total_records": total_records,
        "limit": limit,
        "page": page,
        "total_pages": total_pages,
        "has_next_page": page < total_pages,
        "has_previous_page": page > 1 and total_pages > 0,
        "filters": {
            "status": status,
            "priority": priority,
            "search": search,
        },
        "history": history,
    }