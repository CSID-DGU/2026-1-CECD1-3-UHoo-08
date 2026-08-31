import { useState } from "react";
import { TopBar, TabBar, MeasureError, STATUS, type TabKey } from "./ui";
import { measureApi } from "./lib/careApi";
import { useMeasureSession } from "./lib/useMeasureSession";
import type { MeasureSession } from "./lib/types";

/**
 * 피부 측정
 *
 * ── 화장품 측정과 같은 것, 다른 것 ───────────────────────────
 * 절차는 같다. 백색 표준판으로 조명 기준을 잡고, 대상을 재고, 서버가
 * 두 값을 합쳐 하나의 측정으로 만든다. 그 부분은 useMeasureSession이
 * 두 화면에 공통으로 쓰인다.
 *
 * 다른 것은 무엇을 내놓느냐다. 화장품은 "처음 잰 색과 몇 % 다른가" 하나면
 * 되지만, 피부는 밝기(ITA°)와 붉은기(홍반 지수)가 따로 움직인다. 햇볕에
 * 그을리면 ITA°가 내려가고, 자극을 받으면 홍반이 오른다. 둘은 서로 다른
 * 이야기라 한 숫자로 합칠 수 없다.
 *
 * ── 부위를 먼저 고르는 이유 ──────────────────────────────────
 * 손등과 볼은 색이 다르다. 부위를 섞어 재면 어제 볼을 재고 오늘 손등을
 * 잰 차이가 피부 변화로 보인다. 그래서 부위가 측정의 일부이고, 첫 화면이
 * 그것을 정하는 화면이다. 자유 입력을 받지 않는 이유도 같다 — "손등"과
 * "손등 안쪽"이 다른 부위로 쌓이면 한 사람의 추이가 둘로 갈린다.
 *
 * ── 절대값으로 판정하지 않는다 ───────────────────────────────
 * ITA° 41이 좋다거나 나쁘다고 말할 수 없다. 사람마다 타고난 값이 다르다.
 * 결과 화면이 보여주는 것은 값과, 같은 부위 직전 측정과의 차이뿐이다.
 * 피부 나이 같은 것은 산출하지 않는다.
 */

/** 부위별 밀착 안내. 어디를 어떻게 대야 같은 자리가 재지는지. */
const SITE_GUIDE: Record<string, string> = {
  "손등 안쪽": "엄지와 검지 사이 도톰한 곳에 대세요. 힘줄이 도드라진 자리는 피합니다.",
  "볼": "광대뼈 가장 높은 곳에서 손가락 두 마디 아래에 대세요.",
  "이마": "눈썹 위 손가락 세 마디, 얼굴 한가운데에 대세요.",
  "팔 안쪽": "팔꿈치 안쪽에서 손목 쪽으로 손바닥 하나 내려온 곳에 대세요.",
};

const FALLBACK_SITES = ["손등 안쪽", "볼", "이마", "팔 안쪽"];

type Props = {
  /** 서버가 정한 부위 목록. 없으면 기본값을 쓴다. */
  siteOptions: string[];
  /** 재 본 적 있는 부위. 이어서 재도록 앞에 표시한다. */
  knownSites: string[];
  activeTab: TabKey;
  onTab: (t: TabKey) => void;
  /** 돌아갈 곳. 호출한 쪽이 피부 탭을 다시 부른다. */
  onBack: () => void;
};

