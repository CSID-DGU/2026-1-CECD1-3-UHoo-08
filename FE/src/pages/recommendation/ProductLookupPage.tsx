import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Camera, ImageIcon, Wifi, X } from "lucide-react";
import { type ProductSearchItem, aiRecognizeProduct, searchProducts } from "../../api/productApi";
import { CameraMark } from "../../components/common/CameraMark";
import { PageHeader } from "../../components/common/PageHeader";
import AppLayout from "../../layouts/AppLayout";

const iconBox = {
  background: "linear-gradient(135deg, rgba(91,143,217,0.35), rgba(53,101,181,0.25))",
  border: "1px solid rgba(255,255,255,0.6)",
  boxShadow: "0 2px 8px rgba(91,143,217,0.2)",
};

export function ProductLookupPage() {
  const navigate = useNavigate();
  const [text, setText] = useState("");
  const [searching, setSearching] = useState(false);
  const [searchResults, setSearchResults] = useState<ProductSearchItem[]>([]);
  const [processing, setProcessing] = useState(false);
  const [showCamera, setShowCamera] = useState(false);
  const albumRef = useRef<HTMLInputElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);

  const stopStream = useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
  }, []);

  async function openCamera() {
    setShowCamera(true);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
      }
    } catch {
      setShowCamera(false);
      alert("카메라에 접근할 수 없어요. 브라우저 권한을 확인해주세요.");
    }
  }

  function closeCamera() {
    stopStream();
    setShowCamera(false);
  }

  async function capturePhoto() {
    const video = videoRef.current;
    if (!video) return;
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext("2d")?.drawImage(video, 0, 0);
    canvas.toBlob(async (blob) => {
      if (!blob) return;
      closeCamera();
      const file = new File([blob], "capture.jpg", { type: "image/jpeg" });
      await handleImageFile(file);
    }, "image/jpeg", 0.9);
  }

  useEffect(() => {
    if (showCamera && videoRef.current && streamRef.current) {
      videoRef.current.srcObject = streamRef.current;
    }
  }, [showCamera]);

  useEffect(() => () => stopStream(), [stopStream]);

  async function handleImageFile(file: File) {
    setProcessing(true);
    try {
      const base64 = await fileToBase64(file);
      const res = await aiRecognizeProduct("IMAGE", base64);
      const result = {
        productId: res.productId ?? "",
        name: res.name ?? "",
        brand: res.brand ?? "",
        imageUrl: null,
      };
      navigate("/product/recognize", { state: { result } });
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
      setSearchResults(res.data.products ?? []);
    } catch {
      setSearchResults([]);
    } finally {
      setSearching(false);
    }
  }

  function handleSelectResult(product: ProductSearchItem) {
    const result = {
      productId: product.id,
      name: product.name,
      brand: product.brand,
      imageUrl: product.imageUrl ?? null,
    };
    setText("");
    setSearchResults([]);
    navigate("/product/recognize", { state: { result } });
  }

  return (
    <AppLayout>
      {/* 카메라 오버레이 */}
      {showCamera && (
        <div className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-black">
          <video
            ref={videoRef}
            autoPlay
            playsInline
            muted
            className="h-full w-full object-cover"
          />
          {/* 가이드 프레임 */}
          <div
            className="pointer-events-none absolute inset-0 flex items-center justify-center"
          >
            <div
              className="h-64 w-64 rounded-2xl"
              style={{
                border: "2px solid rgba(255,255,255,0.8)",
                boxShadow: "0 0 0 9999px rgba(0,0,0,0.45)",
              }}
            />
          </div>
          <p className="absolute top-24 text-caption text-white/80">
            제품 라벨을 프레임 안에 맞춰주세요
          </p>
          {/* 컨트롤 */}
          <div className="absolute bottom-12 flex w-full items-center justify-around px-12">
            <button
              className="flex h-12 w-12 items-center justify-center rounded-full bg-white/20"
              onClick={closeCamera}
              type="button"
              aria-label="닫기"
            >
              <X className="h-6 w-6 text-white" />
            </button>
            <button
              className="flex h-20 w-20 items-center justify-center rounded-full border-4 border-white bg-white/30"
              onClick={capturePhoto}
              disabled={processing}
              type="button"
              aria-label="촬영"
            >
              <span className="h-14 w-14 rounded-full bg-white" />
            </button>
            <div className="h-12 w-12" />
          </div>
        </div>
      )}

      <div className="flex h-screen flex-col overflow-hidden">
        <div className="flex-1 overflow-y-auto scrollbar-none">
          <section className="flex flex-col px-6 pb-6 pt-10">
            <PageHeader title="제품 조회" onBack={() => navigate(-1)} />

            <div className="mt-7">
              <h1 className="text-h2 text-gray-500">
                어떤 방법으로
                <br />
                조회할까요?
              </h1>
              <p className="mt-2 text-body2 text-gray-300">제품을 찾아 내 피부와 비교해드려요</p>
            </div>

            {/* 앨범 전용 숨겨진 인풋 */}
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

            {/* 사진 스캔 영역 */}
            <button
              className="mt-5 flex min-h-[200px] flex-col items-center justify-center rounded-2xl border border-dashed border-primary-100 bg-primary-50 px-8 text-center"
              disabled={processing}
              onClick={openCamera}
              type="button"
            >
              {processing ? (
                <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary-200 border-t-primary-500" />
              ) : (
                <>
                  <CameraMark className="mb-4 h-[64px] w-[72px]" />
                  <p className="text-body2 text-primary-500">사진으로 스캔</p>
                  <p className="mt-1 text-caption text-primary-500">카메라 · AI 자동 인식</p>
                </>
              )}
            </button>

            {/* 촬영하기 + 앨범 버튼 */}
            <div className="mt-3 grid grid-cols-2 gap-3">
              <button
                className="flex h-12 items-center justify-center gap-2 rounded-xl text-body2 text-white"
                style={{ background: "linear-gradient(135deg, #5B8FD9, #3565B5)" }}
                onClick={openCamera}
                disabled={processing}
                type="button"
              >
                <span className="grid h-7 w-7 place-items-center rounded-lg" style={iconBox}>
                  <Camera className="h-4 w-4 text-white" strokeWidth={1.8} />
                </span>
                촬영하기
              </button>
              <button
                className="flex h-12 items-center justify-center gap-2 rounded-xl border border-gray-200 bg-white text-body2 text-gray-500"
                onClick={() => albumRef.current?.click()}
                disabled={processing}
                type="button"
              >
                <span className="grid h-7 w-7 place-items-center rounded-lg" style={iconBox}>
                  <ImageIcon className="h-4 w-4 text-primary-600" strokeWidth={1.8} />
                </span>
                앨범에서 선택
              </button>
            </div>

            {/* NFC */}
            <button
              className="mt-4 flex h-[56px] items-center gap-3 rounded-xl border border-gray-200 bg-white px-5 text-body2 text-gray-500"
              onClick={() => navigate("/recommendation/nfc-scan/demo")}
              type="button"
            >
              <span className="grid h-9 w-9 place-items-center rounded-lg" style={iconBox}>
                <Wifi className="h-5 w-5 text-primary-600" strokeWidth={1.8} />
              </span>
              NFC 태그로 조회
            </button>

            {/* 텍스트 검색 */}
            <div className="mt-4">
              <div className="flex h-[52px] items-center gap-3 rounded-xl border border-gray-200 bg-white px-3">
                <input
                  className="h-10 flex-1 rounded-xl bg-gray-100 px-4 text-body2 text-gray-500 outline-none placeholder:text-gray-300"
                  placeholder="브랜드명, 제품명으로 검색..."
                  value={text}
                  onChange={(e) => {
                    setText(e.target.value);
                    if (!e.target.value.trim()) setSearchResults([]);
                  }}
                  onKeyDown={(e) => e.key === "Enter" && handleTextSearch()}
                />
                <button
                  className="h-10 rounded-xl bg-primary-500 px-4 text-caption text-white disabled:opacity-50"
                  disabled={searching || !text.trim()}
                  onClick={handleTextSearch}
                  type="button"
                >
                  {searching ? "···" : "검색"}
                </button>
              </div>

              {searchResults.length > 0 && (
                <div className="mt-2 overflow-hidden rounded-xl border border-gray-200 bg-white">
                  {searchResults.map((product) => (
                    <button
                      key={product.id}
                      className="flex w-full items-center gap-3 border-b border-gray-100 p-3 text-left last:border-b-0 active:bg-gray-50"
                      onClick={() => handleSelectResult(product)}
                      type="button"
                    >
                      <div className="h-11 w-11 shrink-0 overflow-hidden rounded-xl bg-primary-50">
                        {product.imageUrl && (
                          <img src={product.imageUrl} alt={product.name} className="h-full w-full object-cover" />
                        )}
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-body2 text-gray-500">{product.name}</p>
                        <p className="text-caption text-gray-300">{product.brand}</p>
                      </div>
                      {product.originalPrice != null && (
                        <span className="shrink-0 text-caption text-gray-400">
                          {product.originalPrice.toLocaleString()}원
                        </span>
                      )}
                    </button>
                  ))}
                </div>
              )}

              {!searching && text.trim() && searchResults.length === 0 && (
                <p className="mt-2 text-caption text-gray-300">검색 결과가 없어요</p>
              )}
            </div>

            <div className="mt-6 rounded-xl bg-primary-50 p-4">
              <p className="text-body2 text-primary-500">✦ BeautyMatch AI Tip</p>
              <p className="mt-1 text-caption leading-5 text-gray-500">
                목적과 예산을 함께 입력하면 피부 데이터와 결합해 최적의 가성비 제품을 찾아드려요
              </p>
            </div>
          </section>
        </div>
      </div>
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
