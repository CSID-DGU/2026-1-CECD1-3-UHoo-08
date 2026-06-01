import type { AiSearchProduct } from "../api/productApi";

const SEARCH_HISTORY_KEY = "bm_last_search";
const MAX_RECENTLY_VIEWED = 10;

// ── 마지막 AI 검색 결과 캐시 ──────────────────────────────────────────────────

export interface LastSearch {
  query: string;
  category: string;
  products: AiSearchProduct[];  // 상위 5개만 저장
  searchedAt: string;
}

export function saveLastSearch(data: Omit<LastSearch, "searchedAt">) {
  const entry: LastSearch = {
    ...data,
    products: data.products.slice(0, 5),
    searchedAt: new Date().toISOString(),
  };
  localStorage.setItem(SEARCH_HISTORY_KEY, JSON.stringify(entry));
}

export function getLastSearch(): LastSearch | null {
  try {
    const raw = localStorage.getItem(SEARCH_HISTORY_KEY);
    return raw ? (JSON.parse(raw) as LastSearch) : null;
  } catch {
    return null;
  }
}

// ── 최근 본 상품 (클라이언트 사이드 보조 캐시) ────────────────────────────────
// BE의 recently-viewed API가 기준이지만, 오프라인/빠른 렌더링용으로도 사용

export interface ViewedProduct {
  productId: string;
  name: string;
  brand: string;
  imageUrl?: string | null;
  viewedAt: string;
}

export function saveViewedProduct(product: Omit<ViewedProduct, "viewedAt">) {
  const list = getViewedProducts().filter((p) => p.productId !== product.productId);
  const entry: ViewedProduct = { ...product, viewedAt: new Date().toISOString() };
  const updated = [entry, ...list].slice(0, MAX_RECENTLY_VIEWED);
  localStorage.setItem("bm_recently_viewed", JSON.stringify(updated));
}

export function getViewedProducts(): ViewedProduct[] {
  try {
    const raw = localStorage.getItem("bm_recently_viewed");
    return raw ? (JSON.parse(raw) as ViewedProduct[]) : [];
  } catch {
    return [];
  }
}
