-- 015_create_measure_sessions.sql
--
-- 측정 세션.
--
-- 키오스크(iPad PWA)는 센서를 읽을 수 없고, 측정 노드(ESP32+AS7341)는
-- 화면도 입력도 없다. 두 기기가 "지금 이 한 번의 측정"을 같이 가리키려면
-- 그 측정이 서버에 실체로 있어야 한다.
--
--   키오스크가 세션을 연다      → status=waiting_white
--   노드가 폴링으로 발견한다    → 버튼 → 백색 표준판 전송 → waiting_sample
--                              → 버튼 → 시료 전송        → done
--   키오스크가 세션을 다시 읽어 결과를 보여준다
--
-- 백색 표준판을 별도 단계로 둔 이유는 optical.reflectance가 채널값을
-- 그것으로 나누기 때문이다. 조명이 바뀌면 채널값이 통째로 커지거나 작아져
-- 변화율이 의미를 잃는다.
--
-- 값을 optical_measurements에 바로 넣지 않고 세션에 먼저 담는 이유:
-- 백색과 시료는 시각이 다른 두 번의 전송으로 들어오고, 둘이 다 모여야
-- 비로소 한 건의 측정이 된다. 반쪽짜리 행을 측정 이력에 남기지 않는다.

CREATE TABLE IF NOT EXISTS measure_sessions (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  node_id         TEXT NOT NULL REFERENCES iot_nodes(node_id),
  user_id         UUID REFERENCES users(id),

  -- 무엇을 재는가. 화장품이면 user_product_id, 피부면 site가 채워진다.
  target          TEXT NOT NULL DEFAULT 'product'
                  CHECK (target IN ('product','skin')),
  user_product_id UUID REFERENCES user_products(id),
  site            TEXT,

  status          TEXT NOT NULL DEFAULT 'waiting_white'
                  CHECK (status IN ('waiting_white','waiting_sample',
                                    'done','expired','cancelled','failed')),

  -- 노드가 채우는 값
  white_ref       JSONB,   -- 백색 표준판 (암전류 보정 후)
  channels        JSONB,   -- 시료      (암전류 보정 후)
  -- 게인·LED 전류·펌웨어 버전. 백색과 시료가 같은 조건에서 측정됐는지
  -- 확인하는 데 쓴다. 조건이 다르면 나눗셈 자체가 성립하지 않는다.
  meta            JSONB,
  saturated       BOOLEAN NOT NULL DEFAULT FALSE,

  -- 결과. 키오스크가 이것만 읽어 화면을 그린다.
  baseline        BOOLEAN,   -- 이번 측정이 기준값이 되었는지
  delta_pct       REAL,
  message         TEXT,

  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  -- 사용자가 도중에 자리를 뜨면 세션이 영원히 열려 있게 된다. 그러면
  -- 그 노드로는 다음 측정을 시작할 수 없다. 시한을 두고 지난 것은 만료시킨다.
  expires_at      TIMESTAMPTZ NOT NULL
);

-- 노드가 2초 간격으로 "내 일감 있나"를 묻는다. 그 조회만 빠르면 된다.
CREATE INDEX IF NOT EXISTS idx_measure_sessions_open
  ON measure_sessions (node_id, created_at DESC)
  WHERE status IN ('waiting_white','waiting_sample');

CREATE INDEX IF NOT EXISTS idx_measure_sessions_user
  ON measure_sessions (user_id, created_at DESC);

COMMENT ON COLUMN measure_sessions.saturated IS
  'AS7341 ADC가 천장에 닿은 측정. 값이 잘려 나가 비교에 쓸 수 없다';
COMMENT ON COLUMN measure_sessions.meta IS
  '{"gain":"64x","led_ma":10,"dark_applied":true,"fw":"optical-v1"}';
