import { api } from "../lib/api";

/**
 * 키오스크(화담 CARE)가 읽은 환경으로 만든 추천.
 *
 * 앱의 다른 추천과 다른 점은 근거가 센서 측정값이라는 것이다. 그래서 응답이
 * 제품만 주지 않고 왜 골랐는지를 묶음(group)과 이유(reason)로 함께 준다.
 * 화면은 그것을 그대로 보여준다. 근거 없이 목록만 있으면 다른 추천과
 * 구분되지 않는다.
 *
 * BE(Spring)가 아니라 AI 서버로 직접 간다. /ai 접두사가 그 표시다.
 */
export interface CareRecoProduct {
  product_id: string;
  name: string;
  brand: string | null;
  image_url: string | null;
  price: number | null;
  /** 이 제품을 고른 이유 한 줄. 묶음 안에서도 제품마다 다르다. */
  reason: string;
}

export interface CareRecoGroup {
  key: string;
  title: string;
  /** 왜 이 묶음인지. 측정값이나 확인 결과가 그대로 들어온다. */
  note: string | null;
  items: CareRecoProduct[];
}

export interface CareRecoFull {
  generated_at: string;
  /** "침실 21.4℃ / 52% · 외출 자외선 0" */
  context: string | null;
  groups: CareRecoGroup[];
}

export const getCareRecommendations = (userId: string) =>
  api.get<CareRecoFull>(
    `/ai/api/care/recommendations/full?user_id=${encodeURIComponent(userId)}`,
  );
