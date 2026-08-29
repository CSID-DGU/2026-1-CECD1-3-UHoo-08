import { useEffect, useState } from "react";
import { KioskFrame } from "./KioskFrame";
import { IdleScreen } from "./IdleScreen";
import { PriorityScreen } from "./PriorityScreen";
import { SkinScreen } from "./SkinScreen";
import { RecoScreen } from "./RecoScreen";
import { EnvScreen, readSavedRegion } from "./EnvScreen";
import { EventsScreen } from "./EventsScreen";
import { ProtocolScreen } from "./ProtocolScreen";
import { ProductPicker, toPickerProduct } from "./ProductPicker";
import { TabBar, TopBar, type TabKey } from "./ui";
import { KIOSK_USER_ID } from "./lib/kioskApi";
import { careGet } from "./lib/careApi";
import { useKioskQuery } from "./lib/useKioskQuery";
import type {
  DashboardResponse,
  EventsResponse,
  EnvironmentResponse,
  PriorityItem,
  PriorityResponse,
  RecommendationsResponse,
  SkinResponse,
} from "./lib/types";

/**
 * 키오스크 셸.
 *
 * 화면 전환은 URL이 아니라 상태로 한다. 홈 화면에서 실행할 때 경로가
 * 어긋나는 것을 피하기 위해서다(manifest의 start_url이 /kiosk 고정).
 *
 * ── 폴링 주기 ────────────────────────────────────────────────
 *   대시보드 60초 — 노드당 쿼리 2회를 쓴다. 30초로 줄이면 하루 17,000회다
 *   우선순위 5분  — 점수는 열이력 적산이라 분 단위로 변하지 않는다
 *   환경     10분 — 외부 날씨 API가 그보다 자주 갱신되지 않는다
 *   피부     10분 — PSRI는 24시간 적분값이라 더 자주 볼 이유가 없다
 *   추천     30분 — 추천이 몇 분마다 바뀌면 오히려 신뢰가 떨어진다
 */
const DASHBOARD_INTERVAL_MS = 60_000;
const PRIORITY_INTERVAL_MS = 5 * 60_000;
const ENVIRONMENT_INTERVAL_MS = 10 * 60_000;
const SKIN_INTERVAL_MS = 10 * 60_000;
const RECO_INTERVAL_MS = 30 * 60_000;

/** 탭 화면에서 이 시간 동안 아무 조작이 없으면 대기 화면으로 돌아간다. */
const IDLE_RETURN_MS = 3 * 60_000;

/** 조작으로 셀 이벤트. 키오스크는 터치뿐이지만 개발 중 확인을 위해 함께 듣는다. */
const ACTIVITY_EVENTS = ["pointerdown", "keydown", "wheel"] as const;

/** 대기 화면 + 탭 4개 + 탭 아래로 들어가는 하위 화면들. */
export type ScreenKey =
  | "idle" | TabKey | "measure" | "events" | "skinRun" | "protocol";

/** 하위 화면에 있을 때 어느 탭이 켜져 보여야 하는지. */
const OWNER_TAB: Record<"measure" | "events" | "skinRun" | "protocol", TabKey> = {
  measure: "priority",
  events: "priority",
  skinRun: "skin",
  protocol: "priority",
};

/** 알림 바에 쓸 pending 수. 대기 화면에 있을 때만 필요하다. */
const EVENTS_INTERVAL_MS = 5 * 60_000;

