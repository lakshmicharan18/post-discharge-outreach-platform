import { NextRequest, NextResponse } from "next/server";

export const SESSION_COOKIE = "outreach_session";
export const backendUrl = process.env.BACKEND_URL || "http://127.0.0.1:8000";
export const cookieOptions = {
  httpOnly: true,
  sameSite: "strict" as const,
  secure: process.env.SESSION_COOKIE_SECURE
    ? process.env.SESSION_COOKIE_SECURE === "true"
    : process.env.NODE_ENV === "production",
  path: "/",
};

export function sameOrigin(request: NextRequest): boolean {
  // Next.js may normalize request.url to localhost; compare the browser's Host instead.
  const origin = request.headers.get("origin");
  const host = request.headers.get("host");
  if (!origin || !host) return false;
  try {
    return new URL(origin).origin === `${request.nextUrl.protocol}//${host}`;
  } catch {
    return false;
  }
}

export function json(data: unknown, status = 200): NextResponse {
  return NextResponse.json(data, { status, headers: { "Cache-Control": "no-store" } });
}

export function clearSession(response: NextResponse): NextResponse {
  response.cookies.set(SESSION_COOKIE, "", { ...cookieOptions, maxAge: 0 });
  return response;
}

export interface CurrentUser {
  id: string;
  full_name: string;
  email: string;
  role: "PLATFORM_ADMIN" | "HOSPITAL_ADMIN" | "CAMPAIGN_MANAGER" | "CLINICAL_REVIEWER";
  hospital_id: string | null;
  hospital: { id: string; name: string } | null;
}
