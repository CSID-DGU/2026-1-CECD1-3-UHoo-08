-- 점검 결과 피드백
-- 개인별 임계값 조정 + "사람이 몇 %에서 알아채는가" 감지 임계 데이터 축적

CREATE TABLE IF NOT EXISTS user_feedback (
  id              BIGSERIAL PRIMARY KEY,
  user_product_id UUID REFERENCES user_products(id),
  ts              TIMESTAMPTZ NOT NULL DEFAULT now(),
  risk_score      REAL,      -- 안내 시점의 위험 점수
  delta_pct       REAL,      -- 안내 시점의 광학 변화율
  answer          TEXT NOT NULL
                  CHECK (answer IN ('none','color','odor','separation','texture'))
);

CREATE INDEX IF NOT EXISTS idx_feedback_up_ts
  ON user_feedback (user_product_id, ts DESC);

-- 감지 임계 곡선 집계용 (변화율 구간별 감지율)
CREATE INDEX IF NOT EXISTS idx_feedback_delta
  ON user_feedback (delta_pct) WHERE delta_pct IS NOT NULL;