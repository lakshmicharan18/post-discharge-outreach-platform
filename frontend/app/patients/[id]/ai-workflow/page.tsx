"use client";

import Link from "next/link";
import { use, useEffect, useState } from "react";
import { Navigation } from "../../../../components/navigation";
import { api } from "../../../../lib/api";

type AssessmentDetails = {
  patient_reported_findings?: unknown;
  clinical_context_facts?: unknown;
  protocol_references?: unknown;
  missing_information?: unknown;
  recommended_next_action?: unknown;
};

type Assessment = {
  id: string;
  classification: string;
  requires_human_review: boolean;
  assessment: AssessmentDetails;
  created_at: string;
};

interface PatientAIWorkflow {
  patient: {
    id: string;
    first_name: string;
    last_name: string;
    external_patient_id: string;
    preferred_language: string;
  };
  latest_encounter: {
    care_setting: string;
  } | null;
  latest_discharge: {
    discharge_at: string;
    follow_up_deadline: string;
    risk_level: string;
  } | null;
  voice_intake: {
    id: string;
    current_stage: string;
    status: string;
    captured_information: Record<string, unknown>;
    completed_at: string | null;
  } | null;
  triage_assessment: Assessment | null;
  independent_assessments: Assessment[];
  consensus: {
    final_classification: string;
    agreement_status: string;
    requires_human_review: boolean;
    disagreement_reason: string | null;
    recommended_action: string;
    created_at: string;
  } | null;
  escalation: {
    status: string;
    priority: string;
    assigned_reviewer_id: string | null;
    resolution: string | null;
    created_at: string;
    resolved_at: string | null;
  } | null;
  notification: {
    notification_type: string;
    severity: string;
    status: string;
    created_at: string;
    read_at: string | null;
    acknowledged_at: string | null;
  } | null;
  mock_ehr_operation: {
    operation_type: string;
    status: string;
    completed_at: string | null;
    created_at: string;
  };
}

function formatDate(value: string | null | undefined) {
  return value ? new Date(value).toLocaleString() : "—";
}

function values(value: unknown): string[] {
  if (Array.isArray(value)) return value.filter((item): item is string => typeof item === "string");
  return typeof value === "string" ? [value] : [];
}

function DetailList({ label, value }: { label: string; value: unknown }) {
  const items = values(value);
  if (!items.length) return null;
  return <><dt>{label}</dt><dd>{items.join("; ")}</dd></>;
}

function AssessmentCard({ assessment, label }: { assessment: Assessment; label: string }) {
  const details = assessment.assessment;
  return <section>
    <p className="eyebrow">{label}</p>
    <h3><span className="badge">{assessment.classification}</span></h3>
    <dl className="definition-grid">
      <DetailList label="Patient-reported findings" value={details.patient_reported_findings} />
      <DetailList label="Clinical context" value={details.clinical_context_facts} />
      <DetailList label="Protocol references" value={details.protocol_references} />
      <DetailList label="Missing information" value={details.missing_information} />
      <DetailList label="Recommended action" value={details.recommended_next_action} />
      <dt>Human review</dt><dd>{assessment.requires_human_review ? "Required" : "Not required"}</dd>
      <dt>Recorded</dt><dd>{formatDate(assessment.created_at)}</dd>
    </dl>
  </section>;
}

