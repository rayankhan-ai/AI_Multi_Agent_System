import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";

import {
  Activity,
  Bot,
  BrainCircuit,
  FileText,
  FlaskConical,
  LayoutDashboard,
  RefreshCw,
  Settings,
  Clock3,
  Menu,
  X,
} from "lucide-react";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import "./integration.css";

// ============================================================
// API CONFIGURATION
// ============================================================

// Local development uses localhost.
// Production uses the deployed backend if VITE_API_URL is missing.
const API = (
  import.meta.env.VITE_API_URL ||
  (import.meta.env.DEV
    ? "http://127.0.0.1:8000"
    : "https://ai-multi-agent-backend.hostless.app")
).replace(/\/$/, "");

// Maximum time allowed for one API request.
const REQUEST_TIMEOUT = 20000;

// Automatic dashboard refresh interval.
const REFRESH_INTERVAL = 30000;


// ============================================================
// NAVIGATION
// ============================================================

const NAV = [
  ["dashboard", "Overview", LayoutDashboard],
  ["research", "New research", FlaskIcon()],
  ["tasks", "Task manager", Activity],
  ["agents", "AI agents", Bot],
  ["analytics", "Analytics", BrainCircuit],
  ["reports", "Reports", FileText],
  ["history", "History", Clock3],
  ["settings", "Settings", Settings],
];

// Keep the research icon consistent with the existing interface.
function FlaskIcon() {
  return FlaskConical;
}


// ============================================================
// API REQUEST HANDLER
// ============================================================

async function call(path, options = {}) {
  const controller = new AbortController();

  let timedOut = false;

  const timeout = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, REQUEST_TIMEOUT);

  const externalSignal = options.signal;

  const abortFromExternalSignal = () => {
    controller.abort();
  };

  if (externalSignal) {
    if (externalSignal.aborted) {
      controller.abort();
    } else {
      externalSignal.addEventListener(
        "abort",
        abortFromExternalSignal,
        { once: true }
      );
    }
  }

  try {
    const response = await fetch(`${API}${path}`, {
      ...options,

      // Use our own controller so timeout and cleanup work together.
      signal: controller.signal,

      headers: {
        ...(options.body
          ? { "Content-Type": "application/json" }
          : {}),

        ...options.headers,
      },
    });

    const raw = await response.text();

    let body;

    try {
      body = raw ? JSON.parse(raw) : {};
    } catch {
      body = raw;
    }

    if (!response.ok) {
      const message =
        typeof body === "object"
          ? body?.detail || body?.message
          : body;

      throw new Error(
        message || `${response.status} ${response.statusText}`
      );
    }

    return body;

  } catch (error) {

    if (timedOut) {
      throw new Error(
        `Request timed out after ${REQUEST_TIMEOUT / 1000} seconds. The backend may be unavailable or slow.`
      );
    }

    if (error.name === "AbortError") {
      throw new Error("Request was cancelled.");
    }

    if (
      error instanceof TypeError ||
      error.message?.includes("Failed to fetch")
    ) {
      throw new Error(
        "Unable to reach the backend. Check the hosting service and API URL."
      );
    }

    throw error;

  } finally {
    clearTimeout(timeout);

    if (externalSignal) {
      externalSignal.removeEventListener(
        "abort",
        abortFromExternalSignal
      );
    }
  }
}


// ============================================================
// HELPER FUNCTIONS
// ============================================================

const arr = (value, ...keys) => {
  if (Array.isArray(value)) {
    return value;
  }

  for (const key of keys) {
    if (Array.isArray(value?.[key])) {
      return value[key];
    }
  }

  return [];
};


const idOf = (task) =>
  task?.task_id ||
  task?.id ||
  task?.research_id ||
  task?.uuid;


const statusOf = (task) =>
  String(task?.status || task?.state || "unknown").toLowerCase();


const fmt = (value) => {
  if (!value) {
    return "—";
  }

  const date = new Date(value);

  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleString();
};


