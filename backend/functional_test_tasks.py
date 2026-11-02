"""
PROJECT 4 - STAGE 3: TASK AND DEPENDENCY FUNCTIONAL TESTS

This script tests task management without starting a research workflow.
It creates two clearly labelled test tasks in the application's database.
It does not execute either task, call the LLM, or call Tavily directly.

Run from the project root:
    python backend\functional_test_tasks.py

The test tasks are intentionally left in the database for inspection.
"""

import json
import sys
import urllib.error
import urllib.request
from datetime import datetime

BASE_URL = "http://127.0.0.1:8000"
TIMEOUT_SECONDS = 15
results = []


def request(method, path, payload=None):
    """Send one HTTP request and return (status_code, parsed_body)."""
    url = BASE_URL + path
    data = None

    headers = {"Accept": "application/json"}

    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(
        url=url,
        data=data,
        headers=headers,
        method=method,
    )

    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as response:
            status_code = response.status
            raw_body = response.read()
    except urllib.error.HTTPError as error:
        status_code = error.code
        raw_body = error.read()
    except Exception as error:
        raise RuntimeError(
            f"Could not contact {url}. Is the backend running? Details: {error}"
        ) from error

    body_text = raw_body.decode("utf-8", errors="replace")

    try:
        body = json.loads(body_text) if body_text else {}
    except json.JSONDecodeError:
        body = body_text

    return status_code, body


def record(name, passed, details=""):
    """Print and store one test result."""
    results.append((name, passed, details))
    label = "PASS" if passed else "FAIL"
    suffix = f" — {details}" if details else ""
    print(f"[{label}] {name}{suffix}")


def require_status(name, actual_status, expected_status, details=""):
    """Record whether an endpoint returned the expected HTTP status."""
    passed = actual_status == expected_status
    status_details = f"HTTP {actual_status}; expected {expected_status}"
    if details:
        status_details += f"; {details}"
    record(name, passed, status_details)
    return passed


