import Spline from "@splinetool/react-spline";
import type { CSSProperties } from "react";

import appleIcon from "../../assets/Apple.png";
import googleIcon from "../../assets/Google.png";
import kakaoIcon from "../../assets/Kakao.png";

const KAKAO_AUTH_URL =
  `https://kauth.kakao.com/oauth/authorize` +
  `?client_id=${import.meta.env.VITE_KAKAO_CLIENT_ID}` +
  `&redirect_uri=${encodeURIComponent(import.meta.env.VITE_KAKAO_REDIRECT_URI)}` +
  `&response_type=code`;

const COPY = {
  tagline: "나에게 맞는 뷰티 루틴",
  socialStart: "소셜 계정으로 시작하기",
  kakao: "카카오로 계속하기",
  apple: "Apple으로 계속하기",
  google: "Google으로 계속하기",
  terms: "로그인 시 이용약관 및 개인정보처리방침에 동의합니다",
};

const glassBtn: CSSProperties = {
  backdropFilter: "blur(16px)",
  WebkitBackdropFilter: "blur(16px)",
  border: "1px solid rgba(255,255,255,0.35)",
};

const socialButtons = [
  {
    label: COPY.kakao,
    icon: kakaoIcon,
    background: "rgba(254,229,0,0.88)",
    onClick: () => {
      window.location.href = KAKAO_AUTH_URL;
    },
  },
  {
    label: COPY.apple,
    icon: appleIcon,
    background: "rgba(255,255,255,0.86)",
  },
  {
    label: COPY.google,
    icon: googleIcon,
    background: "rgba(255,255,255,0.86)",
  },
];

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
          <div className="px-6 pb-10 pt-24 text-center">
            <div
              className="mx-auto inline-block px-10 py-8"
              style={{
                background: "rgba(10,20,40,0.55)",
                backdropFilter: "blur(20px)",
                WebkitBackdropFilter: "blur(20px)",
                border: "1px solid rgba(255,255,255,0.18)",
                borderRadius: 28,
              }}
            >
              <h1
                style={{
                  color: "#ffffff",
                  fontWeight: 700,
                  fontSize: 34,
                  margin: 0,
                }}
              >
                화담
              </h1>
              <p
                style={{
                  color: "rgba(255,255,255,0.75)",
                  margin: "10px 0 0",
                  fontSize: 14,
                }}
              >
                {COPY.tagline}
              </p>
            </div>
          </div>

          <div className="px-6">
            <p className="mb-4 text-caption">{COPY.socialStart}</p>

            <div className="grid gap-3">
              {socialButtons.map(({ label, icon, background, onClick }) => (
                <button
                  className="relative flex h-[54px] items-center justify-center rounded-xl text-black"
                  key={label}
                  style={{ ...glassBtn, background }}
                  type="button"
                  onClick={onClick}
                >
                  <img
                    alt=""
                    aria-hidden="true"
                    className="absolute left-5 h-5 w-5 object-contain"
                    src={icon}
                  />
                  {label}
                </button>
              ))}
            </div>
          </div>

          <div className="mt-auto px-6 pb-6">
            <p className="text-center text-caption">{COPY.terms}</p>
          </div>
        </section>
      </div>
    </div>
  );
}
