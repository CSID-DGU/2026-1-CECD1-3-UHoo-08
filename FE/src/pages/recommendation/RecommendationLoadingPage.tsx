import { useEffect, useRef } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { getRecommendationStatus } from "../../api/recommendationApi";
import AppLayout from "../../layouts/AppLayout";

export function RecommendationLoadingPage() {
  const navigate = useNavigate();
  const { state } = useLocation() as { state: { jobId?: string } | null };
  const jobId = state?.jobId;
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!jobId) return;

    timerRef.current = setInterval(async () => {
      try {
        const res = await getRecommendationStatus(jobId);
        const { status } = res.data;
        if (status === "COMPLETED") {
          clearInterval(timerRef.current!);
          navigate("/recommendation/result", { state: { jobId }, replace: true });
        } else if (status === "FAILED") {
          clearInterval(timerRef.current!);
          alert("추천 분석에 실패했어요. 다시 시도해주세요.");
          navigate(-1);
        }
      } catch {
        // 네트워크 오류 시 계속 폴링
      }
    }, 1000);

    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [jobId, navigate]);

  return (
    <AppLayout>
      <div className="flex h-screen flex-col overflow-hidden">
        <div className="flex-1 overflow-y-auto scrollbar-none">
      <section className="flex flex-col px-6 pb-10 pt-10">
        <p className="text-h4 text-gray-500">화담</p>

        <div className="mt-10 text-center">
          <LoadingOrb />
          <h1 className="mt-8 text-h2 text-gray-500">
            최적의 매칭을
            <br />
            찾는 중이에요
          </h1>
          <p className="mt-2 text-body2 text-gray-300">잠깐이면 충분해요</p>
        </div>

        <WaitNotice />

        <div className="mt-4 rounded-xl bg-primary-50 p-4">
          <p className="text-body2 text-primary-500">✦ 잠깐, 피부 팁!</p>
          <p className="mt-1 text-caption leading-5 text-gray-500">
            민감한 날엔 진정 성분 제품을 우선 추천해드려요
          </p>
        </div>

        <div className="mt-auto h-1.5 overflow-hidden rounded-full bg-gray-200">
          <div className="recommendation-progress h-full rounded-full bg-primary-500" />
        </div>
      </section>
        </div>
      </div>
    </AppLayout>
  );
}

function WaitNotice() {
  return (
    <section className="mt-6 rounded-2xl border border-primary-100 bg-primary-50 px-5 py-6 text-center">
      <h2 className="text-body1 text-gray-500">잠시만 기다려주세요</h2>
      <p className="mt-2 text-caption leading-5 text-gray-400">
        피부 정보와 제품 데이터를 바탕으로 맞춤 추천을 준비하고 있어요
      </p>
    </section>
  );
}

function LoadingOrb() {
  return (
    <div className="match-loader mx-auto" aria-label="AI 추천 분석 중">
      <div className="match-loader-glow" />
      <div className="match-loader-scene">
        <div className="match-card-stack">
          <div className="match-card card-back" />
          <div className="match-card card-mid" />
          <div className="match-card card-front">
            <span className="match-card-line line-1" />
            <span className="match-card-line line-2" />
            <span className="match-card-dot" />
          </div>
        </div>
      </div>
      <span className="pop-bubble pop-1" />
      <span className="pop-bubble pop-2" />
      <span className="pop-bubble pop-3" />
      <span className="pop-bubble pop-4" />
      <span className="pop-bubble pop-5" />
    </div>
  );
}
