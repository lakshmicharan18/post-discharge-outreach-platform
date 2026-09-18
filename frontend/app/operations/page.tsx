"use client";

import { useCallback, useEffect, useState } from "react";
import { Navigation } from "../../components/navigation";
import { api } from "../../lib/api";

type OperationsSummary = {
  queue: {
    effective_capacity: number;
    active_reserved_count: number;
    available_capacity: number;
    pending_count: number;
    approaching_deadline_count: number;
    deadline_missed_count: number;
  };
  workflows: {
    pending: number;
    processing: number;
    retry_scheduled: number;
    succeeded: number;
    failed: number;
  };
  recent_workflows: {
    id: string;
    event_type: string;
    status: string;
    attempt_count: number;
    max_attempts: number;
    next_attempt_at: string;
    processed_at: string | null;
    last_error_type: string | null;
    created_at: string;
  }[];
  escalations: { open: number; in_review: number; resolved: number; urgent_open: number };
  recent_escalations: {
    id: string;
    status: string;
    priority: string;
    assigned_reviewer_id: string | null;
    created_at: string;
    resolved_at: string | null;
  }[];
  notifications: { unread: number; urgent_unread: number };
  recent_notifications: {
    id: string;
    notification_type: string;
    title: string;
    severity: string;
    status: string;
    related_escalation_id: string | null;
    created_at: string;
  }[];
  ai_executions: { total: number; successful: number; failed: number; average_latency_ms: number | null };
  recent_ai_executions: {
    id: string;
    purpose: string;
    provider: string;
    model: string;
    prompt_version: string;
    latency_ms: number;
    success: boolean;
    input_tokens: number | null;
    output_tokens: number | null;
    error_type: string | null;
    created_at: string;
  }[];
};

function formatDate(value: string | null) {
  return value ? new Date(value).toLocaleString() : "—";
}

export default function OperationsPage() {
  const [summary, setSummary] = useState<OperationsSummary | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setSummary(await api<OperationsSummary>("operations/summary"));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to load operations summary.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return <main>
    <Navigation />
    <p className="eyebrow">HOSPITAL OPERATIONS</p>
    <h1>Operational overview</h1>
    <p className="intro">Tenant-scoped queue, workflow, escalation, notification, and AI execution status.</p>
    <div className="actions"><button className="secondary" onClick={() => void load()} disabled={loading}>Refresh</button></div>
    {error && <p role="alert">{error}</p>}
    {loading && !summary && <p role="status">Loading operations summary…</p>}
    {summary && <>
      <section>
        <h2>Overview</h2>
        <div className="metric-grid">
          <p><strong>{summary.queue.pending_count}</strong><span>Pending queue</span></p>
          <p><strong>{summary.queue.available_capacity}</strong><span>Available capacity</span></p>
          <p><strong>{summary.escalations.open}</strong><span>Open escalations</span></p>
          <p><strong>{summary.escalations.urgent_open}</strong><span>Urgent open escalations</span></p>
          <p><strong>{summary.notifications.unread}</strong><span>Unread notifications</span></p>
          <p><strong>{summary.workflows.failed}</strong><span>Failed workflow events</span></p>
          <p><strong>{summary.ai_executions.successful} / {summary.ai_executions.failed}</strong><span>AI success / failure</span></p>
          <p><strong>{summary.ai_executions.average_latency_ms ?? "—"}</strong><span>Average AI latency (ms)</span></p>
        </div>
      </section>

      <section>
        <h2>Workflow events</h2>
        {!summary.recent_workflows.length && <p>Not available yet.</p>}
        {!!summary.recent_workflows.length && <div className="table-wrap"><table><thead><tr><th>Type</th><th>Status</th><th>Attempts</th><th>Next attempt</th><th>Processed</th><th>Error type</th></tr></thead><tbody>
          {summary.recent_workflows.map((event) => <tr key={event.id}><td>{event.event_type}</td><td><span className="badge">{event.status}</span></td><td>{event.attempt_count} / {event.max_attempts}</td><td>{formatDate(event.next_attempt_at)}</td><td>{formatDate(event.processed_at)}</td><td>{event.last_error_type ?? "—"}</td></tr>)}
        </tbody></table></div>}
      </section>

      <section>
        <h2>Escalations</h2>
        {!summary.recent_escalations.length && <p>Not available yet.</p>}
        {!!summary.recent_escalations.length && <div className="table-wrap"><table><thead><tr><th>Status</th><th>Priority</th><th>Assigned reviewer</th><th>Created</th><th>Resolved</th></tr></thead><tbody>
          {summary.recent_escalations.map((item) => <tr key={item.id}><td><span className="badge">{item.status}</span></td><td>{item.priority}</td><td>{item.assigned_reviewer_id ?? "Unassigned"}</td><td>{formatDate(item.created_at)}</td><td>{formatDate(item.resolved_at)}</td></tr>)}
        </tbody></table></div>}
      </section>

      <section>
        <h2>Notifications</h2>
        {!summary.recent_notifications.length && <p>Not available yet.</p>}
        {!!summary.recent_notifications.length && <div className="table-wrap"><table><thead><tr><th>Title</th><th>Type</th><th>Severity</th><th>Status</th><th>Created</th></tr></thead><tbody>
          {summary.recent_notifications.map((item) => <tr key={item.id}><td>{item.title}</td><td>{item.notification_type}</td><td><span className="badge">{item.severity}</span></td><td>{item.status}</td><td>{formatDate(item.created_at)}</td></tr>)}
        </tbody></table></div>}
      </section>

      <section>
        <h2>Recent AI executions</h2>
        {!summary.recent_ai_executions.length && <p>Not available yet.</p>}
        {!!summary.recent_ai_executions.length && <div className="table-wrap"><table><thead><tr><th>Purpose</th><th>Provider / model</th><th>Prompt version</th><th>Result</th><th>Latency</th><th>Tokens</th><th>Created</th></tr></thead><tbody>
          {summary.recent_ai_executions.map((item) => <tr key={item.id}><td>{item.purpose}</td><td>{item.provider} / {item.model}</td><td>{item.prompt_version}</td><td><span className="badge">{item.success ? "SUCCESS" : "FAILED"}</span>{item.error_type ? ` (${item.error_type})` : ""}</td><td>{item.latency_ms} ms</td><td>{item.input_tokens ?? "—"} / {item.output_tokens ?? "—"}</td><td>{formatDate(item.created_at)}</td></tr>)}
        </tbody></table></div>}
      </section>
    </>}
  </main>;
}
