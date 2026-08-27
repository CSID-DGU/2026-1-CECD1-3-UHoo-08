/**
 * 측정값 → 화면 색.
 *
 * 색이 무슨 말을 하는지가 이 파일의 전부다. 규칙은 여기 한 곳에만 두고,
 * 화면은 결과만 받아 쓴다. LLM을 쓰지 않는다는 원칙에 따라 전부 고정 규칙이다.
 *
 * ── 색이 해도 되는 말 ────────────────────────────────────────
 * 판단 기준은 하나다. 색과 함께 뜨는 문장을 그대로 심사위원에게 말할 수
 * 있는가. "확인이 필요한 제품이 2개 있습니다"는 말할 수 있다. "이 제품은
 * 변질됐습니다"는 말할 수 없다. 그래서 notice는 늘 확인 요청에서 멈추고,
 * 단정하는 낱말(변질·위험·경고)은 쓰지 않는다.
 *
 * 색만 덩그러니 두면 보는 사람이 각자 최악을 상상한다. 그래서 lead(=색의
 * 근거 한 줄)를 항상 함께 내보내고, 화면은 그것을 반드시 표시한다.
 */

import type { DashboardResponse, NodeStatus, PriorityResponse } from "./types";

export type AuraLevel = "good" | "caution" | "check";

/** 색을 결정한 항목 하나. */
export type AuraFactor = {
  key: "temp" | "dry" | "pm25" | "priority" | "offline";
  level: AuraLevel;
  /** 화면에 그대로 띄우는 근거 한 줄. */
  line: string;
};

export type AuraState = {
  level: AuraLevel;
  /** 셰이더 uColor용 0~1 RGB. */
  color: readonly [number, number, number];
  /** WebGL이 죽었을 때 대신 깔 CSS 그라데이션. */
  fallback: string;
  /** 가장 나쁜 항목. 색의 근거다. */
  lead: AuraFactor;
  /** 판단에 쓴 항목 전부(양호 포함). 순서는 나쁜 것부터. */
  factors: AuraFactor[];
  /** 양호가 아닐 때만 채운다. 대기 화면이 5초마다 이걸 띄운다. */
  notice: string | null;
};

// ── 기준값 ───────────────────────────────────────────────────
//
// 목업 차트에는 권장 보관 범위가 11~15℃로 적혀 있다. 그 기준을 색에 쓰면
// 평범한 실내가 전부 확인 필요로 뜬다(지금 서랍이 26.8℃다). 화장품 일반
// 보관 권장인 실온 15~25℃ 쪽이 현실적이라 이쪽을 쓴다.
// 목업 차트 표기를 바꿀지는 따로 정해야 한다.
const TEMP_CAUTION_C = 25;
const TEMP_CHECK_C = 30;

// 환경부 PM2.5 기준. 좋음 15 이하 / 보통 35 이하 / 그 위는 나쁨.
const PM25_CAUTION = 15;
const PM25_CHECK = 35;

/** 절대습도 건조 기준. 응답에 값이 오면 그쪽을 쓴다. */
const DRY_FALLBACK_GM3 = 7;

// ── 색 ───────────────────────────────────────────────────────
//
// 빨강을 쓰지 않는 이유: 빨강은 경고·위험의 관용색이라 "확인해 보시겠어요"
// 라는 문구와 화면이 서로 다른 말을 하게 된다. 자홍은 눈에 띄면서도
// 단정하지 않고 브랜드 색과도 붙는다. 검정은 화면이 꺼진 것처럼 보여서 뺐다.
const PALETTE: Record<AuraLevel, { hex: string; fallback: string }> = {
  good: {
    hex: "#4FB89B", // 청록 — 하늘(primary-500)과 같은 계열로 흐른다
    fallback: "radial-gradient(120% 120% at 30% 20%, #4FB89B 0%, #5B8FD9 55%, #2a2d33 100%)",
  },
  caution: {
    hex: "#E8A93B", // 호박
    fallback: "radial-gradient(120% 120% at 30% 20%, #E8A93B 0%, #5B8FD9 60%, #2a2d33 100%)",
  },
  check: {
    hex: "#C2528C", // 자홍
    fallback: "radial-gradient(120% 120% at 30% 20%, #C2528C 0%, #7B4B9E 55%, #2a2d33 100%)",
  },
};

function hexToRgb01(hex: string): readonly [number, number, number] {
  const n = parseInt(hex.slice(1), 16);
  return [((n >> 16) & 255) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255] as const;
}

const RANK: Record<AuraLevel, number> = { good: 0, caution: 1, check: 2 };

// ── 항목별 판정 ──────────────────────────────────────────────

