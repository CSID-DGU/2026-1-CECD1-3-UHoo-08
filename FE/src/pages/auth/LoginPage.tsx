import Spline from "@splinetool/react-spline";

const KAKAO_AUTH_URL =
  `https://kauth.kakao.com/oauth/authorize` +
  `?client_id=${import.meta.env.VITE_KAKAO_CLIENT_ID}` +
  `&redirect_uri=${encodeURIComponent(import.meta.env.VITE_KAKAO_REDIRECT_URI)}` +
  `&response_type=code`;

const glassBtn: React.CSSProperties = {
  backdropFilter: "blur(16px)",
  WebkitBackdropFilter: "blur(16px)",
  border: "1px solid rgba(255,255,255,0.35)",
};

export function LoginPage() {
  return (
    <div className="min-h-screen bg-[#0d1b2a]">
      <div className="relative mx-auto min-h-screen w-full max-w-[430px] overflow-hidden">
        <Spline
          scene="https://prod.spline.design/10xOe1-aIf1GHnfd/scene.splinecode"
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            width: "100%",
            height: "calc(100% + 80px)",
            zIndex: 0,
            pointerEvents: "none",
          }}
        />

        <section className="relative z-10 flex min-h-screen flex-col">
          {/* 로고 */}
          <div className="px-6 pb-10 pt-24 text-center">
            <div
              className="mx-auto inline-block px-10 py-8"
              style={{
                background: "rgba(10,20,40,0.55)",
                backdropFilter: "blur(20px)",
                WebkitBackdropFilter: "blur(20px)",
                border: "1px solid rgba(255,255,255,0.18)",
                borderRadius: 28,
                boxShadow: "0 8px 32px rgba(0,0,0,0.3)",
              }}
            >
              <h1
                style={{
                  color: "#ffffff",
                  fontWeight: 700,
                  fontSize: 34,
                  margin: 0,
                  letterSpacing: "-0.03em",
                  textShadow: "0 2px 12px rgba(0,0,0,0.4)",
                }}
              >
                BeautyMatch
              </h1>
              <p
                style={{
                  color: "rgba(255,255,255,0.75)",
                  margin: "10px 0 0",
                  fontSize: 14,
                  letterSpacing: "-0.01em",
                }}
              >
                내 피부에 딱 맞는 뷰티 루틴
              </p>
            </div>
          </div>

          {/* 로그인 버튼 */}
          <div className="px-6">
            <p className="mb-4 text-caption" style={{ color: "rgba(255,255,255,0.55)" }}>
              소셜 계정으로 시작하기
            </p>

            <div className="grid gap-3">
              {/* 카카오 — 브랜드 색 유지 + 글래스 테두리 */}
              <button
                className="relative flex h-[54px] items-center justify-center rounded-xl text-body1 font-medium"
                style={{
                  ...glassBtn,
                  background: "rgba(254,229,0,0.88)",
                  color: "#3C1E1E",
                }}
                type="button"
                onClick={() => { window.location.href = KAKAO_AUTH_URL; }}
              >
                <span className="absolute left-5 h-5 w-5 rounded-full bg-[#3C1E1E]" />
                카카오로 계속하기
              </button>

              {/* Apple */}
              <button
                className="relative flex h-[54px] items-center justify-center rounded-xl text-body1 font-medium"
                style={{
                  ...glassBtn,
                  background: "rgba(255,255,255,0.12)",
                  color: "white",
                }}
                type="button"
              >
                <span className="absolute left-5 text-lg font-semibold leading-none" style={{ color: "white" }}>

                </span>
                Apple로 계속하기
              </button>

              {/* Google */}
              <button
                className="relative flex h-[54px] items-center justify-center rounded-xl text-body1 font-medium"
                style={{
                  ...glassBtn,
                  background: "rgba(255,255,255,0.12)",
                  color: "white",
                }}
                type="button"
              >
                <span className="absolute left-5 text-base font-bold" style={{ color: "white" }}>
                  G
                </span>
                Google로 계속하기
              </button>
            </div>
          </div>

          <div className="mt-auto px-6 pb-6">
            <p
              className="text-center text-caption"
              style={{ color: "rgba(255,255,255,0.4)" }}
            >
              로그인 시 이용약관 및 개인정보처리방침에 동의합니다
            </p>
          </div>
        </section>
      </div>
    </div>
  );
}
