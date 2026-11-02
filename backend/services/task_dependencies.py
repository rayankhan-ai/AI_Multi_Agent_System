# ============================================================
#  - INTELLIGENT TASK DEPENDENCY MANAGEMENT
# File: backend/services/task_dependencies.py
# ============================================================

# SQLite is used to store and retrieve task dependencies.
import sqlite3

# Import the existing task database connection.
from backend.services.task_database import (
    get_connection,
    initialize_task_database,
)


# ============================================================
# STEP 1 - INITIALIZE DEPENDENCY STORAGE
# ============================================================

def initialize_task_dependencies():
    """
    Create a table for relationships between research tasks.

    Each dependency records which task must finish before
    another task is allowed to execute.
    """

    # Ensure the existing research task database is initialized.
    initialize_task_database()

    # Create the dependency table if it does not already exist.
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS task_dependencies (
                task_id TEXT NOT NULL,
                depends_on_task_id TEXT NOT NULL,

                PRIMARY KEY (
                    task_id,
                    depends_on_task_id
                ),

                CHECK (task_id != depends_on_task_id)
            )
            """
        )

        # Create an index to make dependency lookups faster.
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_task_dependencies_task_id
            ON task_dependencies(task_id)
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_task_dependencies_parent
            ON task_dependencies(depends_on_task_id)
            """
        )

    return {
        "success": True,
        "message": "Task dependency storage initialized successfully.",
    }


# ============================================================
# STEP 2 - VALIDATE TASK REFERENCES
# ============================================================

def validate_task_exists(task_id):
    """
    Check whether a research task exists in the database.
    """

    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT task_id
            FROM research_tasks
            WHERE task_id = ?
            """,
            (task_id,),
        ).fetchone()

    return row is not None


# ============================================================
# STEP 3 - CHECK WHETHER A DEPENDENCY WOULD CREATE A CYCLE
# ============================================================

def dependency_would_create_cycle(
    task_id,
    depends_on_task_id,
):
    """
    Determine whether adding a dependency would create a cycle.

    Example of an invalid cycle:

        Task A depends on Task B.
        Task B depends on Task A.

    A cycle would prevent the tasks from becoming ready.
    """

    # Start from the proposed prerequisite task.
    pending_tasks = [depends_on_task_id]

    # Track visited tasks to avoid repeatedly checking them.
    visited_tasks = set()

    with get_connection() as connection:

        while pending_tasks:

            current_task_id = pending_tasks.pop()

            # Reaching the original task means a cycle exists.
            if current_task_id == task_id:
                return True

            # Skip tasks already examined.
            if current_task_id in visited_tasks:
                continue

            visited_tasks.add(current_task_id)

            # Find tasks that the current task itself depends on.
            rows = connection.execute(
                """
                SELECT depends_on_task_id
                FROM task_dependencies
                WHERE task_id = ?
                """,
                (current_task_id,),
            ).fetchall()

            for row in rows:
                pending_tasks.append(
                    row["depends_on_task_id"]
                )

    return False


# ============================================================
# STEP 4 - ADD A TASK DEPENDENCY
# ============================================================

def add_task_dependency(
    task_id,
    depends_on_task_id,
):
    """
    Make one task depend on another task.

    The dependent task cannot become ready until its prerequisite
    has completed successfully.
    """

    # Ensure the dependency table exists.
    initialize_task_dependencies()

    # Prevent a task from depending on itself.
    if task_id == depends_on_task_id:
        return {
            "success": False,
            "message": "A task cannot depend on itself.",
        }

    # Confirm that the dependent task exists.
    if not validate_task_exists(task_id):
        return {
            "success": False,
            "message": f"Task '{task_id}' does not exist.",
        }

    # Confirm that the prerequisite task exists.
    if not validate_task_exists(depends_on_task_id):
        return {
            "success": False,
            "message": (
                f"Prerequisite task '{depends_on_task_id}' "
                "does not exist."
            ),
        }

    # Prevent circular task dependencies.
    if dependency_would_create_cycle(
        task_id,
        depends_on_task_id,
    ):
        return {
            "success": False,
            "message": (
                "This dependency would create a cycle. "
                "The dependency was not added."
            ),
        }

    try:
        # Store the dependency relationship.
        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO task_dependencies (
                    task_id,
                    depends_on_task_id
                )
                VALUES (?, ?)
                """,
                (
                    task_id,
                    depends_on_task_id,
                ),
            )

        return {
            "success": True,
            "message": "Task dependency added successfully.",
            "task_id": task_id,
            "depends_on_task_id": depends_on_task_id,
        }

    except sqlite3.IntegrityError:
        return {
            "success": False,
            "message": (
                "This dependency already exists or violates "
                "a database constraint."
            ),
        }


