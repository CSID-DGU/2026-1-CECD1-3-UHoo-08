import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { updateSkinProfile } from "../../api/userApi";
import AppLayout from "../../layouts/AppLayout";

const personalColors = [
  { id: "spring-warm",  label: "웜톤\n봄 웜" },
  { id: "summer-cool",  label: "쿨톤\n여름 쿨" },
  { id: "autumn-warm",  label: "뮤트\n가을 뮤트" },
  { id: "winter-cool",  label: "쿨톤\n겨울 쿨" },
  { id: "unknown",      label: "잘 모르겠어요", wide: true },
];

const skinTypes = ["건성", "중성", "지성", "복합성", "수부지"];

const concerns = [
  "민감성", "여드름", "아토피", "미백/잡티", "피지/블랙헤드",
  "다크서클", "속건조", "주름/탄력", "모공", "홍조", "각질", "해당 없음",
];

export function PreferenceSetupPage() {
  const navigate = useNavigate();
  const [personalColor, setPersonalColor] = useState("spring-warm");
  const [skinType, setSkinType] = useState("지성");
  const [selectedConcerns, setSelectedConcerns] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function toggleConcern(concern: string) {
    if (concern === "해당 없음") {
      setSelectedConcerns(["해당 없음"]);
      return;
    }
    setSelectedConcerns((prev) =>
      prev.filter((c) => c !== "해당 없음").includes(concern)
        ? prev.filter((c) => c !== concern)
        : [...prev.filter((c) => c !== "해당 없음"), concern],
    );
  }

  async function handleNext() {
    setError(null);
    setLoading(true);
    try {
      await updateSkinProfile(personalColor, skinType, selectedConcerns);
      navigate("/onboarding/products");
    } catch {
      setError("저장 중 오류가 발생했어요. 다시 시도해주세요.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <AppLayout>
      <section className="flex min-h-screen flex-col px-6 pb-8 pt-10">
        <div>
          <div className="mb-3 h-[3px] rounded-full bg-gray-100">
            <div className="h-full w-1/2 rounded-full bg-primary-500" />
          </div>
          <div className="mb-2 flex items-center justify-between text-caption text-gray-300">
            <span>1 / 2 단계</span>
            <span className="text-primary-500">50%</span>
          </div>

          <h1 className="text-h2 text-gray-500">
            피부 특성을
            <br />
            알려주세요
          </h1>
          <p className="mt-2 text-body2 text-gray-300">
            정확한 추천을 위해 꼭 필요해요
          </p>

          {/* 퍼스널 컬러 */}
          <div className="mt-5">
            <p className="mb-2 text-body2 text-gray-500">퍼스널 컬러</p>
            <div className="grid grid-cols-2 gap-3">
              {personalColors.map((item) => (
                <button
                  className={`h-[52px] whitespace-pre-line rounded-xl text-body2 ${
                    item.wide ? "col-span-2" : ""
                  } ${
                    personalColor === item.id
                      ? "bg-gray-500 text-white"
                      : "bg-gray-100 text-gray-300"
                  }`}
                  key={item.id}
                  onClick={() => setPersonalColor(item.id)}
                  type="button"
                >
                  {item.label}
                </button>
              ))}
            </div>
          </div>

          {/* 피부 타입 */}
          <div className="mt-5">
            <p className="mb-2 text-body2 text-gray-500">피부 타입</p>
            <div className="flex flex-wrap gap-3">
              {skinTypes.map((type) => (
                <button
                  className={`h-10 rounded-xl px-5 text-body2 ${
                    skinType === type
                      ? "bg-primary-300 text-white"
                      : "bg-gray-100 text-gray-500"
                  }`}
                  key={type}
                  onClick={() => setSkinType(type)}
                  type="button"
                >
                  {type}
                </button>
              ))}
            </div>
          </div>

          {/* 피부 고민 */}
          <div className="mt-4">
            <p className="mb-2 text-body2 text-gray-500">피부 고민 (복수선택)</p>
            <div className="flex flex-wrap gap-3">
              {concerns.map((concern) => {
                const selected = selectedConcerns.includes(concern);
                return (
                  <button
                    className={`h-10 rounded-xl px-5 text-body2 ${
                      selected
                        ? "bg-primary-300 text-white"
                        : "bg-gray-100 text-gray-500"
                    }`}
                    key={concern}
                    onClick={() => toggleConcern(concern)}
                    type="button"
                  >
                    {concern}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="mt-6 border-l-4 border-primary-500 bg-primary-100 px-4 py-3">
            <p className="text-body2 text-primary-700">피부 분석 TIP</p>
            <p className="mt-1 text-caption text-gray-400">
              선택 후 AI가 성분 적합도를 자동으로 계산해요
            </p>
          </div>

          {error && (
            <p className="mt-3 text-caption text-red-500">{error}</p>
          )}
        </div>

        <button
          className="mt-auto h-14 w-full rounded-xl bg-primary-500 text-body1 font-semibold text-white disabled:opacity-50"
          disabled={loading}
          onClick={handleNext}
          type="button"
        >
          {loading ? "저장 중..." : "다음으로 →"}
        </button>
      </section>
    </AppLayout>
  );
}
