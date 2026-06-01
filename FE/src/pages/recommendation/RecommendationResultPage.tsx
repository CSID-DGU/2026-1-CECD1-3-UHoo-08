import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import {
  type RecommendationResultResponse,
  getRecommendationResult,
} from "../../api/recommendationApi";
import { PageHeader } from "../../components/common/PageHeader";
import AppLayout from "../../layouts/AppLayout";

function fmt(n: number | null | undefined) {
  if (n == null) return "—";
  return n.toLocaleString("ko-KR") + "원";
}

function ProductImage({ url, alt }: { url: string | null; alt: string }) {
  return (
    <div className="flex h-full w-full items-center justify-center overflow-hidden rounded-xl bg-primary-50">
      {url ? (
        <img src={url} alt={alt} className="h-full w-full object-contain" />
      ) : (
        <span className="text-3xl">💄</span>
      )}
    </div>
  );
}

export function RecommendationResultPage() {
  const navigate = useNavigate();
  const { state } = useLocation() as { state: { jobId?: string } | null };
  const jobId = state?.jobId;
  const [result, setResult] = useState<RecommendationResultResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!jobId) {
      setLoading(false);
      return;
    }
    getRecommendationResult(jobId)
      .then((res) => setResult(res.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [jobId]);

  if (loading) {
    return (
      <AppLayout>
        <section className="flex min-h-screen items-center justify-center">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary-200 border-t-primary-500" />
        </section>
      </AppLayout>
    );
  }

  const main = result?.mainRecommendations?.[0];

  return (
    <AppLayout>
      <section className="min-h-screen overflow-hidden px-6 pb-6 pt-10">
        <PageHeader title="추천 결과 보고서" onBack={() => navigate(-1)} />

        {/* 매칭 점수 카드 */}
        <section className="relative mt-5 overflow-hidden rounded-2xl bg-gray-500 p-7 text-white">
          <div>
            <p className="text-body2 text-primary-300">AI 매칭 완료</p>
            <p className="mt-1 text-[42px] font-bold leading-none">
              {result?.matchScore ?? "—"}
              {result?.matchScore != null && <span className="text-body1"> 점</span>}
            </p>
            <p className="mt-3 text-body2 text-primary-300">
              {result?.matchLabel ?? "인생템 확률 매칭"}
            </p>
          </div>
          <span className="absolute right-12 top-5 h-[92px] w-[92px] rounded-full bg-gray-400" />
          <span className="absolute right-7 top-16 h-[66px] w-[66px] rounded-full bg-primary-700" />
          <span className="absolute right-[78px] top-[70px] text-h1 text-white">✦</span>
        </section>

        {/* AI 추천 이유 */}
        {result?.aiReason && (
          <section className="mt-4 rounded-xl border border-primary-100 bg-primary-50 p-4">
            <p className="text-body2 text-primary-500">✦ AI가 분석한 추천 이유</p>
            <p className="mt-2 text-caption leading-6 text-gray-500">{result.aiReason}</p>
          </section>
        )}

        {/* 메인 추천 */}
        {main && (
          <section className="mt-4">
            <h2 className="text-body1 text-gray-500">추천 상품</h2>
            <div className="mt-3 flex items-center gap-4 rounded-xl border border-primary-300 bg-white p-4">
              <div className="h-[70px] w-[70px] shrink-0">
                <ProductImage url={main.imageUrl} alt={main.name} />
              </div>
              <div className="flex-1">
                <p className="text-caption text-gray-300">{main.brand}</p>
                <p className="text-body2 text-gray-500">{main.name}</p>
                <p className="mt-1 text-body1 text-primary-500">{fmt(main.price)}</p>
              </div>
              {main.totalScore != null && (
                <div className="text-right">
                  <p className="text-h3 text-primary-500">{main.totalScore}점</p>
                  <p className="text-caption text-gray-300">매칭</p>
                </div>
              )}
            </div>
          </section>
        )}

        {/* 나와 비슷한 사람들 */}
        {result?.similarUserProducts && result.similarUserProducts.length > 0 && (
          <section className="mt-4">
            <h2 className="text-body1 text-gray-500">나와 비슷한 사람들은?</h2>
            <p className="text-caption text-gray-300">비슷한 피부 타입의 실제 만족 제품</p>
            <div className="mt-3 flex gap-3 overflow-x-auto pb-2">
              {result.similarUserProducts.map((p) => (
                <article
                  className="min-w-[154px] cursor-pointer rounded-2xl border border-gray-200 bg-white p-3 text-center"
                  key={p.id}
                  onClick={() => navigate(`/product/${p.id}`)}
                >
                  <div className="h-[94px] overflow-hidden rounded-lg">
                    <ProductImage url={p.imageUrl} alt={p.name} />
                  </div>
                  <p className="mt-3 truncate text-body2 text-gray-500">{p.name}</p>
                  <p className="truncate text-caption text-gray-300">{p.brand}</p>
                  {p.satisfactionPercent != null && (
                    <p className="mt-1 text-caption text-primary-500">
                      만족도 {p.satisfactionPercent}%
                    </p>
                  )}
                  <p className="mt-1 text-caption text-gray-400">{fmt(p.price)}</p>
                </article>
              ))}
            </div>
          </section>
        )}

        {/* 대체 상품 */}
        {result?.alternativeProducts && result.alternativeProducts.length > 0 && (
          <section className="mt-4">
            <h2 className="text-body1 text-gray-500">유사한 대체 상품</h2>
            <div className="mt-3 grid gap-3">
              {result.alternativeProducts.map((p) => (
                <div
                  className="flex cursor-pointer items-center gap-4 rounded-xl border border-gray-200 bg-white p-4"
                  key={p.id}
                  onClick={() => navigate(`/product/${p.id}`)}
                >
                  <div className="h-[60px] w-[60px] shrink-0">
                    <ProductImage url={p.imageUrl} alt={p.name} />
                  </div>
                  <div className="flex-1">
                    <p className="text-body2 text-gray-500">{p.name}</p>
                    <p className="text-caption text-primary-500">
                      성분 유사도 {p.ingredientSimilarity != null ? `${p.ingredientSimilarity}%` : "—"} · {p.brand}
                    </p>
                    <p className="mt-1 text-body1 text-gray-500">{fmt(p.price)}</p>
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}

        <div className="mt-14 grid grid-cols-2 gap-3">
          <button
            className="h-[52px] rounded-xl border border-primary-100 bg-primary-50 text-body1 text-primary-500"
            type="button"
          >
            결과 저장
          </button>
          <button
            className="h-[52px] rounded-xl border border-primary-100 bg-primary-50 text-body1 text-primary-500"
            type="button"
          >
            공유하기
          </button>
        </div>

        <button
          className="mt-4 h-14 w-full rounded-xl bg-primary-500 text-body1 font-semibold text-white"
          onClick={() => navigate("/home")}
          type="button"
        >
          홈으로 돌아가기
        </button>
      </section>
    </AppLayout>
  );
}
