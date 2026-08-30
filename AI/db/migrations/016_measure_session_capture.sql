-- 016_measure_session_capture.sql
--
-- 측정 트리거를 노드 버튼에서 키오스크 화면으로 옮긴다.
--
-- 노드는 "지금 시료가 올라와 있는지"를 알 수 없다. 그것을 아는 사람은 방금
-- 손으로 올려놓은 사용자뿐이다. 처음에는 노드에 물리 버튼을 달아 그 신호를
-- 받으려 했는데, 안내는 키오스크가 하고 트리거만 노드에서 눌러야 해서
-- 사용자의 시선과 손이 두 기기로 갈라진다. 어차피 키오스크를 보고 있으므로
-- 거기서 누르는 편이 낫고, 노드에서는 부품이 하나 줄어든다.
--
-- 그래서 상태가 둘로 갈라진다.
--
--   waiting_white     사용자가 백색 표준판을 올려놓는 중. 노드는 아무것도 안 한다
--   capturing_white   키오스크에서 "측정"을 눌렀다. 노드가 폴링으로 발견해 잰다
--   waiting_sample    백색이 들어왔다. 사용자가 제품으로 바꿔 올리는 중
--   capturing_sample  다시 눌렀다. 노드가 잰다 → done
--
-- 이렇게 나누지 않고 waiting_* 상태에서 바로 재게 하면, 아직 아무것도
-- 올려놓지 않은 허공을 재서 그 값이 기준값으로 굳는다.

ALTER TABLE measure_sessions
  DROP CONSTRAINT IF EXISTS measure_sessions_status_check;

ALTER TABLE measure_sessions
  ADD CONSTRAINT measure_sessions_status_check
  CHECK (status IN ('waiting_white','capturing_white',
                    'waiting_sample','capturing_sample',
                    'done','expired','cancelled','failed'));

-- 노드가 2초 간격으로 "내 일감 있나"를 묻는다. 새 상태도 열린 것으로 본다.
DROP INDEX IF EXISTS idx_measure_sessions_open;
CREATE INDEX IF NOT EXISTS idx_measure_sessions_open
  ON measure_sessions (node_id, created_at DESC)
  WHERE status IN ('waiting_white','capturing_white',
                   'waiting_sample','capturing_sample');
