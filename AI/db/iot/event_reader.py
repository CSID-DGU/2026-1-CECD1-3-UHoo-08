"""
이상 이벤트 조회·기록.

risk_events는 세 종류를 담는다.
    temp_excursion   고온 노출 (30℃ 이상이 30분 넘게 지속)
    humid_excursion  고습 노출
    voc_spike        가스 저항 급락

── 왜 사용자에게 되묻는가 ──────────────────────────────────────────
VOC 급등의 원인을 알고리즘만으로 가릴 수 없다. 향수를 뿌려도, 헤어스프레이를
써도, 네일 리무버를 열어도 저항이 똑같이 떨어진다. 실측에서도 향수 분무에
-92.9%가 나왔다.

그래서 시스템이 단정하지 않고 묻는다. 사용자가 "향수를 뒀다"고 답하면 그
기록을 분석에서 빼고(excluded), "아니다"라고 하면 유효한 이벤트로 남긴다.
설계서의 Human-in-the-loop이 이것이다.

user_answer는 세 값만 허용된다(스키마 CHECK 제약).
    pending           아직 묻지 않았거나 답을 받지 못함
    external_source   외부 요인이었다 → excluded
    none              짚이는 것이 없다 → 유효한 이벤트
"""
from __future__ import annotations

import logging

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from db.supabase_client import get_supabase

logger = logging.getLogger(__name__)

ANSWER_PENDING = "pending"
ANSWER_EXTERNAL = "external_source"
ANSWER_NONE = "none"

VALID_ANSWERS = (ANSWER_EXTERNAL, ANSWER_NONE)

_COLUMNS = ("id, node_id, ts, event_type, magnitude, user_answer, excluded, "
            "answered_at, created_at")


def get_risk_events(
    node_ids: List[str],
    *,
    limit: int = 30,
    pending_only: bool = False,
) -> List[Dict[str, Any]]:
    """
    이벤트 이력. 최신순.

    pending_only는 아직 답하지 않은 건만 가져온다. 대기 화면 알림 바가
    이것을 쓴다.
    """
    if not node_ids:
        return []

    sb = get_supabase()
    q = (
        sb.table("risk_events")
        .select(_COLUMNS)
        .in_("node_id", node_ids)
        .order("ts", desc=True)
        .limit(limit)
    )
    if pending_only:
        q = q.eq("user_answer", ANSWER_PENDING)

    return (q.execute()).data or []


def count_pending(node_ids: List[str]) -> int:
    """답을 기다리는 이벤트 수. 알림 바 표시 여부를 정한다."""
    if not node_ids:
        return 0
    sb = get_supabase()
    res = (
        sb.table("risk_events")
        .select("id", count="exact")
        .in_("node_id", node_ids)
        .eq("user_answer", ANSWER_PENDING)
        .execute()
    )
    return res.count or 0


def get_event(event_id: int) -> Optional[Dict[str, Any]]:
    sb = get_supabase()
    rows = (
        sb.table("risk_events")
        .select(_COLUMNS)
        .eq("id", event_id)
        .limit(1)
        .execute()
    ).data or []
    return rows[0] if rows else None


def answer_event(event_id: int, answer: str) -> Optional[Dict[str, Any]]:
    """
    사용자의 답을 기록한다.

    excluded는 답에서 따라 나오므로 호출하는 쪽이 정하지 않는다. 두 값을
    따로 받으면 "외부 요인인데 제외 안 됨" 같은 모순된 행이 생긴다.

    이미 답한 이벤트에 다시 답하는 것은 허용한다. 사용자가 잘못 눌렀을 때
    되돌릴 방법이 있어야 한다.
    """
    if answer not in VALID_ANSWERS:
        raise ValueError(f"허용되지 않는 답: {answer}")

    sb = get_supabase()
    patch: Dict[str, Any] = {
        "user_answer": answer,
        "excluded": answer == ANSWER_EXTERNAL,
        "answered_at": datetime.now(timezone.utc).isoformat(),
    }
    (sb.table("risk_events").update(patch).eq("id", event_id).execute())

    return get_event(event_id)


def close_event_by_inspection(event_id: int) -> Optional[Dict[str, Any]]:
    """
    제품 확인이 끝났을 때 그 이벤트를 완료로 바꾼다.

    "짚이는 외부 요인이 없다"는 답만으로는 아직 끝이 아니다. 그다음
    제품을 확인해야 무엇이 문제였는지 알 수 있다. 그래서 "아니요"를
    누른 시점에는 이벤트를 그대로 두고, 확인이 끝난 뒤 여기서 닫는다.

    중간에 그만두면 질문이 그대로 남는다. 그게 맞다. 확인하지 않았는데
    답변 완료로 처리하면, 사용자는 아무것도 안 했는데 질문만 사라진다.
    """
    sb = get_supabase()
    patch = {
        "user_answer": ANSWER_NONE,
        "excluded": False,
        "answered_at": datetime.now(timezone.utc).isoformat(),
    }
    (sb.table("risk_events").update(patch).eq("id", event_id).execute())
    return get_event(event_id)


def get_event_findings(event_ids: List[int]) -> Dict[int, List[str]]:
    """
    이벤트별 확인 결과 코드.

    FK로 이어져 있으므로 시각을 추측할 필요가 없다. 같은 확인에서 여러
    항목을 골랐으면 그만큼 행이 있다.
    """
    if not event_ids:
        return {}

    sb = get_supabase()
    rows = (
        sb.table("user_feedback")
        .select("event_id, answer, ts")
        .in_("event_id", event_ids)
        .order("ts", desc=True)
        .limit(200)
        .execute()
    ).data or []

    out: Dict[int, List[str]] = {}
    for r in rows:
        eid = r.get("event_id")
        if eid is None:
            continue
        code = r.get("answer")
        if not code:
            continue
        bucket = out.setdefault(eid, [])
        if code not in bucket:
            bucket.append(code)
    return out


def get_latest_feedback(user_product_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    """
    제품별 가장 최근 확인 결과.

    같은 시각에 여러 항목을 고를 수 있으므로, 최신 ts의 행들을 묶어
    항목 목록으로 만든다. "냄새 변화 · 층 분리"처럼 함께 보여야 한다.

    제품마다 따로 조회하지 않고 한 번에 읽는다. 점검 목록이 열 개 넘는
    제품을 그리는데 제품당 한 번씩 부르면 그만큼 왕복이 늘어난다.
    """
    if not user_product_ids:
        return {}

    sb = get_supabase()
    rows = (
        sb.table("user_feedback")
        .select("user_product_id, ts, answer")
        .in_("user_product_id", user_product_ids)
        .order("ts", desc=True)
        .limit(200)
        .execute()
    ).data or []

    out: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        up = r.get("user_product_id")
        if not up:
            continue
        cur = out.get(up)
        if cur is None:
            out[up] = {"ts": r.get("ts"), "answers": [r.get("answer")]}
        elif cur["ts"] == r.get("ts"):
            # 같은 확인에서 함께 고른 항목
            cur["answers"].append(r.get("answer"))
        # 더 오래된 확인은 무시한다. 최신 것만 본다.

    return out