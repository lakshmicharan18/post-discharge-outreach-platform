"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import type { CurrentUser } from "../lib/auth";
import { Navigation } from "../components/navigation";

export default function Home() {
  const router = useRouter();
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [error, setError] = useState("");
  const refresh = useCallback(async () => {
    try {
      const response = await fetch("/api/auth/me", { cache: "no-store" });
      if (response.status === 401 || response.status === 403) {
        setUser(null);
        router.replace("/login");
        return;
      }
      if (!response.ok) throw new Error("Session unavailable");
      setUser(await response.json());
      setError("");
    } catch {
      setUser(null);
      setError("Unable to check your session. Please retry.");
    }
  }, [router]);

  useEffect(() => {
    void refresh();
    window.addEventListener("focus", refresh);
    const timer = window.setInterval(refresh, 60000);
    return () => { window.removeEventListener("focus", refresh); window.clearInterval(timer); };
  }, [refresh]);

  return <main>
    <p className="eyebrow">MULTI-HOSPITAL OPERATIONS</p>
    <h1>Post-Discharge Outreach Platform</h1>
    {error && <p role="alert">{error} <button onClick={() => void refresh()}>Retry</button></p>}
    {!user && !error && <p role="status">Checking your session…</p>}
    {user && <section aria-labelledby="identity">
      <h2 id="identity">Signed in as {user.full_name}</h2>
      <p>{user.email}</p>
      <p>Role: <strong>{user.role}</strong></p>
      <p>Hospital: <strong>{user.hospital?.name ?? "Platform administration"}</strong></p>
    </section>}
    {user && <><Navigation /><section><h2>Platform overview</h2><p>Review hospital configuration, browse structured patient context, or import discharge data.</p></section></>}
    <footer>Prototype · Use synthetic data only</footer>
  </main>;
}
