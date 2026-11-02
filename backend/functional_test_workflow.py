"""Stage 4 end-to-end workflow test. Run from the project root while backend is running."""
import json
import time
import urllib.error
import urllib.request
from datetime import datetime
from urllib.parse import quote

BASE_URL = "http://127.0.0.1:8000"
POLL_SECONDS = 5
MAX_WAIT_SECONDS = 300


def api(method, path, payload=None, timeout=30):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(BASE_URL + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
            try:
                body = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                body = raw
            return response.status, body
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            body = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            body = raw
        return exc.code, body
    except Exception as exc:
        return 0, {"error": str(exc)}


def main():
    passed, failed = 0, 0

    def check(label, condition, details=""):
        nonlocal passed, failed
        print(f"[{'PASS' if condition else 'FAIL'}] {label}" + (f" — {details}" if details else ""))
        if condition:
            passed += 1
        else:
            failed += 1

    print("=" * 72)
    print("PROJECT 4 — STAGE 4: END-TO-END MULTI-AGENT WORKFLOW TEST")
    print("=" * 72)

    status, health = api("GET", "/health")
    check("Backend health check", status == 200, f"HTTP {status}")
    if status != 200:
        print("Backend is unreachable. Start it and run this script again.")
        print(health)
        return 1

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    question = (
        f"[STAGE 4 AUTOMATED TEST {stamp}] Explain three practical differences "
        "between retrieval-augmented generation (RAG) and fine-tuning for AI "
        "applications. Use credible sources and include a brief conclusion."
    )
    status, created = api("POST", "/research/tasks", {"research_question": question})
    check("Create research task", status in (200, 201), f"HTTP {status}")
    if status not in (200, 201):
        print(json.dumps(created, indent=2, ensure_ascii=False))
        return 1

    task = created.get("task", created) if isinstance(created, dict) else {}
    task_id = task.get("task_id") or task.get("id")
    check("Created task contains task ID", bool(task_id), str(task_id))
    if not task_id:
        print("Unexpected response:", json.dumps(created, indent=2, ensure_ascii=False))
        return 1

    status, result = api("POST", f"/research/tasks/{task_id}/execute", {})
    check("Start real research workflow", status in (200, 202),
          f"HTTP {status}; {str(result)[:180]}")
    if status not in (200, 202):
        print("Check backend logs and task details before proceeding.")
        return 1

    deadline = time.time() + MAX_WAIT_SECONDS
    latest = {}
    final_status = "unknown"
    print(f"Waiting up to {MAX_WAIT_SECONDS} seconds for task {task_id}...")
    while time.time() < deadline:
        status, body = api("GET", f"/research/tasks/{task_id}")
        if status == 200:
            latest = body.get("task", body) if isinstance(body, dict) else {}
            final_status = str(latest.get("status", "unknown")).lower()
            print("  Task status:", final_status)
            if final_status in ("completed", "complete", "success", "succeeded", "failed", "error"):
                break
        else:
            print(f"  Poll returned HTTP {status}: {str(body)[:160]}")
        time.sleep(POLL_SECONDS)

    terminal = final_status in ("completed", "complete", "success", "succeeded", "failed", "error")
    success = final_status in ("completed", "complete", "success", "succeeded")
    check("Task reached a terminal status", terminal, f"status={final_status}")
    check("Research workflow completed successfully", success, f"status={final_status}")

    filename = (latest.get("report_filename") or latest.get("report_file")
                or (latest.get("result") or {}).get("report_filename")
                if isinstance(latest.get("result"), dict) else
                latest.get("report_filename") or latest.get("report_file"))
    print("Task ID:", task_id)
    print("Report filename:", filename or "(not returned in task object)")

    if filename:
        status, report = api("GET", "/research/reports/" + quote(str(filename), safe=""))
        rendered = report if isinstance(report, str) else json.dumps(report, ensure_ascii=False)
        check("Retrieve generated report", status == 200, f"HTTP {status}")
        check("Report response contains data", status == 200 and len(rendered.strip()) > 100,
              f"response length={len(rendered)}")
    else:
        check("Task provides report filename", False, "Inspect task response/report endpoint")

    # These endpoints check observability. A 404 here can mean a route name differs
    # in this project's version; it does not by itself mean research failed.
    optional_routes = [
        ("Agent logs", f"/research/tasks/{task_id}/logs"),
        ("Workflow traces", f"/workflow/traces?task_id={task_id}"),
        ("Agent analytics", "/analytics/agents"),
        ("System monitoring", "/monitoring/overview"),
        ("Research history", "/research/history"),
        ("Retry history", "/research/retries"),
    ]
    print("\nSupporting observability endpoint checks:")
    for label, path in optional_routes:
        status, body = api("GET", path)
        check(label, status == 200, f"HTTP {status}; {str(body)[:90]}")

    if not success:
        print("\nTask details:")
        print(json.dumps(latest, indent=2, ensure_ascii=False)[:4000])
        for path in (f"/research/tasks/{task_id}/diagnostics", "/research/retries/statistics"):
            status, body = api("GET", path)
            print(f"\nGET {path} -> HTTP {status}")
            print(json.dumps(body, indent=2, ensure_ascii=False)[:2000])

    print("\n" + "=" * 72)
    print(f"RESULT: {passed} passed, {failed} failed, {passed + failed} total")
    print("Task ID:", task_id)
    print("SUCCESS: All checks passed." if failed == 0 else
          "Some checks failed. Review details; optional route-name mismatches may need adjustment.")
    print("=" * 72)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
