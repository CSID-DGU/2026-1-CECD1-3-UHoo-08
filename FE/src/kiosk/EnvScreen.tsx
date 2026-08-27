import { useState } from "react";
import { TopBar, TabBar, ErrorPanel, StaleBanner, Loading, STATUS, type TabKey } from "./ui";
import type { EnvironmentResponse, IndoorNode, OutdoorWeather } from "./lib/types";
import type { QueryState } from "./lib/useKioskQuery";

/**
 * 탭4 — 오늘의 환경.
 *
 * ── 두 종류의 값이 섞인다 ────────────────────────────────────
 * 실내는 우리 센서가 잰 값이고, 실외는 외부 날씨 API에서 받은 값이다.
 * 출처가 다르므로 화면에서도 구분해 표시한다. "이 자외선 지수는 어디서
 * 온 것이냐"는 질문에 답할 수 있어야 한다.
 *
 * ── 케어 안내는 규칙 테이블이다 ──────────────────────────────
 * 서버가 조건에 맞는 문장을 고른다. LLM을 쓰지 않는다. 어떤 규칙이
 * 걸렸는지(brief.rules)를 함께 받아 근거를 접어둔 형태로 보인다.
 */

/** 지역 선택지. 예선(서울)과 본선(광주)을 미리 넣어둔다. */
const REGIONS = ["인천 부평", "서울 중구", "광주 서구"] as const;

const REGION_KEY = "hwadam.kiosk.region";

export function readSavedRegion(): string {
  try {
    return window.localStorage.getItem(REGION_KEY) || REGIONS[0];
  } catch {
    // 사파리 시크릿 모드 등에서 접근이 막힐 수 있다. 기본값으로 간다.
    return REGIONS[0];
  }
}

function saveRegion(r: string) {
  try {
    window.localStorage.setItem(REGION_KEY, r);
  } catch {
    /* 저장 못 해도 화면은 동작해야 한다 */
  }
}

type Props = {
  environment: QueryState<EnvironmentResponse>;
  region: string;
  onRegionChange: (r: string) => void;
  activeTab: TabKey;
  onTab: (t: TabKey) => void;
  onHome: () => void;
};

export function EnvScreen({
  environment,
  region,
  onRegionChange,
  activeTab,
  onTab,
  onHome,
}: Props) {
  const { data, error, loading, lastUpdated } = environment;
  const [mode, setMode] = useState<"indoor" | "outdoor">("outdoor");
  const [picking, setPicking] = useState(false);

  const today = new Date().toLocaleDateString("ko-KR", {
    month: "long",
    day: "numeric",
    weekday: "short",
  });

  return (
    <div className="flex h-full flex-col">
      <TopBar
        left={
          <button onClick={onHome} className="text-[25px] font-bold">
            오늘의 환경
          </button>
        }
        right={today}
      />

      {error && data ? <StaleBanner error={error} lastUpdated={lastUpdated} /> : null}

      <div className="flex-1 overflow-y-auto px-[26px] py-[18px]">
        {loading && !data ? (
          <Loading label="환경 정보를 불러오는 중" />
        ) : error && !data ? (
          <ErrorPanel error={error} onRetry={environment.refetch} />
        ) : data ? (
          <>
            <Segments
              mode={mode}
              onMode={setMode}
              region={region}
              indoorLabel={data.indoor[0]?.label ?? "실내"}
              onPick={() => setPicking(true)}
            />

            {mode === "outdoor" ? (
              <OutdoorCards outdoor={data.outdoor} />
            ) : (
              <IndoorCards nodes={data.indoor} />
            )}

            <Brief brief={data.brief} />

            {data.comparison ? (
              <div className="mt-3 rounded-[15px] border border-primary-100 bg-primary-50 p-[15px_19px]">
                <div className="text-[16px] text-gray-300">비교 · 실내 노드</div>
                <div className="mt-1.5 text-[17px]">{data.comparison}</div>
              </div>
            ) : null}

            {mode === "outdoor" && data.outdoor?.source ? (
              <div className="mt-2 text-[14px] text-gray-300">
                실외 값 출처 {data.outdoor.source}
                {data.outdoor.observed_at
                  ? ` · ${new Date(data.outdoor.observed_at).toLocaleString("ko-KR", {
                      month: "numeric",
                      day: "numeric",
                      hour: "2-digit",
                      minute: "2-digit",
                      hour12: false,
                    })} 기준`
                  : ""}
              </div>
            ) : null}
          </>
        ) : null}
      </div>

      {picking ? (
        <RegionPicker
          current={region}
          onSelect={(r) => {
            saveRegion(r);
            onRegionChange(r);
            setPicking(false);
          }}
          onClose={() => setPicking(false)}
        />
      ) : null}

      <TabBar active={activeTab} onChange={onTab} />
    </div>
  );
}

