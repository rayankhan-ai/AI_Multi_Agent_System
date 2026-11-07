# Import FastAPI to create our backend application.
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import BaseModel to define structured API responses.
from pydantic import BaseModel

# Import os to read configuration from environment variables.
import os
import asyncio

# Import the functions used to retrieve research history.
from backend.services.research_history import (
    get_research_history,
    get_research_by_id,
)

from fastapi.responses import Response

# ============================================================
# REPORT RETRIEVAL IMPORTS
# ============================================================

from backend.services.report_retrieval import (
    list_research_reports,
    get_research_report,
)

from fastapi import HTTPException
from pydantic import Field


# FastAPI runs the research job in the background.
from fastapi import BackgroundTasks

# Import the existing research workflow.
from backend.graph.workflow import run_research

# Import task management functions.
from backend.services.task_manager import (
    create_task,
    update_task,
    get_task,
    get_all_tasks,
    initialize_tasks,
    reserve_task_for_execution,
    release_task_execution,
)

from backend.services.agent_monitor import (
    initialize_agent_logs,
    get_agent_logs,
    get_recent_agent_logs,
)

#  Import agent performance analytics functions.
from backend.services.agent_analytics import (
    get_agent_performance_analytics,
    get_task_execution_analytics,
)

#  Import workflow tracing functions.
from backend.services.workflow_tracer import (
    initialize_workflow_tracing,
    start_workflow_trace,
    add_workflow_trace_event,
    finish_workflow_trace,
    get_workflow_trace,
    get_task_workflow_traces,
)

# Unified system monitoring.
from backend.services.system_monitor import (
    get_system_overview,
    get_recent_system_activity,
    get_task_diagnostics,
)

#  Agent retry management.
from backend.services.retry_manager import (
    initialize_retry_database,
    get_retry_history,
    get_retry_statistics,
)

# ============================================================
# TASK PRIORITY MANAGEMENT
# ============================================================

from backend.services.task_priority import (
    initialize_priority_support,
    update_task_priority,
    get_task_priority,
    get_tasks_by_priority,
    get_priority_statistics,
)

from backend.services.task_scheduler import (
initialize_task_scheduler,
async_get_next_scheduled_task,
async_get_scheduled_task_queue,
async_get_scheduler_status,
)

from backend.services.task_dependencies import (
    initialize_task_dependencies,
    add_task_dependency,
    get_task_dependencies,
    check_task_dependencies,
    get_ready_tasks,
    get_workflow_overview,
    get_workflow_statistics,
    get_workflow_health,
    get_workflow_audit_history,
)

# Central PostgreSQL database initialization.
from backend.services.database import initialize_database

import csv
import io

from fastapi.responses import StreamingResponse

# Import load_dotenv to load variables from the local .env file.
from dotenv import load_dotenv


# Load environment variables from the project root.
load_dotenv()


# Create the FastAPI application.
app = FastAPI(
    title=os.getenv(
        "APP_NAME",
        "AI Multi-Agent Research and Automation System"
    ),
    description="Backend API for our multi-agent research system.",
    version="0.1.0",
)

# Allow the local frontend to call this API during development.
# For deployment, set FRONTEND_ORIGINS to a comma-separated list
# of trusted frontend origins, for example:
# FRONTEND_ORIGINS=https://your-frontend.example,https://www.example
_frontend_origins = os.getenv(
    "FRONTEND_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173",
)

_allowed_origins = [
    origin.strip().rstrip("/")
    for origin in _frontend_origins.split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def recover_tasks_on_startup():

    # Initialize all PostgreSQL tables and indexes first.
    database_result = initialize_database()

    if not database_result.get("success"):
        raise RuntimeError(
            "PostgreSQL database initialization failed."
        )

    print(
        "PostgreSQL database initialized successfully. "
        f"Tables created: {database_result.get('tables_created')}"
    )

    # Initialize workflow tracing.
    initialize_workflow_tracing()
    print("Workflow tracing initialized successfully.")
    print("Workflow tracing initialized successfully.")
    """Initialize monitoring and recover interrupted tasks."""

    # Ensure the agent logging table exists.
    initialize_agent_logs()

    initialize_retry_database()
    
    initialize_priority_support()
    print("Task priority management initialized successfully.")
    
    initialize_task_scheduler()
    print("Priority-based task scheduler initialized successfully.")
    
    initialize_task_dependencies()
    
    # Recover tasks interrupted by a previous backend process.
    recovery_result = initialize_tasks()

    print(
        "Task recovery completed. "
        f"Interrupted tasks recovered: "
        f"{recovery_result['recovered_tasks']}"
    )

    print("Agent monitoring database initialized.")

@app.get("/research/history")
def research_history_endpoint():
    """
    Return the history of previously completed research tasks.
    """

    # Retrieve the saved research metadata.
    return get_research_history()

# ============================================================
#  RESEARCH HISTORY DETAILS API
# ============================================================

@app.get("/research/history/{research_id}")
def research_history_details_endpoint(research_id: str):
    """
    Return details for one research record.
    """

    # Search for the research record using its ID.
    result = get_research_by_id(research_id)

    # Return HTTP 404 if the research record does not exist.
    if not result["success"]:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=404,
            detail=result["message"],
        )

    # Return the matching research record.
    return result

