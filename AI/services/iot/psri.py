"""
PSRI — 피부 환경 위험 지수 (Personal Skin Risk Index).

── 무엇을 재는가 ───────────────────────────────────────────────────
피부 상태가 아니라 피부에 작용한 환경을 잰다. 사람을 측정하지 않고
그 사람이 머문 공간의 지난 24시간을 적분한다.

  건조 항  절대습도가 기준(7 g/m³)보다 얼마나 부족했는가
  자극 항  초미세먼지가 기준(15 ㎍/m³)보다 얼마나 많았는가

두 항을 가중 합해 0~100으로 만든다. 점수가 높다는 것은 "환경이 피부에
부담이 되는 쪽이었다"는 뜻이지, 피부가 나빠졌다는 뜻이 아니다. 후자는
피부를 직접 재야 알 수 있고, 그것은 skin_measurements가 담당한다.

── 왜 상대습도가 아니라 절대습도인가 ───────────────────────────────
같은 50%RH라도 30℃ 공기는 15.2 g/m³, 15℃ 공기는 6.4 g/m³를 담는다.
피부에서 수분이 빠져나가는 속도는 공기가 실제로 머금은 물의 양에
좌우되므로 절대습도로 봐야 한다. 겨울 실내가 왜 건조한지도 이것으로
설명된다.

── 평균이 아니라 적분인 이유 ───────────────────────────────────────
잠깐 건조했다가 회복한 것과 하루 종일 건조했던 것은 다르다. 표본마다
부족량을 계산해 평균을 내면 지속 시간이 자연스럽게 반영된다.
"""
from __future__ import annotations

import logging

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence

from services.iot.humidity import DRY_THRESHOLD_GM3, absolute_humidity

logger = logging.getLogger(__name__)

# 적분 구간. 하루를 보는 이유는 낮과 밤의 차이를 모두 담기 위해서다.
WINDOW_HOURS = 24

# 건조 항의 구간.
#
# humidity.py의 DRY_THRESHOLD_GM3(7 g/m³)는 "건조하다고 부를 수 있는 선"이고,
# 피부가 부담을 느끼기 시작하는 지점은 그보다 높다. 경피 수분 손실은 절대습도
# 10 g/m³ 부근에서부터 눈에 띄게 늘어난다고 알려져 있다.
#
# 처음에는 7을 시작점, 0을 최대로 잡았는데 실측값을 넣어보니 사무실
# 6.2 g/m³에서 12점밖에 나오지 않았다. 실제로 건조해서 피부가 당기는
# 상황이 점수에 거의 잡히지 않는다는 뜻이라 구간을 다시 잡았다.
#
#   10 g/m³ 이상  부담 없음 (0점)
#    4 g/m³ 이하  최대 (100점) — 한겨울 난방 실내가 이 수준까지 내려간다
DRY_START_GM3 = 10.0
DRY_FULL_GM3 = 4.0

# 자극 항. 15 이하면 0, 75(매우 나쁨)에서 100이 된다.
PM25_BASE = 15.0
PM25_FULL = 75.0

# 가중치. 건조를 더 크게 보는 이유는 실내 체류 시간이 길고, 국내 실내
# 환경에서 건조가 미세먼지보다 지속적으로 작용하기 때문이다.
W_DRY = 0.6
W_PM = 0.4

# 밴드 경계
BAND_CHECK = 65.0
BAND_CAUTION = 35.0


def _clamp01(x: float) -> float:
    return 0.0 if x < 0 else (1.0 if x > 1 else x)


def _as_utc(v: Any) -> Optional[datetime]:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    try:
        dt = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def band_of(score: float) -> str:
    if score >= BAND_CHECK:
        return "check"
    if score >= BAND_CAUTION:
        return "caution"
    return "good"


