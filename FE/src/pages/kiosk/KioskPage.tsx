import { useCallback, useEffect, useRef, useState } from "react";

/**
 * 키오스크 임시 화면.
 *
 * 아직 실제 UI가 아니다. 아이패드에서 다음을 눈으로 확인하기 위한 화면이다.
 *
 *   · HTTPS로 AI 서버에 닿는가 (혼합 콘텐츠·CORS)
 *   · 홈 화면에 추가했을 때 주소창·툴바 없이 뜨는가 (standalone)
 *   · 화면 크기가 얼마인가 (목업 1024×600을 어떻게 확대할지 결정할 근거)
 *
 * 아이패드 사파리에는 개발자 도구가 없다. 그래서 콘솔에 찍는 대신
 * 화면에 그대로 출력한다. 오류가 나면 그 자리에서 원문을 봐야 한다.
 */

// 예선 한정. 키오스크는 브라우저라 X-Node-Key를 쓸 수 없어 user_id를
// 쿼리로 넘긴다. 본선 전에 카카오 JWT 검증으로 바꾼다.
const DEFAULT_USER_ID = "aa000000-0000-0000-0000-000000000001";

// Vercel 환경변수가 비어 있어도 화면이 뜨도록 기본값을 둔다.
// 환경변수가 잡히면 그쪽이 우선이며, 화면에 어느 쪽을 썼는지 표시한다.
const FALLBACK_API_BASE = "https://uhoo08-api.duckdns.org";

const ENV_API_BASE = (
  import.meta.env.VITE_AI_API_BASE_URL as string | undefined
)?.replace(/\/$/, "");

const API_BASE = ENV_API_BASE || FALLBACK_API_BASE;

const KIOSK_MANIFEST = "/kiosk.webmanifest";

type Probe = {
  label: string;
  path: string;
  status: "idle" | "loading" | "ok" | "fail";
  httpStatus?: number;
  ms?: number;
  summary?: string;
  error?: string;
};

function isStandalone(): boolean {
  // iOS는 navigator.standalone, 그 외는 display-mode 미디어 쿼리를 쓴다.
  const nav = navigator as Navigator & { standalone?: boolean };
  if (typeof nav.standalone === "boolean") return nav.standalone;
  return window.matchMedia("(display-mode: standalone)").matches;
}