# ============================================================
#  LIST SAVED RESEARCH REPORTS
# ============================================================

@app.get("/research/reports")
def research_reports_endpoint():
    """
    List all saved Markdown research reports.
    """

    # Retrieve the saved reports.
    return list_research_reports()

# ============================================================
#  RETRIEVE ONE RESEARCH REPORT
# ============================================================

@app.get("/research/reports/{report_filename}")
def research_report_details_endpoint(report_filename: str):
    """
    Retrieve the full contents of a saved Markdown report.
    """

    # Retrieve the requested report.
    result = get_research_report(report_filename)

    # Return HTTP 404 if the report is unavailable.
    if not result["success"]:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=404,
            detail=result["message"],
        )

    # Return the filename and complete report content.
    return result

# ============================================================
# DOWNLOAD RESEARCH REPORT FROM POSTGRESQL
# ============================================================

@app.get("/research/reports/{report_filename}/download")
def download_research_report_endpoint(report_filename: str):
    """Download a Markdown report stored in PostgreSQL."""

    result = get_research_report(report_filename)

    if not result["success"]:
        raise HTTPException(
            status_code=404,
            detail=result["message"],
        )

    return Response(
        content=result["report_content"],
        media_type="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{result["report_filename"]}"'
            )
        },
    )

# Define the structure of the health-check response.
class HealthResponse(BaseModel):
    status: str
    message: str

class TaskDependencyRequest(BaseModel):
    """Request body for creating a task dependency."""

    depends_on_task_id: str = Field(
        min_length=1,
        description="ID of the prerequisite research task.",
    )

# Create a health-check endpoint.
@app.get("/health", response_model=HealthResponse)
def health_check():
    # Return a simple response to confirm the backend is running.
    return HealthResponse(
        status="healthy",
        message="AI Multi-Agent System API is running."
    )


# Create a root endpoint for basic API information.
@app.get("/")
def root():
    # Return basic information about the application.
    return {
        "application": "AI Multi-Agent Research and Automation System",
        "status": "running",
        "documentation": "/docs",
        "health_check": "/health",
    }
    
# ============================================================
#  - BACKGROUND RESEARCH EXECUTION
# ============================================================

async def execute_research_task(
    task_id: str,
    research_question: str,
):
    """Execute research and persist its final result."""

    try:
        # Run the research workflow without blocking the event loop.
        import asyncio

        research_result = await asyncio.to_thread(
            run_research,
            research_question,
            task_id,
        )

        # Handle workflows that return a failure status.
        if research_result.get("status") == "failed":
            await update_task(
                task_id=task_id,
                status="failed",
                error=research_result.get(
                    "error",
                    "The research workflow failed.",
                ),
            )
            return

        # Save the generated report and result metadata.
        await update_task(
            task_id=task_id,
            status="completed",
            report_filename=research_result.get(
                "report_filename"
            ),
            quality_score=research_result.get(
                "quality_score"
            ),
            result={
                "research_id": research_result.get(
                    "research_id"
                ),
                "research_timestamp": research_result.get(
                    "research_timestamp"
                ),
                "report_filename": research_result.get(
                    "report_filename"
                ),
                "report_file": research_result.get(
                    "report_file"
                ),
                "metadata_filename": research_result.get(
                    "metadata_filename"
                ),
                "quality_score": research_result.get(
                    "quality_score"
                ),
                "trace_id": research_result.get("trace_id"),
            },
        )

    except Exception as error:
        # Save unexpected errors so the user can inspect or retry.
        await update_task(
            task_id=task_id,
            status="failed",
            error=f"{type(error).__name__}: {error}",
        )

    finally:
        # Always release the execution reservation.
        await release_task_execution(task_id)

