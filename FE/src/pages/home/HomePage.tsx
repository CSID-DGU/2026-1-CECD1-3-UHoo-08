import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { type ProductSearchItem, getRecentlyViewed } from "../../api/productApi";
import { getUnreadCount } from "../../api/notificationApi";
import { getTrackings } from "../../api/priceTrackingApi";
import { TrendingUp } from "lucide-react";
import { BottomNav } from "../../components/common/BottomNav";
import { SearchField } from "../../components/common/SearchField";
import { WishlistButton } from "../../components/common/WishlistButton";
import { type LastSearch, getLastSearch } from "../../lib/localHistory";
import AppLayout from "../../layouts/AppLayout";
import Spline from "@splinetool/react-spline";

export function HomePage() {
  const navigate = useNavigate();
  const [hasUnread, setHasUnread] = useState(false);
  const [lastSearch, setLastSearch] = useState<LastSearch | null>(null);
  const [recentlyViewed, setRecentlyViewed] = useState<ProductSearchItem[]>([]);
  const [trackingCount, setTrackingCount] = useState<number | null>(null);

  useEffect(() => {
    getUnreadCount()
      .then((count) => setHasUnread(count > 0))
      .catch(() => setHasUnread(false));

    setLastSearch(getLastSearch());

    getRecentlyViewed(10)
      .then((res) => setRecentlyViewed(res.data.products))
      .catch(() => setRecentlyViewed([]));

    getTrackings()
      .then((res) => setTrackingCount(res.data?.summary?.totalTracking ?? 0))
      .catch(() => setTrackingCount(0));
  }, []);

  function handleSearch(query: string) {
    if (!query) return;
    navigate("/search", { state: { query } });
  }

  return (
    <AppLayout>
      {/* 전체 뷰포트 고정 레이아웃 */}
      <div className="flex h-screen flex-col overflow-hidden">
        {/* 스크롤 영역 */}
        <div className="flex-1 overflow-y-auto scrollbar-none">
          <div className="pb-44">
            {/* Spline 헤더 */}
            <div style={{ position: "relative", height: 150, overflow: "hidden" }}>
              <Spline
                scene="https://prod.spline.design/10xOe1-aIf1GHnfd/scene.splinecode"
                style={{
                  position: "absolute",
                  top: 0,
                  left: 0,
                  width: "100%",
                  height: "300px",
                  pointerEvents: "none",
                }}
              />
              <div style={{ position: "relative", zIndex: 1, padding: "20px 20px 0" }}>
                <div className="flex items-center justify-between">
                  <h2 className="text-h3" style={{ color: "white", fontWeight: 700 }}>
                    BeautyMatch
                  </h2>
                  <div className="flex items-center gap-2">
                    <WishlistButton style={{ background: "rgba(255,255,255,0.25)", backdropFilter: "blur(8px)" }} />
                    <button
                      className="relative h-11 w-11 rounded-full"
                      style={{ background: "rgba(255,255,255,0.25)", backdropFilter: "blur(8px)" }}
                      onClick={() => navigate("/notifications")}
                      type="button"
                      aria-label="알림"
                    >
                      {hasUnread && (
                        <span className="absolute right-0.5 top-0.5 h-2.5 w-2.5 rounded-full bg-primary-500" />
                      )}
                      <span className="absolute left-1/2 top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-sm bg-white/50" />
                    </button>
                  </div>
                </div>
                <div className="mt-3">
                  <SearchField
                    editable
                    placeholder="여름 가벼운 쿠션 추천해줘"
                    onSubmit={handleSearch}
                  />
                </div>
              </div>
            </div>

            <div className="px-5 pt-4">
              {/* 오늘의 추천 배너 */}
              <section
                className="overflow-hidden rounded-2xl border border-primary-100 text-gray-500"
                style={{ background: "#F0F5FD" }}
              >
                <div className="grid grid-cols-[1fr_46%]">
                  <div className="p-5">
                    <p className="text-caption text-primary-500">오늘의 추천 ✦</p>
                    <h2 className="mt-2 text-h3 text-gray-500">
                      내 피부에 딱 맞는
                      <br />
                      제품을 찾았어요
                    </h2>
                    <button
                      className="mt-5 rounded-full px-7 py-2 text-caption font-semibold text-white"
                      style={{ background: "#5B8FD9" }}
                      onClick={() => navigate("/recommendation/lookup")}
                      type="button"
                    >
                      확인하기 →
                    </button>
                  </div>
                  <div
                    className="relative min-h-[118px] rounded-l-2xl"
                    style={{ background: "linear-gradient(135deg, #DBE6F8, #9DBFEE)" }}
                  >
                    <span className="absolute left-16 top-7 h-16 w-16 rounded-full bg-primary-500/10" />
                    <span className="absolute right-6 top-12 h-12 w-12 rounded-full bg-primary-500/15" />
                    <span className="absolute bottom-7 left-12 h-6 w-6 rounded-full bg-primary-500/20" />
                  </div>
                </div>
              </section>

              {lastSearch && lastSearch.products.length > 0 && (
                <section className="mt-4">
                  <div className="mb-2 flex items-center justify-between">
                    <div>
                      <h2 className="text-body1 text-gray-500">최근 검색 기반 추천</h2>
                      <p className="text-caption text-gray-300">"{lastSearch.query}" 검색 결과</p>
                    </div>
                    <button
                      className="text-body2 text-primary-500"
                      onClick={() => navigate("/search", { state: { query: lastSearch.query } })}
                      type="button"
                    >
                      더보기
                    </button>
                  </div>
                  <div className="flex gap-3 overflow-x-auto pb-1 scrollbar-none">
                    {lastSearch.products.map((product) => (
                      <button
                        className="min-w-[154px] rounded-2xl border border-gray-100 bg-white p-3 text-left"
                        style={{ boxShadow: "0 2px 12px rgba(45,125,210,0.08)" }}
                        key={product.productId}
                        onClick={() => navigate(`/product/${product.productId}`)}
                        type="button"
                      >
                        <div className="h-[94px] overflow-hidden rounded-xl bg-primary-50">
                          {product.imageUrl && (
                            <img src={product.imageUrl} alt={product.name} className="h-full w-full object-cover" />
                          )}
                        </div>
                        <p className="mt-3 truncate text-body2 text-gray-500">{product.name}</p>
                        <div className="mt-2 flex items-center justify-between">
                          <span
                            className="rounded-full px-2 py-0.5 text-caption"
                            style={{ background: "#DBE6F8", color: "#3565B5" }}
                          >
                            {product.matchScore}%
                          </span>
                          {product.originalPrice != null && (
                            <span className="text-caption text-gray-300">
                              {product.originalPrice.toLocaleString()}원
                            </span>
                          )}
                        </div>
                      </button>
                    ))}
                  </div>
                </section>
              )}

              {/* AI 분석 카드 */}
              <section
                className="mt-4 rounded-xl p-4"
                style={{
                  background: "#F0F7FF",
                  border: "1px solid #E8F2FC",
                  borderLeftWidth: 3,
                  borderLeftColor: "#2D7DD2",
                }}
              >
                <p className="text-body2 text-primary-500">✦ AI 분석</p>
                <p className="mt-1 text-caption text-gray-500">
                  가벼운 제형 선호도 + 여름철 지성 고민 기반으로 피지 조절 강화 제품을 우선 추천했어요
                </p>
              </section>

              {recentlyViewed.length > 0 && (
                <section className="mt-4">
                  <h2 className="text-body1 text-gray-500">최근 본 상품</h2>
                  <div className="mt-3 flex gap-3 overflow-x-auto scrollbar-none">
                    {recentlyViewed.map((product) => (
                      <button
                        className="min-w-[96px] rounded-xl border border-gray-100 bg-white p-2 text-center"
                        style={{ boxShadow: "0 2px 8px rgba(45,125,210,0.06)" }}
                        key={String(product.id)}
                        onClick={() => navigate(`/product/${product.id}`)}
                        type="button"
                      >
                        <div className="h-[70px] overflow-hidden rounded-lg bg-gray-100">
                          {product.imageUrl && (
                            <img src={product.imageUrl} alt={product.name} className="h-full w-full object-cover" />
                          )}
                        </div>
                        <p className="mt-2 truncate text-caption text-gray-500">{product.name}</p>
                        <p className="truncate text-[10px] text-gray-300">{product.brand}</p>
                      </button>
                    ))}
                  </div>
                </section>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* 가격 추적 플로팅 바 — 고정 */}
      {trackingCount !== null && (
        <div className="fixed bottom-[72px] left-1/2 z-30 w-full max-w-[430px] -translate-x-1/2 px-4">
          <button
            className="relative flex w-full items-center gap-3 overflow-hidden rounded-2xl px-5 py-4"
            style={{
              background: "linear-gradient(135deg, rgba(91,143,217,0.18) 0%, rgba(155,191,238,0.14) 100%)",
              backdropFilter: "blur(20px)",
              WebkitBackdropFilter: "blur(20px)",
              border: "1px solid rgba(255,255,255,0.75)",
              boxShadow: "0 8px 32px rgba(91,143,217,0.18), 0 1px 0 rgba(255,255,255,0.9) inset",
            }}
            onClick={() => navigate("/favorites")}
            type="button"
          >
            <span
              className="pointer-events-none absolute inset-x-0 top-0 h-px"
              style={{ background: "linear-gradient(90deg, transparent, rgba(255,255,255,0.9), transparent)" }}
            />
            <span
              className="grid h-10 w-10 shrink-0 place-items-center rounded-xl"
              style={{
                background: "linear-gradient(135deg, rgba(91,143,217,0.35), rgba(53,101,181,0.25))",
                border: "1px solid rgba(255,255,255,0.6)",
                boxShadow: "0 2px 8px rgba(91,143,217,0.2)",
              }}
            >
              <TrendingUp className="h-5 w-5 text-primary-600" strokeWidth={1.8} />
            </span>
            <div className="flex-1 text-left">
              <p className="text-caption font-semibold text-primary-600">가격 추적</p>
              <p className="text-body2 text-gray-400">
                {trackingCount > 0
                  ? `${trackingCount}개 제품 모니터링 중이에요`
                  : "지금 바로 가격 추적을 시작해보세요"}
              </p>
            </div>
            <span
              className="flex h-7 w-7 items-center justify-center rounded-full text-body2 text-primary-500"
              style={{ background: "rgba(255,255,255,0.55)", border: "1px solid rgba(91,143,217,0.2)" }}
            >
              ›
            </span>
          </button>
        </div>
      )}

      {/* 하단 네비게이션 — 고정 */}
      <BottomNav />
    </AppLayout>
  );
}
