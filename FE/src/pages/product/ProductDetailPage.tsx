import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Heart, Smile, Layers, Sun, Droplets, Folder } from "lucide-react";
import { type ProductDetail, type StoreInfo, getProductDetail, recordProductView } from "../../api/productApi";
import { addWishlist, deleteWishlist } from "../../api/wishlistApi";
import { PageHeader } from "../../components/common/PageHeader";
import AppLayout from "../../layouts/AppLayout";

function fmt(n: number | null | undefined) {
  if (n == null) return null;
  return n.toLocaleString("ko-KR") + "원";
}

const FOLDERS = [
  { key: "lip", label: "Lip", Icon: Smile },
  { key: "base", label: "Base", Icon: Layers },
  { key: "sun", label: "Sun", Icon: Sun },
  { key: "skincare", label: "Skincare", Icon: Droplets },
  { key: "other", label: "기타", Icon: Folder },
];

function GlassHeart() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <linearGradient id="hFill" x1="4" y1="4" x2="20" y2="20" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#7AAEE4" />
          <stop offset="100%" stopColor="#3565B5" />
        </linearGradient>
        <linearGradient id="hShine" x1="6" y1="5" x2="13" y2="11" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="rgba(255,255,255,0.6)" />
          <stop offset="100%" stopColor="rgba(255,255,255,0)" />
        </linearGradient>
      </defs>
      <path
        d="M12 21C12 21 3 14.5 3 8.5C3 5.42 5.42 3 8.5 3C10.24 3 11.91 3.81 13 5.08C14.09 3.81 15.76 3 17.5 3C20.58 3 23 5.42 23 8.5C23 14.5 12 21 12 21Z"
        fill="url(#hFill)"
      />
      <path
        d="M8 5.5C6.5 6 5 7.5 4.5 9.5"
        stroke="url(#hShine)"
        strokeWidth="2.5"
        strokeLinecap="round"
        opacity="0.75"
      />
      <path
        d="M12 21C12 21 3 14.5 3 8.5C3 5.42 5.42 3 8.5 3C10.24 3 11.91 3.81 13 5.08C14.09 3.81 15.76 3 17.5 3C20.58 3 23 5.42 23 8.5C23 14.5 12 21 12 21Z"
        fill="none"
        stroke="rgba(255,255,255,0.4)"
        strokeWidth="1"
      />
    </svg>
  );
}

