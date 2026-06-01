import { useState } from "react";
import { useNavigate } from "react-router-dom";
import AppLayout from "../../layouts/AppLayout";
import {
  getRegisteredProducts,
  removeRegisteredProduct,
} from "../../lib/onboardingProducts";

export function KnownProductSetupPage() {
  const navigate = useNavigate();
  const [products, setProducts] = useState(getRegisteredProducts);

  function handleRemove(id: string) {
    setProducts(removeRegisteredProduct(id));
  }

  const count = products.length;
  const progressPct = Math.min((count / 5) * 100, 100);

  return (
    <AppLayout>
      <section className="flex min-h-screen flex-col px-6 pb-6 pt-10">
        <div>
          <div className="mb-3 h-[3px] rounded-full bg-primary-500" />
          <div className="mb-2 flex items-center justify-between text-caption">
            <span className="text-gray-300">2 / 2 단계</span>
            <span className="text-primary-500">완료 직전!</span>
          </div>

          <h1 className="text-h2 text-gray-500">
            자주 사용하는 제품을
            <br />
            알려주세요!
          </h1>
          <p className="mt-2 text-body2 text-gray-300">
            등록할수록 추천 정확도가 올라가요
          </p>

          <div className="mt-6 grid grid-cols-2 gap-4">
            <button
              className="h-[120px] rounded-2xl border border-primary-100 bg-primary-50 text-center"
              onClick={() => navigate("/onboarding/photo")}
              type="button"
            >
              <span className="mx-auto mb-3 flex h-11 w-11 items-center justify-center rounded-full bg-primary-500 text-white">
                <span className="h-5 w-3 rounded-full bg-white" />
              </span>
              <span className="block text-body2 text-primary-500">사진으로 등록</span>
              <span className="block text-caption text-primary-500">AI 자동 인식</span>
            </button>

            <button
              className="h-[120px] rounded-2xl bg-gray-100 text-center"
              onClick={() => navigate("/onboarding/product-search")}
              type="button"
            >
              <span className="mx-auto mb-3 flex h-11 w-11 items-center justify-center rounded-full bg-gray-200">
                <span className="h-4 w-5 rounded-sm border-2 border-gray-300" />
              </span>
              <span className="block text-body2 text-gray-400">텍스트 검색</span>
              <span className="block text-caption text-gray-300">직접 입력</span>
            </button>
          </div>

          {count > 0 && (
            <>
              <p className="mt-4 text-body2 text-gray-500">등록된 제품 {count}개</p>
              <div className="mt-3 grid gap-3">
                {products.map((product) => (
                  <div
                    className="flex items-center gap-3 rounded-xl border border-gray-200 bg-white p-3"
                    key={product.id}
                  >
                    {product.imageUrl ? (
                      <img
                        src={product.imageUrl}
                        alt={product.name}
                        className="h-11 w-11 rounded-lg object-cover"
                      />
                    ) : (
                      <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-primary-50">
                        <div className="h-8 w-8 rounded-md bg-primary-100" />
                      </div>
                    )}
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-body2 text-gray-500">{product.name}</p>
                      <p className="text-caption text-gray-300">{product.brand}</p>
                    </div>
                    <button
                      className="h-9 w-9 rounded-lg bg-gray-100 text-gray-300"
                      onClick={() => handleRemove(product.id)}
                      type="button"
                      aria-label={`${product.name} 삭제`}
                    >
                      ×
                    </button>
                  </div>
                ))}
              </div>
            </>
          )}

          <button
            className="mt-3 h-[58px] w-full rounded-xl border border-dashed border-gray-200 bg-gray-100 text-h3 text-primary-500"
            onClick={() => navigate("/onboarding/product-search")}
            type="button"
          >
            +
          </button>

          <div className="mt-6 rounded-xl bg-primary-50 p-4">
            <p className="text-body2 text-primary-500">
              지금까지 등록한 제품: {count}개
            </p>
            <p className="mt-1 text-caption text-gray-400">
              5개 이상 등록하면 추천 정확도가 크게 높아져요
            </p>
            <div className="mt-3 h-2 rounded-full bg-primary-100">
              <div
                className="h-full rounded-full bg-primary-500 transition-all duration-300"
                style={{ width: `${progressPct}%` }}
              />
            </div>
          </div>
        </div>

        <p className="mt-auto text-center text-caption text-gray-300">
          나중에 My 페이지에서 추가할 수 있어요!
        </p>
        <button
          className="mt-5 h-14 w-full rounded-xl bg-primary-500 text-body1 font-semibold text-white"
          onClick={() => navigate("/onboarding/complete")}
          type="button"
        >
          다음으로 →
        </button>
      </section>
    </AppLayout>
  );
}