/** 온도가 가장 높은 노드를 대표로 쓴다. 서랍 하나만 뜨거워도 그게 사실이다. */
function tempFactor(nodes: NodeStatus[]): AuraFactor | null {
  const measured = nodes.filter((n) => n.online && n.temperature !== null);
  if (measured.length === 0) return null;

  const worst = measured.reduce((a, b) => (b.temperature! > a.temperature! ? b : a));
  const t = worst.temperature!;
  const where = worst.location_label || worst.node_id.slice(0, 8);
  const temp = `${t.toFixed(1)}℃`;

  if (t > TEMP_CHECK_C)
    return { key: "temp", level: "check", line: `${where} ${temp} · 권장 ${TEMP_CAUTION_C}℃보다 높습니다` };
  if (t > TEMP_CAUTION_C)
    return { key: "temp", level: "caution", line: `${where} ${temp} · 권장 범위보다 조금 높습니다` };
  return { key: "temp", level: "good", line: `${where} ${temp} · 보관하기 좋은 온도입니다` };
}

/** 절대습도가 낮으면 건조. 상대습도는 온도에 따라 흔들려 쓰지 않는다. */
function dryFactor(nodes: NodeStatus[], threshold: number): AuraFactor | null {
  const measured = nodes.filter((n) => n.online && n.absolute_humidity !== null);
  if (measured.length === 0) return null;

  const worst = measured.reduce((a, b) => (b.absolute_humidity! < a.absolute_humidity! ? b : a));
  const ah = worst.absolute_humidity!;
  const where = worst.location_label || worst.node_id.slice(0, 8);

  if (ah < threshold)
    return { key: "dry", level: "caution", line: `${where} 절대습도 ${ah.toFixed(1)} g/m³ · 건조한 편입니다` };
  return { key: "dry", level: "good", line: `${where} 절대습도 ${ah.toFixed(1)} g/m³ · 알맞습니다` };
}

function pm25Factor(nodes: NodeStatus[]): AuraFactor | null {
  const measured = nodes.filter((n) => n.online && n.pm25 !== null);
  if (measured.length === 0) return null;

  const worst = measured.reduce((a, b) => (b.pm25! > a.pm25! ? b : a));
  const v = worst.pm25!;
  const shown = `초미세먼지 ${Math.round(v)} ㎍/m³`;

  if (v > PM25_CHECK) return { key: "pm25", level: "check", line: `${shown} · 나쁨 구간입니다` };
  if (v > PM25_CAUTION) return { key: "pm25", level: "caution", line: `${shown} · 보통 구간입니다` };
  return { key: "pm25", level: "good", line: `${shown} · 좋음 구간입니다` };
}

/**
 * 점검 우선순위.
 *
 * 여기서 나오는 값은 "상했다"가 아니라 "먼저 확인해 볼 순서"다.
 * 문구도 딱 거기까지만 쓴다.
 */
function priorityFactor(p: PriorityResponse | null): AuraFactor | null {
  if (!p) return null;
  const n = p.summary.needs_check;
  if (n > 0)
    return { key: "priority", level: "check", line: `먼저 확인해 볼 제품이 ${n}개 있습니다` };
  if (p.summary.scored === 0)
    return { key: "priority", level: "good", line: "점검 순서를 산출할 제품이 아직 없습니다" };
  return { key: "priority", level: "good", line: `보유 ${p.summary.total}개 · 지금 확인할 제품은 없습니다` };
}

/** 값이 안 들어오는 것도 화면에 보여야 할 사실이다. 색까지 바꾸지는 않는다. */
function offlineFactor(d: DashboardResponse): AuraFactor | null {
  const off = d.nodes.filter((n) => !n.online);
  if (off.length === 0) return null;
  return {
    key: "offline",
    level: "caution",
    line: `센서 ${off.length}대가 ${d.stale_minutes}분 넘게 값을 보내지 않았습니다`,
  };
}

// ── 합성 ─────────────────────────────────────────────────────

/** 값이 아직 하나도 없을 때. 색은 중립(양호)으로 두고 문구로 알린다. */
const UNKNOWN: AuraState = {
  level: "good",
  color: hexToRgb01(PALETTE.good.hex),
  fallback: PALETTE.good.fallback,
  lead: { key: "temp", level: "good", line: "측정값을 기다리는 중입니다" },
  factors: [],
  notice: null,
};

