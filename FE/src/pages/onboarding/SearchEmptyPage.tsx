import { useLocation, useNavigate } from "react-router-dom";
import { PageHeader } from "../../components/common/PageHeader";
import AppLayout from "../../layouts/AppLayout";

export function SearchEmptyPage() {
  const navigate = useNavigate();
  const { state } = useLocation();
  const keyword: string = (state as { keyword?: string } | null)?.keyword ?? "";

  return (
    <AppLayout>
      <section className="flex min-h-screen flex-col px-6 pb-6 pt-10">
        <PageHeader title="검색 결과" onBack={() => navigate(-1)} />

        <div className="mt-10 text-center">
          <div className="mx-auto flex h-40 w-40 items-center justify-center rounded-full bg-gray-100">
            <div className="relative flex h-[90px] w-[90px] items-center justify-center rounded-full bg-gray-200">
              <span className="text-h1 text-gray-300">×</span>
              <span className="absolute bottom-5 right-4 h-9 w-2 rotate-[-45deg] rounded-full bg-gray-300" />
            </div>
          </div>
          <h2 className="mt-6 text-h3 text-gray-500">검색 결과가 없어요</h2>
          <p className="mt-2 text-body2 text-gray-300">
            {keyword ? (
              <>
                "{keyword}"을<br />
              </>
            ) : null}
            찾을 수 없었어요
          </p>
        </div>

        <div className="mt-10 rounded-xl border border-gray-200 bg-white p-4">
          <p className="text-body2 text-gray-500">이렇게 시도해보세요</p>
          <div className="my-3 h-px bg-gray-100" />
          <ul className="grid gap-2 text-caption text-gray-400">
            <li>● 검색어를 더 짧게 입력해보세요</li>
            <li>● 브랜드명만 입력해보세요 (예: 아이오페)</li>
            <li>● 사진으로 직접 등록해보세요</li>
          </ul>
          <button
            className="mt-2 text-caption text-primary-500"
            onClick={() => navigate("/onboarding/photo")}
            type="button"
          >
            사진으로 등록하기 →
          </button>
        </div>

        <button
          className="mt-auto h-[52px] w-full rounded-xl bg-gray-100 text-body1 text-gray-500"
          onClick={() => navigate("/onboarding/products")}
          type="button"
        >
          돌아가기
        </button>
      </section>
    </AppLayout>
  );
}
