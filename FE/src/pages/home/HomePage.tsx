import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { type ProductSearchItem, getRecentlyViewed } from "../../api/productApi";
import { getUnreadCount } from "../../api/notificationApi";
import { getTrackings } from "../../api/priceTrackingApi";
import { BottomNav } from "../../components/common/BottomNav";
import { SearchField } from "../../components/common/SearchField";
import { type LastSearch, getLastSearch } from "../../lib/localHistory";
import AppLayout from "../../layouts/AppLayout";

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
      .then((res) => setTrackingCount(res.data?.total ?? 0))
      .catch(() => setTrackingCount(0));
  }, []);

  function handleSearch(query: string) {
    if (!query) return;
    navigate("/search", { state: { query } });
  }

  return (
    <AppLayout>
      <section className="min-h-screen overflow-hidden px-6 pb-[148px] pt-10">
        <header className="flex items-start justify-between">
          <div>
            <h1 className="text-h3 text-gray-500">BeautyMatch</h1>
            <p className="mt-1 text-body2 text-gray-300">안녕하세요 👋</p>
          </div>
          <button
            className="relative h-11 w-11 rounded-full bg-gray-100"
            onClick={() => navigate("/notifications")}
            type="button"
            aria-label="알림"
          >
            {hasUnread && (
              <span className="absolute right-0.5 top-0.5 h-2.5 w-2.5 rounded-full bg-primary-500" />
            )}
            <span className="absolute left-1/2 top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-sm bg-gray-200" />
          </button>
        </header>

        <div className="mt-5">
          <SearchField
            editable
            placeholder="여름 가벼운 쿠션 추천해줘"
            onSubmit={handleSearch}
          />
        </div>

        <section className="mt-4 overflow-hidden rounded-2xl bg-gray-500 text-white">
          <div className="grid grid-cols-[1fr_46%]">
            <div className="p-5">
              <p className="text-caption text-primary-300">오늘의 추천 ✦</p>
              <h2 className="mt-2 text-h3">
                내 피부에 딱 맞는
                <br />
                제품을 찾았어요
              </h2>
              <button
                className="mt-5 rounded-full bg-primary-500 px-7 py-2 text-caption font-semibold"
                onClick={() => navigate("/recommendation/lookup")}
                type="button"
              >
                확인하기 →
              </button>
            </div>
            <div className="relative min-h-[118px] rounded-l-2xl bg-primary-700">
              <span className="absolute left-16 top-7 h-16 w-16 rounded-full bg-primary-100/20" />
              <span className="absolute right-6 top-12 h-12 w-12 rounded-full bg-primary-300/30" />
              <span className="absolute bottom-7 left-12 h-6 w-6 rounded-full bg-primary-300/40" />
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
            <div className="flex gap-3 overflow-x-auto pb-1">
              {lastSearch.products.map((product) => (
                <button
                  className="min-w-[154px] rounded-2xl border border-gray-200 bg-white p-3 text-left"
                  key={product.productId}
                  onClick={() => navigate(`/product/${product.productId}`)}
                  type="button"
                >
                  <div className="h-[94px] rounded-xl bg-primary-50" />
                  <p className="mt-3 truncate text-body2 text-gray-500">{product.name}</p>
                  <div className="mt-2 flex items-center justify-between">
                    <span className="rounded-full bg-primary-50 px-2 py-0.5 text-caption text-primary-500">
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

        <section className="mt-4 rounded-xl border border-primary-100 bg-primary-50 p-4">
          <p className="text-body2 text-primary-500">✦ AI 분석</p>
          <p className="mt-1 text-caption text-gray-500">
            가벼운 제형 선호도 + 여름철 지성 고민 기반으로 피지 조절 강화 제품을 우선 추천했어요
          </p>
        </section>

        {recentlyViewed.length > 0 && (
          <section className="mt-4">
            <h2 className="text-body1 text-gray-500">최근 본 상품</h2>
            <div className="mt-3 flex gap-3 overflow-x-auto">
              {recentlyViewed.map((product) => (
                <button
                  className="min-w-[96px] rounded-xl border border-gray-200 bg-white p-2 text-center"
                  key={String(product.id)}
                  onClick={() => navigate(`/product/${product.id}`)}
                  type="button"
                >
                  <div className="h-[70px] rounded-lg bg-gray-100" />
                  <p className="mt-2 truncate text-caption text-gray-500">{product.name}</p>
                  <p className="truncate text-[10px] text-gray-300">{product.brand}</p>
                </button>
              ))}
            </div>
          </section>
        )}
      </section>

      {trackingCount !== null && (
        <div className="fixed bottom-[72px] left-1/2 z-30 w-full max-w-[430px] -translate-x-1/2 px-4">
          <button
            className="flex w-full items-center gap-3 rounded-2xl bg-gray-500 px-5 py-3.5 text-white shadow-xl"
            onClick={() => navigate("/favorites")}
            type="button"
          >
            <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-primary-500 text-sm">
              📊
            </span>
            <div className="flex-1 text-left">
              <p className="text-caption text-primary-300">가격 추적</p>
              <p className="text-body2">
                {trackingCount > 0 ? `${trackingCount}개 제품 모니터링 중이에요` : "지금 바로 가격 추적을 시작해보세요"}
              </p>
            </div>
            <span className="text-body1 text-gray-300">›</span>
          </button>
        </div>
      )}

      <BottomNav />
    </AppLayout>
  );
}
