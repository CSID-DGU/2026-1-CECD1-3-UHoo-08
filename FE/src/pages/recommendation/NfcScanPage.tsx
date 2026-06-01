import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { recognizeProduct } from "../../api/productApi";
import { PageHeader } from "../../components/common/PageHeader";
import AppLayout from "../../layouts/AppLayout";

type ScanState = "idle" | "scanning" | "reading" | "error";

export function NfcScanPage() {
  const navigate = useNavigate();
  const [state, setState] = useState<ScanState>("idle");
  const [errorMsg, setErrorMsg] = useState("");

  async function startNfcScan() {
    if (!("NDEFReader" in window)) {
      setErrorMsg("이 기기는 NFC를 지원하지 않아요.");
      setState("error");
      return;
    }

    setState("scanning");
    try {
      // @ts-expect-error - NDEFReader is experimental
      const reader = new window.NDEFReader();
      await reader.scan();

      reader.onreading = async (event: { message: { records: Array<{ recordType: string; toText: () => string }> } }) => {
        setState("reading");
        const record = event.message.records.find(
          (r: { recordType: string }) => r.recordType === "url" || r.recordType === "text",
        );
        if (!record) {
          setErrorMsg("인식된 제품 정보가 없어요.");
          setState("error");
          return;
        }
        const nfcData = record.toText();
        try {
          const res = await recognizeProduct("NFC", nfcData);
          navigate("/product/recognize", { state: { result: res.data } });
        } catch {
          setErrorMsg("제품 조회에 실패했어요.");
          setState("error");
        }
      };

      reader.onreadingerror = () => {
        setErrorMsg("NFC 태그를 읽을 수 없어요. 다시 시도해주세요.");
        setState("error");
      };
    } catch {
      setErrorMsg("NFC 스캔을 시작할 수 없어요. 권한을 확인해주세요.");
      setState("error");
    }
  }

  useEffect(() => {
    startNfcScan();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <AppLayout>
      <section className="flex min-h-screen flex-col items-center px-6 pb-8 pt-10">
        <div className="w-full">
          <PageHeader title="NFC 태그 조회" onBack={() => navigate(-1)} />
        </div>

        <div className="mt-14 flex flex-1 flex-col items-center justify-center text-center">
          {state !== "error" ? (
            <>
              <div className="relative flex h-40 w-40 items-center justify-center">
                <div
                  className={`absolute inset-0 rounded-full border-4 border-primary-300 ${
                    state === "scanning" ? "animate-ping opacity-30" : "opacity-0"
                  }`}
                />
                <div className="flex h-28 w-28 items-center justify-center rounded-full bg-primary-50">
                  <svg className="h-12 w-12 text-primary-500" fill="none" viewBox="0 0 24 24">
                    <path
                      d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 3a7 7 0 110 14A7 7 0 0112 5zm0 2a5 5 0 100 10A5 5 0 0012 7zm0 2a3 3 0 110 6 3 3 0 010-6z"
                      fill="currentColor"
                    />
                  </svg>
                </div>
              </div>
              <h2 className="mt-8 text-h3 text-gray-500">
                {state === "idle" && "NFC 스캔 준비 중..."}
                {state === "scanning" && "제품 태그를 가져다 대세요"}
                {state === "reading" && "제품 정보를 읽는 중..."}
              </h2>
              <p className="mt-3 text-body2 text-gray-300">
                {state === "scanning"
                  ? "스마트폰 후면을 제품 NFC 태그에 가까이 대주세요"
                  : "잠시만 기다려주세요"}
              </p>
            </>
          ) : (
            <>
              <div className="flex h-28 w-28 items-center justify-center rounded-full bg-gray-100">
                <span className="text-[40px]">⚠️</span>
              </div>
              <h2 className="mt-8 text-h3 text-gray-500">스캔 실패</h2>
              <p className="mt-3 text-body2 text-gray-300">{errorMsg}</p>
              <button
                className="mt-8 h-12 rounded-xl bg-primary-500 px-8 text-body2 text-white"
                onClick={() => {
                  setState("idle");
                  setErrorMsg("");
                  startNfcScan();
                }}
                type="button"
              >
                다시 시도
              </button>
            </>
          )}
        </div>
      </section>
    </AppLayout>
  );
}
