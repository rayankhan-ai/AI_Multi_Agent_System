import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.services.retry_manager import execute_with_retry


def test_temporary_connection_errors():
    """Test retries after temporary connection failures."""

    attempts = {"count": 0}

    def simulated_operation():
        attempts["count"] += 1
        print(f"Connection test attempt {attempts['count']}")

        if attempts["count"] < 3:
            raise ConnectionError("Temporary connection error")

        return {
            "status": "completed",
            "message": "Connection test succeeded.",
        }

    result = execute_with_retry(
        function=simulated_operation,
        agent_name="Connection Test Agent",
        task_id=f"connection-test-{uuid.uuid4()}",
        max_retries=3,
        initial_delay=0.1,
        max_delay=0.2,
    )

    assert attempts["count"] == 3
    assert result["status"] == "completed"

    print("PASS: Temporary connection errors were retried.")


def test_failed_agent_result():
    """Test retrying when an agent returns a failure dictionary."""

    attempts = {"count": 0}

    def simulated_agent():
        attempts["count"] += 1
        print(f"Agent test attempt {attempts['count']}")

        if attempts["count"] == 1:
            return {
                "status": "failed",
                "error": (
                    "Coordinator Agent failed: "
                    "APIConnectionError: Connection error"
                ),
            }

        return {
            "status": "completed",
            "message": "Agent recovered successfully.",
        }

    result = execute_with_retry(
        function=simulated_agent,
        agent_name="Simulated Coordinator Agent",
        task_id=f"agent-test-{uuid.uuid4()}",
        max_retries=2,
        initial_delay=0.1,
        max_delay=0.2,
    )

    assert attempts["count"] == 2
    assert result["status"] == "completed"

    print("PASS: Returned agent failures were retried.")


if __name__ == "__main__":
    test_temporary_connection_errors()
    test_failed_agent_result()
    print("\nALL RETRY TESTS PASSED.")
