import type { AiSearchProduct } from "../api/productApi";

interface MockSearchResult {
  products: AiSearchProduct[];
  category: string;
}

const CUSHION_RESULTS: AiSearchProduct[] = [
  { productId: "mock-cushion-001", name: "에어핏 쿠션 SPF50+", brand: "에스네이처", category: "base", imageUrl: null, originalPrice: 19000, matchScore: 96 },
  { productId: "mock-cushion-002", name: "네오쿠션 21N1 크리미 포슬린", brand: "라네즈", category: "base", imageUrl: null, originalPrice: 38000, matchScore: 92 },
  { productId: "mock-cushion-003", name: "노세범 파우더 쿠션", brand: "이니스프리", category: "base", imageUrl: null, originalPrice: 20000, matchScore: 89 },
  { productId: "mock-cushion-004", name: "UV 미스트 쿠션 블랙 에디션", brand: "헤라", category: "base", imageUrl: null, originalPrice: 45000, matchScore: 87 },
  { productId: "mock-cushion-005", name: "킬 커버 에어핏 쿠션", brand: "클리오", category: "base", imageUrl: null, originalPrice: 22000, matchScore: 84 },
  { productId: "mock-cushion-006", name: "M 매직 쿠션 커버", brand: "미샤", category: "base", imageUrl: null, originalPrice: 14000, matchScore: 81 },
];

const SNATURE_RESULTS: AiSearchProduct[] = [
  { productId: "mock-snature-001", name: "아쿠아 스쿠알란 수분크림", brand: "에스네이처", category: "skincare", imageUrl: null, originalPrice: 18000, matchScore: 98 },
  { productId: "mock-snature-002", name: "그린티 수분크림", brand: "에스네이처", category: "skincare", imageUrl: null, originalPrice: 15000, matchScore: 85 },
  { productId: "mock-snature-003", name: "히알루론산 앰플", brand: "에스네이처", category: "skincare", imageUrl: null, originalPrice: 22000, matchScore: 72 },
  { productId: "mock-snature-004", name: "다이브-인 로우 세럼", brand: "토리든", category: "skincare", imageUrl: null, originalPrice: 19000, matchScore: 68 },
  { productId: "mock-snature-005", name: "시카페어 크림", brand: "닥터자르트", category: "skincare", imageUrl: null, originalPrice: 35000, matchScore: 65 },
];

export function getMockSearchResult(query: string): MockSearchResult | null {
  const q = query.toLowerCase().trim();
  if (q.includes("쿠션")) {
    return { products: CUSHION_RESULTS, category: "base" };
  }
  if (q.includes("에스네이처") || q.includes("s'nature") || q.includes("수분크림")) {
    return { products: SNATURE_RESULTS, category: "skincare" };
  }
  return null;
}