# ============================================================
#  - TASK MANAGEMENT API
# ============================================================


class ResearchTaskRequest(BaseModel):
    """Validate data submitted when creating a research task."""

    research_question: str = Field(
        ...,
        min_length=5,
        max_length=2000,
        description="The research question to track.",
    )


@app.post("/research/tasks", status_code=201)
async def create_research_task_endpoint(
    request: ResearchTaskRequest,
):
    """Create a task record for a research question."""

    task = await create_task(request.research_question)

    return {
        "success": True,
        "message": "Research task created successfully.",
        "task": task,
    }


@app.get("/research/tasks")
async def list_research_tasks_endpoint():
    """List all task records."""

    return await get_all_tasks()


@app.get("/research/tasks/{task_id}")
async def get_research_task_endpoint(task_id: str):
    """Retrieve one task by its ID."""

    task = await get_task(task_id)

    if task is None:
        raise HTTPException(
            status_code=404,
            detail="Research task not found.",
        )

    return {
        "success": True,
        "task": task,
    }

# ============================================================
# -  DEPENDENCY-AWARE TASK EXECUTION
# ============================================================

@app.post("/research/tasks/{task_id}/execute")
async def execute_research_task_endpoint(
    task_id: str,
    background_tasks: BackgroundTasks,
):
    """
    Start a pending task or retry a failed task.

    A task cannot execute until all its prerequisite tasks
    have completed successfully.
    """

    # STEP 1: Check whether the requested task exists.
    task = await get_task(task_id)

    if task is None:
        raise HTTPException(
            status_code=404,
            detail="Research task not found.",
        )

    # STEP 2: Check whether all prerequisite tasks are completed.
    dependency_result = await asyncio.to_thread(
        check_task_dependencies,
        task_id,
    )

    # STEP 3: Handle dependency-check failures.
    if not dependency_result.get("success"):
        raise HTTPException(
            status_code=400,
            detail=dependency_result.get(
                "message",
                "Could not validate task dependencies.",
            ),
        )

    # STEP 4: Block execution if prerequisites are unfinished.
    if not dependency_result.get("ready"):
        raise HTTPException(
            status_code=409,
            detail={
                "message": (
                    "This task cannot execute because "
                    "one or more prerequisite tasks "
                    "are not completed."
                ),
                "task_id": task_id,
                "incomplete_dependencies": (
                    dependency_result.get(
                        "incomplete_dependencies",
                        [],
                    )
                ),
            },
        )
    
    # STEP 5: Reserve the task through the existing task manager.
    reservation = await reserve_task_for_execution(task_id)

    # STEP 6: Handle reservation failures.
    if not reservation.get("success"):
        message = reservation.get(
            "message",
            "The task could not be reserved for execution.",
        )

        if message == "Research task not found.":
            raise HTTPException(
                status_code=404,
                detail=message,
            )

        raise HTTPException(
            status_code=409,
            detail=message,
        )

    # STEP 7: Retrieve the reserved task information.
    task = reservation["task"]

    # STEP 8: Schedule the existing research execution function.
    background_tasks.add_task(
        execute_research_task,
        task_id,
        task["research_question"],
    )

    # STEP 9: Return the execution confirmation.
    return {
        "success": True,
        "message": (
            "Research task has been scheduled. "
            "All prerequisite tasks are completed."
        ),
        "task_id": task_id,
        "status": "running",
        "retry_count": task.get("retry_count", 0),
        "dependencies_ready": True,
        "status_endpoint": f"/research/tasks/{task_id}",
    }
        
@app.get("/research/tasks/{task_id}/agent-logs")
def get_task_agent_logs_endpoint(task_id: str):
    """Retrieve agent execution logs for one task."""

    result = get_agent_logs(task_id)

    return result


@app.get("/research/agent-logs")
def get_recent_agent_logs_endpoint(limit: int = 100):
    """Retrieve recent agent execution logs."""

    return get_recent_agent_logs(limit=limit)

# ============================================================
# - AGENT PERFORMANCE ANALYTICS API
# ============================================================


# Return overall execution statistics for all monitored agents.
@app.get("/research/analytics/agents")
def get_agent_analytics_endpoint():
    return get_agent_performance_analytics()


