import Spline from "@splinetool/react-spline";
import appleIcon from "../../assets/Apple.png";
import googleIcon from "../../assets/Google.png";
import kakaoIcon from "../../assets/Kakao.png";
import HwadamLogo from "../../assets/Hwadam.svg";

const KAKAO_AUTH_URL =
  `https://kauth.kakao.com/oauth/authorize` +
  `?client_id=${import.meta.env.VITE_KAKAO_CLIENT_ID}` +
  `&redirect_uri=${encodeURIComponent(import.meta.env.VITE_KAKAO_REDIRECT_URI)}` +
  `&response_type=code`;

const COPY = {
  kakao: "카카오로 계속하기",
  apple: "Apple으로 계속하기",
  google: "Google으로 계속하기",
  terms: "로그인 시 이용약관 및 개인정보처리방침에 동의합니다",
};

const socialButtons = [
  {
    label: COPY.kakao,
    icon: kakaoIcon,
    className: "bg-[#fee500]",
    onClick: () => {
      window.location.href = KAKAO_AUTH_URL;
    },
  },
  {
    label: COPY.apple,
    icon: appleIcon,
    className: "bg-white",
  },
  {
    label: COPY.google,
    icon: googleIcon,
    className: "bg-white",
  },
];

export function LoginPage() {
  return (
    <div className="min-h-screen bg-[#0d1b2a]">
      <div className="relative mx-auto min-h-screen w-full max-w-[430px] overflow-hidden">
        {/* <Spline
          className="pointer-events-none absolute left-0 top-0 z-0 h-[calc(100%+80px)] w-full"
          scene="https://prod.spline.design/10xOe1-aIf1GHnfd/scene.splinecode"
        /> */}
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
          <div className="flex items-end mx-auto pb-10 pt-24 justify-between gap-6">
            <img src={HwadamLogo} alt="HwaDam Logo" className="w-25" />
            <h1 className="text-[48px] font-bold text-black">HwaDam</h1>
          </div>

          <div className="px-6">
            <div className="grid gap-3">
              {socialButtons.map(({ label, icon, className, onClick }) => (
                <button
                  className={`relative flex h-[54px] items-center justify-center rounded-xl text-black backdrop-blur-lg ${className}`}
                  key={label}
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
            <p className="text-center text-caption text-gray-300">
              {COPY.terms}
            </p>
          </div>
        </section>
      </div>
    </div>
  );
}
