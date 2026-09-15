import { clearSession, getToken } from "./auth";

/** Vacío = same-origin (nginx /api → backend). Evita fallos cross-host con bkavaluos. */
function resolveApiUrl(): string {
  const raw = import.meta.env.VITE_API_URL;
  if (raw === undefined || raw === null) return "http://127.0.0.1:8000";
  return String(raw).replace(/\/$/, "");
}

export const API_URL = resolveApiUrl();

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export async function api<T>(
  path: string,
  options: RequestInit = {},
  auth = false,
): Promise<T> {
  const headers = new Headers(options.headers || {});
  const isFormData = typeof FormData !== "undefined" && options.body instanceof FormData;
  if (!headers.has("Content-Type") && options.body && !isFormData) {
    headers.set("Content-Type", "application/json");
  }
  if (auth) {
    const token = getToken();
    if (token) headers.set("Authorization", `Bearer ${token}`);
  }

  const res = await fetch(`${API_URL}${path}`, { ...options, headers });
  if (res.status === 401 && auth) {
    clearSession();
  }

  const text = await res.text();
  let data: unknown = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = text;
    }
  }

  if (!res.ok) {
    let message = "Error de servidor";
    if (typeof data === "object" && data && "detail" in data) {
      const detail = (data as { detail: unknown }).detail;
      if (typeof detail === "string") message = detail;
      else if (Array.isArray(detail)) {
        message = detail
          .map((d) => (typeof d === "object" && d && "msg" in d ? String((d as { msg: string }).msg) : String(d)))
          .join(". ");
      }
    }
    throw new ApiError(res.status, message);
  }
  return data as T;
}

/** URL para <img>/enlaces de /api/v1/media/… (same-origin si VITE_API_URL está vacío). */
export function mediaUrl(path: string, bust?: string | number | null): string {
  if (!path) return "";
  const absolute = path.startsWith("http") ? path : `${API_URL}${path}`;
  if (bust == null || bust === "") return absolute;
  const sep = absolute.includes("?") ? "&" : "?";
  return `${absolute}${sep}v=${encodeURIComponent(String(bust))}`;
}