// ── 상단 선택 ────────────────────────────────────────────────

function Segments({
  mode,
  onMode,
  region,
  indoorLabel,
  onPick,
}: {
  mode: "indoor" | "outdoor";
  onMode: (m: "indoor" | "outdoor") => void;
  region: string;
  indoorLabel: string;
  onPick: () => void;
}) {
  const base =
    "h-[60px] rounded-[14px] border px-[26px] text-[18px] font-semibold";
  const on = "border-primary-500 bg-primary-500 text-white";
  const off = "border-gray-200 bg-white text-gray-400";

  return (
    <div className="mb-[14px] flex gap-[9px]">
      <button className={`${base} ${mode === "indoor" ? on : off}`} onClick={() => onMode("indoor")}>
        🏠 실내 · {indoorLabel}
      </button>
      <button className={`${base} ${mode === "outdoor" ? on : off}`} onClick={() => onMode("outdoor")}>
        🚶 외출 · {region}
      </button>
      <button className={`${base} ${off} ml-auto px-[20px]`} onClick={onPick}>
        변경
      </button>
    </div>
  );
}

// ── 수치 카드 ────────────────────────────────────────────────

function Cell({ k, v, unit, color }: { k: string; v: string; unit?: string; color?: string }) {
  return (
    <div className="rounded-[16px] bg-white p-[14px_8px] text-center">
      <div className="mb-[5px] text-[14px] text-gray-300">{k}</div>
      <div className="text-[28px] font-bold tabular-nums" style={color ? { color } : undefined}>
        {v}
        {unit ? <span className="text-[18px] font-medium"> {unit}</span> : null}
      </div>
    </div>
  );
}

function num(v: number | null | undefined, digits = 0): string {
  return v == null ? "—" : v.toFixed(digits);
}

function OutdoorCards({ outdoor }: { outdoor: OutdoorWeather | null }) {
  if (!outdoor) {
    return (
      <div className="rounded-[16px] border border-gray-200 bg-white p-[19px] text-[17px] text-gray-300">
        실외 날씨를 불러오지 못했습니다. 실내 값은 아래에서 볼 수 있습니다.
      </div>
    );
  }

  // 자외선 지수는 8 이상이 "매우 높음"이다(세계보건기구 기준).
  // 색을 입히되 문구로는 단정하지 않는다.
  const uvColor =
    outdoor.uv_index == null
      ? undefined
      : outdoor.uv_index >= 8
        ? STATUS.red
        : outdoor.uv_index >= 6
          ? STATUS.amber
          : undefined;

  // PM2.5 환경부 기준: 좋음 ≤15 / 보통 ≤35 / 나쁨 초과
  const pmColor =
    outdoor.pm25 == null
      ? undefined
      : outdoor.pm25 > 35
        ? STATUS.red
        : outdoor.pm25 > 15
          ? STATUS.amber
          : undefined;

  return (
    <div className="mb-[13px] grid grid-cols-4 gap-[11px]">
      <Cell k="기온" v={num(outdoor.temperature)} unit="℃" />
      <Cell k="습도" v={num(outdoor.humidity)} unit="%" />
      <Cell k="자외선" v={num(outdoor.uv_index)} color={uvColor} />
      <Cell k="초미세먼지" v={num(outdoor.pm25)} color={pmColor} />
    </div>
  );
}