export function ProductDetailPage() {
  const navigate = useNavigate();
  const { productId } = useParams<{ productId: string }>();
  const [product, setProduct] = useState<ProductDetail | null>(null);
  const [wishlisted, setWishlisted] = useState(false);
  const [wishlistId, setWishlistId] = useState<string | null>(null);
  const [showCategorySheet, setShowCategorySheet] = useState(false);
  const [sheetEverOpened, setSheetEverOpened] = useState(false);
  const [adding, setAdding] = useState(false);

  useEffect(() => {
    if (!productId) return;
    recordProductView(productId).catch(() => {});
    getProductDetail(productId)
      .then((res) => {
        setProduct(res.data);
        setWishlisted(res.data.wishlisted ?? false);
        setWishlistId(res.data.wishlistId ?? null);
      })
      .catch(() => {});
  }, [productId]);

  function handleHeartClick() {
    if (!productId) return;
    if (wishlisted && wishlistId) {
      deleteWishlist(wishlistId).catch(() => {});
      setWishlisted(false);
      setWishlistId(null);
    } else {
      setSheetEverOpened(true);
      setShowCategorySheet(true);
    }
  }

  async function handleAddToCategory(_categoryKey: string) {
    if (!productId || adding) return;
    setAdding(true);
    try {
      const res = await addWishlist(productId);
      if (res?.data?.wishlistId) {
        setWishlisted(true);
        setWishlistId(res.data.wishlistId);
      }
    } catch {
      // silent
    } finally {
      setAdding(false);
      setShowCategorySheet(false);
    }
  }

  const features =
    product?.featureJson && typeof product.featureJson === "object"
      ? (product.featureJson as Record<string, unknown>)
      : null;

  const ingredients = features ? (features.key_ingredient as string[] | null) : null;

  return (
    <AppLayout>
      <div className="flex h-screen flex-col overflow-hidden">
        <div className="flex-1 overflow-y-auto scrollbar-none">
      <section className="px-6 pb-28 pt-10">
        <PageHeader
          onBack={() => navigate(-1)}
          rightSlot={
            <button
              className="grid h-10 w-10 place-items-center rounded-xl bg-gray-100"
              onClick={handleHeartClick}
              type="button"
              aria-label="찜하기"
            >
              {wishlisted ? <GlassHeart /> : <Heart className="h-6 w-6 text-gray-400" strokeWidth={1.8} />}
            </button>
          }
        />

        {/* 이미지 */}
        <div className="relative mt-7 h-[210px] overflow-hidden rounded-2xl bg-primary-50">
          {product?.imageUrl ? (
            <img src={product.imageUrl} alt={product.name} className="h-full w-full object-contain" />
          ) : (
            <div className="h-full w-full bg-primary-100" />
          )}
        </div>

        <p className="mt-3 text-caption text-gray-300">
          {product?.brand ?? "—"}
          {product?.category ? ` · ${product.category}` : ""}
        </p>
        <h1 className="mt-1 text-h2 text-gray-500">{product?.name ?? "로딩 중..."}</h1>

        {/* 가격 */}
        {product?.originalPrice != null && (
          <div className="mt-7 flex items-center justify-between text-body2">
            <span className="text-gray-300">정가</span>
            <span className="text-gray-300 line-through">{fmt(product.originalPrice)}</span>
          </div>
        )}

        {product?.lowestPrice != null && (
          <div className="mt-2 flex items-center justify-between rounded-xl bg-gray-500 px-5 py-4 text-white">
            <div className="flex items-center gap-4">
              <span className="text-primary-500">╋</span>
              <div>
                <p className="text-caption text-gray-300">최저가 검색 결과입니다.</p>
                <p className="text-h2">{fmt(product.lowestPrice)}</p>
              </div>
            </div>
            {product.originalPrice != null && (
              <p className="text-caption">{fmt(product.originalPrice - product.lowestPrice)} 절약 가능</p>
            )}
          </div>
        )}

        {/* 주요 성분 */}
        {ingredients && ingredients.length > 0 && (
          <section className="mt-6 border-t border-gray-100 pt-5">
            <h2 className="text-body1 text-gray-500">주요 성분</h2>
            <div className="mt-3 rounded-xl bg-primary-50 p-4">
              <div className="flex flex-wrap gap-2">
                {ingredients.map((item) => (
                  <span
                    key={item}
                    className="rounded-full border border-primary-500 px-3 py-1 text-caption text-primary-500"
                  >
                    {item}
                  </span>
                ))}
              </div>
            </div>
          </section>
        )}

        {/* 리뷰 요약 */}
        {(product?.reviewSummary || product?.averageScore != null) && (
          <section className="mt-6">
            <div className="flex justify-between">
              <h2 className="text-body1 text-gray-500">리뷰 요약</h2>
              {product?.reviewCount != null && (
                <span className="text-caption text-gray-300">
                  {product.reviewCount.toLocaleString("ko-KR")}개의 리뷰 기준
                </span>
              )}
            </div>
            {product?.averageScore != null && (
              <div className="mt-3 flex items-center justify-between rounded-xl border border-gray-200 bg-white p-4">
                <div>
                  <span className="text-h1 text-gray-500">{product.averageScore} 점</span>
                  <span className="ml-3 text-[#FFB000]">★★★★★</span>
                  <p className="text-caption text-gray-300">/ 5.0점</p>
                </div>
              </div>
            )}
            {product?.reviewSummary && (
              <div className="mt-3 bg-primary-50 p-4">
                <p className="text-body2 text-primary-500">✦ AI 리뷰 요약</p>
                <p className="mt-2 text-caption leading-6 text-gray-500">
                  "{product.reviewSummary}"
                </p>
              </div>
            )}
          </section>
        )}

        {/* 구매처별 가격 */}
        {product?.stores && product.stores.length > 0 && (
          <section className="mt-6 border-t border-gray-100 pt-5">
            <h2 className="text-body1 text-gray-500">구매처별 가격</h2>
            <div className="mt-3 grid gap-2">
              {product.stores.map((store: StoreInfo) => (
                <div
                  key={store.storeName}
                  className={`flex items-center justify-between rounded-xl px-4 py-3 ${
                    store.isLowest ? "border border-primary-100 bg-primary-50" : "bg-gray-100"
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <span className="text-body2 text-gray-500">{store.storeName}</span>
                    {store.isLowest && (
                      <span className="rounded-full bg-primary-500 px-2 py-0.5 text-[10px] text-white">최저</span>
                    )}
                  </div>
                  <span className={`text-body2 ${store.isLowest ? "font-semibold text-primary-500" : "text-gray-500"}`}>
                    {store.price.toLocaleString("ko-KR")}원
                  </span>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* 하단 버튼 */}
        <div className="fixed bottom-0 left-1/2 flex h-[86px] w-full max-w-[430px] -translate-x-1/2 gap-3 bg-white px-6 py-4">
          <button
            className="grid h-12 w-14 place-items-center rounded-xl border border-gray-200"
            onClick={handleHeartClick}
            type="button"
            aria-label="찜하기"
          >
            {wishlisted ? <GlassHeart /> : <Heart className="h-6 w-6 text-gray-400" strokeWidth={1.8} />}
          </button>
          <button
            className="h-12 flex-1 rounded-xl bg-primary-500 text-body1 font-semibold text-white"
            onClick={() =>
              navigate("/recommendation/extra-info", {
                state: {
                  productId: product?.productId,
                  productName: product?.name,
                  productBrand: product?.brand,
                  productImageUrl: product?.imageUrl,
                },
              })
            }
            type="button"
          >
            나와 맞는지 알아보기 ✦
          </button>
        </div>
      </section>
        </div>
      </div>

      {/* dim */}
      <div
        className="fixed inset-0 z-40 transition-all duration-300"
        style={{
          background: "rgba(0,0,0,0.3)",
          opacity: showCategorySheet ? 1 : 0,
          pointerEvents: showCategorySheet ? "auto" : "none",
        }}
        onClick={() => setShowCategorySheet(false)}
      />

      {/* 카테고리 선택 바텀시트 */}
      <div
        className="fixed inset-x-0 bottom-0 z-50 mx-auto max-w-[430px] rounded-t-2xl bg-white p-6 shadow-2xl"
        style={{
          transform: showCategorySheet ? "translateY(0)" : "translateY(105%)",
          transition: sheetEverOpened ? "transform 0.32s cubic-bezier(0.32, 0.72, 0, 1)" : "none",
          willChange: "transform",
        }}
      >
        <div className="mx-auto mb-5 h-1 w-10 rounded-full bg-gray-200" />
        <h2 className="text-h3 text-gray-500">어떤 폴더에 추가할까요?</h2>
        <p className="mt-1 text-caption text-gray-300">카테고리를 선택해주세요</p>

        <div className="mt-5 grid grid-cols-3 gap-3">
          {FOLDERS.map(({ key, label, Icon }) => (
            <button
              key={key}
              className="flex flex-col items-center gap-2 rounded-2xl py-4 transition-all"
              style={{
                background: "linear-gradient(135deg, #9DBFEE, #C5DDF5)",
              }}
              onClick={() => handleAddToCategory(key)}
              disabled={adding}
              type="button"
            >
              <span
                className="flex h-10 w-10 items-center justify-center rounded-full"
                style={{ background: "rgba(255,255,255,0.5)" }}
              >
                <Icon className="h-5 w-5 text-primary-600" strokeWidth={1.8} />
              </span>
              <span className="text-caption font-medium text-primary-700">{label}</span>
            </button>
          ))}
        </div>

        <button
          className="mt-4 w-full py-3 text-body2 text-gray-300"
          onClick={() => setShowCategorySheet(false)}
          type="button"
        >
          취소
        </button>
      </div>
    </AppLayout>
  );
}
