"use client";

import Link from "next/link";
import { use, useEffect, useState } from "react";
import { Navigation } from "../../../../components/navigation";
import { api } from "../../../../lib/api";

type RecordData = Record<string, unknown>;

interface PatientContext {
  patient: RecordData & {
    first_name: string;
    last_name: string;
    external_patient_id: string;
    preferred_language?: string;
  };
  encounters: RecordData[];
  discharges: RecordData[];
}

function text(record: RecordData, key: string) {
  const value = record[key];
  return typeof value === "string" || typeof value === "number" ? String(value) : "—";
}

function formatDate(value: unknown) {
  return typeof value === "string" ? new Date(value).toLocaleString() : "—";
}

export default function PatientAIWorkflowPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [context, setContext] = useState<PatientContext | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api<PatientContext>(`patients/${id}/context`).then(setContext).catch((reason: Error) => {
      setError(reason.message);
    });
  }, [id]);

  return <main>
    <Navigation />
    <Link href={`/patients/${id}`}>← Back to patient detail</Link>
    <p className="eyebrow">AI WORKFLOW ACTIVITY</p>
    <h1>Patient workflow</h1>
    {error && <p role="alert">{error}</p>}
    {!context && !error && <p role="status">Loading patient context…</p>}
    {context && <>
      <section>
        <h2>Patient context</h2>
        <dl className="definition-grid">
          <dt>Patient</dt><dd>{context.patient.first_name} {context.patient.last_name}</dd>
          <dt>Identifier</dt><dd>{context.patient.external_patient_id}</dd>
          <dt>Preferred language</dt><dd>{context.patient.preferred_language || "—"}</dd>
          <dt>Encounters</dt><dd>{context.encounters.length}</dd>
          <dt>Discharges</dt><dd>{context.discharges.length}</dd>
        </dl>
      </section>
      <section>
        <h2>Discharge context</h2>
        {context.discharges.length === 0 && <p>No discharge context is available.</p>}
        {context.discharges.length > 0 && <div className="table-wrap"><table><thead><tr><th>Discharged</th><th>Follow-up deadline</th><th>Status</th></tr></thead><tbody>
          {context.discharges.map((discharge, index) => <tr key={String(discharge.id || index)}>
            <td>{formatDate(discharge.discharge_at)}</td>
            <td>{formatDate(discharge.follow_up_deadline)}</td>
            <td>{text(discharge, "status")}</td>
          </tr>)}
        </tbody></table></div>}
      </section>
    </>}
  </main>;
}
