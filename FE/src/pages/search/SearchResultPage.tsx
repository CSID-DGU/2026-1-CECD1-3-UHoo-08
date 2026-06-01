import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { type AiSearchProduct, aiSearch, recordProductView } from "../../api/productApi";
import { BottomNav } from "../../components/common/BottomNav";
import { PageHeader } from "../../components/common/PageHeader";
import { SearchField } from "../../components/common/SearchField";
import { saveLastSearch } from "../../lib/localHistory";
import AppLayout from "../../layouts/AppLayout";

const CATEGORY_LABEL: Record<string, string> = {
  base: "베이스 메이크업",
  sun: "선케어",
  lip: "립 메이크업",
  skincare: "스킨케어",
};

export function SearchResultPage() {
  const navigate = useNavigate();
  const { state } = useLocation() as { state: { query?: string } | null };
  const initialQuery = state?.query ?? "";

  const [query, setQuery] = useState(initialQuery);
  const [products, setProducts] = useState<AiSearchProduct[]>([]);
  const [category, setCategory] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!initialQuery) return;
    runSearch(initialQuery);
  }, [initialQuery]);

  async function runSearch(q: string) {
    if (!q.trim()) return;
    setLoading(true);
    setError("");
    try {
      const res = await aiSearch(q);
      setProducts(res.products);
      setCategory(res.category);
      saveLastSearch({ query: q, category: res.category, products: res.products });
    } catch {
      setError("검색 중 오류가 발생했어요. 다시 시도해주세요.");
    } finally {
      setLoading(false);
    }
  }

  function handleSubmit(q: string) {
    setQuery(q);
    runSearch(q);
  }

  return (
    <AppLayout>
      <section className="flex min-h-screen flex-col px-6 pb-[88px] pt-10">
        <PageHeader title="검색 결과" onBack={() => navigate(-1)} />

        <div className="mt-5">
          <SearchField
            editable
            variant="outlined"
            placeholder="여름 가벼운 쿠션 추천해줘"
            value={query}
            onSubmit={handleSubmit}
          />
        </div>

        {loading && (
          <div className="mt-8 flex flex-col items-center gap-3 text-gray-300">
            <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary-200 border-t-primary-500" />
            <p className="text-body2">AI가 상품을 분석하고 있어요...</p>
          </div>
        )}

        {!loading && error && (
          <p className="mt-8 text-center text-body2 text-gray-300">{error}</p>
        )}

        {!loading && !error && products.length > 0 && (
          <>
            <div className="mt-4 flex items-center justify-between">
              <p className="text-caption text-gray-300">
                {category ? `${CATEGORY_LABEL[category] ?? category} · ` : ""}총 {products.length}개 결과
              </p>
            </div>

            <div className="mt-3 grid gap-4">
              {products.map((product) => (
                <button
                  className="flex items-center gap-4 rounded-2xl border border-gray-100 bg-white p-4 text-left shadow-sm"
                  key={product.productId}
                  onClick={() => {
                    recordProductView(product.productId).catch(() => {});
                    navigate(`/product/${product.productId}`);
                  }}
                  type="button"
                >
                  <div className="h-[72px] w-[72px] shrink-0 rounded-xl bg-gray-100" />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-body2 font-semibold text-gray-500">{product.name}</p>
                    <p className="mt-0.5 text-caption text-gray-300">{product.brand}</p>
                    {product.originalPrice != null && (
                      <p className="mt-1 text-body2 text-gray-500">
                        {product.originalPrice.toLocaleString()}원
                      </p>
                    )}
                  </div>
                  {product.matchScore > 0 && (
                    <span className="shrink-0 rounded-full bg-primary-50 px-2.5 py-1 text-caption font-semibold text-primary-500">
                      {product.matchScore}%
                    </span>
                  )}
                </button>
              ))}
            </div>

            <div className="mt-5 rounded-xl bg-primary-50 p-4">
              <p className="text-body2 text-primary-500">✦ AI 추천 기준</p>
              <p className="mt-1 text-caption text-gray-500">
                입력하신 조건에서 카테고리와 피부 타입·마무리감 등을 분석해 유사도 높은 순으로 정렬했어요
              </p>
            </div>
          </>
        )}

        {!loading && !error && products.length === 0 && query && (
          <div className="mt-12 flex flex-col items-center gap-2 text-center">
            <p className="text-body2 text-gray-400">검색 결과가 없어요</p>
            <p className="text-caption text-gray-300">다른 표현으로 다시 검색해 보세요</p>
          </div>
        )}
      </section>

      <BottomNav />
    </AppLayout>
  );
}
