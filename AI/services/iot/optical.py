"""
AS7341 색 변화 계산.

── 왜 기준값이 필요한가 ────────────────────────────────────────────
이 센서는 "이 제품이 상했다"를 알려주지 않는다. 알려주는 것은 **처음 잰
색과 지금 색이 얼마나 다른가**뿐이다. 그래서 등록 시점의 첫 측정이 있어야
이후 측정이 의미를 갖는다. 기준값이 없으면 비교 대상이 없어 risk_score의
광학 항(w4)이 통째로 빠진다.

── 왜 white_ref로 나누는가 ─────────────────────────────────────────
AS7341이 주는 채널값은 그 순간의 조명 밝기에 그대로 비례한다. 같은 제품을
밝은 데서 재면 값이 전부 커진다. 흰 기준판을 함께 재서 그것으로 나누면
조명이 달라져도 비교할 수 있는 값(반사율)이 된다.

── 판정하지 않는다 ─────────────────────────────────────────────────
여기서 나오는 것은 변화율(%)뿐이다. 몇 %부터 문제인지는 정하지 않는다.
그 판단은 risk_score가 다른 근거와 함께 종합해서 하고, 화면은 "확인해
보시겠어요"까지만 말한다.
"""
from __future__ import annotations

import logging

from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# 가시광 채널만 쓴다. NIR·CLEAR는 제형보다 조명·거리에 더 크게 흔들린다.
VISIBLE = ("F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8")

# 노드가 함께 보내는 진단용 채널. 비교에는 쓰지 않지만 저장은 한다.
# CLEAR는 전체 밝기라 차광·거리가 흔들렸는지 사후에 보는 데 쓰이고,
# NIR은 가시광 밖이라 조명이 바뀐 것인지 시료가 바뀐 것인지 가른다.
DIAGNOSTIC = ("CLEAR", "NIR")

# 광학 측정이 의미 있는 제형인지. product_thermal_profile.optical_grade와 같은 값.
GRADE_GUIDE = {
    "suitable": (True, "색이 있는 제형이라 변화를 재기 좋습니다."),
    "conditional": (True, "반투명 제형이라 변화가 작게 나올 수 있습니다."),
    "unsuitable": (False, "투명한 제형이라 색으로는 변화를 재기 어렵습니다."),
}


def should_measure(optical_grade: Optional[str]) -> tuple[bool, str]:
    """
    이 제품을 색으로 재는 것이 의미 있는지와, 그 이유 한 줄.

    등록 화면이 이 값을 보고 안내한다. 투명 토너까지 "재세요"라고 하면
    쓸모없는 측정을 시키고, 나중에 그 숫자를 근거처럼 보여주게 된다.
    """
    return GRADE_GUIDE.get(
        (optical_grade or "").lower(),
        (False, "제품 정보가 없어 색 측정 여부를 판단할 수 없습니다."),
    )


def reflectance(
    channels: Dict[str, Any],
    white_ref: Optional[Dict[str, Any]],
) -> Dict[str, float]:
    """채널값을 흰 기준판으로 나눠 조명 영향을 없앤다."""
    out: Dict[str, float] = {}
    for k in VISIBLE:
        try:
            v = float(channels[k])
        except (KeyError, TypeError, ValueError):
            continue

        w = None
        if white_ref is not None:
            try:
                w = float(white_ref[k])
            except (KeyError, TypeError, ValueError):
                w = None

        # 기준판이 없으면 원값을 쓴다. 같은 조건에서 잰 것끼리만 비교되므로
        # 아주 틀리지는 않지만, 조명이 바뀌면 값이 흔들린다.
        out[k] = v / w if (w and w > 0) else v
    return out


def delta_pct(
    base_channels: Dict[str, Any],
    base_white: Optional[Dict[str, Any]],
    now_channels: Dict[str, Any],
    now_white: Optional[Dict[str, Any]],
) -> Optional[float]:
    """
    기준값 대비 색 변화율(%). 비교할 채널이 없으면 None.

    채널별 반사율의 상대 변화를 평균한다. 평균을 쓰는 이유는, 한 채널만
    튀는 것은 측정 흔들림일 때가 많고 진짜 변색은 여러 채널에 함께
    나타나기 때문이다.
    """
    base = reflectance(base_channels, base_white)
    now = reflectance(now_channels, now_white)

    diffs: List[float] = []
    for k in VISIBLE:
        b, n = base.get(k), now.get(k)
        if b is None or n is None or b <= 0:
            continue
        diffs.append(abs(n - b) / b * 100.0)

    if not diffs:
        return None
    return round(sum(diffs) / len(diffs), 2)


def missing_channels(channels: Optional[Dict[str, Any]]) -> List[str]:
    """
    비교에 필요한데 빠졌거나 숫자가 아닌 채널.

    delta_pct는 채널이 하나만 살아 있어도 값을 내기 때문에, 여덟 개 중
    두세 개만 도착해도 그럴듯한 숫자가 나온다. 전송이 깨진 것을 변화로
    읽지 않도록 받는 쪽에서 먼저 막는다.
    """
    out: List[str] = []
    for k in VISIBLE:
        try:
            float((channels or {})[k])
        except (KeyError, TypeError, ValueError):
            out.append(k)
    return out
