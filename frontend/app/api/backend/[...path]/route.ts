import { NextRequest, NextResponse } from "next/server";
import { backendUrl, clearSession, json, sameOrigin, SESSION_COOKIE } from "../../../../lib/auth";

async function proxy(request: NextRequest, segments: string[]) {
  const token = request.cookies.get(SESSION_COOKIE)?.value;
  if (!token) return json({ message: "Please sign in." }, 401);
  if (request.method !== "GET" && !sameOrigin(request)) {
    return json({ message: "Request origin is not permitted." }, 403);
  }
  const target = new URL(`${backendUrl}/api/v1/${segments.map(encodeURIComponent).join("/")}`);
  request.nextUrl.searchParams.forEach((value, key) => target.searchParams.append(key, value));
  const headers: Record<string, string> = { Authorization: `Bearer ${token}` };
  const contentType = request.headers.get("content-type");
  if (contentType) headers["Content-Type"] = contentType;
  try {
    const upstream = await fetch(target, {
      method: request.method,
      headers,
      body: request.method === "GET" ? undefined : await request.arrayBuffer(),
      cache: "no-store",
      signal: AbortSignal.timeout(30000),
    });
    const response = new NextResponse(await upstream.arrayBuffer(), {
      status: upstream.status,
      headers: {
        "Content-Type": upstream.headers.get("content-type") || "application/json",
        "Cache-Control": "no-store",
      },
    });
    if (upstream.status === 401) return clearSession(response);
    return response;
  } catch {
    return json({ message: "The backend is temporarily unavailable." }, 503);
  }
}

type RouteContext = { params: Promise<{ path: string[] }> };

export async function GET(request: NextRequest, context: RouteContext) {
  return proxy(request, (await context.params).path);
}

export async function POST(request: NextRequest, context: RouteContext) {
  return proxy(request, (await context.params).path);
}

export async function PUT(request: NextRequest, context: RouteContext) {
  return proxy(request, (await context.params).path);
}

export async function PATCH(request: NextRequest, context: RouteContext) {
  return proxy(request, (await context.params).path);
}
