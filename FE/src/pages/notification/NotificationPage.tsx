import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  getNotifications,
  markAllAsRead,
  markAsRead,
  type NotificationItem,
} from "../../api/notificationApi";
import { PageHeader } from "../../components/common/PageHeader";
import AppLayout from "../../layouts/AppLayout";

const TYPE_LABEL: Record<string, string> = {
  PRICE_ALERT: "가격 추적 알림",
  AI_RECOMMENDATION: "AI 추천",
  PRICE_CHANGE: "가격 변동",
  WEEKLY_REPORT: "주간 가격 리포트",
  REVIEW_REQUEST: "리뷰 요청",
};

function formatTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const min = Math.floor(diff / 60000);
  if (min < 1) return "방금 전";
  if (min < 60) return `${min}분 전`;
  const hour = Math.floor(min / 60);
  if (hour < 24) return `${hour}시간 전`;
  const DAYS = ["일", "월", "화", "수", "목", "금", "토"];
  const day = Math.floor(hour / 24);
  if (day === 1) return "어제";
  if (day < 7) return `${DAYS[new Date(iso).getDay()]}요일`;
  return `${day}일 전`;
}

function isToday(iso: string): boolean {
  const d = new Date(iso);
  const now = new Date();
  return (
    d.getFullYear() === now.getFullYear() &&
    d.getMonth() === now.getMonth() &&
    d.getDate() === now.getDate()
  );
}

function isThisWeek(iso: string): boolean {
  return Date.now() - new Date(iso).getTime() < 7 * 24 * 60 * 60 * 1000;
}

export function NotificationPage() {
  const navigate = useNavigate();
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getNotifications()
      .then((res) => setNotifications(res.data.notifications))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  async function handleMarkAllRead() {
    await markAllAsRead().catch(() => {});
    setNotifications((prev) => prev.map((n) => ({ ...n, isRead: true })));
  }

  async function handleMarkRead(id: string) {
    if (notifications.find((n) => n.id === id)?.isRead) return;
    await markAsRead(id).catch(() => {});
    setNotifications((prev) =>
      prev.map((n) => (n.id === id ? { ...n, isRead: true } : n)),
    );
  }

  const todayItems = notifications.filter((n) => isToday(n.createdAt));
  const weekItems = notifications.filter(
    (n) => !isToday(n.createdAt) && isThisWeek(n.createdAt),
  );
  const olderItems = notifications.filter((n) => !isThisWeek(n.createdAt));

  return (
    <AppLayout>
      <section className="min-h-screen px-6 pb-20 pt-10">
        <PageHeader
          title="알림"
          onBack={() => navigate(-1)}
          rightSlot={
            <button
              className="text-body2 text-gray-300"
              type="button"
              onClick={handleMarkAllRead}
            >
              모두 읽음
            </button>
          }
        />

        {loading ? (
          <p className="mt-10 text-center text-body2 text-gray-300">불러오는 중...</p>
        ) : notifications.length === 0 ? (
          <p className="mt-10 text-center text-body2 text-gray-300">알림이 없습니다.</p>
        ) : (
          <>
            {todayItems.length > 0 && (
              <>
                <h2 className="mt-7 text-body2 text-gray-500">오늘</h2>
                <div className="mt-2 grid gap-3">
                  {todayItems.map((item) => (
                    <NotificationCard key={item.id} item={item} onRead={handleMarkRead} />
                  ))}
                </div>
              </>
            )}

            {weekItems.length > 0 && (
              <>
                <h2 className="mt-4 text-body2 text-gray-500">이번 주</h2>
                <div className="mt-2 grid gap-3">
                  {weekItems.map((item) => (
                    <NotificationCard key={item.id} item={item} onRead={handleMarkRead} />
                  ))}
                </div>
              </>
            )}

            {olderItems.length > 0 ? (
              <>
                <h2 className="mt-4 text-body2 text-gray-500">더 이전</h2>
                <div className="mt-2 grid gap-3">
                  {olderItems.map((item) => (
                    <NotificationCard key={item.id} item={item} onRead={handleMarkRead} />
                  ))}
                </div>
              </>
            ) : (
              <button
                className="mt-5 h-[52px] w-full rounded-xl bg-gray-100 text-body2 text-gray-300"
                type="button"
                disabled
              >
                더 이전 알림 없음
              </button>
            )}
          </>
        )}

        <div className="mt-12 text-center">
          <p className="text-caption text-gray-300">알림 설정 변경</p>
          <button
            className="mt-2 text-body2 text-primary-500"
            type="button"
            onClick={() => navigate("/my/settings")}
          >
            MY › 앱 설정 › 알림
          </button>
        </div>
      </section>
    </AppLayout>
  );
}

function NotificationCard({
  item,
  onRead,
}: {
  item: NotificationItem;
  onRead: (id: string) => void;
}) {
  const active = !item.isRead;
  const label = TYPE_LABEL[item.type] ?? "알림";
  const time = formatTime(item.createdAt);

  return (
    <article
      className={`relative cursor-pointer rounded-xl border p-4 ${
        active ? "border-primary-500 bg-primary-50" : "border-gray-200 bg-white"
      }`}
      onClick={() => onRead(item.id)}
    >
      {active && <span className="absolute right-4 top-4 h-3 w-3 rounded-full bg-primary-500" />}
      <div className="flex gap-4">
        <div
          className={`grid h-11 w-11 shrink-0 place-items-center rounded-full ${
            active ? "bg-primary-500 text-white" : "bg-gray-100 text-gray-300"
          }`}
        >
          {active ? "↓" : label === "AI 추천" ? "✦" : "%"}
        </div>
        <div className="min-w-0 flex-1">
          <p className={`text-caption ${active ? "text-primary-500" : "text-gray-300"}`}>
            {label}
          </p>
          <h3 className="mt-1 truncate text-body2 text-gray-500">{item.title}</h3>
          <p className="mt-1 truncate text-caption text-gray-400">{item.body}</p>
          {active && item.actionUrl && (
            <button
              className="mt-2 rounded-md bg-primary-500 px-4 py-1 text-caption text-white"
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                window.open(item.actionUrl!, "_blank");
              }}
            >
              지금 구매
            </button>
          )}
        </div>
        <span className="self-end text-caption text-gray-300">{time}</span>
      </div>
    </article>
  );
}
