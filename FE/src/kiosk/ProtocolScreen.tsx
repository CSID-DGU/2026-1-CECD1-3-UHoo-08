import { useState } from "react";
import { TopBar, TabBar, ErrorPanel, Loading, BAND_STYLE, type TabKey } from "./ui";
import { careGet, carePost } from "./lib/careApi";
import { KIOSK_USER_ID, KioskApiError } from "./lib/kioskApi";
import { useKioskQuery } from "./lib/useKioskQuery";
import type { InspectionResponse, ProtocolResponse } from "./lib/types";

/**
 * 확인 절차
 *
 * ── "확인해 보세요"만으로는 부족하다 ─────────────────────────
 * 무엇을 어떻게 볼지 순서대로 알려준다. 색을 봐야 하는 제품과 냄새를
 * 맡아야 하는 제품이 다르고, 순서도 다르다.
 *
 * 항목은 임의로 만든 것이 아니라 식약처 「화장품 안정성시험 가이드라인」의
 * 시험항목을 소비자가 확인 가능한 형태로 옮긴 것이다. 각 줄에 근거가 된
 * 시험항목을 함께 보여주는 이유가 그것이다.
 *
 * ── 판정은 사용자가 한다 ─────────────────────────────────────
 * 시스템은 무엇을 볼지 알려줄 뿐이고, 결과는 사용자가 고른다.
 * 그 답을 받아 기록하고, 다음 점검의 기준으로 삼는다.
 */

type Props = {
  userProductId: string;
  /**
   * 이 확인이 어느 이상 이벤트에서 이어진 것인지.
   * 이벤트 이력에서 들어왔다면 채워지고, 점검 목록에서 바로 들어왔다면 없다.
   * 채워져 있으면 확인을 마칠 때 그 이벤트가 완료로 바뀐다.
   */
  eventId?: number | null;
  activeTab: TabKey;
  onTab: (t: TabKey) => void;
  onBack: () => void;
  /** 색 항목에서 AS7341 측정으로 넘어갈 때 */
  onMeasure?: (userProductId: string) => void;
};

