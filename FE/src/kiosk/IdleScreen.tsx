import { useEffect, useState } from "react";
import { KioskAura } from "./KioskAura";
import { Brand } from "./ui";
import { computeAura, pickReadings, LEVEL_LABEL, type Reading } from "./lib/auraState";
import type { DashboardResponse, PriorityResponse } from "./lib/types";
import type { KioskApiError } from "./lib/kioskApi";

/**
 * 대기 화면.
 *
 * 배경은 끊기지 않고 계속 흐른다. 그 위에 패널만 5초마다 바뀐다. 교대로
 * 만들지 않은 이유는, 심사위원이 다가온 순간에 숫자 차례가 아니면 화면이
 * 텅 비어 보이기 때문이다. 색은 언제나 보인다.
 *
 * 화면 아무 데나 누르면 점검 탭으로 간다. 탭바는 그대로 두는데, 시연 중
 * 원하는 탭으로 바로 가야 할 때가 있어서다.
 */

/** 패널이 바뀌는 주기. */
const SWAP_MS = 5000;
/** 페이드 시간. 이 값의 두 배가 SWAP_MS를 넘으면 안 된다. */
const FADE_MS = 900;

type Props = {
  dashboard: DashboardResponse | null;
  priority: PriorityResponse | null;
  error: KioskApiError | null;
  onEnter: () => void;
};

export function IdleScreen({ dashboard, priority, error, onEnter }: Props) {
  const aura = computeAura(dashboard, priority);
  const readings = pickReadings(dashboard);

  const [slot, setSlot] = useState(0);
  useEffect(() => {
    const t = window.setInterval(() => setSlot((s) => (s + 1) % 2), SWAP_MS);
    return () => window.clearInterval(t);
  }, []);

  // 다른 탭에 가려져 있으면 셰이더를 멈춘다. 아이패드 발열을 줄인다.
  const [hidden, setHidden] = useState(document.hidden);
  useEffect(() => {
    const on = () => setHidden(document.hidden);
    document.addEventListener("visibilitychange", on);
    return () => document.removeEventListener("visibilitychange", on);
  }, []);

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
    <div
      className="relative flex-1 overflow-hidden"
      onPointerDown={onEnter}
      role="button"
      tabIndex={0}
    >
      <KioskAura color={aura.color} fallback={aura.fallback} paused={hidden} />

      {/* 배경이 밝은 쪽으로 흐를 때 글자가 묻히지 않도록 위아래를 눌러준다 */}
      <div
        className="absolute inset-0"
        style={{
          background:
            "linear-gradient(180deg, rgba(16,18,22,0.42) 0%, rgba(16,18,22,0.12) 38%, rgba(16,18,22,0.55) 100%)",
        }}
      />

      <div className="relative flex h-full flex-col px-[46px] pt-[26px] pb-[22px] text-white">
        <div className="flex flex-none items-start justify-between">
          <div className="drop-shadow-[0_2px_10px_rgba(0,0,0,0.45)]">
            <Brand />
          </div>
          <div className="text-[18px] font-medium tabular-nums opacity-85">{clock}</div>
        </div>

        {/* 두 패널을 겹쳐두고 투명도만 바꾼다. 자리를 옮기면 배경이 출렁여 보인다. */}
        <div className="relative flex-1">
          <Panel show={slot === 0}>
            <ReadingRow readings={readings} error={error} />
          </Panel>
          <Panel show={slot === 1}>
            <NoticeBlock aura={aura} readings={readings} />
          </Panel>
        </div>

        {/* 색의 근거. 이 줄은 패널과 상관없이 항상 보인다. */}
        <div className="flex flex-none items-center gap-3">
          <span
            className="rounded-full bg-white/18 px-[14px] py-[5px] text-[15px] font-semibold backdrop-blur-sm"
            style={{ boxShadow: "inset 0 0 0 1px rgba(255,255,255,0.28)" }}
          >
            {LEVEL_LABEL[aura.level]}
          </span>
          <span className="text-[17px] font-medium opacity-90">{aura.lead.line}</span>
        </div>
      </div>
    </div>
  );
}

