"""
점검 우선순위 목록 조립.

risk_score.py는 순수 계산 모듈이다. 측정값 배열을 주면 점수를 돌려줄 뿐,
그 배열을 어디서 가져오는지는 모른다. 이 모듈이 그 사이를 잇는다.

    보유 제품 조회 → 노드별 측정 이력 조회 → 개봉일 이후로 절단
    → 제품별 점수 계산 → 정렬 → 요약

── 측정 이력은 노드당 한 번만 읽는다 ──────────────────────────────
제품 다섯 개가 전부 화장대 서랍(storage-01)에 있으면, 제품마다 조회하면
같은 데이터를 다섯 번 읽는다. 3개월치면 13,000행이므로 페이지네이션까지
다섯 배가 된다.

그래서 노드별로 묶고, 그 노드에 속한 제품 중 가장 이른 개봉일부터
한 번만 읽은 뒤, 제품별로는 메모리에서 잘라 쓴다. 절단은 이진 탐색이라
행 수가 늘어도 비용이 늘지 않는다.

── 점수를 못 내는 제품을 목록에서 지우지 않는다 ────────────────────
개봉일이 없거나, 보관 위치가 지정되지 않았거나, 열민감도 프로파일이
없으면 점수를 낼 수 없다. 이런 제품을 조용히 빼면 사용자는 "내 세럼이
왜 목록에 없지"를 알 수 없고, 우리도 데이터 누락을 눈치채지 못한다.

따라서 skipped로 분리해 무엇이 비어 있는지와 무엇을 하면 되는지를
함께 돌려준다. 키오스크는 이것을 "정보를 추가하면 점검할 수 있어요"로
표시한다. 경고가 아니라 안내다.

── 이 점수는 판정이 아니다 ────────────────────────────────────────
어떤 제품부터 눈으로 확인할지 순서를 정하는 값이다. 변질 여부는
미생물·pH 시험 없이 알 수 없고, 이 모듈은 그런 주장을 하지 않는다.
"""
from __future__ import annotations

import logging

from bisect import bisect_left
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from db.iot.event_reader import get_latest_feedback
from db.iot.reader import get_care_products, get_latest_optical, get_readings
from services.iot.risk_score import (
    BAND_HIGH, BAND_MEDIUM, compute_risk_score,
)
# 날짜 정규화는 risk_score와 완전히 같은 규칙을 써야 한다. 절단 기준과
# 점수 계산 기준이 어긋나면 미세하게 다른 구간을 보게 된다.
from services.iot.risk_score import _as_utc as to_utc

logger = logging.getLogger(__name__)

# 민감도 계수 → 사람이 읽는 문구. 목업 탭1의 "고민감 성분(k 1.5)" 표기.
_K_LABEL = (
    (1.45, "고민감 성분"),
    (1.15, "중민감 성분"),
    (0.85, "일반 성분"),
    (0.0, "저민감 성분"),
)


def _k_label(k: Optional[float]) -> Optional[str]:
    if k is None:
        return None
    for threshold, label in _K_LABEL:
        if k >= threshold:
            return f"{label}(k {k:g})"
    return None


# ── 점수를 낼 수 없는 이유 ───────────────────────────────────────
# (필드, 사용자에게 보일 문구, 무엇을 하면 되는지)
_REQUIRED = (
    ("opened_at", "개봉일 미등록", "앱에서 개봉일을 입력하면 점검 순서에 포함됩니다"),
    ("storage_node_id", "보관 위치 미지정", "제품을 어느 보관함에 두었는지 지정해 주세요"),
    ("has_profile", "제품 정보 미등록", "제품의 성분 민감도 정보가 아직 없습니다"),
    ("pao_months", "사용기간 미등록", "개봉 후 사용기간(PAO)이 등록되어 있지 않습니다"),
)