# ============================================================
# STEP 5 - GET A TASK'S DEPENDENCIES
# ============================================================

def get_task_dependencies(task_id):
    """
    Return the prerequisites configured for a research task.
    """

    # Verify that the requested task exists.
    if not validate_task_exists(task_id):
        return {
            "success": False,
            "message": f"Task '{task_id}' does not exist.",
        }

    # Read the task's prerequisite IDs and current statuses.
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                dependencies.depends_on_task_id,
                tasks.status
            FROM task_dependencies AS dependencies
            JOIN research_tasks AS tasks
                ON tasks.task_id =
                   dependencies.depends_on_task_id
            WHERE dependencies.task_id = ?
            ORDER BY dependencies.depends_on_task_id
            """,
            (task_id,),
        ).fetchall()

    # Convert database records into API-friendly dictionaries.
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
# STEP 6 - CHECK WHETHER A TASK IS READY
# ============================================================

def check_task_dependencies(task_id):
    """
    Determine whether a task's prerequisites are satisfied.

    A task is ready only when all its prerequisite tasks
    have status 'completed'.
    """

    # Load the prerequisite tasks.
    dependency_result = get_task_dependencies(task_id)

    # Return the error if the requested task does not exist.
    if not dependency_result["success"]:
        return dependency_result

    dependencies = dependency_result["dependencies"]

    # Identify prerequisites that have not completed.
    incomplete_dependencies = [
        dependency
        for dependency in dependencies
        if dependency["status"] != "completed"
    ]

    # The task is ready when every prerequisite has completed.
    ready = len(incomplete_dependencies) == 0

    return {
        "success": True,
        "task_id": task_id,
        "ready": ready,
        "total_dependencies": len(dependencies),
        "incomplete_dependencies": incomplete_dependencies,
        "message": (
            "All dependencies are satisfied."
            if ready
            else "One or more prerequisite tasks are incomplete."
        ),
    }


# ============================================================
# STEP 7 - FIND TASKS THAT ARE READY TO EXECUTE
# ============================================================

def get_ready_tasks(limit=100):
    """
    Return pending research tasks whose dependencies are satisfied.

    Tasks retain the existing priority-based scheduling order.
    """

    # Validate the result limit.
    if limit < 1 or limit > 500:
        raise ValueError("Limit must be between 1 and 500.")

    # Ensure the dependency table exists.
    initialize_task_dependencies()

    # Find pending tasks without unfinished prerequisites.
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

    # Convert the database results into dictionaries.
    ready_tasks = [
        dict(row)
        for row in rows
    ]

    return {
        "success": True,
        "total_ready_tasks": len(ready_tasks),
        "tasks": ready_tasks,
    }
    
# ============================================================
# - WORKFLOW OVERVIEW SERVICE
# ============================================================

def get_workflow_overview():
    """
    Return an overview of research tasks and their dependencies.

    This function provides the information needed to monitor
    the workflow and build a future frontend dashboard.
    """

    # Ensure that the dependency database tables exist.
    initialize_task_dependencies()

    # Open a connection to the existing SQLite database.
    with get_connection() as connection:

        # Retrieve task information without including large
        # research results or complete report contents.
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

        # Retrieve every dependency and its prerequisite status.
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
                dependencies.task_id ASC,
                dependencies.depends_on_task_id ASC
        """).fetchall()

    # Create a dictionary to group dependencies by task ID.
    dependencies_by_task = {}

    # Process each dependency returned by the database.
    for row in dependency_rows:

        # Identify the task that depends on another task.
        task_id = row["task_id"]

        # Create its dependency list if this is the first entry.
        if task_id not in dependencies_by_task:
            dependencies_by_task[task_id] = []

        # Store the prerequisite ID and its current status.
        dependencies_by_task[task_id].append({
            "task_id": row["depends_on_task_id"],
            "status": row["prerequisite_status"],
        })

    # Prepare the final list of workflow tasks.
    workflow_tasks = []

    # Count tasks by status for the workflow summary.
    status_counts = {}

    # Count tasks that are currently eligible to execute.
    total_ready_tasks = 0

    # Process every task.
    for row in task_rows:

        # Convert the database row into a regular dictionary.
        task = dict(row)

        # Retrieve this task's prerequisites.
        dependencies = dependencies_by_task.get(
            task["task_id"],
            [],
        )

        # Find prerequisites that have not completed.
        incomplete_dependencies = [
            dependency
            for dependency in dependencies
            if dependency["status"] != "completed"
        ]

        # A task is ready when all prerequisites are complete.
        dependencies_satisfied = (
            len(incomplete_dependencies) == 0
        )

        # Only pending tasks can be selected for execution.
        ready_to_execute = (
            task["status"] == "pending"
            and dependencies_satisfied
        )

        # Add the task to the ready-task count when eligible.
        if ready_to_execute:
            total_ready_tasks += 1

        # Update the count for the task's current status.
        task_status = task["status"]

        status_counts[task_status] = (
            status_counts.get(task_status, 0) + 1
        )

        # Add dependency and readiness information.
        task["dependencies"] = dependencies
        task["dependencies_satisfied"] = (
            dependencies_satisfied
        )
        task["incomplete_dependencies"] = (
            incomplete_dependencies
        )
        task["ready_to_execute"] = ready_to_execute

        # Add this task to the workflow overview.
        workflow_tasks.append(task)

    # Return a structured workflow overview.
    return {
        "success": True,
        "workflow_type": "priority_and_dependency_based",
        "total_tasks": len(workflow_tasks),
        "total_ready_tasks": total_ready_tasks,
        "status_counts": status_counts,
        "tasks": workflow_tasks,
    }
    
