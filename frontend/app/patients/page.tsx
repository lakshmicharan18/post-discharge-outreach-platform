"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Navigation } from "../../components/navigation";
import { api } from "../../lib/api";

interface Patient {
  id: string;
  external_patient_id: string;
  first_name: string;
  last_name: string;
  date_of_birth: string;
  preferred_language: string;
}

export default function PatientsPage() {
  const [patients, setPatients] = useState<Patient[]>([]);
  const [error, setError] = useState("");
  useEffect(() => { api<Patient[]>("patients?limit=100").then(setPatients).catch((e) => setError(e.message)); }, []);
  return <main>
    <Navigation />
    <p className="eyebrow">CLINICAL CONTEXT</p>
    <h1>Patients</h1>
    <p>Showing up to 100 patients for your authenticated hospital.</p>
    {error && <p role="alert">{error}</p>}
    <div className="table-wrap"><table>
      <thead><tr><th>Name</th><th>External ID</th><th>Date of birth</th><th>Language</th></tr></thead>
      <tbody>{patients.map((patient) => <tr key={patient.id}>
        <td><Link href={`/patients/${patient.id}`}>{patient.first_name} {patient.last_name}</Link></td>
        <td>{patient.external_patient_id}</td><td>{patient.date_of_birth}</td><td>{patient.preferred_language}</td>
      </tr>)}</tbody>
    </table></div>
    {!error && patients.length === 0 && <p role="status">Loading patients…</p>}
  </main>;
}
