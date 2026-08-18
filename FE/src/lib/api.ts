import { getAccessToken } from "./auth";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, "") ?? "";
const AI_API_BASE_URL = (import.meta.env.VITE_AI_API_BASE_URL as string | undefined)?.replace(/\/$/, "") ?? "";

function getApiUrl(path: string): string {
  if (/^https?:\/\//i.test(path)) return path;
  if (AI_API_BASE_URL && path.startsWith("/ai/")) return `${AI_API_BASE_URL}${path.replace(/^\/ai/, "")}`;
  if (!API_BASE_URL) return path;
  return `${API_BASE_URL}${path.startsWith("/") ? path : `/${path}`}`;
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getAccessToken();
  const isFormData = options.body instanceof FormData;

  const res = await fetch(getApiUrl(path), {
    ...options,
    headers: {
      // FormData는 Content-Type 자동 설정 (boundary 포함)
      ...(isFormData ? {} : { "Content-Type": "application/json" }),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });

  const data = await res.json();
  if (!res.ok) throw data;
  return data as T;
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: JSON.stringify(body) }),
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "PATCH", body: JSON.stringify(body) }),
  patchForm: <T>(path: string, form: FormData) =>
    request<T>(path, { method: "PATCH", body: form }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
};
