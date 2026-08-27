import { TopBar, TabBar, ErrorPanel, StaleBanner, Loading, STATUS, type TabKey } from "./ui";
import type { DashboardResponse, SkinResponse, SkinTrendPoint } from "./lib/types";
import type { QueryState } from "./lib/useKioskQuery";

/**
 * 탭2 — 피부.
 *
 * ── 두 종류의 값이 섞인다 ────────────────────────────────────
 * PSRI는 환경(절대습도·PM2.5)을 24시간 적분한 값이라 센서만 있으면 나온다.
 * ITA°와 홍반 지수는 AS7341로 피부를 재야 나오는 값이다. 측정 이력이
 * 없으면 오른쪽 카드는 "측정 전"이 되고, PSRI만 보인다.
 *
 * ── 진단하지 않는다 ──────────────────────────────────────────
 * ITA°와 홍반 지수는 피부과학에서 쓰는 표준 지표지만, 우리는 그 절대값으로
 * 무엇을 판정하지 않는다. 같은 부위를 반복 측정한 **변화 추이**만 보인다.
 * 화면 하단의 면책 문구는 장식이 아니라 이 시스템이 무엇을 하지 않는지를
 * 밝히는 부분이다.
 */

type Props = {
  skin: QueryState<SkinResponse>;
  dashboard: DashboardResponse | null;
  activeTab: TabKey;
  onTab: (t: TabKey) => void;
  onHome: () => void;
  onMeasure: () => void;
};

export function SkinScreen({ skin, dashboard, activeTab, onTab, onHome, onMeasure }: Props) {
  const { data, error, loading, lastUpdated } = skin;

  const node =
    dashboard?.nodes.find((n) => n.node_type === "ambient" && n.online) ??
    dashboard?.nodes.find((n) => n.online) ??
    null;

  const envText =
    node && node.temperature != null
      ? `${node.location_label || node.node_id} ${node.temperature.toFixed(1)}℃ / ${
          node.humidity != null ? `${node.humidity.toFixed(0)}%` : "—"
        }` +
        (node.absolute_humidity != null
          ? ` · 절대습도 ${node.absolute_humidity.toFixed(1)} g/m³`
          : "")
      : "센서 응답 없음";

  return (
    <div className="flex h-full flex-col">
      <TopBar
        left={
          <button onClick={onHome} className="text-[25px] font-bold">
            피부
          </button>
        }
        right={envText}
      />

      {error && data ? <StaleBanner error={error} lastUpdated={lastUpdated} /> : null}

      <div className="flex-1 overflow-hidden px-[26px] py-[18px]">
        {loading && !data ? (
          <Loading label="피부 정보를 불러오는 중" />
        ) : error && !data ? (
          <ErrorPanel error={error} onRetry={skin.refetch} />
        ) : data ? (
          <div className="grid h-full grid-cols-[1.15fr_1fr] gap-[14px]">
            <div className="flex min-h-0 flex-col gap-3">
              <PsriCard data={data} />
              {data.relation ? (
                <div className="rounded-[16px] border border-primary-100 bg-primary-50 p-[17px_19px]">
                  <div className="text-[15px] text-gray-300">환경과의 관계</div>
                  <div className="mt-1.5 text-[17px] leading-[1.5]">{data.relation}</div>
                </div>
              ) : null}
            </div>

            <MeasurementCard data={data} onMeasure={onMeasure} />
          </div>
        ) : null}
      </div>

      <TabBar active={activeTab} onChange={onTab} />
    </div>
  );
}

// ── PSRI ─────────────────────────────────────────────────────

const PSRI_BAND_COLOR = {
  good: STATUS.green,
  caution: STATUS.amber,
  check: STATUS.red,
} as const;

const PSRI_BAND_LABEL = {
  good: "양호",
  caution: "주의",
  check: "확인 권장",
} as const;

function PsriCard({ data }: { data: SkinResponse }) {
  const p = data.psri;
  const color = PSRI_BAND_COLOR[p.band];

  return (
    <div className="rounded-[16px] bg-white p-[17px_19px]">
      <div className="text-[15px] text-gray-300">피부 환경 위험 지수 (PSRI)</div>

      <div className="mt-1.5 flex items-baseline gap-2.5">
        <span className="text-[38px] font-bold tabular-nums" style={{ color }}>
          {Math.round(p.score)}
        </span>
        <span className="text-[17px] font-medium text-gray-300">
          {PSRI_BAND_LABEL[p.band]} · {p.window_hours}시간 적분값
        </span>
      </div>

      {/* 막대는 점수를 눈으로 가늠하기 위한 것이다. 색은 밴드를 따른다. */}
      <div className="mt-2.5 h-3 overflow-hidden rounded-full bg-gray-100">
        <div
          className="h-full rounded-full transition-[width] duration-700"
          style={{
            width: `${Math.max(0, Math.min(100, p.score))}%`,
            background: `linear-gradient(90deg, var(--color-primary-300), ${color})`,
          }}
        />
      </div>

      <div className="mt-2.5">
        <Factor label="건조 항 (절대습도 부족)" value={p.dryness} />
        <Factor label="자극 항 (PM2.5)" value={p.irritation} />
        <Factor
          label="개인 가중치"
          text={`${p.personal_weight.toFixed(1)}${p.personal_label ? ` (${p.personal_label})` : ""}`}
        />
      </div>
    </div>
  );
}

