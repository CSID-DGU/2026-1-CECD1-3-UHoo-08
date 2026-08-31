-- 017_skin_measurement_channels.sql
--
-- 피부 측정에 원본 채널값을 함께 남긴다.
--
-- skin_measurements는 지금까지 L*a*b*만 담았다. 시드 스크립트가 Lab을 바로
-- 만들어 넣었기 때문에 그것으로 충분했다.
--
-- 그런데 실제 노드가 보내는 것은 AS7341 채널값이고, Lab은 거기서 계산한
-- 결과다(services/iot/skin_color). 계산 결과만 남기면 변환식을 고쳤을 때
-- 과거 측정을 다시 계산할 방법이 없다. 여덟 점 적분은 근사라 앞으로 손볼
-- 여지가 크고, 그때 지난 데이터가 통째로 버려지면 추이가 끊긴다.
--
-- db/iot/skin_reader가 ITA°와 홍반 지수를 저장하지 않고 읽을 때 계산하는
-- 것과 같은 이유다. 원본을 남기고, 파생값은 언제든 다시 만든다.
--
-- lab_l/a/b도 그대로 둔다. 시드가 만든 과거 측정에는 채널값이 없고,
-- 조회 경로가 이미 그 컬럼을 쓰고 있다.

ALTER TABLE skin_measurements ADD COLUMN IF NOT EXISTS channels  JSONB;
ALTER TABLE skin_measurements ADD COLUMN IF NOT EXISTS white_ref JSONB;

COMMENT ON COLUMN skin_measurements.channels IS
  'AS7341 원본 채널값(암전류 보정 후). 시드로 만든 과거 측정에는 없다';
COMMENT ON COLUMN skin_measurements.white_ref IS
  '같은 세션에서 잰 백색 표준판. 이것으로 나눠야 반사율이 된다';

-- 부위별 추이 조회. 부위가 다르면 값도 달라 섞어서 그리면 안 된다.
CREATE INDEX IF NOT EXISTS idx_skin_user_site_ts
  ON skin_measurements (user_id, site, ts DESC);