export function SkinRunScreen({
  siteOptions,
  knownSites,
  activeTab,
  onTab,
  onBack,
}: Props) {
  const sites = siteOptions.length ? siteOptions : FALLBACK_SITES;
  const [site, setSite] = useState<string | null>(null);

  const m = useMeasureSession(() => measureApi.startSkin(site!), onBack);
  const { session, busy, error, elapsed, stalled, phase } = m;

  return (
    <div className="flex h-full flex-col">
      <TopBar
        left={
          <button onClick={m.leave} className="text-[25px] font-bold">
            ← 피부
          </button>
        }
        right={site ?? "피부 측정"}
      />

      <Steps phase={phase} step={session?.step ?? null} />

      <div className="flex-1 overflow-y-auto px-[26px] pb-[16px]">
        {phase === "intro" ? (
          <Intro
            sites={sites}
            knownSites={knownSites}
            site={site}
            busy={busy}
            onPick={setSite}
            onStart={m.begin}
          />
        ) : phase === "run" ? (
          <Run
            session={session!}
            busy={busy}
            stalled={stalled}
            elapsed={elapsed}
            onCapture={m.capture}
            onCancel={m.leave}
          />
        ) : (
          <Result session={session!} onRetry={m.restart} onClose={m.leave} />
        )}

        {error ? <MeasureError error={error} onClose={m.clearError} /> : null}
      </div>

      <TabBar active={activeTab} onChange={onTab} />
    </div>
  );
}

// ── 단계 표시 ────────────────────────────────────────────────

function Steps({
  phase,
  step,
}: {
  phase: "intro" | "run" | "result";
  step: "white" | "sample" | null;
}) {
  const current =
    phase === "intro" ? 0 : phase === "result" ? 3 : step === "white" ? 1 : 2;
  const labels = ["부위 선택", "백색 표준판", "피부", "결과"];

  return (
    <div className="flex flex-none items-center gap-2 px-[26px] py-[12px]">
      {labels.map((label, i) => {
        const on = i === current;
        const passed = i < current;
        return (
          <div
            key={label}
            className={
              "flex h-[38px] flex-1 items-center justify-center gap-2 rounded-[11px] text-[16px] font-semibold " +
              (on
                ? "bg-primary-500 text-white"
                : passed
                  ? "bg-primary-50 text-primary-500"
                  : "bg-white text-gray-300")
            }
          >
            <span>{passed ? "✓" : i + 1}</span>
            {label}
          </div>
        );
      })}
    </div>
  );
}

// ── 1단계: 부위 선택 + 밀착 안내 ─────────────────────────────

function Intro({
  sites,
  knownSites,
  site,
  busy,
  onPick,
  onStart,
}: {
  sites: string[];
  knownSites: string[];
  site: string | null;
  busy: boolean;
  onPick: (s: string) => void;
  onStart: () => void;
}) {
  return (
    <div className="rounded-[16px] bg-white p-[24px]">
      <div className="text-[26px] font-bold">어디를 잴까요?</div>
      <div className="mt-1.5 text-[18px] text-gray-300">
        부위마다 색이 달라서, 다음에도 같은 자리를 재야 변화를 비교할 수 있습니다.
      </div>

      <div className="mt-4 grid grid-cols-2 gap-2">
        {sites.map((s) => {
          const on = s === site;
          const known = knownSites.includes(s);
          return (
            <button
              key={s}
              onClick={() => onPick(s)}
              className={
                "flex h-[74px] items-center justify-between rounded-[14px] border px-[20px] text-left " +
                (on
                  ? "border-primary-500 bg-primary-50"
                  : "border-gray-200 bg-white active:bg-primary-50")
              }
            >
              <span className="text-[20px] font-semibold">{s}</span>
              {/* 이미 재 본 부위를 표시한다. 이어서 재야 추이가 쌓인다. */}
              {known ? (
                <span className="text-[15px] font-medium text-primary-500">
                  이력 있음
                </span>
              ) : (
                <span className="text-[15px] text-gray-300">처음</span>
              )}
            </button>
          );
        })}
      </div>

      {site ? (
        <div className="mt-4 rounded-[13px] bg-primary-50 p-[16px_18px]">
          <div className="text-[17px] font-bold">밀착 안내</div>
          <div className="mt-1 text-[18px] leading-[1.6]">{SITE_GUIDE[site]}</div>
          <div className="mt-2 text-[16px] leading-[1.55] text-gray-400">
            차광 커버가 피부에 완전히 닿아야 합니다. 틈이 있으면 방 조명이 새어
            들어와 잰 값이 그만큼 밝아집니다.
          </div>
        </div>
      ) : null}

      {site && !knownSites.includes(site) ? (
        <div className="mt-2 text-[16px] leading-[1.55] text-gray-300">
          이 부위는 처음입니다. 이번 측정이 기준선이 되고, 변화는 다음 측정부터
          보여드립니다.
        </div>
      ) : null}

      <button
        disabled={busy || !site}
        onClick={onStart}
        className="mt-5 h-[68px] w-full rounded-[14px] bg-primary-500 text-[21px] font-semibold text-white disabled:bg-gray-200 disabled:text-gray-300"
      >
        {busy
          ? "측정 노드를 부르는 중…"
          : site
            ? "측정 시작"
            : "부위를 골라 주세요"}
      </button>
    </div>
  );
}

