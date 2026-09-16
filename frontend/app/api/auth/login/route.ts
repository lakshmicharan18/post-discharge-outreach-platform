import { NextRequest } from "next/server";
import { backendUrl, cookieOptions, json, sameOrigin, SESSION_COOKIE } from "../../../../lib/auth";

export async function POST(request: NextRequest) {
  if (!sameOrigin(request)) return json({ message: "Request origin is not permitted." }, 403);
  let payload;
  try {
    payload = await request.json();
  } catch {
    return json({ message: "Enter an email and password." }, 400);
  }
  if (!payload || typeof payload.email !== "string" || typeof payload.password !== "string" ||
      payload.email.length > 254 || payload.password.length > 128) {
    return json({ message: "Enter a valid email and password." }, 422);
  }
  try {
    const upstream = await fetch(`${backendUrl}/api/v1/auth/login`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: payload.email, password: payload.password }),
      cache: "no-store", signal: AbortSignal.timeout(10000),
    });
    if (!upstream.ok) {
      const status = upstream.status;
      return json({ message: status === 401 ? "Invalid email or password." :
        status === 403 ? "Your hospital is unavailable." :
        status === 422 ? "Enter a valid email and password." : "Sign-in is temporarily unavailable." }, status);
    }
    const result = await upstream.json();
    const response = json({ user: result.user, expires_in: result.expires_in });
    response.cookies.set(SESSION_COOKIE, result.access_token, { ...cookieOptions, maxAge: result.expires_in });
    return response;
  } catch {
    return json({ message: "Sign-in is temporarily unavailable." }, 503);
  }
}
