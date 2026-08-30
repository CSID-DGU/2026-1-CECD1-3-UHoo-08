/**
 * 키오스크 전용 API 클라이언트.
 *
 * lib/api.ts를 쓰지 않는 이유: 그쪽은 Authorization 헤더를 붙이고 401이면
 * 토큰 갱신·로그인 화면으로 보낸다. 키오스크는 로그인하지 않으므로 그
 * 흐름을 타면 시연 도중 로그인 화면으로 튕긴다.
 *
 * ── 오류를 감추지 않는다 ─────────────────────────────────────
 * 아이패드에는 개발자 도구가 없다. 시연 중 화면이 비면 원인을 찾을 방법이
 * 없으므로, 실패한 주소와 상태 코드와 응답 본문을 그대로 들고 다닌다.
 * 화면은 그것을 사람이 읽을 수 있게 출력한다.
 */

const ENV_BASE = (
  import.meta.env.VITE_AI_API_BASE_URL as string | undefined
)?.replace(/\/$/, "");

/** 환경변수가 비어 있어도 시연이 가능하도록 기본값을 둔다. */
export const FALLBACK_API_BASE = "https://uhoo08-api.duckdns.org";

export const API_BASE = ENV_BASE || FALLBACK_API_BASE;
export const API_BASE_FROM_ENV = Boolean(ENV_BASE);

/**
 * 예선 한정. 키오스크는 브라우저라 X-Node-Key를 쓸 수 없고 로그인도 없다.
 * 본선 전에 카카오 JWT 검증으로 바꾸고 이 값은 제거한다.
 */
const DEFAULT_USER_ID = "e3985354-0a60-4330-b7cb-b83b674c0eb0";

export const KIOSK_USER_ID =
  new URLSearchParams(window.location.search).get("user_id") || DEFAULT_USER_ID;

/** 응답이 늦으면 화면이 멈춘 것처럼 보인다. 끊고 오류로 넘긴다. */
const TIMEOUT_MS = 12000;

export class KioskApiError extends Error {
  readonly url: string;
  readonly status: number | null;
  readonly body: string;

  constructor(message: string, url: string, status: number | null, body = "") {
    super(message);
    this.name = "KioskApiError";
    this.url = url;
    this.status = status;
    this.body = body;
  }

  /** 화면에 그대로 띄울 요약 한 줄. */
  get summary(): string {
    if (this.status === null) return `연결 실패 — ${this.message}`;
    return `HTTP ${this.status}`;
  }

  /**
   * FastAPI가 HTTPException에 담아 보낸 사람이 읽을 문장.
   *
   * 4xx는 대부분 서버가 이유를 문장으로 적어 보낸다("연결된 측정 노드가
   * 없습니다" 같은 것). 그 문장이 body 안에 갇혀 있으면 화면에는 "HTTP 409"만
   * 뜨고, 정작 무엇을 하라는 것인지 알 수 없다.
   */
  get detail(): string | null {
    if (!this.body) return null;
    try {
      const parsed = JSON.parse(this.body) as { detail?: unknown };
      return typeof parsed.detail === "string" ? parsed.detail : null;
    } catch {
      return null;
    }
  }
}

export async function kioskGet<T>(
  path: string,
  params: Record<string, string | number | boolean | undefined> = {}
): Promise<T> {
  const url = new URL(API_BASE + path);
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined) url.searchParams.set(k, String(v));
  }
  const href = url.toString();

  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), TIMEOUT_MS);

  let res: Response;
  try {
    res = await fetch(href, {
      headers: { Accept: "application/json" },
      signal: controller.signal,
    });
  } catch (e) {
    // TypeError: Load failed → CORS 차단이거나 서버에 닿지 못한 것.
    // AbortError → 타임아웃.
    const msg =
      e instanceof Error
        ? e.name === "AbortError"
          ? `응답 없음 (${TIMEOUT_MS / 1000}초 초과)`
          : `${e.name}: ${e.message}`
        : String(e);
    throw new KioskApiError(msg, href, null);
  } finally {
    window.clearTimeout(timer);
  }

  const text = await res.text();

  if (!res.ok) {
    throw new KioskApiError(res.statusText || "요청 실패", href, res.status, text.slice(0, 500));
  }

  try {
    return JSON.parse(text) as T;
  } catch {
    throw new KioskApiError("JSON 파싱 실패", href, res.status, text.slice(0, 500));
  }
}

/**
 * DELETE 요청. 본문 없는 204를 정상으로 본다.
 *
 * 측정 화면에서 뒤로 나갈 때 세션을 닫는 데 쓴다. 닫지 않으면 노드가
 * 시한이 다 될 때까지 그 세션을 붙들고 있어 다음 측정을 시작할 수 없다.
 */
export async function kioskDelete(
  path: string,
  params: Record<string, string | number | boolean | undefined> = {}
): Promise<void> {
  const url = new URL(API_BASE + path);
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined) url.searchParams.set(k, String(v));
  }
  const href = url.toString();

  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), TIMEOUT_MS);

  let res: Response;
  try {
    res = await fetch(href, {
      method: "DELETE",
      headers: { Accept: "application/json" },
      signal: controller.signal,
    });
  } catch (e) {
    const msg =
      e instanceof Error
        ? e.name === "AbortError"
          ? `응답 없음 (${TIMEOUT_MS / 1000}초 초과)`
          : `${e.name}: ${e.message}`
        : String(e);
    throw new KioskApiError(msg, href, null);
  } finally {
    window.clearTimeout(timer);
  }

  if (!res.ok) {
    const text = await res.text();
    throw new KioskApiError(res.statusText || "요청 실패", href, res.status, text.slice(0, 500));
  }
}

/**
 * POST 요청.
 *
 * GET과 오류 처리를 똑같이 한다. 아이패드에는 개발자 도구가 없으므로
 * 실패한 주소와 응답 본문을 그대로 들고 다닌다.
 */
export async function kioskPost<T>(
  path: string,
  body: unknown,
  params: Record<string, string | number | boolean | undefined> = {}
): Promise<T> {
  const url = new URL(API_BASE + path);
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined) url.searchParams.set(k, String(v));
  }
  const href = url.toString();

  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), TIMEOUT_MS);

  let res: Response;
  try {
    res = await fetch(href, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
  } catch (e) {
    const msg =
      e instanceof Error
        ? e.name === "AbortError"
          ? `응답 없음 (${TIMEOUT_MS / 1000}초 초과)`
          : `${e.name}: ${e.message}`
        : String(e);
    throw new KioskApiError(msg, href, null);
  } finally {
    window.clearTimeout(timer);
  }

  const text = await res.text();

  if (!res.ok) {
    throw new KioskApiError(res.statusText || "요청 실패", href, res.status, text.slice(0, 500));
  }

  try {
    return JSON.parse(text) as T;
  } catch {
    throw new KioskApiError("JSON 파싱 실패", href, res.status, text.slice(0, 500));
  }
}