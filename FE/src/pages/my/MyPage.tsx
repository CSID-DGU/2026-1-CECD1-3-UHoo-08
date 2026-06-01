import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  type UserMeResponse,
  CONCERN_LABEL,
  PERSONAL_COLOR_LABEL,
  SKIN_TYPE_LABEL,
  getMyProfile,
  getProfileImageUrl,
} from "../../api/userApi";
import { getUnreadCount } from "../../api/notificationApi";
import { clearTokens } from "../../lib/auth";
import { BottomNav } from "../../components/common/BottomNav";
import AppLayout from "../../layouts/AppLayout";

const MENU_ITEMS = [
  { title: "내 피부 정보", path: "/my/skin", emoji: "🌿" },
  { title: "관심 제품", path: "/favorites", emoji: "♡" },
  { title: "앱 설정 및 고객센터", path: "/my/settings", emoji: "⚙️" },
];

export function MyPage() {
  const navigate = useNavigate();
  const [user, setUser] = useState<UserMeResponse | null>(null);
  const [hasUnread, setHasUnread] = useState(false);

  useEffect(() => {
    getMyProfile()
      .then((res) => setUser(res.data))
      .catch(() => {});
    getUnreadCount()
      .then((count) => setHasUnread(count > 0))
      .catch(() => {});
  }, []);

  const skin = user?.skinProfile;
  const skinSummary = [
    skin?.personalColor ? PERSONAL_COLOR_LABEL[skin.personalColor]?.split("\n")[0] ?? skin.personalColor : null,
    skin?.skinType ? SKIN_TYPE_LABEL[skin.skinType] ?? skin.skinType : null,
    ...(skin?.skinConcerns?.map((c) => CONCERN_LABEL[c] ?? c) ?? []),
  ]
    .filter(Boolean)
    .join(" · ");

  const initial = (user?.name ?? "?")[0];
  const stats = user?.stats;

  function handleLogout() {
    clearTokens();
    navigate("/", { replace: true });
  }

  return (
    <AppLayout>
      <section className="min-h-screen px-6 pb-28 pt-12">
        {/* 헤더 */}
        <header className="flex items-center justify-between">
          <h1 className="text-h3 text-gray-500">My</h1>
          <button
            className="relative grid h-10 w-10 place-items-center rounded-full bg-gray-100"
            onClick={() => navigate("/notifications")}
            type="button"
            aria-label="알림"
          >
            <span className="h-3 w-3 rounded-sm bg-gray-200" />
            {hasUnread && (
              <span className="absolute right-0.5 top-0.5 h-2.5 w-2.5 rounded-full bg-primary-500" />
            )}
          </button>
        </header>

        {/* 프로필 카드 */}
        <section className="mt-4 rounded-2xl bg-gray-500 p-5 text-white">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-4">
              <div className="grid h-16 w-16 place-items-center rounded-full bg-primary-700">
                {getProfileImageUrl(user?.profileImageUrl ?? null) ? (
                  <img
                    src={getProfileImageUrl(user!.profileImageUrl)!}
                    alt="프로필"
                    className="h-16 w-16 rounded-full object-cover"
                  />
                ) : (
                  <div className="grid h-11 w-11 place-items-center rounded-full bg-primary-500 text-h4">
                    {initial}
                  </div>
                )}
              </div>
              <div>
                <h2 className="text-h4">{user?.name ?? "이름 없음"}</h2>
                {skinSummary && (
                  <p className="mt-1 text-caption text-primary-300">{skinSummary}</p>
                )}
                <button
                  className="mt-3 rounded-full bg-white/20 px-5 py-1 text-caption"
                  onClick={() => navigate("/my/profile")}
                  type="button"
                >
                  프로필 수정
                </button>
              </div>
            </div>
            {skin?.skinType && (
              <span className="rounded-full bg-primary-500 px-3 py-1 text-caption">업데이트됨</span>
            )}
          </div>
        </section>

        {/* 통계 */}
        <div className="mt-4 grid grid-cols-3 gap-3">
          {[
            [String(stats?.wishlistCount ?? 0), "관심 제품"],
            [String(stats?.trackingCount ?? 0), "가격 추적"],
            [String(stats?.registeredCount ?? 0), "등록 제품"],
          ].map(([value, label], index) => (
            <div
              className={`rounded-xl border p-4 text-center ${
                index === 2 ? "border-primary-100 bg-primary-50" : "border-gray-200 bg-white"
              }`}
              key={label}
            >
              <p className={`text-h2 ${index === 2 ? "text-primary-500" : "text-gray-500"}`}>
                {value}
              </p>
              <p className={`mt-1 text-caption ${index === 2 ? "text-primary-500" : "text-gray-300"}`}>
                {label}
              </p>
            </div>
          ))}
        </div>

        {/* 메뉴 */}
        <div className="mt-4 grid gap-3">
          {MENU_ITEMS.map((item) => (
            <button
              className="flex items-center gap-4 rounded-xl border border-gray-200 bg-white p-4 text-left"
              key={item.title}
              onClick={() => navigate(item.path)}
              type="button"
            >
              <div className="grid h-11 w-11 shrink-0 place-items-center rounded-full bg-primary-50 text-lg">
                {item.emoji}
              </div>
              <div className="flex-1">
                <p className="text-body2 text-gray-500">{item.title}</p>
              </div>
              <span className="grid h-8 w-8 place-items-center rounded-lg bg-gray-100 text-gray-300">
                ›
              </span>
            </button>
          ))}
        </div>

        <button
          className="mt-5 w-full py-4 text-body2 text-gray-300"
          onClick={handleLogout}
          type="button"
        >
          로그아웃
        </button>

        <BottomNav />
      </section>
    </AppLayout>
  );
}
