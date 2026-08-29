import type {
  DashboardResponse,
  EnvironmentResponse,
  PriorityResponse,
  RecommendationsResponse,
  SkinResponse,
} from "./types";

/**
 * 서버 없이 화면을 보기 위한 시드 데이터.
 *
 * 주소에 ?mock=1 을 붙이면 켜진다. 예선 시연에서는 쓰지 않는다.
 * 화면을 만드는 동안 API가 아직 없어서 배치·줄바꿈·넘침을 확인할
 * 방법이 없기 때문에 둔다.
 *
 * ── 실제 시연 데이터와 혼동하지 않기 ─────────────────────────
 * 이 모드가 켜져 있으면 화면 오른쪽 위에 표시가 뜬다. 시연 중에
 * 모르고 켜둔 채 발표하는 사고를 막기 위해서다.
 */

export const MOCK_ENABLED =
  new URLSearchParams(window.location.search).get("mock") === "1";

const now = new Date();
const iso = (offsetMin: number) =>
  new Date(now.getTime() - offsetMin * 60_000).toISOString();

const mockDashboard: DashboardResponse = {
  generated_at: iso(0),
  reference_temp_c: 20,
  stale_minutes: 30,
  dry_threshold_gm3: 7,
  nodes: [
    {
      node_id: "storage-01",
      node_type: "storage",
      location_label: "화장대 서랍",
      online: true,
      last_ts: iso(4),
      minutes_since: 4,
      temperature: 26.8,
      humidity: 52,
      pm25: null,
      absolute_humidity: 13.2,
      dry: false,
      aging_factor: 1.62,
      aging_text: "20℃ 보관보다 약 1.6배 빠르게 시간이 흐릅니다",
      readings_total: 3312,
      first_ts: iso(60 * 24 * 23),
      days_collected: 23,
    },
    {
      node_id: "ambient-01",
      node_type: "ambient",
      location_label: "침실",
      online: true,
      last_ts: iso(6),
      minutes_since: 6,
      temperature: 24.1,
      humidity: 47,
      pm25: 18,
      absolute_humidity: 10.4,
      dry: false,
      aging_factor: 1.31,
      aging_text: "20℃ 보관보다 약 1.3배 빠르게 시간이 흐릅니다",
      readings_total: 3180,
      first_ts: iso(60 * 24 * 22),
      days_collected: 22,
    },
    {
      node_id: "ambient-02",
      node_type: "ambient",
      location_label: "사무실",
      online: true,
      last_ts: iso(9),
      minutes_since: 9,
      temperature: 22.6,
      humidity: 31,
      pm25: 24,
      absolute_humidity: 6.2,
      dry: true,
      aging_factor: 1.19,
      aging_text: "20℃ 보관보다 약 1.2배 빠르게 시간이 흐릅니다",
      readings_total: 2940,
      first_ts: iso(60 * 24 * 21),
      days_collected: 21,
    },
  ],
  totals: { nodes: 3, online: 3, offline: 0, readings: 9432 },
};

const mockPriority: PriorityResponse = {
  user_id: "mock",
  generated_at: iso(0),
  summary: {
    total: 12,
    scored: 12,
    unscored: 1,
    high: 1,
    medium: 1,
    low: 10,
    needs_check: 1,
    band_thresholds: { high: 70, medium: 40 },
  },
  items: [
    {
      // 사용자가 이미 확인한 제품. 점검 목록에서 배지가 붙는다.
      inspection: { ts: iso(60 * 24), findings: ["냄새 변화"], clear: false },
      user_product_id: "m1",
      product_id: "p1",
      name: "레티놀 나이트 세럼",
      brand: "이니스프리",
      category: "skincare",
      storage_node_id: "storage-01",
      opened_at: "2026-01-02",
      last_checked_at: null,
      score: 87,
      band: "high",
      reasons: ["개봉 8개월", "34℃ 노출 42시간", "열이력 소모 96%", "고민감 성분(k 1.5)"],
      detail: {
        sensitivity_k: 1.5,
        pao_months: 6,
        optical_grade: "conditional",
        optical_delta_pct: null,
        consumed_ratio: 0.96,
        measured_hours: 552,
        assumed_hours: 5208,
        excursion_events: 3,
        excursion_counted: true,
      },
    },
    {
      inspection: null,
      user_product_id: "m2",
      product_id: "p2",
      name: "비타민C 브라이트닝 앰플",
      brand: "코스알엑스",
      category: "skincare",
      storage_node_id: "storage-01",
      opened_at: "2026-05-28",
      last_checked_at: null,
      score: 54,
      band: "medium",
      reasons: ["개봉 3개월", "광학 변화 6.2%", "고민감 성분(k 1.5)"],
      detail: {
        sensitivity_k: 1.5,
        pao_months: 6,
        optical_grade: "suitable",
        optical_delta_pct: 6.2,
        consumed_ratio: 0.58,
        measured_hours: 552,
        assumed_hours: 1656,
        excursion_events: 1,
        excursion_counted: true,
      },
    },
    ...Array.from({ length: 10 }, (_, i) => ({
      inspection: null,
      user_product_id: `mlow${i}`,
      product_id: `plow${i}`,
      name: `정상 범위 제품 ${i + 1}`,
      brand: "테스트",
      category: "skincare",
      storage_node_id: "storage-01",
      opened_at: "2026-07-01",
      last_checked_at: null,
      score: 20 - i,
      band: "low" as const,
      reasons: ["개봉 2개월", "일반 성분(k 1)"],
      detail: { measured_hours: 552, assumed_hours: 800, excursion_events: 0 },
    })),
  ],
  skipped: [
    {
      user_product_id: "ms1",
      product_id: "ps1",
      name: "수분 크림",
      brand: "라운드랩",
      category: "skincare",
      missing: [
        {
          field: "opened_at",
          title: "개봉일 미등록",
          action: "앱에서 개봉일을 입력하면 점검 순서에 포함됩니다",
        },
      ],
    },
  ],
  nodes_used: [
    { node_id: "storage-01", readings: 3312, first_ts: iso(60 * 24 * 23), last_ts: iso(4) },
  ],
};