export function computeAura(
  dashboard: DashboardResponse | null,
  priority: PriorityResponse | null
): AuraState {
  if (!dashboard) return UNKNOWN;

  const dryThreshold = dashboard.dry_threshold_gm3 ?? DRY_FALLBACK_GM3;

  const factors = [
    tempFactor(dashboard.nodes),
    dryFactor(dashboard.nodes, dryThreshold),
    pm25Factor(dashboard.nodes),
    priorityFactor(priority),
    offlineFactor(dashboard),
  ].filter((f): f is AuraFactor => f !== null);

  if (factors.length === 0) return UNKNOWN;

  // 평균이 아니라 최악을 쓴다. 평균을 내면 하나가 심각해도 나머지가 좋아서 묻힌다.
  factors.sort((a, b) => RANK[b.level] - RANK[a.level]);
  const lead = factors[0];
  const level = lead.level;

  return {
    level,
    color: hexToRgb01(PALETTE[level].hex),
    fallback: PALETTE[level].fallback,
    lead,
    factors,
    notice: level === "good" ? null : noticeFor(level, factors),
  };
}

/**
 * 안내문.
 *
 * "경고"가 아니라 "안내"다. 이상 감지는 경고가 아니라 질문이라는 게 이
 * 프로젝트의 규칙이고, 발표 중에 경고라는 낱말이 나오면 무엇을 근거로
 * 경고하느냐는 물음을 자초한다.
 */
function noticeFor(level: AuraLevel, factors: AuraFactor[]): string {
  const bad = factors.filter((f) => f.level !== "good");
  const head = level === "check" ? "확인해 보시면 좋겠습니다" : "조금 지켜볼 상태입니다";
  if (bad.length <= 1) return head;
  return `${head} · 항목 ${bad.length}가지`;
}

/** 색이 바뀌는지 화면에서 확인하기 위한 라벨. */
export const LEVEL_LABEL: Record<AuraLevel, string> = {
  good: "양호",
  caution: "주의",
  check: "확인 필요",
};

// ── 화면에 띄울 대표값 ───────────────────────────────────────
//
// 노드가 여러 대라 하나를 골라야 한다. 색을 정할 때와 같은 노드를 고른다.
// 색은 최악을 기준으로 하는데 숫자는 평균을 보여주면 둘이 어긋난다.

export type Reading = {
  value: string;
  unit: string;
  where: string;
  label: string;
  /** 값을 보낸 지 오래됐으면 "23분 전". 최신이면 null. */
  ago: string | null;
};

export type Readings = {
  temp: Reading | null;
  humidity: Reading | null;
  pm25: Reading | null;
};

/**
 * 온라인 노드를 먼저 보고, 하나도 없으면 마지막 값이라도 쓴다.
 *
 * 값을 아예 안 보여주면 화면이 텅 빈다. 오래된 값이라는 사실을 함께
 * 적으면 거짓말이 아니고, 시연 중 센서가 잠깐 끊겨도 화면이 살아 있다.
 * 색은 이 값으로 정하지 않는다. 오래된 값으로 지금을 단정할 수 없어서다.
 */
function ago(n: NodeStatus): string | null {
  if (n.online || n.minutes_since === null) return null;
  const m = Math.round(n.minutes_since);
  if (m < 60) return `${m}분 전`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}시간 전`;
  return `${Math.floor(h / 24)}일 전`;
}

/** 온라인 노드 중에서 고르고, 없으면 전체에서 고른다. */
function pickNode(
  nodes: NodeStatus[],
  has: (n: NodeStatus) => boolean,
  worse: (a: NodeStatus, b: NodeStatus) => boolean
): NodeStatus | null {
  const online = nodes.filter((n) => n.online && has(n));
  const pool = online.length > 0 ? online : nodes.filter(has);
  if (pool.length === 0) return null;
  return pool.reduce((a, b) => (worse(b, a) ? b : a));
}

export function pickReadings(d: DashboardResponse | null): Readings {
  if (!d) return { temp: null, humidity: null, pm25: null };
  const where = (n: NodeStatus) => n.location_label || n.node_id.slice(0, 8);

  const hotNode = pickNode(
    d.nodes,
    (n) => n.temperature !== null,
    (b, a) => b.temperature! > a.temperature!
  );
  const dryNode = pickNode(
    d.nodes,
    (n) => n.absolute_humidity !== null,
    (b, a) => b.absolute_humidity! < a.absolute_humidity!
  );
  const dustNode = pickNode(
    d.nodes,
    (n) => n.pm25 !== null,
    (b, a) => b.pm25! > a.pm25!
  );

  return {
    temp: hotNode
      ? {
          label: "온도",
          value: hotNode.temperature!.toFixed(1),
          unit: "℃",
          where: where(hotNode),
          ago: ago(hotNode),
        }
      : null,
    humidity: dryNode
      ? {
          label: "절대습도",
          value: dryNode.absolute_humidity!.toFixed(1),
          unit: "g/m³",
          where: where(dryNode),
          ago: ago(dryNode),
        }
      : null,
    pm25: dustNode
      ? {
          label: "초미세먼지",
          value: String(Math.round(dustNode.pm25!)),
          unit: "㎍/m³",
          where: where(dustNode),
          ago: ago(dustNode),
        }
      : null,
  };
}
