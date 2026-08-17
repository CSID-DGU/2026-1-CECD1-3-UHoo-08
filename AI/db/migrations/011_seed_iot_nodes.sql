-- 011_seed_iot_nodes.sql
-- 개발 환경 전용 시드. 프로덕션 배포 대상 아님.
-- 
-- iot_nodes.user_id가 users(id)를 FK로 참조하므로, 테스트 사용자를 먼저 생성한다.
-- WHERE EXISTS로 건너뛰는 대신 전제를 직접 만드는 이유:
-- 조용히 0행 삽입되면 마이그레이션은 성공으로 보이지만 노드가 없어,
-- ESP32가 404를 받은 뒤에야 원인을 찾게 된다.

-- 1. 테스트 사용자 (users에서 NOT NULL은 name, provider)
INSERT INTO users (id, name, provider, onboarding_completed)
VALUES ('aa000000-0000-0000-0000-000000000001',
        'IoT 테스트', 'local', true)
ON CONFLICT (id) DO NOTHING;

-- 2. 노드 4대
INSERT INTO iot_nodes (node_id, user_id, node_type, location_label)
VALUES
  ('storage-01', 'aa000000-0000-0000-0000-000000000001', 'storage', '화장대'),
  ('ambient-01', 'aa000000-0000-0000-0000-000000000001', 'ambient', '침실'),
  ('ambient-02', 'aa000000-0000-0000-0000-000000000001', 'ambient', '사무실'),
  ('measure-01', 'aa000000-0000-0000-0000-000000000001', 'measure', '휴대형')
ON CONFLICT (node_id) DO NOTHING;