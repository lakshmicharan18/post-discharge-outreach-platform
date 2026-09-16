"use client";

import { FormEvent, useState } from "react";
import { Navigation } from "../../components/navigation";
import { api } from "../../lib/api";

interface ImportResult { id: string; status: string; total_records: number; successful_records: number; failed_records: number; errors: Array<{record_index:number; field:string|null; message:string}> }
const example = JSON.stringify({ source: "manual-json", records: [] }, null, 2);

export default function ImportPage() {
  const [payload, setPayload] = useState(example);
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [error, setError] = useState("");
  async function submitJson(event: FormEvent) {
    event.preventDefault(); setError(""); setResult(null);
    try {
      const parsed = JSON.parse(payload);
      setResult(await api<ImportResult>("discharges/import", { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(parsed) }));
    } catch (e) { setError(e instanceof Error ? e.message : "Import failed."); }
  }
  async function submitCsv() {
    if (!file) return;
    setError(""); setResult(null);
    try { const body = new FormData(); body.append("file", file); setResult(await api<ImportResult>("discharges/import/csv", {method:"POST",body})); }
    catch (e) { setError(e instanceof Error ? e.message : "Import failed."); }
  }
  return <main><Navigation /><p className="eyebrow">DISCHARGE INGESTION</p><h1>Import data</h1>
    <p>Hospital administrators can submit a JSON batch or UTF-8 CSV. Each record is atomic; failures do not roll back valid records.</p>
    <form className="wide-form" onSubmit={submitJson}><label>JSON batch<textarea rows={16} value={payload} onChange={(e)=>setPayload(e.target.value)}/></label><button>Import JSON</button></form>
    <section><h2>CSV upload</h2><input type="file" accept=".csv,text/csv" onChange={(e)=>setFile(e.target.files?.[0]||null)}/><button type="button" disabled={!file} onClick={submitCsv}>Import CSV</button></section>
    {error && <p role="alert">{error}</p>}
    {result && <section><h2>Import result</h2><p><strong>{result.status}</strong>: {result.successful_records} successful, {result.failed_records} failed, {result.total_records} total.</p>
      {result.errors.length > 0 && <ul>{result.errors.map((item)=><li key={`${item.record_index}-${item.field}`}>Record {item.record_index + 1}{item.field ? ` (${item.field})`:""}: {item.message}</li>)}</ul>}</section>}
  </main>;
}