function IndoorCards({ nodes }: { nodes: IndoorNode[] }) {
  const n = nodes.find((x) => x.online) ?? nodes[0];

  if (!n) {
    return (
      <div className="rounded-[16px] border border-gray-200 bg-white p-[19px] text-[17px] text-gray-300">
        등록된 실내 노드가 없습니다.
      </div>
    );
  }

  // 절대습도 7 g/m³ 미만이 건조 기준(humidity.py와 같은 값).
  const dryColor =
    n.absolute_humidity != null && n.absolute_humidity < 7 ? STATUS.amber : undefined;

  return (
    <>
      <div className="mb-[13px] grid grid-cols-4 gap-[11px]">
        <Cell k="온도" v={num(n.temperature, 1)} unit="℃" />
        <Cell k="상대습도" v={num(n.humidity)} unit="%" />
        <Cell k="절대습도" v={num(n.absolute_humidity, 1)} unit="g/m³" color={dryColor} />
        <Cell k="초미세먼지" v={num(n.pm25)} />
      </div>
      {!n.online ? (
        <div className="mb-[13px] text-[15px] text-gray-300">
          {n.label} 노드가 응답하지 않습니다. 마지막으로 받은 값입니다.
        </div>
      ) : null}
    </>
  );
}

// ── 케어 안내 ────────────────────────────────────────────────

function Brief({ brief }: { brief: { headline: string; lines: string[]; rules: string[] } }) {
  const [showRules, setShowRules] = useState(false);

  return (
    <div className="rounded-[14px] border-l-4 border-primary-500 bg-primary-50 p-[15px_19px]">
      <div className="mb-[7px] flex items-center justify-between">
        <span className="text-[15px] font-semibold text-primary-500">✦ 오늘의 케어 안내</span>
        {brief.rules.length > 0 ? (
          <button
            onClick={() => setShowRules((s) => !s)}
            className="text-[14px] font-medium text-gray-300"
          >
            {showRules ? "근거 숨기기" : "근거 보기"}
          </button>
        ) : null}
      </div>

      <div className="text-[20px] leading-[1.55] font-semibold">{brief.headline}</div>
      {brief.lines.map((line, i) => (
        <p key={i} className="mt-1 text-[19px] leading-[1.55]">
          {line}
        </p>
      ))}

      {showRules ? (
        <div className="mt-2 border-t border-primary-100 pt-2 text-[15px] text-gray-300">
          적용된 규칙 · {brief.rules.join(" / ")}
        </div>
      ) : null}
    </div>
  );
}

// ── 지역 선택 ────────────────────────────────────────────────

function RegionPicker({
  current,
  onSelect,
  onClose,
}: {
  current: string;
  onSelect: (r: string) => void;
  onClose: () => void;
}) {
  return (
    <div
      className="absolute inset-0 z-10 flex items-center justify-center bg-black/35"
      onPointerDown={onClose}
    >
      <div
        className="w-[440px] rounded-[18px] bg-white p-[22px]"
        onPointerDown={(e) => e.stopPropagation()}
      >
        <div className="text-[22px] font-bold">외출 지역</div>
        <div className="mt-1 text-[15px] text-gray-300">
          선택한 지역의 날씨로 케어 안내를 만듭니다.
        </div>

        <div className="mt-3 space-y-2">
          {REGIONS.map((r) => (
            <button
              key={r}
              onClick={() => onSelect(r)}
              className={
                "h-[58px] w-full rounded-[14px] border px-4 text-left text-[19px] font-semibold " +
                (r === current
                  ? "border-primary-500 bg-primary-50 text-primary-500"
                  : "border-gray-200 bg-white")
              }
            >
              {r}
            </button>
          ))}
        </div>

        <button
          onClick={onClose}
          className="mt-3 h-[54px] w-full rounded-[14px] border border-gray-200 text-[18px] font-semibold text-gray-400"
        >
          닫기
        </button>
      </div>
    </div>
  );
}

export default EnvScreen;