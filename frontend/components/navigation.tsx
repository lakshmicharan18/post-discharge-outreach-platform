"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

export function Navigation() {
  const router = useRouter();
  const [pending, setPending] = useState(false);
  async function logout() {
    setPending(true);
    await fetch("/api/auth/logout", { method: "POST" });
    router.replace("/login");
    router.refresh();
  }
  return <nav aria-label="Main navigation">
    <Link href="/">Home</Link>
    <Link href="/patients">Patients</Link>
    <Link href="/configuration">Configuration</Link>
    <Link href="/import">Import</Link>
    <button onClick={logout} disabled={pending}>{pending ? "Signing out…" : "Sign out"}</button>
  </nav>;
}