# Return execution statistics for a particular research task.
@app.get("/research/tasks/{task_id}/analytics")
def get_task_analytics_endpoint(task_id: str):
    return get_task_execution_analytics(task_id)

# ============================================================
#  - WORKFLOW EXECUTION TRACING API
# ============================================================


# Retrieve one workflow trace using its trace ID.
@app.get("/research/traces/{trace_id}")
def get_workflow_trace_endpoint(trace_id: str):
    trace = get_workflow_trace(trace_id)

    # Return a clear error if the trace does not exist.
    if trace is None:
        raise HTTPException(
            status_code=404,
            detail="Workflow trace not found.",
        )

    return trace


# Retrieve all traces associated with a research task.
@app.get("/research/tasks/{task_id}/traces")
def get_task_workflow_traces_endpoint(task_id: str):
    return get_task_workflow_traces(task_id)

# ============================================================
#  - UNIFIED SYSTEM MONITORING API
# ============================================================


@app.get("/research/monitoring/overview")
def get_system_overview_endpoint():
    """Return combined task, agent, and workflow statistics."""

    return get_system_overview()


@app.get("/research/monitoring/activity")
def get_recent_system_activity_endpoint(
    limit: int = 20,
):
    """Return recent agent execution activity."""

    return get_recent_system_activity(limit=limit)


@app.get("/research/tasks/{task_id}/diagnostics")
def get_task_diagnostics_endpoint(
    task_id: str,
):
    """Return the agent logs and workflow traces for a task."""

    return get_task_diagnostics(task_id)

# ============================================================
# - RETRY MANAGEMENT API
# ============================================================


@app.get("/research/retries")
def get_retry_history_endpoint(
    task_id: str = "",
    limit: int = 100,
):
    """Retrieve retry records, optionally filtered by task."""

    return get_retry_history(
        task_id=task_id or None,
        limit=limit,
    )


@app.get("/research/retries/statistics")
def get_retry_statistics_endpoint():
    """Return aggregate retry statistics."""

    return get_retry_statistics()


# ============================================================
# — INTELLIGENT TASK PRIORITIZATION API
# ============================================================


# Update the priority of an existing research task.
@app.patch("/research/tasks/{task_id}/priority")
async def update_research_task_priority_endpoint(
    task_id: str,
    request: dict,
):
    """Change a research task's priority."""

    # Read the priority supplied in the JSON request body.
    priority = request.get("priority")

    # Require the priority field.
    if not isinstance(priority, str):
        raise HTTPException(
            status_code=422,
            detail="Provide a priority string.",
        )

    try:
        # Update the priority in the existing SQLite database.
        result = await asyncio.to_thread(
        update_task_priority,
        task_id=task_id,
        priority=priority,
    )

    except ValueError as error:
        # Return a clear validation error for invalid priorities.
        raise HTTPException(
            status_code=422,
            detail=str(error),
        )

    # Return 404 when the task ID does not exist.
    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Research task not found.",
        )

    # Return the updated priority information.
    return {
        "success": True,
        "message": "Task priority updated successfully.",
        "task": result,
    }


# Retrieve the priority information for one task.
@app.get("/research/tasks/{task_id}/priority")
async def get_research_task_priority_endpoint(
    task_id: str,
):
    """Retrieve a task's priority and numerical score."""

    # Look up the task in the priority service.
    result = await asyncio.to_thread(
        get_task_priority,
        task_id,
    )

    # Return 404 if the task does not exist.
    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Research task not found.",
        )

    return {
        "success": True,
        "task": result,
    }


# Retrieve tasks ordered by priority.
@app.get("/research/tasks-by-priority")
async def list_tasks_by_priority_endpoint(
    status: str = "pending",
    limit: int = 100,
):
    """List tasks from highest to lowest priority."""

    # Allow the caller to request a particular status or all tasks.
    if status not in {
        "pending",
        "running",
        "completed",
        "failed",
        "all",
    }:
        raise HTTPException(
            status_code=422,
            detail=(
                "Status must be pending, running, completed, "
                "failed, or all."
            ),
        )

    try:
        # Retrieve the ordered task list.
        result = await asyncio.to_thread(
        get_tasks_by_priority,
        status=status,
        limit=limit,
    )

    except ValueError as error:
        # Return a validation error for an invalid limit.
        raise HTTPException(
            status_code=422,
            detail=str(error),
        )

    return result


