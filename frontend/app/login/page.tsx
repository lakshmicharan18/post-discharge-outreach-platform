"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

export default function Login() {
  const router = useRouter();
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    setPending(true);
    setError("");
    try {
      const response = await fetch("/api/auth/login", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: data.get("email"), password: data.get("password") }),
      });
      const result = await response.json();
      if (!response.ok) { setError(result.message); return; }
      form.reset();
      router.replace("/");
      router.refresh();
    } catch {
      setError("Unable to connect. Please try again.");
    } finally {
      setPending(false);
    }
  }

  return <main>
    <p className="eyebrow">POST-DISCHARGE OUTREACH PLATFORM</p>
    <h1>Sign in</h1>
    <form onSubmit={submit}>
      <label htmlFor="email">Email</label>
      <input id="email" name="email" type="email" autoComplete="username" required maxLength={254} />
      <label htmlFor="password">Password</label>
      <input id="password" name="password" type="password" autoComplete="current-password" required maxLength={128} />
      {error && <p role="alert">{error}</p>}
      <button disabled={pending} type="submit">{pending ? "Signing in…" : "Sign in"}</button>
    </form>
    <footer>Prototype · Use synthetic data only</footer>
  </main>;
}