# ============================================================
#  - WORKFLOW EXECUTION STATISTICS
# ============================================================

def get_workflow_statistics():
    """
    Calculate workflow statistics from the research task database.

    ```
    The function reports task statuses, priorities, dependency
    readiness, and overall completion percentage.
    """

    # Retrieve the complete workflow overview.
    overview = get_workflow_overview()

    # Extract all tasks from the overview.
    tasks = overview["tasks"]

    # Count the total number of tasks.
    total_tasks = len(tasks)

    # Initialize task-status counters.
    status_counts = {
        "pending": 0,
        "running": 0,
        "completed": 0,
        "failed": 0,
    }

    # Initialize priority counters.
    priority_counts = {
        "critical": 0,
        "high": 0,
        "normal": 0,
        "low": 0,
    }

    # Count tasks that are blocked by dependencies.
    blocked_tasks = 0

    # Examine each task in the workflow.
    for task in tasks:

    # Count the task's current status.
        status = task.get("status", "pending")

    if status in status_counts:
        status_counts[status] += 1

    # Count the task's priority.
    priority = task.get("priority", "normal")

    if priority in priority_counts:
        priority_counts[priority] += 1

    # A pending task with incomplete prerequisites is blocked.
    if (
        status == "pending"
        and not task.get("dependencies_satisfied", True)
    ):
        blocked_tasks += 1

    # Calculate completion percentage safely.
    completion_percentage = (
        round(
            (status_counts["completed"] / total_tasks) * 100,
            2,
    )
    if total_tasks > 0
    else 0.0
    )

    # Return the workflow statistics.
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
#  - WORKFLOW HEALTH MONITORING
# ============================================================