export default function PatientAIWorkflowPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [workflow, setWorkflow] = useState<PatientAIWorkflow | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api<PatientAIWorkflow>(`patients/${id}/ai-workflow`).then(setWorkflow).catch((reason: Error) => {
      setError(reason.message);
    });
  }, [id]);

  return <main>
    <Navigation />
    <Link href={`/patients/${id}`}>← Back to patient detail</Link>
    <p className="eyebrow">AI WORKFLOW ACTIVITY</p>
    <h1>Patient workflow</h1>
    {error && <p role="alert">{error}</p>}
    {!workflow && !error && <p role="status">Loading workflow…</p>}
    {workflow && <>
      <section>
        <h2>Patient and discharge context</h2>
        <dl className="definition-grid">
          <dt>Patient</dt><dd>{workflow.patient.first_name} {workflow.patient.last_name}</dd>
          <dt>Identifier</dt><dd>{workflow.patient.external_patient_id}</dd>
          <dt>Preferred language</dt><dd>{workflow.patient.preferred_language || "—"}</dd>
          <dt>Care setting</dt><dd>{workflow.latest_encounter?.care_setting ?? "Not available yet"}</dd>
          <dt>Discharged</dt><dd>{formatDate(workflow.latest_discharge?.discharge_at)}</dd>
          <dt>Follow-up deadline</dt><dd>{formatDate(workflow.latest_discharge?.follow_up_deadline)}</dd>
          <dt>Discharge risk</dt><dd>{workflow.latest_discharge?.risk_level ?? "Not available yet"}</dd>
        </dl>
      </section>
      <section>
        <h2>Voice Intake</h2>
        {!workflow.voice_intake && <p>Not available yet.</p>}
        {workflow.voice_intake && <dl className="definition-grid">
          <dt>Status</dt><dd><span className="badge">{workflow.voice_intake.status}</span></dd>
          <dt>Stage</dt><dd>{workflow.voice_intake.current_stage}</dd>
          <DetailList label="Reported symptoms" value={workflow.voice_intake.captured_information.symptoms_reported} />
          <DetailList label="Medication concerns" value={workflow.voice_intake.captured_information.medication_concerns} />
          <DetailList label="Follow-up concerns" value={workflow.voice_intake.captured_information.follow_up_concerns} />
          <DetailList label="Patient questions" value={workflow.voice_intake.captured_information.patient_questions} />
          <dt>Completed</dt><dd>{formatDate(workflow.voice_intake.completed_at)}</dd>
        </dl>}
      </section>
      <section>
        <h2>Clinical Triage</h2>
        {!workflow.triage_assessment && <p>Not available yet.</p>}
        {workflow.triage_assessment && <AssessmentCard assessment={workflow.triage_assessment} label="Latest triage assessment" />}
      </section>
      <section>
        <h2>Independent Assessments</h2>
        {!workflow.independent_assessments.length && <p>Not available yet.</p>}
        {workflow.independent_assessments.map((assessment, index) => (
          <AssessmentCard key={assessment.id} assessment={assessment} label={`Assessment ${index + 1}`} />
        ))}
      </section>
      <section>
        <h2>Conservative Consensus</h2>
        {!workflow.consensus && <p>Not available yet.</p>}
        {workflow.consensus && <dl className="definition-grid">
          <dt>Classification</dt><dd><span className="badge">{workflow.consensus.final_classification}</span></dd>
          <dt>Agreement</dt><dd>{workflow.consensus.agreement_status}</dd>
          <dt>Human review</dt><dd>{workflow.consensus.requires_human_review ? "Required" : "Not required"}</dd>
          <dt>Recommended action</dt><dd>{workflow.consensus.recommended_action}</dd>
          <dt>Disagreement reason</dt><dd>{workflow.consensus.disagreement_reason ?? "—"}</dd>
          <dt>Recorded</dt><dd>{formatDate(workflow.consensus.created_at)}</dd>
        </dl>}
      </section>
      <section>
        <h2>Escalation</h2>
        {!workflow.escalation && <p>Not available yet.</p>}
        {workflow.escalation && <dl className="definition-grid">
          <dt>Status</dt><dd><span className="badge">{workflow.escalation.status}</span></dd>
          <dt>Priority</dt><dd>{workflow.escalation.priority}</dd>
          <dt>Assigned reviewer</dt><dd>{workflow.escalation.assigned_reviewer_id ?? "Unassigned"}</dd>
          <dt>Resolution</dt><dd>{workflow.escalation.resolution ?? "Not resolved"}</dd>
          <dt>Created</dt><dd>{formatDate(workflow.escalation.created_at)}</dd>
          <dt>Resolved</dt><dd>{formatDate(workflow.escalation.resolved_at)}</dd>
        </dl>}
      </section>
      <section>
        <h2>Notification and human-review status</h2>
        {!workflow.notification && <p>Not available yet.</p>}
        {workflow.notification && <dl className="definition-grid">
          <dt>Status</dt><dd><span className="badge">{workflow.notification.status}</span></dd>
          <dt>Severity</dt><dd>{workflow.notification.severity}</dd>
          <dt>Type</dt><dd>{workflow.notification.notification_type}</dd>
          <dt>Created</dt><dd>{formatDate(workflow.notification.created_at)}</dd>
          <dt>Read</dt><dd>{formatDate(workflow.notification.read_at)}</dd>
          <dt>Acknowledged</dt><dd>{formatDate(workflow.notification.acknowledged_at)}</dd>
        </dl>}
      </section>
      <section>
        <h2>Mock EHR operation</h2>
        {!workflow.mock_ehr_operation && <p>Not available yet.</p>}
        {workflow.mock_ehr_operation && <dl className="definition-grid">
          <dt>Operation</dt><dd>{workflow.mock_ehr_operation.operation_type}</dd>
          <dt>Status</dt><dd><span className="badge">{workflow.mock_ehr_operation.status}</span></dd>
          <dt>Created</dt><dd>{formatDate(workflow.mock_ehr_operation.created_at)}</dd>
          <dt>Completed</dt><dd>{formatDate(workflow.mock_ehr_operation.completed_at)}</dd>
        </dl>}
      </section>
    </>}
  </main>;
}
