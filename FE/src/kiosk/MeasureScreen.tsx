import { TopBar, TabBar, MeasureError, STATUS, type TabKey } from "./ui";
import { measureApi } from "./lib/careApi";
import { useMeasureSession, type MeasurePhase } from "./lib/useMeasureSession";
import type { MeasureSession, MeasureStartResponse } from "./lib/types";

/**
 * 광학 측정
 *
 * ── 왜 백색 표준판을 먼저 재는가 ─────────────────────────────
 * AS7341이 주는 채널값은 그 순간의 조명 밝기에 그대로 비례한다. 같은
 * 제품을 밝은 데서 재면 값이 전부 커진다. 흰 기준판을 함께 재서 그것으로
 * 나누면 조명이 달라져도 비교할 수 있는 값이 된다. 이 단계를 건너뛰면
 * 나중에 나오는 변화율이 제품의 변화가 아니라 조명의 변화가 된다.
 *
 * ── 왜 화면에서 눌러야 하는가 ────────────────────────────────
 * 측정 노드는 측정부에 무엇이 올라와 있는지 알 수 없다. 그것을 아는 사람은
 * 방금 손으로 올려놓은 사용자뿐이다. 그래서 "올려놓았습니다"를 여기서
 * 누르고, 노드는 그 신호를 폴링으로 받아 잰다. 누르기 전에 재면 아직
 * 아무것도 없는 측정부를 재게 되고, 그 값이 기준값으로 굳는다.
 *
 * ── 네 단계 ──────────────────────────────────────────────────
 *   안내 → 백색 표준판 → 제품 → 결과
 * 상태는 서버의 세션이 가지고 있고 이 화면은 그것을 따라 그린다.
 * 화면이 따로 단계를 세면 새로고침이나 잠깐의 통신 실패로 어긋난다.
 *
 * ── 결과는 변화율까지만 말한다 ───────────────────────────────
 * 몇 %부터 문제인지는 여기서 정하지 않는다. 그 판단은 점검 순위가 다른
 * 근거와 함께 종합해서 하고, 이 화면은 "얼마나 달라졌는지"에서 멈춘다.
 */

/**
 * 제형별 안내. services/iot/optical.py의 GRADE_GUIDE를 옮긴 것이다.
 * 한쪽을 고치면 반드시 양쪽을 고쳐야 한다.
 *
 * 서버도 시작 요청에서 같은 판정을 하고 unsuitable이면 422로 끊는다.
 * 여기서 미리 막는 것은 쓸모없는 측정을 시작시키지 않기 위해서이고,
 * 서버 쪽이 최종 방어선이다.
 */
const GRADE_NOTE: Record<string, string> = {
  suitable: "색이 있는 제형이라 변화를 재기 좋습니다.",
  conditional: "반투명 제형이라 변화가 작게 나올 수 있습니다.",
  unsuitable: "투명한 제형이라 색으로는 변화를 재기 어렵습니다.",
};

export type MeasureTarget = {
  user_product_id: string;
  name: string | null;
  brand: string | null;
  /** product_thermal_profile.optical_grade. 모르면 null. */
  optical_grade: string | null;
};

type Props = {
  target: MeasureTarget | null;
  activeTab: TabKey;
  onTab: (t: TabKey) => void;
  /** 돌아갈 곳. 호출한 쪽이 점검 순위를 다시 부른다. */
  onBack: () => void;
  /** 돌아갈 곳의 이름. "점검 우선순위" 또는 "확인 절차". */
  backLabel: string;
};

export function MeasureScreen({ target, activeTab, onTab, onBack, backLabel }: Props) {
  const m = useMeasureSession(
    () => measureApi.start(target!.user_product_id),
    onBack
  );
  const { session, start, busy, error, elapsed, stalled, phase } = m;

  const blocked = target?.optical_grade === "unsuitable";

  return (
    <div className="flex h-full flex-col">
      <TopBar
        left={
          <button onClick={m.leave} className="text-[25px] font-bold">
            ← {backLabel}
          </button>
        }
        right={target?.name ?? "광학 측정"}
      />

      <Steps phase={phase} step={session?.step ?? null} />

      <div className="flex-1 overflow-y-auto px-[26px] pb-[16px]">
        {!target ? (
          <Centered
            title="측정할 제품이 선택되지 않았습니다"
            lines={["점검 목록에서 제품을 골라 주세요."]}
          />
        ) : phase === "intro" ? (
          <Intro
            target={target}
            blocked={blocked}
            busy={busy}
            onStart={m.begin}
            onBack={m.leave}
          />
        ) : phase === "run" ? (
          <Run
            session={session!}
            start={start}
            busy={busy}
            stalled={stalled}
            elapsed={elapsed}
            onCapture={m.capture}
            onCancel={m.leave}
          />
        ) : (
          <Result
            session={session!}
            onRetry={m.restart}
            onClose={m.leave}
          />
        )}

        {error ? <MeasureError error={error} onClose={m.clearError} /> : null}
      </div>

      <TabBar active={activeTab} onChange={onTab} />
    </div>
  );
}

