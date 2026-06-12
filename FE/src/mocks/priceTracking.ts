import type { PriceTrackingDetail, PriceTrackingListData } from "../api/priceTrackingApi";

// ── 데모용 목업 데이터 ────────────────────────────────────────────────────

function makeDates(n: number): string[] {
  return Array.from({ length: n }, (_, i) => {
    const d = new Date("2026-06-12");
    d.setDate(d.getDate() - (n - 1 - i));
    return d.toISOString().substring(0, 10);
  });
}

const DATES_30 = makeDates(30);

export const MOCK_TRACKING_LIST: PriceTrackingListData = {
  summary: { totalTracking: 4, monthlySavings: 5600 },
  achieved: [
    {
      trackingId: "mock-track-001",
      product: { id: "mock-prod-001", name: "네오쿠션 21N1 크리미 포슬린", brand: "라네즈", imageUrl: null },
      targetPrice: 29000,
      currentLowestPrice: 28600,
      lowestStoreUrl: null,
    },
  ],
  tracking: [
    {
      trackingId: "mock-track-002",
      product: { id: "mock-prod-002", name: "노세범 파우더 팩트", brand: "이니스프리", imageUrl: null },
      targetPrice: 11000,
      currentLowestPrice: 12200,
      historicalLowest: 11500,
    },
    {
      trackingId: "mock-track-003",
      product: { id: "mock-prod-003", name: "아토베리어 365 크림", brand: "에스트라", imageUrl: null },
      targetPrice: 26000,
      currentLowestPrice: 28800,
      historicalLowest: 25000,
    },
    {
      trackingId: "mock-track-004",
      product: { id: "mock-prod-004", name: "다이브-인 로우 세럼", brand: "토리든", imageUrl: null },
      targetPrice: 17000,
      currentLowestPrice: 18500,
      historicalLowest: 17200,
    },
  ],
  alertSettings: { targetPriceAlert: true, weeklyReport: false },
};

const PRICES: Record<string, number[]> = {
  "mock-track-001": [38000,37500,37500,36800,36800,36000,35500,35500,34800,34200,33500,33500,32800,32000,31500,31500,30800,30200,30200,29800,29500,29200,29200,28900,28900,28600,28600,28600,28600,28600],
  "mock-track-002": [13000,13000,12800,12800,12600,12600,12800,12800,12500,12500,12300,12300,12500,12500,12300,12200,12200,12300,12400,12400,12200,12200,12300,12300,12200,12200,12100,12100,12200,12200],
  "mock-track-003": [32000,31500,31500,31000,30800,30500,30500,30200,30200,30000,30000,29800,29500,29500,29300,29300,29000,29000,28800,28800,29000,29200,29000,28800,28800,28800,29000,29000,28800,28800],
  "mock-track-004": [22000,21800,21500,21500,21200,21000,20800,20500,20500,20200,20000,19800,19800,19500,19500,19200,19000,19000,18800,18800,18500,18500,18800,18800,18500,18500,18800,18500,18500,18500],
};

const STORES: Record<string, PriceTrackingDetail["stores"]> = {
  "mock-track-001": [
    { storeName: "올리브영", price: 28600, isLowest: true, purchaseUrl: null },
    { storeName: "쿠팡", price: 29400, isLowest: false, purchaseUrl: null },
    { storeName: "네이버쇼핑", price: 30000, isLowest: false, purchaseUrl: null },
  ],
  "mock-track-002": [
    { storeName: "이니스프리몰", price: 12200, isLowest: true, purchaseUrl: null },
    { storeName: "올리브영", price: 12500, isLowest: false, purchaseUrl: null },
    { storeName: "쿠팡", price: 12800, isLowest: false, purchaseUrl: null },
  ],
  "mock-track-003": [
    { storeName: "올리브영", price: 28800, isLowest: true, purchaseUrl: null },
    { storeName: "쿠팡", price: 29500, isLowest: false, purchaseUrl: null },
    { storeName: "GS샵", price: 30200, isLowest: false, purchaseUrl: null },
  ],
  "mock-track-004": [
    { storeName: "쿠팡", price: 18500, isLowest: true, purchaseUrl: null },
    { storeName: "올리브영", price: 19200, isLowest: false, purchaseUrl: null },
    { storeName: "네이버쇼핑", price: 19800, isLowest: false, purchaseUrl: null },
  ],
};

const ORIGINALS: Record<string, number> = {
  "mock-track-001": 38000,
  "mock-track-002": 13000,
  "mock-track-003": 32000,
  "mock-track-004": 22000,
};

const PRODUCTS: Record<string, { id: string; name: string; brand: string }> = {
  "mock-track-001": { id: "mock-prod-001", name: "네오쿠션 21N1 크리미 포슬린", brand: "라네즈" },
  "mock-track-002": { id: "mock-prod-002", name: "노세범 파우더 팩트", brand: "이니스프리" },
  "mock-track-003": { id: "mock-prod-003", name: "아토베리어 365 크림", brand: "에스트라" },
  "mock-track-004": { id: "mock-prod-004", name: "다이브-인 로우 세럼", brand: "토리든" },
};

const TARGET_PRICES: Record<string, number> = {
  "mock-track-001": 29000,
  "mock-track-002": 11000,
  "mock-track-003": 26000,
  "mock-track-004": 17000,
};

function buildDetail(trackingId: string): PriceTrackingDetail {
  const prices = PRICES[trackingId];
  const current = prices[prices.length - 1];
  const first = prices[0];
  const changePercent = Math.round(((current - first) / first) * 100);
  return {
    trackingId,
    product: { ...PRODUCTS[trackingId], imageUrl: null },
    stats: {
      originalPrice: ORIGINALS[trackingId],
      currentLowestPrice: current,
      historicalLowest: Math.min(...prices),
      changePercent,
      changeAmount: current - first,
    },
    targetPrice: TARGET_PRICES[trackingId],
    alertEnabled: true,
    period: "DAILY",
    priceHistory: DATES_30.map((date, i) => ({ date, price: prices[i] })),
    stores: STORES[trackingId],
  };
}

export const MOCK_TRACKING_DETAILS: Record<string, PriceTrackingDetail> = {
  "mock-track-001": buildDetail("mock-track-001"),
  "mock-track-002": buildDetail("mock-track-002"),
  "mock-track-003": buildDetail("mock-track-003"),
  "mock-track-004": buildDetail("mock-track-004"),
};

export const MOCK_TRACKING_DETAIL_DEFAULT = MOCK_TRACKING_DETAILS["mock-track-002"];
