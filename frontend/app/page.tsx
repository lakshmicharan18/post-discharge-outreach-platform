"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import type { CurrentUser } from "../lib/auth";

export default function Home() {
  const router = useRouter();
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
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

  async function logout() {
    setPending(true);
    try {
      const response = await fetch("/api/auth/logout", { method: "POST" });
      if (!response.ok) throw new Error("Logout failed");
      setUser(null);
      router.replace("/login");
      router.refresh();
    } catch {
      setError("Could not sign out. Please retry.");
    } finally { setPending(false); }
  }

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
      <button onClick={logout} disabled={pending}>{pending ? "Signing out…" : "Sign out"}</button>
    </section>}
    <footer>Prototype · Use synthetic data only</footer>
  </main>;
}
