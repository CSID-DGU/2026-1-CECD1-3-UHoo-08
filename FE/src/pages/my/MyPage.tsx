import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Droplets, Heart, Settings, Bell } from "lucide-react";
import type { LucideIcon } from "lucide-react";
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
import { WishlistButton } from "../../components/common/WishlistButton";
import AppLayout from "../../layouts/AppLayout";

const MENU_ITEMS: { title: string; desc: string; path: string; Icon: LucideIcon }[] = [
  { title: "내 피부 정보", desc: "피부 타입, 고민 등 수정", path: "/my/skin", Icon: Droplets },
  { title: "가격 추적", desc: "모니터링 중인 상품", path: "/favorites", Icon: Heart },
  { title: "앱 설정 및 고객센터", desc: "알림, 계정, 도움말", path: "/my/settings", Icon: Settings },
];

const glass = {
  background: "rgba(255,255,255,0.68)",
  backdropFilter: "blur(14px)",
  WebkitBackdropFilter: "blur(14px)",
  border: "1px solid rgba(255,255,255,0.9)",
  boxShadow: "0 4px 24px rgba(91,143,217,0.09)",
};

const menuGlass = {
  background: "linear-gradient(135deg, rgba(157,191,238,0.55), rgba(197,221,245,0.45))",
  backdropFilter: "blur(12px)",
  WebkitBackdropFilter: "blur(12px)",
  border: "1px solid rgba(255,255,255,0.85)",
  boxShadow: "0 4px 20px rgba(91,143,217,0.1), 0 1px 0 rgba(255,255,255,0.8) inset",
};

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
      <div
        className="min-h-screen"
        style={{ background: "linear-gradient(160deg, #eef4fc 0%, #f8fbff 55%, #e8f1fb 100%)" }}
      >
        <section className="px-5 pb-32 pt-6">
          {/* 헤더 */}
          <header className="flex items-center justify-between">
            <h1 className="font-bold text-h2 text-gray-500">My</h1>
            <div className="flex items-center gap-2">
              <WishlistButton
                style={{
                  ...glass,
                  background: "rgba(255,255,255,0.6)",
                }}
                iconColor="#4778C8"
              />
              <button
                className="relative flex h-10 w-10 items-center justify-center rounded-full"
                style={{ ...glass, background: "rgba(255,255,255,0.6)" }}
                onClick={() => navigate("/notifications")}
                type="button"
                aria-label="알림"
              >
                <Bell className="h-5 w-5 text-primary-600" strokeWidth={1.8} />
                {hasUnread && (
                  <span className="absolute right-0.5 top-0.5 h-2.5 w-2.5 rounded-full bg-primary-500" />
                )}
              </button>
            </div>
          </header>

          {/* 프로필 카드 */}
          <section
            className="mt-5 overflow-hidden rounded-2xl p-5 text-white"
            style={{
              background: "linear-gradient(135deg, #7AAEE4, #B8D8F5)",
              border: "1px solid rgba(255,255,255,0.5)",
              boxShadow: "0 8px 32px rgba(91,143,217,0.2), 0 1px 0 rgba(255,255,255,0.6) inset",
            }}
          >
            {/* shine line */}
            <div
              className="pointer-events-none absolute inset-x-0 top-0 h-px"
              style={{ background: "linear-gradient(90deg, transparent, rgba(255,255,255,0.7), transparent)" }}
            />
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-4">
                <div
                  className="grid h-16 w-16 place-items-center rounded-full"
                  style={{ background: "rgba(255,255,255,0.25)", border: "2px solid rgba(255,255,255,0.6)" }}
                >
                  {getProfileImageUrl(user?.profileImageUrl ?? null) ? (
                    <img
                      src={getProfileImageUrl(user!.profileImageUrl)!}
                      alt="프로필"
                      className="h-16 w-16 rounded-full object-cover"
                    />
                  ) : (
                    <span className="text-h3 font-semibold text-white">{initial}</span>
                  )}
                </div>
                <div>
                  <h2 className="text-h4">{user?.name ?? "이름 없음"}</h2>
                  {skinSummary && (
                    <p className="mt-1 text-caption" style={{ color: "rgba(255,255,255,0.8)" }}>
                      {skinSummary}
                    </p>
                  )}
                  <button
                    className="mt-3 rounded-full px-5 py-1 text-caption"
                    style={{ background: "rgba(255,255,255,0.22)", border: "1px solid rgba(255,255,255,0.4)" }}
                    onClick={() => navigate("/my/profile")}
                    type="button"
                  >
                    프로필 수정
                  </button>
                </div>
              </div>
              {skin?.skinType && (
                <span
                  className="rounded-full px-3 py-1 text-caption"
                  style={{ background: "rgba(255,255,255,0.22)", border: "1px solid rgba(255,255,255,0.4)" }}
                >
                  업데이트됨
                </span>
              )}
            </div>
          </section>

          {/* 통계 카드 */}
          <div className="mt-4 grid grid-cols-3 gap-3">
            {(
              [
                { value: String(stats?.wishlistCount ?? 0), label: "관심 제품", path: "/wishlist" },
                { value: String(stats?.trackingCount ?? 0), label: "가격 추적", path: "/favorites" },
                { value: String(stats?.registeredCount ?? 0), label: "구매 제품", path: null },
              ] as { value: string; label: string; path: string | null }[]
            ).map(({ value, label, path }, index) => {
              const content = (
                <>
                  <p className={`text-h2 ${index === 2 ? "text-primary-500" : "text-gray-500"}`}>{value}</p>
                  <p className={`mt-1 text-caption ${index === 2 ? "text-primary-500" : "text-gray-400"}`}>{label}</p>
                </>
              );
              return path ? (
                <button
                  key={label}
                  className="rounded-2xl p-4 text-center"
                  style={glass}
                  onClick={() => navigate(path)}
                  type="button"
                >
                  {content}
                </button>
              ) : (
                <div key={label} className="rounded-2xl p-4 text-center" style={glass}>
                  {content}
                </div>
              );
            })}
          </div>

          {/* 메뉴 */}
          <div className="mt-4 grid gap-3">
            {MENU_ITEMS.map((item) => (
              <button
                key={item.title}
                className="flex items-center gap-4 rounded-2xl p-4 text-left"
                style={menuGlass}
                onClick={() => navigate(item.path)}
                type="button"
              >
                <div
                  className="grid h-12 w-12 shrink-0 place-items-center rounded-full"
                  style={{ background: "rgba(255,255,255,0.6)", boxShadow: "0 2px 8px rgba(91,143,217,0.15)" }}
                >
                  <item.Icon className="h-6 w-6 text-primary-600" strokeWidth={1.8} />
                </div>
                <div className="flex-1">
                  <p className="text-body2 font-medium text-gray-500">{item.title}</p>
                  <p className="mt-0.5 text-caption text-gray-300">{item.desc}</p>
                </div>
                <span
                  className="flex h-7 w-7 items-center justify-center rounded-full text-body2 text-primary-500"
                  style={{ background: "rgba(255,255,255,0.6)" }}
                >
                  ›
                </span>
              </button>
            ))}
          </div>

          <button
            className="mt-6 w-full py-4 text-body2 text-gray-300"
            onClick={handleLogout}
            type="button"
          >
            로그아웃
          </button>

          <BottomNav />
        </section>
      </div>
    </AppLayout>
  );
}
