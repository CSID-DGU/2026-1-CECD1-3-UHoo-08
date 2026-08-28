"""
환경 → 케어 안내 규칙 테이블.

── 문장은 단정하지 않는다 ──────────────────────────────────────────
"자외선이 강합니다"는 측정값이므로 말할 수 있다. "이 제품을 쓰세요"는
권유이므로 조심스럽게 쓴다. 어느 쪽이든 "변질됐다" 같은 판정은 하지 않는다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# ── 기준값 ───────────────────────────────────────────────────────
# 화면(auraState.ts)과 같은 값을 쓴다. 한쪽만 고치면 색과 문장이 어긋난다.
UV_HIGH = 8          # 세계보건기구 "매우 높음"
UV_MODERATE = 6
PM25_BAD = 35        # 환경부 나쁨
PM25_NORMAL = 15
DRY_GM3 = 7.0        # humidity.py와 같은 값
OUTDOOR_DRY_RH = 40
TEMP_WATCH_C = 25
TEMP_CHECK_C = 30


@dataclass
class Rule:
    """조건 하나와 그때 보여줄 문장."""
    key: str
    line: str
    # 우선순위. 작을수록 먼저 보인다. 화면에 두세 줄만 들어가므로
    # 무엇을 먼저 말할지 정해두어야 한다.
    order: int = 50


@dataclass
class Brief:
    headline: str
    lines: List[str] = field(default_factory=list)
    rules: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {"headline": self.headline, "lines": self.lines, "rules": self.rules}


def _josa(word: str, with_final: str, without_final: str) -> str:
    """
    한국어 조사 선택.

    "사무실이(가)"처럼 두 개를 병기하면 화면에서 읽기 나쁘다. 마지막 글자에
    받침이 있는지 보고 하나만 고른다. 한글 음절은 유니코드에서 초성·중성·종성
    순서로 배열되어 있어, 시작점에서의 거리를 28로 나눈 나머지가 종성 번호다.
    """
    if not word:
        return without_final
    ch = word[-1]
    if not ("가" <= ch <= "힣"):
        # 영문·숫자로 끝나면 판단할 수 없다. 받침 없는 쪽이 덜 어색하다.
        return without_final
    return with_final if (ord(ch) - 0xAC00) % 28 else without_final


def _f(v: Any) -> Optional[float]:
    try:
        return None if v is None else float(v)
    except (TypeError, ValueError):
        return None


def build_brief(
    outdoor: Optional[Dict[str, Any]],
    indoor: List[Dict[str, Any]],
    *,
    max_lines: int = 2,
) -> Brief:
    """
    실외·실내 값을 받아 안내 문장을 고른다.

    headline은 가장 우선순위가 높은 항목 하나를 요약하고, lines에는
    행동으로 이어지는 문장을 담는다. rules에는 걸린 조건을 사람이 읽는
    형태로 남긴다.
    """
    hits: List[Rule] = []
    rules: List[str] = []
    region = (outdoor or {}).get("region")

    # ── 실외 ─────────────────────────────────────────────────────
    uv = _f((outdoor or {}).get("uv_index"))
    if uv is not None:
        if uv >= UV_HIGH:
            hits.append(Rule("uv_high", "외출 전 자외선 차단제를 충분히 바르고, 2~3시간마다 덧바르는 것을 권장합니다.", 10))
            rules.append(f"자외선 지수 {uv:.0f} ≥ {UV_HIGH}")
        elif uv >= UV_MODERATE:
            hits.append(Rule("uv_mid", "외출 전 자외선 차단을 권장합니다.", 20))
            rules.append(f"자외선 지수 {uv:.0f} ≥ {UV_MODERATE}")

    o_pm25 = _f((outdoor or {}).get("pm25"))
    if o_pm25 is not None:
        if o_pm25 > PM25_BAD:
            hits.append(Rule("pm_bad", "귀가 후 이중 세안으로 미세먼지를 씻어내는 것을 권장합니다.", 15))
            rules.append(f"실외 PM2.5 {o_pm25:.0f} > {PM25_BAD}")
        elif o_pm25 > PM25_NORMAL:
            hits.append(Rule("pm_mid", "귀가 후 평소보다 꼼꼼히 세안하시면 좋습니다.", 35))
            rules.append(f"실외 PM2.5 {o_pm25:.0f} > {PM25_NORMAL}")

    o_rh = _f((outdoor or {}).get("humidity"))
    if o_rh is not None and o_rh < OUTDOOR_DRY_RH:
        hits.append(Rule("out_dry", "바깥 공기가 건조합니다. 수분 보충을 권장합니다.", 30))
        rules.append(f"실외 습도 {o_rh:.0f}% < {OUTDOOR_DRY_RH}%")

    # ── 실내 ─────────────────────────────────────────────────────
    driest = None
    for n in indoor:
        ah = _f(n.get("absolute_humidity"))
        if ah is None:
            continue
        if driest is None or ah < driest[1]:
            driest = (n.get("label") or n.get("node_id"), ah)

    if driest and driest[1] < DRY_GM3:
        label, ah = driest
        hits.append(Rule("in_dry",
                         f"{label}{_josa(label, '이', '가')} 건조합니다. "
                         "가습이나 수분 제품을 권장합니다.", 25))
        rules.append(f"{label} 절대습도 {ah:.1f} < {DRY_GM3} g/m³")

    hottest = None
    for n in indoor:
        t = _f(n.get("temperature"))
        if t is None:
            continue
        if hottest is None or t > hottest[1]:
            hottest = (n.get("label") or n.get("node_id"), t)

    if hottest and hottest[1] > TEMP_CHECK_C:
        label, t = hottest
        hits.append(Rule("in_hot", f"{label} 온도가 {t:.1f}℃입니다. 화장품을 서늘한 곳으로 옮기시면 좋습니다.", 5))
        rules.append(f"{label} {t:.1f}℃ > {TEMP_CHECK_C}℃")
    elif hottest and hottest[1] > TEMP_WATCH_C:
        label, t = hottest
        hits.append(Rule("in_warm", f"{label} 온도가 권장 범위보다 조금 높습니다.", 40))
        rules.append(f"{label} {t:.1f}℃ > {TEMP_WATCH_C}℃")

    # ── 조립 ─────────────────────────────────────────────────────
    if not hits:
        return Brief(
            headline="특별히 주의할 점은 없습니다.",
            lines=["오늘은 평소 쓰시던 대로 하시면 됩니다."],
            rules=[],
        )

    hits.sort(key=lambda r: r.order)

    # headline은 무엇이 걸렸는지를 한 줄로 요약한다. 문장을 붙여 쓰면
    # 길어져 화면에서 두 줄로 넘어간다.
    top_keys = {r.key for r in hits[:2]}
    headline = _headline(top_keys, region)

    return Brief(
        headline=headline,
        lines=[r.line for r in hits[:max_lines]],
        rules=rules,
    )


def _headline(keys: set, region: Optional[str]) -> str:
    """걸린 조건 조합에 맞는 한 줄. 여기도 규칙 테이블이다."""
    uv = keys & {"uv_high", "uv_mid"}
    dry = keys & {"in_dry", "out_dry"}
    pm = keys & {"pm_bad", "pm_mid"}
    hot = keys & {"in_hot", "in_warm"}

    if uv and dry:
        return "자외선이 강하고 건조합니다."
    if uv and pm:
        return "자외선이 강하고 미세먼지가 많습니다."
    if uv:
        return "자외선이 강합니다."
    if hot:
        return "보관 온도가 높습니다."
    if dry:
        return "공기가 건조합니다."
    if pm:
        return "미세먼지가 많습니다."
    return f"{region or '오늘'} 환경을 확인했습니다."


def compare_indoor(indoor: List[Dict[str, Any]]) -> Optional[str]:
    """
    실내 노드 두 곳 이상을 비교하는 한 줄.

    "침실 24.1℃ / 47% · 사무실 22.6℃ / 31% — 사무실이 더 건조합니다"

    프론트에서 조립하지 않고 서버가 만드는 이유는, 비교 기준(절대습도)이
    규칙 테이블의 일부이기 때문이다. 두 곳에 흩어지면 한쪽만 고치게 된다.
    """
    usable = [n for n in indoor if _f(n.get("absolute_humidity")) is not None]
    if len(usable) < 2:
        return None

    parts = []
    for n in usable[:3]:
        label = n.get("label") or n.get("node_id")
        t = _f(n.get("temperature"))
        rh = _f(n.get("humidity"))
        parts.append(f"{label} {t:.1f}℃ / {rh:.0f}%" if t is not None and rh is not None
                     else f"{label}")

    driest = min(usable, key=lambda n: _f(n.get("absolute_humidity")))
    label = driest.get("label") or driest.get("node_id")

    return " · ".join(parts) + f" — {label}{_josa(label, '이', '가')} 더 건조합니다"