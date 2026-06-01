import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { completeOnboarding, saveOnboardingProducts } from "../../api/userApi";
import AppLayout from "../../layouts/AppLayout";
import { getRegisteredProducts } from "../../lib/onboardingProducts";

const KEY = "onboarding_products";

export function OnboardingCompletePage() {
  const navigate = useNavigate();
  const products = getRegisteredProducts();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleStart() {
    setLoading(true);
    setError(null);
    try {
      if (products.length > 0) {
        await saveOnboardingProducts(products.map((p) => p.id));
      }
      await completeOnboarding();
      localStorage.removeItem(KEY);
      navigate("/home");
    } catch {
      setError("저장 중 오류가 발생했어요. 다시 시도해주세요.");
      setLoading(false);
    }
  }

  return (
    <AppLayout>
      <section className="flex min-h-screen flex-col px-6 pb-28 pt-[120px]">
        <div className="text-center">
          <div className="mx-auto flex h-40 w-40 items-center justify-center rounded-full bg-primary-50">
            <div className="flex h-[116px] w-[116px] items-center justify-center rounded-full bg-primary-100">
              <div className="flex h-[72px] w-[72px] items-center justify-center rounded-full bg-primary-500 text-white">
                <svg
                  aria-hidden="true"
                  className="h-11 w-11"
                  fill="none"
                  viewBox="0 0 24 24"
                >
                  <path
                    d="m5 12 4 4L19 6"
                    stroke="currentColor"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2.5"
                  />
                </svg>
              </div>
            </div>
          </div>

          <h1 className="mt-6 text-h2 text-gray-500">준비 완료!</h1>
          <p className="mt-3 text-body2 text-gray-300">
            맞춤 설정이 완료됐어요
          </p>
        </div>

        <div className="mt-4 rounded-xl bg-primary-50 p-4">
          <p className="text-body2 text-primary-500">✦ 이제 뭘 하면 될까요?</p>
          <p className="mt-1 text-caption text-gray-500">
            홈에서 제품을 검색하거나 AI 추천을 받아보세요
          </p>
        </div>

        {error && (
          <p className="mt-3 text-center text-caption text-red-500">{error}</p>
        )}

        <button
          className="mt-4 h-14 w-full rounded-xl bg-primary-500 text-body1 font-semibold text-white disabled:opacity-50"
          onClick={handleStart}
          disabled={loading}
          type="button"
        >
          {loading ? "저장 중..." : "BeautyMatch 시작하기"}
        </button>

        <p className="mt-5 text-center text-caption text-gray-300">
          설정은 MY 페이지에서 언제든 바꿀 수 있어요
        </p>
      </section>
    </AppLayout>
  );
}
