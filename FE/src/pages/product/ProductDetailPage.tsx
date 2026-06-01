import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { type ProductDetail, getProductDetail, recordProductView } from "../../api/productApi";
import { PageHeader } from "../../components/common/PageHeader";
import AppLayout from "../../layouts/AppLayout";

function fmt(n: number | null | undefined) {
  if (n == null) return null;
  return n.toLocaleString("ko-KR") + "원";
}

export function ProductDetailPage() {
  const navigate = useNavigate();
  const { productId } = useParams<{ productId: string }>();
  const [product, setProduct] = useState<ProductDetail | null>(null);

  useEffect(() => {
    if (!productId) return;
    recordProductView(productId).catch(() => {});
    getProductDetail(productId)
      .then((res) => setProduct(res.data))
      .catch(() => {});
  }, [productId]);

  const features =
    product?.featureJson && typeof product.featureJson === "object"
      ? (product.featureJson as Record<string, unknown>)
      : null;

  const ingredients = features
    ? (features.key_ingredient as string[] | null)
    : null;

  return (
    <AppLayout>
      <section className="min-h-screen px-6 pb-28 pt-10">
        <PageHeader
          onBack={() => navigate(-1)}
          rightSlot={
            <button
              className="grid h-10 w-10 place-items-center rounded-xl bg-gray-100 text-h3 text-gray-300"
              type="button"
            >
              ♡
            </button>
          }
        />

        {/* 이미지 */}
        <div className="relative mt-7 h-[210px] overflow-hidden rounded-2xl bg-primary-50">
          {product?.imageUrl ? (
            <img
              src={product.imageUrl}
              alt={product.name}
              className="h-full w-full object-contain"
            />
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
              <p className="text-caption">
                {fmt(product.originalPrice - product.lowestPrice)} 절약 가능
              </p>
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
                    className="rounded-full border border-primary-500 px-3 py-1 text-caption text-primary-500"
                    key={item}
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

        {/* 하단 버튼 */}
        <div className="fixed bottom-0 left-1/2 flex h-[86px] w-full max-w-[430px] -translate-x-1/2 gap-3 bg-white px-6 py-4">
          <button
            className="h-12 w-14 rounded-xl border border-gray-300 text-h3 text-gray-300"
            type="button"
          >
            ♡
          </button>
          <button
            className="h-12 flex-1 rounded-xl bg-primary-500 text-body1 font-semibold text-white"
            onClick={() =>
              navigate("/recommendation/extra-info", {
                state: { productId: product?.productId },
              })
            }
            type="button"
          >
            추천 받기 ✦
          </button>
        </div>
      </section>
    </AppLayout>
  );
}
