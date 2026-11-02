"""Read-only smoke tests for the running Project 4 FastAPI backend.

Run from the project root while Uvicorn is running:
    python backend/smoke_test_api.py

Optional custom API base URL:
    python backend/smoke_test_api.py http://127.0.0.1:8000

This script only sends GET requests. It does not create, update, or delete tasks.
"""

import sys
from typing import List, Tuple

import httpx


DEFAULT_BASE_URL = "http://127.0.0.1:8000"

# Read-only endpoints that should respond without running a new research job.
ENDPOINTS: List[Tuple[str, str]] = [
    ("Root information", ""),
    ("Health check", "/health"),
    ("OpenAPI schema", "/openapi.json"),
    ("Research history", "/research/history"),
    ("Saved research reports", "/research/reports"),
    ("Research task list", "/research/tasks"),
    ("Recent agent logs", "/research/agent-logs?limit=5"),
    ("Agent performance analytics", "/research/analytics/agents"),
    ("System monitoring overview", "/research/monitoring/overview"),
    ("Recent system activity", "/research/monitoring/activity?limit=5"),
    ("Retry history", "/research/retries?limit=5"),
    ("Retry statistics", "/research/retries/statistics"),
    ("Priority statistics", "/research/priorities/statistics"),
    ("Tasks by priority", "/research/tasks-by-priority?status=all&limit=5"),
    ("Scheduler queue", "/scheduler/queue?limit=5"),
    ("Scheduler status", "/scheduler/status"),
    ("Ready tasks", "/research/tasks-ready?limit=5"),
    ("Workflow overview", "/workflow/overview"),
    ("Workflow statistics", "/workflow/statistics"),
    ("Workflow health", "/workflow/health"),
    ("Workflow audit history", "/workflow/audit-history?limit=5&page=1"),
    ("Workflow audit CSV export", "/workflow/audit-history/export"),
]


def main() -> int:
    """Call each read-only endpoint and print a concise test report."""

    base_url = (sys.argv[1] if len(sys.argv) > 1 else DEFAULT_BASE_URL).rstrip("/")
    passed = 0
    failed = 0

    print("=" * 72)
    print("PROJECT 4 - BACKEND API SMOKE TEST")
    print("=" * 72)
    print(f"API base URL: {base_url}")
    print("These checks use GET requests only; no research tasks are created.\n")

    try:
        with httpx.Client(base_url=base_url, timeout=15.0, follow_redirects=True) as client:
            for label, path in ENDPOINTS:
                try:
                    response = client.get("/" + path.lstrip("/"))
                    if response.status_code == 200:
                        passed += 1
                        print(f"[PASS] {label:<34} HTTP {response.status_code}")
                    else:
                        failed += 1
                        detail = response.text.replace("\n", " ")[:180]
                        print(f"[FAIL] {label:<34} HTTP {response.status_code} | {detail}")
                except httpx.HTTPError as error:
                    failed += 1
                    print(f"[FAIL] {label:<34} Connection error: {error}")
    except httpx.HTTPError as error:
        print("Could not connect to the backend.")
        print(f"Details: {error}")
        print("Make sure Uvicorn is running, then run this script again.")
        return 2

    print("\n" + "=" * 72)
    print(f"RESULT: {passed} passed, {failed} failed, {len(ENDPOINTS)} total")
    print("=" * 72)

    if failed:
        print("\nOne or more endpoints did not return HTTP 200.")
        print("Copy the failing endpoint names and error details into ChatGPT.")
        return 1

    print("\nSUCCESS: All read-only backend endpoint checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
