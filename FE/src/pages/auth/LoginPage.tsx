
import AppLayout from "../../layouts/AppLayout";

const KAKAO_AUTH_URL =
  `https://kauth.kakao.com/oauth/authorize` +
  `?client_id=${import.meta.env.VITE_KAKAO_CLIENT_ID}` +
  `&redirect_uri=${encodeURIComponent(import.meta.env.VITE_KAKAO_REDIRECT_URI)}` +
  `&response_type=code`;

export function LoginPage() {

  return (
    <AppLayout>
      <section className="flex min-h-screen flex-col bg-white">
        <div className="bg-primary-50 px-6 pb-14 pt-24 text-center">
          <div className="mx-auto h-[104px] w-[104px] rounded-full bg-primary-500" />
          <h1 className="mt-5 text-h1 text-gray-500">BeautyMatch</h1>
          <p className="text-body2 text-gray-400">내 피부에 딱 맞는 뷰티 루틴</p>
        </div>

        <div className="-mt-3 px-6">
          <p className="mb-3 text-caption text-gray-300">소셜 계정으로 시작하기</p>

          <div className="grid gap-3">
            <button
              className="relative h-[54px] rounded-xl bg-[#FEE500] text-body1 text-gray-500"
              type="button"
              onClick={() => { window.location.href = KAKAO_AUTH_URL; }}
            >
              <span className="absolute left-6 top-1/2 h-5 w-5 -translate-y-1/2 rounded-full bg-[#3C1E1E]" />
              카카오로 계속하기
            </button>
            <button
              className="h-[54px] rounded-xl bg-gray-500 text-body1 text-white"
              type="button"
            >
              Apple로 계속하기
            </button>
            <button
              className="h-[54px] rounded-xl border border-gray-200 bg-white text-body1 text-gray-500"
              type="button"
            >
              Google로 계속하기
            </button>
          </div>
        </div>

        <div className="mt-auto px-6 pb-5">
          <p className="mt-3 text-center text-caption text-gray-200">
            로그인 시 이용약관 및 개인정보처리방침에 동의합니다
          </p>
        </div>
      </section>
    </AppLayout>
  );
}
