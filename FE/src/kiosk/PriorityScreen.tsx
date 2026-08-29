import { useState } from "react";
import { TopBar, TabBar, BAND_STYLE, STATUS, ErrorPanel, StaleBanner, Loading, type TabKey } from "./ui";
import type { PriorityItem, PriorityResponse, DashboardResponse } from "./lib/types";
import type { QueryState } from "./lib/useKioskQuery";

/**
 * 탭1 — 점검 우선순위.
 *
 * ── 이 화면이 말하는 것과 말하지 않는 것 ─────────────────────
 * 여기 있는 점수는 **어떤 제품부터 눈으로 확인할지 순서를 정하는 값**이다.
 * 변질 여부는 미생물·pH 시험 없이 알 수 없고, 이 화면은 그런 주장을 하지
 * 않는다. 그래서 문구는 "확인이 필요합니다"에서 멈춘다.
 *
 * 목업에 없지만 추가한 것이 둘이다.
 *
 * 1. 정보가 더 필요한 제품
 *    개봉일이나 보관 위치가 없으면 점수를 낼 수 없다. 서버는 이런 제품을
 *    목록에서 빼지 않고 skipped로 따로 준다. 화면에서도 감추지 않는다.
 *    감추면 사용자는 "내 세럼이 왜 목록에 없지"를 알 수 없다.
 *
 * 2. 근거 배지
 *    점수 옆에 실측·가정 시간을 함께 보인다. "8개월치를 측정했다"와
 *    "8개월 중 9일을 측정했다"는 전혀 다른 주장이고, 후자를 전자처럼
 *    보이게 두면 발표에서 곤란해진다.
 */

type Props = {
  priority: QueryState<PriorityResponse>;
  dashboard: DashboardResponse | null;
  activeTab: TabKey;
  onTab: (t: TabKey) => void;
  onHome: () => void;
  /** 측정하기 — 어느 제품을 잴지 사용자가 고른다. */
  onMeasure: () => void;
  onEvents: () => void;
  /** 제품을 누르면 확인 절차로. */
  onProtocol: (userProductId: string) => void;
};

export function PriorityScreen({
  priority,
  dashboard,
  activeTab,
  onTab,
  onHome,
  onMeasure,
  onEvents,
  onProtocol,
}: Props) {
  const { data, error, loading, lastUpdated } = priority;

  // 상단 오른쪽에 보관 노드의 현재 환경을 띄운다. 목업의
  // "화장대 서랍 26.8℃ / 52%" 자리다.
  const storage =
    dashboard?.nodes.find((n) => n.node_type === "storage" && n.online) ??
    dashboard?.nodes.find((n) => n.online) ??
    null;

  const storageText =
    storage && storage.temperature != null
      ? `${storage.location_label || storage.node_id} ${storage.temperature.toFixed(1)}℃` +
        (storage.humidity != null ? ` / ${storage.humidity.toFixed(0)}%` : "")
      : "센서 응답 없음";

  return (
    <div className="flex h-full flex-col">
      <TopBar
        left={
          <button onClick={onHome} className="text-[25px] font-bold">
            점검 우선순위
          </button>
        }
        right={storageText}
      />

      {error && data ? <StaleBanner error={error} lastUpdated={lastUpdated} /> : null}

      <div className="flex-1 overflow-hidden px-[26px] py-[18px]">
        {loading && !data ? (
          <Loading label="점검 목록을 불러오는 중" />
        ) : error && !data ? (
          <ErrorPanel error={error} onRetry={priority.refetch} />
        ) : data ? (
          <PriorityBody
            data={data}
            onMeasure={onMeasure}
            onEvents={onEvents}
            onProtocol={onProtocol}
          />
        ) : null}
      </div>

      <TabBar active={activeTab} onChange={onTab} />
    </div>
  );
}

