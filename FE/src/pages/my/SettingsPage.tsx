import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { clearTokens } from "../../lib/auth";
import { PageHeader } from "../../components/common/PageHeader";
import AppLayout from "../../layouts/AppLayout";

function Toggle({ on, onToggle }: { on: boolean; onToggle: () => void }) {
  return (
    <button
      className={`relative h-6 w-11 rounded-full transition-colors ${on ? "bg-primary-500" : "bg-gray-200"}`}
      onClick={onToggle}
      type="button"
      aria-pressed={on}
    >
      <span
        className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform ${
          on ? "translate-x-5" : "translate-x-0.5"
        }`}
      />
    </button>
  );
}

function SettingRow({
  label,
  desc,
  on,
  onToggle,
}: {
  label: string;
  desc?: string;
  on: boolean;
  onToggle: () => void;
}) {
  return (
    <div className="flex items-center justify-between py-4">
      <div>
        <p className="text-body2 text-gray-500">{label}</p>
        {desc && <p className="mt-0.5 text-caption text-gray-300">{desc}</p>}
      </div>
      <Toggle on={on} onToggle={onToggle} />
    </div>
  );
}

export function SettingsPage() {
  const navigate = useNavigate();
  const [priceAlert, setPriceAlert] = useState(true);
  const [aiRecommend, setAiRecommend] = useState(true);
  const [weeklyReport, setWeeklyReport] = useState(false);
  const [reviewRequest, setReviewRequest] = useState(true);

  function handleLogout() {
    clearTokens();
    navigate("/", { replace: true });
  }

  return (
    <AppLayout>
      <section className="min-h-screen px-6 pb-10 pt-10">
        <PageHeader title="앱 설정 및 고객센터" onBack={() => navigate(-1)} />

        {/* 알림 설정 */}
        <div className="mt-6">
          <h2 className="text-body1 text-gray-500">알림 설정</h2>
          <div className="mt-3 divide-y divide-gray-100 rounded-xl border border-gray-200 bg-white px-4">
            <SettingRow
              label="가격 변동 알림"
              desc="추적 중인 상품의 가격이 변경되면 알려드려요"
              on={priceAlert}
              onToggle={() => setPriceAlert((v) => !v)}
            />
            <SettingRow
              label="AI 추천 알림"
              desc="맞춤 제품 추천 소식을 알려드려요"
              on={aiRecommend}
              onToggle={() => setAiRecommend((v) => !v)}
            />
            <SettingRow
              label="주간 리포트"
              desc="매주 피부 케어 리포트를 보내드려요"
              on={weeklyReport}
              onToggle={() => setWeeklyReport((v) => !v)}
            />
            <SettingRow
              label="리뷰 요청"
              desc="사용한 제품에 대한 리뷰를 남겨주세요"
              on={reviewRequest}
              onToggle={() => setReviewRequest((v) => !v)}
            />
          </div>
        </div>

        {/* 고객센터 */}
        <div className="mt-6">
          <h2 className="text-body1 text-gray-500">고객센터</h2>
          <div className="mt-3 divide-y divide-gray-100 rounded-xl border border-gray-200 bg-white">
            {[
              { label: "자주 묻는 질문" },
              { label: "1:1 문의" },
              { label: "서비스 이용약관" },
              { label: "개인정보 처리방침" },
            ].map((item) => (
              <button
                className="flex w-full items-center justify-between px-4 py-4 text-left"
                key={item.label}
                type="button"
              >
                <span className="text-body2 text-gray-500">{item.label}</span>
                <span className="text-gray-300">›</span>
              </button>
            ))}
          </div>
        </div>

        {/* 앱 정보 */}
        <div className="mt-6">
          <h2 className="text-body1 text-gray-500">앱 정보</h2>
          <div className="mt-3 divide-y divide-gray-100 rounded-xl border border-gray-200 bg-white">
            <div className="flex items-center justify-between px-4 py-4">
              <span className="text-body2 text-gray-500">버전</span>
              <span className="text-body2 text-gray-300">1.0.0</span>
            </div>
          </div>
        </div>

        <button
          className="mt-8 w-full rounded-xl border border-red-100 bg-red-50 py-4 text-body2 text-red-500"
          onClick={handleLogout}
          type="button"
        >
          로그아웃
        </button>
      </section>
    </AppLayout>
  );
}
