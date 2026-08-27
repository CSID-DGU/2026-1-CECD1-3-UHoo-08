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
  return null;
}