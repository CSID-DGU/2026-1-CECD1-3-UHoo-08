import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { recognizeProduct } from "../../api/productApi";
import AppLayout from "../../layouts/AppLayout";
import { addRegisteredProduct } from "../../lib/onboardingProducts";

type Phase = "camera" | "recognizing" | "result" | "error";

interface ProductInfo {
  id: string;
  name: string;
  brand: string;
  imageUrl?: string | null;
}

export function PhotoRegisterPage() {
  const navigate = useNavigate();
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const streamRef = useRef<MediaStream | null>(null);

  const [phase, setPhase] = useState<Phase>("camera");
  const [preview, setPreview] = useState<string | null>(null);
  const [product, setProduct] = useState<ProductInfo | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    startCamera();
    return () => stopCamera();
  }, []);

  async function startCamera() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "environment" },
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
      }
    } catch {
      // Camera unavailable (desktop/permissions denied) — album still works
    }
  }

  function stopCamera() {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
  }

  function captureFromVideo() {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas) return;
    canvas.width = video.videoWidth || 640;
    canvas.height = video.videoHeight || 480;
    canvas.getContext("2d")?.drawImage(video, 0, 0);
    const dataUrl = canvas.toDataURL("image/jpeg", 0.85);
    stopCamera();
    submitImage(dataUrl.split(",")[1], dataUrl);
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      const dataUrl = reader.result as string;
      stopCamera();
      submitImage(dataUrl.split(",")[1], dataUrl);
    };
    reader.readAsDataURL(file);
  }

  async function submitImage(base64: string, dataUrl: string) {
    setPreview(dataUrl);
    setPhase("recognizing");
    try {
      const res = await recognizeProduct("IMAGE", base64);
      const p = res.data;
      setProduct({ id: p.productId, name: p.name, brand: p.brand, imageUrl: p.imageUrl });
      setPhase("result");
    } catch {
      setErrorMsg("제품을 인식하지 못했어요. 다시 시도해주세요.");
      setPhase("error");
    }
  }

  function handleAdd() {
    if (!product) return;
    addRegisteredProduct(product);
    navigate("/onboarding/products");
  }

  function handleRetry() {
    setPreview(null);
    setProduct(null);
    setErrorMsg(null);
    setPhase("camera");
    startCamera();
  }

  return (
    <AppLayout>
      <section className="flex min-h-screen flex-col px-6 pb-7 pt-10">
        <header className="relative flex h-6 items-center justify-center">
          <button
            className="absolute left-0 text-h3 text-gray-500"
            onClick={() => navigate(-1)}
            type="button"
            aria-label="뒤로가기"
          >
            ←
          </button>
          <h1 className="text-body1 text-gray-500">사진으로 등록</h1>
        </header>

        <div className="mt-7">
          <h2 className="text-h2 text-gray-500">
            화장품 정면을
            <br />
            비춰주세요
          </h2>
          <p className="mt-2 text-body2 text-gray-300">
            AI가 브랜드와 제품명을 자동으로 인식해요
          </p>
        </div>

        {/* Camera / Captured preview */}
        <div
          className="relative mt-5 overflow-hidden rounded-2xl bg-black"
          style={{ minHeight: 280 }}
        >
          {phase === "camera" && (
            <video
              ref={videoRef}
              autoPlay
              playsInline
              muted
              className="h-full w-full object-cover"
              style={{ minHeight: 280 }}
            />
          )}
          {phase !== "camera" && preview && (
            <img
              src={preview}
              alt="캡처 이미지"
              className="h-full w-full object-cover"
              style={{ minHeight: 280 }}
            />
          )}
          {phase === "camera" && (
            <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
              <div className="h-52 w-52 rounded-2xl border-2 border-white opacity-60" />
            </div>
          )}
          {phase === "recognizing" && (
            <div className="absolute inset-0 flex items-center justify-center bg-black/50">
              <div className="rounded-xl bg-white px-6 py-4 text-center">
                <p className="text-body2 text-gray-500">인식 중...</p>
                <p className="mt-1 text-caption text-gray-300">잠시만 기다려주세요</p>
              </div>
            </div>
          )}
        </div>

        <canvas ref={canvasRef} className="hidden" />
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          className="hidden"
          onChange={handleFileChange}
        />

        {/* Recognizing skeleton */}
        {phase === "recognizing" && (
          <div className="mt-4 flex items-center gap-3 rounded-xl border border-primary-100 bg-white p-3">
            <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-xl bg-primary-50">
              <div className="h-9 w-9 rounded-md bg-primary-300" />
            </div>
            <div className="flex-1">
              <span className="rounded-md bg-primary-100 px-3 py-1 text-caption text-primary-500">
                인식 중...
              </span>
              <div className="mt-2 h-2 rounded-full bg-gray-100">
                <div className="h-full w-2/3 animate-pulse rounded-full bg-gray-200" />
              </div>
              <div className="mt-2 h-2 w-1/2 rounded-full bg-gray-100" />
            </div>
          </div>
        )}

        {/* Result card */}
        {phase === "result" && product && (
          <div className="mt-4 flex items-center gap-3 rounded-xl border border-primary-100 bg-white p-3">
            {product.imageUrl ? (
              <img
                src={product.imageUrl}
                alt={product.name}
                className="h-14 w-14 shrink-0 rounded-xl object-cover"
              />
            ) : (
              <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-xl bg-primary-50">
                <div className="h-9 w-9 rounded-md bg-primary-300" />
              </div>
            )}
            <div className="min-w-0 flex-1">
              <p className="truncate text-body2 text-gray-500">{product.name}</p>
              <p className="text-caption text-gray-300">{product.brand}</p>
            </div>
            <button
              className="h-9 rounded-xl bg-primary-500 px-4 text-caption text-white"
              onClick={handleAdd}
              type="button"
            >
              추가
            </button>
          </div>
        )}

        {/* Error card */}
        {phase === "error" && (
          <div className="mt-4 rounded-xl border border-red-100 bg-red-50 p-4">
            <p className="text-body2 text-red-500">{errorMsg}</p>
            <p className="mt-1 text-caption text-gray-400">
              다른 각도에서 다시 찍거나 앨범에서 선택해보세요
            </p>
          </div>
        )}

        {phase === "camera" && (
          <div className="mt-4 rounded-xl bg-gray-100 p-4">
            <p className="text-body2 text-gray-500">잘 인식되지 않나요?</p>
            <p className="mt-1 text-caption text-gray-300">
              앨범에서 기존 사진을 불러올 수도 있어요
            </p>
          </div>
        )}

        {/* Action buttons */}
        <div className="mt-4 grid grid-cols-2 gap-4">
          {phase === "camera" && (
            <>
              <button
                className="h-[52px] rounded-xl bg-gray-500 text-body2 text-white"
                onClick={captureFromVideo}
                type="button"
              >
                촬영하기
              </button>
              <button
                className="h-[52px] rounded-xl bg-gray-100 text-body2 text-gray-500"
                onClick={() => fileInputRef.current?.click()}
                type="button"
              >
                앨범에서 선택
              </button>
            </>
          )}
          {phase === "recognizing" && (
            <button
              className="col-span-2 h-[52px] rounded-xl bg-gray-100 text-body2 text-gray-300"
              disabled
              type="button"
            >
              인식 중...
            </button>
          )}
          {(phase === "result" || phase === "error") && (
            <>
              <button
                className="h-[52px] rounded-xl bg-gray-100 text-body2 text-gray-500"
                onClick={handleRetry}
                type="button"
              >
                다시 찍기
              </button>
              {phase === "result" ? (
                <button
                  className="h-[52px] rounded-xl bg-primary-500 text-body2 text-white"
                  onClick={handleAdd}
                  type="button"
                >
                  추가하기
                </button>
              ) : (
                <button
                  className="h-[52px] rounded-xl bg-gray-100 text-body2 text-gray-500"
                  onClick={() => fileInputRef.current?.click()}
                  type="button"
                >
                  앨범에서 선택
                </button>
              )}
            </>
          )}
        </div>
      </section>
    </AppLayout>
  );
}
