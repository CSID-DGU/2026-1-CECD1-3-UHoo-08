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
  api.post<{ success: boolean; data: AiSearchResponse }>("/recommendations/search", { query })
    .then((res) => res.data);

// ── AI 제품 인식 (FastAPI /internal/recognize) ────────────────────────────────

export interface AiRecognizeResult {
  productId: string | null;
  name: string | null;
  brand: string | null;
  category: string | null;
  geminiPrice: Record<string, unknown>;
  reviewSummary: Record<string, unknown>;
  ingredients: string[];
}

export const aiRecognizeProduct = (
  type: "IMAGE" | "TEXT" | "NFC",
  data: string,
): Promise<AiRecognizeResult> =>
  api.post<AiRecognizeResult>("/ai/internal/recognize", { type, data });