def _missing_reasons(item: Dict[str, Any]) -> List[Dict[str, str]]:
    """
    점수 계산에 필요한 값 중 빠진 것을 찾는다.

    pao_months를 필수로 두는 이유: 없어도 risk_score는 소모 항을 빼고
    점수를 내지만, 그러면 이 시스템의 핵심 근거(열이력 소모 비율)가
    빠진 채로 순위에 섞인다. 반쪽 점수를 정상 점수처럼 보여주느니
    "정보가 필요하다"고 말하는 편이 정직하다.
    """
    out = []
    for field, title, action in _REQUIRED:
        v = item.get(field)
        if field == "has_profile":
            ok = bool(v)
        elif field == "pao_months":
            ok = v is not None and float(v) > 0
        else:
            ok = v not in (None, "")
        if not ok:
            out.append({"field": field, "title": title, "action": action})
    return out


# user_feedback.answer 코드 → 화면 표기.
# DB CHECK 제약이 다섯 값만 허용해 화면 항목보다 거칠다.
FEEDBACK_LABEL = {
    "color": "색 변화",
    "odor": "냄새 변화",
    "separation": "층 분리",
    "texture": "질감 변화",
}


def _finding_labels(answers: List[Optional[str]]) -> List[str]:
    """'none'만 있으면 이상 없음이므로 빈 목록."""
    out = []
    for a in answers:
        label = FEEDBACK_LABEL.get(a or "")
        if label and label not in out:
            out.append(label)
    return out


def _slice_since(
    rows: Sequence[Dict[str, Any]],
    ts_index: Sequence[datetime],
    since: Optional[datetime],
) -> List[Dict[str, Any]]:
    """정렬된 측정 배열에서 since 이후 구간만 잘라낸다 (이진 탐색)."""
    if since is None:
        return list(rows)
    i = bisect_left(ts_index, since)
    return list(rows[i:])


def _load_node_readings(
    scorable: Sequence[Dict[str, Any]],
) -> Dict[str, tuple]:
    """
    노드별로 측정 이력을 한 번씩만 읽는다.

    반환: {node_id: (rows, ts_index)}
    rows는 ts 오름차순이며 ts_index는 같은 순서의 datetime 리스트다.
    """
    by_node: Dict[str, List[Dict[str, Any]]] = {}
    for it in scorable:
        by_node.setdefault(it["storage_node_id"], []).append(it)

    cache: Dict[str, tuple] = {}
    for node_id, items in by_node.items():
        opens = [to_utc(i.get("opened_at")) for i in items]
        opens = [o for o in opens if o is not None]
        since = min(opens) if opens else None

        rows = get_readings(node_id, since=since)
        ts_index = []
        clean = []
        for r in rows:
            ts = to_utc(r.get("ts"))
            if ts is None:
                continue
            r = dict(r)
            r["ts"] = ts
            clean.append(r)
            ts_index.append(ts)

        # get_readings가 ts 오름차순으로 주지만, 페이지 경계에서 순서가
        # 어긋나면 이진 탐색이 조용히 틀린 구간을 잘라낸다. 확인 비용이
        # 싸므로 검사하고, 어긋나면 정렬한다.
        if any(ts_index[i] > ts_index[i + 1] for i in range(len(ts_index) - 1)):
            logger.warning("node=%s 측정값이 정렬되어 있지 않아 재정렬한다", node_id)
            clean.sort(key=lambda r: r["ts"])
            ts_index = [r["ts"] for r in clean]

        cache[node_id] = (clean, ts_index)
        logger.info("node=%s readings=%d since=%s", node_id, len(clean), since)

    return cache


