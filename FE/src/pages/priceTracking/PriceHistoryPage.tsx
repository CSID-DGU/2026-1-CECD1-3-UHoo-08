import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  type PriceTrackingDetail,
  getPriceTrackingDetail,
  updateTracking,
} from "../../api/priceTrackingApi";
import { PageHeader } from "../../components/common/PageHeader";
import { Toggle } from "../../components/common/Toggle";
import AppLayout from "../../layouts/AppLayout";
import { MOCK_TRACKING_DETAIL_DEFAULT, MOCK_TRACKING_DETAILS } from "../../mocks/priceTracking";

const USE_MOCK = import.meta.env.VITE_USE_MOCK === "true";

const TABS = [
  { label: "1주", period: "DAILY" },
  { label: "2주", period: "WEEKLY" },
  { label: "한달", period: "MONTHLY" },
];

function fmt(n: number | null | undefined) {
  if (n == null) return "—";
  return n.toLocaleString("ko-KR") + "원";
}

export function PriceHistoryPage() {
  const navigate = useNavigate();
  const { trackingId } = useParams<{ trackingId: string }>();
  const [data, setData] = useState<PriceTrackingDetail | null>(null);
  const [activeTab, setActiveTab] = useState(0);
  const [loading, setLoading] = useState(true);
  const [showSheet, setShowSheet] = useState(false);
  const [sheetEverOpened, setSheetEverOpened] = useState(false);
  const [newTargetPrice, setNewTargetPrice] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!trackingId) return;
    setLoading(true);
    if (USE_MOCK) {
      setData(MOCK_TRACKING_DETAILS[trackingId] ?? MOCK_TRACKING_DETAIL_DEFAULT);
      setLoading(false);
      return;
    }
    getPriceTrackingDetail(trackingId, TABS[activeTab].period)
      .then((res) => setData(res.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [trackingId, activeTab]);

  async function handleAlertToggle() {
    if (!trackingId || !data) return;
    const next = !data.alertEnabled;
    setData((d) => (d ? { ...d, alertEnabled: next } : d));
    await updateTracking(trackingId, { alertEnabled: next }).catch(() => {});
  }

  async function handleSaveTargetPrice() {
    if (!trackingId || !newTargetPrice) return;
    const price = parseInt(newTargetPrice.replace(/,/g, ""), 10);
    if (isNaN(price) || price <= 0) return;
    setSaving(true);
    try {
      await updateTracking(trackingId, { targetPrice: price });
      setData((d) => (d ? { ...d, targetPrice: price } : d));
      setShowSheet(false);
      setNewTargetPrice("");
    } catch {
      alert("목표가 설정에 실패했어요. 현재 최저가보다 낮은 금액으로 설정해주세요.");
    } finally {
      setSaving(false);
    }
  }

  const product = data?.product;
  const stats = data?.stats;

  return (
    <AppLayout>
      <div className="flex h-screen flex-col overflow-hidden">
        <div className="flex-1 overflow-y-auto scrollbar-none">
        <section className="flex flex-col px-6 pb-8 pt-10">
        <PageHeader onBack={() => navigate(-1)} />

        {/* 상품 정보 */}
        <section className="mt-4 flex items-center gap-4 rounded-xl border border-gray-200 bg-white p-4">
          <div className="h-[68px] w-[68px] shrink-0 overflow-hidden rounded-xl bg-primary-50">
            {product?.imageUrl && (
              <img
                src={product.imageUrl}
                alt={product.name}
                className="h-full w-full object-cover"
              />
            )}
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-body2 font-semibold text-gray-500">
              {loading ? "로딩 중..." : (product?.name ?? "—")}
            </p>
            <p className="text-caption text-gray-300">{product?.brand}</p>
            {stats?.currentLowestPrice != null && (
              <p className="mt-1 text-body2 text-gray-500">
                현재{" "}
                <strong className="ml-1 text-h4 text-primary-500">
                  {fmt(stats.currentLowestPrice)}
                </strong>
              </p>
            )}
          </div>
          {stats?.changePercent != null && stats.changePercent !== 0 && (
            <span
              className={`shrink-0 rounded-full px-3 py-1 text-caption ${
                stats.changePercent < 0
                  ? "bg-primary-50 text-primary-500"
                  : "bg-red-50 text-red-400"
              }`}
            >
              {stats.changePercent < 0 ? "" : "+"}
              {stats.changePercent}%
            </span>
          )}
        </section>

        {/* 기간 탭 */}
        <div className="mt-3 grid grid-cols-3 rounded-xl bg-gray-100 p-1">
          {TABS.map((tab, i) => (
            <button
              key={tab.label}
              className={`h-9 rounded-lg text-caption transition-colors ${
                i === activeTab
                  ? "bg-white text-gray-500 shadow-sm"
                  : "text-gray-300"
              }`}
              onClick={() => setActiveTab(i)}
              type="button"
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* 차트 */}
        <PriceChart
          history={data?.priceHistory ?? []}
          targetPrice={data?.targetPrice}
        />

        {/* 가격 통계 */}
        <section className="mt-3 rounded-xl border border-gray-200 bg-white p-4">
          {(
            [
              ["정가", fmt(stats?.originalPrice)],
              ["현재 최저가", fmt(stats?.currentLowestPrice)],
              ["역대 최저가", fmt(stats?.historicalLowest)],
            ] as [string, string][]
          ).map(([label, value]) => (
            <div
              className="flex justify-between border-b border-gray-100 py-2 last:border-b-0"
              key={label}
            >
              <span className="text-body2 text-gray-300">{label}</span>
              <span
                className={`text-body2 ${
                  label === "현재 최저가" ? "text-primary-500" : "text-gray-500"
                }`}
              >
                {value}
              </span>
            </div>
          ))}
        </section>

        {/* 구매처별 현재가 */}
        {data?.stores && data.stores.length > 0 && (
          <>
            <h2 className="mt-4 text-body1 text-gray-500">구매처별 현재가</h2>
            <div className="mt-3 grid gap-2">
              {data.stores.map((store) => (
                <div
                  key={store.storeName}
                  className={`flex items-center justify-between rounded-xl px-4 py-3 ${
                    store.isLowest
                      ? "border border-primary-100 bg-primary-50"
                      : "bg-gray-100"
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <span className="text-body2 text-gray-500">{store.storeName}</span>
                    {store.isLowest && (
                      <span className="rounded-full bg-primary-500 px-2 py-0.5 text-[10px] text-white">
                        최저
                      </span>
                    )}
                  </div>
                  <span
                    className={`text-body2 ${
                      store.isLowest ? "font-semibold text-primary-500" : "text-gray-500"
                    }`}
                  >
                    {fmt(store.price)}
                  </span>
                </div>
              ))}
            </div>
          </>
        )}

        {/* 하단 설정 */}
        <div className="mt-auto grid gap-3 pt-6">
          {/* 가격 도달 알림 */}
          <div className="flex items-center gap-3 rounded-xl border border-gray-200 p-4">
            <div className="flex-1">
              <p className="text-body2 text-gray-500">가격 도달 알림</p>
              <p className="text-caption text-gray-300">목표가 이하가 되면 즉시 알려드려요</p>
            </div>
            <button onClick={handleAlertToggle} type="button">
              <Toggle checked={data?.alertEnabled ?? false} />
            </button>
          </div>

          {/* 목표가 */}
          <div className="flex items-center gap-3 rounded-xl border border-gray-200 p-4">
            <div className="flex-1">
              <p className="text-caption text-gray-300">목표가</p>
              <p className="text-h2 text-gray-500">{fmt(data?.targetPrice)}</p>
            </div>
            <button
              className="rounded-xl bg-gray-100 px-4 py-2 text-body2 text-gray-500"
              onClick={() => {
                setNewTargetPrice(String(data?.targetPrice ?? ""));
                setSheetEverOpened(true);
                setShowSheet(true);
              }}
              type="button"
            >
              재설정
            </button>
          </div>
        </div>
        </section>
        </div>
      </div>

      {/* dim */}
      <div
        className="fixed inset-0 z-40 transition-all duration-300"
        style={{
          background: "rgba(0,0,0,0.35)",
          opacity: showSheet ? 1 : 0,
          pointerEvents: showSheet ? "auto" : "none",
        }}
        onClick={() => setShowSheet(false)}
      />

      {/* 바텀시트 */}
      <div
        className="fixed inset-x-0 bottom-0 z-50 mx-auto max-w-[430px] rounded-t-2xl bg-white p-6 shadow-2xl"
        style={{
          transform: showSheet ? "translateY(0)" : "translateY(105%)",
          transition: sheetEverOpened ? "transform 0.32s cubic-bezier(0.32, 0.72, 0, 1)" : "none",
          willChange: "transform",
          pointerEvents: showSheet ? "auto" : "none",
        }}
      >
        <div className="mx-auto mb-5 h-1 w-10 rounded-full bg-gray-200" />
        <h2 className="text-h3 text-gray-500">목표가 재설정</h2>
        <p className="mt-1 text-caption text-gray-300">
          현재 최저가({fmt(stats?.currentLowestPrice)})보다 낮게 설정하세요
        </p>
        <div className="mt-5 flex h-14 items-center gap-2 rounded-xl border border-gray-200 px-4 focus-within:border-primary-500">
          <input
            className="flex-1 text-h3 text-gray-500 outline-none placeholder:text-gray-200"
            type="text"
            inputMode="numeric"
            pattern="[0-9]*"
            placeholder="목표 금액 입력"
            value={newTargetPrice}
            onChange={(e) => setNewTargetPrice(e.target.value.replace(/[^0-9]/g, ""))}
          />
          <span className="text-body2 text-gray-300">원</span>
        </div>
        <button
          className="mt-4 h-14 w-full rounded-xl bg-primary-500 text-body1 font-semibold text-white disabled:opacity-50"
          disabled={saving || !newTargetPrice}
          onClick={handleSaveTargetPrice}
          type="button"
        >
          {saving ? "저장 중..." : "저장하기"}
        </button>
      </div>
    </AppLayout>
  );
}

function PriceChart({
  history,
  targetPrice,
}: {
  history: { date: string; price: number }[];
  targetPrice?: number;
}) {
  if (!history.length) {
    return (
      <div className="mt-3 flex h-[160px] items-center justify-center rounded-xl border border-gray-200 bg-white">
        <p className="text-caption text-gray-300">가격 데이터가 없어요</p>
      </div>
    );
  }

  const W = 300;
  const H = 160;
  const PAD = { top: 16, right: 24, bottom: 24, left: 40 };
  const innerW = W - PAD.left - PAD.right;
  const innerH = H - PAD.top - PAD.bottom;

  const prices = history.map((h) => h.price);
  const allVals = targetPrice ? [...prices, targetPrice] : prices;
  const minP = Math.min(...allVals) * 0.96;
  const maxP = Math.max(...allVals) * 1.04;

  const toX = (i: number) =>
    PAD.left + (i / Math.max(history.length - 1, 1)) * innerW;
  const toY = (p: number) =>
    PAD.top + (1 - (p - minP) / (maxP - minP)) * innerH;

  const linePath = history
    .map((h, i) => `${i === 0 ? "M" : "L"} ${toX(i).toFixed(1)} ${toY(h.price).toFixed(1)}`)
    .join(" ");

  const areaPath =
    linePath +
    ` L ${toX(history.length - 1).toFixed(1)} ${(PAD.top + innerH).toFixed(1)}` +
    ` L ${toX(0).toFixed(1)} ${(PAD.top + innerH).toFixed(1)} Z`;

  const targetY = targetPrice != null ? toY(targetPrice) : null;
  const last = history[history.length - 1];
  const midIdx = Math.floor(history.length / 2);
  const xLabels = [0, midIdx, history.length - 1].filter(
    (v, i, arr) => arr.indexOf(v) === i,
  );
  const yLabels = [maxP, (maxP + minP) / 2, minP];

  return (
    <div className="mt-3 rounded-xl border border-gray-200 bg-white p-3">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full">
        {/* y축 라벨 */}
        {yLabels.map((val, i) => (
          <text
            key={i}
            x={PAD.left - 4}
            y={toY(val) + 4}
            fill="#CBD0D6"
            fontSize="9"
            textAnchor="end"
          >
            {(val / 1000).toFixed(0)}k
          </text>
        ))}

        {/* 그리드 */}
        {yLabels.map((val, i) => (
          <line
            key={i}
            x1={PAD.left}
            x2={W - PAD.right}
            y1={toY(val)}
            y2={toY(val)}
            stroke="#F3F4F6"
          />
        ))}

        {/* 목표가 점선 */}
        {targetY != null && (
          <>
            <line
              x1={PAD.left}
              x2={W - PAD.right}
              y1={targetY}
              y2={targetY}
              stroke="#5B8FD9"
              strokeDasharray="4 3"
              strokeWidth="1.5"
            />
            <text x={W - PAD.right + 2} y={targetY + 4} fill="#5B8FD9" fontSize="8">
              목표
            </text>
          </>
        )}

        {/* 면적 채우기 */}
        <path d={areaPath} fill="#DBE6F8" opacity="0.35" />

        {/* 라인 */}
        <path
          d={linePath}
          fill="none"
          stroke="#5B8FD9"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />

        {/* 마지막 점 + 말풍선 */}
        <circle cx={toX(history.length - 1)} cy={toY(last.price)} r="3.5" fill="#5B8FD9" />

        {/* x축 날짜 */}
        {xLabels.map((idx) => (
          <text
            key={idx}
            x={toX(idx)}
            y={H - 4}
            fill="#9EA5AE"
            fontSize="8"
            textAnchor="middle"
          >
            {history[idx].date.substring(5)}
          </text>
        ))}
      </svg>
    </div>
  );
}
