import { api } from "../lib/api";

interface ApiResponse<T> {
  success: boolean;
  data: T;
}

export interface ProductDetail {
  productId: string;
  name: string;
  brand: string;
  category: string | null;
  imageUrl: string | null;
  originalPrice: number | null;
  lowestPrice: number | null;
  featureJson: unknown;
  reviewSummary: string | null;
  averageScore: number | null;
  reviewCount: number | null;
}

export const getProductDetail = (productId: string) =>
  api.get<ApiResponse<ProductDetail>>(`/products/${productId}`);

export interface RecognizeResult {
  productId: string;
  name: string;
  brand: string;
  imageUrl?: string | null;
}

export interface ProductSearchItem {
  id: string;
  name: string;
  brand: string;
  category: string;
  imageUrl?: string | null;
  originalPrice?: number | null;
}

export const recognizeProduct = (type: "IMAGE" | "TEXT" | "NFC", data: string) =>
  api.post<ApiResponse<RecognizeResult>>("/products/recognize", { type, data });

export const searchProducts = (keyword: string) =>
  api.get<ApiResponse<{ products: ProductSearchItem[] }>>(
    `/products/search?keyword=${encodeURIComponent(keyword)}`,
  );

export const recordProductView = (productId: string) =>
  api.post<ApiResponse<null>>(`/products/${productId}/view`);

export const getRecentlyViewed = (limit = 10) =>
  api.get<ApiResponse<{ products: ProductSearchItem[] }>>(
    `/products/recently-viewed?limit=${limit}`,
  );

// ── AI 자연어 검색 (FastAPI) ─────────────────────────────────────────────────

export interface AiSearchProduct {
  productId: string;
  name: string;
  brand: string;
  category: string;
  imageUrl?: string | null;
  originalPrice?: number | null;
  matchScore: number;
}

export interface AiSearchResponse {
  query: string;
  category: string;
  products: AiSearchProduct[];
}

export const aiSearch = (query: string): Promise<AiSearchResponse> =>
  fetch("/ai/search", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
  }).then((r) => {
    if (!r.ok) return r.json().then((e) => Promise.reject(e));
    return r.json() as Promise<AiSearchResponse>;
  });
