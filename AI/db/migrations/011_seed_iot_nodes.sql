-- 011_seed_iot_nodes.sql
-- 개발 환경 전용 시드. 프로덕션 배포 대상 아님.

INSERT INTO iot_nodes (node_id, user_id, node_type, location_label)
VALUES
  ('storage-01', 'aa000000-0000-0000-0000-000000000001', 'storage', '화장대'),
  ('ambient-01', 'aa000000-0000-0000-0000-000000000001', 'ambient', '침실'),
  ('ambient-02', 'aa000000-0000-0000-0000-000000000001', 'ambient', '사무실'),
  ('measure-01', 'aa000000-0000-0000-0000-000000000001', 'measure', '휴대형')
ON CONFLICT (node_id) DO NOTHING;