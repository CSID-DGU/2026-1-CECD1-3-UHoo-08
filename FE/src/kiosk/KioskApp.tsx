import { useEffect, useState } from "react";
import { KioskFrame } from "./KioskFrame";
import { TabBar, TopBar, Brand, type TabKey } from "./ui";
import { kioskGet, KIOSK_USER_ID, API_BASE, API_BASE_FROM_ENV } from "./lib/kioskApi";
import { useKioskQuery } from "./lib/useKioskQuery";
import type { DashboardResponse, PriorityResponse } from "./lib/types";

/**
 * 키오스크 셸.
 *
 * 화면 전환은 URL이 아니라 상태로 한다. 홈 화면에서 실행할 때 경로가
 * 어긋나는 것을 피하기 위해서다(manifest의 start_url이 /kiosk 고정).
 *
 * 폴링 주기
 *   대시보드 60초 — 노드당 쿼리 2회를 쓴다. 30초로 줄이면 하루 17,000회다
 *   우선순위 5분  — 점수는 열이력 적산이라 분 단위로 변하지 않는다
 */
const DASHBOARD_INTERVAL_MS = 60_000;
const PRIORITY_INTERVAL_MS = 5 * 60_000;

/** 화면 상태. 탭 4개 + 대기 화면 + 하위 화면들. */
export type ScreenKey = "idle" | TabKey;

export function KioskApp() {
  const [screen, setScreen] = useState<ScreenKey>("idle");

  const dashboard = useKioskQuery<DashboardResponse>(
    () => kioskGet<DashboardResponse>("/api/care/dashboard", { user_id: KIOSK_USER_ID }),
    DASHBOARD_INTERVAL_MS
  );

  const priority = useKioskQuery<PriorityResponse>(
    () => kioskGet<PriorityResponse>("/api/care/priority", { user_id: KIOSK_USER_ID }),
    PRIORITY_INTERVAL_MS
  );

  return (
    <KioskFrame>
      <div className="flex h-full flex-col">
        {screen === "idle" ? (
          <PlaceholderScreen
            title="대기 화면"
            note="2단계에서 노드 카드·24시간 차트·알림 바를 채웁니다."
            dashboard={dashboard}
            priority={priority}
            onTab={setScreen}
          />
        ) : (
          <PlaceholderScreen
            title={screen}
            note="해당 탭은 다음 단계에서 구현합니다."
            dashboard={dashboard}
            priority={priority}
            onTab={setScreen}
            onHome={() => setScreen("idle")}
          />
        )}

        <TabBar
          active={screen === "idle" ? null : screen}
          onChange={(t) => setScreen(t)}
        />
      </div>
    </KioskFrame>
  );
}

/**
 * 1단계 확인용 임시 화면.
 *
 * 확대 배율이 맞는지, 두 API가 실제로 응답하는지, 폴링이 도는지를
 * 아이패드에서 눈으로 확인하기 위한 것이다. 2단계부터 실제 화면으로
 * 하나씩 교체한다.
 */
function PlaceholderScreen({
  title,
  note,
  dashboard,
  priority,
  onTab,
  onHome,
}: {
  title: string;
  note: string;
  dashboard: ReturnType<typeof useKioskQuery<DashboardResponse>>;
  priority: ReturnType<typeof useKioskQuery<PriorityResponse>>;
  onTab: (t: ScreenKey) => void;
  onHome?: () => void;
}) {
  const [now, setNow] = useState(new Date());
  useEffect(() => {
    const t = window.setInterval(() => setNow(new Date()), 10_000);
    return () => window.clearInterval(t);
  }, []);

  const clock = now.toLocaleString("ko-KR", {
    month: "long",
    day: "numeric",
    weekday: "short",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });

  return (
    <>
      <TopBar
        left={
          onHome ? (
            <button onClick={onHome} className="py-1.5 text-[18px] font-semibold text-gray-300">
              ← 대기 화면
            </button>
          ) : (
            <Brand />
          )
        }
        right={clock}
      />

      <div className="flex-1 overflow-hidden px-[26px] py-[18px]">
        <div className="text-[24px] font-bold">{title}</div>
        <div className="mt-1 text-[16px] text-gray-300">{note}</div>

        <div className="mt-4 grid grid-cols-2 gap-3">
          <StatusCard
            label="GET /api/care/dashboard"
            state={dashboard}
            summary={(d) =>
              `노드 ${d.totals.nodes ?? "?"}개 · 온라인 ${d.totals.online ?? "?"} · 측정 ${
                d.totals.readings ?? "?"
              }건`
            }
          />
          <StatusCard
            label="GET /api/care/priority"
            state={priority}
            summary={(p) =>
              `보유 ${p.summary.total} · 산출 ${p.summary.scored} · 확인 필요 ${p.summary.needs_check}`
            }
          />
        </div>

        <div className="mt-3 rounded-[14px] border border-primary-100 bg-primary-50 p-4 text-[15px] text-gray-400">
          <div>
            API 기준 주소 <b>{API_BASE}</b> ({API_BASE_FROM_ENV ? "환경변수" : "기본값"})
          </div>
          <div className="mt-1">사용자 {KIOSK_USER_ID}</div>
          <div className="mt-1">
            표시 영역 {window.innerWidth} × {window.innerHeight} · 프레임 1024 × 600
          </div>
        </div>

        <button
          onClick={() => onTab("priority")}
          className="mt-4 h-[62px] rounded-[14px] bg-primary-500 px-[34px] text-[20px] font-semibold text-white"
        >
          점검 탭으로
        </button>
      </div>
    </>
  );
}

function StatusCard<T>({
  label,
  state,
  summary,
}: {
  label: string;
  state: ReturnType<typeof useKioskQuery<T>>;
  summary: (data: T) => string;
}) {
  const { data, error, loading, lastUpdated, refetch } = state;

  return (
    <div className="rounded-[16px] bg-white p-[17px_19px]">
      <div className="flex items-center justify-between">
        <span className="text-[15px] font-medium text-gray-300">{label}</span>
        <button onClick={refetch} className="text-[14px] font-medium text-primary-500">
          새로고침
        </button>
      </div>

      {loading && !data ? (
        <div className="mt-2 text-[18px] text-gray-300">불러오는 중…</div>
      ) : data ? (
        <div className="mt-2 text-[18px] font-medium">{summary(data)}</div>
      ) : null}

      {error ? (
        <div className="mt-2 rounded bg-gray-100 p-2 text-[13px] break-all">
          <div className="font-semibold text-[#E05A5A]">{error.summary}</div>
          <div className="mt-0.5">{error.message}</div>
          <div className="mt-0.5 text-gray-300">{error.url}</div>
        </div>
      ) : null}

      {lastUpdated ? (
        <div className="mt-2 text-[13px] text-gray-300">
          갱신 {lastUpdated.toLocaleTimeString("ko-KR", { hour12: false })}
        </div>
      ) : null}
    </div>
  );
}

export default KioskApp;