import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Heart } from "lucide-react";
import { type WishlistItem, deleteWishlist, getWishlists } from "../../api/wishlistApi";
import { PageHeader } from "../../components/common/PageHeader";
import AppLayout from "../../layouts/AppLayout";

export function WishlistCategoryPage() {
  const navigate = useNavigate();
  const { category } = useParams<{ category: string }>();
  const [items, setItems] = useState<WishlistItem[]>([]);
  const [loading, setLoading] = useState(true);

  const decoded = decodeURIComponent(category ?? "");

  useEffect(() => {
    getWishlists()
      .then((res) => {
        const all = res.data.wishlists ?? [];
        setItems(
          decoded === "all"
            ? all
            : all.filter(
                (i) => (i.product.category ?? "").toLowerCase() === decoded.toLowerCase(),
              ),
        );
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [decoded]);

  async function handleDelete(e: React.MouseEvent, wishlistId: string) {
    e.stopPropagation();
    await deleteWishlist(wishlistId).catch(() => {});
    setItems((prev) => prev.filter((i) => i.wishlistId !== wishlistId));
  }

  return (
    <AppLayout>
      <div className="flex h-screen flex-col overflow-hidden">
        <div className="flex-1 overflow-y-auto scrollbar-none">
        <section className="overflow-x-hidden px-5 pb-8 pt-10">
        <PageHeader
          title={decoded === "all" ? "전체" : decoded.charAt(0).toUpperCase() + decoded.slice(1)}
          onBack={() => navigate(-1)}
        />

        {loading ? (
          <p className="mt-16 text-center text-body2 text-gray-300">불러오는 중...</p>
        ) : items.length === 0 ? (
          <div className="mt-24 flex flex-col items-center gap-3 text-center">
            <span className="flex h-20 w-20 items-center justify-center rounded-full bg-primary-50">
              <Heart className="h-9 w-9 text-primary-300" strokeWidth={1.5} />
            </span>
            <p className="mt-2 text-body1 text-gray-500">이 폴더에 찜한 제품이 없어요</p>
            <p className="text-body2 text-gray-300">마음에 드는 제품을 찜해보세요</p>
          </div>
        ) : (
          <>
            <div className="mt-4 rounded-xl bg-primary-50 px-4 py-3">
              <p className="text-body2 text-primary-500">{items.length}개 제품</p>
            </div>

            <div className="mt-3 flex flex-col gap-3">
              {items.map((item) => (
                <article
                  key={item.wishlistId}
                  className="flex items-center gap-3 rounded-xl border border-gray-100 bg-white p-4"
                >
                  {/* 이미지 */}
                  <button
                    className="h-[58px] w-[58px] shrink-0 overflow-hidden rounded-xl bg-primary-50"
                    onClick={() => navigate(`/product/${item.product.id}`)}
                    type="button"
                  >
                    {item.product.imageUrl ? (
                      <img
                        src={item.product.imageUrl}
                        alt={item.product.name}
                        className="h-full w-full object-cover"
                      />
                    ) : (
                      <div className="flex h-full w-full items-center justify-center">
                        <Heart className="h-5 w-5 text-primary-300" strokeWidth={1.5} />
                      </div>
                    )}
                  </button>

                  {/* 텍스트 */}
                  <button
                    className="min-w-0 flex-1 text-left"
                    onClick={() => navigate(`/product/${item.product.id}`)}
                    type="button"
                  >
                    <p className="truncate text-body2 text-gray-500">{item.product.name}</p>
                    <p className="truncate text-caption text-gray-300">{item.product.brand}</p>
                    {item.product.lowestPrice != null ? (
                      <p className="mt-1 text-caption text-primary-500">
                        최저 {item.product.lowestPrice.toLocaleString()}원
                      </p>
                    ) : item.product.currentPrice != null ? (
                      <p className="mt-1 text-caption text-gray-400">
                        {item.product.currentPrice.toLocaleString()}원
                      </p>
                    ) : null}
                  </button>

                  {/* 우측 */}
                  <div className="flex shrink-0 flex-col items-end gap-2">
                    {item.matchScore != null && (
                      <span
                        className="rounded-full px-2 py-0.5 text-caption"
                        style={{ background: "#DBE6F8", color: "#3565B5" }}
                      >
                        {item.matchScore}%
                      </span>
                    )}
                    <button
                      className="flex h-8 w-8 items-center justify-center rounded-full bg-gray-100"
                      onClick={(e) => handleDelete(e, item.wishlistId)}
                      type="button"
                      aria-label="찜 해제"
                    >
                      <Heart className="h-4 w-4 fill-primary-400 text-primary-400" strokeWidth={1.5} />
                    </button>
                  </div>
                </article>
              ))}
            </div>
          </>
        )}
        </section>
        </div>
      </div>
    </AppLayout>
  );
}
