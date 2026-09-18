"use client";

import Link from "next/link";
import { use, useEffect, useState } from "react";
import { Navigation } from "../../../components/navigation";
import { api } from "../../../lib/api";

interface Context {
  patient: Record<string, unknown> & { first_name: string; last_name: string; external_patient_id: string };
  encounters: Array<Record<string, unknown>>;
  discharges: Array<Record<string, unknown>>;
  conditions: Array<Record<string, unknown>>;
  observations: Array<Record<string, unknown>>;
  medications: Array<Record<string, unknown>>;
  care_plans: Array<Record<string, unknown>>;
  procedures: Array<Record<string, unknown>>;
  timeline: Array<{ occurred_at: string; event_type: string; title: string; summary: string | null }>;
}

function ResourceSection({ title, records }: { title: string; records: Array<Record<string, unknown>> }) {
  return <section><h2>{title}</h2>{records.length ? records.map((record, index) =>
    <pre key={String(record.id || index)}>{JSON.stringify(record, null, 2)}</pre>) : <p>No records.</p>}</section>;
}

export default function PatientDetail({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [context, setContext] = useState<Context | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { api<Context>(`patients/${id}/context`).then(setContext).catch((e) => setError(e.message)); }, [id]);
  return <main>
    <Navigation />
    {error && <p role="alert">{error}</p>}
    {!context && !error && <p role="status">Loading patient context…</p>}
    {context && <>
      <p className="eyebrow">{context.patient.external_patient_id}</p>
      <h1>{context.patient.first_name} {context.patient.last_name}</h1>
      <p><Link href={`/patients/${id}/ai-workflow`}>View AI workflow activity</Link></p>
      <ResourceSection title="Demographics" records={[context.patient]} />
      <ResourceSection title="Encounters" records={context.encounters} />
      <ResourceSection title="Discharges" records={context.discharges} />
      <ResourceSection title="Conditions" records={context.conditions} />
      <ResourceSection title="Observations" records={context.observations} />
      <ResourceSection title="Medications" records={context.medications} />
      <ResourceSection title="Care plans" records={context.care_plans} />
      <ResourceSection title="Procedures" records={context.procedures} />
      <section><h2>Timeline</h2><ol className="timeline">{context.timeline.map((event, index) =>
        <li key={`${event.occurred_at}-${index}`}><time>{new Date(event.occurred_at).toLocaleString()}</time>
          <strong>{event.title}</strong><span>{event.summary || event.event_type}</span></li>)}</ol></section>
    </>}
  </main>;
}
