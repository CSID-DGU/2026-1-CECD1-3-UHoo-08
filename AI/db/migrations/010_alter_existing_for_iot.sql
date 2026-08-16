-- ============================================
-- IoT 스키마
--   products.product_id      : uuid
--   users.id                 : uuid
--   user_products.id         : uuid
-- ============================================

-- 1. 노드 레지스트리
CREATE TABLE IF NOT EXISTS iot_nodes (
  node_id        TEXT PRIMARY KEY,
  user_id        UUID REFERENCES users(id),
  node_type      TEXT NOT NULL
                 CHECK (node_type IN ('storage','ambient','measure')),
  location_label TEXT,
  installed_at   TIMESTAMPTZ DEFAULT now()
);

-- 2. 센서 원시 데이터
CREATE TABLE IF NOT EXISTS sensor_readings (
  id             BIGSERIAL PRIMARY KEY,
  node_id        TEXT NOT NULL REFERENCES iot_nodes(node_id),
  ts             TIMESTAMPTZ NOT NULL,      -- 센서 측정 시각 (NTP)
  temperature    REAL,
  humidity       REAL,
  pm25           REAL,
  gas_resistance REAL,
  created_at     TIMESTAMPTZ DEFAULT now()  -- 서버 수신 시각
);
CREATE INDEX IF NOT EXISTS idx_readings_node_ts
  ON sensor_readings (node_id, ts DESC);

-- 3. VOC 회귀 기준선
CREATE TABLE IF NOT EXISTS storage_baseline (
  node_id     TEXT PRIMARY KEY REFERENCES iot_nodes(node_id),
  coef_a      REAL,
  coef_temp   REAL,
  coef_humid  REAL,
  residual_sd REAL,
  trained_at  TIMESTAMPTZ,
  sample_n    INT
);

-- 4. 제품 열 민감도 + 광학 적합성  ★ uuid
CREATE TABLE IF NOT EXISTS product_thermal_profile (
  product_id    UUID PRIMARY KEY REFERENCES products(product_id),
  sensitivity_k REAL NOT NULL DEFAULT 1.0,
  pao_months    INT,
  optical_grade TEXT
                CHECK (optical_grade IN ('suitable','conditional','unsuitable')),
  driver_note   TEXT,
  updated_at    TIMESTAMPTZ DEFAULT now()
);

-- 5. 광학 기준값  ★ user_product_id uuid
CREATE TABLE IF NOT EXISTS optical_baselines (
  id              BIGSERIAL PRIMARY KEY,
  user_product_id UUID REFERENCES user_products(id),
  ts              TIMESTAMPTZ NOT NULL,
  channels        JSONB,     -- F1~F8, Clear, NIR
  white_ref       JSONB      -- 백색 표준판 측정값
);
CREATE INDEX IF NOT EXISTS idx_optbase_up
  ON optical_baselines (user_product_id, ts DESC);

-- 6. 광학 측정 이력
CREATE TABLE IF NOT EXISTS optical_measurements (
  id              BIGSERIAL PRIMARY KEY,
  user_product_id UUID REFERENCES user_products(id),
  ts              TIMESTAMPTZ NOT NULL,
  channels        JSONB,
  white_ref       JSONB,
  delta_pct       REAL       -- 기준값 대비 변화율
);
CREATE INDEX IF NOT EXISTS idx_optmeas_up
  ON optical_measurements (user_product_id, ts DESC);

-- 7. 이상 이벤트 + 사용자 확인
CREATE TABLE IF NOT EXISTS risk_events (
  id           BIGSERIAL PRIMARY KEY,
  node_id      TEXT REFERENCES iot_nodes(node_id),
  ts           TIMESTAMPTZ NOT NULL,
  event_type   TEXT
               CHECK (event_type IN ('voc_spike','temp_excursion','humid_excursion')),
  magnitude    REAL,
  user_answer  TEXT
               CHECK (user_answer IN ('external_source','none','pending')),
  excluded     BOOLEAN DEFAULT FALSE,
  created_at   TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_events_pending
  ON risk_events (ts DESC) WHERE user_answer = 'pending';

-- 8. 피부 광학 측정
CREATE TABLE IF NOT EXISTS skin_measurements (
  id      BIGSERIAL PRIMARY KEY,
  user_id UUID REFERENCES users(id),
  ts      TIMESTAMPTZ NOT NULL,
  lab_l   REAL, lab_a REAL, lab_b REAL,
  gloss   REAL,
  site    TEXT
);
CREATE INDEX IF NOT EXISTS idx_skin_user_ts
  ON skin_measurements (user_id, ts DESC);

-- ============================================
-- 9. 기존 테이블 확장
-- ============================================
ALTER TABLE user_products ADD COLUMN IF NOT EXISTS purchased_at    DATE;
ALTER TABLE user_products ADD COLUMN IF NOT EXISTS opened_at       DATE;
ALTER TABLE user_products ADD COLUMN IF NOT EXISTS storage_node_id TEXT;
ALTER TABLE user_products ADD COLUMN IF NOT EXISTS last_checked_at TIMESTAMPTZ;
ALTER TABLE products      ADD COLUMN IF NOT EXISTS barcode         TEXT;
CREATE INDEX IF NOT EXISTS idx_products_barcode
  ON products (barcode) WHERE barcode IS NOT NULL;