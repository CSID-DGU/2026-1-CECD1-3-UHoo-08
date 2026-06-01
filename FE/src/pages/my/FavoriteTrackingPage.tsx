import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  type AchievedItem,
  type AlertSettings,
  type TrackingItem,
  deleteTracking,
  getTrackings,
  updateAlertSettings,
  updateTracking,
} from "../../api/priceTrackingApi";
import { BottomNav } from "../../components/common/BottomNav";
import { PageHeader } from "../../components/common/PageHeader";
import { Toggle } from "../../components/common/Toggle";
import AppLayout from "../../layouts/AppLayout";

export function FavoriteTrackingPage() {
  const navigate = useNavigate();
  const [achieved, setAchieved] = useState<AchievedItem[]>([]);
  const [tracking, setTracking] = useState<TrackingItem[]>([]);
  const [summary, setSummary] = useState({ totalTracking: 0, monthlySavings: 0 });
  const [alertSettings, setAlertSettings] = useState<AlertSettings>({
    targetPriceAlert: true,
    weeklyReport: false,
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getTrackings()
      .then((res) => {
        const d = res.data;
        setAchieved(d?.achieved ?? []);
        setTracking(d?.tracking ?? []);
        setSummary(d?.summary ?? { totalTracking: 0, monthlySavings: 0 });
        if (d?.alertSettings) setAlertSettings(d.alertSettings);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  async function handleDeleteAchieved(trackingId: string) {
    await deleteTracking(trackingId).catch(() => {});
    setAchieved((prev) => prev.filter((t) => t.trackingId !== trackingId));
    setSummary((s) => ({ ...s, totalTracking: Math.max(0, s.totalTracking - 1) }));
  }

  async function handleDeleteTracking(trackingId: string) {
    await deleteTracking(trackingId).catch(() => {});
    setTracking((prev) => prev.filter((t) => t.trackingId !== trackingId));
    setSummary((s) => ({ ...s, totalTracking: Math.max(0, s.totalTracking - 1) }));
  }

  async function handleToggleAlert(trackingId: string, current: boolean) {
    await updateTracking(trackingId, { alertEnabled: !current }).catch(() => {});
    setTracking((prev) =>
      prev.map((t) =>
        t.trackingId === trackingId ? { ...t, _alertEnabled: !current } : t,
      ),
    );
  }

  async function handleTargetPriceAlert() {
    const next = !alertSettings.targetPriceAlert;
    setAlertSettings((s) => ({ ...s, targetPriceAlert: next }));
    await updateAlertSettings(next, alertSettings.weeklyReport).catch(() => {});
  }

  async function handleWeeklyReport() {
    const next = !alertSettings.weeklyReport;
    setAlertSettings((s) => ({ ...s, weeklyReport: next }));
    await updateAlertSettings(alertSettings.targetPriceAlert, next).catch(() => {});
  }

  const total = summary.totalTracking;

  return (
    <AppLayout>
      <section className="min-h-screen px-6 pb-28 pt-10">
        <PageHeader title="가격 추적" onBack={() => navigate(-1)} />

        {/* 통계 카드 */}
        <section className="mt-5 rounded-2xl bg-gray-500 p-6 text-white">
          <div className="grid grid-cols-2 divide-x divide-gray-400/40">
            <div>
              <p className="text-caption">추적 중인 제품</p>
              <p className="mt-1 text-[34px] leading-none">
                {total} <span className="text-body1">개</span>
              </p>
            </div>
            <div className="pl-5">
              <p className="text-caption">이번 달 절약</p>
              <p className="mt-1 text-[34px] leading-none">
                {summary.monthlySavings.toLocaleString()} <span className="text-body1">원</span>
              </p>
            </div>
          </div>
        </section>

        {loading ? (
          <p className="mt-10 text-center text-body2 text-gray-300">불러오는 중...</p>
        ) : total === 0 ? (
          <EmptyState onAdd={() => navigate("/price-tracking/add")} />
        ) : (
          <>
            {/* 목표가 달성 */}
            {achieved.length > 0 && (
              <>
                <h2 className="mt-5 text-body1 text-gray-500">지금 살 때예요!</h2>
                <p className="text-caption text-gray-300">설정한 목표가에 도달한 제품이에요</p>
                <div className="mt-3 grid gap-3">
                  {achieved.map((item) => (
                    <AchievedCard
                      key={item.trackingId}
                      item={item}
                      onDelete={handleDeleteAchieved}
                      onNavigate={() => navigate(`/product/${item.product.id}`)}
                    />
                  ))}
                </div>
              </>
            )}

            {/* 추적 중 */}
            {tracking.length > 0 && (
              <>
                <h2 className="mt-5 text-body1 text-gray-500">추적 중</h2>
                <div className="mt-3 grid gap-3">
                  {tracking.map((item) => (
                    <TrackingCard
                      key={item.trackingId}
                      item={item}
                      onDelete={handleDeleteTracking}
                      onNavigate={() => navigate(`/price-tracking/${item.product.id}`)}
                    />
                  ))}
                </div>
              </>
            )}

            {/* 제품 추가 */}
            <button
              className="mt-5 h-[58px] w-full rounded-xl border border-dashed border-primary-100 bg-primary-50 text-body1 text-primary-500"
              onClick={() => navigate("/price-tracking/add")}
              type="button"
            >
              + 제품 추가하기
            </button>

            {/* 전역 알림 설정 */}
            <section className="mt-5 rounded-xl border border-gray-200 bg-white">
              <h2 className="px-4 pt-4 text-body1 text-gray-500">알림 설정</h2>
              <AlertRow
                label="목표가 도달 시 알림"
                desc="설정한 금액 이하가 되면 푸시 알림을 보내요"
                checked={alertSettings.targetPriceAlert}
                onToggle={handleTargetPriceAlert}
              />
              <AlertRow
                label="주간 가격 리포트"
                desc="매주 월요일 가격 변동 요약을 보내드려요"
                checked={alertSettings.weeklyReport}
                onToggle={handleWeeklyReport}
              />
            </section>
          </>
        )}

        <BottomNav />
      </section>
    </AppLayout>
  );
}

function EmptyState({ onAdd }: { onAdd: () => void }) {
  return (
    <div className="mt-16 flex flex-col items-center gap-4 text-center">
      <div className="grid h-20 w-20 place-items-center rounded-full bg-primary-50 text-4xl">
        📊
      </div>
      <div>
        <p className="text-body1 text-gray-500">아직 추적 중인 제품이 없어요</p>
        <p className="mt-1 text-body2 text-gray-300">지금 바로 가격 추적을 시작해보세요</p>
      </div>
      <button
        className="mt-2 h-12 rounded-xl bg-primary-500 px-8 text-body2 text-white"
        onClick={onAdd}
        type="button"
      >
        가격 추적 시작하기
      </button>
    </div>
  );
}

function AchievedCard({
  item,
  onDelete,
  onNavigate,
}: {
  item: AchievedItem;
  onDelete: (id: string) => void;
  onNavigate: () => void;
}) {
  return (
    <article className="flex items-center gap-3 rounded-xl border border-primary-500 bg-white p-3">
      <div className="h-[60px] w-[60px] shrink-0 rounded-xl bg-primary-50" />
      <div className="min-w-0 flex-1">
        <p className="truncate text-body2 text-gray-500">{item.product.name}</p>
        <p className="text-caption text-gray-300">목표가 {item.targetPrice.toLocaleString()}원 달성!</p>
        {item.currentLowestPrice != null && (
          <p className="mt-1 text-body2 text-primary-500">
            현재 {item.currentLowestPrice.toLocaleString()}원
          </p>
        )}
      </div>
      <div className="flex flex-col gap-2">
        <button
          className="rounded-xl bg-primary-500 px-4 py-2 text-caption text-white"
          onClick={onNavigate}
          type="button"
        >
          지금 구매
        </button>
        <button
          className="rounded-xl bg-gray-100 px-4 py-2 text-caption text-gray-300"
          onClick={() => onDelete(item.trackingId)}
          type="button"
        >
          삭제
        </button>
      </div>
    </article>
  );
}

function TrackingCard({
  item,
  onDelete,
  onNavigate,
}: {
  item: TrackingItem;
  onDelete: (id: string) => void;
  onNavigate: () => void;
}) {
  return (
    <article className="rounded-xl border border-gray-200 bg-white p-4">
      <div className="flex items-start gap-4">
        <button
          className="h-[60px] w-[60px] shrink-0 rounded-xl bg-primary-50"
          onClick={onNavigate}
          type="button"
        />
        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-2">
            <button
              className="block truncate text-left text-body2 text-gray-500"
              onClick={onNavigate}
              type="button"
            >
              {item.product.name}
            </button>
            <button
              className="shrink-0 text-gray-200"
              onClick={() => onDelete(item.trackingId)}
              type="button"
              aria-label="삭제"
            >
              ✕
            </button>
          </div>
          <p className="text-caption text-gray-300">{item.product.brand}</p>
          <div className="mt-3 grid grid-cols-2 gap-3">
            <div>
              <p className="text-caption text-gray-300">현재 최저가</p>
              <p className="text-h4 text-gray-500">
                {item.currentLowestPrice != null
                  ? `${item.currentLowestPrice.toLocaleString()}원`
                  : "조회 중"}
              </p>
              {item.historicalLowest != null && (
                <p className="text-caption text-gray-300">
                  역대 최저 {item.historicalLowest.toLocaleString()}원
                </p>
              )}
            </div>
            <div>
              <p className="text-caption text-gray-300">목표가</p>
              <p className="rounded-full bg-primary-100 px-3 py-2 text-center text-body2 text-gray-500">
                {item.targetPrice.toLocaleString()}원
              </p>
            </div>
          </div>
        </div>
      </div>
    </article>
  );
}

function AlertRow({
  label,
  desc,
  checked,
  onToggle,
}: {
  label: string;
  desc: string;
  checked: boolean;
  onToggle: () => void;
}) {
  return (
    <div className="flex items-center gap-3 border-b border-gray-100 p-4 last:border-b-0">
      <div className="flex-1">
        <p className="text-body2 text-gray-500">{label}</p>
        <p className="text-caption text-gray-300">{desc}</p>
      </div>
      <button onClick={onToggle} type="button">
        <Toggle checked={checked} />
      </button>
    </div>
  );
}
