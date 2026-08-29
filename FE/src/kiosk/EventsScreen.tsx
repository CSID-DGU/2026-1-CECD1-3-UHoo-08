import { useEffect, useState } from "react";
import { TopBar, TabBar, ErrorPanel, StaleBanner, Loading, STATUS, type TabKey } from "./ui";
import { ProductPicker } from "./ProductPicker";
import { careGet, carePost } from "./lib/careApi";
import { KIOSK_USER_ID, KioskApiError } from "./lib/kioskApi";
import { useKioskQuery } from "./lib/useKioskQuery";
import type { CareEvent, EventAnswerResponse, EventsResponse } from "./lib/types";

/**
 * 이벤트 이력과 확인 질문.
 *
 * ── 경고가 아니라 질문이다 ───────────────────────────────────
 * VOC 급락의 원인은 알고리즘으로 가릴 수 없다. 향수·헤어스프레이·네일
 * 리무버가 모두 같은 신호를 낸다. 실측에서도 향수 분무에 -92.9%가 나왔다.
 * 그래서 시스템이 단정하지 않고 사용자에게 묻는다.
 *
 * ── 답하고 끝나지 않는다 ─────────────────────────────────────
 * "향수를 뒀다"면 기록을 빼고, "아니요"면 같은 보관함의 확인 순위 상위
 * 제품을 함께 보여준다. 설계서의 "이벤트 유효 → 위험 점수 상위 제품 선별"이다.
 */

const POLL_MS = 5 * 60_000;

type Props = {
  activeTab: TabKey;
  onTab: (t: TabKey) => void;
  onBack: () => void;
  /**
   * 확인할 제품들과 이벤트 id. 여러 개면 순서대로 확인한다.
   */
  onProduct: (userProductIds: string[], eventId: number) => void;
};

