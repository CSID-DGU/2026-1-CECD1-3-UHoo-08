import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { recognizeProduct, searchProducts } from "../../api/productApi";
import { CameraMark } from "../../components/common/CameraMark";
import { PageHeader } from "../../components/common/PageHeader";
import AppLayout from "../../layouts/AppLayout";

export function ProductLookupPage() {
  const navigate = useNavigate();
  const [showCameraToggle, setShowCameraToggle] = useState(false);
  const [text, setText] = useState("");
  const [searching, setSearching] = useState(false);
  const [processing, setProcessing] = useState(false);
  const cameraRef = useRef<HTMLInputElement>(null);
  const albumRef = useRef<HTMLInputElement>(null);

  async function handleImageFile(file: File) {
    setProcessing(true);
    try {
      const base64 = await fileToBase64(file);
      const res = await recognizeProduct("IMAGE", base64);
      navigate("/product/recognize", { state: { result: res.data } });
    } catch {
      alert("이미지 인식에 실패했어요. 다시 시도해주세요.");
    } finally {
      setProcessing(false);
    }
  }

  async function handleTextSearch() {
    const q = text.trim();
    if (!q) return;
    setSearching(true);
    try {
      const res = await searchProducts(q);
      const first = res.data.products[0];
      if (!first) {
        alert("검색 결과가 없어요.");
        return;
      }
      const result = {
        productId: first.id,
        name: first.name,
        brand: first.brand,
        imageUrl: first.imageUrl ?? null,
      };
      navigate("/product/recognize", { state: { result } });
    } catch {
      alert("검색에 실패했어요. 다시 시도해주세요.");
    } finally {
      setSearching(false);
    }
  }

  return (
    <AppLayout>
      <section className="flex min-h-screen flex-col px-6 pb-6 pt-10">
        <PageHeader title="제품 조회" onBack={() => navigate(-1)} />

        <div className="mt-7">
          <h1 className="text-h2 text-gray-500">
            어떤 방법으로
            <br />
            조회할까요?
          </h1>
          <p className="mt-2 text-body2 text-gray-300">제품을 찾아 내 피부와 비교해드려요</p>
        </div>

        {/* 숨겨진 파일 인풋 */}
        <input
          ref={cameraRef}
          accept="image/*"
          capture="environment"
          className="hidden"
          type="file"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) handleImageFile(f);
            e.target.value = "";
          }}
        />
        <input
          ref={albumRef}
          accept="image/*"
          className="hidden"
          type="file"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) handleImageFile(f);
            e.target.value = "";
          }}
        />

        {/* 카메라 영역 */}
        <button
          className="mt-5 flex min-h-[220px] flex-col items-center justify-center rounded-2xl border border-dashed border-primary-100 bg-primary-50 px-8 text-center"
          disabled={processing}
          onClick={() => setShowCameraToggle((v) => !v)}
          type="button"
        >
          {processing ? (
            <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary-200 border-t-primary-500" />
          ) : (
            <>
              <CameraMark className="mb-4 h-[64px] w-[72px]" />
              <p className="text-body2 text-primary-500">사진으로 스캔</p>
              <p className="mt-1 text-caption text-primary-500">이미지 업로드 · AI 자동 인식</p>
              <p className="mt-2 text-caption text-gray-300">탭하여 카메라 열기</p>
            </>
          )}
        </button>

        {/* 카메라 토글 버튼 */}
        {showCameraToggle && (
          <div className="mt-3 grid grid-cols-2 gap-3">
            <button
              className="flex h-11 items-center justify-center gap-2 rounded-xl bg-gray-500 text-body2 text-white"
              onClick={() => {
                setShowCameraToggle(false);
                cameraRef.current?.click();
              }}
              type="button"
            >
              <span>📷</span> 촬영하기
            </button>
            <button
              className="flex h-11 items-center justify-center gap-2 rounded-xl border border-gray-200 bg-white text-body2 text-gray-500"
              onClick={() => {
                setShowCameraToggle(false);
                albumRef.current?.click();
              }}
              type="button"
            >
              <span>🖼</span> 앨범에서 선택
            </button>
          </div>
        )}

        {/* NFC */}
        <button
          className="mt-4 flex h-[56px] items-center gap-3 rounded-xl border border-gray-200 bg-white px-5 text-body2 text-gray-500"
          onClick={() => navigate("/recommendation/nfc-scan")}
          type="button"
        >
          <span className="grid h-9 w-9 place-items-center rounded-lg bg-primary-50 text-lg">📡</span>
          NFC 태그로 조회
        </button>

        {/* 텍스트 검색 */}
        <div className="mt-4 flex h-[68px] items-center gap-3 rounded-xl border border-gray-200 bg-white px-3">
          <input
            className="h-11 flex-1 rounded-xl bg-gray-100 px-4 text-body2 text-gray-500 outline-none placeholder:text-gray-300"
            placeholder="브랜드명, 제품명 검색..."
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleTextSearch()}
          />
          <button
            className="h-11 rounded-xl bg-primary-500 px-4 text-caption text-white disabled:opacity-50"
            disabled={searching || !text.trim()}
            onClick={handleTextSearch}
            type="button"
          >
            {searching ? "..." : "검색"}
          </button>
        </div>

        <div className="mt-6 rounded-xl bg-primary-50 p-4">
          <p className="text-body2 text-primary-500">✦ BeautyMatch AI Tip</p>
          <p className="mt-1 text-caption leading-5 text-gray-500">
            목적과 예산을 함께 입력하면 피부 데이터와 결합해 최적의 가성비 제품을 찾아드려요
          </p>
        </div>
      </section>
    </AppLayout>
  );
}

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result as string;
      resolve(result.split(",")[1] ?? result);
    };
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}
