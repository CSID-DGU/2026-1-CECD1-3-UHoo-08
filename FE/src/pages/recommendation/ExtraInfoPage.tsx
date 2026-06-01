import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { requestRecommendation } from "../../api/recommendationApi";
import { PageHeader } from "../../components/common/PageHeader";
import AppLayout from "../../layouts/AppLayout";
import { recommendationPriceRanges, recommendationReasons } from "../../mocks/recommendations";

export function ExtraInfoPage() {
  const navigate = useNavigate();
  const { state } = useLocation() as { state: { productId?: string } | null };
  const productId = state?.productId;

  const [reason, setReason] = useState("데일리");
  const [priceRange, setPriceRange] = useState("balanced");
  const [loading, setLoading] = useState(false);

  async function handleSubmit() {
    if (!productId) return;
    setLoading(true);
    try {
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
      <section className="flex min-h-screen flex-col px-6 pb-6 pt-10">
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

        <div className="mt-7">
          <h1 className="text-h2 text-gray-500">
            더 정확한 추천을 위해
            <br />
            정보를 입력해주세요
          </h1>
          <p className="mt-2 text-body2 text-gray-300">모두 선택사항이에요</p>
        </div>

        <label className="mt-7 block">
          <span className="text-body2 text-gray-500">왜 찾으세요?</span>
          <input
            className="mt-2 h-[54px] w-full rounded-xl border border-gray-200 px-4 text-body2 outline-none placeholder:text-gray-300 focus:border-primary-500"
            placeholder="예: 데일리 루틴, 선물, 여행용..."
            type="text"
          />
        </label>

        <div className="mt-3 flex gap-2">
          {recommendationReasons.map((item) => (
            <button
              className={`h-9 rounded-full px-4 text-caption ${
                reason === item ? "bg-primary-500 text-white" : "bg-gray-100 text-gray-500"
              }`}
              key={item}
              onClick={() => setReason(item)}
              type="button"
            >
              {item}
            </button>
          ))}
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
    </AppLayout>
  );
}
