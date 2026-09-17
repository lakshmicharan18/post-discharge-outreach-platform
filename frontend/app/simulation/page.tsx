"use client";

import { useCallback, useEffect, useState } from "react";
import { Navigation } from "../../components/navigation";
import type { CurrentUser } from "../../lib/auth";
import { api } from "../../lib/api";
import { canManageCampaigns, formatDate } from "../../lib/campaigns";
import type { SimulationEvent, SimulationRun, SimulationSummary, SimulationTask } from "../../lib/simulation";

const metricLabels: [keyof SimulationSummary, string][] = [
  ["total_tasks", "Total tasks"], ["completed", "Completed"], ["pending", "Pending"],
  ["active", "Active"], ["retry_scheduled", "Retry scheduled"], ["callback_scheduled", "Callback scheduled"],
  ["manual_follow_up", "Manual follow-up"], ["failed", "Failed"], ["total_attempts", "Total attempts"],
  ["simulation_event_count", "Events"], ["total_simulation_steps", "Simulation steps"],
  ["simulated_duration_minutes", "Simulated minutes"],
];

function details(payload: Record<string, unknown>) {
  const items = Object.entries(payload).filter(([, value]) => typeof value !== "object");
  return items.length ? items.map(([key, value]) => `${key.replaceAll("_", " ")}: ${String(value)}`).join(" · ") : "—";
}

export default function SimulationPage() {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [run, setRun] = useState<SimulationRun | null>(null);
  const [summary, setSummary] = useState<SimulationSummary | null>(null);
  const [tasks, setTasks] = useState<SimulationTask[]>([]);
  const [events, setEvents] = useState<SimulationEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [acting, setActing] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const canManage = canManageCampaigns(user?.role);

  const load = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const nextRun = await api<SimulationRun>("simulation/status");
      const [nextSummary, nextTasks, nextEvents] = await Promise.all([
        api<SimulationSummary>(`simulation/${nextRun.id}/summary`),
        api<SimulationTask[]>(`simulation/${nextRun.id}/tasks`),
        api<SimulationEvent[]>(`simulation/${nextRun.id}/events`),
      ]);
      setRun(nextRun); setSummary(nextSummary); setTasks(nextTasks); setEvents(nextEvents);
    } catch (cause) {
      setRun(null); setSummary(null); setTasks([]); setEvents([]);
      const text = cause instanceof Error ? cause.message : "Unable to load simulation.";
      if (!text.toLowerCase().includes("not been initialized")) setError(text);
    } finally { setLoading(false); }
  }, []);

  useEffect(() => {
    void load();
    fetch("/api/auth/me", { cache: "no-store" }).then((response) => response.ok ? response.json() : null).then(setUser).catch(() => setUser(null));
  }, [load]);

  async function action(path: string, label: string) {
    setActing(true); setError(""); setMessage("");
    try {
      await api(path, { method: "POST" });
      setMessage(label); await load();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Simulation action failed."); }
    finally { setActing(false); }
  }

  const disabled = acting || !canManage || user?.role === "PLATFORM_ADMIN";
  return <main><Navigation /><p className="eyebrow">DETERMINISTIC QUEUE DEMO</p><h1>Simulation</h1>
    <p className="intro">A safe, synthetic 25-patient demonstration using the production scheduling and outcome rules.</p>
    {error && <p role="alert">{error}</p>}{message && <p role="status">{message}</p>}
    <section><h2>Controls</h2><div className="actions">
      <button onClick={() => void action("simulation/initialize", "Scenario initialized.")} disabled={disabled}>Initialize scenario</button>
      <button className="secondary" onClick={() => void action("simulation/reset", "Scenario reset to its fixed start time.")} disabled={disabled}>Reset scenario</button>
      <button onClick={() => run && void action(`simulation/${run.id}/step`, "Simulation step completed.")} disabled={disabled || !run}>Step once</button>
      <button onClick={() => run && void action(`simulation/${run.id}/advance-next`, "Clock advanced to the next actionable time.")} disabled={disabled || !run}>Advance next</button>
      <button onClick={() => run && void action(`simulation/${run.id}/run`, "Simulation ran to completion.")} disabled={disabled || !run}>Run to completion</button>
      <button className="secondary" onClick={() => void load()} disabled={loading || acting}>Refresh</button>
    </div>{user && !canManage && <p className="muted">Simulation controls are read-only for your role.</p>}</section>
    {loading && <p role="status">Loading simulation…</p>}
    {run && <><section><h2>Run status</h2><div className="metric-grid"><p><strong>{summary?.status ?? "—"}</strong><span>Run status</span></p><p><strong>{formatDate(run.simulated_now)}</strong><span>Simulated clock</span></p><p><strong>{run.configured_capacity}</strong><span>Capacity</span></p><p className={summary?.capacity_exceeded ? "deadline-risk" : ""}><strong>{summary?.capacity_exceeded ? "Exceeded" : "Safe"}</strong><span>Capacity safety</span></p></div></section>
    {summary && <><section><h2>Queue and final results</h2><div className="metric-grid">{metricLabels.map(([key, label]) => <p key={String(key)}><strong>{String(summary[key])}</strong><span>{label}</span></p>)}</div><p>Maximum observed active calls: {summary.max_observed_active_calls}. Capacity never exceeded: {summary.capacity_exceeded ? "No" : "Yes"}.</p></section>
    <section><div className="two-columns"><div><h2>Outcome distribution</h2><ul>{Object.entries(summary.outcome_counts).sort().map(([outcome, count]) => <li key={outcome}><strong>{outcome}</strong>: {count}</li>)}</ul></div><div><h2>Clock</h2><p>Started: {formatDate(summary.simulated_start_time)}</p><p>Current: {formatDate(summary.simulated_now)}</p><p>Duration: {summary.simulated_duration_minutes} minutes</p></div></div></section></>}
    <section><h2>Synthetic queue tasks</h2>{tasks.length === 0 ? <p>No initialized scenario tasks.</p> : <div className="table-wrap"><table><thead><tr><th>Scenario</th><th>Risk</th><th>State</th><th>Attempts</th><th>Priority</th><th>Next eligible</th><th>Deadline</th><th>Last outcome</th></tr></thead><tbody>{tasks.map((task) => <tr key={task.scenario_key}><td>{task.scenario_key}</td><td>{task.risk}</td><td><span className="badge">{task.state}</span></td><td>{task.attempt_count}</td><td>{task.priority_score}</td><td>{formatDate(task.next_eligible_at)}</td><td>{formatDate(task.clinical_deadline)}</td><td>{task.last_outcome ?? "—"}</td></tr>)}</tbody></table></div>}</section>
    <section><h2>Event timeline</h2>{events.length === 0 ? <p>No events yet.</p> : <div className="table-wrap"><table><thead><tr><th>Sequence</th><th>Simulated time</th><th>Event</th><th>Safe details</th></tr></thead><tbody>{events.map((event) => <tr key={event.sequence_number}><td>{event.sequence_number}</td><td>{formatDate(event.simulated_at)}</td><td><span className="badge">{event.event_type}</span></td><td>{details(event.safe_payload)}</td></tr>)}</tbody></table></div>}</section></>}
  </main>;
}
