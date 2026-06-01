export const recommendationReasons = ["데일리", "선물용", "여행용", "특별일"];

export const recommendationPriceRanges = [
  { id: "same", title: "±0", desc: "딱 맞게" },
  { id: "flex", title: "±5%", desc: "조금 유연" },
  { id: "balanced", title: "±10%", desc: "적당히" },
  { id: "wide", title: "±20%", desc: "넉넉하게" },
  { id: "any", title: "∞", desc: "상관 없음" },
];

export const agentTools = [
  {
    name: "VLM",
    action: "제품 이미지 인식",
    detail: "브랜드, 제품명, 카테고리 추출",
    call: "call_input_agent()",
  },
  {
    name: "Score",
    action: "매칭 점수 계산",
    detail: "피부 타입과 성분 적합도 비교",
    call: "call_score_agent()",
  },
  {
    name: "Alternative",
    action: "대체상품 탐색",
    detail: "가격대와 유사 성분 후보 검색",
    call: "call_alternative_agent()",
  },
  {
    name: "Report",
    action: "추천 리포트 생성",
    detail: "추천 이유와 구매 후보 정리",
    call: "final_answer",
  },
];

export const similarRecommendationProducts = [
  { name: "네오쿠션 매트", brand: "라네즈 · 만족도 96%", price: "28,000원", green: true },
  { name: "노세범 파우더", brand: "이니스프리 · 리오더 1위", price: "8,000원" },
  { name: "시카 톤업", brand: "닥터지 · 진정", price: "18,000원", green: true },
];
