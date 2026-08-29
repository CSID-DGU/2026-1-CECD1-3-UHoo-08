"""
환경 기반 제품 추천 규칙.

── 왜 기존 추천 파이프라인을 쓰지 않는가 ───────────────────────────
모바일 앱의 추천은 사용자의 피부 타입·고민·리뷰 임베딩을 종합한다.
좋은 추천이지만 키오스크에서 하려는 것과 다르다. 여기서는

    "지금 이 공간이 이런 상태라서 이 제품을 권한다"

를 보여준다. 근거가 센서 값이어야 하고, 그 값이 화면에 그대로 나와야
한다. 임베딩 유사도는 그런 문장을 만들 수 없다.

── 이유 없는 추천은 광고와 구분되지 않는다 ─────────────────────────
카드마다 "실내 절대습도 6.2 g/m³ — 건조 기준 이하" 같은 한 줄을 붙인다.
이 한 줄이 없으면 그냥 제품 목록이 된다.

── 재고가 없으면 억지로 채우지 않는다 ──────────────────────────────
조건에 맞는 제품을 DB에서 못 찾으면 그 자리를 비운다. 아무거나 넣으면
이유와 제품이 어긋나고, 그게 더 나쁘다.
"""
from __future__ import annotations

import logging

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from db.product_reader import search_products_by_name
from services.iot.humidity import absolute_humidity

logger = logging.getLogger(__name__)

# care_rules.py와 같은 기준값을 쓴다.
UV_MODERATE = 6
PM25_NORMAL = 15
DRY_GM3 = 7.0
TEMP_WATCH_C = 25


@dataclass
class Candidate:
    """조건 하나와, 그 조건에 맞는 제품을 찾을 검색어."""
    key: str
    keywords: List[str]
    reason: str
    order: int


def _f(v: Any) -> Optional[float]:
    try:
        return None if v is None else float(v)
    except (TypeError, ValueError):
        return None


# 제형·마무리를 사람 말로 옮긴다. DB 값이 "글로우"라고만 되어 있으면
# 그게 촉촉하다는 뜻인지 사용자는 모른다.
_FINISH_WORD = {
    "매트": "매트하게 마무리되는",
    "세미매트": "세미매트로 마무리되는",
    "글로우": "촉촉하게 마무리되는",
    "촉촉": "촉촉하게 마무리되는",
    "내추럴": "자연스럽게 마무리되는",
}
_TEXTURE_WORD = {
    "가벼운": "가볍게 발리는",
    "중간": "무겁지 않은",
    "진한": "진하고 촘촘한",
}


@dataclass
class NodeHistory:
    """노드 한 곳의 누적 환경. 하루치가 아니라 쌓인 기간 전체를 본다."""
    days: int
    samples: int
    mean_temp: Optional[float]
    max_temp: Optional[float]
    hot_ratio: float          # TEMP_WATCH_C를 넘긴 측정 비율
    mean_ah: Optional[float]  # 평균 절대습도
    dry_ratio: float          # DRY_GM3 아래였던 비율
    mean_pm25: Optional[float]


def summarize_history(readings: List[Dict[str, Any]]) -> Optional[NodeHistory]:
    """
    측정 이력을 한 덩어리로 요약한다.

    화장품은 하루 쓰려고 사는 물건이 아니다. 지금 이 순간의 온도가 아니라
    이 자리에 몇 주 두었을 때 어떤 환경이었는지가 추천의 근거여야 한다.
    """
    temps: List[float] = []
    ahs: List[float] = []
    pms: List[float] = []
    hot = dry = 0

    for r in readings:
        t = _f(r.get("temperature"))
        h = _f(r.get("humidity"))
        pm = _f(r.get("pm25"))

        if t is not None:
            temps.append(t)
            if t > TEMP_WATCH_C:
                hot += 1
        if pm is not None:
            pms.append(pm)

        ah = absolute_humidity(t, h)
        if ah is not None:
            ahs.append(ah)
            if ah < DRY_GM3:
                dry += 1

    if not temps and not ahs:
        return None

    # 10분 간격 수집을 전제로 대략의 일수를 낸다. 정확한 날짜 차이보다
    # 화면에 "며칠치인가"를 알려주는 것이 목적이다.
    days = max(1, round(len(readings) * 10 / 60 / 24))

    return NodeHistory(
        days=days,
        samples=len(readings),
        mean_temp=(sum(temps) / len(temps)) if temps else None,
        max_temp=max(temps) if temps else None,
        hot_ratio=(hot / len(temps)) if temps else 0.0,
        mean_ah=(sum(ahs) / len(ahs)) if ahs else None,
        dry_ratio=(dry / len(ahs)) if ahs else 0.0,
        mean_pm25=(sum(pms) / len(pms)) if pms else None,
    )


