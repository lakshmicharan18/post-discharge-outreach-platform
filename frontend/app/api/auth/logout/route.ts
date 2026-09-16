import { NextRequest } from "next/server";
import { clearSession, json, sameOrigin } from "../../../../lib/auth";

export async function POST(request: NextRequest) {
  if (!sameOrigin(request)) return json({ message: "Request origin is not permitted." }, 403);
  return clearSession(json({ message: "Signed out." }));
}
