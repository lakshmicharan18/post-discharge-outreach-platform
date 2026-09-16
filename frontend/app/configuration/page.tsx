"use client";

import { FormEvent, useEffect, useState } from "react";
import { Navigation } from "../../components/navigation";
import { api } from "../../lib/api";

interface Configuration {
  timezone: string; calling_window_start: string; calling_window_end: string;
  default_follow_up_hours: number; max_concurrent_calls: number; default_max_retries: number;
  retry_initial_delay_minutes: number; retry_backoff_multiplier: string;
  notification_preferences: Record<string, boolean>; escalation_contacts: Array<Record<string, string>>;
  ehr_settings: Record<string, string | boolean>; is_ready: boolean;
}

export default function ConfigurationPage() {
  const [configuration, setConfiguration] = useState<Configuration | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [canEdit, setCanEdit] = useState(false);
  useEffect(() => {
    api<Configuration>("hospital/configuration").then(setConfiguration).catch((e) => setError(e.message));
    fetch("/api/auth/me", { cache: "no-store" }).then((response) => response.json())
      .then((user) => setCanEdit(user.role === "HOSPITAL_ADMIN")).catch(() => setCanEdit(false));
  }, []);
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!configuration) return;
    setError(""); setMessage("");
    try {
      setConfiguration(await api<Configuration>("hospital/configuration", {
        method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(configuration),
      }));
      setMessage("Configuration saved.");
    } catch (e) { setError(e instanceof Error ? e.message : "Save failed."); }
  }
  function number(field: keyof Configuration, value: string) {
    setConfiguration((current) => current ? { ...current, [field]: Number(value) } : current);
  }
  return <main><Navigation /><p className="eyebrow">HOSPITAL OPERATIONS</p><h1>Configuration</h1>
    {error && <p role="alert">{error}</p>}{message && <p role="status">{message}</p>}
    {configuration && <form className="wide-form" onSubmit={save}><fieldset disabled={!canEdit}>
      <label>Timezone<input value={configuration.timezone} onChange={(e) => setConfiguration({...configuration, timezone:e.target.value})}/></label>
      <label>Calling start<input type="time" value={configuration.calling_window_start.slice(0,5)} onChange={(e) => setConfiguration({...configuration, calling_window_start:e.target.value})}/></label>
      <label>Calling end<input type="time" value={configuration.calling_window_end.slice(0,5)} onChange={(e) => setConfiguration({...configuration, calling_window_end:e.target.value})}/></label>
      <label>Follow-up hours<input type="number" min="1" value={configuration.default_follow_up_hours} onChange={(e) => number("default_follow_up_hours",e.target.value)}/></label>
      <label>Concurrent calls<input type="number" min="1" value={configuration.max_concurrent_calls} onChange={(e) => number("max_concurrent_calls",e.target.value)}/></label>
      <label>Max retries<input type="number" min="0" value={configuration.default_max_retries} onChange={(e) => number("default_max_retries",e.target.value)}/></label>
      <label>Initial retry delay (minutes)<input type="number" min="1" value={configuration.retry_initial_delay_minutes} onChange={(e) => number("retry_initial_delay_minutes",e.target.value)}/></label>
      <label>Backoff multiplier<input type="number" min="1" step="0.1" value={configuration.retry_backoff_multiplier} onChange={(e) => setConfiguration({...configuration,retry_backoff_multiplier:e.target.value})}/></label>
      <label className="checkbox"><input type="checkbox" checked={configuration.is_ready} onChange={(e) => setConfiguration({...configuration,is_ready:e.target.checked})}/> Ready for operations</label>
      <button type="submit">Save configuration</button>
    </fieldset></form>}
    {configuration && !canEdit && <p>Configuration is read-only for your role.</p>}
  </main>;
}
