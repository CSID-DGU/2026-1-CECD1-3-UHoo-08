-- 014_link_feedback_to_event.sql
--
-- 확인 결과를 어느 이벤트에 대한 것인지 잇는다.
--
-- answered_at도 함께 둔다. "언제 답했는가"는 이벤트의 속성이고,
-- 확인 결과와는 별개로 알아야 할 값이다.

ALTER TABLE user_feedback
  ADD COLUMN IF NOT EXISTS event_id BIGINT REFERENCES risk_events(id) ON DELETE SET NULL;

-- 이벤트별 확인 결과 조회용
CREATE INDEX IF NOT EXISTS idx_feedback_event
  ON user_feedback (event_id) WHERE event_id IS NOT NULL;

ALTER TABLE risk_events
  ADD COLUMN IF NOT EXISTS answered_at TIMESTAMPTZ;

COMMENT ON COLUMN user_feedback.event_id IS
  '이 확인이 어느 이상 이벤트에 대한 것인지. 이벤트와 무관한 확인이면 NULL';
COMMENT ON COLUMN risk_events.answered_at IS '사용자가 답한 시각';