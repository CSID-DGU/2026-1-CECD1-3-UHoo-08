import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { type ProductSearchItem, getProductDetail, searchProducts } from "../../api/productApi";
import { addTracking } from "../../api/priceTrackingApi";
import { type WishlistItem, getWishlists } from "../../api/wishlistApi";
import { PageHeader } from "../../components/common/PageHeader";
import { PrimaryButton } from "../../components/common/PrimaryButton";
import { Toggle } from "../../components/common/Toggle";
import AppLayout from "../../layouts/AppLayout";

type SelectedProduct = {
  productId: string;
  name: string;
  brand: string;
  price: number;
  lowestPrice: number | null;
};

function roundToThousand(n: number) {
  return Math.round(n / 1000) * 1000;
}

export function PriceTrackingAddPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const stateProduct = (location.state as { product?: SelectedProduct } | null)?.product;

  const [wishlists, setWishlists] = useState<WishlistItem[]>([]);
  const [selected, setSelected] = useState<SelectedProduct | null>(stateProduct ?? null);
  const [targetPrice, setTargetPrice] = useState(0);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [alertEnabled, setAlertEnabled] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<ProductSearchItem[]>([]);
  const [searching, setSearching] = useState(false);
  const searchRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    getWishlists()
      .then((res) => {
        const list = res.data?.wishlists ?? (Array.isArray(res.data) ? (res.data as WishlistItem[]) : []);
        setWishlists(list);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!selected) return;
    // lowestPrice가 없으면 상품 상세 조회
    if (selected.lowestPrice === null) {
      setLoadingDetail(true);
      getProductDetail(selected.productId)
        .then((res) => {
          const lp = res.data?.lowestPrice ?? null;
          setSelected((prev) => prev ? { ...prev, lowestPrice: lp } : prev);
          // 목표가 기본값: lowestPrice - 1000 (없으면 현재가 90%)
          const base = lp != null ? lp - 1000 : (selected.price > 0 ? roundToThousand(selected.price * 0.9) : 10000);
          setTargetPrice(Math.max(1000, base));
        })
        .catch(() => {
          const base = selected.price > 0 ? roundToThousand(selected.price * 0.9) : 10000;
          setTargetPrice(base);
        })
        .finally(() => setLoadingDetail(false));
    } else {
      const base = selected.lowestPrice > 0 ? selected.lowestPrice - 1000 : 10000;
      setTargetPrice(Math.max(1000, base));
    }
  }, [selected?.productId]);

  function handleSelectWishlist(item: WishlistItem) {
    setSelected({
      productId: item.product.id,
      name: item.product.name,
      brand: item.product.brand,
      price: item.product.currentPrice ?? 0,
      lowestPrice: null,
    });
  }

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!searchQuery.trim()) return;
    setSearching(true);
    try {
      const res = await searchProducts(searchQuery.trim());
      setSearchResults(res.data?.products ?? []);
    } catch {
      setSearchResults([]);
    } finally {
      setSearching(false);
    }
  }

  function handleSelectSearchResult(product: ProductSearchItem) {
    setSelected({
      productId: product.id,
      name: product.name,
      brand: product.brand,
      price: product.originalPrice ?? 0,
      lowestPrice: null,
    });
    setSearchQuery("");
    setSearchResults([]);
  }

  async function handleSubmit() {
    if (!selected || loadingDetail) return;
    if (targetPrice <= 0) {
      setSubmitError("목표가를 설정해주세요.");
      return;
    }
    if (selected.lowestPrice != null && targetPrice >= selected.lowestPrice) {
      setSubmitError(`목표가는 역대 최저가(${selected.lowestPrice.toLocaleString()}원)보다 낮아야 해요`);
      return;
    }
    setSubmitError(null);
    setSubmitting(true);
    try {
      await addTracking(selected.productId, targetPrice, alertEnabled);
      navigate("/favorites", { replace: true });
    } catch (err: unknown) {
      const msg =
        (err as { message?: string })?.message ??
        (err as { error?: string })?.error ??
        "추적 등록에 실패했어요. 다시 시도해주세요.";
      setSubmitError(msg);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AppLayout>
      <div className="flex h-screen flex-col overflow-hidden">
        <div className="flex-1 overflow-y-auto scrollbar-none">
      <section className="px-6 pb-6 pt-10">
        <PageHeader title="가격 추적 추가" onBack={() => navigate(-1)} />

        <div className="mt-7">
          <h1 className="text-h2 text-gray-500">
            어떤 제품을
            <br />
            추적할까요?
          </h1>
          <p className="mt-2 text-body2 text-gray-300">실시간으로 가격을 모니터링해요</p>
        </div>

        {/* 찜 목록에서 선택 */}
        {wishlists.length > 0 && (
          <>
            <div className="mt-6">
              <h2 className="text-body2 text-gray-500">찜 목록에서 선택</h2>
            </div>
            <div className="mt-3 flex gap-2 overflow-x-auto pb-1">
              {wishlists.map((item) => (
                <button
                  key={item.wishlistId}
                  className={`min-w-[90px] rounded-xl border p-3 text-center ${
                    selected?.productId === item.product.id
                      ? "border-primary-500 bg-primary-50"
                      : "border-gray-200 bg-white"
                  }`}
                  onClick={() => handleSelectWishlist(item)}
                  type="button"
                >
                  <div className="mx-auto h-11 w-11 rounded-xl bg-primary-50" />
                  <p className="mt-2 truncate text-caption text-primary-500">{item.product.name}</p>
                  <p className="truncate text-[10px] text-gray-300">{item.product.brand}</p>
                  {item.product.currentPrice != null && (
                    <p className="text-caption text-primary-500">
                      {item.product.currentPrice.toLocaleString()}원
                    </p>
                  )}
                </button>
              ))}
            </div>
          </>
        )}

        <Divider />

        {/* 직접 검색 */}
        <h2 className="text-body2 text-gray-500">직접 검색해서 추가</h2>
        <form className="mt-3 flex gap-2" onSubmit={handleSearch}>
          <input
            ref={searchRef}
            className="h-12 flex-1 rounded-xl bg-gray-100 px-4 text-body2 outline-none placeholder:text-gray-300 focus:border focus:border-primary-500 focus:bg-white"
            placeholder="브랜드명, 제품명 검색..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
          <button
            className="h-12 rounded-xl bg-primary-500 px-4 text-body2 text-white disabled:opacity-50"
            disabled={searching || !searchQuery.trim()}
            type="submit"
          >
            {searching ? "···" : "검색"}
          </button>
        </form>

        {searchResults.length > 0 && (
          <div className="mt-2 overflow-hidden rounded-xl border border-gray-200 bg-white">
            {searchResults.map((product) => (
              <button
                key={product.id}
                className="flex w-full items-center gap-3 border-b border-gray-100 p-3 text-left last:border-b-0 active:bg-gray-50"
                onClick={() => handleSelectSearchResult(product)}
                type="button"
              >
                <div className="h-11 w-11 shrink-0 rounded-xl bg-primary-50" />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-body2 text-gray-500">{product.name}</p>
                  <p className="text-caption text-gray-300">{product.brand}</p>
                </div>
                <div className="shrink-0 text-right">
                  {product.originalPrice != null && (
                    <p className="text-caption text-gray-400">{product.originalPrice.toLocaleString()}원</p>
                  )}
                </div>
              </button>
            ))}
          </div>
        )}

        {!searching && searchQuery.trim() && searchResults.length === 0 && (
          <p className="mt-2 text-caption text-gray-300">검색 결과가 없어요</p>
        )}

        {/* 선택된 제품 */}
        {selected && (
          <>
            <Divider />
            <h2 className="text-body2 text-gray-500">선택한 제품</h2>
            <div className="mt-3 flex items-center gap-3 rounded-xl border border-primary-500 bg-white p-3">
              <div className="h-14 w-14 shrink-0 rounded-xl bg-primary-50" />
              <div className="min-w-0 flex-1">
                <p className="truncate text-body2 text-gray-500">{selected.name}</p>
                <p className="text-caption text-gray-300">
                  {selected.brand}{selected.price > 0 ? ` · 현재가 ${selected.price.toLocaleString()}원` : ""}
                </p>
              </div>
              <button
                className="h-7 w-7 rounded-full bg-gray-100 text-gray-300"
                onClick={() => setSelected(null)}
                type="button"
              >
                ×
              </button>
            </div>

            {/* 목표가 설정 */}
            <h2 className="mt-5 text-body2 text-gray-500">목표가 설정</h2>
            {loadingDetail ? (
              <div className="mt-3 flex h-[60px] items-center justify-center rounded-xl border border-gray-200">
                <p className="text-caption text-gray-300">최저가 조회 중...</p>
              </div>
            ) : (
              <>
                {selected?.lowestPrice != null && (
                  <p className="mt-2 text-caption text-primary-500">
                    역대 최저가 {selected.lowestPrice.toLocaleString()}원 —
                    <span className="text-gray-400"> 그보다 낮게 설정해야 해요</span>
                  </p>
                )}
                <button
                  className="mt-2 flex h-[60px] w-full items-center justify-between rounded-xl border border-primary-500 px-3"
                  onClick={() => setModalOpen(true)}
                  type="button"
                >
                  <span
                    className="grid h-9 w-9 place-items-center rounded-lg bg-gray-100 text-h3"
                    onClick={(e) => {
                      e.stopPropagation();
                      setTargetPrice((p) => Math.max(1000, p - 1000));
                    }}
                  >
                    −
                  </span>
                  <strong className="text-h2 text-gray-500">{targetPrice.toLocaleString()}원</strong>
                  <span
                    className="grid h-9 w-9 place-items-center rounded-lg bg-gray-100 text-h3"
                    onClick={(e) => {
                      e.stopPropagation();
                      setTargetPrice((p) => p + 1000);
                    }}
                  >
                    ＋
                  </span>
                </button>
                {selected?.lowestPrice != null && targetPrice >= selected.lowestPrice && (
                  <p className="mt-1 text-caption text-red-400">
                    목표가는 역대 최저가({selected.lowestPrice.toLocaleString()}원)보다 낮아야 해요
                  </p>
                )}
              </>
            )}

            {/* 알림 토글 */}
            <div className="mt-4 flex items-center gap-3 rounded-xl border border-gray-200 p-4">
              <div className="flex-1">
                <p className="text-body2 text-gray-500">목표가 도달 시 푸시 알림</p>
                <p className="text-caption text-gray-300">설정한 금액 이하가 되면 바로 알려드려요</p>
              </div>
              <button onClick={() => setAlertEnabled((v) => !v)} type="button">
                <Toggle checked={alertEnabled} />
              </button>
            </div>

            {submitError && (
              <p className="mt-3 rounded-xl bg-red-50 px-4 py-3 text-caption text-red-500">
                {submitError}
              </p>
            )}
            <PrimaryButton className="mt-3" onClick={handleSubmit} disabled={submitting || loadingDetail}>
              {submitting ? "등록 중..." : loadingDetail ? "가격 조회 중..." : "추적 시작하기"}
            </PrimaryButton>
          </>
        )}
      </section>
        </div>
      </div>

      {modalOpen && (
        <TargetPriceModal
          current={targetPrice}
          onChange={setTargetPrice}
          onClose={() => setModalOpen(false)}
        />
      )}
    </AppLayout>
  );
}