const mockEnvironment: EnvironmentResponse = {
  generated_at: iso(0),
  outdoor: {
    region: "인천 부평",
    observed_at: iso(35),
    temperature: 29,
    humidity: 38,
    uv_index: 7,
    pm10: 42,
    pm25: 31,
    source: "기상청 단기예보 · 에어코리아",
  },
  indoor: [
    {
      node_id: "ambient-01",
      label: "침실",
      online: true,
      temperature: 24.1,
      humidity: 47,
      absolute_humidity: 10.4,
      pm25: 18,
    },
    {
      node_id: "ambient-02",
      label: "사무실",
      online: true,
      temperature: 22.6,
      humidity: 31,
      absolute_humidity: 6.2,
      pm25: 24,
    },
  ],
  brief: {
    headline: "자외선이 강하고 건조합니다.",
    lines: [
      "오늘 인천 부평으로 외출하시는군요.",
      "외출 전 자외선 차단과 수분 보충을 권장합니다.",
    ],
    rules: ["자외선 지수 7 ≥ 6", "실외 습도 38% < 40%", "사무실 절대습도 6.2 < 7 g/m³"],
  },
  comparison: "침실 24.1℃ / 47% · 사무실 22.6℃ / 31% — 사무실이 더 건조합니다",
};

const mockSkin: SkinResponse = {
  generated_at: iso(0),
  psri: {
    score: 61,
    band: "caution",
    dryness: 48,
    irritation: 13,
    personal_weight: 1.0,
    personal_label: "성인",
    window_hours: 24,
  },
  relation:
    "사무실 절대습도가 6.2 g/m³로 침실보다 낮습니다. 체류 시간이 긴 쪽의 환경이 피부에 더 크게 작용합니다.",
  latest: {
    measured_at: iso(60 * 24 * 2),
    ita: 41.2,
    ita_class: "Intermediate",
    erythema: 12.8,
    erythema_delta: 1.6,
  },
  trend: [
    { date: "8/14", erythema: 10.4, ita: 43.1 },
    { date: "8/15", erythema: 10.2, ita: 43.0 },
    { date: "8/16", erythema: 10.7, ita: 42.6 },
    { date: "8/17", erythema: 10.9, ita: 42.4 },
    { date: "8/18", erythema: 11.1, ita: 42.2 },
    { date: "8/19", erythema: 10.8, ita: 42.5 },
    { date: "8/20", erythema: 11.4, ita: 42.0 },
    { date: "8/21", erythema: 11.9, ita: 41.8 },
    { date: "8/22", erythema: 12.2, ita: 41.6 },
    { date: "8/23", erythema: 12.0, ita: 41.7 },
    { date: "8/24", erythema: 12.5, ita: 41.4 },
    { date: "8/25", erythema: 12.8, ita: 41.2 },
  ],
  trend_note: "저습 구간(8/19~8/23) 이후 상승 경향",
};

const mockReco: RecommendationsResponse = {
  generated_at: iso(0),
  context: "침실 24.1℃ / 47% · 외출 자외선 7",
  items: [
    {
      product_id: "r1",
      name: "수분 진정 토너",
      brand: "라운드랩",
      image_url: null,
      reason: "실내 절대습도 10.4 g/m³ — 건조 임계 이하",
    },
    {
      product_id: "r2",
      name: "무기자차 선크림",
      brand: "닥터지",
      image_url: null,
      reason: "외출 지역 자외선 지수 7 — 매우 높음",
    },
    {
      product_id: "r3",
      name: "약산성 클렌징 폼",
      brand: "토리든",
      image_url: null,
      reason: "사무실 PM2.5 24 — 세정 강화 권장",
    },
  ],
  qr_url: "https://2026-1-cecd-1-3-u-hoo-08.vercel.app",
};

