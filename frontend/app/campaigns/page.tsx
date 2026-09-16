"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import type { CurrentUser } from "../../lib/auth";
import { api } from "../../lib/api";
import { asIso, canManageCampaigns, Campaign, formatDate } from "../../lib/campaigns";
import { Navigation } from "../../components/navigation";
import { useRouter } from "next/navigation";

type FormState = {
  name: string; description: string; start_at: string; end_at: string; follow_up_hours: string;
  calling_start: string; calling_end: string; priority: string; max_retries: string; outbound_capacity: string;
  risk_levels: string[]; care_settings: string[]; discharge_after: string; discharge_before: string;
  condition_codes: string; communication_eligible: boolean; preferences: string;
};

const initialForm: FormState = {
  name: "", description: "", start_at: "", end_at: "", follow_up_hours: "72", calling_start: "09:00",
  calling_end: "17:00", priority: "50", max_retries: "3", outbound_capacity: "", risk_levels: [],
  care_settings: [], discharge_after: "", discharge_before: "", condition_codes: "", communication_eligible: false,
  preferences: "{}",
};

function ToggleGroup({ label, values, selected, onChange }: { label: string; values: string[]; selected: string[]; onChange: (next: string[]) => void }) {
  return <fieldset className="toggle-group"><legend>{label}</legend>{values.map((value) => <label key={value} className="checkbox">
    <input type="checkbox" checked={selected.includes(value)} onChange={(event) => onChange(event.target.checked ? [...selected, value] : selected.filter((item) => item !== value))}/>{value}
  </label>)}</fieldset>;
}

export default function CampaignsPage() {
  const router = useRouter();
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [form, setForm] = useState(initialForm);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(true);
  const canManage = canManageCampaigns(user?.role);

  async function load() {
    setLoading(true); setError("");
    try { setCampaigns(await api<Campaign[]>("campaigns?limit=100")); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Unable to load campaigns."); }
    finally { setLoading(false); }
  }
  useEffect(() => {
    void load();
    fetch("/api/auth/me", { cache: "no-store" }).then((response) => response.ok ? response.json() : null).then(setUser).catch(() => setUser(null));
  }, []);
  function change(field: keyof FormState, value: string | boolean | string[]) { setForm((current) => ({ ...current, [field]: value })); }
  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError(""); setMessage("");
    try {
      const preferences = JSON.parse(form.preferences) as Record<string, boolean>;
      const campaign = await api<Campaign>("campaigns", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({
          name: form.name, description: form.description || null, start_at: asIso(form.start_at), end_at: asIso(form.end_at),
          clinical_follow_up_hours: Number(form.follow_up_hours), calling_window_start: form.calling_start,
          calling_window_end: form.calling_end, campaign_priority: Number(form.priority), max_retries: Number(form.max_retries),
          outbound_capacity: form.outbound_capacity ? Number(form.outbound_capacity) : null,
          eligibility_criteria: {
            risk_levels: form.risk_levels, care_settings: form.care_settings, discharge_after: asIso(form.discharge_after),
            discharge_before: asIso(form.discharge_before), condition_codes: form.condition_codes.split(",").map((code) => code.trim()).filter(Boolean),
            communication_eligible: form.communication_eligible || null, required_communication_preferences: preferences,
          },
        }),
      });
      router.push(`/campaigns/${campaign.id}`);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Campaign creation failed."); }
  }

  return <main><Navigation /><p className="eyebrow">CAMPAIGN OPERATIONS</p><h1>Campaigns</h1>
    <p>Campaign activation validates configuration and evaluates current eligibility. It does not create outbound work yet.</p>
    {error && <p role="alert">{error}</p>}{message && <p role="status">{message}</p>}
    <section><h2>Your hospital campaigns</h2>{loading && <p role="status">Loading campaigns…</p>}
      {!loading && !error && campaigns.length === 0 && <p>No campaigns have been created for this hospital.</p>}
      {campaigns.length > 0 && <div className="table-wrap"><table><thead><tr><th>Name</th><th>Status</th><th>Priority</th><th>Dates</th><th>Calling window</th><th>Updated</th></tr></thead><tbody>
        {campaigns.map((campaign) => <tr key={campaign.id}><td><Link href={`/campaigns/${campaign.id}`}>{campaign.name}</Link></td><td><span className="badge">{campaign.status}</span></td><td>{campaign.campaign_priority ?? "—"}</td><td>{formatDate(campaign.start_at)} — {formatDate(campaign.end_at)}</td><td>{campaign.calling_window_start ?? "—"} – {campaign.calling_window_end ?? "—"}</td><td>{formatDate(campaign.updated_at)}</td></tr>)}
      </tbody></table></div>}</section>
    {canManage && <section><h2>Create campaign</h2><form className="wide-form" onSubmit={create}><fieldset>
      <label>Name<input required value={form.name} onChange={(event) => change("name", event.target.value)}/></label>
      <label>Description<textarea rows={3} value={form.description} onChange={(event) => change("description", event.target.value)}/></label>
      <div className="form-grid"><label>Campaign start<input type="datetime-local" value={form.start_at} onChange={(event) => change("start_at", event.target.value)}/></label><label>Campaign end<input type="datetime-local" value={form.end_at} onChange={(event) => change("end_at", event.target.value)}/></label>
      <label>Follow-up hours<input required min="1" max="720" type="number" value={form.follow_up_hours} onChange={(event) => change("follow_up_hours", event.target.value)}/></label><label>Priority (1–100)<input required min="1" max="100" type="number" value={form.priority} onChange={(event) => change("priority", event.target.value)}/></label>
      <label>Calling start<input required type="time" value={form.calling_start} onChange={(event) => change("calling_start", event.target.value)}/></label><label>Calling end<input required type="time" value={form.calling_end} onChange={(event) => change("calling_end", event.target.value)}/></label>
      <label>Max retries<input required min="0" max="20" type="number" value={form.max_retries} onChange={(event) => change("max_retries", event.target.value)}/></label><label>Outbound capacity (optional)<input min="1" type="number" value={form.outbound_capacity} onChange={(event) => change("outbound_capacity", event.target.value)}/></label></div>
      <h3>Eligibility criteria</h3><ToggleGroup label="Risk levels" values={["LOW", "MEDIUM", "HIGH", "UNKNOWN"]} selected={form.risk_levels} onChange={(value) => change("risk_levels", value)}/><ToggleGroup label="Care settings" values={["INPATIENT", "OUTPATIENT", "EMERGENCY"]} selected={form.care_settings} onChange={(value) => change("care_settings", value)}/>
      <div className="form-grid"><label>Discharged after<input type="datetime-local" value={form.discharge_after} onChange={(event) => change("discharge_after", event.target.value)}/></label><label>Discharged before<input type="datetime-local" value={form.discharge_before} onChange={(event) => change("discharge_before", event.target.value)}/></label></div>
      <label>Condition codes (comma-separated)<input value={form.condition_codes} onChange={(event) => change("condition_codes", event.target.value)} placeholder="I10, E11"/></label>
      <label className="checkbox"><input type="checkbox" checked={form.communication_eligible} onChange={(event) => change("communication_eligible", event.target.checked)}/> Require communication eligibility</label>
      <label>Required communication preferences (JSON object)<textarea rows={2} value={form.preferences} onChange={(event) => change("preferences", event.target.value)} placeholder='{"voice": true}'/></label>
      <button type="submit">Create campaign</button>
    </fieldset></form></section>}
    {user && !canManage && <p>Campaign creation is read-only for your role.</p>}
  </main>;
}
