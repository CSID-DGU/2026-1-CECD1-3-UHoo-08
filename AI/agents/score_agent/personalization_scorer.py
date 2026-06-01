"""personalization: userProfile vs feature_json 매칭률."""
from typing import Any, Dict, List, Optional


def _norm_color(value: Optional[str]) -> Optional[str]:
    """SPRING_WARM/AUTUMN_MUTE → 웜톤, SUMMER_COOL/WINTER_COOL → 쿨톤, UNKNOWN → 뉴트럴."""
    if not value:
        return None
    v = value.upper()
    if "WARM" in v or "AUTUMN" in v:
        return "웜톤"
    if "COOL" in v:
        return "쿨톤"
    return "뉴트럴"


def _norm_skin_type(value: Optional[str]) -> Optional[str]:
    """OILY→지성, DRY→건성, NORMAL→중성, COMBINATION→복합, DEHYDRATED_OILY→복합, SENSITIVE→민감."""
    if not value:
        return None
    mapping = {
        "OILY": "지성",
        "DRY": "건성",
        "NORMAL": "중성",
        "COMBINATION": "복합",
        "DEHYDRATED_OILY": "복합",
        "SENSITIVE": "민감",
    }
    return mapping.get(value.upper())


def _norm_concerns(values: List[str]) -> List[str]:
    """피부고민 영문 → 한글 매핑."""
    mapping = {
        "SENSITIVITY": "민감",
        "ACNE": "트러블",
        "ATOPY": "진정",
        "WHITENING": "미백",
        "SEBUM": "모공",
        "DARK_CIRCLE": "다크서클",
    }
    return [mapping.get(v.upper(), v) for v in values]


def compute(
    user_profile: Dict[str, Any],
    feature_json: Optional[Dict[str, Any]],
) -> int:
    """
    feature_json의 personal_color, skin_type, skin_concern과
    userProfile 비교해서 매칭 횟수를 0~100점 매핑.

    feature_json 없으면 50점 중립.
    """
    if not feature_json:
        return 50

    checks: List[bool] = []

    # personal_color
    user_color = _norm_color(user_profile.get("personal_color"))
    feat_color = feature_json.get("personal_color")
    if user_color and feat_color:
        checks.append(user_color == feat_color or feat_color == "뉴트럴")

    # skin_type
    user_skin = _norm_skin_type(user_profile.get("skin_type"))
    feat_skin = feature_json.get("skin_type")
    if user_skin and feat_skin:
        checks.append(user_skin == feat_skin)

    # skin_concern (교집합 있으면 매칭)
    user_concerns = set(_norm_concerns(user_profile.get("skin_concerns") or []))
    feat_concerns = set(feature_json.get("skin_concern") or [])
    if user_concerns and feat_concerns:
        checks.append(bool(user_concerns & feat_concerns))

    if not checks:
        return 50

    hits = sum(1 for c in checks if c)
    return round(hits / len(checks) * 100)