"""
이벤트 문구와 답변 후 안내 규칙 테이블.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from db.iot.event_reader import ANSWER_EXTERNAL, ANSWER_NONE, ANSWER_PENDING

KST = timezone(timedelta(hours=9))


# ── 이벤트 문구 ──────────────────────────────────────────────────

def describe(event: Dict[str, Any], node_label: Optional[str] = None) -> Dict[str, Any]:
    """
    이벤트 한 건을 사람이 읽는 형태로.

    magnitude의 의미가 종류마다 다르다는 점이 중요하다. 고온 노출은 최고
    온도(℃)이고 VOC는 하락률(%)이다. 숫자만 보여주면 34.9와 66.8이 같은
    단위처럼 보인다.
    """
    kind = event.get("event_type")
    mag = event.get("magnitude")
    where = node_label or event.get("node_id") or "보관함"

    if kind == "temp_excursion":
        return {
            "title": "고온 노출",
            "detail": (f"{where} 최고 {mag:.1f}℃ · 30분 이상 지속"
                       if mag is not None else f"{where} 고온 지속"),
            "question": None,
            "unit": "℃",
        }

    if kind == "humid_excursion":
        return {
            "title": "고습 노출",
            "detail": (f"{where} 최고 {mag:.0f}% · 30분 이상 지속"
                       if mag is not None else f"{where} 고습 지속"),
            "question": None,
            "unit": "%",
        }

    if kind == "voc_spike":
        return {
            "title": "공기 성분 변화",
            "detail": (f"{where} 가스 저항이 평소보다 {mag:.0f}% 낮아졌습니다"
                       if mag is not None else f"{where} 가스 저항 변화"),
            # 이 질문이 Human-in-the-loop의 입구다.
            "question": "이 시각에 향수나 스프레이 제품을 두셨나요?",
            "unit": "%",
        }

    return {"title": "이상 기록", "detail": where, "question": None, "unit": None}


def when(ts: Any) -> str:
    """시각을 짧게. 화면이 좁아 연도는 빼고 요일을 넣는다."""
    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00")).astimezone(KST)
    except (ValueError, TypeError):
        return "-"
    return f"{dt.month}/{dt.day}({'월화수목금토일'[dt.weekday()]}) {dt.hour:02d}:{dt.minute:02d}"


# ── 답변 후 안내 ─────────────────────────────────────────────────

def guidance(
    event: Dict[str, Any],
    answer: str,
    top_products: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    답을 받은 뒤 보여줄 안내.

    top_products는 "아니요"일 때만 쓴다. 점검 우선순위 상위 제품을 넘기면
    화면이 그것을 함께 보여준다. 없으면 문장만 나온다.
    """
    kind = event.get("event_type")

    if answer == ANSWER_EXTERNAL:
        lines = ["확인해 주셔서 감사합니다.",
                 "이 기록은 분석에서 빼겠습니다."]
        if kind == "voc_spike":
            lines.append(
                "향이 강한 제품은 화장품과 조금 떨어뜨려 두시면 "
                "기록이 더 정확해집니다."
            )
        return {
            "headline": "외부 요인으로 기록했습니다",
            "lines": lines,
            "next": None,
            "excluded": True,
        }

    # "아니요" — 이벤트가 유효하다. 다만 여기서도 판정하지 않는다.
    lines = ["알겠습니다. 이 기록은 그대로 두겠습니다."]

    if top_products:
        lines.append("같은 보관함에 있던 제품 중 확인 순위가 높은 것을 보여드릴게요.")
        return {
            "headline": "확인해 보시겠어요?",
            "lines": lines,
            "next": {"action": "priority", "products": top_products},
            "excluded": False,
        }

    lines.append("현재 확인이 필요한 제품은 없습니다. 기록만 남겨두겠습니다.")
    return {
        "headline": "기록했습니다",
        "lines": lines,
        "next": None,
        "excluded": False,
    }


# ── 알림 바 ──────────────────────────────────────────────────────

def alert_line(pending: int) -> Optional[str]:
    """
    대기 화면 하단에 띄울 한 줄. 없으면 None.

    경고가 아니라 질문이므로 "확인이 필요한 질문"이라고 쓴다.
    "이상 감지" 같은 표현은 쓰지 않는다.
    """
    if pending <= 0:
        return None
    if pending == 1:
        return "확인이 필요한 질문이 하나 있습니다"
    return f"확인이 필요한 질문이 {pending}개 있습니다"


__all__ = [
    "describe", "when", "guidance", "alert_line",
    "ANSWER_PENDING", "ANSWER_EXTERNAL", "ANSWER_NONE",
]