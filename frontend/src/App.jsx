import { useCallback, useEffect, useState } from "react";
import { Activity, Bot, BrainCircuit, CheckCircle2, CircleAlert, FileText, FlaskConical, LayoutDashboard, RefreshCw, Settings, Clock3, Menu, X } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import "./integration.css";

const API = (import.meta.env.VITE_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
const NAV = [["dashboard","Overview",LayoutDashboard],["research","New research",FlaskConical],["tasks","Task manager",Activity],["agents","AI agents",Bot],["analytics","Analytics",BrainCircuit],["reports","Reports",FileText],["history","History",Clock3],["settings","Settings",Settings]];
async function call(path, options={}) {
  const response = await fetch(`${API}${path}`, {...options, headers:{...(options.body?{"Content-Type":"application/json"}:{}),...options.headers}});
  const raw = await response.text(); let body;
  try { body = raw ? JSON.parse(raw) : {}; } catch { body = raw; }
  if (!response.ok) throw new Error(body?.detail || body?.message || `${response.status} ${response.statusText}`);
  return body;
}
const arr = (v,...keys) => Array.isArray(v) ? v : keys.map(k=>v?.[k]).find(Array.isArray) || [];
const idOf = t => t?.task_id || t?.id || t?.research_id || t?.uuid;
const statusOf = t => String(t?.status || t?.state || "unknown").toLowerCase();
const fmt = v => v ? (Number.isNaN(new Date(v).getTime()) ? v : new Date(v).toLocaleString()) : "—";
const label = v => String(v||"Unknown").replaceAll("_"," ").replace(/\b\w/g,c=>c.toUpperCase());
function Badge({value}) { const s=statusOf({status:value}); return <span className={`badge ${s}`}>{label(s)}</span>; }
function Empty({text}) { return <div className="empty">{text}</div>; }

export default function App() {
  const [page,setPage]=useState("dashboard"), [menu,setMenu]=useState(false);
  const [connected,setConnected]=useState(false), [busy,setBusy]=useState(false);
  const [error,setError]=useState(""), [notice,setNotice]=useState("");
  const [question,setQuestion]=useState(""), [submitting,setSubmitting]=useState(false);
  const [data,setData]=useState({tasks:[],history:[],reports:[],agents:{},activity:[],workflow:{},health:null});
  const [report,setReport]=useState(""), [reportName,setReportName]=useState("");

  const refresh=useCallback(async(show=true)=>{
    if(show)setBusy(true); setError("");
    const endpoints=[["health","/health"],["tasks","/research/tasks"],["history","/research/history"],["reports","/research/reports"],["agents","/research/analytics/agents"],["activity","/research/monitoring/activity"],["workflow","/workflow/statistics"]];
    const results=await Promise.allSettled(endpoints.map(([,p])=>call(p)));
    setConnected(results[0].status==="fulfilled");
    const next={}; results.forEach((r,i)=>{if(r.status==="fulfilled")next[endpoints[i][0]]=r.value;});
    setData(old=>({...old,...next,
      tasks:next.tasks?arr(next.tasks,"tasks","items","results","data"):old.tasks,
      history:next.history?arr(next.history,"history","items","records","data"):old.history,
      reports:next.reports?arr(next.reports,"reports","items","data"):old.reports,
      activity:next.activity?arr(next.activity?.activity,"logs","items").length?arr(next.activity?.activity,"logs","items"):arr(next.activity,"logs","items"):old.activity
    }));
    if(results.every(r=>r.status==="rejected"))setError("Backend is unreachable. Start FastAPI and verify frontend/.env.");
    setBusy(false);
  },[]);
  useEffect(()=>{refresh();const timer=setInterval(()=>refresh(false),30000);return()=>clearInterval(timer);},[refresh]);

  const counts={
    total:data.tasks.length,
    completed:data.tasks.filter(t=>["completed","success"].includes(statusOf(t))).length,
    running:data.tasks.filter(t=>["running","in_progress","processing"].includes(statusOf(t))).length,
    pending:data.tasks.filter(t=>["pending","queued","created"].includes(statusOf(t))).length,
    failed:data.tasks.filter(t=>["failed","error"].includes(statusOf(t))).length
  };
  async function submit(e){
    e.preventDefault();setError("");setNotice("");
    if(question.trim().length<5){setError("Enter at least 5 characters.");return;}
    setSubmitting(true);
    try{
      const created=await call("/research/tasks",{method:"POST",body:JSON.stringify({research_question:question.trim()})});
      const id=idOf(created)||idOf(created?.task)||idOf(created?.data);
      if(!id)throw new Error("Task created, but task ID was not found in the response. Check Task Manager.");
      await call(`/research/tasks/${encodeURIComponent(id)}/execute`,{method:"POST"});
      setNotice(`Task ${id} submitted for execution.`);setQuestion("");await refresh(false);setPage("tasks");
    }catch(e){setError(String(e.message||e));}finally{setSubmitting(false);}
  }
  async function execute(id){setError("");try{await call(`/research/tasks/${encodeURIComponent(id)}/execute`,{method:"POST"});setNotice(`Execution requested for ${id}.`);await refresh(false);}catch(e){setError(String(e.message||e));}}
  async function openReport(r){
    const filename=r.report_filename||r.filename||r.file_name;if(!filename){setError("Report filename missing.");return;}
    setReportName(filename);setReport("Loading...");
    try{const result=await call(`/research/reports/${encodeURIComponent(filename)}`);const content=result.content||result.report_content||result.report||result.markdown||result.text;setReport(typeof content==="string"?content:JSON.stringify(result,null,2));}
    catch(e){setReport(`Unable to load report: ${e.message}`);}
  }

  const navigation=<nav>{NAV.map(([key,name,Icon])=><button key={key} className={page===key?"active":""} onClick={()=>{setPage(key);setMenu(false);}}><Icon size={18}/>{name}</button>)}</nav>;
  const stat=(name,value,sub)=><div className="stat" key={name}><small>{name}</small><strong>{value}</strong><span>{sub}</span></div>;
  return <div className="app-shell">
    <aside className={`sidebar ${menu?"open":""}`}><div className="brand"><BrainCircuit/><span><b>AgenticLab</b><small>RESEARCH AUTOMATION</small></span><button className="close" onClick={()=>setMenu(false)}><X/></button></div><small className="caption">WORKSPACE</small>{navigation}<div className="side-status"><i className={connected?"online":"offline"}/>{connected?"Backend connected":"Backend offline"}</div></aside>
    {menu&&<button className="scrim" onClick={()=>setMenu(false)} aria-label="Close menu"/>}
    <main className="main"><header className="topbar"><button className="menu-button" onClick={()=>setMenu(true)}><Menu/></button><div><small>AI MULTI-AGENT SYSTEM</small><h1>{NAV.find(x=>x[0]===page)?.[1]}</h1></div><span className={connected?"online-text":"offline-text"}>{connected?"● API online":"● API offline"}</span><button className="refresh" onClick={()=>refresh()} disabled={busy}><RefreshCw size={17}/></button></header>
      {error&&<div className="alert error">{error}<button onClick={()=>setError("")}>Dismiss</button></div>}{notice&&<div className="alert success">{notice}<button onClick={()=>setNotice("")}>Dismiss</button></div>}
      {page==="dashboard"&&<section className="page"><div className="welcome"><div><small>COMMAND CENTER</small><h2>Your research operations, at a glance.</h2><p>Monitor tasks, agent activity, and generated reports.</p></div><button className="primary" onClick={()=>setPage("research")}>＋ Start research</button></div><div className="stats">{stat("Total tasks",counts.total,"Tasks in database")}{stat("Completed",counts.completed,"Successfully finished")}{stat("Running",counts.running,"Currently executing")}{stat("Failed",counts.failed,"Need review")}</div><div className="card"><h3>Recent research tasks</h3><p>Latest task records from FastAPI</p>{data.tasks.length?<div className="table-wrap"><table><thead><tr><th>Research question</th><th>Status</th><th>Created</th></tr></thead><tbody>{data.tasks.slice(0,8).map((t,i)=><tr key={idOf(t)||i}><td>{t.research_question||t.question||t.title||"Untitled"}</td><td><Badge value={statusOf(t)}/></td><td>{fmt(t.created_at||t.timestamp)}</td></tr>)}</tbody></table></div>:<Empty text="No tasks yet. Start a research workflow."/>}</div><div className="two"><div className="card"><h3>System status</h3><p>Live backend summary</p><div className="line"><span>API</span><Badge value={connected?"completed":"failed"}/></div><div className="line"><span>Pending tasks</span><b>{counts.pending}</b></div><div className="line"><span>Reports available</span><b>{data.reports.length}</b></div></div><div className="card"><h3>Recent agent activity</h3><p>Monitoring events</p>{data.activity.length?data.activity.slice(0,5).map((a,i)=><div className="line" key={a.log_id||i}><span>{label(a.agent_name)}</span><Badge value={a.status}/></div>):<Empty text="No agent activity recorded yet."/>}</div></div></section>}
      {page==="research"&&<section className="page narrow"><small>NEW WORKFLOW</small><h2>What should the agents research?</h2><p>Submit a question to create and execute a research task.</p><form className="card form" onSubmit={submit}><label htmlFor="rq">Research question</label><textarea id="rq" rows="7" maxLength="2000" minLength="5" value={question} onChange={e=>setQuestion(e.target.value)} placeholder="Example: Compare RAG and fine-tuning for enterprise knowledge assistants. Include strengths, limitations, costs, and recent sources." required/><div className="form-foot"><span>{question.length}/2000 characters</span><button className="primary" disabled={submitting||question.trim().length<5}>{submitting?"Submitting...":"Start research →"}</button></div><p className="hint">Uses POST /research/tasks, followed by POST /research/tasks/{'{task_id}'}/execute. Backend default priority is used.</p></form></section>}
      {page==="tasks"&&<section className="page"><small>WORKFLOW QUEUE</small><h2>Task manager</h2><p>Review tasks and execute pending or failed items.</p><div className="stats">{stat("Pending",counts.pending,"Waiting")}{stat("Running",counts.running,"Active")}{stat("Completed",counts.completed,"Finished")}{stat("Failed",counts.failed,"Review")}</div><div className="card"><h3>All research tasks</h3>{data.tasks.length?<div className="table-wrap"><table><thead><tr><th>Question</th><th>Task ID</th><th>Status</th><th>Created</th><th>Action</th></tr></thead><tbody>{data.tasks.map((t,i)=><tr key={idOf(t)||i}><td>{t.research_question||t.question||t.title||"Untitled"}</td><td>{(idOf(t)||"—").slice(0,12)}</td><td><Badge value={statusOf(t)}/></td><td>{fmt(t.created_at||t.timestamp)}</td><td>{idOf(t)&&["pending","queued","created","failed"].includes(statusOf(t))?<button className="mini" onClick={()=>execute(idOf(t))}>Execute</button>:"—"}</td></tr>)}</tbody></table></div>:<Empty text="No task records found."/>}</div></section>}
      {page==="agents"&&<section className="page"><small>AGENT OBSERVABILITY</small><h2>AI agent activity</h2><p>Agent metrics and latest execution logs.</p><div className="stats">{stat("Executions",data.agents?.total_executions??data.agents?.total_runs??"—","Recorded runs")}{stat("Successful",data.agents?.successful_executions??data.agents?.success_count??"—","Successful runs")}{stat("Failed",data.agents?.failed_executions??data.agents?.failure_count??"—","Failed runs")}{stat("Success rate",data.agents?.success_rate!=null?`${Number(data.agents.success_rate).toFixed(1)}%`:"—","Backend metric")}</div><div className="card"><h3>Agent logs</h3>{data.activity.length?<div className="table-wrap"><table><thead><tr><th>Agent</th><th>Task ID</th><th>Status</th><th>Duration</th><th>Error</th></tr></thead><tbody>{data.activity.map((a,i)=><tr key={a.log_id||i}><td>{label(a.agent_name)}</td><td>{(a.task_id||"—").slice(0,12)}</td><td><Badge value={a.status}/></td><td>{a.duration_seconds??"—"}</td><td>{a.error_message||"—"}</td></tr>)}</tbody></table></div>:<Empty text="No agent logs yet."/>}</div></section>}
      {page==="analytics"&&<section className="page"><small>PERFORMANCE INSIGHTS</small><h2>Workflow analytics</h2><p>Task distribution and backend workflow metrics.</p><div className="stats">{stat("Total",counts.total,"Tasks")}{stat("Completed",counts.completed,"Successful")}{stat("Pending",counts.pending,"Waiting")}{stat("Failed",counts.failed,"Errors")}</div><div className="card"><h3>Workflow statistics</h3><div className="line"><span>Total workflows</span><b>{data.workflow?.total_workflows??data.workflow?.total??"—"}</b></div><div className="line"><span>Completed</span><b>{data.workflow?.completed_workflows??data.workflow?.completed??"—"}</b></div><div className="line"><span>Failed</span><b>{data.workflow?.failed_workflows??data.workflow?.failed??"—"}</b></div><div className="line"><span>Success rate</span><b>{data.workflow?.success_rate!=null?`${data.workflow.success_rate}%`:"—"}</b></div></div></section>}
      {page==="reports"&&<section className="page"><small>GENERATED OUTPUT</small><h2>Research reports</h2><p>Preview and download generated research documents.</p><div className="two"><div className="card"><h3>Available reports</h3>{data.reports.length?data.reports.map((r,i)=><div className="report" key={r.report_filename||i}><button onClick={()=>openReport(r)}><FileText size={17}/><span>{r.research_question||r.report_filename||"Research report"}<small>Quality: {r.quality_score??"—"}</small></span></button>{r.report_filename&&<a href={`${API}/research/reports/${encodeURIComponent(r.report_filename)}/download`} target="_blank" rel="noreferrer">Download</a>}</div>):<Empty text="No reports available yet."/>}</div><div className="card"><h3>Report preview</h3><p>{reportName||"Select a report"}</p>{report?<div className="markdown"><ReactMarkdown remarkPlugins={[remarkGfm]}>{report}</ReactMarkdown></div>:<Empty text="Choose a report from the list."/>}</div></div></section>}
      {page==="history"&&<section className="page"><small>PAST WORK</small><h2>Research history</h2><p>Previously completed research tasks.</p><div className="card"><h3>History records</h3>{data.history.length?<div className="table-wrap"><table><thead><tr><th>Question</th><th>Status</th><th>Completed</th><th>Quality</th></tr></thead><tbody>{data.history.map((h,i)=><tr key={h.research_id||h.task_id||i}><td>{h.research_question||h.question||"Research record"}</td><td><Badge value={h.status||"completed"}/></td><td>{fmt(h.completed_at||h.updated_at||h.created_at)}</td><td>{h.quality_score??"—"}</td></tr>)}</tbody></table></div>:<Empty text="No history records returned."/>}</div></section>}
      {page==="settings"&&<section className="page narrow"><small>CONFIGURATION</small><h2>Connection settings</h2><p>Frontend API configuration and diagnostics.</p><div className="card"><div className="line"><span>API URL</span><code>{API}</code></div><div className="line"><span>Connection</span><Badge value={connected?"completed":"failed"}/></div><div className="line"><span>Health response</span><code>{data.health?JSON.stringify(data.health):"No response"}</code></div><p className="hint">Set VITE_API_URL=http://127.0.0.1:8000 in frontend/.env and restart Vite after changing it.</p></div></section>}
      <footer className="footer">AI Multi-Agent Research & Automation System <span>Auto-refresh every 30 seconds</span></footer>
    </main>
  </div>;
}
