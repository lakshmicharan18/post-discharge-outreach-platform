"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Navigation } from "../../components/navigation";
import type { CurrentUser } from "../../lib/auth";
import { api } from "../../lib/api";
import { canManageCampaigns, Campaign, formatDate } from "../../lib/campaigns";

type QueueStatus = {
  effective_capacity: number;
  active_reserved_count: number;
  available_capacity: number;
  pending_count: number;
  oldest_pending_at: string | null;
  approaching_deadline_count: number;
  deadline_missed_count: number;
};

type Task = {
  id: string; campaign_id: string; patient_id: string; state: string; priority_score: number;
  priority_components: Record<string, number>; attempt_count: number; clinical_deadline: string;
  next_eligible_at: string; reserved_at: string | null;
};

type Patient = { id: string; first_name: string; last_name: string };

const taskLimit = 100;

function deadlineState(task: Task, now: number) {
  const deadline = Date.parse(task.clinical_deadline);
  if (deadline <= now) return "Deadline missed";
  if (deadline <= now + 6 * 60 * 60 * 1000) return "Approaching cutoff";
  return "Normal";
}

export default function QueuePage() {
  const [status, setStatus] = useState<QueueStatus | null>(null);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [patients, setPatients] = useState<Patient[]>([]);
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [state, setState] = useState("");
  const [campaign, setCampaign] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(true);
  const [reserving, setReserving] = useState(false);
  const canManage = canManageCampaigns(user?.role);

  const load = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const [nextStatus, nextCampaigns, nextPatients] = await Promise.all([
        api<QueueStatus>("queue/status"), api<Campaign[]>("campaigns?limit=100"), api<Patient[]>("patients?limit=100"),
      ]);
      const groups = await Promise.all(nextCampaigns.map((item) => api<Task[]>(`campaigns/${item.id}/outreach-tasks?limit=${taskLimit}`)));
      setStatus(nextStatus); setCampaigns(nextCampaigns); setPatients(nextPatients); setTasks(groups.flat());
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Unable to load queue operations."); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => {
    void load();
    fetch("/api/auth/me", { cache: "no-store" }).then((response) => response.ok ? response.json() : null).then(setUser).catch(() => setUser(null));
  }, [load]);

  const campaignNames = useMemo(() => new Map(campaigns.map((item) => [item.id, item.name])), [campaigns]);
  const patientNames = useMemo(() => new Map(patients.map((item) => [item.id, `${item.first_name} ${item.last_name}`])), [patients]);
  const visibleTasks = useMemo(() => tasks.filter((item) => (!state || item.state === state) && (!campaign || item.campaign_id === campaign)).sort((left, right) => Date.parse(left.clinical_deadline) - Date.parse(right.clinical_deadline) || right.priority_score - left.priority_score), [campaign, state, tasks]);
  const scheduled = tasks.filter((item) => item.state === "SCHEDULED").length;
  const utilization = status && status.effective_capacity ? Math.round(status.active_reserved_count / status.effective_capacity * 100) : 0;

  async function reserve(path: "queue/reserve-next" | "queue/reserve-available?limit=100") {
    setReserving(true); setError(""); setMessage("");
    try {
      const result = await api<Task | Task[] | null>(path, { method: "POST" });
      const count = Array.isArray(result) ? result.length : result ? 1 : 0;
      setMessage(count ? `Reserved ${count} task${count === 1 ? "" : "s"}.` : "No eligible task is available; capacity may be full or work may be deferred.");
      await load();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Unable to reserve queue work."); }
    finally { setReserving(false); }
  }

  return <main><Navigation /><p className="eyebrow">OUTBOUND OPERATIONS</p><h1>Queue</h1>
    <p className="intro">Milestone 5 schedules and reserves outreach work but does not execute calls.</p>
    {error && <p role="alert">{error}</p>}{message && <p role="status">{message}</p>}
    <div className="actions"><button className="secondary" onClick={() => void load()} disabled={loading}>Refresh</button>{canManage && <><button onClick={() => void reserve("queue/reserve-next")} disabled={reserving}>Reserve next</button><button onClick={() => void reserve("queue/reserve-available?limit=100")} disabled={reserving}>Fill available capacity</button></>}{user && !canManage && <span className="muted">Read-only queue visibility for your role.</span>}</div>
    {status && <><section><h2>Capacity</h2><div className="metric-grid"><p><strong>{status.effective_capacity}</strong><span>Configured capacity</span></p><p><strong>{status.active_reserved_count}</strong><span>Active / reserved</span></p><p><strong>{status.available_capacity}</strong><span>Available slots</span></p><p><strong>{utilization}%</strong><span>Utilization</span></p></div></section>
      <section><h2>Queue health</h2><div className="metric-grid"><p><strong>{status.pending_count}</strong><span>Pending</span></p><p><strong>{scheduled}</strong><span>Scheduled in loaded tasks</span></p><p><strong>{status.approaching_deadline_count}</strong><span>Approaching cutoff</span></p><p><strong>{status.deadline_missed_count}</strong><span>Deadline missed</span></p></div><p>Oldest pending work: {formatDate(status.oldest_pending_at)}.</p></section></>}
    <section><div className="section-heading"><h2>Outreach tasks</h2><div className="queue-filters"><label>State<select value={state} onChange={(event) => setState(event.target.value)}><option value="">All states</option>{[...new Set(tasks.map((item) => item.state))].sort().map((item) => <option key={item}>{item}</option>)}</select></label><label>Campaign<select value={campaign} onChange={(event) => setCampaign(event.target.value)}><option value="">All campaigns</option>{campaigns.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label></div></div>
      <p className="muted">Higher score = higher scheduling priority. Priority components are returned by the backend and are not recalculated here.</p>
      {loading && <p role="status">Loading queue tasks…</p>}{!loading && visibleTasks.length === 0 && <p>No outreach tasks match the current filters.</p>}
      {!loading && visibleTasks.length > 0 && <div className="table-wrap"><table><thead><tr><th>Patient</th><th>Campaign</th><th>State</th><th>Priority</th><th>Deadline</th><th>Next eligible</th><th>Attempts</th><th>Reserved</th></tr></thead><tbody>{visibleTasks.map((task) => <tr key={task.id} className={deadlineState(task, Date.now()) !== "Normal" ? "deadline-risk" : undefined}><td><Link href={`/patients/${task.patient_id}`}>{patientNames.get(task.patient_id) ?? task.patient_id}</Link></td><td><Link href={`/campaigns/${task.campaign_id}`}>{campaignNames.get(task.campaign_id) ?? task.campaign_id}</Link></td><td><span className="badge">{task.state}</span><br /><small>{deadlineState(task, Date.now())}</small></td><td><details><summary>{task.priority_score}</summary><ul className="priority-components">{Object.entries(task.priority_components).filter(([key]) => key !== "total").map(([key, value]) => <li key={key}>{key.replaceAll("_", " ")}: {value}</li>)}</ul></details></td><td>{formatDate(task.clinical_deadline)}</td><td>{formatDate(task.next_eligible_at)}</td><td>{task.attempt_count}</td><td>{formatDate(task.reserved_at)}</td></tr>)}</tbody></table></div>}</section>
  </main>;
}