# Retrieve counts for all four priority levels.
@app.get("/research/priorities/statistics")
async def get_priority_statistics_endpoint():
    """Return task counts grouped by priority."""

    return await asyncio.to_thread(
        get_priority_statistics
    )

# ============================================================

#  — PRIORITY-BASED SCHEDULING API

# ============================================================

@app.get("/scheduler/next-task")
async def get_next_scheduled_task_endpoint():
    """
    Preview the highest-priority pending task.
    This endpoint does not reserve or execute the task.
    """
    return await async_get_next_scheduled_task()
@app.get("/scheduler/queue")
async def get_scheduled_task_queue_endpoint(limit: int = 100):
    """
    Return pending research tasks in priority order.
    """
    try:
        return await async_get_scheduled_task_queue(limit=limit)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
@app.get("/scheduler/status")
async def get_scheduler_status_endpoint():
    """
    Return pending task counts for each priority level.
    """
    return await async_get_scheduler_status()

@app.post("/scheduler/run-next")
async def run_next_scheduled_task_endpoint(
    background_tasks: BackgroundTasks,
):
    """
    Select the highest-priority pending task and schedule its execution.

    The existing task manager reserves the task before execution.
    """

    # Step 1: Preview the highest-priority pending task.
    next_task = await async_get_next_scheduled_task()

    # Step 2: Stop if the queue contains no pending tasks.
    if not next_task.get("success") or not next_task.get("task"):
        return {
            "success": False,
            "message": "No pending research tasks are available.",
        }

    # Step 3: Extract the selected task.
    selected_task = next_task["task"]
    task_id = selected_task["task_id"]

    # Step 4: Reserve the task through the existing task manager.
    reservation = await reserve_task_for_execution(task_id)

    # Step 5: Handle reservation failures safely.
    if not reservation.get("success"):
        raise HTTPException(
            status_code=409,
            detail=reservation.get(
                "message",
                "The selected task could not be reserved.",
            ),
        )

    # Step 6: Get the reserved task information.
    task = reservation["task"]

    # Step 7: Schedule the existing research execution function.
    background_tasks.add_task(
        execute_research_task,
        task_id,
        task["research_question"],
    )

    # Step 8: Return information about the scheduled task.
    return {
        "success": True,
        "message": "Highest-priority research task scheduled successfully.",
        "task_id": task_id,
        "research_question": task["research_question"],
        "priority": selected_task.get("priority", "normal"),
        "status": "running",
        "retry_count": task.get("retry_count", 0),
        "status_endpoint": f"/research/tasks/{task_id}",
    }
    
# ============================================================
#  - AUTOMATIC PRIORITY-BASED TASK WORKER
# ============================================================

# These variables maintain the worker's state in this process.
SCHEDULER_WORKER_TASK = None
SCHEDULER_WORKER_STOP_REQUESTED = False
SCHEDULER_WORKER_CURRENT_TASK_ID = None


async def automatic_scheduler_worker():
    """
    Automatically execute pending research tasks in priority order.

    The worker reuses the existing task reservation and execution
    functions instead of implementing a separate execution system.
    """

    global SCHEDULER_WORKER_STOP_REQUESTED
    global SCHEDULER_WORKER_CURRENT_TASK_ID

    print("Automatic scheduler worker started.")

    try:
        while not SCHEDULER_WORKER_STOP_REQUESTED:

            # Step 1: Preview the highest-priority pending task.
            next_task = await async_get_next_scheduled_task()

            # Step 2: Wait when the queue is empty.
            if (
                not next_task.get("success")
                or not next_task.get("task")
            ):
                await asyncio.sleep(3)
                continue

            # Step 3: Extract the selected task.
            selected_task = next_task["task"]
            task_id = selected_task["task_id"]

            # Step 4: Reserve the task using the existing task manager.
            reservation = await reserve_task_for_execution(task_id)

            # Step 5: If reservation fails, check the queue again.
            if not reservation.get("success"):
                print(
                    f"Could not reserve task {task_id}: "
                    f"{reservation.get('message', 'Unknown reason')}"
                )

                await asyncio.sleep(1)
                continue

            # Step 6: Store the current task ID for monitoring.
            task = reservation["task"]
            SCHEDULER_WORKER_CURRENT_TASK_ID = task_id

            print(
                f"Starting task {task_id} "
                f"with priority "
                f"{selected_task.get('priority', 'normal')}."
            )

            try:
                # Step 7: Execute the existing research workflow.
                await execute_research_task(
                    task_id,
                    task["research_question"],
                )

            except Exception as error:
                # Log unexpected errors without crashing the worker.
                print(
                    f"Unexpected worker error for task "
                    f"{task_id}: {error}"
                )

            finally:
                # Step 8: Clear the current task indicator.
                SCHEDULER_WORKER_CURRENT_TASK_ID = None

            # Step 9: Check the queue again after execution finishes.
            await asyncio.sleep(1)

    finally:
        SCHEDULER_WORKER_CURRENT_TASK_ID = None

        print("Automatic scheduler worker stopped.")


