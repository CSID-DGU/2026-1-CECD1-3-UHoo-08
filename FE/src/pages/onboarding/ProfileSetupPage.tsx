import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { updateProfile } from "../../api/userApi";
import AppLayout from "../../layouts/AppLayout";

export function ProfileSetupPage() {
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [name, setName] = useState("");
  const [gender, setGender] = useState("female");
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function handleImageChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setImageFile(file);
    setPreviewUrl(URL.createObjectURL(file));
  }

  async function handleNext() {
    if (name.trim().length > 0 && name.trim().length < 2) {
      setError("이름은 2자 이상이어야 해요.");
      return;
    }
    setError(null);
    setLoading(true);
    try {
      await updateProfile(
        name.trim() || null,
        gender,
        imageFile,
      );
      navigate("/onboarding/preference");
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
          <div className="mb-5">
            <div className="mb-2 flex items-center justify-between text-caption text-gray-300">
              <span>1 / 2 단계</span>
              <span className="text-primary-500">50%</span>
            </div>
            <div className="h-[3px] rounded-full bg-gray-100">
              <div className="h-full w-1/2 rounded-full bg-primary-500" />
            </div>
          </div>

          <h1 className="text-h2 text-gray-500">
            프로필을
            <br />
            설정해주세요
          </h1>
          <p className="mt-3 text-body2 text-gray-300">
            BeautyMatch에서 사용할 정보를 입력해주세요
          </p>

          {/* 프로필 사진 */}
          <input
            ref={fileInputRef}
            accept="image/*"
            className="hidden"
            type="file"
            onChange={handleImageChange}
          />
          <button
            className="mx-auto mt-8 block"
            type="button"
            aria-label="프로필 사진 선택"
            onClick={() => fileInputRef.current?.click()}
          >
            <div className="relative mx-auto h-[120px] w-[120px]">
              <div className="flex h-full w-full items-center justify-center overflow-hidden rounded-full border border-gray-200 bg-white">
                {previewUrl ? (
                  <img
                    src={previewUrl}
                    alt="프로필 미리보기"
                    className="h-full w-full object-cover"
                  />
                ) : (
                  <span className="relative h-10 w-10 before:absolute before:left-1/2 before:top-0 before:h-10 before:w-[2px] before:-translate-x-1/2 before:bg-gray-200 after:absolute after:left-0 after:top-1/2 after:h-[2px] after:w-10 after:-translate-y-1/2 after:bg-gray-200" />
                )}
              </div>
              <span className="absolute bottom-1 right-0 flex h-9 w-9 items-center justify-center rounded-full border-4 border-white bg-primary-500">
                <svg aria-hidden="true" className="h-5 w-5 text-white" fill="none" viewBox="0 0 24 24">
                  <path d="M4 8.5A2.5 2.5 0 0 1 6.5 6H9l1.5-2h3L15 6h2.5A2.5 2.5 0 0 1 20 8.5v8A2.5 2.5 0 0 1 17.5 19h-11A2.5 2.5 0 0 1 4 16.5v-8Z" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" />
                  <path d="M9 12.5a3 3 0 1 0 6 0 3 3 0 0 0-6 0Z" stroke="currentColor" strokeWidth="2" />
                </svg>
              </span>
            </div>
            <span className="mt-3 block text-caption text-gray-300">프로필 사진 선택</span>
          </button>

          {/* 이름 */}
          <div className="mt-5">
            <label className="text-body2 text-gray-500" htmlFor="name">
              이름
            </label>
            <input
              id="name"
              className="mt-2 h-12 w-full rounded-lg border border-gray-200 px-3 text-body2 outline-none placeholder:text-gray-200 focus:border-primary-500"
              placeholder="이름을 입력해주세요"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>

          {/* 성별 */}
          <div className="mt-5">
            <p className="text-body2 text-gray-500">성별</p>
            <div className="mt-2 grid grid-cols-3 gap-5">
              {([["female", "여성"], ["male", "남성"], ["none", "선택 안함"]] as const).map(
                ([value, label]) => (
                  <button
                    className={`h-[50px] rounded-lg text-body1 ${
                      gender === value
                        ? "bg-primary-300 text-white"
                        : "bg-gray-100 text-gray-500"
                    }`}
                    key={value}
                    onClick={() => setGender(value)}
                    type="button"
                  >
                    {label}
                  </button>
                ),
              )}
            </div>
          </div>

          {error && (
            <p className="mt-3 text-caption text-red-500">{error}</p>
          )}
        </div>

        <button
          className="mt-auto h-14 w-full rounded-xl bg-primary-500 text-body1 text-white disabled:opacity-50"
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
