import { getAccessToken } from "./auth";

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getAccessToken();
  const isFormData = options.body instanceof FormData;

  const res = await fetch(path, {
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
