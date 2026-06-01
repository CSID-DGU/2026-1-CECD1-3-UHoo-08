import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { searchProducts } from "../../api/productApi";
import type { ProductSearchItem } from "../../api/productApi";
import { PageHeader } from "../../components/common/PageHeader";
import AppLayout from "../../layouts/AppLayout";
import { addRegisteredProduct, getRegisteredProducts } from "../../lib/onboardingProducts";

export function ProductSearchSetupPage() {
  const navigate = useNavigate();
  const [keyword, setKeyword] = useState("");
  const [results, setResults] = useState<ProductSearchItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const [addedIds, setAddedIds] = useState<Set<string>>(
    () => new Set(getRegisteredProducts().map((p) => p.id)),
  );

  async function handleSearch() {
    const term = keyword.trim();
    if (!term || loading) return;
    setLoading(true);
    setResults([]);
    setSearched(false);
    try {
      const res = await searchProducts(term);
      if (res.data.products.length === 0) {
        navigate("/onboarding/search-empty", { state: { keyword: term } });
        return;
      }
      setResults(res.data.products);
      setSearched(true);
    } catch {
      navigate("/onboarding/search-empty", { state: { keyword: term } });
    } finally {
      setLoading(false);
    }
  }

  function handleAdd(item: ProductSearchItem) {
    addRegisteredProduct({
      id: item.id,
      name: item.name,
      brand: item.brand,
      imageUrl: item.imageUrl,
    });
    setAddedIds((prev) => new Set(prev).add(item.id));
  }

  return (
    <AppLayout>
      <section className="flex min-h-screen flex-col px-6 pb-6 pt-10">
        <PageHeader title="제품 검색" onBack={() => navigate(-1)} />

        <div className="mt-5 flex gap-2">
          <input
            className="h-12 flex-1 rounded-xl border border-gray-200 px-4 text-body2 outline-none placeholder:text-gray-200 focus:border-primary-500"
            placeholder="브랜드명 또는 제품명을 입력하세요"
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
          />
          <button
            className="h-12 rounded-xl bg-primary-500 px-5 text-body2 text-white disabled:opacity-50"
            onClick={handleSearch}
            disabled={loading || !keyword.trim()}
            type="button"
          >
            {loading ? "..." : "검색"}
          </button>
        </div>

        {searched && results.length > 0 && (
          <div className="mt-4">
            <div className="mb-3 flex items-center justify-between">
              <p className="text-body2 text-gray-500">검색 결과 {results.length}개</p>
            </div>
            <div className="grid gap-3">
              {results.map((item) => (
                <div
                  key={item.id}
                  className="flex items-center gap-4 rounded-xl border border-gray-200 bg-white p-3"
                >
                  {item.imageUrl ? (
                    <img
                      src={item.imageUrl}
                      alt={item.name}
                      className="h-14 w-14 shrink-0 rounded-xl object-cover"
                    />
                  ) : (
                    <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-xl bg-primary-50">
                      <div className="h-9 w-9 rounded-md bg-primary-100" />
                    </div>
                  )}
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-body2 text-gray-500">{item.name}</p>
                    <p className="truncate text-caption text-gray-300">{item.brand}</p>
                    {item.originalPrice && (
                      <p className="text-caption text-gray-300">
                        {item.originalPrice.toLocaleString()}원
                      </p>
                    )}
                  </div>
                  <button
                    className={`h-8 rounded-xl px-4 text-caption ${
                      addedIds.has(item.id)
                        ? "bg-primary-100 text-primary-500"
                        : "bg-primary-500 text-white"
                    }`}
                    onClick={() => handleAdd(item)}
                    disabled={addedIds.has(item.id)}
                    type="button"
                  >
                    {addedIds.has(item.id) ? "추가됨 ✓" : "추가"}
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {!searched && !loading && (
          <p className="mt-10 text-center text-caption text-gray-300">
            검색어를 입력하고 검색 버튼을 눌러주세요
          </p>
        )}

        <button
          className="mt-auto h-14 w-full rounded-xl bg-primary-500 text-body1 font-semibold text-white"
          onClick={() => navigate("/onboarding/products")}
          type="button"
        >
          완료
        </button>
      </section>
    </AppLayout>
  );
}
