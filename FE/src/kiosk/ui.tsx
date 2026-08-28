import type { ReactNode } from "react";
import { API_BASE, API_BASE_FROM_ENV, KioskApiError, KIOSK_USER_ID } from "./lib/kioskApi";

/**
 * 키오스크 공통 조각.
 *
 * 색상 토큰은 index.css의 @theme에 있는 것을 그대로 쓴다(primary·gray).
 * 다만 상태색(red/amber/green)은 index.css에 없다. 기존 모바일 화면이
 * 쓰지 않는 색이라 전역 토큰에 추가하면 그쪽에도 영향이 가므로,
 * 키오스크 안에서만 상수로 들고 쓴다.
 */
export const STATUS = {
  red: "#E05A5A",
  amber: "#E8A93B",
  green: "#4CAF7D",
} as const;

export const BAND_STYLE = {
  high: { emoji: "🔴", pill: "#FBE9E9", text: STATUS.red, label: "확인 필요" },
  medium: { emoji: "🟡", pill: "#FDF3E7", text: STATUS.amber, label: "지켜보기" },
  low: { emoji: "🟢", pill: "#E8F5EE", text: STATUS.green, label: "정상 범위" },
} as const;

// ── 상단 바 ──────────────────────────────────────────────────

export function TopBar({ left, right }: { left: ReactNode; right?: ReactNode }) {
  return (
    <div className="flex flex-none items-center justify-between border-b border-primary-100 bg-primary-50 px-[26px] pt-4 pb-[13px]">
      {left}
      {right ? <div className="text-[18px] font-medium text-gray-300 tabular-nums">{right}</div> : null}
    </div>
  );
}

export function Brand() {
  return (
    <div className="text-[25px] font-bold">
      화담 <span className="text-primary-500">CARE</span>
    </div>
  );
}

// ── 하단 탭 ──────────────────────────────────────────────────

export const TABS = [
  { key: "priority", label: "점검" },
  { key: "skin", label: "피부" },
  { key: "reco", label: "추천" },
  { key: "env", label: "환경" },
] as const;

export type TabKey = (typeof TABS)[number]["key"];

export function TabBar({
  active,
  onChange,
}: {
  active: TabKey | null;
  onChange: (t: TabKey) => void;
}) {
  return (
    // 터치 타겟 68px. 목업 기준이며 손가락으로 누르는 화면이라 줄이지 않는다.
    <div className="grid flex-none grid-cols-4 border-t border-gray-200 bg-white">
      {TABS.map((t) => {
        const on = active === t.key;
        return (
          <button
            key={t.key}
            onClick={() => onChange(t.key)}
            className={
              "flex h-[68px] items-center justify-center gap-2 border-t-[3px] text-[17px] font-semibold " +
              (on
                ? "border-primary-500 bg-primary-50 text-primary-500"
                : "border-transparent text-gray-300")
            }
          >
            <i className="h-2 w-2 rounded-full bg-current opacity-50" />
            {t.label}
          </button>
        );
      })}
    </div>
  );
}

// ── 오류 표시 ────────────────────────────────────────────────

/**
 * 아이패드에는 개발자 도구가 없다. 시연 중 문제가 생기면 이 화면이
 * 유일한 단서이므로, 주소와 상태 코드와 응답 본문을 그대로 보여준다.
 */
export function ErrorPanel({
  error,
  onRetry,
  title = "서버에 연결하지 못했습니다",
}: {
  error: KioskApiError;
  onRetry?: () => void;
  title?: string;
}) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-4 px-10 text-center">
      <div className="text-[24px] font-bold">{title}</div>
      <div className="text-[18px] font-medium text-gray-400">{error.summary}</div>

      <div className="w-full max-w-[820px] rounded-[14px] bg-white p-4 text-left">
        <div className="text-[13px] font-medium text-gray-300">요청한 주소</div>
        <div className="mt-1 break-all font-mono text-[15px]">{error.url}</div>

        <div className="mt-3 text-[13px] font-medium text-gray-300">메시지</div>
        <div className="mt-1 break-all text-[15px]">{error.message}</div>

        {error.body ? (
          <>
            <div className="mt-3 text-[13px] font-medium text-gray-300">응답 본문</div>
            <pre className="mt-1 max-h-[120px] overflow-auto rounded bg-gray-100 p-2 font-mono text-[13px] whitespace-pre-wrap">
              {error.body}
            </pre>
          </>
        ) : null}

        <div className="mt-3 text-[13px] text-gray-300">
          API 기준 주소 {API_BASE} ({API_BASE_FROM_ENV ? "환경변수" : "기본값"})
          {" · "}사용자 {KIOSK_USER_ID.slice(0, 8)}…
        </div>
      </div>

      {onRetry ? (
        <button
          onClick={onRetry}
          className="h-[62px] rounded-[14px] bg-primary-500 px-[34px] text-[20px] font-semibold text-white"
        >
          다시 시도
        </button>
      ) : null}
    </div>
  );
}

/** 마지막 값은 살아 있지만 최신 갱신에 실패했을 때 위에 얇게 띄우는 줄. */
export function StaleBanner({ error, lastUpdated }: { error: KioskApiError; lastUpdated: Date | null }) {
  return (
    <div className="flex items-center gap-2 bg-[#FDF3E7] px-[26px] py-1.5 text-[14px] font-medium text-[#8A5A12]">
      <span>갱신 실패 · {error.summary}</span>
      {lastUpdated ? (
        <span className="opacity-70">
          마지막 갱신 {lastUpdated.toLocaleTimeString("ko-KR", { hour12: false })}
        </span>
      ) : null}
      <span className="ml-auto max-w-[520px] truncate opacity-60">{error.url}</span>
    </div>
  );
}

// ── 로딩 ─────────────────────────────────────────────────────

export function Loading({ label = "불러오는 중" }: { label?: string }) {
  return (
    <div className="flex h-full items-center justify-center text-[20px] font-medium text-gray-300">
      {label}…
    </div>
  );
}