def get_workflow_health():
    """
    Inspect workflow tasks and report potential problems.

    ```
    This function only reads workflow information.
    It does not modify or execute research tasks.
    """

    # Retrieve the current workflow overview.
    overview = get_workflow_overview()

    # Extract all workflow tasks.
    tasks = overview["tasks"]

    # Prepare lists for different workflow conditions.
    failed_tasks = []
    blocked_tasks = []
    running_tasks = []
    ready_tasks = []

    # Examine every task in the workflow.
    for task in tasks:

        # Collect tasks that have failed.
        if task.get("status") == "failed":
            failed_tasks.append({
                "task_id": task["task_id"],
                "research_question": task["research_question"],
                "error": task.get("error"),
            })

        # Collect pending tasks waiting for prerequisites.
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

        # Collect tasks currently executing.
        if task.get("status") == "running":
            running_tasks.append({
                "task_id": task["task_id"],
                "research_question": task["research_question"],
            })

        # Collect pending tasks eligible for execution.
        if task.get("ready_to_execute"):
            ready_tasks.append({
                "task_id": task["task_id"],
                "research_question": task["research_question"],
                "priority": task.get("priority", "normal"),
            })

    # Determine whether the workflow has reported problems.
    has_failures = len(failed_tasks) > 0
    has_blocked_tasks = len(blocked_tasks) > 0

    # Report an overall health classification.
    if has_failures:
        health_status = "attention_required"
    elif has_blocked_tasks:
        health_status = "blocked_tasks_present"
    else:
        health_status = "healthy"

    # Return the health report.
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
#- PAGINATED AUDIT HISTORY SERVICE
# ============================================================

def get_workflow_audit_history(
    limit=100,
    status=None,
    priority=None,
    search=None,
    page=1,
        ):
    """
    Retrieve filtered audit records using pagination.

    ```
    Page 1 returns the first group of matching records.
    Page 2 returns the next group, and so on.
    """

    # Validate the number of records requested per page.
    if limit < 1 or limit > 100:
        raise ValueError(
            "Limit must be between 1 and 100."
        )

    # Validate the requested page number.
    if page < 1:
        raise ValueError(
            "Page must be greater than or equal to 1."
        )

    # Validate task statuses.
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

    # Validate task priorities.
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

    # Build the SQL filter conditions.
    conditions = []
    filter_parameters = []

    if status is not None:
        conditions.append("status = ?")
        filter_parameters.append(status)

    if priority is not None:
        conditions.append("priority = ?")
        filter_parameters.append(priority)

    if search is not None and search.strip():
        conditions.append("research_question LIKE ?")
        filter_parameters.append(f"%{search.strip()}%")

    # Prepare the reusable SQL filter.
    where_clause = ""

    if conditions:
        where_clause = " WHERE " + " AND ".join(conditions)

    # Initialize the database before querying.
    initialize_task_dependencies()

    # Calculate the number of matching records and retrieve
    # the requested page using the same database connection.
    with get_connection() as connection:

        # Count every matching record, not just this page.
        count_row = connection.execute(
            "SELECT COUNT(*) AS total FROM research_tasks"
            + where_clause,
            tuple(filter_parameters),
        ).fetchone()

        total_records = count_row["total"]

        # Calculate how many pages are available.
        total_pages = (
            (total_records + limit - 1) // limit
        )

        # Calculate how many matching records to skip.
        offset = (page - 1) * limit

        # Retrieve only the records needed for this page.
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
            LIMIT ? OFFSET ?
        """

        rows = connection.execute(
            query,
            tuple(filter_parameters) + (limit, offset),
        ).fetchall()

    # Prepare the page's history records.
    history = []

    for row in rows:
        task = dict(row)
        task["duration_seconds"] = None

        started_at = task.get("started_at")
        finished_at = task.get("finished_at")

        # Calculate duration when both timestamps are available.
        if started_at and finished_at:
            try:
                from datetime import datetime

                start_time = datetime.fromisoformat(
                    started_at
                )
                finish_time = datetime.fromisoformat(
                    finished_at
                )

                task["duration_seconds"] = round(
                    max(
                        (finish_time - start_time).total_seconds(),
                        0,
                    ),
                    2,
                )

            except (ValueError, TypeError):
                # Preserve the record if a timestamp is invalid.
                task["duration_seconds"] = None

        history.append(task)

    # Return pagination metadata and the requested records.
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

