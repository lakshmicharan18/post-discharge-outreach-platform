"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import type { CurrentUser } from "../lib/auth";

export function Navigation() {
  const router = useRouter();
  const [pending, setPending] = useState(false);
  const [user, setUser] = useState<CurrentUser | null>(null);
  useEffect(() => {
    fetch("/api/auth/me", { cache: "no-store" })
      .then((response) => response.ok ? response.json() : null)
      .then(setUser)
      .catch(() => setUser(null));
  }, []);
  async function logout() {
    setPending(true);
    await fetch("/api/auth/logout", { method: "POST" });
    router.replace("/login");
    router.refresh();
  }
  return <nav aria-label="Main navigation">
    <Link href="/">Home</Link>
    <Link href="/patients">Patients</Link>
    {user?.role && user.role !== "PLATFORM_ADMIN" && <Link href="/campaigns">Campaigns</Link>}
    <Link href="/configuration">Configuration</Link>
    <Link href="/import">Import</Link>
    <button onClick={logout} disabled={pending}>{pending ? "Signing out…" : "Sign out"}</button>
  </nav>;
}
