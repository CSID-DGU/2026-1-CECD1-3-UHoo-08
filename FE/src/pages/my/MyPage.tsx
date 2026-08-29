import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Bell, Droplets, Heart, PackagePlus, Settings } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import {
  type UserMeResponse,
  CONCERN_LABEL,
  PERSONAL_COLOR_LABEL,
  SKIN_TYPE_LABEL,
  getMyProfile,
  getProfileImageUrl,
} from "../../api/userApi";
import {
  type ProductSearchItem,
  getRecentlyViewed,
} from "../../api/productApi";
import { getUnreadCount } from "../../api/notificationApi";
import { clearTokens } from "../../lib/auth";
import { BottomNav } from "../../components/common/BottomNav";
import { WishlistButton } from "../../components/common/WishlistButton";
import AppLayout from "../../layouts/AppLayout";

const MENU_ITEMS: {
  title: string;
  desc: string;
  path: string;
  Icon: LucideIcon;
}[] = [
  {
    title: "내 피부 정보",
    desc: "피부 타입, 고민 등 수정",
    path: "/my/skin",
    Icon: Droplets,
  },
  {
    title: "가격 추적",
    desc: "모니터링 중인 상품",
    path: "/favorites",
    Icon: Heart,
  },
  {
    title: "보유 화장품",
    desc: "등록·수정, 개봉일과 보관 위치 관리",
    path: "/my/products",
    Icon: PackagePlus,
  },
  {
    title: "앱 설정 및 고객센터",
    desc: "알림, 계정, 도움말",
    path: "/my/settings",
    Icon: Settings,
  },
];

