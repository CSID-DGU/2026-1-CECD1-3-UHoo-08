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

/**
 * 사용자가 직접 확인한 결과.
 *
 * 점수는 "확인해 볼 순서"이고 이쪽은 "사람이 실제로 본 것"이다.
 * 후자가 더 강한 정보라 목록에서 눈에 띄게 보여야 한다.
 */
export type InspectionRecord = {
  ts: string;
  findings: string[];
  /** 이상 항목 없이 "이상 없음"으로 확인한 경우 */
  clear: boolean;
};

export type PriorityItem = {
  inspection: InspectionRecord | null;
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
  /** 아직 확인하지 않은 고위험 제품 수. high 밴드 개수가 아니다. */
  needs_check: number;
  /** 고위험 중 이미 확인을 마친 수. needs_check와 합하면 high가 된다. */
  checked_high: number;
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
  /** 이상이 발견된 제품을 대신하는 추천이면 그 제품 이름. */
  replacing: string | null;
  qr_url: string;
};

// ── GET /api/care/events ─────────────────────────────────────

export type EventType = "temp_excursion" | "humid_excursion" | "voc_spike";
export type EventAnswer = "pending" | "external_source" | "none";

export type CareEvent = {
  id: number;
  node_id: string | null;
  node_label: string | null;
  ts: string;
  /** 화면에 그대로 쓰는 짧은 시각 표기. 서버가 만든다. */
  when: string;
  event_type: EventType | string;
  magnitude: number | null;
  title: string;
  detail: string;
  /** 답을 받아야 하면 문구, 아니면 null. 이미 답한 건은 null이다. */
  question: string | null;
  user_answer: EventAnswer | string;
  excluded: boolean;
  /** 답한 뒤 목록에 표시할 한 줄. 아직 답하지 않았으면 null. */
  status: string | null;
};

export type EventsResponse = {
  generated_at: string;
  /** 목록 위에 한 번만 두는 설명. 칸마다 반복하지 않는다. */
  intro: string[];
  summary: {
    total: number;
    pending: number;
    excluded: number;
    /** 대기 화면 알림 바 문구. 없으면 null. */
    alert: string | null;
  };
  items: CareEvent[];
};

// ── POST /api/care/events/{id}/answer ────────────────────────

export type GuidanceProduct = {
  user_product_id: string;
  name: string | null;
  brand: string | null;
  score: number;
  band: RiskBand;
};

export type EventAnswerResponse = {
  event: CareEvent;
  headline: string;
  lines: string[];
  /** "아니요"로 답했을 때만 온다. 확인 순위 상위 제품이 담긴다. */
  next: { action: string; products: GuidanceProduct[] } | null;
};

// ── GET /api/care/products/{id}/protocol ─────────────────────
//
// 설계서 §5-6. 식약처 화장품 안정성시험 가이드라인의 시험항목을
// 소비자가 확인 가능한 형태로 옮긴 표다. 카테고리마다 순서가 다르다.

export type CheckStep = {
  order: number;
  /** 가이드라인의 어느 시험항목에서 왔는지 (성상·색, 냄새 등) */
  basis: string;
  text: string;
  /** AS7341 측정으로 도울 수 있는 항목 */
  optical: boolean;
};

export type ProtocolResponse = {
  user_product_id: string;
  name: string | null;
  brand: string | null;
  /** 확인 유형 (오일·세럼 등) */
  label: string;
  score: number | null;
  band: RiskBand | null;
  reasons: string[];
  steps: CheckStep[];
  answers: string[];
  /** 눈가 제품처럼 따로 덧붙일 말 */
  caution: string | null;
  note: string | null;
};

// ── POST /api/care/products/{id}/inspection ──────────────────

export type GuidanceSection = {
  label: string;
  lines: string[];
};

export type InspectionResponse = {
  user_product_id: string;
  answers: string[];
  headline: string;
  /** 사용자가 고른 항목마다 하나씩 */
  sections: GuidanceSection[];
  lines: string[];
  recommend_replace: boolean;
  /** 점검 목록에 표시할 짧은 항목명 */
  findings: string[];
};
// ── 측정 세션 (/api/care/measure/sessions) ───────────────────
//
// 키오스크는 센서를 읽을 수 없고 측정 노드에는 화면이 없다. 둘이 "지금
// 이 한 번의 측정"을 같이 가리키는 것이 세션이다. 키오스크가 열고, 노드가
// 두 번에 나눠 채우고(백색 표준판 → 시료), 키오스크가 읽어 간다.
//
// 상태가 waiting_*와 capturing_*로 갈라지는 이유: 노드는 측정부에 무엇이
// 올라와 있는지 알 수 없다. 사용자가 화면에서 "측정"을 눌러야(capture)
// 비로소 잰다. 그 전에 재면 아무것도 없는 측정부를 잰다.

export type MeasureStatus =
  | "waiting_white"
  | "capturing_white"
  | "waiting_sample"
  | "capturing_sample"
  | "done"
  | "failed"
  | "expired"
  | "cancelled";

export type MeasureSession = {
  session_id: string;
  status: MeasureStatus;
  /** 지금 다루는 단계. 누르기 전과 재는 중이 같은 단계다. */
  step: "white" | "sample" | null;
  /** 노드가 재고 있는 중. 화면은 버튼을 감추고 기다린다. */
  capturing: boolean;
  /** 사용자가 눌러야 다음으로 넘어가는 상태. */
  awaiting_tap: boolean;
  node_id: string;
  node_label: string | null;
  user_product_id: string | null;
  /** done일 때만. 이번 측정이 기준값이 되었는지. */
  baseline: boolean | null;
  /** done이고 기준값이 아닐 때만. 처음 잰 색과의 차이(%). */
  delta_pct: number | null;
  message: string;
  poll_sec: number;
  expires_at: string | null;
};

export type MeasureStartResponse = MeasureSession & {
  /** 이미 기준값이 있는지. 첫 측정이면 결과 화면이 달라진다. */
  has_baseline: boolean;
  /** 이 제형을 색으로 재는 것의 한계 한 줄. 서버가 만든다. */
  optical_note: string;
};
