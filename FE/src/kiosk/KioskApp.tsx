import { useState } from "react";
import { KioskFrame } from "./KioskFrame";
import { IdleScreen } from "./IdleScreen";
import { PriorityScreen } from "./PriorityScreen";
import { TabBar, TopBar, type TabKey } from "./ui";
import { kioskGet, KIOSK_USER_ID } from "./lib/kioskApi";
import { useKioskQuery } from "./lib/useKioskQuery";
import type { DashboardResponse, PriorityItem, PriorityResponse } from "./lib/types";

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

/** 대기 화면 + 탭 4개 + 탭 아래로 들어가는 하위 화면들. */
export type ScreenKey = "idle" | TabKey | "measure" | "events";

/** 하위 화면에 있을 때 어느 탭이 켜져 보여야 하는지. */
const OWNER_TAB: Record<"measure" | "events", TabKey> = {
  measure: "priority",
  events: "priority",
};

export function KioskApp() {
  const [screen, setScreen] = useState<ScreenKey>("idle");
  const [target, setTarget] = useState<PriorityItem | null>(null);

  const dashboard = useKioskQuery<DashboardResponse>(
    () => kioskGet<DashboardResponse>("/api/care/dashboard", { user_id: KIOSK_USER_ID }),
    DASHBOARD_INTERVAL_MS
  );

  const priority = useKioskQuery<PriorityResponse>(
    () => kioskGet<PriorityResponse>("/api/care/priority", { user_id: KIOSK_USER_ID }),
    PRIORITY_INTERVAL_MS
  );

  const activeTab: TabKey =
    screen === "idle"
      ? "priority"
      : screen === "measure" || screen === "events"
        ? OWNER_TAB[screen]
        : screen;

  const goHome = () => setScreen("idle");

  return (
    <KioskFrame>
      {screen === "idle" ? (
        <div className="flex h-full flex-col">
          <IdleScreen
            dashboard={dashboard.data}
            priority={priority.data}
            error={dashboard.error}
            onEnter={() => setScreen("priority")}
          />
          <TabBar active={null} onChange={(t) => setScreen(t)} />
        </div>
      ) : screen === "priority" ? (
        <PriorityScreen
          priority={priority}
          dashboard={dashboard.data}
          activeTab={activeTab}
          onTab={setScreen}
          onHome={goHome}
          onMeasure={(item) => {
            setTarget(item);
            setScreen("measure");
          }}
          onEvents={() => setScreen("events")}
        />
      ) : screen === "measure" ? (
        <Pending
          title="광학 측정"
          back="← 점검 우선순위"
          onBack={() => setScreen("priority")}
          activeTab={activeTab}
          onTab={setScreen}
          note={
            target
              ? `${target.name ?? "선택한 제품"} 측정 흐름은 다음 단계에서 구현합니다.`
              : "측정 흐름은 다음 단계에서 구현합니다."
          }
          detail="백색 표준판으로 기준을 잡고 → 측정 → 확인 항목 안내 → 사용자 피드백 순으로 네 화면이 필요합니다. AS7341 재장착 반복성을 더 낮춘 뒤에 붙입니다."
        />
      ) : screen === "events" ? (
        <Pending
          title="이벤트 이력"
          back="← 점검 우선순위"
          onBack={() => setScreen("priority")}
          activeTab={activeTab}
          onTab={setScreen}
          note="risk_events 조회 API가 아직 없습니다."
          detail="GET /api/care/events 추가가 먼저입니다. 고온 노출·이탈 이벤트를 시간순으로 보여주는 화면입니다."
        />
      ) : screen === "skin" ? (
        <Pending
          title="피부"
          back="← 대기 화면"
          onBack={goHome}
          activeTab={activeTab}
          onTab={setScreen}
          note="AS7341 피부 측정 흐름이 아직 없습니다."
          detail="skin_measurements 테이블은 있으나 측정 절차와 조회 API가 남았습니다. 광학 지그 반복성이 정리된 뒤에 붙입니다."
        />
      ) : screen === "reco" ? (
        <Pending
          title="추천"
          back="← 대기 화면"
          onBack={goHome}
          activeTab={activeTab}
          onTab={setScreen}
          note="기존 추천 파이프라인을 키오스크에 붙이는 작업이 남았습니다."
          detail="모바일 앱의 추천 API를 그대로 쓰되, 키오스크는 로그인이 없어 사용자 식별 방법을 먼저 정해야 합니다."
        />
      ) : (
        <Pending
          title="환경"
          back="← 대기 화면"
          onBack={goHome}
          activeTab={activeTab}
          onTab={setScreen}
          note="노드 카드와 24시간 차트가 들어갈 자리입니다."
          detail="차트에 필요한 시계열이 현재 API에 없습니다. GET /api/care/history 추가가 선행되어야 합니다."
        />
      )}
    </KioskFrame>
  );
}

/**
 * 아직 구현하지 않은 화면.
 *
 * 빈 화면을 두지 않는 이유: 시연 중 잘못 눌렀을 때 아무것도 없으면
 * 고장처럼 보인다. 무엇이 들어올 자리이고 무엇이 선행되어야 하는지
 * 적어두면 화면이 비어 보이지 않는다.
 */
function Pending({
  title,
  note,
  detail,
  back,
  onBack,
  activeTab,
  onTab,
}: {
  title: string;
  note: string;
  detail: string;
  back: string;
  onBack: () => void;
  activeTab: TabKey;
  onTab: (t: TabKey) => void;
}) {
  return (
    <div className="flex h-full flex-col">
      <TopBar
        left={
          <button onClick={onBack} className="text-[18px] font-semibold text-gray-300">
            {back}
          </button>
        }
        right={title}
      />

      <div className="flex flex-1 flex-col items-center justify-center gap-3 px-[80px] text-center">
        <div className="text-[28px] font-bold">{title}</div>
        <div className="text-[19px] text-gray-400">{note}</div>
        <div className="max-w-[640px] text-[16px] leading-[1.6] text-gray-300">{detail}</div>
      </div>

      <TabBar active={activeTab} onChange={onTab} />
    </div>
  );
}

export default KioskApp;