/** 겹쳐 둔 채로 투명도만 바꾸는 껍데기. */
function Panel({ show, children }: { show: boolean; children: React.ReactNode }) {
  return (
    <div
      className="absolute inset-0 flex flex-col justify-center"
      style={{
        opacity: show ? 1 : 0,
        transform: show ? "translateY(0)" : "translateY(10px)",
        transition: `opacity ${FADE_MS}ms ease, transform ${FADE_MS}ms ease`,
        pointerEvents: "none",
      }}
    >
      {children}
    </div>
  );
}

// ── 패널 1: 숫자 ─────────────────────────────────────────────

function ReadingRow({
  readings,
  error,
}: {
  readings: ReturnType<typeof pickReadings>;
  error: KioskApiError | null;
}) {
  const items = [readings.temp, readings.humidity, readings.pm25].filter(
    (r): r is Reading => r !== null
  );

  // 값이 없으면 왜 없는지 보여준다. 아이패드에는 개발자 도구가 없다.
  if (items.length === 0) {
    return (
      <div className="text-[22px] font-medium opacity-85">
        {error ? (
          <>
            <div>측정값을 불러오지 못했습니다 · {error.summary}</div>
            <div className="mt-2 text-[15px] break-all opacity-60">{error.url}</div>
          </>
        ) : (
          "측정값을 기다리는 중입니다"
        )}
      </div>
    );
  }

  return (
    <div className="flex items-end gap-[54px]">
      {items.map((r) => (
        <div key={r.label}>
          <div className="text-[17px] font-medium opacity-70">{r.label}</div>
          <div className="mt-1 flex items-baseline gap-1.5 drop-shadow-[0_3px_14px_rgba(0,0,0,0.4)]">
            <span className="text-[76px] leading-none font-bold tabular-nums">{r.value}</span>
            <span className="text-[24px] font-semibold opacity-80">{r.unit}</span>
          </div>
          <div className="mt-1.5 text-[15px] opacity-60">
            {r.where}
            {r.ago ? <span className="ml-2 opacity-80">{r.ago}</span> : null}
          </div>
        </div>
      ))}
    </div>
  );
}

// ── 패널 2: 안내문 ───────────────────────────────────────────

/**
 * 안내문과 숫자를 함께 띄운다. 문구만 두면 보는 사람이 근거를 못 보고,
 * 근거 없이 색만 강하면 각자 최악을 상상한다.
 */
function NoticeBlock({
  aura,
  readings,
}: {
  aura: ReturnType<typeof computeAura>;
  readings: ReturnType<typeof pickReadings>;
}) {
  const bad = aura.factors.filter((f) => f.level !== "good");
  const lines = (bad.length > 0 ? bad : aura.factors).slice(0, 3);

  const items = [readings.temp, readings.humidity, readings.pm25].filter(
    (r): r is Reading => r !== null
  );

  return (
    <div>
      <div className="text-[42px] leading-tight font-bold drop-shadow-[0_3px_14px_rgba(0,0,0,0.45)]">
        {aura.notice ?? "보관하기 좋은 상태입니다"}
      </div>

      <div className="mt-4 flex flex-col gap-2">
        {lines.map((f) => (
          <div key={f.key} className="flex items-center gap-2.5 text-[21px] font-medium opacity-90">
            <i className="h-2 w-2 flex-none rounded-full bg-current opacity-60" />
            {f.line}
          </div>
        ))}
      </div>

      {/* 안내문 차례에도 숫자가 사라지지 않게 작게 붙여 둔다 */}
      {items.length > 0 ? (
        <div className="mt-5 flex gap-6 text-[17px] font-medium tabular-nums opacity-70">
          {items.map((r) => (
            <span key={r.label}>
              {r.label} {r.value}
              {r.unit}
            </span>
          ))}
        </div>
      ) : null}
    </div>
  );
}

export default IdleScreen;
