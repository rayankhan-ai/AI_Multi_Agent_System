# backend/services/monitored_agent.py

# Import timing support.
import time

# Import typing helpers.
from typing import Any, Callable, Dict

# Import the persistent logging functions.
from backend.services.agent_monitor import (
    start_agent_log,
    finish_agent_log,
)


def summarize_value(
    value: Any,
    max_length: int = 500,
) -> str:
    """Convert a value into a short, readable summary."""

    if value is None:
        return "No data"

    if isinstance(value, str):
        summary = value
    else:
        summary = repr(value)

    # Keep database logs reasonably small.
    return summary[:max_length]


def execute_monitored_agent(
    task_id: str,
    agent_name: str,
    agent_function: Callable,
    agent_input: Any,
) -> Dict[str, Any]:
    """
    Run an existing agent function and record its execution.

    The wrapped function must accept agent_input as its argument.
    """

    log_id = start_agent_log(
        task_id=task_id,
        agent_name=agent_name,
        input_summary=summarize_value(agent_input),
    )

    start_time = time.perf_counter()

    try:
        # Execute the original agent without changing its logic.
        result = agent_function(agent_input)

        duration = time.perf_counter() - start_time

        # Record successful execution.
        finish_agent_log(
            log_id=log_id,
            status="completed",
            output_summary=summarize_value(result),
        )

        return {
            "success": True,
            "agent_name": agent_name,
            "duration_seconds": round(duration, 3),
            "result": result,
        }

    except Exception as error:

        # Record the error before passing it to the caller.
        finish_agent_log(
            log_id=log_id,
            status="failed",
            error_message=(
                f"{type(error).__name__}: {error}"
            ),
        )

        # Preserve the original failure behavior.
        raise