function PriorityBody({
  data,
  onMeasure,
  onEvents,
  onProtocol,
}: {
  data: PriorityResponse;
  onMeasure: () => void;
  onEvents: () => void;
  onProtocol: (userProductId: string) => void;
}) {
  // 확인이 필요한 것과 지켜볼 것만 목록에 올린다. 정상 범위는 개수만
  // 알려준다. 열두 개를 전부 나열하면 어디부터 봐야 할지 알 수 없다.
  // 확인 결과가 있는 제품은 밴드와 무관하게 목록에 남긴다.
  //
  // 확인하고 나면 last_checked_at이 갱신되어 점수가 떨어지고, 그러면
  // 정상 범위로 내려가 목록에서 사라진다. 사용자 입장에서는 "냄새가
  // 난다"고 방금 답했는데 그 제품이 없어지는 셈이다.
  //
  // 점수는 "확인해 볼 순서"이고 확인 결과는 "사람이 실제로 본 것"이다.
  // 후자가 있으면 그것이 먼저다.
  // 확인한 제품은 결과와 무관하게 위쪽 목록에 남긴다. 방금 확인했는데
  // 접힌 곳으로 내려가면 결과를 다시 보기 어렵다.
  const inspected = (i: PriorityItem) => i.inspection != null;

  const listed = data.items.filter((i) => i.band !== "low" || inspected(i));
  const rest = data.items.filter((i) => i.band === "low" && !inspected(i));
  const restCount = rest.length;
  const [showRest, setShowRest] = useState(false);


  return (
    <div className="flex h-full flex-col">
      {/* 요약 */}
      <div className="flex flex-none items-baseline gap-[11px]">
        <span className="text-[16px] text-gray-300">
          보유 {data.summary.total}개 중 확인 필요
        </span>
        <span className="text-[35px] font-bold text-primary-500">
          {data.summary.needs_check}개
        </span>
        {data.summary.medium > 0 ? (
          <span className="text-[16px] text-gray-300">
            · 지켜볼 제품 {data.summary.medium}개
          </span>
        ) : null}
      </div>

      {/* 목록 */}
      <div className="mt-[13px] flex-1 overflow-y-auto pr-1">
        {listed.length === 0 ? (
          <div className="rounded-[15px] border border-primary-100 bg-primary-50 p-[19px]">
            <div className="text-[21px] font-bold">지금 확인할 제품이 없습니다</div>
            <div className="mt-1 text-[16px] text-gray-300">
              보관 중인 {data.summary.scored}개 모두 정상 범위입니다.
            </div>
          </div>
        ) : (
          listed.map((item) => (
            <ItemRow
              key={item.user_product_id}
              item={item}
              onOpen={() => onProtocol(item.user_product_id)}
            />
          ))
        )}

        {/* 정상 범위 제품도 열어볼 수 있어야 한다. 사용자가 그중 하나를
            직접 확인하거나 측정하고 싶을 수 있는데, 접어두기만 하면
            그 방법이 없다. */}
        {restCount > 0 ? (
          <div className="mt-2.5 overflow-hidden rounded-[15px] border border-primary-100 bg-primary-50">
            <button
              onClick={() => setShowRest((v) => !v)}
              className="flex w-full items-center gap-2 p-[15px_19px] text-left"
            >
              <span className="text-[16px] text-gray-300">나머지 {restCount}개</span>
              <span className="ml-auto text-[16px] font-medium text-primary-500">
                {showRest ? "접기 ▲" : "열어보기 ▼"}
              </span>
            </button>

            <div className="px-[19px] pb-[15px] text-[16px]">
              🟢 정상 범위입니다. 확인이나 측정을 원하시면 열어보세요.
            </div>

            {showRest ? (
              <div className="px-[13px] pb-[13px]">
                {rest.map((item) => (
                  <ItemRow
                    key={item.user_product_id}
                    item={item}
                    onOpen={() => onProtocol(item.user_product_id)}
                  />
                ))}
              </div>
            ) : null}
          </div>
        ) : null}

        {data.skipped.length > 0 ? <SkippedCard data={data} /> : null}
      </div>

      {/* 버튼 */}
      <div className="mt-[14px] flex flex-none gap-[11px]">
        {/* 어느 제품을 잴지는 모달에서 고른다. 예전에는 1순위 제품으로
            고정했는데, 사용자가 다른 제품을 재고 싶어도 방법이 없었다. */}
        <button
          onClick={onMeasure}
          disabled={data.items.length === 0}
          className="h-[62px] rounded-[14px] bg-primary-500 px-[34px] text-[20px] font-semibold text-white disabled:opacity-40"
        >
          측정하기
        </button>
        <button
          onClick={onEvents}
          className="h-[62px] rounded-[14px] border border-gray-200 bg-white px-[34px] text-[20px] font-semibold text-gray-400"
        >
          이벤트 이력
        </button>
      </div>
    </div>
  );
}