function Factor({ label, value, text }: { label: string; value?: number; text?: string }) {
  return (
    <div className="flex justify-between border-b border-gray-100 py-[7px] text-[16px] last:border-0">
      <span>{label}</span>
      <b className="tabular-nums">{text ?? Math.round(value ?? 0)}</b>
    </div>
  );
}

// ── 측정 결과 ────────────────────────────────────────────────

function MeasurementCard({ data, onMeasure }: { data: SkinResponse; onMeasure: () => void }) {
  const m = data.latest;

  return (
    <div className="flex min-h-0 flex-col rounded-[16px] bg-white p-[17px_19px]">
      <div className="text-[15px] text-gray-300">
        {m
          ? `최근 피부 측정 · ${new Date(m.measured_at).toLocaleDateString("ko-KR", {
              month: "long",
              day: "numeric",
            })}`
          : "피부 측정 기록 없음"}
      </div>

      {m ? (
        <>
          <div className="mt-2 grid grid-cols-2 gap-2.5">
            <div>
              <div className="text-[15px] text-gray-300">ITA°</div>
              <div className="mt-1.5 flex items-baseline gap-2">
                <span className="text-[32px] font-bold tabular-nums">
                  {m.ita?.toFixed(1) ?? "—"}
                </span>
                <span className="text-[17px] font-medium text-gray-300">{m.ita_class ?? ""}</span>
              </div>
            </div>
            <div>
              <div className="text-[15px] text-gray-300">홍반 지수 (a*)</div>
              <div className="mt-1.5 flex items-baseline gap-2">
                <span
                  className="text-[32px] font-bold tabular-nums"
                  style={{ color: STATUS.red }}
                >
                  {m.erythema?.toFixed(1) ?? "—"}
                </span>
                {m.erythema_delta != null ? (
                  <span className="text-[17px] font-medium text-gray-300">
                    {m.erythema_delta > 0 ? "▲" : "▼"} {Math.abs(m.erythema_delta).toFixed(1)}
                  </span>
                ) : null}
              </div>
            </div>
          </div>

          <div className="mt-3 text-[15px] text-gray-300">2주 추이 · 홍반 지수</div>
          <TrendChart points={data.trend} />
          {data.trend_note ? (
            <div className="text-[15px] text-gray-300">{data.trend_note}</div>
          ) : null}
        </>
      ) : (
        <div className="mt-3 text-[17px] leading-[1.55] text-gray-300">
          아직 측정 기록이 없습니다. 측정할 때마다 값을 쌓아 두었다가
          <br />
          같은 부위의 변화 추이를 보여드립니다.
        </div>
      )}

      <button
        onClick={onMeasure}
        className="mt-auto h-[62px] w-full rounded-[14px] bg-primary-500 text-[20px] font-semibold text-white"
      >
        피부 측정하기
      </button>

      {/* 이 문구는 지우지 않는다. 무엇을 하지 않는지 밝히는 부분이다. */}
      <div className="mt-2.5 text-[13px] leading-[1.5] text-gray-300">
        의학적 진단이 아닙니다. 피부과학 표준 지표인 ITA°와 홍반 지수의{" "}
        <b>변화 추이</b>만 제공하며, 피부 나이·질환 판정은 하지 않습니다.
      </div>
    </div>
  );
}

/**
 * 홍반 지수 추이.
 *
 * 눈금을 데이터에서 잡는다. 고정 범위를 쓰면 변화가 작을 때 직선처럼
 * 보이고, 클 때는 화면 밖으로 나간다.
 */
function TrendChart({ points }: { points: SkinTrendPoint[] }) {
  const vals = points.map((p) => p.erythema).filter((v): v is number => v != null);

  if (vals.length < 2) {
    return (
      <div className="my-2 flex h-[70px] items-center text-[15px] text-gray-300">
        추이를 그리려면 측정이 두 번 이상 필요합니다.
      </div>
    );
  }

  const W = 300;
  const H = 70;
  const PAD = 8;
  const min = Math.min(...vals);
  const max = Math.max(...vals);
  const span = max - min || 1;

  const xy = vals.map((v, i) => {
    const x = PAD + (i / (vals.length - 1)) * (W - PAD * 2);
    // 위쪽이 높은 값이 되도록 뒤집는다
    const y = PAD + (1 - (v - min) / span) * (H - PAD * 3);
    return [x, y] as const;
  });

  const last = xy[xy.length - 1];

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="my-1.5 w-full" style={{ height: 70 }}>
      {/* 기준선. 첫 측정값 위치에 점선을 둬서 얼마나 올랐는지 보이게 한다 */}
      <line
        x1={0}
        y1={xy[0][1]}
        x2={W}
        y2={xy[0][1]}
        stroke="#cbd0d6"
        strokeWidth={1}
        strokeDasharray="3 4"
      />
      <polyline
        points={xy.map(([x, y]) => `${x},${y}`).join(" ")}
        fill="none"
        stroke={STATUS.red}
        strokeWidth={2.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx={last[0]} cy={last[1]} r={4} fill={STATUS.red} />
    </svg>
  );
}

export default SkinScreen;