/** 경로별 시드 응답. 없는 경로는 null. */
export function mockFor(path: string): unknown | null {
  if (path.startsWith("/api/care/dashboard")) return mockDashboard;
  if (path.startsWith("/api/care/priority")) return mockPriority;
  if (path.startsWith("/api/care/environment")) return mockEnvironment;
  if (path.startsWith("/api/care/skin")) return mockSkin;
  if (path.startsWith("/api/care/recommendations")) return mockReco;
  if (path.startsWith("/api/care/events")) return mockEvents;
  const m = /\/api\/care\/products\/([^/]+)\/protocol/.exec(path);
  // 목업도 제품마다 다른 값을 준다. 하나로 고정하면 다른 제품을 골라도
  // 같은 화면이 나와 연결이 잘못된 것처럼 보인다.
  if (m) return mockProtocolFor(decodeURIComponent(m[1]));
  return null;
}

// ── 이벤트 이력 ──────────────────────────────────────────────

const mockEvents = {
  generated_at: iso(0),
  intro: [
    "온도가 높을수록 화장품 성분이 빨리 변합니다.",
    "화장품이 상하기 시작하면 특유의 냄새가 나는데, 센서가 그 변화를 감지합니다.",
    "다만 향수나 스프레이도 같은 신호를 내기 때문에 원인을 여쭤봅니다.",
  ],
  // 고온 노출은 되물을 것이 없어 pending에 세지 않는다.
  summary: { total: 3, pending: 1, excluded: 1, alert: "확인이 필요한 질문이 하나 있습니다" },
  items: [
    {
      id: 1, node_id: "storage-01", node_label: "화장대",
      ts: iso(60 * 24 * 2), when: "8/26(수) 20:10",
      event_type: "voc_spike", magnitude: 66.8,
      title: "공기 성분 변화",
      detail: "화장대 가스 저항이 평소보다 67% 낮아졌습니다",
      question: "이 무렵 근처에서 향수·스프레이·소독제처럼 냄새가 강한 것을 쓰신 적이 있나요?",
      user_answer: "pending", excluded: false, status: null,
    },
    {
      id: 2, node_id: "storage-01", node_label: "화장대",
      ts: iso(60 * 24 * 5), when: "8/23(일) 13:20",
      event_type: "temp_excursion", magnitude: 34.9,
      title: "고온 노출",
      detail: "화장대 최고 34.9℃ · 30분 이상 지속",
      question: null, user_answer: "none", excluded: false,
      status: "확인함 · 짚이는 외부 요인 없음",
    },
    {
      id: 3, node_id: "storage-01", node_label: "화장대",
      ts: iso(60 * 24 * 9), when: "8/19(수) 18:20",
      event_type: "voc_spike", magnitude: 64.0,
      title: "공기 성분 변화",
      detail: "화장대 가스 저항이 평소보다 64% 낮아졌습니다",
      question: null, user_answer: "external_source", excluded: true,
      status: "확인함 · 일시적 외부 요인의 영향",
    },
  ],
};

// ── 확인 절차 ────────────────────────────────────────────────

const mockProtocolBase = {
  user_product_id: "m1",
  name: "레티놀 나이트 세럼",
  brand: "이니스프리",
  label: "오일·세럼",
  score: 87,
  band: "high",
  reasons: ["개봉 8개월", "34℃ 노출 42시간", "열이력 소모 96%", "고민감 성분(k 1.5)"],
  steps: [
    { order: 1, basis: "냄새", text: "향이 평소와 다른가요? 시큼하거나 기름 전 냄새가 나나요?", optical: false },
    { order: 2, basis: "유화상태", text: "용기를 세워 두었을 때 층이 분리돼 있나요?", optical: false },
    { order: 3, basis: "점도", text: "한 방울 떨어뜨렸을 때 평소보다 묽거나 되직한가요?", optical: false },
    { order: 4, basis: "사용기간", text: "용기에 표시된 개봉 후 사용기간을 확인하세요. 등록된 정보로는 6개월 기준을 2개월 지났습니다.", optical: false },
  ],
  answers: ["이상 없음", "냄새가 남", "분리됨", "질감 변화"],
  caution: null,
  note: "식물성 오일은 산패하면 냄새가 먼저 바뀝니다. 색보다 코가 빠릅니다.",
};

/**
 * POST 응답. 보낸 값에 따라 다른 안내를 돌려준다.
 *
 * 서버 규칙 테이블을 그대로 옮기지 않고 흐름만 흉내 낸다. 목업은 배치를
 * 확인하는 용도이고, 문구가 서버와 조금 달라도 화면 작업에는 지장이 없다.
 */
