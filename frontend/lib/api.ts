export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/backend/${path}`, { cache: "no-store", ...init });
  if (response.status === 401) {
    window.location.assign("/login");
    throw new Error("Your session has ended.");
  }
  const result = await response.json();
  if (!response.ok) {
    throw new Error(result?.error?.message || result?.message || "Request failed.");
  }
  return result as T;
}
