import { useEffect, useRef } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { socialLogin } from "../../api/authApi";
import { setTokens } from "../../lib/auth";

export function KakaoCallbackPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const called = useRef(false);

  useEffect(() => {
    const code = searchParams.get("code");
    if (!code || called.current) return;
    called.current = true;

    socialLogin(code)
      .then(({ data }) => {
        setTokens(data.accessToken, data.refreshToken);
        navigate(data.isNewUser ? "/onboarding/profile" : "/home", {
          replace: true,
        });
      })
      .catch(() => {
        navigate("/", { replace: true });
      });
  }, [searchParams, navigate]);

  return (
    <div className="flex min-h-screen items-center justify-center">
      <p className="text-body2 text-gray-400">로그인 중...</p>
    </div>
  );
}