# ============================================================
# START AUTOMATIC WORKER
# ============================================================

@app.post("/scheduler/worker/start")
async def start_scheduler_worker_endpoint():
    """
    Start automatic priority-based task processing.
    """

    global SCHEDULER_WORKER_TASK
    global SCHEDULER_WORKER_STOP_REQUESTED

    # Avoid starting duplicate workers.
    if (
        SCHEDULER_WORKER_TASK is not None
        and not SCHEDULER_WORKER_TASK.done()
    ):
        return {
            "success": True,
            "message": "The automatic scheduler worker is already running.",
        }

    # Reset the stop flag before starting a new worker.
    SCHEDULER_WORKER_STOP_REQUESTED = False

    # Start the worker as a background asyncio task.
    SCHEDULER_WORKER_TASK = asyncio.create_task(
        automatic_scheduler_worker()
    )

    return {
        "success": True,
        "message": "Automatic scheduler worker started successfully.",
    }


# ============================================================
# STOP AUTOMATIC WORKER
# ============================================================

@app.post("/scheduler/worker/stop")
async def stop_scheduler_worker_endpoint():
    """
    Ask the worker to stop after its current task finishes.
    """

    global SCHEDULER_WORKER_STOP_REQUESTED

    # Request a graceful stop.
    SCHEDULER_WORKER_STOP_REQUESTED = True

    return {
        "success": True,
        "message": (
            "Worker stop requested. "
            "The current research task will finish before the worker stops."
        ),
        "current_task_id": SCHEDULER_WORKER_CURRENT_TASK_ID,
    }


# ============================================================
# AUTOMATIC WORKER STATUS
# ============================================================

@app.get("/scheduler/worker/status")
async def scheduler_worker_status_endpoint():
    """
    Return the current automatic worker status.
    """

    worker_running = (
        SCHEDULER_WORKER_TASK is not None
        and not SCHEDULER_WORKER_TASK.done()
    )

    return {
        "success": True,
        "worker_running": worker_running,
        "stop_requested": SCHEDULER_WORKER_STOP_REQUESTED,
        "current_task_id": SCHEDULER_WORKER_CURRENT_TASK_ID,
    }
    
# ============================================================
#  - TASK DEPENDENCY API ENDPOINTS
# ============================================================


@app.post("/research/tasks/{task_id}/dependencies")
async def add_task_dependency_endpoint(
    task_id: str,
    request: TaskDependencyRequest,
):
    """
    Add a prerequisite task to a research task.
    """

    # Run synchronous database operations in a worker thread.
    result = await asyncio.to_thread(
        add_task_dependency,
        task_id=task_id,
        depends_on_task_id=request.depends_on_task_id,
    )

    if not result["success"]:
        message = result["message"]

        if "does not exist" in message:
            raise HTTPException(
                status_code=404,
                detail=message,
            )

        if "cycle" in message.lower():
            raise HTTPException(
                status_code=400,
                detail=message,
            )

        if "already exists" in message.lower():
            raise HTTPException(
                status_code=409,
                detail=message,
            )

        raise HTTPException(
            status_code=400,
            detail=message,
        )

    return result


@app.get("/research/tasks/{task_id}/dependencies")
async def get_task_dependencies_endpoint(task_id: str):
    """
    Retrieve the prerequisites of a research task.
    """

    # Run the database query outside the event loop.
    result = await asyncio.to_thread(
        get_task_dependencies,
        task_id,
    )

    if not result["success"]:
        raise HTTPException(
            status_code=404,
            detail=result["message"],
        )

    return result
@app.get("/research/tasks/{task_id}/dependency-status")
async def check_task_dependencies_endpoint(task_id: str):
    """
    Check whether all prerequisites are complete.
    """

    result = await asyncio.to_thread(
        check_task_dependencies,
        task_id,
    )

    if not result["success"]:
        raise HTTPException(
            status_code=404,
            detail=result["message"],
        )

    return result


