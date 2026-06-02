import { api } from "../lib/api";

interface ApiResponse<T> {
  success: boolean;
  data: T;
}

// ── 응답 타입 (백엔드 실제 구조) ─────────────────────────────────────────

export interface ProductInfo {
  id: string;
  name: string;
  brand: string;
  imageUrl: string | null;
}

export interface AchievedItem {
  trackingId: string;
  product: ProductInfo;
  targetPrice: number;
  currentLowestPrice: number | null;
  lowestStoreUrl: string | null;
}

export interface TrackingItem {
  trackingId: string;
  product: ProductInfo;
  targetPrice: number;
  currentLowestPrice: number | null;
  historicalLowest: number | null;
}

export interface AlertSettings {
  targetPriceAlert: boolean;
  weeklyReport: boolean;
}

export interface PriceTrackingListData {
  summary: {
    totalTracking: number;
    monthlySavings: number;
  };
  achieved: AchievedItem[];
  tracking: TrackingItem[];
  alertSettings: AlertSettings;
}

// ── 요청 타입 ────────────────────────────────────────────────────────────

export interface PriceTrackingCreateResponse {
  trackingId: string;
  productId: string;
  targetPrice: number;
  alertEnabled: boolean;
  createdAt: string;
}

export interface PriceTrackingDetail {
  trackingId: string;
  product: {
    id: string;
    name: string;
    brand: string;
    imageUrl: string | null;
  };
  stats: {
    originalPrice: number | null;
    currentLowestPrice: number | null;
    historicalLowest: number | null;
    changePercent: number | null;
    changeAmount: number | null;
  };
  targetPrice: number;
  alertEnabled: boolean;
  period: string;
  priceHistory: { date: string; price: number }[];
  stores: {
    storeName: string;
    price: number;
    isLowest: boolean;
    purchaseUrl: string | null;
  }[];
}

// ── API 함수 ─────────────────────────────────────────────────────────────

export const getTrackings = () =>
  api.get<ApiResponse<PriceTrackingListData>>("/price-trackings");

export const addTracking = (productId: string, targetPrice: number, alertEnabled: boolean) =>
  api.post<ApiResponse<PriceTrackingCreateResponse>>("/price-trackings", {
    productId,
    targetPrice,
    alertEnabled,
  });

export const deleteTracking = (trackingId: string) =>
  api.delete<ApiResponse<unknown>>(`/price-trackings/${trackingId}`);

export const updateTracking = (
  trackingId: string,
  body: { targetPrice?: number; alertEnabled?: boolean },
) => api.patch<ApiResponse<unknown>>(`/price-trackings/${trackingId}`, body);

export const getPriceTrackingDetail = (trackingId: string, period: string) =>
  api.get<ApiResponse<PriceTrackingDetail>>(`/price-trackings/${trackingId}?period=${period}`);

export const updateAlertSettings = (targetPriceAlert: boolean, weeklyReport: boolean) =>
  api.patch<ApiResponse<unknown>>("/price-trackings/alert-settings", {
    targetPriceAlert,
    weeklyReport,
  });
