import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  CONCERN_LABEL,
  PERSONAL_COLOR_LABEL,
  SKIN_TYPE_LABEL,
  getMyProfile,
  updateSkinProfileByLabel,
} from "../../api/userApi";
import { PageHeader } from "../../components/common/PageHeader";
import { PrimaryButton } from "../../components/common/PrimaryButton";
import AppLayout from "../../layouts/AppLayout";
import { personalColors, skinConcerns, skinTypes } from "../../mocks/user";

export function SkinInfoEditPage() {
  const navigate = useNavigate();
  const [skinType, setSkinType] = useState("지성");
  const [color, setColor] = useState("잘 모르겠어요");
  const [selected, setSelected] = useState<string[]>([]);
  const [notes, setNotes] = useState<string[]>([]);
  const [noteInput, setNoteInput] = useState("");
  const [showInput, setShowInput] = useState(false);
  const [loading, setLoading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    getMyProfile()
      .then((res) => {
        const skin = res.data.skinProfile;
        if (!skin) return;
        if (skin.skinType) {
          const label = SKIN_TYPE_LABEL[skin.skinType];
          if (label) setSkinType(label);
        }
        if (skin.personalColor) {
          const label = PERSONAL_COLOR_LABEL[skin.personalColor];
          if (label) setColor(label);
        }
        if (skin.skinConcerns?.length) {
          setSelected(
            skin.skinConcerns
              .map((c) => CONCERN_LABEL[c])
              .filter(Boolean) as string[],
          );
        }
        if (skin.notes?.length) {
          setNotes(skin.notes);
        }
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (showInput) inputRef.current?.focus();
  }, [showInput]);

  function toggleConcern(concern: string) {
    setSelected((cur) =>
      cur.includes(concern) ? cur.filter((c) => c !== concern) : [...cur, concern],
    );
  }

  function addNote() {
    const trimmed = noteInput.trim();
    if (trimmed) {
      setNotes((cur) => [...cur, trimmed]);
      setNoteInput("");
    }
    setShowInput(false);
  }

  async function handleSave() {
    setLoading(true);
    try {
      await updateSkinProfileByLabel(color, skinType, selected, notes);
      navigate("/my");
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  }

  return (
    <AppLayout>
      <section className="flex min-h-screen flex-col px-6 pb-8 pt-10">
        <PageHeader title="피부 정보 수정" onBack={() => navigate(-1)} />

        <div className="mt-5">
          <h1 className="text-h2 text-gray-500">피부 정보</h1>
          <p className="mt-2 text-body2 text-gray-300">맞춤 서비스를 위해 반드시 입력해주세요</p>
        </div>

        <section className="mt-6">
          <h2 className="mb-3 text-body2 text-gray-500">피부 타입</h2>
          <div className="flex flex-wrap gap-2">
            {skinTypes.map((type) => (
              <button
                className={`h-10 rounded-xl px-5 text-body2 ${
                  skinType === type ? "bg-primary-300 text-white" : "bg-gray-100 text-gray-500"
                }`}
                key={type}
                onClick={() => setSkinType(type)}
                type="button"
              >
                {type}
              </button>
            ))}
          </div>
        </section>

        <section className="mt-6">
          <h2 className="mb-3 text-body2 text-gray-500">퍼스널 컬러</h2>
          <div className="grid grid-cols-2 gap-3">
            {personalColors.map((item) => (
              <button
                className={`h-[52px] whitespace-pre-line rounded-xl text-body2 ${
                  item === "잘 모르겠어요" ? "col-span-2" : ""
                } ${color === item ? "bg-gray-500 text-white" : "bg-gray-100 text-gray-300"}`}
                key={item}
                onClick={() => setColor(item)}
                type="button"
              >
                {item}
              </button>
            ))}
          </div>
        </section>

        <section className="mt-6">
          <h2 className="mb-3 text-body2 text-gray-500">피부 고민 (복수선택)</h2>
          <div className="flex flex-wrap gap-2">
            {skinConcerns.map((concern) => (
              <button
                className={`h-9 rounded-full px-4 text-body2 ${
                  selected.includes(concern)
                    ? "bg-primary-300 text-white"
                    : "bg-gray-100 text-gray-500"
                }`}
                key={concern}
                onClick={() => toggleConcern(concern)}
                type="button"
              >
                {concern}
              </button>
            ))}
          </div>
        </section>

        <section className="mt-6">
          <h2 className="mb-3 text-body2 text-gray-500">특이사항</h2>
          <div className="grid gap-2">
            {notes.map((note, idx) => (
              <div
                className="flex items-center justify-between rounded-xl border border-gray-200 bg-white px-4 py-3"
                key={idx}
              >
                <p className="flex-1 text-body2 text-gray-500">{note}</p>
                <button
                  className="ml-3 text-caption text-gray-300"
                  onClick={() => setNotes((cur) => cur.filter((_, i) => i !== idx))}
                  type="button"
                  aria-label="삭제"
                >
                  ✕
                </button>
              </div>
            ))}
          </div>

          {showInput ? (
            <div className="mt-2 flex gap-2">
              <input
                ref={inputRef}
                className="h-10 flex-1 rounded-xl border border-gray-200 px-3 text-body2 outline-none focus:border-primary-500"
                placeholder="특이사항을 입력해주세요"
                value={noteInput}
                onChange={(e) => setNoteInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && addNote()}
              />
              <button
                className="h-10 rounded-xl bg-primary-500 px-4 text-caption text-white"
                onClick={addNote}
                type="button"
              >
                확인
              </button>
            </div>
          ) : (
            <button
              className="mt-2 w-full py-2 text-body2 text-primary-500"
              onClick={() => setShowInput(true)}
              type="button"
            >
              + 추가하기
            </button>
          )}
        </section>

        <PrimaryButton className="mt-auto" disabled={loading} onClick={handleSave}>
          {loading ? "저장 중..." : "정보 저장하기"}
        </PrimaryButton>
      </section>
    </AppLayout>
  );
}
