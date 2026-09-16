import { NextRequest } from "next/server";
import { backendUrl, clearSession, json, SESSION_COOKIE } from "../../../../lib/auth";

export async function GET(request: NextRequest) {
  const token = request.cookies.get(SESSION_COOKIE)?.value;
  if (!token) return json({ message: "Please sign in." }, 401);
  try {
    const upstream = await fetch(`${backendUrl}/api/v1/users/me`, {
      headers: { Authorization: `Bearer ${token}` }, cache: "no-store", signal: AbortSignal.timeout(10000),
    });
    if (upstream.status === 401 || upstream.status === 403) {
      return clearSession(json({ message: "Your session has ended. Please sign in again." }, upstream.status));
    }
    if (!upstream.ok) return json({ message: "Your session could not be checked. Please retry." }, 503);
    return json(await upstream.json());
  } catch {
    return json({ message: "Your session could not be checked. Please retry." }, 503);
  }
}
