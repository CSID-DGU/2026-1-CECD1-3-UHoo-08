/**
 * 화담 CARE(AI 서버) 호출 주소.
 *
 * lib/api.ts의 `/ai/` 접두사를 쓰지 않는다. 그 경로는 VITE_AI_API_BASE_URL이
 * 있을 때만 AI 서버로 가고, 없으면 BE 주소에 그대로 붙는다. 배포 환경에는 그
 * 값이 없어서 요청이 BE로 가 500이 났다. 빌드 시점에 분기가 통째로 제거되기
 * 때문에 코드만 봐서는 드러나지 않는다.
 *
 * 키오스크(kiosk/lib/kioskApi.ts)가 쓰는 방식과 같게 맞춘다. 환경변수가 있으면
 * 그것을 쓰고, 없으면 배포 주소로 떨어진다.
 *
 * Authorization 헤더는 붙이지 않는다. AI 서버는 그 토큰을 보지 않고, 헤더가
 * 붙으면 프리플라이트가 한 번 더 돈다.
 */
const ENV_BASE = (
  import.meta.env.VITE_AI_API_BASE_URL as string | undefined
)?.trim().replace(/\/$/, "");

export const CARE_BASE = ENV_BASE || "https://uhoo08-api.duckdns.org";

export class CareApiError extends Error {
  readonly url: string;
  readonly status: number | null;

  constructor(message: string, url: string, status: number | null) {
    super(message);
    this.name = "CareApiError";
    this.url = url;
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${CARE_BASE}${path}`;
  let res: Response;
  try {
    res = await fetch(url, {
      ...init,
      headers: {
        Accept: "application/json",
        ...(init?.body ? { "Content-Type": "application/json" } : {}),
        ...init?.headers,
      },
    });
  } catch (e) {
    throw new CareApiError(e instanceof Error ? e.message : String(e), url, null);
  }

  if (!res.ok) {
    throw new CareApiError(res.statusText || "요청 실패", url, res.status);
  }
  // 204 등 본문이 없는 응답
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const care = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: JSON.stringify(body ?? {}) }),
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "PATCH", body: JSON.stringify(body ?? {}) }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
};
