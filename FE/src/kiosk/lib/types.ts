/**
 * /api/care 응답 타입.
 *
 * AI/api/care/router.py의 pydantic 모델과 1:1로 맞춘다.
 * 한쪽을 고치면 반드시 양쪽을 고쳐야 한다.
 */

// ── GET /api/care/dashboard ──────────────────────────────────

export type NodeStatus = {
  node_id: string;
  node_type: string | null;
  location_label: string | null;
  online: boolean;
  last_ts: string | null;
  minutes_since: number | null;
  temperature: number | null;
  humidity: number | null;
  pm25: number | null;
  /** 절대습도 g/m³ */
  absolute_humidity: number | null;
  dry: boolean | null;
  /** 20℃ 보관 대비 노화 속도 배율 */
  aging_factor: number | null;
  aging_text: string | null;
  readings_total: number | null;
  first_ts: string | null;
  days_collected: number | null;
};

export type DashboardResponse = {
  generated_at: string;
  reference_temp_c: number;
  stale_minutes: number;
  dry_threshold_gm3: number;
  nodes: NodeStatus[];
  totals: {
    nodes?: number;
    online?: number;
    offline?: number;
    readings?: number;
  };
};

// ── GET /api/care/priority ───────────────────────────────────

export type RiskBand = "high" | "medium" | "low";

export type PriorityDetail = {
  sensitivity_k?: number | null;
  pao_months?: number | null;
  optical_grade?: string | null;
  optical_delta_pct?: number | null;
  consumed_ratio?: number | null;
  measured_hours?: number;
  assumed_hours?: number;
  gap_hours?: number;
  sample_n?: number;
  acceleration?: number | null;
  mean_temp_c?: number | null;
  max_temp_c?: number | null;
  excursion_events?: number;
  excursion_counted?: boolean;
  hours_above_temp?: number;
  hours_above_humid?: number;
  days_since_last_check?: number | null;
  [key: string]: unknown;
};

export type PriorityItem = {
  user_product_id: string;
  product_id: string | null;
  name: string | null;
  brand: string | null;
  category: string | null;
  storage_node_id: string | null;
  opened_at: string | null;
  last_checked_at: string | null;
  score: number;
  band: RiskBand;
  reasons: string[];
  detail: PriorityDetail;
};

export type MissingInfo = {
  field: string;
  title: string;
  action: string;
};

export type SkippedProduct = {
  user_product_id: string;
  product_id: string | null;
  name: string | null;
  brand: string | null;
  category: string | null;
  missing: MissingInfo[];
};

export type PrioritySummary = {
  total: number;
  scored: number;
  unscored: number;
  high: number;
  medium: number;
  low: number;
  /** 확인이 필요한 제품 수 (high 밴드) */
  needs_check: number;
  band_thresholds: Record<string, number>;
};

export type PriorityResponse = {
  user_id: string;
  generated_at: string;
  summary: PrioritySummary;
  items: PriorityItem[];
  skipped: SkippedProduct[];
  nodes_used: { node_id: string; readings: number; first_ts: string | null; last_ts: string | null }[];
};

// ── GET /api/care/environment ────────────────────────────────
//
// 탭4가 쓰는 응답. 아직 서버에 없다. 화면 틀을 먼저 잡고 이 계약에 맞춰
// 서버를 만든다.
//
// 실내 값은 센서에서 오고, 실외 값은 외부 날씨 API에서 온다. 출처가
// 다르므로 source를 함께 받아 화면에 표시한다. 심사위원이 "이 자외선
// 지수는 어디서 온 것이냐"고 물었을 때 답할 수 있어야 한다.

export type OutdoorWeather = {
  region: string;
  observed_at: string | null;
  temperature: number | null;
  humidity: number | null;
  /** 자외선 지수 0~11+ */
  uv_index: number | null;
  pm10: number | null;
  pm25: number | null;
  /** "기상청 단기예보" 등. 출처를 감추지 않는다. */
  source: string | null;
};

export type IndoorNode = {
  node_id: string;
  label: string;
  online: boolean;
  temperature: number | null;
  humidity: number | null;
  absolute_humidity: number | null;
  pm25: number | null;
};

/**
 * 케어 안내.
 *
 * LLM을 쓰지 않는다. 서버의 규칙 테이블이 조건에 맞는 문장을 고른다.
 * rules에는 어떤 규칙이 걸렸는지가 들어와, 화면에서 근거를 보일 수 있다.
 */
export type CareBrief = {
  headline: string;
  lines: string[];
  rules: string[];
};

export type EnvironmentResponse = {
  generated_at: string;
  outdoor: OutdoorWeather | null;
  indoor: IndoorNode[];
  brief: CareBrief;
  /** "사무실이 더 건조합니다" 같은 노드 간 비교 한 줄. */
  comparison: string | null;
};


// ── GET /api/care/skin ───────────────────────────────────────
//
// 탭2가 쓰는 응답. 아직 서버에 없다.
//
// PSRI는 환경(절대습도·PM2.5)만으로 계산되므로 센서 데이터만 있으면
// 나온다. 반면 ITA°와 홍반 지수는 AS7341로 피부를 재야 나오는 값이다.
// 측정 이력이 없으면 latest는 null이고 화면은 "측정 전"으로 보인다.

export type PsriBreakdown = {
  /** 0~100. 높을수록 환경이 피부에 부담이 크다는 뜻. */
  score: number;
  band: "good" | "caution" | "check";
  /** 건조 항. 절대습도 부족에서 온다. */
  dryness: number;
  /** 자극 항. PM2.5에서 온다. */
  irritation: number;
  /** 연령대 등 개인 가중치. 1.0이 성인 기준. */
  personal_weight: number;
  personal_label: string | null;
  /** 몇 시간을 적분했는지. 24시간이 기본. */
  window_hours: number;
};

export type SkinMeasurement = {
  measured_at: string;
  /** Individual Typology Angle. 피부 밝기의 표준 지표. */
  ita: number | null;
  ita_class: string | null;
  /** 홍반 지수 (a*). */
  erythema: number | null;
  /** 직전 측정 대비 변화량. */
  erythema_delta: number | null;
};

export type SkinTrendPoint = {
  date: string;
  erythema: number | null;
  ita: number | null;
};

export type SkinResponse = {
  generated_at: string;
  psri: PsriBreakdown;
  /** 환경과의 관계를 설명하는 문장. 규칙 테이블이 만든다. */
  relation: string | null;
  latest: SkinMeasurement | null;
  trend: SkinTrendPoint[];
  trend_note: string | null;
};

// ── GET /api/care/recommendations ────────────────────────────
//
// 탭3이 쓰는 응답. 기존 추천 파이프라인을 키오스크용으로 감싼다.
//
// reason은 왜 이 제품인지 한 줄이다. 환경 수치를 근거로 들며,
// 문장은 서버가 만든다.

export type RecommendedProduct = {
  product_id: string;
  name: string;
  brand: string | null;
  image_url: string | null;
  reason: string;
};

export type RecommendationsResponse = {
  generated_at: string;
  /** 상단에 띄울 환경 한 줄. "침실 24.1℃ / 47% · 외출 자외선 7" */
  context: string | null;
  items: RecommendedProduct[];
  /** QR에 넣을 주소. 휴대폰에서 전체 추천을 보는 곳. */
  qr_url: string;
};