const label = (value) =>
  String(value || "Unknown")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());


// ============================================================
// REUSABLE COMPONENTS
// ============================================================

function Badge({ value }) {
  const status = statusOf({ status: value });

  return (
    <span className={`badge ${status}`}>
      {label(status)}
    </span>
  );
}


function Empty({ text }) {
  return <div className="empty">{text}</div>;
}


// ============================================================
// MAIN APPLICATION
// ============================================================

export default function App() {

  // ----------------------------------------------------------
  // APPLICATION STATE
  // ----------------------------------------------------------

  const [page, setPage] = useState("dashboard");
  const [menu, setMenu] = useState(false);

  const [connected, setConnected] = useState(false);
  const [busy, setBusy] = useState(false);

  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const [question, setQuestion] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const [data, setData] = useState({
    tasks: [],
    history: [],
    reports: [],
    agents: {},
    activity: [],
    workflow: {},
    health: null,
  });

  const [report, setReport] = useState("");
  const [reportName, setReportName] = useState("");


  // ----------------------------------------------------------
  // REQUEST MANAGEMENT REFERENCES
  // ----------------------------------------------------------

  // Prevent multiple dashboard refreshes from running together.
  const refreshInProgress = useRef(false);

  // Keep track of the current dashboard refresh request.
  const refreshController = useRef(null);

  // Prevent state updates after component unmount.
  const mounted = useRef(false);


  // ==========================================================
  // DASHBOARD REFRESH
  // ==========================================================

  const refresh = useCallback(async (show = true) => {

    // Do not start another refresh while one is already running.
    if (refreshInProgress.current) {
      return;
    }

    refreshInProgress.current = true;

    const controller = new AbortController();

    refreshController.current = controller;

    if (show) {
      setBusy(true);
    }

    setError("");

    const endpoints = [
      ["health", "/health"],
      ["tasks", "/research/tasks"],
      ["history", "/research/history"],
      ["reports", "/research/reports"],
      ["agents", "/research/analytics/agents"],
      ["activity", "/research/monitoring/activity"],
      ["workflow", "/workflow/statistics"],
    ];

    try {

      // Request all dashboard data concurrently.
      const results = await Promise.allSettled(
        endpoints.map(([, path]) =>
          call(path, {
            signal: controller.signal,
          })
        )
      );

      if (!mounted.current || controller.signal.aborted) {
        return;
      }

      // Health endpoint determines the backend connection status.
      const healthResult = results[0];

      const isConnected =
        healthResult.status === "fulfilled";

      setConnected(isConnected);

      // Extract successful endpoint responses.
      const next = {};

      results.forEach((result, index) => {
        if (result.status === "fulfilled") {
          next[endpoints[index][0]] = result.value;
        }
      });

      // Update dashboard data without deleting previously loaded
      // information when an individual endpoint temporarily fails.
      setData((old) => ({
        ...old,

        ...(next.health !== undefined
          ? { health: next.health }
          : {}),

        ...(next.agents !== undefined
          ? { agents: next.agents }
          : {}),

        ...(next.workflow !== undefined
          ? { workflow: next.workflow }
          : {}),

        tasks:
          next.tasks !== undefined
            ? arr(next.tasks, "tasks", "items", "results", "data")
            : old.tasks,

        history:
          next.history !== undefined
            ? arr(next.history, "history", "items", "records", "data")
            : old.history,

        reports:
          next.reports !== undefined
            ? arr(next.reports, "reports", "items", "data")
            : old.reports,

        activity:
          next.activity !== undefined
            ? arr(
                next.activity,
                "activity",
                "logs",
                "items",
                "records",
                "data"
              )
            : old.activity,
      }));

      // Show an error only when the health endpoint fails.
      if (!isConnected) {

        const reason =
          healthResult.status === "rejected"
            ? healthResult.reason?.message
            : "Health endpoint returned an unsuccessful result.";

        setError(`Backend connection failed: ${reason}`);

      } else if (results.some((result) => result.status === "rejected")) {

        // Backend is online, but one or more optional endpoints failed.
        const failedCount = results.filter(
          (result) => result.status === "rejected"
        ).length;

        setError(
          `Backend is online, but ${failedCount} dashboard endpoint(s) could not be loaded.`
        );
      }

    } catch (error) {

      if (mounted.current && !controller.signal.aborted) {
        setError(error.message || "Dashboard refresh failed.");
      }

    } finally {

      refreshInProgress.current = false;

      if (mounted.current) {
        setBusy(false);
      }

      if (refreshController.current === controller) {
        refreshController.current = null;
      }
    }

  }, []);


  // ==========================================================
  // AUTOMATIC REFRESH AND CLEANUP
  // ==========================================================

  useEffect(() => {

    mounted.current = true;

    // Initial dashboard loading.
    refresh();

    // Refresh every 30 seconds.
    const timer = setInterval(() => {
      refresh(false);
    }, REFRESH_INTERVAL);

    return () => {

      mounted.current = false;

      clearInterval(timer);

      // Cancel requests when leaving the application.
      refreshController.current?.abort();

    };

  }, [refresh]);


  // ==========================================================
  // TASK STATISTICS
  // ==========================================================

  const counts = {
    total: data.tasks.length,

    completed: data.tasks.filter((task) =>
      ["completed", "success"].includes(statusOf(task))
    ).length,

    running: data.tasks.filter((task) =>
      ["running", "in_progress", "processing"].includes(
        statusOf(task)
      )
    ).length,

    pending: data.tasks.filter((task) =>
      ["pending", "queued", "created"].includes(statusOf(task))
    ).length,

    failed: data.tasks.filter((task) =>
      ["failed", "error"].includes(statusOf(task))
    ).length,
  };


  // ==========================================================
  // CREATE AND EXECUTE RESEARCH TASK
  // ==========================================================

  async function submit(event) {

    event.preventDefault();

    setError("");
    setNotice("");

    if (question.trim().length < 5) {
      setError("Enter at least 5 characters.");
      return;
    }

    setSubmitting(true);

    try {

      // Step 1: Create the research task.
      const created = await call("/research/tasks", {
        method: "POST",

        body: JSON.stringify({
          research_question: question.trim(),
        }),
      });

      // Find the task ID in possible response structures.
      const id =
        idOf(created) ||
        idOf(created?.task) ||
        idOf(created?.data);

      if (!id) {
        throw new Error(
          "Task created, but task ID was not found in the response. Check Task Manager."
        );
      }

      // Step 2: Request task execution.
      await call(
        `/research/tasks/${encodeURIComponent(id)}/execute`,
        {
          method: "POST",
        }
      );

      setNotice(`Task ${id} submitted for execution.`);

      setQuestion("");

      await refresh(false);

      setPage("tasks");

    } catch (error) {

      setError(error.message || "Unable to submit research task.");

    } finally {

      setSubmitting(false);

    }
  }


  // ==========================================================
  // EXECUTE EXISTING TASK
  // ==========================================================

  async function execute(id) {

    setError("");
    setNotice("");

    try {

      await call(
        `/research/tasks/${encodeURIComponent(id)}/execute`,
        {
          method: "POST",
        }
      );

      setNotice(`Execution requested for ${id}.`);

      await refresh(false);

    } catch (error) {

      setError(error.message || "Unable to execute task.");

    }
  }


  // ==========================================================
  // LOAD RESEARCH REPORT
  // ==========================================================

  async function openReport(item) {

    const filename =
      item.report_filename ||
      item.filename ||
      item.file_name;

    if (!filename) {
      setError("Report filename missing.");
      return;
    }

    setReportName(filename);
    setReport("Loading...");

    setError("");

    try {

      const result = await call(
        `/research/reports/${encodeURIComponent(filename)}`
      );

      const content =
        result.content ||
        result.report_content ||
        result.report ||
        result.markdown ||
        result.text;

      setReport(
        typeof content === "string"
          ? content
          : JSON.stringify(result, null, 2)
      );

    } catch (error) {

      setReport(`Unable to load report: ${error.message}`);

    }
  }


  // ==========================================================
  // REUSABLE UI HELPERS
  // ==========================================================

  const navigation = (
    <nav>
      {NAV.map(([key, name, Icon]) => (
        <button
          key={key}
          className={page === key ? "active" : ""}
          onClick={() => {
            setPage(key);
            setMenu(false);
          }}
        >
          <Icon size={18} />
          {name}
        </button>
      ))}
    </nav>
  );


  const stat = (name, value, sub) => (
    <div className="stat" key={name}>
      <small>{name}</small>
      <strong>{value}</strong>
      <span>{sub}</span>
    </div>
  );


  // ==========================================================
  // APPLICATION INTERFACE
  // ==========================================================

  return (
    <div className="app-shell">

      {/* Sidebar */}
      <aside className={`sidebar ${menu ? "open" : ""}`}>

        <div className="brand">
          <BrainCircuit />

          <span>
            <b>AgenticLab</b>
            <small>RESEARCH AUTOMATION</small>
          </span>

          <button
            className="close"
            onClick={() => setMenu(false)}
          >
            <X />
          </button>
        </div>

        <small className="caption">WORKSPACE</small>

        {navigation}

        <div className="side-status">
          <i className={connected ? "online" : "offline"} />

          {connected
            ? "Backend connected"
            : "Backend offline"}
        </div>

      </aside>


      {/* Mobile menu overlay */}
      {menu && (
        <button
          className="scrim"
          onClick={() => setMenu(false)}
          aria-label="Close menu"
        />
      )}


      {/* Main content */}
      <main className="main">

        {/* Top navigation */}
        <header className="topbar">

          <button
            className="menu-button"
            onClick={() => setMenu(true)}
          >
            <Menu />
          </button>

          <div>
            <small>AI MULTI-AGENT SYSTEM</small>

            <h1>
              {NAV.find((item) => item[0] === page)?.[1]}
            </h1>
          </div>

          <span
            className={
              connected ? "online-text" : "offline-text"
            }
          >
            {connected ? "● API online" : "● API offline"}
          </span>

          <button
            className="refresh"
            onClick={() => refresh()}
            disabled={busy}
            title="Refresh dashboard"
          >
            <RefreshCw size={17} />
          </button>

        </header>


        {/* Error message */}
        {error && (
          <div className="alert error">
            {error}

            <button onClick={() => setError("")}>
              Dismiss
            </button>
          </div>
        )}


        {/* Success message */}
        {notice && (
          <div className="alert success">
            {notice}

            <button onClick={() => setNotice("")}>
              Dismiss
            </button>
          </div>
        )}


        {/* ==================================================
            DASHBOARD
        ================================================== */}

        {page === "dashboard" && (

          <section className="page">

            <div className="welcome">

              <div>
                <small>COMMAND CENTER</small>

                <h2>
                  Your research operations, at a glance.
                </h2>

                <p>
                  Monitor tasks, agent activity, and generated reports.
                </p>
              </div>

              <button
                className="primary"
                onClick={() => setPage("research")}
              >
                ＋ Start research
              </button>

            </div>


            <div className="stats">

              {stat("Total tasks", counts.total, "Tasks in database")}

              {stat("Completed", counts.completed, "Successfully finished")}

              {stat("Running", counts.running, "Currently executing")}

              {stat("Failed", counts.failed, "Need review")}

            </div>


            <div className="card">

              <h3>Recent research tasks</h3>

              <p>Latest task records from FastAPI</p>

              {data.tasks.length ? (

                <div className="table-wrap">

                  <table>
                    <thead>
                      <tr>
                        <th>Research question</th>
                        <th>Status</th>
                        <th>Created</th>
                      </tr>
                    </thead>

                    <tbody>
                      {data.tasks.slice(0, 8).map((task, index) => (

                        <tr key={idOf(task) || index}>

                          <td>
                            {task.research_question ||
                              task.question ||
                              task.title ||
                              "Untitled"}
                          </td>

                          <td>
                            <Badge value={statusOf(task)} />
                          </td>

                          <td>
                            {fmt(task.created_at || task.timestamp)}
                          </td>

                        </tr>

                      ))}
                    </tbody>
                  </table>

                </div>

              ) : (

                <Empty text="No tasks yet. Start a research workflow." />

              )}

            </div>


            <div className="two">

              <div className="card">

                <h3>System status</h3>

                <p>Live backend summary</p>

                <div className="line">
                  <span>API</span>
                  <Badge value={connected ? "completed" : "failed"} />
                </div>

                <div className="line">
                  <span>Pending tasks</span>
                  <b>{counts.pending}</b>
                </div>

                <div className="line">
                  <span>Reports available</span>
                  <b>{data.reports.length}</b>
                </div>

              </div>


              <div className="card">

                <h3>Recent agent activity</h3>

                <p>Monitoring events</p>

                {data.activity.length ? (

                  data.activity.slice(0, 5).map((activity, index) => (

                    <div
                      className="line"
                      key={activity.log_id || index}
                    >
                      <span>
                        {label(activity.agent_name)}
                      </span>

                      <Badge value={activity.status} />
                    </div>

                  ))

                ) : (

                  <Empty text="No agent activity recorded yet." />

                )}

              </div>

            </div>

          </section>

        )}


        {/* ==================================================
            NEW RESEARCH
        ================================================== */}

        {page === "research" && (

          <section className="page narrow">

            <small>NEW WORKFLOW</small>

            <h2>What should the agents research?</h2>

            <p>
              Submit a question to create and execute a research task.
            </p>


            <form className="card form" onSubmit={submit}>

              <label htmlFor="rq">
                Research question
              </label>

              <textarea
                id="rq"
                rows="7"
                maxLength="2000"
                minLength="5"
                value={question}
                onChange={(event) =>
                  setQuestion(event.target.value)
                }
                placeholder="Example: Compare RAG and fine-tuning for enterprise knowledge assistants. Include strengths, limitations, costs, and recent sources."
                required
              />

              <div className="form-foot">

                <span>
                  {question.length}/2000 characters
                </span>

                <button
                  className="primary"
                  disabled={
                    submitting ||
                    question.trim().length < 5
                  }
                >
                  {submitting
                    ? "Submitting..."
                    : "Start research →"}
                </button>

              </div>

              <p className="hint">
                Uses POST /research/tasks, followed by
                POST /research/tasks/{"{task_id}"}/execute.
                Backend default priority is used.
              </p>

            </form>

          </section>

        )}


        {/* ==================================================
            TASK MANAGER
        ================================================== */}

        {page === "tasks" && (

          <section className="page">

            <small>WORKFLOW QUEUE</small>

            <h2>Task manager</h2>

            <p>
              Review tasks and execute pending or failed items.
            </p>


            <div className="stats">

              {stat("Pending", counts.pending, "Waiting")}

              {stat("Running", counts.running, "Active")}

              {stat("Completed", counts.completed, "Finished")}

              {stat("Failed", counts.failed, "Review")}

            </div>


            <div className="card">

              <h3>All research tasks</h3>

              {data.tasks.length ? (

                <div className="table-wrap">

                  <table>

                    <thead>
                      <tr>
                        <th>Question</th>
                        <th>Task ID</th>
                        <th>Status</th>
                        <th>Created</th>
                        <th>Action</th>
                      </tr>
                    </thead>

                    <tbody>

                      {data.tasks.map((task, index) => (

                        <tr key={idOf(task) || index}>

                          <td>
                            {task.research_question ||
                              task.question ||
                              task.title ||
                              "Untitled"}
                          </td>

                          <td>
                            {(idOf(task) || "—").slice(0, 12)}
                          </td>

                          <td>
                            <Badge value={statusOf(task)} />
                          </td>

                          <td>
                            {fmt(task.created_at || task.timestamp)}
                          </td>

                          <td>

                            {idOf(task) &&
                            [
                              "pending",
                              "queued",
                              "created",
                              "failed",
                            ].includes(statusOf(task)) ? (

                              <button
                                className="mini"
                                onClick={() => execute(idOf(task))}
                              >
                                Execute
                              </button>

                            ) : (
                              "—"
                            )}

                          </td>

                        </tr>

                      ))}

                    </tbody>

                  </table>

                </div>

              ) : (

                <Empty text="No task records found." />

              )}

            </div>

          </section>

        )}


        {/* ==================================================
            AI AGENTS
        ================================================== */}

        {page === "agents" && (

          <section className="page">

            <small>AGENT OBSERVABILITY</small>

            <h2>AI agent activity</h2>

            <p>
              Agent metrics and latest execution logs.
            </p>


            <div className="stats">

              {stat(
                "Executions",
                data.agents?.total_executions ??
                  data.agents?.total_runs ??
                  "—",
                "Recorded runs"
              )}

              {stat(
                "Successful",
                data.agents?.successful_executions ??
                  data.agents?.success_count ??
                  "—",
                "Successful runs"
              )}

              {stat(
                "Failed",
                data.agents?.failed_executions ??
                  data.agents?.failure_count ??
                  "—",
                "Failed runs"
              )}

              {stat(
                "Success rate",
                data.agents?.success_rate != null
                  ? `${Number(data.agents.success_rate).toFixed(1)}%`
                  : "—",
                "Backend metric"
              )}

            </div>


            <div className="card">

              <h3>Agent logs</h3>

              {data.activity.length ? (

                <div className="table-wrap">

                  <table>

                    <thead>
                      <tr>
                        <th>Agent</th>
                        <th>Task ID</th>
                        <th>Status</th>
                        <th>Duration</th>
                        <th>Error</th>
                      </tr>
                    </thead>

                    <tbody>

                      {data.activity.map((activity, index) => (

                        <tr key={activity.log_id || index}>

                          <td>
                            {label(activity.agent_name)}
                          </td>

                          <td>
                            {(activity.task_id || "—").slice(0, 12)}
                          </td>

                          <td>
                            <Badge value={activity.status} />
                          </td>

                          <td>
                            {activity.duration_seconds ?? "—"}
                          </td>

                          <td>
                            {activity.error_message || "—"}
                          </td>

                        </tr>

                      ))}

                    </tbody>

                  </table>

                </div>

              ) : (

                <Empty text="No agent logs yet." />

              )}

            </div>

          </section>

        )}


        {/* ==================================================
            ANALYTICS
        ================================================== */}

        {page === "analytics" && (

          <section className="page">

            <small>PERFORMANCE INSIGHTS</small>

            <h2>Workflow analytics</h2>

            <p>
              Task distribution and backend workflow metrics.
            </p>


            <div className="stats">

              {stat("Total", counts.total, "Tasks")}

              {stat("Completed", counts.completed, "Successful")}

              {stat("Pending", counts.pending, "Waiting")}

              {stat("Failed", counts.failed, "Errors")}

            </div>


            <div className="card">

              <h3>Workflow statistics</h3>

              <div className="line">
                <span>Total workflows</span>

                <b>
                  {data.workflow?.total_workflows ??
                    data.workflow?.total ??
                    "—"}
                </b>
              </div>

              <div className="line">
                <span>Completed</span>

                <b>
                  {data.workflow?.completed_workflows ??
                    data.workflow?.completed ??
                    "—"}
                </b>
              </div>

              <div className="line">
                <span>Failed</span>

                <b>
                  {data.workflow?.failed_workflows ??
                    data.workflow?.failed ??
                    "—"}
                </b>
              </div>

              <div className="line">
                <span>Success rate</span>

                <b>
                  {data.workflow?.success_rate != null
                    ? `${data.workflow.success_rate}%`
                    : "—"}
                </b>
              </div>

            </div>

          </section>

        )}


        {/* ==================================================
            REPORTS
        ================================================== */}

        {page === "reports" && (

          <section className="page">

            <small>GENERATED OUTPUT</small>

            <h2>Research reports</h2>

            <p>
              Preview and download generated research documents.
            </p>


            <div className="two">

              <div className="card">

                <h3>Available reports</h3>

                {data.reports.length ? (

                  data.reports.map((item, index) => (

                    <div
                      className="report"
                      key={item.report_filename || index}
                    >

                      <button onClick={() => openReport(item)}>

                        <FileText size={17} />

                        <span>

                          {item.research_question ||
                            item.report_filename ||
                            "Research report"}

                          <small>
                            Quality: {item.quality_score ?? "—"}
                          </small>

                        </span>

                      </button>

                      {item.report_filename && (

                        <a
                          href={`${API}/research/reports/${encodeURIComponent(item.report_filename)}/download`}
                          target="_blank"
                          rel="noreferrer"
                        >
                          Download
                        </a>

                      )}

                    </div>

                  ))

                ) : (

                  <Empty text="No reports available yet." />

                )}

              </div>


              <div className="card">

                <h3>Report preview</h3>

                <p>
                  {reportName || "Select a report"}
                </p>

                {report ? (

                  <div className="markdown">

                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {report}
                    </ReactMarkdown>

                  </div>

                ) : (

                  <Empty text="Choose a report from the list." />

                )}

              </div>

            </div>

          </section>

        )}


        {/* ==================================================
            RESEARCH HISTORY
        ================================================== */}

        {page === "history" && (

          <section className="page">

            <small>PAST WORK</small>

            <h2>Research history</h2>

            <p>
              Previously completed research tasks.
            </p>


            <div className="card">

              <h3>History records</h3>

              {data.history.length ? (

                <div className="table-wrap">

                  <table>

                    <thead>
                      <tr>
                        <th>Question</th>
                        <th>Status</th>
                        <th>Completed</th>
                        <th>Quality</th>
                      </tr>
                    </thead>

                    <tbody>

                      {data.history.map((item, index) => (

                        <tr
                          key={
                            item.research_id ||
                            item.task_id ||
                            index
                          }
                        >

                          <td>
                            {item.research_question ||
                              item.question ||
                              "Research record"}
                          </td>

                          <td>
                            <Badge value={item.status || "completed"} />
                          </td>

                          <td>
                            {fmt(
                              item.completed_at ||
                              item.updated_at ||
                              item.created_at
                            )}
                          </td>

                          <td>
                            {item.quality_score ?? "—"}
                          </td>

                        </tr>

                      ))}

                    </tbody>

                  </table>

                </div>

              ) : (

                <Empty text="No history records returned." />

              )}

            </div>

          </section>

        )}


        {/* ==================================================
            SETTINGS
        ================================================== */}

        {page === "settings" && (

          <section className="page narrow">

            <small>CONFIGURATION</small>

            <h2>Connection settings</h2>

            <p>
              Frontend API configuration and diagnostics.
            </p>


            <div className="card">

              <div className="line">
                <span>API URL</span>
                <code>{API}</code>
              </div>

              <div className="line">
                <span>Connection</span>

                <Badge value={connected ? "completed" : "failed"} />
              </div>

              <div className="line">
                <span>Health response</span>

                <code>
                  {data.health
                    ? JSON.stringify(data.health)
                    : "No response"}
                </code>
              </div>

              <p className="hint">
                Local development: set VITE_API_URL in
                frontend/.env to http://127.0.0.1:8000.
                Production uses the deployed backend URL
                unless VITE_API_URL is configured separately.
              </p>

            </div>

          </section>

        )}


        {/* Footer */}
        <footer className="footer">

          AI Multi-Agent Research & Automation System

          <span>
            Auto-refresh every 30 seconds
          </span>

        </footer>

      </main>

    </div>
  );
}