export function MyPage() {
  const navigate = useNavigate();
  const [user, setUser] = useState<UserMeResponse | null>(null);
  const [hasUnread, setHasUnread] = useState(false);
  const [recentlyViewed, setRecentlyViewed] = useState<ProductSearchItem[]>([]);

  useEffect(() => {
    getMyProfile()
      .then((res) => setUser(res.data))
      .catch(() => {});
    getUnreadCount()
      .then((count) => setHasUnread(count > 0))
      .catch(() => {});
    getRecentlyViewed(10)
      .then((res) => setRecentlyViewed(res.data.products))
      .catch(() => {});
  }, []);

  const skin = user?.skinProfile;
  const skinSummary = [
    skin?.personalColor
      ? (PERSONAL_COLOR_LABEL[skin.personalColor]?.split("\n")[0] ??
        skin.personalColor)
      : null,
    skin?.skinType ? (SKIN_TYPE_LABEL[skin.skinType] ?? skin.skinType) : null,
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
      <div className="flex h-screen flex-col overflow-hidden bg-white">
        <div className="flex-1 overflow-y-auto scrollbar-none">
          <section className="px-5 pb-8 pt-6">
            {/* 헤더 */}
            <header className="flex items-center justify-between">
              <h1 className="font-bold text-h2 text-gray-500">My</h1>
              <div className="flex items-center gap-2">
                <WishlistButton
                  style={{
                    background: "#DBE6F8",
                  }}
                />
                <button
                  className="relative flex h-10 w-10 items-center justify-center rounded-full bg-primary-100"
                  onClick={() => navigate("/notifications")}
                  type="button"
                  aria-label="알림"
                >
                  <Bell className="h-5 w-5 text-white" strokeWidth={1.8} />
                  {hasUnread && (
                    <span className="absolute right-0.5 top-0.5 h-2.5 w-2.5 rounded-full bg-primary-500" />
                  )}
                </button>
              </div>
            </header>

            {/* 프로필 카드 */}
            <section className="relative mt-5 overflow-hidden rounded-2xl bg-primary-300 p-5 text-white">
              {/* shine line */}
              <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-primary-300" />
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-4">
                  <div className="grid h-25 w-25 rounded-full">
                    {getProfileImageUrl(user?.profileImageUrl ?? null) ? (
                      <img
                        src={getProfileImageUrl(user!.profileImageUrl)!}
                        alt="프로필"
                        className="h-25 w-25 rounded-full object-cover"
                      />
                    ) : (
                      <span className="text-h3 text-white">{initial}</span>
                    )}
                  </div>
                  <div>
                    <h2 className="text-h4">{user?.name ?? "이름 없음"}</h2>
                    {skinSummary && (
                      <p className="mt-1 text-caption text-white whitespace-nowrap">
                        {skinSummary}
                      </p>
                    )}
                    <button
                      className="mt-3 rounded-full border border-white px-3 py-1 text-caption"
                      onClick={() => navigate("/my/profile")}
                      type="button"
                    >
                      프로필 수정
                    </button>
                  </div>
                </div>
                {skin?.skinType && (
                  <span className="rounded-full border border-white px-3 py-1 text-caption whitespace-nowrap">
                    업데이트됨
                  </span>
                )}
              </div>
            </section>

            {/* 통계 카드 */}
            <div className="mt-4 grid grid-cols-3 gap-3">
              {(
                [
                  {
                    value: String(stats?.wishlistCount ?? 0),
                    label: "관심 제품",
                    path: "/wishlist",
                  },
                  {
                    value: String(stats?.trackingCount ?? 0),
                    label: "가격 추적",
                    path: "/favorites",
                  },
                  {
                    value: String(stats?.registeredCount ?? 0),
                    label: "구매 제품",
                    path: null,
                  },
                ] as { value: string; label: string; path: string | null }[]
              ).map(({ value, label, path }, index) => {
                const content = (
                  <>
                    <p
                      className={`text-h2 ${index === 2 ? "text-primary-500" : "text-gray-500"}`}
                    >
                      {value}
                    </p>
                    <p
                      className={`mt-1 text-caption ${index === 2 ? "text-primary-500" : "text-gray-400"}`}
                    >
                      {label}
                    </p>
                  </>
                );
                return path ? (
                  <button
                    key={label}
                    className={`rounded-2xl p-4 text-center bg-primary-100`}
                    onClick={() => navigate(path)}
                    type="button"
                  >
                    {content}
                  </button>
                ) : (
                  <div
                    key={label}
                    className={`rounded-2xl p-4 text-center bg-primary-100`}
                  >
                    {content}
                  </div>
                );
              })}
            </div>

            {/* 최근 본 상품 */}
            {recentlyViewed.length > 0 && (
              <section className="mt-4">
                <h2 className="mb-3 text-body2 font-medium text-gray-500">
                  최근 본 상품
                </h2>
                <div className="flex gap-3 overflow-x-auto scrollbar-none pb-1">
                  {recentlyViewed.map((product) => (
                    <button
                      key={String(product.id)}
                      className={`min-w-[88px] rounded-xl p-2 text-center bg-primary-100`}
                      onClick={() => navigate(`/product/${product.id}`)}
                      type="button"
                    >
                      <div className="h-[64px] w-[64px] overflow-hidden rounded-lg bg-primary-50">
                        {product.imageUrl && (
                          <img
                            src={product.imageUrl}
                            alt={product.name}
                            className="h-full w-full object-cover"
                          />
                        )}
                      </div>
                      <p className="mt-2 w-[64px] truncate text-caption text-gray-500">
                        {product.name}
                      </p>
                      <p className="w-[64px] truncate text-[10px] text-gray-300">
                        {product.brand}
                      </p>
                    </button>
                  ))}
                </div>
              </section>
            )}

            {/* 메뉴 */}
            <div className="mt-4 grid gap-3">
              {MENU_ITEMS.map((item) => (
                <button
                  key={item.title}
                  className={`flex items-center gap-4 rounded-2xl p-4 text-left bg-primary-100`}
                  onClick={() => navigate(item.path)}
                  type="button"
                >
                  <div className="grid h-12 w-12 shrink-0 place-items-center rounded-full bg-white/60">
                    <item.Icon
                      className="h-6 w-6 text-primary-600"
                      strokeWidth={1.8}
                    />
                  </div>
                  <div className="flex-1">
                    <p className="text-body2 font-medium text-gray-500">
                      {item.title}
                    </p>
                    <p className="mt-0.5 text-caption text-gray-300">
                      {item.desc}
                    </p>
                  </div>
                  <span className="flex h-7 w-7 items-center justify-center rounded-full bg-white/60 text-body2 text-primary-500">
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
          </section>
        </div>
      </div>
      <BottomNav />
    </AppLayout>
  );
}