export function EventsScreen({ activeTab, onTab, onBack, onProduct }: Props) {
  const events = useKioskQuery<EventsResponse>(
    () => careGet<EventsResponse>("/api/care/events", { user_id: KIOSK_USER_ID }),
    POLL_MS
  );

  const { data, error, loading, lastUpdated } = events;

  // 답변 중인 이벤트와 그 결과. 화면 위에 카드로 띄운다.
  const [answering, setAnswering] = useState<number | null>(null);
  const [result, setResult] = useState<EventAnswerResponse | null>(null);
  // 안내를 닫으면 제품 목록을 띄운다. 두 카드를 겹쳐 놓으면 화면이 좁다.
  const [picking, setPicking] = useState<EventAnswerResponse | null>(null);

  // 답한 직후의 상태를 화면에 바로 반영한다.
  //
  // refetch를 걸어도 서버 왕복이 끝날 때까지 목록이 그대로다. 시연에서
  // 버튼을 눌렀는데 아무 변화가 없으면 고장처럼 보인다. 응답으로 받은
  // 이벤트를 즉시 덮어쓴다.
  const [patched, setPatched] = useState<Record<number, CareEvent>>({});

  // 서버 값이 새로 도착하면 임시 덮어쓰기를 버린다.
  //
  // 버리지 않으면 문제가 생긴다. "아니요"로 답한 뒤 제품을 확인해
  // "냄새 변화"를 골라도, 화면은 답변 직후의 "짚이는 외부 요인 없음"에
  // 머문다. 확인 결과가 반영된 서버 값이 임시 값에 가려지기 때문이다.
  useEffect(() => {
    if (lastUpdated) setPatched({});
  }, [lastUpdated]);
  const [answerError, setAnswerError] = useState<KioskApiError | null>(null);

  const answer = async (
    id: number,
    value: "external_source" | "none",
    inspect = true,
    opts: { silent?: boolean } = {}
  ) => {
    setAnswering(id);
    setAnswerError(null);
    try {
      const res = await carePost<EventAnswerResponse>(
        `/api/care/events/${id}/answer`,
        { answer: value, inspect },
        { user_id: KIOSK_USER_ID }
      );
      // silent면 안내 카드를 띄우지 않는다. 사용자가 이미 "괜찮다"고
      // 했는데 또 무언가를 읽게 하지 않는다.
      if (!opts.silent) setResult(res);
      setPatched((p) => ({ ...p, [id]: res.event }));
      // 서버 값으로도 맞춘다. 위 덮어쓰기는 그때까지의 임시 표시다.
      events.refetch();
    } catch (e) {
      setAnswerError(e instanceof KioskApiError ? e : new KioskApiError(String(e), "-", null));
    } finally {
      setAnswering(null);
    }
  };

  return (
    <div className="flex h-full flex-col">
      <TopBar
        left={
          <button onClick={onBack} className="text-[25px] font-bold">
            ← 이벤트 이력
          </button>
        }
        right={data ? `기록 ${data.summary.total}건` : undefined}
      />

      {error && data ? <StaleBanner error={error} lastUpdated={lastUpdated} /> : null}

      <div className="flex-1 overflow-hidden px-[26px] py-[18px]">
        {loading && !data ? (
          <Loading label="이벤트를 불러오는 중" />
        ) : error && !data ? (
          <ErrorPanel error={error} onRetry={events.refetch} />
        ) : data ? (
          <div className="flex h-full flex-col">
            {/* 설명은 여기 한 번만. 칸마다 반복하면 기록이 안 보인다. */}
            {data.intro?.length ? (
              <div className="mb-2.5 flex-none rounded-[14px] bg-white px-[19px] py-[13px] text-[16px] leading-[1.5] text-gray-400">
                {data.intro.map((l, i) => (
                  <div key={i}>{l}</div>
                ))}
              </div>
            ) : null}

            {data.summary.pending > 0 ? (
              <div className="mb-2.5 flex-none rounded-[14px] border-l-4 border-primary-500 bg-primary-50 px-[19px] py-[11px] text-[17px]">
                답을 기다리는 질문이 {data.summary.pending}개 있습니다.
                답해 주시면 기록을 더 정확하게 남길 수 있습니다.
              </div>
            ) : null}

            <div className="flex-1 overflow-y-auto pr-1">
              {data.items.length === 0 ? (
                <div className="flex h-full items-center justify-center text-[19px] text-gray-300">
                  기록된 이벤트가 없습니다.
                </div>
              ) : (
                data.items.map((raw) => {
                  const e = patched[raw.id] ?? raw;
                  return (
                  <EventRow
                    key={e.id}
                    event={e}
                    busy={answering === e.id}
                    onAnswer={(v) => void answer(e.id, v)}
                  />
                  );
                })
              )}
            </div>
          </div>
        ) : null}
      </div>

      {result ? (
        <GuidanceCard
          result={result}
          onClose={() => setResult(null)}
          onInspect={() => {
            setPicking(result);
            setResult(null);
          }}
          onSkip={() => {
            const id = result.event.id;
            setResult(null);
            void answer(id, "none", false, { silent: true });
          }}
        />
      ) : null}

      {picking?.next?.products?.length ? (
        <ProductPicker
          title="어떤 제품을 확인할까요?"
          products={picking.next.products.map((p) => ({
            user_product_id: p.user_product_id,
            name: p.name,
            brand: p.brand,
            score: p.score,
            band: p.band,
          }))}
          multi
          confirmLabel="확인 시작"
          onPick={(ids) => {
            const eid = picking.event.id;
            setPicking(null);
            onProduct(ids, eid);
          }}
          onClose={() => setPicking(null)}
        />
      ) : null}

      {answerError ? (
        <div className="absolute inset-0 z-10 flex items-center justify-center bg-black/35 p-10">
          <div className="w-full max-w-[720px] rounded-[18px] bg-white p-[22px]">
            <div className="text-[22px] font-bold">답변을 저장하지 못했습니다</div>
            <div className="mt-1 text-[17px] text-gray-400">{answerError.summary}</div>
            <div className="mt-2 rounded bg-gray-100 p-2 font-mono text-[13px] break-all">
              {answerError.url}
            </div>
            <button
              onClick={() => setAnswerError(null)}
              className="mt-3 h-[56px] w-full rounded-[14px] bg-primary-500 text-[19px] font-semibold text-white"
            >
              닫기
            </button>
          </div>
        </div>
      ) : null}

      <TabBar active={activeTab} onChange={onTab} />
    </div>
  );
}

