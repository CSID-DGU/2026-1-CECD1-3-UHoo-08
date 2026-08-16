-- sensor_readings 중복 방지
-- ESP32가 Wi-Fi 복구 후 버퍼를 재전송할 때 동일 (node_id, ts)가 중복 유입되는 것을 막는다.

CREATE UNIQUE INDEX IF NOT EXISTS uq_readings_node_ts
  ON sensor_readings (node_id, ts);