export function KioskApp() {
  const [screen, setScreen] = useState<ScreenKey>("idle");
  const [target, setTarget] = useState<PriorityItem | null>(null);
  /**
   * 확인 결과 이상이 발견되어 대체품을 보러 넘어온 제품.
   *
   * 점검 화면이 "새 제품으로 바꾸시는 편이 좋겠습니다"라고 안내한 뒤
   * 추천 탭으로 넘긴다. 그 안내가 빈말이 되지 않으려면 추천 탭이 그
   * 제품을 알아야 한다.
   */
  const [replaceFor, setReplaceFor] = useState<string | null>(null);
  const [region, setRegion] = useState<string>(readSavedRegion);
  // 확인 절차 화면이 볼 제품. 점검 목록이나 이벤트 안내에서 넘어온다.
  const [protocolTarget, setProtocolTarget] = useState<string | null>(null);
  // 확인 절차를 마쳤을 때 돌아갈 곳. 점검 탭에서 들어왔는지 이벤트에서
  // 들어왔는지에 따라 달라야 한다. 고정해 두면 이벤트 → 확인 → 완료에서
  // 엉뚱한 화면으로 가거나, 조건이 어긋나 빈 화면이 뜬다.
  const [protocolBack, setProtocolBack] = useState<ScreenKey>("priority");
  // 이벤트에서 이어진 확인이면 그 id. 점검 목록에서 바로 들어오면 null.
  const [protocolEvent, setProtocolEvent] = useState<number | null>(null);
  // 여러 제품을 이어서 확인할 때의 대기열과 위치.
  const [queue, setQueue] = useState<string[]>([]);
  const [queueIndex, setQueueIndex] = useState(0);
  // 측정할 제품을 고르는 모달. 점검 탭의 "측정하기"가 연다.
  const [pickingMeasure, setPickingMeasure] = useState(false);

  const dashboard = useKioskQuery<DashboardResponse>(
    () => careGet<DashboardResponse>("/api/care/dashboard", { user_id: KIOSK_USER_ID }),
    DASHBOARD_INTERVAL_MS
  );

  const priority = useKioskQuery<PriorityResponse>(
    () => careGet<PriorityResponse>("/api/care/priority", { user_id: KIOSK_USER_ID }),
    PRIORITY_INTERVAL_MS
  );

  // 지역이 바뀌면 즉시 다시 부른다. deps에 넣어 전달한다.
  const environment = useKioskQuery<EnvironmentResponse>(
    () =>
      careGet<EnvironmentResponse>("/api/care/environment", {
        user_id: KIOSK_USER_ID,
        region,
      }),
    ENVIRONMENT_INTERVAL_MS,
    [region]
  );

  const skin = useKioskQuery<SkinResponse>(
    () => careGet<SkinResponse>("/api/care/skin", { user_id: KIOSK_USER_ID }),
    SKIN_INTERVAL_MS
  );

  // 대기 화면 알림 바가 쓴다. 목록 자체는 이벤트 화면이 따로 부른다.
  const events = useKioskQuery<EventsResponse>(
    () => careGet<EventsResponse>("/api/care/events", { user_id: KIOSK_USER_ID }),
    EVENTS_INTERVAL_MS
  );

  const reco = useKioskQuery<RecommendationsResponse>(
    () =>
      careGet<RecommendationsResponse>("/api/care/recommendations", {
        user_id: KIOSK_USER_ID,
        replace_for: replaceFor ?? undefined,
      }),
    RECO_INTERVAL_MS,
    // 대상이 바뀌면 곧바로 다시 부른다. 폴링을 기다리면 빈 화면을 본다.
    [replaceFor]
  );

  const activeTab: TabKey =
    screen === "idle"
      ? "priority"
      : screen === "measure" || screen === "events" ||
        screen === "skinRun" || screen === "protocol"
        ? OWNER_TAB[screen]
        : screen;

  /**
   * 무조작 복귀.
   *
   * 시연 중 누군가 탭을 열어둔 채 자리를 뜨면 다음 사람이 남의 화면을
   * 본다. 대기 화면은 멀리서도 읽히는 화면이므로 기본으로 돌려놓는다.
   *
   * 대기 화면에서는 타이머를 걸지 않는다. 이미 돌아갈 곳이라 걸어봐야
   * 아이패드만 계속 깨워둔다.
   */
  useEffect(() => {
    if (screen === "idle") return;

    let timer = 0;
    const reset = () => {
      window.clearTimeout(timer);
      timer = window.setTimeout(() => setScreen("idle"), IDLE_RETURN_MS);
    };
    reset();

    // 캡처 단계로 듣는다. 버튼이 이벤트를 삼켜도 타이머는 되살아나야 한다.
    const opts = { capture: true, passive: true } as const;
    for (const name of ACTIVITY_EVENTS) {
      window.addEventListener(name, reset, opts);
    }

    return () => {
      window.clearTimeout(timer);
      for (const name of ACTIVITY_EVENTS) {
        window.removeEventListener(name, reset, { capture: true });
      }
    };
    // screen이 바뀌는 것 자체가 조작이므로, 화면을 옮길 때마다 다시 잰다.
  }, [screen]);

  const goHome = () => setScreen("idle");

  return (
    <KioskFrame>
      {pickingMeasure ? (
        <ProductPicker
          title="어떤 제품을 측정할까요?"
          products={(priority.data?.items ?? []).map(toPickerProduct)}
          onPick={(ids) => {
            setPickingMeasure(false);
            const found = priority.data?.items.find(
              (i) => i.user_product_id === ids[0]
            );
            if (found) setTarget(found);
            setScreen("measure");
          }}
          onClose={() => setPickingMeasure(false)}
        />
      ) : null}

      {screen === "idle" ? (
        // 대기 화면에는 탭바를 두지 않는다. 멀리서 보는 화면이라
        // 색과 숫자만 남기고, 조작은 화면을 누르는 것 하나로 좁힌다.
        <div className="flex h-full flex-col">
          <IdleScreen
            dashboard={dashboard.data}
            priority={priority.data}
            error={dashboard.error}
            alert={events.data?.summary.alert ?? null}
            onAlert={() => setScreen("events")}
            onEnter={() => setScreen("priority")}
          />
        </div>
      ) : screen === "priority" ? (
        <PriorityScreen
          priority={priority}
          dashboard={dashboard.data}
          activeTab={activeTab}
          onTab={setScreen}
          onHome={goHome}
          onMeasure={() => setPickingMeasure(true)}
          onEvents={() => setScreen("events")}
          onProtocol={(id) => {
            setProtocolTarget(id);
            setProtocolEvent(null);
            setQueue([id]);
            setQueueIndex(0);
            setProtocolBack("priority");
            setScreen("protocol");
          }}
        />
      ) : screen === "skin" ? (
        <SkinScreen
          skin={skin}
          dashboard={dashboard.data}
          activeTab={activeTab}
          onTab={setScreen}
          onHome={goHome}
          onMeasure={() => setScreen("skinRun")}
        />
      ) : screen === "reco" ? (
        <RecoScreen
          reco={reco}
          dashboard={dashboard.data}
          activeTab={activeTab}
          onTab={setScreen}
          onHome={goHome}
          // 대체 추천을 보다가 평소 추천으로 돌아갈 수단.
          onClearReplace={replaceFor ? () => setReplaceFor(null) : undefined}
        />
      ) : screen === "env" ? (
        <EnvScreen
          environment={environment}
          region={region}
          onRegionChange={setRegion}
          activeTab={activeTab}
          onTab={setScreen}
          onHome={goHome}
        />
      ) : screen === "events" ? (
        <EventsScreen
          activeTab={activeTab}
          onTab={setScreen}
          onBack={() => setScreen("priority")}
          onProduct={(ids, eventId) => {
            if (ids.length === 0) return;
            setQueue(ids);
            setQueueIndex(0);
            setProtocolTarget(ids[0]);
            setProtocolEvent(eventId);
            setProtocolBack("events");
            setScreen("protocol");
          }}
        />
      ) : screen === "protocol" && protocolTarget ? (
        <ProtocolScreen
          // key를 주어 제품이 바뀌면 화면 상태(선택·결과)가 초기화된다.
          // 없으면 앞 제품에서 고른 항목이 남는다.
          key={protocolTarget}
          userProductId={protocolTarget}
          // 이상이 발견됐을 때 "비슷한 제품 보기"로 추천 탭에 넘긴다.
          onSeeAlternatives={(id) => {
            setReplaceFor(id);
            setScreen("reco");
          }}
          // 이벤트는 마지막 제품에서만 닫는다. 중간에 닫으면 남은 제품을
          // 확인하는 동안 질문이 이미 사라진 상태가 된다.
          eventId={queueIndex === queue.length - 1 ? protocolEvent : null}
          step={{ index: queueIndex + 1, total: queue.length }}
          onNext={
            queueIndex < queue.length - 1
              ? () => {
                  const next = queueIndex + 1;
                  setQueueIndex(next);
                  setProtocolTarget(queue[next]);
                }
              : undefined
          }
          activeTab={activeTab}
          onTab={setScreen}
          onBack={() => {
            // 확인 결과가 이벤트 상태에도 반영되므로 다시 부른다.
            // 그러지 않으면 방금 고른 항목이 목록에 나타나지 않는다.
            events.refetch();
            priority.refetch();
            setScreen(protocolBack);
          }}
          onMeasure={() => setScreen("measure")}
        />
      ) : screen === "protocol" ? (
        // target이 비어 있는데 protocol로 온 경우. 원래는 일어나지 않지만
        // 빈 화면을 띄우느니 목록으로 돌려보낸다.
        <Pending
          title="확인 절차"
          back="← 점검 우선순위"
          onBack={() => setScreen("priority")}
          activeTab={activeTab}
          onTab={setScreen}
          note="확인할 제품이 선택되지 않았습니다."
          detail="점검 목록에서 제품을 눌러 주세요."
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
      ) : screen === "skinRun" ? (
        <Pending
          title="피부 측정"
          back="← 피부"
          onBack={() => setScreen("skin")}
          activeTab={activeTab}
          onTab={setScreen}
          note="측정 노드 연결과 측정 절차가 아직 없습니다."
          detail="측정부를 손등 안쪽에 대고 차광 커버가 완전히 닿은 상태로 재야 합니다. 같은 부위를 반복해야 비교가 성립하므로, 부위 안내 화면이 함께 필요합니다."
        />
      ) : (
        <Pending
          title="이벤트 이력"
          back="← 점검 우선순위"
          onBack={() => setScreen("priority")}
          activeTab={activeTab}
          onTab={setScreen}
          note="risk_events 조회 API가 아직 없습니다."
          detail="GET /api/care/events 추가가 먼저입니다. 고온 노출·이탈 이벤트를 시간순으로 보여주는 화면입니다."
        />
      )}
    </KioskFrame>
  );
}

/**
 * 아직 구현하지 않은 화면.
 *
 * 빈 화면을 두지 않는 이유: 시연 중 잘못 눌렀을 때 아무것도 없으면
 * 고장처럼 보인다. 무엇이 들어올 자리인지 적어두면 화면이 비어 보이지 않는다.
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