def main():
    print("=" * 76)
    print("PROJECT 4 - STAGE 3: TASK & DEPENDENCY FUNCTIONAL TESTS")
    print("=" * 76)
    print(f"API base URL: {BASE_URL}")
    print("This test creates two labelled test tasks but does not execute research.")
    print("The test tasks will remain in your task database.")
    print()

    # Confirm the backend is available before creating any test data.
    try:
        status, health = request("GET", "/health")
    except RuntimeError as error:
        print(f"[ERROR] {error}")
        return 2

    if not require_status("Backend health check", status, 200):
        print("Stop: the backend health check failed; no test tasks were created.")
        return 2

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    first_question = (
        f"[AUTOMATED TEST {stamp}] Prerequisite task: verify task-management flow."
    )
    second_question = (
        f"[AUTOMATED TEST {stamp}] Dependent task: verify dependency blocking."
    )

    # Test 1: Create the prerequisite task.
    status, body = request(
        "POST",
        "/research/tasks",
        {"research_question": first_question},
    )
    if not require_status("Create prerequisite test task", status, 201):
        print("Cannot continue safely because the first test task was not created.")
        print("Response:", body)
        return 1

    first_task = body.get("task", {}) if isinstance(body, dict) else {}
    first_id = first_task.get("task_id")
    record("Prerequisite task response contains task_id", bool(first_id))

    if not first_id:
        print("Cannot continue because the API response did not contain task.task_id.")
        print("Response:", body)
        return 1

    # Test 2: Retrieve the newly created task.
    status, body = request("GET", f"/research/tasks/{first_id}")
    ok = require_status("Retrieve prerequisite task", status, 200)
    if ok and isinstance(body, dict):
        task = body.get("task", {})
        record(
            "Retrieved prerequisite task has pending status",
            task.get("status") == "pending",
            f"status={task.get('status')!r}",
        )
    else:
        record("Retrieved prerequisite task has pending status", False, "No task response")

    # Test 3: Update the prerequisite task priority.
    status, body = request(
        "PATCH",
        f"/research/tasks/{first_id}/priority",
        {"priority": "high"},
    )
    require_status("Set prerequisite task priority to high", status, 200)

    # Test 4: Read back the priority.
    status, body = request("GET", f"/research/tasks/{first_id}/priority")
    ok = require_status("Read prerequisite task priority", status, 200)
    if ok and isinstance(body, dict):
        actual_priority = body.get("priority")
        if actual_priority is None and isinstance(body.get("task"), dict):
            actual_priority = body["task"].get("priority")
        record(
            "Priority persisted as high",
            str(actual_priority).lower() == "high",
            f"priority={actual_priority!r}",
        )
    else:
        record("Priority persisted as high", False, "No priority response")

    # Test 5: Invalid priority should be rejected.
    status, body = request(
        "PATCH",
        f"/research/tasks/{first_id}/priority",
        {"priority": "super-ultra"},
    )
    require_status("Reject invalid task priority", status, 422)

    # Test 6: Create a second task that depends on the prerequisite.
    status, body = request(
        "POST",
        "/research/tasks",
        {"research_question": second_question},
    )
    if not require_status("Create dependent test task", status, 201):
        print("Response:", body)
        return 1

    second_task = body.get("task", {}) if isinstance(body, dict) else {}
    second_id = second_task.get("task_id")
    record("Dependent task response contains task_id", bool(second_id))

    if not second_id:
        print("Cannot continue because the API response did not contain task.task_id.")
        print("Response:", body)
        return 1

    # Test 7: Add the prerequisite relationship.
    status, body = request(
        "POST",
        f"/research/tasks/{second_id}/dependencies",
        {"depends_on_task_id": first_id},
    )
    require_status("Add task dependency", status, 200)

    # Test 8: Confirm the dependency is recorded.
    status, body = request("GET", f"/research/tasks/{second_id}/dependencies")
    ok = require_status("Retrieve task dependencies", status, 200)
    if ok:
        body_text = json.dumps(body).lower()
        record(
            "Dependency response references prerequisite task",
            first_id.lower() in body_text,
            f"prerequisite_id={first_id}",
        )
    else:
        record("Dependency response references prerequisite task", False)

    # Test 9: Confirm the dependent task is not ready yet.
    status, body = request(
        "GET",
        f"/research/tasks/{second_id}/dependency-status",
    )
    ok = require_status("Check dependency status", status, 200)
    if ok and isinstance(body, dict):
        ready = body.get("ready")
        if ready is None and isinstance(body.get("dependency_status"), dict):
            ready = body["dependency_status"].get("ready")
        record(
            "Dependent task is blocked while prerequisite is pending",
            ready is False,
            f"ready={ready!r}",
        )
    else:
        record(
            "Dependent task is blocked while prerequisite is pending",
            False,
            "Could not read dependency status",
        )

    # Test 10: Attempting to execute the dependent task must be blocked.
    # Expected HTTP 409 is important: the endpoint must not start research.
    status, body = request(
        "POST",
        f"/research/tasks/{second_id}/execute",
    )
    require_status(
        "Block execution while prerequisite is incomplete",
        status,
        409,
        "expected dependency protection; research should not start",
    )

    # Test 11: Try to add a reverse dependency. That would create a cycle.
    status, body = request(
        "POST",
        f"/research/tasks/{first_id}/dependencies",
        {"depends_on_task_id": second_id},
    )
    require_status("Reject circular task dependency", status, 400)

    # Test 12: A nonexistent task should return 404.
    status, body = request("GET", "/research/tasks/this-task-id-does-not-exist")
    require_status("Return 404 for unknown task ID", status, 404)

    # Print the summary.
    passed_count = sum(1 for _, passed, _ in results if passed)
    failed_count = len(results) - passed_count

    print()
    print("=" * 76)
    print(f"RESULT: {passed_count} passed, {failed_count} failed, {len(results)} total")
    print("=" * 76)
    print(f"Prerequisite test task ID: {first_id}")
    print(f"Dependent test task ID:    {second_id}")
    print("Both test tasks remain in the database; neither was executed.")
    print()

    if failed_count:
        print("Some functional checks failed. Share the complete output for diagnosis.")
        return 1

    print("SUCCESS: Task creation, priority, dependency protection, and validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
