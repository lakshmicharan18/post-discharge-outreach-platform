"use client";

import Link from "next/link";
import { use, useCallback, useEffect, useState } from "react";
import type { CurrentUser } from "../../../lib/auth";
import { api } from "../../../lib/api";
import { canManageCampaigns, Campaign, EligibilityPage, Estimate, formatDate } from "../../../lib/campaigns";
import { Navigation } from "../../../components/navigation";

const pageSize = 25;
const terminal = new Set(["COMPLETED", "CANCELLED", "FAILED"]);

function CountList({ title, values }: { title: string; values: Record<string, number> }) {
  const entries = Object.entries(values);
  return <section className="compact-section"><h3>{title}</h3>{entries.length ? <ul>{entries.map(([key, value]) => <li key={key}><code>{key}</code>: {value}</li>)}</ul> : <p>None.</p>}</section>;
}

export default function CampaignDetail({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [campaign, setCampaign] = useState<Campaign | null>(null);
  const [estimate, setEstimate] = useState<Estimate | null>(null);
  const [eligibility, setEligibility] = useState<EligibilityPage | null>(null);
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [filter, setFilter] = useState<"" | "true" | "false">("");
  const [offset, setOffset] = useState(0);
  const [scheduleAt, setScheduleAt] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(true);
  const canManage = canManageCampaigns(user?.role);

  const load = useCallback(async (nextOffset = offset, nextFilter = filter) => {
    setLoading(true); setError("");
    try {
      const query = new URLSearchParams({ limit: String(pageSize), offset: String(nextOffset) });
      if (nextFilter) query.set("eligible", nextFilter);
      const [nextCampaign, nextEstimate, nextEligibility] = await Promise.all([
        api<Campaign>(`campaigns/${id}`), api<Estimate>(`campaigns/${id}/estimate`), api<EligibilityPage>(`campaigns/${id}/eligibility?${query}`),
      ]);
      setCampaign(nextCampaign); setEstimate(nextEstimate); setEligibility(nextEligibility);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Unable to load campaign."); }
    finally { setLoading(false); }
  }, [filter, id, offset]);

  useEffect(() => {
    void load();
    fetch("/api/auth/me", { cache: "no-store" }).then((response) => response.ok ? response.json() : null).then(setUser).catch(() => setUser(null));
  }, [load]);

  async function action(name: "ready" | "schedule" | "start" | "pause" | "resume" | "complete" | "cancel") {
    setError(""); setMessage("");
    try {
      const init: RequestInit = { method: "POST" };
      if (name === "schedule") {
        if (!scheduleAt) throw new Error("Choose a scheduled start time first.");
        init.headers = { "Content-Type": "application/json" };
        init.body = JSON.stringify({ start_at: new Date(scheduleAt).toISOString() });
      }
      const updated = await api<Campaign>(`campaigns/${id}/${name}`, init);
      setCampaign(updated); setMessage(`Campaign is now ${updated.status}.`);
      await load(0, filter); setOffset(0);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Campaign action failed."); }
  }
  function changeFilter(value: "" | "true" | "false") { setFilter(value); setOffset(0); void load(0, value); }
  function changePage(next: number) { setOffset(next); void load(next, filter); }

  const status = campaign?.status;
  return <main><Navigation />
    {error && <p role="alert">{error}</p>}{message && <p role="status">{message}</p>}
    {!campaign && !error && <p role="status">Loading campaign…</p>}
    {campaign && <><p className="eyebrow">CAMPAIGN OPERATIONS</p><h1>{campaign.name}</h1><p><span className="badge">{campaign.status}</span></p>
      {campaign.description && <p className="intro">{campaign.description}</p>}
      <section><h2>Configuration</h2><dl className="definition-grid"><dt>Priority</dt><dd>{campaign.campaign_priority ?? "—"}</dd><dt>Campaign dates</dt><dd>{formatDate(campaign.start_at)} — {formatDate(campaign.end_at)}</dd><dt>Calling window</dt><dd>{campaign.calling_window_start ?? "—"} – {campaign.calling_window_end ?? "—"}</dd><dt>Follow-up window</dt><dd>{campaign.clinical_follow_up_hours ?? "—"} hours</dd><dt>Max retries</dt><dd>{campaign.max_retries ?? "—"}</dd><dt>Outbound capacity</dt><dd>{campaign.outbound_capacity ?? "Hospital default"}</dd><dt>Updated</dt><dd>{formatDate(campaign.updated_at)}</dd></dl></section>
      <section><h2>Workload estimate</h2>{!estimate && <p role="status">Loading estimate…</p>}{estimate && <><div className="metric-grid"><p><strong>{estimate.total_evaluated}</strong><span>Evaluated</span></p><p><strong>{estimate.eligible_patients}</strong><span>Eligible</span></p><p><strong>{estimate.ineligible_patients}</strong><span>Ineligible</span></p><p><strong>{estimate.estimated_outreach_attempts}</strong><span>Estimated attempts</span></p></div><div className="two-columns"><CountList title="Eligible by risk" values={estimate.by_risk_level}/><CountList title="Ineligibility reasons" values={estimate.by_ineligibility_reason}/></div></>}</section>
      {canManage && status && !terminal.has(status) && <section><h2>Lifecycle actions</h2><div className="actions">
        {status === "DRAFT" && <button onClick={() => void action("ready")}>Mark ready</button>}
        {status === "READY" && <><label>Schedule start<input type="datetime-local" value={scheduleAt} onChange={(event) => setScheduleAt(event.target.value)}/></label><button onClick={() => void action("schedule")}>Schedule</button><button onClick={() => void action("start")}>Start now</button></>}
        {status === "SCHEDULED" && <button onClick={() => void action("start")}>Start</button>}
        {status === "RUNNING" && <><button onClick={() => void action("pause")}>Pause</button><button onClick={() => void action("complete")}>Complete</button></>}
        {status === "PAUSED" && <button onClick={() => void action("resume")}>Resume</button>}
        <button className="secondary" onClick={() => void action("cancel")}>Cancel campaign</button>
      </div></section>}
      {user && !canManage && <p>Campaign lifecycle actions are unavailable for your role.</p>}
      <section><div className="section-heading"><h2>Eligibility</h2><label>Show<select value={filter} onChange={(event) => changeFilter(event.target.value as "" | "true" | "false")}><option value="">All</option><option value="true">Eligible</option><option value="false">Ineligible</option></select></label></div>
        {loading && <p role="status">Loading eligibility…</p>}{eligibility && !loading && <><p>{eligibility.total} result{eligibility.total === 1 ? "" : "s"}.</p><div className="table-wrap"><table><thead><tr><th>Patient</th><th>Status</th><th>Risk</th><th>Care setting</th><th>Follow-up deadline</th><th>Reasons</th></tr></thead><tbody>{eligibility.items.map((item) => <tr key={item.discharge_id}><td><Link href={`/patients/${item.patient_id}`}>{item.patient_id}</Link></td><td><span className="badge">{item.eligible ? "ELIGIBLE" : "INELIGIBLE"}</span></td><td>{item.risk_level}</td><td>{item.care_setting}</td><td>{formatDate(item.follow_up_deadline)}</td><td>{item.reasons.length ? item.reasons.map((reason) => <code className="reason" key={reason}>{reason}</code>) : "—"}</td></tr>)}</tbody></table></div>{eligibility.items.length === 0 && <p>No results match this filter.</p>}<div className="pagination"><button className="secondary" disabled={offset === 0} onClick={() => changePage(Math.max(0, offset - pageSize))}>Previous</button><span>{offset + 1}–{Math.min(offset + pageSize, eligibility.total)} of {eligibility.total}</span><button className="secondary" disabled={offset + pageSize >= eligibility.total} onClick={() => changePage(offset + pageSize)}>Next</button></div></>}</section>
      <p className="muted">Campaign activation does not yet create or schedule outbound work. Queue creation and scheduling are implemented in Milestone 5.</p>
    </>}
  </main>;
}
