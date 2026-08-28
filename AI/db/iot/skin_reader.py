"""
피부 측정 조회.

skin_measurements는 CIE L*a*b*와 광택을 저장한다. 화면이 쓰는 ITA°와
홍반 지수는 그 값에서 계산해 낸다. DB에 계산 결과를 넣지 않는 이유는,
계산식이 바뀌면 과거 데이터를 전부 다시 써야 하기 때문이다. 원본을
남기고 읽을 때 계산한다.

── ITA°와 홍반 지수 ────────────────────────────────────────────────
ITA°(Individual Typology Angle)는 피부 밝기를 하나의 각도로 나타내는
피부과학 표준 지표다.

    ITA° = arctan((L* - 50) / b*) × 180 / π

홍반 지수는 붉은기다. 여러 정의가 있는데 여기서는 a*를 그대로 쓴다.
a*는 CIE Lab의 적록 축이고, 값이 클수록 붉다.

── 절대값으로 판정하지 않는다 ──────────────────────────────────────
ITA° 41이 "좋다"거나 "나쁘다"고 말할 수 없다. 사람마다 타고난 값이 다르다.
우리가 보는 것은 같은 부위를 반복 측정했을 때의 변화뿐이다. 그래서
화면도 절대값 옆에 항상 직전 대비 변화량을 함께 보여준다.
"""
from __future__ import annotations

import logging
import math

from typing import Any, Dict, List, Optional

from db.supabase_client import get_supabase

logger = logging.getLogger(__name__)

# ITA° 구간. 국제적으로 통용되는 분류를 그대로 쓴다.
_ITA_CLASSES = (
    (55.0, "Very light"),
    (41.0, "Light"),
    (28.0, "Intermediate"),
    (10.0, "Tan"),
    (-30.0, "Brown"),
)


def ita_degree(lab_l: Optional[float], lab_b: Optional[float]) -> Optional[float]:
    """ITA°. b*가 0이면 정의되지 않으므로 None."""
    if lab_l is None or lab_b is None:
        return None
    try:
        b = float(lab_b)
        if abs(b) < 1e-6:
            return None
        return math.degrees(math.atan((float(lab_l) - 50.0) / b))
    except (TypeError, ValueError):
        return None


def ita_class(ita: Optional[float]) -> Optional[str]:
    if ita is None:
        return None
    for threshold, name in _ITA_CLASSES:
        if ita > threshold:
            return name
    return "Dark"


def get_skin_measurements(
    user_id: str,
    *,
    limit: int = 20,
    site: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    피부 측정 이력을 최신순으로 가져온다.

    site를 지정하면 그 부위만 본다. 부위가 다르면 값도 다르므로 섞어서
    추이를 그리면 안 된다. 지정하지 않으면 가장 최근 측정의 부위를
    기준으로 상위 호출자가 걸러야 한다.
    """
    sb = get_supabase()
    q = (
        sb.table("skin_measurements")
        .select("id, ts, lab_l, lab_a, lab_b, gloss, site")
        .eq("user_id", user_id)
        .order("ts", desc=True)
        .limit(limit)
    )
    if site:
        q = q.eq("site", site)

    rows = (q.execute()).data or []

    out: List[Dict[str, Any]] = []
    for r in rows:
        ita = ita_degree(r.get("lab_l"), r.get("lab_b"))
        out.append({
            "ts": r.get("ts"),
            "lab_l": r.get("lab_l"),
            "lab_a": r.get("lab_a"),
            "lab_b": r.get("lab_b"),
            "gloss": r.get("gloss"),
            "site": r.get("site"),
            "ita": round(ita, 1) if ita is not None else None,
            "ita_class": ita_class(ita),
            # 홍반 지수는 a*를 그대로 쓴다
            "erythema": r.get("lab_a"),
        })
    return out


def get_risk_events(
    node_ids: List[str],
    *,
    limit: int = 30,
    pending_only: bool = False,
) -> List[Dict[str, Any]]:
    """
    이상 이벤트 이력.

    pending_only는 사용자가 아직 답하지 않은 건만 가져온다. 키오스크가
    "향수나 스프레이 제품을 두셨나요?"를 물어야 하는 건들이다.
    """
    if not node_ids:
        return []

    sb = get_supabase()
    q = (
        sb.table("risk_events")
        .select("id, node_id, ts, event_type, magnitude, user_answer, excluded")
        .in_("node_id", node_ids)
        .order("ts", desc=True)
        .limit(limit)
    )
    if pending_only:
        q = q.eq("user_answer", "pending")

    return (q.execute()).data or []