// ── 단계 표시 ────────────────────────────────────────────────

/**
 * 네 단계 중 어디인지.
 *
 * 측정이 두 번이라는 것을 미리 보여주지 않으면, 백색 표준판을 재고 나서
 * "끝났나?" 하고 자리를 뜬다. 그러면 세션이 시한까지 열린 채 남는다.
 */
function Steps({ phase, step }: { phase: MeasurePhase; step: "white" | "sample" | null }) {
  const current =
    phase === "intro" ? 0 : phase === "result" ? 3 : step === "white" ? 1 : 2;

  const labels = ["안내", "백색 표준판", "제품", "결과"];

  return (
    <div className="flex flex-none items-center gap-2 px-[26px] py-[12px]">
      {labels.map((label, i) => {
        const on = i === current;
        const passed = i < current;
        return (
          <div key={label} className="flex flex-1 items-center gap-2">
            <div
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
          </div>
        );
      })}
    </div>
  );
}

// ── 1단계: 안내 ──────────────────────────────────────────────

function Intro({
  target,
  blocked,
  busy,
  onStart,
  onBack,
}: {
  target: MeasureTarget;
  blocked: boolean;
  busy: boolean;
  onStart: () => void;
  onBack: () => void;
}) {
  const note = target.optical_grade ? GRADE_NOTE[target.optical_grade] : null;

  if (blocked) {
    return (
      <div className="rounded-[16px] bg-white p-[24px]">
        <div className="text-[26px] font-bold">이 제품은 색으로 재기 어렵습니다</div>
        <div className="mt-2 text-[19px] leading-[1.6] text-gray-400">
          {GRADE_NOTE.unsuitable}
        </div>
        {/* 재게 해놓고 나중에 그 숫자를 근거처럼 보여주는 쪽이 더 나쁘다.
            대신 사람이 직접 볼 수 있는 것을 안내한다. */}
        <div className="mt-4 rounded-[13px] bg-primary-50 p-[16px_18px] text-[18px] leading-[1.6]">
          냄새와 질감, 부유물은 사람이 더 잘 알아봅니다. 점검 목록에서 이 제품의
          확인 절차를 따라가 보세요.
        </div>
        <button
          onClick={onBack}
          className="mt-4 h-[62px] w-full rounded-[14px] bg-primary-500 text-[20px] font-semibold text-white"
        >
          돌아가기
        </button>
      </div>
    );
  }

  return (
    <div className="rounded-[16px] bg-white p-[24px]">
      <div className="text-[26px] font-bold">
        {target.name || "선택한 제품"}의 색을 잽니다
      </div>
      {note ? (
        <div className="mt-1.5 text-[18px] text-gray-300">{note}</div>
      ) : null}

      <div className="mt-4 space-y-2">
        <Prep
          n={1}
          text="백색 표준판을 먼저 잽니다. 조명이 밝거나 어두워도 같은 기준으로 비교하기 위해서입니다."
        />
        <Prep
          n={2}
          text="그다음 제품을 같은 자리에 올려 잽니다. 두 번 다 측정부에 밀착시켜 주세요."
        />
        <Prep
          n={3}
          text="올려놓은 뒤에는 이 화면에서 측정을 눌러 주세요. 누르기 전에는 재지 않습니다."
        />
      </div>

      <button
        disabled={busy}
        onClick={onStart}
        className="mt-5 h-[68px] w-full rounded-[14px] bg-primary-500 text-[21px] font-semibold text-white disabled:bg-gray-200 disabled:text-gray-300"
      >
        {busy ? "측정 노드를 부르는 중…" : "측정 시작"}
      </button>
    </div>
  );
}

function Prep({ n, text }: { n: number; text: string }) {
  return (
    <div className="flex items-start gap-3">
      <span className="grid h-8 w-8 flex-none place-items-center rounded-full bg-primary-50 text-[16px] font-bold text-primary-500">
        {n}
      </span>
      <span className="text-[18px] leading-[1.55] text-gray-400">{text}</span>
    </div>
  );
}

// ── 2·3단계: 백색 표준판 / 제품 ──────────────────────────────