export function KioskPage() {
  const params = new URLSearchParams(window.location.search);
  const userId = params.get("user_id") || DEFAULT_USER_ID;

  const [probes, setProbes] = useState<Probe[]>([
    { label: "환경 대시보드", path: `/api/care/dashboard?user_id=${userId}`, status: "idle" },
    { label: "점검 우선순위", path: `/api/care/priority?user_id=${userId}&limit=3`, status: "idle" },
  ]);
  const [now, setNow] = useState(new Date());
  const [manifestHref, setManifestHref] = useState<string>("(확인 중)");
  const restoreRef = useRef<{ el: HTMLLinkElement; href: string } | null>(null);

  // ── manifest 바꿔치기 ────────────────────────────────────────
  // SPA라 index.html이 하나뿐이고 vite-plugin-pwa가 앱용 manifest를
  // 박아 넣는다. 이 페이지에 있는 동안만 키오스크용으로 갈아끼운다.
  // Safari는 "홈 화면에 추가"를 누른 시점의 DOM을 읽으므로 이걸로 충분하다.
  // 페이지를 벗어나면 원래 manifest로 되돌린다.
  useEffect(() => {
    let link = document.querySelector<HTMLLinkElement>('link[rel="manifest"]');
    if (!link) {
      link = document.createElement("link");
      link.rel = "manifest";
      document.head.appendChild(link);
    }
    restoreRef.current = { el: link, href: link.getAttribute("href") ?? "" };
    link.setAttribute("href", KIOSK_MANIFEST);
    setManifestHref(link.getAttribute("href") ?? "(없음)");

    // 홈 화면 아이콘 아래 이름. iOS는 manifest의 name보다 이 태그를 우선한다.
    const title = document.querySelector<HTMLMetaElement>(
      'meta[name="apple-mobile-web-app-title"]'
    );
    const prevTitle = title?.getAttribute("content") ?? null;
    title?.setAttribute("content", "화담 CARE");

    const prevDocTitle = document.title;
    document.title = "화담 CARE 키오스크";

    return () => {
      const saved = restoreRef.current;
      if (saved) saved.el.setAttribute("href", saved.href);
      if (title && prevTitle !== null) title.setAttribute("content", prevTitle);
      document.title = prevDocTitle;
    };
  }, []);

  // 화면이 살아 있는지 한눈에 보이도록 시계를 돌린다.
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  const runProbes = useCallback(async () => {
    setProbes((prev) => prev.map((p) => ({ ...p, status: "loading" as const })));

    const next = await Promise.all(
      probes.map(async (p): Promise<Probe> => {
        const started = performance.now();
        try {
          const res = await fetch(`${API_BASE}${p.path}`, {
            headers: { Accept: "application/json" },
          });
          const ms = Math.round(performance.now() - started);
          const text = await res.text();

          if (!res.ok) {
            return {
              ...p, status: "fail", httpStatus: res.status, ms,
              error: text.slice(0, 300) || res.statusText,
            };
          }

          const data = JSON.parse(text);
          let summary = "";
          if (p.path.includes("dashboard")) {
            const t = data.totals ?? {};
            summary = `노드 ${t.nodes ?? "?"}개 · 온라인 ${t.online ?? "?"} · 측정 ${t.readings ?? "?"}건`;
          } else {
            const s = data.summary ?? {};
            summary = `보유 ${s.total ?? "?"} · 산출 ${s.scored ?? "?"} · 확인 필요 ${s.needs_check ?? "?"}`;
          }
          return { ...p, status: "ok", httpStatus: res.status, ms, summary };
        } catch (e) {
          return {
            ...p, status: "fail",
            ms: Math.round(performance.now() - started),
            // TypeError: Load failed → CORS 차단이거나 서버에 닿지 못한 것
            error: e instanceof Error ? `${e.name}: ${e.message}` : String(e),
          };
        }
      })
    );

    setProbes(next);
    // probes를 의존성에 넣으면 갱신될 때마다 다시 도니 제외한다.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    void runProbes();
  }, [runProbes]);

  const standalone = isStandalone();

  return (
    <div className="min-h-screen w-full bg-[#0f1115] text-white font-outfit">
      <div className="mx-auto max-w-[1024px] px-8 py-8">
        <header className="mb-8 flex items-baseline justify-between border-b border-white/10 pb-4">
          <div>
            <h1 className="text-3xl font-semibold">화담 CARE 키오스크</h1>
            <p className="mt-1 text-sm text-white/50">연결 확인용 임시 화면</p>
          </div>
          <div className="text-right">
            <div className="text-3xl tabular-nums">
              {now.toLocaleTimeString("ko-KR", { hour12: false })}
            </div>
            <div className="text-sm text-white/50">
              {now.toLocaleDateString("ko-KR")}
            </div>
          </div>
        </header>

        {/* ── 서버 연결 ── */}
        <section className="mb-8">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-lg font-medium">서버 연결</h2>
            <button
              onClick={() => void runProbes()}
              className="rounded-lg bg-white/10 px-4 py-2 text-sm active:bg-white/20"
            >
              다시 시도
            </button>
          </div>

          <div className="mb-3 rounded-lg bg-white/5 px-4 py-3 text-sm">
            <div className="text-white/50">API 주소</div>
            <div className="break-all">{API_BASE}</div>
            <div className="mt-1 text-xs text-white/40">
              {ENV_API_BASE
                ? "VITE_AI_API_BASE_URL 환경변수 사용"
                : "환경변수가 비어 있어 기본값 사용"}
            </div>
          </div>

          <div className="space-y-2">
            {probes.map((p) => (
              <div key={p.path} className="rounded-lg bg-white/5 px-4 py-3">
                <div className="flex items-center justify-between">
                  <span className="font-medium">
                    {p.status === "ok" && "🟢 "}
                    {p.status === "fail" && "🔴 "}
                    {p.status === "loading" && "⏳ "}
                    {p.label}
                  </span>
                  <span className="text-sm text-white/50">
                    {p.httpStatus ? `HTTP ${p.httpStatus}` : ""}
                    {p.ms !== undefined ? ` · ${p.ms}ms` : ""}
                  </span>
                </div>
                {p.summary && (
                  <div className="mt-1 text-sm text-white/70">{p.summary}</div>
                )}
                {p.error && (
                  <pre className="mt-2 overflow-x-auto whitespace-pre-wrap rounded bg-black/40 p-2 text-xs text-red-300">
                    {p.error}
                  </pre>
                )}
              </div>
            ))}
          </div>
        </section>

        {/* ── 표시 환경 ── */}
        <section>
          <h2 className="mb-3 text-lg font-medium">표시 환경</h2>
          <dl className="grid grid-cols-2 gap-x-6 gap-y-2 rounded-lg bg-white/5 px-4 py-3 text-sm">
            <Row
              k="전체화면(standalone)"
              v={standalone ? "예 — 주소창 없음" : "아니오 — 사파리 탭"}
            />
            <Row
              k="표시 영역"
              v={`${window.innerWidth} × ${window.innerHeight}`}
            />
            <Row
              k="화면 해상도"
              v={`${window.screen.width} × ${window.screen.height} (DPR ${window.devicePixelRatio})`}
            />
            <Row
              k="목업 대비 배율"
              v={`가로 ${(window.innerWidth / 1024).toFixed(2)}× · 세로 ${(
                window.innerHeight / 600
              ).toFixed(2)}×`}
            />
            <Row k="manifest" v={manifestHref} />
            <Row k="네트워크" v={navigator.onLine ? "온라인" : "오프라인"} />
            <Row k="사용자" v={userId} />
          </dl>

          {!standalone && (
            <p className="mt-3 text-sm text-white/50">
              공유 버튼 → 홈 화면에 추가 → 홈 화면 아이콘으로 실행하면
              주소창 없이 뜹니다.
            </p>
          )}
        </section>
      </div>
    </div>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <>
      <dt className="text-white/50">{k}</dt>
      <dd className="text-right break-all">{v}</dd>
    </>
  );
}

export default KioskPage;