export function mockPostFor(path: string, body: unknown): unknown | null {
  const answer = (body as { answer?: string } | null)?.answer;

  if (/\/api\/care\/events\/\d+\/answer$/.test(path)) {
    const external = answer === "external_source";
    return {
      event: {
        ...mockEvents.items[0], question: null,
        user_answer: answer, excluded: external,
        status: external
          ? "확인함 · 일시적 외부 요인의 영향"
          : "확인함 · 짚이는 외부 요인 없음",
      },
      headline: external ? "일시적인 외부 요인이었습니다" : "화장품 상태를 확인해 보시겠어요?",
      lines: external
        ? ["보관 중인 화장품에서 비롯된 변화가 아닙니다."]
        : ["같은 보관함에 있던 제품 중 확인 순위가 높은 것부터 보여드릴게요."],
      // 목록은 자르지 않는다. 점검 탭의 측정하기 모달과 같은 범위다.
      next: external ? null : {
        action: "priority",
        products: mockPriority.items.map((i) => ({
          user_product_id: i.user_product_id,
          name: i.name, brand: i.brand, score: i.score, band: i.band,
        })),
      },
    };
  }

  if (/\/api\/care\/products\/[^/]+\/inspection$/.test(path)) {
    const answers = (body as { answers?: string[] } | null)?.answers ?? [];
    const issues = answers.filter((a) => a !== "이상 없음");

    const advice: Record<string, string[]> = {
      "냄새가 남": ["냄새 변화는 되돌아오지 않습니다.",
                  "얼굴에 쓰기 전에 팔 안쪽에 발라 보시고, 붉어지면 사용을 멈추세요."],
      "색이 다름": ["색 변화만으로 사용 여부를 정하기는 어렵습니다.",
                  "냄새와 질감도 함께 확인해 보세요."],
      "분리됨": ["흔들었을 때 다시 섞인다면 일시적인 분리일 수 있습니다.",
               "섞이지 않는다면 사용을 멈추시는 편이 좋습니다."],
      "혼탁함": ["부유물이 보이면 눈가나 상처가 있는 부위에는 쓰지 마세요."],
      "덩어리짐": ["굳은 덩어리는 세균이 자라기 쉬운 자리입니다.",
                "눈가나 상처가 있는 부위에는 쓰지 마세요."],
      "질감 변화": ["질감이 달라졌다면 성분이 변했을 수 있습니다.",
                 "팔 안쪽에 먼저 발라 보시고 자극이 없는지 확인하세요."],
    };
    const short: Record<string, string> = {
      "색이 다름": "색 변화", "냄새가 남": "냄새 변화", "분리됨": "층 분리",
      "혼탁함": "부유물", "질감 변화": "질감 변화", "덩어리짐": "덩어리",
    };

    return {
      user_product_id: "m1",
      answers,
      headline: issues.length === 0
        ? "이상이 없다고 확인하셨습니다"
        : issues.length === 1 ? "확인해 주셔서 감사합니다" : "확인하신 내용입니다",
      sections: issues.map((a) => ({ label: short[a] ?? a, lines: advice[a] ?? [] })),
      lines: [],
      recommend_replace: issues.some((a) => ["냄새가 남", "혼탁함", "덩어리짐"].includes(a)),
      findings: issues.map((a) => short[a] ?? a),
    };
  }

  return null;
}


/** 제품 id에 따라 다른 확인 절차. 목업에서도 연결이 맞는지 보이게 한다. */
function mockProtocolFor(id: string) {
  const found = mockPriority.items.find((i) => i.user_product_id === id);
  if (!found) return { ...mockProtocolBase, user_product_id: id };

  const clear = /토너|에센스|스킨/.test(found.name ?? "");
  return {
    ...mockProtocolBase,
    user_product_id: id,
    name: found.name,
    brand: found.brand,
    score: found.score,
    band: found.band,
    reasons: found.reasons,
    label: clear ? "투명 토너·에센스" : mockProtocolBase.label,
    steps: clear
      ? [
          { order: 1, basis: "냄새", text: "향이 평소와 다른가요? 시큼하거나 알코올 냄새가 강해졌나요?", optical: false },
          { order: 2, basis: "성상", text: "밝은 빛에 비춰 부유물이나 혼탁이 있는지 보세요.", optical: false },
          { order: 3, basis: "점도", text: "평소보다 묽거나 끈적한가요?", optical: false },
        ]
      : mockProtocolBase.steps,
    answers: clear
      ? ["이상 없음", "냄새가 남", "혼탁함", "질감 변화"]
      : mockProtocolBase.answers,
    note: clear
      ? "투명 제형은 광학 측정 대상이 아닙니다. 감각으로 확인해 주세요."
      : mockProtocolBase.note,
  };
}