// ── 2·3단계: 백색 표준판 / 피부 ──────────────────────────────

function Run({
  session,
  busy,
  stalled,
  elapsed,
  onCapture,
  onCancel,
}: {
  session: MeasureSession;
  busy: boolean;
  stalled: boolean;
  elapsed: number;
  onCapture: () => void;
  onCancel: () => void;
}) {
  const white = session.step === "white";
  const site = session.site ?? "피부";

  return (
    <div className="rounded-[16px] bg-white p-[24px]">
      <div className="text-[27px] font-bold">
        {white ? "백색 표준판을 올려 주세요" : `${site}에 대 주세요`}
      </div>

      {/* 문구는 서버가 만든 것을 그대로 쓴다. 상태와 안내가 어긋나면
          화면이 서버보다 앞서 나간 것처럼 보인다. */}
      <div className="mt-2 text-[19px] leading-[1.6] text-gray-400">
        {session.message}
      </div>

      <div className="mt-3 text-[17px] leading-[1.6] text-gray-300">
        {white
          ? "피부를 재기 전에 조명 기준을 먼저 잡습니다. 이 값이 없으면 방이 밝은지 어두운지가 그대로 피부색이 됩니다."
          : SITE_GUIDE[site] ?? "차광 커버가 완전히 닿도록 밀착시켜 주세요."}
      </div>

      <div className="mt-5">
        {session.capturing ? (
          <div className="rounded-[14px] bg-primary-50 p-[20px] text-center">
            <div className="text-[21px] font-semibold text-primary-500">
              재는 중… {elapsed}초
            </div>
            <div className="mt-1 text-[17px] text-gray-400">
              {white ? "측정부를 건드리지 마세요." : "그대로 대고 계세요."}
            </div>
          </div>
        ) : (
          <button
            disabled={busy || !session.awaiting_tap}
            onClick={onCapture}
            className="h-[74px] w-full rounded-[14px] bg-primary-500 text-[22px] font-semibold text-white disabled:bg-gray-200 disabled:text-gray-300"
          >
            {busy ? "전달하는 중…" : white ? "백색 표준판 측정" : "피부 측정"}
          </button>
        )}
      </div>

      {stalled ? (
        <div
          className="mt-3 rounded-[14px] border-l-4 bg-[#FDF3E7] p-[15px_18px]"
          style={{ borderColor: STATUS.amber }}
        >
          <div className="text-[19px] font-bold">측정 노드가 응답하지 않습니다</div>
          <div className="mt-1 text-[17px] leading-[1.55] text-gray-400">
            {session.node_label ?? session.node_id}의 전원과 Wi-Fi를 확인해 주세요.
            {elapsed}초째 기다리고 있습니다.
          </div>
        </div>
      ) : null}

      <button
        onClick={onCancel}
        className="mt-3 h-[56px] w-full rounded-[14px] border border-gray-200 text-[18px] font-semibold text-gray-400"
      >
        측정 중단
      </button>
    </div>
  );
}

// ── 4단계: 결과 ──────────────────────────────────────────────

/**
 * 첫 측정은 기준선이라 변화량을 말하지 않는다.
 *
 * 비교할 대상이 없는데 "변화 없음"이라고 쓰면 안정적이라는 뜻으로 읽힌다.
 * 사실은 아직 아무것도 모르는 상태다.
 */
