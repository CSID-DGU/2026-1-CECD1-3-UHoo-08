import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { type RecommendationResultResponse, requestRecommendation } from "../../api/recommendationApi";
import { PageHeader } from "../../components/common/PageHeader";
import AppLayout from "../../layouts/AppLayout";
import { recommendationPriceRanges } from "../../mocks/recommendations";

const USE_MOCK = import.meta.env.VITE_USE_MOCK === "true";

const MOCK_RECOMMENDATION_DATA: RecommendationResultResponse = {
  jobId: "mock-job-001",
  baseProduct: {
    id: "mock-base-001",
    name: "아쿠아 스쿠알란 수분크림",
    brand: "에스네이처",
    imageUrl: null,
  },
  matchScore: 94,
  matchLabel: "인생템 확률",
  aiReason:
    "수분 부족형 피부에 최적화된 스쿠알란 성분이 피부 장벽을 강화하고, 가벼운 텍스처로 데일리 사용에 이상적입니다. 유사 피부 타입 사용자 만족도 94% 달성.",
  mainRecommendations: [
    {
      id: "mock-main-001",
      name: "아쿠아 스쿠알란 수분크림",
      brand: "에스네이처",
      imageUrl: null,
      price: 18000,
      totalScore: 94,
      breakdown: { budgetFit: 95, priceValue: 92, reviewScore: 91, personalization: 96 },
    },
  ],
  similarUserProducts: [
    { id: "mock-sim-001", name: "시카페어 크림", brand: "닥터자르트", imageUrl: null, price: 35000, satisfactionPercent: 91 },
    { id: "mock-sim-002", name: "어성초 진정 크림", brand: "이니스프리", imageUrl: null, price: 14000, satisfactionPercent: 88 },
    { id: "mock-sim-003", name: "워터뱅크 수분크림", brand: "라네즈", imageUrl: null, price: 29000, satisfactionPercent: 89 },
  ],
  alternativeProducts: [
    { id: "mock-alt-001", name: "히알루론산 수분크림", brand: "더마토리", imageUrl: null, price: 22000, ingredientSimilarity: 89 },
    { id: "mock-alt-002", name: "세라마이드 모이스처라이징 크림", brand: "CeraVe", imageUrl: null, price: 19900, ingredientSimilarity: 85 },
    { id: "mock-alt-003", name: "마데카소사이드 크림", brand: "에이프릴스킨", imageUrl: null, price: 16000, ingredientSimilarity: 82 },
  ],
  createdAt: new Date().toISOString(),
};

interface ExtraInfoState {
  productId?: string;
  productName?: string;
  productBrand?: string;
  productImageUrl?: string | null;
}

export function ExtraInfoPage() {
  const navigate = useNavigate();
  const { state } = useLocation() as { state: ExtraInfoState | null };
  const productId = state?.productId;
  const productName = state?.productName;
  const productBrand = state?.productBrand;
  const productImageUrl = state?.productImageUrl;

  const [reason, setReason] = useState("데일리");
  const [priceRange, setPriceRange] = useState("balanced");
  const [loading, setLoading] = useState(false);

  async function handleSubmit() {
    if (!productId) return;
    setLoading(true);
    try {
      if (USE_MOCK) {
        navigate("/recommendation/loading", {
          state: { mock: true, mockData: MOCK_RECOMMENDATION_DATA },
        });
        return;
      }
      const res = await requestRecommendation(productId, reason, priceRange);
      navigate("/recommendation/loading", {
        state: { jobId: res.data.jobId },
      });
    } catch {
      alert("추천 요청에 실패했어요. 다시 시도해주세요.");
    } finally {
      setLoading(false);
    }
  }

  function handleSkip() {
    if (productId) {
      handleSubmit();
    } else {
      navigate("/recommendation/loading", { state: {} });
    }
  }

  return (
    <AppLayout>
      <div className="flex h-screen flex-col overflow-hidden">
        <div className="flex-1 overflow-y-auto scrollbar-none">
      <section className="flex flex-col px-6 pb-6 pt-10">
        <PageHeader
          title="추가 정보 입력"
          onBack={() => navigate(-1)}
          rightSlot={
            <button
              className="text-body2 text-primary-500"
              onClick={handleSkip}
              disabled={loading}
              type="button"
            >
              건너뛰기
            </button>
          }
        />

        {/* 대상 상품 컨텍스트 */}
        {productName && (
          <div className="mt-5 flex items-center gap-3 rounded-xl border border-primary-100 bg-primary-50 p-3">
            <div className="h-12 w-12 shrink-0 overflow-hidden rounded-xl bg-primary-100">
              {productImageUrl ? (
                <img src={productImageUrl} alt={productName} className="h-full w-full object-cover" />
              ) : (
                <div className="h-full w-full" />
              )}
            </div>
            <div className="min-w-0">
              <p className="text-caption text-primary-500">분석할 제품</p>
              <p className="truncate text-body2 text-gray-500">{productName}</p>
              {productBrand && <p className="text-caption text-gray-300">{productBrand}</p>}
            </div>
          </div>
        )}

        <div className="mt-5">
          <h1 className="text-h2 text-gray-500">
            더 정확한 추천을 위해
            <br />
            정보를 입력해주세요
          </h1>
          <p className="mt-2 text-body2 text-gray-300">모두 선택사항이에요</p>
        </div>

        <div className="my-6 h-px bg-gray-100" />

        <div className="flex items-center justify-between">
          <h2 className="text-body2 text-gray-500">가격 허용 폭</h2>
          <span className="text-caption text-gray-300">대체·유사 상품 추천에 반영돼요</span>
        </div>
        <div className="mt-3 rounded-lg bg-primary-50 px-4 py-2 text-caption text-primary-500">
          조회한 상품 가격 기준으로 자동 계산돼요
        </div>

        <div className="mt-6 grid grid-cols-5 gap-2">
          {recommendationPriceRanges.map((item) => {
            const selected = priceRange === item.id;
            return (
              <button
                className={`h-[84px] rounded-xl text-center ${
                  selected ? "bg-primary-500 text-white" : "bg-gray-100 text-gray-300"
                }`}
                key={item.id}
                onClick={() => setPriceRange(item.id)}
                type="button"
              >
                <span className="block text-h3">{item.title}</span>
                <span className="mt-1 block text-caption">{item.desc}</span>
                {selected && (
                  <span className="mt-2 inline-block rounded-full bg-primary-300 px-2 py-1 text-[10px] text-white">
                    선택됨 ✓
                  </span>
                )}
              </button>
            );
          })}
        </div>

        <div className="mt-16 border-l-4 border-primary-500 bg-primary-50 px-4 py-3">
          <p className="text-body2 text-primary-500">✦ AI Tip</p>
          <p className="mt-1 text-caption leading-5 text-gray-500">
            허용 폭이 넓을수록 더 다양한 대체 상품을 발견할 수 있어요.
          </p>
        </div>

        <button
          className="mt-auto h-14 w-full rounded-xl bg-primary-500 text-body1 font-semibold text-white disabled:opacity-50"
          disabled={loading || !productId}
          onClick={handleSubmit}
          type="button"
        >
          {loading ? "요청 중..." : "추천 받기 ✦"}
        </button>

        {!productId && (
          <p className="mt-2 text-center text-caption text-gray-300">
            제품 조회 후 추천을 받을 수 있어요
          </p>
        )}
      </section>
        </div>
      </div>
    </AppLayout>
  );
}