def build_node_candidates(hist: NodeHistory, label: str) -> List[Candidate]:
    """
    누적 환경에서 추천 조건을 뽑는다.

    build_candidates가 "지금"을 본다면 이쪽은 "그동안"을 본다. 보관 장소를
    고정해 두고 쓰는 제품이라 이 기준이 맞다.
    """
    out: List[Candidate] = []
    span = f"{hist.days}일"

    if hist.hot_ratio >= 0.15 and hist.max_temp is not None:
        pct = round(hist.hot_ratio * 100)
        out.append(Candidate(
            "hot-history",
            ["수분", "젤", "가벼운"],
            f"{label} 최근 {span} 중 {pct}%가 {TEMP_WATCH_C:.0f}℃를 넘었습니다 "
            f"(최고 {hist.max_temp:.1f}℃) — 열에 덜 예민한 가벼운 제형",
            10,
        ))

    if hist.dry_ratio >= 0.3 and hist.mean_ah is not None:
        pct = round(hist.dry_ratio * 100)
        out.append(Candidate(
            "dry-history",
            ["수분크림", "보습", "밤"],
            f"{label} 최근 {span} 중 {pct}%가 건조 기준 아래였습니다 "
            f"(평균 {hist.mean_ah:.1f} g/m³) — 보습 위주",
            20,
        ))

    if hist.mean_pm25 is not None and hist.mean_pm25 > PM25_NORMAL:
        out.append(Candidate(
            "pm-history",
            ["클렌징", "폼", "클렌저"],
            f"{label} 최근 {span} 평균 초미세먼지 {hist.mean_pm25:.0f} ㎍/m³ — 세정 강화",
            30,
        ))

    if not out:
        # "오늘 이슈 없음"이라고 쓰지 않는다. 하루가 아니라 그동안 어땠는지를
        # 숫자로 말해 주는 편이 추천의 근거로 읽힌다.
        bits = []
        if hist.mean_temp is not None:
            bits.append(f"평균 {hist.mean_temp:.1f}℃")
        if hist.mean_ah is not None:
            bits.append(f"절대습도 {hist.mean_ah:.1f} g/m³")
        out.append(Candidate(
            "stable-history",
            ["수분", "보습", "토너"],
            f"{label} 최근 {span} {' · '.join(bits)}로 안정적이었습니다 — 꾸준히 쓰기 좋은 제품",
            90,
        ))

    out.sort(key=lambda c: c.order)
    return out


def product_blurb(feat: Optional[Dict[str, Any]]) -> Optional[str]:
    """
    이 제품이 어떤 제품인지 한 줄.

    "같은 용도 제품입니다"는 고를 근거가 못 된다. 촉촉한지 매트한지, 어떤
    피부에 맞춘 것인지를 말해야 사용자가 판단할 수 있다.

    feature_json에 있는 값만 쓴다. 없는 항목은 조용히 건너뛴다.
    """
    f = feat or {}
    ptype = (f.get("product_type") or "").strip()

    head = _FINISH_WORD.get((f.get("finish") or "").strip()) \
        or _TEXTURE_WORD.get((f.get("texture") or "").strip())

    lead = f"{head} {ptype}".strip() if (head and ptype) else (ptype or head)
    if not lead:
        return None

    tail: List[str] = []
    skin = (f.get("skin_type") or "").strip()
    if skin:
        tail.append(f"{skin} 피부용")

    concerns = [c for c in (f.get("skin_concern") or []) if c]
    if concerns:
        tail.append(" · ".join(concerns[:2]))

    spf = (f.get("spf") or "").strip()
    if spf and not tail:
        tail.append(spf)

    return f"{lead} · {' · '.join(tail)}" if tail else lead