def compute_psri(
    readings: Sequence[Dict[str, Any]],
    *,
    window_hours: int = WINDOW_HOURS,
    personal_weight: float = 1.0,
    personal_label: Optional[str] = "성인",
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    측정값 배열에서 PSRI를 계산한다.

    readings는 ts / temperature / humidity / pm25를 가진 dict 목록이다.
    창 밖의 값은 알아서 버린다. 호출하는 쪽이 정확히 24시간을 잘라 넘길
    필요는 없다.

    표본이 하나도 없으면 0점이 아니라 "계산 불가"를 뜻하는 상태로 돌려준다.
    측정이 없는 것과 환경이 좋은 것은 다르다.
    """
    now = now or datetime.now(timezone.utc)
    since = now - timedelta(hours=window_hours)

    dry_sum = 0.0
    dry_n = 0
    pm_sum = 0.0
    pm_n = 0

    for r in readings:
        ts = _as_utc(r.get("ts"))
        if ts is None or ts < since or ts > now:
            continue

        t = r.get("temperature")
        rh = r.get("humidity")
        ah = absolute_humidity(t, rh)
        if ah is not None:
            # 기준보다 얼마나 모자랐는가. 기준 이상이면 0.
            dry_sum += _clamp01((DRY_START_GM3 - ah) / (DRY_START_GM3 - DRY_FULL_GM3))
            dry_n += 1

        pm = r.get("pm25")
        if pm is not None:
            try:
                pm = float(pm)
            except (TypeError, ValueError):
                pm = None
        if pm is not None:
            pm_sum += _clamp01((pm - PM25_BASE) / (PM25_FULL - PM25_BASE))
            pm_n += 1

    dryness = (dry_sum / dry_n * 100.0) if dry_n else None
    irritation = (pm_sum / pm_n * 100.0) if pm_n else None

    # 한쪽 항목이 없으면 남은 가중치로 다시 정규화한다. 0으로 채우면
    # 미세먼지 센서가 없는 노드가 무조건 안전해 보인다. risk_score.py의
    # 광학 항 처리와 같은 원칙이다.
    parts = []
    if dryness is not None:
        parts.append((W_DRY, dryness))
    if irritation is not None:
        parts.append((W_PM, irritation))

    if not parts:
        return {
            "score": 0.0,
            "band": "good",
            "dryness": 0.0,
            "irritation": 0.0,
            "personal_weight": personal_weight,
            "personal_label": personal_label,
            "window_hours": window_hours,
            "sample_n": 0,
            "computable": False,
        }

    total_w = sum(w for w, _ in parts)
    raw = sum(w * v for w, v in parts) / total_w
    score = max(0.0, min(100.0, raw * personal_weight))

    return {
        "score": round(score, 1),
        "band": band_of(score),
        "dryness": round(dryness or 0.0, 1),
        "irritation": round(irritation or 0.0, 1),
        "personal_weight": personal_weight,
        "personal_label": personal_label,
        "window_hours": window_hours,
        "sample_n": max(dry_n, pm_n),
        "computable": True,
    }


def relation_sentence(nodes: List[Dict[str, Any]]) -> Optional[str]:
    """
    PSRI가 왜 이 값인지 환경과 이어주는 한 줄.

    점수만 보여주면 "그래서 뭘 하라는 거지"가 된다. 어느 공간이 원인인지
    지목해야 행동으로 이어진다.
    """
    usable = [n for n in nodes if n.get("absolute_humidity") is not None]
    if not usable:
        return None

    driest = min(usable, key=lambda n: n["absolute_humidity"])
    label = driest.get("label") or driest.get("node_id")
    ah = driest["absolute_humidity"]

    if ah >= DRY_THRESHOLD_GM3:
        return f"{label}의 절대습도가 {ah:.1f} g/m³로 건조 기준({DRY_THRESHOLD_GM3} g/m³) 위에 있습니다."

    others = [n for n in usable if n is not driest]
    if others:
        other_label = max(others, key=lambda n: n["absolute_humidity"])
        ol = other_label.get("label") or other_label.get("node_id")
        return (f"{label}의 절대습도가 {ah:.1f} g/m³로 {ol}보다 낮습니다. "
                f"체류 시간이 긴 쪽의 환경이 피부에 더 크게 작용합니다.")

    return f"{label}의 절대습도가 {ah:.1f} g/m³로 건조 기준 아래입니다."


if __name__ == "__main__":
    import math

    # DB 없이 계산만 확인한다.
    now = datetime.now(timezone.utc)

    def series(temp, rh, pm, n=144):
        return [{"ts": now - timedelta(minutes=10 * i),
                 "temperature": temp, "humidity": rh, "pm25": pm}
                for i in range(n)]

    cases = [
        ("쾌적 (24℃ 50% PM10)", series(24, 50, 10)),
        ("건조 (23℃ 30% PM10)", series(23, 30, 10)),
        ("먼지 (24℃ 50% PM50)", series(24, 50, 50)),
        ("둘 다 (23℃ 28% PM60)", series(23, 28, 60)),
        ("겨울 (20℃ 35% PM20)", series(20, 35, 20)),
    ]

    print(f"  {'상황':<24}{'AH':>7}{'건조':>7}{'자극':>7}{'PSRI':>8}  밴드")
    print("  " + "-" * 62)
    for label, rows in cases:
        ah = absolute_humidity(rows[0]["temperature"], rows[0]["humidity"])
        p = compute_psri(rows, now=now)
        print(f"  {label:<24}{ah:>7.1f}{p['dryness']:>7.0f}{p['irritation']:>7.0f}"
              f"{p['score']:>8.1f}  {p['band']}")

    print()
    print("  측정값이 없을 때:", compute_psri([], now=now)["computable"])