export function ProtocolScreen({
  userProductId,
  eventId,
  activeTab,
  onTab,
  onBack,
  onMeasure,
}: Props) {
  // 한 번 받으면 바뀌지 않는 값이라 폴링하지 않는다.
  const protocol = useKioskQuery<ProtocolResponse>(
    () =>
      careGet<ProtocolResponse>(`/api/care/products/${userProductId}/protocol`, {
        user_id: KIOSK_USER_ID,
      }),
    60 * 60_000,
    [userProductId]
  );

  const { data, error, loading } = protocol;

  const [done, setDone] = useState<Record<number, boolean>>({});
  const [saving, setSaving] = useState(false);
  const [result, setResult] = useState<InspectionResponse | null>(null);
  const [saveError, setSaveError] = useState<KioskApiError | null>(null);

  // 여러 항목을 고를 수 있다. 냄새도 나고 층도 분리됐다면 둘 다 골라야 한다.
  const [picked, setPicked] = useState<string[]>([]);

  const toggle = (a: string) => {
    setPicked((prev) => {
      const isOk = a === "이상 없음";
      if (prev.includes(a)) return prev.filter((x) => x !== a);
      // "이상 없음"과 다른 항목은 함께 고를 수 없다. 서로 모순이다.
      if (isOk) return [a];
      return [...prev.filter((x) => x !== "이상 없음"), a];
    });
  };

  const submit = async () => {
    if (picked.length === 0) return;
    setSaving(true);
    setSaveError(null);
    try {
      const res = await carePost<InspectionResponse>(
        `/api/care/products/${userProductId}/inspection`,
        { answers: picked, event_id: eventId ?? null },
        { user_id: KIOSK_USER_ID }
      );
      setResult(res);
    } catch (e) {
      setSaveError(e instanceof KioskApiError ? e : new KioskApiError(String(e), "-", null));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex h-full flex-col">
      <TopBar
        left={
          <button onClick={onBack} className="text-[25px] font-bold">
            ← 확인 절차
          </button>
        }
        right={data?.label}
      />

      <div className="flex-1 overflow-hidden px-[26px] py-[16px]">
        {loading && !data ? (
          <Loading label="확인 항목을 불러오는 중" />
        ) : error && !data ? (
          <ErrorPanel error={error} onRetry={protocol.refetch} />
        ) : data ? (
          <div className="flex h-full flex-col">
            <Header data={data} />

            <div className="mt-2.5 flex-1 overflow-y-auto pr-1">
              {data.steps.map((s) => (
                <div
                  key={s.order}
                  className={
                    "mb-2 flex items-start gap-3 rounded-[14px] p-[13px_17px] " +
                    (done[s.order] ? "bg-primary-50" : "bg-white")
                  }
                >
                  {/* 눌러서 확인 표시. 여러 항목을 순서대로 보다가
                      어디까지 봤는지 잊기 쉽다. */}
                  <button
                    onClick={() => setDone((d) => ({ ...d, [s.order]: !d[s.order] }))}
                    className={
                      "grid h-9 w-9 flex-none place-items-center rounded-full text-[17px] font-bold " +
                      (done[s.order]
                        ? "bg-primary-500 text-white"
                        : "border border-gray-200 text-gray-300")
                    }
                  >
                    {done[s.order] ? "✓" : s.order}
                  </button>

                  <div className="min-w-0 flex-1">
                    <div className="text-[18px] leading-[1.45]">{s.text}</div>
                    <div className="mt-0.5 text-[14px] text-gray-300">
                      식약처 가이드라인 · {s.basis}
                    </div>
                  </div>

                  {/* 색 관련 항목은 기계가 사람보다 잘 본다. */}
                  {s.optical && onMeasure ? (
                    <button
                      onClick={() => onMeasure(userProductId)}
                      className="h-[42px] flex-none rounded-[11px] border border-primary-500 px-3.5 text-[15px] font-semibold text-primary-500"
                    >
                      측정하기
                    </button>
                  ) : null}
                </div>
              ))}

              {data.caution ? (
                <div className="mb-2 rounded-[14px] border-l-4 border-[#E05A5A] bg-[#FBE9E9] p-[13px_17px] text-[17px] leading-[1.5]">
                  {data.caution}
                </div>
              ) : null}

              {data.note ? (
                <div className="mb-2 text-[15px] leading-[1.5] text-gray-300">
                  {data.note}
                </div>
              ) : null}
            </div>

            <div className="mt-2 flex-none">
              <div className="mb-1.5 text-[16px] text-gray-300">
                해당하는 것을 모두 선택해 주세요 (여러 개 선택 가능)
              </div>
              <div className="flex gap-2">
                {data.answers.map((a) => {
                  const on = picked.includes(a);
                  return (
                    <button
                      key={a}
                      disabled={saving}
                      onClick={() => toggle(a)}
                      className={
                        "flex h-[58px] flex-1 items-center justify-center gap-2 rounded-[14px] text-[18px] font-semibold disabled:opacity-50 " +
                        (on
                          ? "bg-primary-500 text-white"
                          : "border border-gray-200 bg-white text-gray-400")
                      }
                    >
                      <span
                        className={
                          "grid h-6 w-6 flex-none place-items-center rounded-md text-[14px] " +
                          (on ? "bg-white/25" : "border border-gray-200")
                        }
                      >
                        {on ? "✓" : ""}
                      </span>
                      {a}
                    </button>
                  );
                })}
              </div>

              <button
                disabled={saving || picked.length === 0}
                onClick={() => void submit()}
                className="mt-2 h-[58px] w-full rounded-[14px] bg-primary-500 text-[19px] font-semibold text-white disabled:bg-gray-200 disabled:text-gray-300"
              >
                {saving
                  ? "확인하는 중…"
                  : picked.length === 0
                    ? "위에서 선택해 주세요"
                    : `선택 완료 (${picked.length}개)`}
              </button>
            </div>
          </div>
        ) : null}
      </div>

      {result ? (
        <ResultCard result={result} onClose={onBack} />
      ) : null}

      {saveError ? (
        <div className="absolute inset-0 z-10 flex items-center justify-center bg-black/35 p-10">
          <div className="w-full max-w-[720px] rounded-[18px] bg-white p-[22px]">
            <div className="text-[22px] font-bold">기록하지 못했습니다</div>
            <div className="mt-1 text-[17px] text-gray-400">{saveError.summary}</div>
            <div className="mt-2 rounded bg-gray-100 p-2 font-mono text-[13px] break-all">
              {saveError.url}
            </div>
            <button
              onClick={() => setSaveError(null)}
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

function Header({ data }: { data: ProtocolResponse }) {
  const style = data.band ? BAND_STYLE[data.band] : null;

  return (
    <div className="flex-none rounded-[15px] bg-white p-[15px_19px]">
      <div className="flex items-center gap-3">
        {style ? (
          <span
            className="grid h-11 w-11 flex-none place-items-center rounded-[12px] text-[21px]"
            style={{ background: style.pill }}
          >
            {style.emoji}
          </span>
        ) : null}

        <div className="min-w-0">
          <div className="truncate text-[21px] font-bold">
            {data.name || "이름 없는 제품"}
          </div>
          {data.reasons.length ? (
            <div className="mt-0.5 truncate text-[15px] text-gray-300">
              {data.reasons.join(" · ")}
            </div>
          ) : null}
        </div>

        {data.score != null && style ? (
          <div className="ml-auto flex-none text-right">
            <div className="text-[26px] font-bold tabular-nums" style={{ color: style.text }}>
              {Math.round(data.score)}
            </div>
            <div className="text-[13px] text-gray-300">점검 순위 점수</div>
          </div>
        ) : null}
      </div>
    </div>
  );
}

function ResultCard({
  result,
  onClose,
}: {
  result: InspectionResponse;
  onClose: () => void;
}) {
  return (
    <div className="absolute inset-0 z-10 flex items-center justify-center bg-black/35 p-8">
      <div className="flex max-h-full w-full max-w-[760px] flex-col rounded-[18px] bg-white p-[24px]">
        <div className="flex-none text-[24px] font-bold">{result.headline}</div>

        <div className="my-3 min-h-0 flex-1 overflow-y-auto pr-1">
          {/* 고른 항목마다 하나씩. 여러 개를 골랐으면 여러 개가 나온다.
              하나만 보여주면 나머지는 못 본 것이 된다. */}
          {result.sections.map((sec) => (
            <div
              key={sec.label}
              className="mb-2 rounded-[14px] border-l-4 border-[#E8A93B] bg-[#FDF3E7] p-[14px_17px]"
            >
              <div className="text-[18px] font-bold">{sec.label}</div>
              <div className="mt-1 space-y-0.5">
                {sec.lines.map((l, i) => (
                  <p key={i} className="text-[17px] leading-[1.5]">
                    {l}
                  </p>
                ))}
              </div>
            </div>
          ))}

          {result.lines.map((l, i) => (
            <p key={i} className="mt-1 text-[17px] leading-[1.5] text-gray-400">
              {l}
            </p>
          ))}

          {/* 교체를 권할 상황이어도 "버리세요"라고 쓰지 않는다.
              판단은 사용자가 한다. */}
          {result.recommend_replace ? (
            <div className="mt-2 rounded-[13px] bg-primary-50 p-[13px_16px] text-[17px] leading-[1.5]">
              새 제품으로 바꾸시는 편이 좋겠습니다. 추천 탭에서 비슷한 제품을
              보실 수 있습니다.
            </div>
          ) : null}
        </div>

        <button
          onClick={onClose}
          className="h-[58px] flex-none rounded-[14px] bg-primary-500 text-[19px] font-semibold text-white"
        >
          확인
        </button>
      </div>
    </div>
  );
}

export default ProtocolScreen;