import { useCallback, useEffect, useRef, useState } from "react";
import { measureApi } from "./careApi";
import { KioskApiError } from "./kioskApi";
import type { MeasureSession, MeasureStartResponse } from "./types";

/**
 * 측정 세션을 따라가는 훅.
 *
 * 화장품(MeasureScreen)과 피부(SkinRunScreen)는 안내 문구와 결과가 다르지만,
 * 그 사이의 절차는 완전히 같다. 세션을 열고 → 사용자가 누르면 노드에 알리고
 * → 노드가 채우는 동안 서버에 물어보고 → 나갈 때 닫는다. 두 화면이 각자
 * 들고 있으면 한쪽만 고치는 사고가 난다.
 *
 * ── 단계는 서버가 센다 ───────────────────────────────────────
 * 화면이 따로 단계를 세지 않는다. 새로고침이나 잠깐의 통신 실패로 어긋나면
 * 사용자는 백색 표준판을 다시 올리라는 안내를 받으면서 실제로는 시료가
 * 필요한 상태에 있게 된다.
 */

/** 더 이상 바뀌지 않는 상태. 여기 닿으면 폴링을 멈춘다. */
const TERMINAL = ["done", "failed", "expired", "cancelled"] as const;

/**
 * 노드가 이 시간 안에 답하지 않으면 무언가 잘못된 것이다.
 *
 * 한 번 재는 데 걸리는 시간은 적분 약 0.6초에 폴링 간격을 더해도 5초를
 * 넘지 않는다. 그보다 오래 걸리면 노드가 꺼져 있거나 Wi-Fi가 끊긴 것이다.
 * 세션 시한(5분)까지 기다리게 두면 사용자는 5분 동안 도는 표시만 본다.
 */
export const STALL_SEC = 15;

export type MeasurePhase = "intro" | "run" | "result";

export type MeasureSessionState = {
  session: MeasureSession | null;
  /** 시작 응답. has_baseline처럼 세션 조회에는 없는 값이 들어 있다. */
  start: MeasureStartResponse | null;
  phase: MeasurePhase;
  busy: boolean;
  error: KioskApiError | null;
  clearError: () => void;
  /** 노드가 재기 시작한 뒤 흐른 초. 재는 중이 아니면 0. */
  elapsed: number;
  /** 노드가 응답하지 않는 것으로 보이는지. */
  stalled: boolean;
  begin: () => void;
  capture: () => void;
  /** 열린 세션을 닫고 나간다. */
  leave: () => void;
  restart: () => void;
};

export function useMeasureSession(
  startFn: () => Promise<MeasureStartResponse>,
  onExit: () => void
): MeasureSessionState {
  const [session, setSession] = useState<MeasureSession | null>(null);
  const [start, setStart] = useState<MeasureStartResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<KioskApiError | null>(null);
  /**
   * 노드가 재기 시작한 뒤 흐른 시간.
   *
   * 어느 단계를 재던 중이었는지(status)를 함께 담는다. 백색과 시료는 각각
   * 따로 세야 하는데, 초 수만 담아 두면 시료를 재기 시작한 첫 순간에 백색을
   * 재며 쌓인 값이 남아 "20초째 기다리는 중"이 잠깐 스친다.
   */
  const [progress, setProgress] = useState<{ status: string; sec: number } | null>(null);

  // 매 렌더마다 새 함수라 의존성에 넣으면 무한 루프가 된다. ref에 담아
  // 두고 부를 때 최신 것을 쓴다. 갱신을 렌더 중이 아니라 effect에서 하는
  // 이유는, 렌더는 부수효과 없이 끝나야 하기 때문이다.
  const startRef = useRef(startFn);
  const exitRef = useRef(onExit);
  useEffect(() => {
    startRef.current = startFn;
    exitRef.current = onExit;
  });

  const sessionId = session?.session_id ?? null;
  const finished = session
    ? (TERMINAL as readonly string[]).includes(session.status)
    : false;

  const fail = (e: unknown) =>
    setError(e instanceof KioskApiError ? e : new KioskApiError(String(e), "-", null));

  // ── 세션 상태 따라가기 ─────────────────────────────────────
  // 노드가 값을 채워 넣는 동안 서버만 진행을 안다. 끝난 세션은 더 볼 것이
  // 없으므로 폴링을 멈춘다. 결과 화면에서 계속 부르면 아무것도 달라지지
  // 않는 요청이 화면이 닫힐 때까지 이어진다.
  useEffect(() => {
    if (!sessionId || finished) return;

    let alive = true;
    const tick = async () => {
      try {
        const next = await measureApi.status(sessionId);
        if (alive) setSession(next);
      } catch (e) {
        // 폴링 실패는 화면을 갈아엎지 않는다. 잠깐 끊긴 것일 수 있고,
        // 마지막으로 받은 상태를 계속 보여주는 편이 낫다.
        if (alive && e instanceof KioskApiError && e.status !== null) setError(e);
      }
    };

    const id = window.setInterval(() => void tick(), (session?.poll_sec ?? 2) * 1000);
    return () => {
      alive = false;
      window.clearInterval(id);
    };
  }, [sessionId, finished, session?.poll_sec]);

  // 노드가 재고 있는 동안만 시간을 센다.
  useEffect(() => {
    if (!session?.capturing) return;

    const began = Date.now();
    const status = session.status;
    const id = window.setInterval(
      () => setProgress({ status, sec: Math.floor((Date.now() - began) / 1000) }),
      500
    );
    return () => window.clearInterval(id);
  }, [session?.status, session?.capturing]);

  const elapsed =
    session?.capturing && progress?.status === session.status ? progress.sec : 0;

  const begin = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const res = await startRef.current();
      setStart(res);
      setSession(res);
    } catch (e) {
      fail(e);
    } finally {
      setBusy(false);
    }
  }, []);

  const capture = useCallback(async () => {
    if (!sessionId) return;
    setBusy(true);
    setError(null);
    try {
      setSession(await measureApi.capture(sessionId));
    } catch (e) {
      fail(e);
    } finally {
      setBusy(false);
    }
  }, [sessionId]);

  /**
   * 열린 세션을 닫고 나간다.
   *
   * 닫지 않으면 노드가 시한이 다 될 때까지 그 세션을 붙들고 있어, 다음
   * 사람이 측정을 시작해도 노드가 반응하지 않는다. 취소가 실패해도
   * 화면은 나간다 — 시한이 지나면 서버가 알아서 만료시킨다.
   */
  const leave = useCallback(async () => {
    if (sessionId && !finished) {
      try {
        await measureApi.cancel(sessionId);
      } catch {
        /* 시한 만료에 맡긴다 */
      }
    }
    exitRef.current();
  }, [sessionId, finished]);

  const restart = useCallback(() => {
    setSession(null);
    setStart(null);
    setError(null);
    void begin();
  }, [begin]);

  return {
    session,
    start,
    phase: !session ? "intro" : finished ? "result" : "run",
    busy,
    error,
    clearError: () => setError(null),
    elapsed,
    stalled: elapsed >= STALL_SEC,
    begin: () => void begin(),
    capture: () => void capture(),
    leave: () => void leave(),
    restart,
  };
}
