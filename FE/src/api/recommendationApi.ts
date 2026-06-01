import { api } from "../lib/api";

interface ApiResponse<T> {
  success: boolean;
  data: T;
}

export interface RecommendationJobResponse {
  jobId: string;
}

export interface RecommendationStatusResponse {
  jobId: string;
  status: string;
  step: string | null;
  progress: number | null;
}

export interface MainRecommendation {
  id: string;
  name: string;
  brand: string;
  imageUrl: string | null;
  price: number | null;
  totalScore: number | null;
  breakdown: {
    budgetFit: number | null;
    priceValue: number | null;
    reviewScore: number | null;
    personalization: number | null;
  } | null;
}

export interface SimilarProduct {
  id: string;
  name: string;
  brand: string;
  imageUrl: string | null;
  price: number | null;
  satisfactionPercent: number | null;
}

export interface AlternativeProduct {
  id: string;
  name: string;
  brand: string;
  imageUrl: string | null;
  price: number | null;
  ingredientSimilarity: number | null;
}

export interface RecommendationResultResponse {
  jobId: string;
  baseProduct: {
    id: string;
    name: string;
    brand: string;
    imageUrl: string | null;
  };
  matchScore: number | null;
  matchLabel: string | null;
  aiReason: string | null;
  mainRecommendations: MainRecommendation[];
  similarUserProducts: SimilarProduct[];
  alternativeProducts: AlternativeProduct[];
  createdAt: string;
}

const PURPOSE_MAP: Record<string, string> = {
  데일리: "DAILY",
  선물용: "GIFT",
  여행용: "TRAVEL",
  특별일: "SPECIAL",
};

const PRICE_TOLERANCE_MAP: Record<string, number | null> = {
  same: 0,
  flex: 5,
  balanced: 10,
  wide: 20,
  any: null,
};

export const requestRecommendation = (
  baseProductId: string,
  reason: string,
  priceRangeId: string,
) =>
  api.post<ApiResponse<RecommendationJobResponse>>("/recommendations", {
    baseProductId,
    searchPurpose: PURPOSE_MAP[reason] ?? null,
    priceTolerancePercent: PRICE_TOLERANCE_MAP[priceRangeId] ?? null,
  });

export const getRecommendationStatus = (jobId: string) =>
  api.get<ApiResponse<RecommendationStatusResponse>>(
    `/recommendations/${jobId}/status`,
  );

export const getRecommendationResult = (jobId: string) =>
  api.get<ApiResponse<RecommendationResultResponse>>(`/recommendations/${jobId}`);
