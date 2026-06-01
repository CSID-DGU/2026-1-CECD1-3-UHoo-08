import { useLocation, useNavigate } from "react-router-dom";
import { type RecognizeResult } from "../../api/productApi";
import { PageHeader } from "../../components/common/PageHeader";
import AppLayout from "../../layouts/AppLayout";

export function ProductRecognizePage() {
  const navigate = useNavigate();
  const { state } = useLocation() as {
    state: { result: RecognizeResult } | null;
  };

  const result = state?.result;

  function handleConfirm() {
    if (!result?.productId) return;
    navigate("/recommendation/extra-info", {
      state: { productId: result.productId },
    });
  }

  return (
    <AppLayout>
      <section className="flex min-h-screen flex-col px-6 pb-8 pt-10">
        <PageHeader title="제품 확인" onBack={() => navigate(-1)} />

        <div className="mt-7">
          <h1 className="text-h2 text-gray-500">이 상품이 맞나요?</h1>
          <p className="mt-2 text-body2 text-gray-300">
            인식된 제품 정보를 확인해주세요
          </p>
        </div>

        {result ? (
          <div className="mt-6 overflow-hidden rounded-2xl border border-gray-200 bg-white">
            <div className="flex h-[180px] items-center justify-center bg-primary-50">
              {result.imageUrl ? (
                <img
                  src={result.imageUrl}
                  alt={result.name}
                  className="h-full w-full object-contain"
                />
              ) : (
                <span className="text-[48px]">💄</span>
              )}
            </div>
            <div className="p-5">
              <p className="text-caption text-gray-300">{result.brand}</p>
              <h2 className="mt-1 text-h3 text-gray-500">{result.name}</h2>
            </div>
          </div>
        ) : (
          <div className="mt-6 flex h-[260px] items-center justify-center rounded-2xl border border-gray-200 bg-gray-50">
            <p className="text-body2 text-gray-300">인식된 상품이 없어요</p>
          </div>
        )}

        <div className="mt-auto grid gap-3">
          <button
            className="h-14 w-full rounded-xl bg-primary-500 text-body1 font-semibold text-white disabled:opacity-50"
            disabled={!result?.productId}
            onClick={handleConfirm}
            type="button"
          >
            맞아요, 추천받기 →
          </button>
          <button
            className="h-12 w-full rounded-xl border border-gray-200 text-body2 text-gray-500"
            onClick={() => navigate(-1)}
            type="button"
          >
            다시 검색
          </button>
        </div>
      </section>
    </AppLayout>
  );
}
