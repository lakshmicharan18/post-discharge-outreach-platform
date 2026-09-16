export default function Home() {
  return (
    <main>
      <p className="eyebrow">MULTI-HOSPITAL OPERATIONS</p>
      <h1>Post-Discharge<br />Outreach Platform</h1>
      <p className="intro">A foundation for coordinated follow-up across hospitals.</p>
      <section aria-labelledby="foundation">
        <span className="badge">Milestone 1</span>
        <h2 id="foundation">Project foundation &amp; multi-tenant core</h2>
        <p>Hospital, patient, encounter, and discharge records are supported by a tenant-scoped backend.</p>
        <p>Operational workflows will be introduced in future milestones.</p>
      </section>
      <footer>Prototype · Use synthetic data only</footer>
    </main>
  );
}
