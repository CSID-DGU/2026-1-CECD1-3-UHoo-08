import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { type WishlistItem, deleteWishlist, getWishlists } from "../../api/wishlistApi";
import { PageHeader } from "../../components/common/PageHeader";
import AppLayout from "../../layouts/AppLayout";

export function WishlistPage() {
  const navigate = useNavigate();
  const [items, setItems] = useState<WishlistItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getWishlists()
      .then((res) => setItems(res.data.wishlists))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  async function handleDelete(e: React.MouseEvent, wishlistId: string) {
    e.stopPropagation();
    await deleteWishlist(wishlistId).catch(() => {});
    setItems((prev) => prev.filter((i) => i.wishlistId !== wishlistId));
  }

  return (
    <AppLayout>
      <section className="min-h-screen px-6 pb-8 pt-10 page-enter">
        <PageHeader title="찜한 제품" onBack={() => navigate(-1)} />

        {loading ? (
          <p className="mt-16 text-center text-body2 text-gray-300">불러오는 중...</p>
        ) : items.length === 0 ? (
          <div className="mt-24 flex flex-col items-center gap-3 text-center">
            <span className="text-5xl">🤍</span>
            <p className="mt-2 text-body1 text-gray-500">찜한 제품이 없어요</p>
            <p className="text-body2 text-gray-300">마음에 드는 제품을 찜해보세요</p>
          </div>
        ) : (
          <>
            <div className="mt-4 rounded-xl bg-primary-50 px-4 py-3">
              <p className="text-body2 text-primary-500">찜한 제품 {items.length}개</p>
            </div>

            <div className="mt-3 grid gap-3">
              {items.map((item) => (
                <button
                  key={item.wishlistId}
                  className="flex items-center gap-4 rounded-xl border border-gray-100 bg-white p-4 text-left"
                  style={{ boxShadow: "0 2px 8px rgba(91,143,217,0.06)" }}
                  onClick={() => navigate(`/product/${item.productId}`)}
                  type="button"
                >
                  <div className="flex h-[60px] w-[60px] shrink-0 items-center justify-center overflow-hidden rounded-xl bg-primary-50">
                    {item.imageUrl ? (
                      <img
                        src={item.imageUrl}
                        alt={item.name}
                        className="h-full w-full object-cover"
                      />
                    ) : (
                      <span className="text-2xl">💄</span>
                    )}
                  </div>

                  <div className="min-w-0 flex-1">
                    <p className="truncate text-body2 text-gray-500">{item.name}</p>
                    <p className="text-caption text-gray-300">{item.brand}</p>
                    {item.price != null && (
                      <p className="mt-1 text-caption text-gray-400">
                        {item.price.toLocaleString()}원
                      </p>
                    )}
                  </div>

                  <div className="flex flex-col items-end gap-2">
                    {item.matchScore != null && (
                      <span
                        className="rounded-full px-2 py-0.5 text-caption"
                        style={{ background: "#DBE6F8", color: "#3565B5" }}
                      >
                        {item.matchScore}%
                      </span>
                    )}
                    <button
                      className="text-xl leading-none"
                      onClick={(e) => handleDelete(e, item.wishlistId)}
                      type="button"
                      aria-label="찜 해제"
                    >
                      🤍
                    </button>
                  </div>
                </button>
              ))}
            </div>
          </>
        )}
      </section>
    </AppLayout>
  );
}
