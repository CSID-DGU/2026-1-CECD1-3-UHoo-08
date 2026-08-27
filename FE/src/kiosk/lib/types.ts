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