function ItemRow({ item, onOpen }: { item: PriorityItem; onOpen: () => void }) {
  const style = BAND_STYLE[item.band];
  const found = item.inspection?.findings ?? [];

  // 근거는 서버가 만든 문장을 그대로 쓴다. 화면에서 다시 조립하면
  // 서버 로직과 어긋나기 시작한다.
  const why = item.reasons.join(" · ");

  const d = item.detail;
  const measured = d.measured_hours ?? 0;
  const assumed = d.assumed_hours ?? 0;
  const total = measured + assumed;
  const measuredPct = total > 0 ? (measured / total) * 100 : 0;

  return (
    <button
      onClick={onOpen}
      className="mb-2.5 flex w-full items-center gap-4 rounded-[15px] bg-white p-[15px_19px] text-left active:bg-primary-50"
    >
      <div
        className="grid h-12 w-12 flex-none place-items-center rounded-[13px] text-[22px]"
        style={{ background: style.pill }}
      >
        {style.emoji}
      </div>

      <div className="min-w-0 flex-1">
        <div className="truncate text-[21px] font-bold">
          {item.name || "이름 없는 제품"}
        </div>

        {/* 사용자가 직접 확인한 결과.
            점수는 "확인해 볼 순서"이고 이쪽은 "사람이 실제로 본 것"이다.
            둘은 별개이므로 밴드 색을 쓰지 않는다. 이상이 없으면 초록,
            있으면 붉은 틀이다. 위험도 점수는 오른쪽에 그대로 남는다. */}
        {found.length > 0 ? (
          <div
            className="mt-1.5 inline-block rounded-[10px] border px-2.5 py-1 text-[15px] font-semibold"
            style={{
              borderColor: STATUS.red,
              background: BAND_STYLE.high.pill,
              color: STATUS.red,
            }}
          >
            {found.join(" · ")} 확인됨 · 주의가 필요합니다
          </div>
        ) : item.inspection?.clear ? (
          <div
            className="mt-1.5 inline-block rounded-[10px] border px-2.5 py-1 text-[15px] font-semibold"
            style={{
              borderColor: STATUS.green,
              background: BAND_STYLE.low.pill,
              color: STATUS.green,
            }}
          >
            직접 확인함 · 이상 없음
          </div>
        ) : null}
        <div className="mt-[3px] truncate text-[16px] text-gray-300">{why}</div>

        {/* 이 점수가 실측에 얼마나 근거하는지 숨기지 않는다. */}
        <div className="mt-[3px] text-[13px] text-gray-300">
          열이력 {formatHours(total)} 중 실측 {formatHours(measured)}
          {measuredPct < 50 ? ` (${measuredPct.toFixed(0)}%, 나머지는 20℃ 가정)` : ""}
          {d.excursion_counted === false ? " · 이탈 통계는 측정 부족으로 제외" : ""}
        </div>
      </div>

      <div className="ml-auto flex-none text-right">
        <div className="text-[29px] font-bold tabular-nums" style={{ color: style.text }}>
          {Math.round(item.score)}
        </div>
        <div className="text-[13px] text-gray-300">점검 순위 점수</div>
      </div>
    </button>
  );
}

/**
 * 점수를 낼 수 없는 제품.
 *
 * 서버가 무엇이 비었는지와 무엇을 하면 되는지를 함께 준다. 경고가 아니라
 * 안내이므로 색을 쓰지 않고 회색으로 둔다.
 */
function SkippedCard({ data }: { data: PriorityResponse }) {
  return (
    <div className="mt-2.5 rounded-[15px] border border-gray-200 bg-white p-[15px_19px]">
      <div className="text-[16px] text-gray-300">
        정보가 더 필요한 제품 {data.skipped.length}개
      </div>
      <div className="mt-1.5 space-y-1">
        {data.skipped.slice(0, 3).map((s) => (
          <div key={s.user_product_id} className="text-[16px]">
            <span className="font-semibold">{s.name || "이름 없는 제품"}</span>
            <span className="text-gray-300">
              {" — "}
              {s.missing.map((m) => m.title).join(", ")}
            </span>
          </div>
        ))}
        {data.skipped.length > 3 ? (
          <div className="text-[15px] text-gray-300">외 {data.skipped.length - 3}개</div>
        ) : null}
      </div>
      <div className="mt-1.5 text-[15px] text-gray-300">
        {data.skipped[0]?.missing[0]?.action ?? "앱에서 정보를 채우면 점검 순서에 포함됩니다."}
      </div>
    </div>
  );
}

function formatHours(h: number): string {
  if (h >= 720) return `${(h / 720).toFixed(1)}개월`;
  if (h >= 48) return `${Math.round(h / 24)}일`;
  return `${Math.round(h)}시간`;
}

export default PriorityScreen;