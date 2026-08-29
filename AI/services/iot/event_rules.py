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
            #
            # 처음에는 "향수나 스프레이 제품을 두셨나요"였는데 너무 좁았다.
            # 매니큐어, 소독용 알코올, 헤어 제품, 방향제, 청소 세제까지
            # 전부 같은 신호를 낸다. 사용자가 "향수는 안 뒀는데"라고
            # 생각하고 아니요를 누르면 엉뚱한 곳을 뒤지게 된다.
            "question": "이 무렵 근처에서 향수·스프레이·소독제처럼 "
                        "냄새가 강한 것을 쓰신 적이 있나요?",
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
        # 저장 이야기는 하지 않는다. 사용자가 알아야 할 것은
        # "내 화장품 문제가 아니었다"는 사실이다.
        lines = ["보관 중인 화장품에서 비롯된 변화가 아닙니다.",
                 "주변에서 일시적으로 들어온 성분으로 보입니다."]
        if kind == "voc_spike":
            lines.append(
                "냄새가 강한 제품은 화장품과 조금 떨어뜨려 두시면 "
                "이런 일이 줄어듭니다."
            )
        return {
            "headline": "일시적인 외부 요인이었습니다",
            "lines": lines,
            "next": None,
            "excluded": True,
        }

    # "아니요" — 외부 요인이 아니라면 보관 중인 제품 쪽을 볼 차례다.
    # 여기서도 판정하지 않는다. 확인해 볼 순서를 알려줄 뿐이다.
    if top_products:
        return {
            "headline": "어떤 제품을 확인해 볼까요?",
            "lines": ["같은 보관함에 있던 제품을 확인 순위가 높은 순으로 보여드릴게요.",
                      "확인할 제품을 골라 주세요."],
            "next": {"action": "priority", "products": top_products},
            "excluded": False,
        }

    return {
        "headline": "지금 확인할 제품은 없습니다",
        "lines": ["같은 보관함의 제품은 모두 정상 범위입니다."],
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