def build_priority(
    user_id: str,
    *,
    limit: Optional[int] = None,
    now: Optional[datetime] = None,
    include_components: bool = False,
) -> Dict[str, Any]:
    """
    사용자의 점검 우선순위 목록을 만든다.

    limit은 **표시 개수만** 자른다. 요약 수치(확인 필요 n개 등)는 항상
    전체 기준이다. 상위 3개만 보여주면서 "확인 필요 2개"라고 쓰려면
    분모가 전체여야 하기 때문이다.
    """
    now = now or datetime.now(timezone.utc)
    products = get_care_products(user_id)

    scorable: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []

    for it in products:
        missing = _missing_reasons(it)
        if missing:
            skipped.append({
                "user_product_id": it["user_product_id"],
                "product_id": it["product_id"],
                "name": it.get("name"),
                "brand": it.get("brand"),
                "category": it.get("category"),
                "missing": missing,
            })
        else:
            scorable.append(it)

    cache = _load_node_readings(scorable)

    # 사용자가 직접 확인한 결과. 점수와 별개로 목록에 표시한다.
    #
    # 점수는 "확인해 볼 순서"이고, 이 값은 "사람이 실제로 본 것"이다.
    # 후자가 더 강한 정보라 화면에서 눈에 띄게 보여야 한다. 점수가 낮아도
    # 냄새가 난다고 확인했다면 그 사실이 먼저다.
    try:
        feedback = get_latest_feedback([it["user_product_id"] for it in scorable])
    except Exception:
        logger.exception("확인 결과 조회 실패 user_id=%s", user_id)
        feedback = {}

    items: List[Dict[str, Any]] = []
    for it in scorable:
        rows, ts_index = cache.get(it["storage_node_id"], ([], []))
        opened = to_utc(it.get("opened_at"))
        sliced = _slice_since(rows, ts_index, opened)

        # 광학 측정은 제품당 1건씩 조회한다. unsuitable(투명 토너 등)은
        # 가중치가 0이라 결과에 영향이 없으므로 조회 자체를 건너뛴다.
        optical = None
        if (it.get("optical_grade") or "").lower() != "unsuitable":
            optical = get_latest_optical(it["user_product_id"])

        fb = feedback.get(it["user_product_id"])
        findings = _finding_labels(fb["answers"]) if fb else []

        rs = compute_risk_score(
            sliced,
            sensitivity=it.get("sensitivity_k"),
            pao_months=it.get("pao_months"),
            opened_at=it.get("opened_at"),
            last_checked_at=it.get("last_checked_at"),
            # 이상이 발견된 확인은 점수를 낮추지 않는다.
            last_check_clear=not findings,
            optical_delta_pct=(optical or {}).get("delta_pct"),
            optical_grade=it.get("optical_grade"),
            now=now,
        )

        reasons = list(rs.reasons)
        label = _k_label(it.get("sensitivity_k"))
        if label:
            reasons.append(label)

        detail = {
            "sensitivity_k": it.get("sensitivity_k"),
            "pao_months": it.get("pao_months"),
            "optical_grade": it.get("optical_grade"),
            "optical_delta_pct": rs.optical_delta_pct,
            "consumed_ratio": (round(rs.consumed_ratio, 4)
                               if rs.consumed_ratio is not None else None),
            "measured_hours": round(rs.measured_hours, 1),
            "assumed_hours": round(rs.assumed_hours, 1),
            "gap_hours": round(rs.load.history.gap_hours, 1),
            "sample_n": rs.load.history.sample_n,
            "acceleration": (round(rs.load.history.acceleration, 3)
                             if rs.load.history.sample_n else None),
            "mean_temp_c": rs.load.history.mean_temp_c,
            "max_temp_c": rs.excursions.max_temp_c,
            "excursion_events": rs.excursions.total_events,
            # 실측 구간이 짧으면 이탈 통계를 점수에 반영하지 않는다.
            # 화면에서 "아직 판단할 만큼 측정되지 않음"으로 구분해야 한다.
            "excursion_counted": rs.excursion_counted,
            "hours_above_temp": round(rs.excursions.hours_above_temp, 1),
            "hours_above_humid": round(rs.excursions.hours_above_humid, 1),
            "days_since_last_check": (round(rs.days_since_last_check, 1)
                                      if rs.days_since_last_check is not None else None),
        }
        if include_components:
            detail["components"] = rs.components

        items.append({
            "inspection": ({
                "ts": fb["ts"],
                "findings": findings,
                # 이상 항목이 하나도 없으면 "이상 없음"으로 확인한 것이다.
                "clear": not findings,
            } if fb else None),
            "user_product_id": it["user_product_id"],
            "product_id": it["product_id"],
            "name": it.get("name"),
            "brand": it.get("brand"),
            "category": it.get("category"),
            "storage_node_id": it["storage_node_id"],
            "opened_at": it.get("opened_at"),
            "last_checked_at": it.get("last_checked_at"),
            "score": rs.score,
            "band": rs.band,
            "reasons": reasons,
            "detail": detail,
        })

    items.sort(key=lambda x: x["score"], reverse=True)

    # ── 요약은 전체 기준 ─────────────────────────────────────────
    bands = {"high": 0, "medium": 0, "low": 0}
    # 확인을 마친 고위험 제품. "확인 필요"에서 빼기 위해 따로 센다.
    checked_high = 0
    for i in items:
        bands[i["band"]] = bands.get(i["band"], 0) + 1
        if i["band"] == "high" and i.get("inspection"):
            checked_high += 1

    summary = {
        "total": len(products),
        "scored": len(items),
        "unscored": len(skipped),
        "high": bands["high"],
        "medium": bands["medium"],
        "low": bands["low"],
        # 키오스크 문구용. "보유 12개 중 확인 필요 2개"
        #
        # 밴드가 아니라 "아직 확인하지 않은 고위험 제품" 수다. 사용자가 직접
        # 확인한 제품은 결과가 어떻든 이 수에서 빠진다. 확인하러 가라는 안내인데
        # 이미 확인한 제품이 계속 남아 있으면 숫자가 줄지 않는다.
        #
        # 이상이 발견된 제품은 점수를 낮추지 않으므로 목록 위쪽에 그대로 남고,
        # 카드 안에서 "주의가 필요합니다"로 따로 알린다. 확인 여부와 위험도는
        # 별개라는 원칙을 여기서도 지킨다.
        "needs_check": bands["high"] - checked_high,
        # 그중 확인을 마친 것. 화면이 "19개 중 4개 확인함"처럼 쓸 수 있다.
        "checked_high": checked_high,
        "band_thresholds": {"high": BAND_HIGH, "medium": BAND_MEDIUM},
    }

    nodes_used = [
        {
            "node_id": nid,
            "readings": len(rows),
            "first_ts": ts_index[0].isoformat() if ts_index else None,
            "last_ts": ts_index[-1].isoformat() if ts_index else None,
        }
        for nid, (rows, ts_index) in cache.items()
    ]

    shown = items[:limit] if limit else items

    return {
        "user_id": user_id,
        "generated_at": now.isoformat(),
        "summary": summary,
        "items": shown,
        "skipped": skipped,
        "nodes_used": nodes_used,
    }


