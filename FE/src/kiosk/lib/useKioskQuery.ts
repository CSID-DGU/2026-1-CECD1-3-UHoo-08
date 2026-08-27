import { useCallback, useEffect, useRef, useState } from "react";
import { KioskApiError } from "./kioskApi";

/**
 * 주기적으로 다시 불러오는 조회 훅.
 *
 * ── 실패해도 화면을 비우지 않는다 ────────────────────────────
 * 시연 중 와이파이가 잠깐 끊기면 다음 폴링이 실패한다. 그때 data를 null로
 * 되돌리면 멀쩡히 보이던 화면이 갑자기 빈다. 마지막으로 성공한 값을 계속
 * 보여주고, 오류는 따로 들고 있다가 배너로 알린다.
 *
 * 대신 언제 받은 값인지(lastUpdated)를 함께 주어, 화면이 오래된 값을 보여줄
 * 때 그 사실을 숨기지 않는다.
 */
export type QueryState<T> = {
  data: T | null;
  error: KioskApiError | null;
  loading: boolean;
  /** 마지막으로 성공한 시각 */
  lastUpdated: Date | null;
  refetch: () => void;
};

export function useKioskQuery<T>(
  fetcher: () => Promise<T>,
  intervalMs: number,
  deps: unknown[] = []
): QueryState<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<KioskApiError | null>(null);
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  // fetcher는 매 렌더마다 새 함수라 의존성에 넣으면 무한 루프가 된다.
  // ref에 담아두고 deps로만 재실행을 통제한다.
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  const aliveRef = useRef(true);

  const run = useCallback(async () => {
    try {
      const result = await fetcherRef.current();
      if (!aliveRef.current) return;
      setData(result);
      setError(null);
      setLastUpdated(new Date());
    } catch (e) {
      if (!aliveRef.current) return;
      setError(
        e instanceof KioskApiError
          ? e
          : new KioskApiError(String(e), "(알 수 없음)", null)
      );
    } finally {
      if (aliveRef.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    aliveRef.current = true;
    setLoading(true);
    void run();

    const id = window.setInterval(() => void run(), intervalMs);
    return () => {
      aliveRef.current = false;
      window.clearInterval(id);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [intervalMs, run, ...deps]);

  return { data, error, loading, lastUpdated, refetch: () => void run() };
}