// ── 이벤트 한 줄 ─────────────────────────────────────────────

function EventRow({
  event,
  busy,
  onAnswer,
}: {
  event: CareEvent;
  busy: boolean;
  onAnswer: (v: "external_source" | "none") => void;
}) {
  const isVoc = event.event_type === "voc_spike";

  return (
    <div
      className={
        "mb-2.5 rounded-[15px] p-[15px_19px] " +
        (event.excluded ? "bg-gray-100" : "bg-white")
      }
    >
      <div className="flex items-baseline gap-2.5">
        <span
          className="h-2.5 w-2.5 flex-none rounded-full"
          style={{ background: event.excluded ? "#c9ced6" : isVoc ? STATUS.amber : STATUS.red }}
        />
        <span className="text-[19px] font-bold">{event.title}</span>
        <span className="text-[16px] text-gray-300">{event.when}</span>

        {event.excluded ? (
          <span className="ml-auto rounded-full bg-gray-200 px-2.5 py-0.5 text-[14px] text-gray-400">
            분석 제외
          </span>
        ) : null}
      </div>

      <div className="mt-1 text-[17px] text-gray-400">{event.detail}</div>

      {/* 아직 답하지 않은 건만 질문이 온다. 답한 건은 question이 null이다. */}
      {event.question ? (
        <div className="mt-2.5 rounded-[13px] bg-primary-50 p-[13px_15px]">
          <div className="text-[18px] font-semibold">{event.question}</div>
          <div className="mt-2 flex gap-2">
            <button
              disabled={busy}
              onClick={() => onAnswer("external_source")}
              className="h-[54px] flex-1 rounded-[13px] bg-primary-500 text-[18px] font-semibold text-white disabled:opacity-50"
            >
              네
            </button>
            <button
              disabled={busy}
              onClick={() => onAnswer("none")}
              className="h-[54px] flex-1 rounded-[13px] border border-gray-200 bg-white text-[18px] font-semibold text-gray-400 disabled:opacity-50"
            >
              아니요
            </button>
          </div>
          {busy ? (
            <div className="mt-1.5 text-[15px] text-gray-300">저장하는 중…</div>
          ) : null}
        </div>
      ) : event.status ? (
        // 문구는 서버가 만든다. 화면에서 조립하면 규칙이 두 곳에 흩어진다.
        <div className="mt-1 text-[15px] font-medium text-primary-500">
          {event.status}
        </div>
      ) : null}
    </div>
  );
}

// ── 답변 후 안내 ─────────────────────────────────────────────

function GuidanceCard({
  result,
  onClose,
  onInspect,
  onSkip,
}: {
  result: EventAnswerResponse;
  onClose: () => void;
  onInspect: () => void;
  onSkip: () => void;
}) {
  const canInspect = Boolean(result.next?.products?.length);
  return (
    <div className="absolute inset-0 z-10 flex items-center justify-center bg-black/35 p-8">
      <div className="w-full max-w-[760px] rounded-[18px] bg-white p-[24px]">
        <div className="text-[24px] font-bold">{result.headline}</div>

        <div className="mt-2 space-y-1">
          {result.lines.map((l, i) => (
            <p key={i} className="text-[18px] leading-[1.5] text-gray-400">
              {l}
            </p>
          ))}
        </div>

        {canInspect ? (
          <div className="mt-4 flex gap-2">
            <button
              onClick={onSkip}
              className="h-[58px] flex-1 rounded-[14px] border border-gray-200 text-[19px] font-semibold text-gray-400"
            >
              지금은 괜찮아요
            </button>
            <button
              onClick={onInspect}
              className="h-[58px] flex-1 rounded-[14px] bg-primary-500 text-[19px] font-semibold text-white"
            >
              확인해 볼게요
            </button>
          </div>
        ) : (
          <button
            onClick={onClose}
            className="mt-4 h-[58px] w-full rounded-[14px] bg-primary-500 text-[19px] font-semibold text-white"
          >
            닫기
          </button>
        )}
      </div>
    </div>
  );
}

export default EventsScreen;