if __name__ == "__main__":
    import sys

    uid = sys.argv[1] if len(sys.argv) > 1 else "e3985354-0a60-4330-b7cb-b83b674c0eb0"
    res = build_priority(uid, include_components=True)
    s = res["summary"]

    print(f"사용자 {uid}")
    print(f"보유 {s['total']}개 · 점수 산출 {s['scored']}개 · 정보 부족 {s['unscored']}개")
    print(f"🔴 {s['high']}  🟡 {s['medium']}  🟢 {s['low']}")

    print("\n── 점검 우선순위 ──")
    for i, it in enumerate(res["items"], 1):
        mark = {"high": "🔴", "medium": "🟡", "low": "🟢"}[it["band"]]
        print(f"  {i}. {mark} {it['score']:>5.1f}  {it['brand'] or ''} {it['name']}")
        print(f"       {' · '.join(it['reasons'])}")
        d = it["detail"]
        print(f"       실측 {d['measured_hours']:.0f}h / 가정 {d['assumed_hours']:.0f}h"
              f" · 이탈 {d['excursion_events']}회 · 결측 {d['gap_hours']:.0f}h")

    if res["skipped"]:
        print("\n── 정보가 더 필요한 제품 ──")
        for it in res["skipped"]:
            titles = ", ".join(m["title"] for m in it["missing"])
            print(f"  · {it['brand'] or ''} {it['name']} — {titles}")

    print("\n── 사용한 노드 ──")
    for n in res["nodes_used"]:
        print(f"  {n['node_id']}  {n['readings']}건  {n['first_ts']} ~ {n['last_ts']}")