function Run({
  session,
  start,
  busy,
  stalled,
  elapsed,
  onCapture,
  onCancel,
}: {
  session: MeasureSession;
  start: MeasureStartResponse | null;
  busy: boolean;
  stalled: boolean;
  elapsed: number;
  onCapture: () => void;
  onCancel: () => void;
}) {
  const white = session.step === "white";

  return (
    <div className="rounded-[16px] bg-white p-[24px]">
      <div className="text-[27px] font-bold">
        {white ? "백색 표준판을 올려 주세요" : "제품을 올려 주세요"}
      </div>

      {/* 문구는 서버가 만든 것을 그대로 쓴다. 상태와 안내가 어긋나면
          화면이 서버보다 앞서 나간 것처럼 보인다. */}
      <div className="mt-2 text-[19px] leading-[1.6] text-gray-400">
        {session.message}
      </div>

      {white ? (
        <div className="mt-3 text-[17px] leading-[1.6] text-gray-300">
          이 값이 조명의 기준이 됩니다. 제품과 같은 자리, 같은 높이에 놓아 주세요.
        </div>
      ) : (
        <div className="mt-3 text-[17px] leading-[1.6] text-gray-300">
          방금 백색 표준판을 잰 그 자리에 그대로 올려 주세요.
          {start && !start.has_baseline
            ? " 이번이 첫 측정이라 이 값이 기준이 됩니다."
            : null}
        </div>
      )}

      <div className="mt-5">
        {session.capturing ? (
          <div className="rounded-[14px] bg-primary-50 p-[20px] text-center">
            <div className="text-[21px] font-semibold text-primary-500">
              재는 중… {elapsed}초
            </div>
            <div className="mt-1 text-[17px] text-gray-400">
              측정부를 건드리지 마세요.
            </div>
          </div>
        ) : (
          <button
            disabled={busy || !session.awaiting_tap}
            onClick={onCapture}
            className="h-[74px] w-full rounded-[14px] bg-primary-500 text-[22px] font-semibold text-white disabled:bg-gray-200 disabled:text-gray-300"
          >
            {busy ? "전달하는 중…" : white ? "백색 표준판 측정" : "제품 측정"}
          </button>
        )}
      </div>

      {/* 노드가 꺼져 있거나 Wi-Fi가 끊기면 아무 일도 일어나지 않는다.
          그 상태로 두면 사용자는 도는 표시만 보다가 고장으로 여긴다. */}
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
 * 첫 측정과 비교 측정은 결과가 다르다.
 *
 * 첫 측정은 비교할 대상이 없어 그 자체가 기준값이 된다. 여기에 변화율을
 * 0%라고 쓰면 "아무 변화 없음"으로 읽히는데, 사실은 아직 아무것도 모르는
 * 상태다. 그래서 두 화면을 갈랐다.
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
  const baseline = ok && session.baseline === true;
  const delta = session.delta_pct;

  return (
    <div className="rounded-[16px] bg-white p-[24px]">
      {!ok ? (
        <>
          <div className="text-[26px] font-bold">측정을 마치지 못했습니다</div>
          <div className="mt-2 text-[19px] leading-[1.6] text-gray-400">
            {session.message}
          </div>
        </>
      ) : baseline ? (
        <>
          <div className="text-[26px] font-bold">기준값을 저장했습니다</div>
          <div className="mt-2 text-[19px] leading-[1.6] text-gray-400">
            {session.message}
          </div>
          <div className="mt-4 rounded-[13px] bg-primary-50 p-[16px_18px] text-[18px] leading-[1.6]">
            이번 측정은 비교할 대상이 없어 그 자체가 기준이 됩니다. 다음에 같은
            제품을 재면 이 색과 얼마나 달라졌는지 알려드릴게요.
          </div>
        </>
      ) : (
        <>
          <div className="text-[26px] font-bold">처음 잰 색과 비교했습니다</div>

          {delta != null ? (
            <div className="mt-4 flex items-baseline gap-2">
              <span className="text-[64px] font-bold leading-none tabular-nums text-primary-500">
                {delta.toFixed(1)}
              </span>
              <span className="text-[26px] font-semibold text-gray-300">% 차이</span>
            </div>
          ) : (
            <div className="mt-2 text-[19px] leading-[1.6] text-gray-400">
              {session.message}
            </div>
          )}

          {/* 변질 여부는 말하지 않는다. 색 변화 하나만으로는 판정할 수 없고,
              점검 순위가 보관 이력·개봉 경과와 함께 종합해서 낸다. */}
          <div className="mt-4 rounded-[13px] bg-primary-50 p-[16px_18px] text-[18px] leading-[1.6]">
            이 숫자는 색이 얼마나 달라졌는지만 말합니다. 상했는지 여부는 냄새·질감
            확인과 보관 이력을 함께 봐야 알 수 있어, 점검 목록의 확인 절차에서
            이어서 안내합니다.
          </div>

          <div className="mt-3 text-[16px] leading-[1.55] text-gray-300">
            재장착 오차보다 작은 차이는 변화로 볼 수 없습니다. 같은 제품을 연달아
            재도 조금씩 다른 값이 나옵니다.
          </div>
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

// ── 공통 ─────────────────────────────────────────────────────

function Centered({ title, lines }: { title: string; lines: string[] }) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-2 text-center">
      <div className="text-[26px] font-bold">{title}</div>
      {lines.map((l) => (
        <div key={l} className="text-[18px] text-gray-300">
          {l}
        </div>
      ))}
    </div>
  );
}

export default MeasureScreen;