@app.get("/research/tasks-ready")
async def get_ready_tasks_endpoint(limit: int = 100):
    """
    List pending tasks whose prerequisites are complete.
    """

    try:
        # Execute the synchronous database query in a worker thread.
        return await asyncio.to_thread(
            get_ready_tasks,
            limit=limit,
        )

    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error),
        )
        
# ============================================================
# - WORKFLOW OVERVIEW API
# ============================================================

@app.get("/workflow/overview")
async def workflow_overview_endpoint():
    """
    Return an overview of research tasks, priorities,
    dependencies, and execution readiness.
    """

    # Retrieve workflow information without blocking FastAPI.
    overview = await asyncio.to_thread(
        get_workflow_overview
    )

    return overview

# ============================================================
#  - WORKFLOW STATISTICS API
# ============================================================

@app.get("/workflow/statistics")
async def workflow_statistics_endpoint():
    """
    Return task counts, priorities, readiness, and completion.
    """
    
    # Calculate statistics using the workflow service.
    statistics = await asyncio.to_thread(
        get_workflow_statistics
    )

    # Return the statistics as JSON.
    return statistics

# ============================================================
#  - WORKFLOW HEALTH API
# ============================================================

@app.get("/workflow/health")
async def workflow_health_endpoint():
    """
    Return the health status of the research workflow.
    """
    # Generate the workflow health report.
    health_report = await asyncio.to_thread(
        get_workflow_health
    )

    # Return the report as JSON.
    return health_report

# ============================================================
# - PAGINATED AUDIT HISTORY API
# ============================================================

@app.get("/workflow/audit-history")
async def workflow_audit_history_endpoint(
    limit: int = 20,
    page: int = 1,
    status: str | None = None,
    priority: str | None = None,
    search: str | None = None,
    ):
    """
    Return a page of filtered workflow audit records.
    """


    # Validate the page size.
    if limit < 1 or limit > 100:
        raise HTTPException(
            status_code=400,
            detail="Limit must be between 1 and 100.",
        )

    # Validate the page number.
    if page < 1:
        raise HTTPException(
            status_code=400,
            detail="Page must be greater than or equal to 1.",
        )

    try:
        # Retrieve the requested page of audit records.
        return await asyncio.to_thread(
            get_workflow_audit_history,
            limit=limit,
            status=status,
            priority=priority,
            search=search,
            page=page,
        )

    except ValueError as error:
        # Report invalid filters or pagination parameters.
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )


# ============================================================
# WORKFLOW AUDIT CSV EXPORT
# ============================================================

@app.get("/workflow/audit-history/export")
async def export_workflow_audit_history_endpoint(
    status: str | None = None,
    priority: str | None = None,
    search: str | None = None,
):
    """
    Export all matching workflow audit records as a CSV file.
    """

    # Create an in-memory CSV buffer.
    csv_buffer = io.StringIO()

    # Define CSV columns.
    fieldnames = [
        "task_id",
        "research_question",
        "status",
        "priority",
        "created_at",
        "started_at",
        "finished_at",
        "duration_seconds",
        "retry_count",
        "error",
    ]

    # Create CSV writer.
    writer = csv.DictWriter(
        csv_buffer,
        fieldnames=fieldnames,
    )

    # Write CSV header.
    writer.writeheader()

    # Start from the first page.
    page = 1

    # Track exported records.
    exported_records = 0

    try:
        # Retrieve all matching audit records.
        while True:

            result = await asyncio.to_thread(
                get_workflow_audit_history,
                limit=100,
                page=page,
                status=status,
                priority=priority,
                search=search,
            )

            # Write records into CSV.
            for task in result["history"]:

                csv_row = {
                    field: task.get(field)
                    for field in fieldnames
                }

                writer.writerow(csv_row)
                exported_records += 1

            # Stop when all pages are processed.
            if page >= result["total_pages"]:
                break

            page += 1

    except ValueError as error:

        raise HTTPException(
            status_code=400,
            detail=str(error),
        )

    # Get the generated CSV content.
    csv_content = csv_buffer.getvalue()

    # Close the buffer.
    csv_buffer.close()

    # Return a downloadable CSV file.
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": (
                "attachment; filename=workflow_audit_history.csv"
            ),
            "X-Exported-Records": str(exported_records),
        },
    )