def build_candidates(
    outdoor: Optional[Dict[str, Any]],
    indoor: List[Dict[str, Any]],
) -> List[Candidate]:
    """환경에서 추천 후보 조건을 뽑는다. 우선순위 순으로 정렬해 돌려준다."""
    out: List[Candidate] = []

    uv = _f((outdoor or {}).get("uv_index"))
    if uv is not None and uv >= UV_MODERATE:
        out.append(Candidate(
            "uv",
            ["선크림", "자외선차단", "선스틱"],
            f"외출 지역 자외선 지수 {uv:.0f} — 차단 권장",
            10,
        ))

    o_pm = _f((outdoor or {}).get("pm25"))
    if o_pm is not None and o_pm > PM25_NORMAL:
        out.append(Candidate(
            "pm",
            ["클렌징", "폼", "클렌저"],
            f"실외 PM2.5 {o_pm:.0f} ㎍/m³ — 세정 강화 권장",
            30,
        ))

    driest = None
    for n in indoor:
        ah = _f(n.get("absolute_humidity"))
        if ah is None:
            continue
        if driest is None or ah < driest[1]:
            driest = (n.get("label") or n.get("node_id"), ah)

    if driest and driest[1] < DRY_GM3:
        label, ah = driest
        out.append(Candidate(
            "dry",
            ["수분", "히알루론", "세라마이드", "크림"],
            f"{label} 절대습도 {ah:.1f} g/m³ — 건조 기준 이하",
            5,
        ))

    hottest = None
    for n in indoor:
        t = _f(n.get("temperature"))
        if t is None:
            continue
        if hottest is None or t > hottest[1]:
            hottest = (n.get("label") or n.get("node_id"), t)

    if hottest and hottest[1] > TEMP_WATCH_C:
        label, t = hottest
        out.append(Candidate(
            "hot",
            ["진정", "시카", "쿨링", "토너"],
            f"{label} {t:.1f}℃ — 진정 케어 권장",
            40,
        ))

    # 아무 조건도 안 걸리면 기본 케어를 하나 둔다. 빈 화면보다는 낫고,
    # 이유도 "특별한 이슈가 없다"로 정직하게 적는다.
    if not out:
        out.append(Candidate(
            "base",
            ["수분", "토너"],
            "오늘 환경에 특별한 이슈가 없습니다 — 기본 케어",
            90,
        ))

    out.sort(key=lambda c: c.order)
    return out


def pick_products(
    candidates: List[Candidate],
    *,
    limit: int = 3,
    exclude_ids: Optional[set] = None,
) -> List[Dict[str, Any]]:
    """
    후보 조건마다 제품을 하나씩 찾는다.

    같은 제품이 여러 조건에 걸릴 수 있으므로 이미 고른 것은 건너뛴다.
    조건 하나당 하나씩만 고르는 이유는, 세 칸이 전부 수분 크림이면
    "환경을 반영했다"는 말이 무색해지기 때문이다.
    """
    seen = set(exclude_ids or ())
    out: List[Dict[str, Any]] = []

    for cand in candidates:
        if len(out) >= limit:
            break

        found = None
        for kw in cand.keywords:
            try:
                metas = search_products_by_name(kw, limit=10)
            except Exception:
                logger.exception("제품 검색 실패 keyword=%s", kw)
                continue

            for m in metas:
                if m["id"] in seen:
                    continue
                found = m
                break
            if found:
                break

        if not found:
            # 조건에 맞는 제품이 DB에 없다. 억지로 다른 것을 넣지 않는다.
            logger.info("추천 후보 %s에 맞는 제품 없음 (검색어 %s)",
                        cand.key, ", ".join(cand.keywords))
            continue

        seen.add(found["id"])
        out.append({
            "product_id": found["id"],
            "name": found["name"],
            "brand": found.get("brand"),
            "image_url": found.get("image_url"),
            # 앱 목록이 가격을 함께 보여준다.
            "price": found.get("price"),
            "reason": cand.reason,
        })

    return out


def context_line(
    outdoor: Optional[Dict[str, Any]],
    indoor: List[Dict[str, Any]],
) -> Optional[str]:
    """상단에 띄울 환경 한 줄. "침실 24.1℃ / 47% · 외출 자외선 7" """
    parts: List[str] = []

    lead = next((n for n in indoor if n.get("temperature") is not None), None)
    if lead:
        label = lead.get("label") or lead.get("node_id")
        t = _f(lead.get("temperature"))
        rh = _f(lead.get("humidity"))
        if t is not None:
            parts.append(f"{label} {t:.1f}℃" + (f" / {rh:.0f}%" if rh is not None else ""))

    uv = _f((outdoor or {}).get("uv_index"))
    if uv is not None:
        parts.append(f"외출 자외선 {uv:.0f}")

    return " · ".join(parts) if parts else None