function TargetPriceModal({
  current,
  onChange,
  onClose,
}: {
  current: number;
  onChange: (v: number) => void;
  onClose: () => void;
}) {
  const [local, setLocal] = useState(current);

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/60">
      <div className="w-full max-w-[430px] rounded-t-3xl bg-white px-6 pb-9 pt-4">
        <div className="mx-auto mb-6 h-1 w-12 rounded-full bg-gray-200" />
        <p className="ml-auto w-fit rounded-full bg-primary-50 px-5 py-2 text-caption text-primary-500">
          현재 목표 {local.toLocaleString()}원
        </p>
        <div className="mt-3 flex h-[76px] items-center justify-between rounded-2xl bg-gray-100 px-3">
          <button
            className="grid h-12 w-12 place-items-center rounded-xl bg-white text-h3"
            onClick={() => setLocal((p) => Math.max(1000, p - 1000))}
            type="button"
          >
            −
          </button>
          <strong className="text-h2 text-gray-500">{local.toLocaleString()}원</strong>
          <button
            className="grid h-12 w-12 place-items-center rounded-xl bg-white text-h3"
            onClick={() => setLocal((p) => p + 1000)}
            type="button"
          >
            ＋
          </button>
        </div>
        <p className="mt-2 text-center text-caption text-gray-300">1,000원 단위로 조정돼요</p>
        <PrimaryButton
          className="mt-4"
          onClick={() => {
            onChange(local);
            onClose();
          }}
        >
          목표가 저장하기
        </PrimaryButton>
      </div>
    </div>
  );
}

function Divider() {
  return <div className="my-5 h-px bg-gray-100" />;
}