function Result({
  session,
  onRetry,
  onClose,
}: {
  session: MeasureSession;
  onRetry: () => void;
  onClose: () => void;
}) {
  const ok = session.status === "done";
  const skin = session.skin;
  const baseline = ok && session.baseline === true;

  return (
    <div className="rounded-[16px] bg-white p-[24px]">
      {!ok ? (
        <>
          <div className="text-[26px] font-bold">측정을 마치지 못했습니다</div>
          <div className="mt-2 text-[19px] leading-[1.6] text-gray-400">
            {session.message}
          </div>
        </>
      ) : (
        <>
          <div className="text-[26px] font-bold">
            {baseline ? "기준선을 잡았습니다" : `${skin?.site ?? "피부"} 측정 결과`}
          </div>

          {skin ? (
            <div className="mt-4 grid grid-cols-2 gap-2">
              <Metric
                label="ITA°"
                sub={skin.ita_class ?? "—"}
                value={skin.ita != null ? skin.ita.toFixed(1) : "—"}
                delta={baseline ? null : skin.ita_delta}
                deltaHint="내려가면 그을린 것"
              />
              <Metric
                label="홍반 지수"
                sub="붉은기 (a*)"
                value={skin.erythema != null ? skin.erythema.toFixed(1) : "—"}
                delta={baseline ? null : skin.erythema_delta}
                deltaHint="올라가면 붉어진 것"
              />
            </div>
          ) : null}

          {baseline ? (
            <div className="mt-4 rounded-[13px] bg-primary-50 p-[16px_18px] text-[18px] leading-[1.6]">
              이번 측정은 비교할 대상이 없어 그 자체가 기준이 됩니다. 다음에 같은
              부위를 재면 얼마나 달라졌는지 알려드릴게요.
            </div>
          ) : (
            <div className="mt-4 rounded-[13px] bg-primary-50 p-[16px_18px] text-[18px] leading-[1.6]">
              값 자체로 피부가 좋다 나쁘다를 말하지 않습니다. 사람마다 타고난 값이
              달라서, 같은 자리를 반복해서 잰 변화만 의미가 있습니다.
            </div>
          )}

          {skin && skin.measured_n > 0 ? (
            <div className="mt-3 text-[16px] leading-[1.55] text-gray-300">
              {skin.site} {skin.measured_n}번째 측정입니다. 피부 탭에서 추이를 볼 수
              있습니다.
            </div>
          ) : null}
        </>
      )}

      <div className="mt-5 flex gap-2">
        <button
          onClick={onRetry}
          className="h-[64px] flex-1 rounded-[14px] border border-primary-500 text-[19px] font-semibold text-primary-500"
        >
          다시 측정
        </button>
        <button
          onClick={onClose}
          className="h-[64px] flex-1 rounded-[14px] bg-primary-500 text-[19px] font-semibold text-white"
        >
          확인
        </button>
      </div>
    </div>
  );
}

function Metric({
  label,
  sub,
  value,
  delta,
  deltaHint,
}: {
  label: string;
  sub: string;
  value: string;
  delta: number | null | undefined;
  deltaHint: string;
}) {
  return (
    <div className="rounded-[14px] bg-primary-50 p-[18px_20px]">
      <div className="text-[16px] font-medium text-gray-400">{label}</div>
      <div className="mt-0.5 text-[44px] font-bold leading-none tabular-nums text-primary-500">
        {value}
      </div>
      <div className="mt-1 text-[15px] text-gray-300">{sub}</div>
      {delta != null ? (
        <div className="mt-2 text-[17px] font-semibold">
          직전 대비 {delta > 0 ? "+" : ""}
          {delta.toFixed(1)}
          <span className="ml-1 text-[14px] font-normal text-gray-300">
            {deltaHint}
          </span>
        </div>
      ) : (
        <div className="mt-2 text-[15px] text-gray-300">직전 비교 없음</div>
      )}
    </div>
  );
}

export default SkinRunScreen;
