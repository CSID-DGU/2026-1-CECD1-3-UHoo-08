"""
열이력 적산 (Effective Residual Life).

보관 온도가 높을수록 화장품의 화학적 노화가 빨라진다는 사실을
"실제로 흐른 시간"이 아닌 "제품이 체감한 시간"으로 환산한다.

    AF(T)      = Q10 ^ ((T - T_ref) / 10)      가속 계수
    t_eff      = ∫ AF(T(t)) dt                 유효 경과 시간
    t_consumed = t_eff × k                     성분 민감도 반영

    고민감 1.5 (레티놀, 순수 비타민C) / 중민감 1.3 (식물성 오일, 유기 자외선차단제)
    일반   1.0 (일반 에멀전)          / 저민감 0.7 (무기 자외선차단제, 파우더)

── 왜 평균 온도로 계산하면 안 되는가 ───────────────────────────────
AF는 온도에 대해 위로 볼록한(convex) 지수 함수다. 따라서 옌센 부등식에 의해

    평균(AF(T))  ≥  AF(평균(T))

가 항상 성립한다. 즉 "평균 26.8℃였다"로 계산하면 실제 열이력을 과소평가한다.
일교차가 클수록 차이가 커진다. 창가 화장대처럼 낮에 33℃, 밤에 21℃를 오가는
환경은 평균만 보면 27℃로 무난해 보이지만, 적산하면 27℃ 항온보다 노화가 빠르다.
이 모듈이 존재하는 이유가 그것이다.

── 결측 구간 처리 ──────────────────────────────────────────────────
노드가 꺼져 있던 구간을 마지막 온도로 메우면 열이력이 통째로 조작된다.
(사흘 정전 → 마지막에 읽은 30℃로 사흘을 채우는 상황)
따라서 연속한 두 측정의 간격이 MAX_GAP_HOURS를 넘으면 그 구간은
적산에서 제외하고 gap_hours로 따로 보고한다. 숨기지 않는다.
"""
from __future__ import annotations

import logging

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Optional, Sequence

logger = logging.getLogger(__name__)

# Q10 = 2 : 온도가 10℃ 오를 때 반응 속도가 2배가 된다는 경험칙.
# 화장품 안정성 시험에서 관행적으로 쓰이는 값이며 설계서 §5-1의 전제다.
Q10 = 2.0

# 기준 온도. 이 온도에서 AF = 1.0 이 되어 실시간과 유효시간이 같아진다.
T_REF_C = 20.0

# 이 시간을 넘는 측정 공백은 적산하지 않는다. 10분 주기 기준으로
# 6배까지는 일시적 전송 지연으로 보고 이어붙인다.
MAX_GAP_HOURS = 1.0

# PAO(개봉 후 사용기간) 개월 → 시간 환산에 쓰는 한 달의 길이.
DAYS_PER_MONTH = 30.0
HOURS_PER_MONTH = DAYS_PER_MONTH * 24.0

# 성분군별 민감도 계수
SENSITIVITY_K = {
    "high": 1.5,
    "medium": 1.3,
    "normal": 1.0,
    "low": 0.7,
}


@dataclass(frozen=True)
class ThermalHistory:
    """열이력 적산 결과."""

    sample_n: int              # 온도가 유효했던 측정 건수
    wall_hours: float          # 적산에 실제로 반영된 실시간 (공백 제외)
    gap_hours: float           # 결측으로 제외한 시간
    effective_hours: float     # t_eff — 20℃ 환산 유효 경과 시간
    acceleration: float        # t_eff / wall_hours. 1.0이면 20℃와 동일
    mean_temp_c: Optional[float]
    max_temp_c: Optional[float]
    min_temp_c: Optional[float]
    first_ts: Optional[datetime]
    last_ts: Optional[datetime]

    @property
    def effective_days(self) -> float:
        return self.effective_hours / 24.0

    @property
    def effective_months(self) -> float:
        return self.effective_hours / HOURS_PER_MONTH


@dataclass(frozen=True)
class ThermalLoad:
    """제품 하나에 대한 열이력 소모 결과."""

    history: ThermalHistory
    k: float                   # 성분 민감도
    consumed_hours: float      # t_consumed = t_eff × k
    pao_hours: Optional[float]
    consumed_ratio: Optional[float]   # t_consumed / PAO. PAO 미상이면 None

    @property
    def consumed_months(self) -> float:
        return self.consumed_hours / HOURS_PER_MONTH


def acceleration_factor(temp_c: float, *, q10: float = Q10, t_ref_c: float = T_REF_C) -> float:
    """
    단일 온도에서의 가속 계수.

        20℃ → 1.00   (기준)
        25℃ → 1.41
        30℃ → 2.00
        40℃ → 4.00
    """
    return q10 ** ((temp_c - t_ref_c) / 10.0)


def _as_utc(ts: Any) -> datetime:
    """DB에서 온 ts를 tz-aware UTC datetime으로 정규화한다."""
    if isinstance(ts, datetime):
        dt = ts
    else:
        s = str(ts)
        # PostgREST는 '2026-08-18T01:23:45+00:00' 또는 '...Z' 로 준다.
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def accumulate(
    readings: Iterable[dict],
    *,
    q10: float = Q10,
    t_ref_c: float = T_REF_C,
    max_gap_hours: float = MAX_GAP_HOURS,
) -> ThermalHistory:
    """
    측정 시계열에서 유효 경과 시간을 적산한다.

    readings: {"ts": ..., "temperature": ...} 를 가진 dict의 나열.
              sensor_readings 행을 그대로 넣으면 된다. 순서는 무관하다.

    구간 적분은 사다리꼴로 한다. 연속한 두 측정의 AF를 평균해 간격을 곱하므로,
    계단 근사보다 온도가 오르내리는 실측 데이터에서 오차가 작다.
    """
    rows: list[tuple[datetime, float]] = []
    for r in readings:
        t = r.get("temperature")
        if t is None:
            continue
        try:
            rows.append((_as_utc(r["ts"]), float(t)))
        except (KeyError, ValueError, TypeError):
            logger.warning("열이력 적산에서 건너뛴 행: %r", r)
            continue

    if not rows:
        return ThermalHistory(
            sample_n=0, wall_hours=0.0, gap_hours=0.0, effective_hours=0.0,
            acceleration=1.0, mean_temp_c=None, max_temp_c=None, min_temp_c=None,
            first_ts=None, last_ts=None,
        )

    rows.sort(key=lambda x: x[0])

    eff_hours = 0.0
    wall_hours = 0.0
    gap_hours = 0.0

    prev_ts, prev_t = rows[0]
    prev_af = acceleration_factor(prev_t, q10=q10, t_ref_c=t_ref_c)

    for ts, t in rows[1:]:
        dt_h = (ts - prev_ts).total_seconds() / 3600.0
        af = acceleration_factor(t, q10=q10, t_ref_c=t_ref_c)

        if dt_h <= 0:
            # 동일 ts 중복. 유니크 인덱스가 있으므로 정상적으로는 오지 않는다.
            prev_ts, prev_t, prev_af = ts, t, af
            continue

        if dt_h > max_gap_hours:
            gap_hours += dt_h          # 노드가 죽어 있던 구간. 적산하지 않는다.
        else:
            eff_hours += (prev_af + af) / 2.0 * dt_h
            wall_hours += dt_h

        prev_ts, prev_t, prev_af = ts, t, af

    temps = [t for _, t in rows]

    return ThermalHistory(
        sample_n=len(rows),
        wall_hours=wall_hours,
        gap_hours=gap_hours,
        effective_hours=eff_hours,
        acceleration=(eff_hours / wall_hours) if wall_hours > 0 else 1.0,
        mean_temp_c=sum(temps) / len(temps),
        max_temp_c=max(temps),
        min_temp_c=min(temps),
        first_ts=rows[0][0],
        last_ts=rows[-1][0],
    )


def resolve_k(sensitivity: Any) -> float:
    """
    성분 민감도를 계수로 바꾼다.

    product_thermal_profile.sensitivity_k에 숫자가 들어 있으면 그대로 쓰고,
    'high'/'medium'/'normal'/'low' 문자열이면 표에서 찾는다.
    알 수 없으면 1.0(일반)으로 떨어뜨린다. 조용히 0으로 만들지 않는다.
    """
    if sensitivity is None:
        return SENSITIVITY_K["normal"]
    if isinstance(sensitivity, (int, float)):
        return float(sensitivity)
    key = str(sensitivity).strip().lower()
    if key in SENSITIVITY_K:
        return SENSITIVITY_K[key]
    try:
        return float(key)
    except ValueError:
        logger.warning("알 수 없는 민감도 값 %r → 1.0으로 처리", sensitivity)
        return SENSITIVITY_K["normal"]


def thermal_load(
    readings: Sequence[dict],
    *,
    sensitivity: Any = "normal",
    pao_months: Optional[float] = None,
    q10: float = Q10,
    t_ref_c: float = T_REF_C,
    max_gap_hours: float = MAX_GAP_HOURS,
) -> ThermalLoad:
    """
    제품 하나의 열이력 소모를 계산한다.

    readings는 그 제품이 놓인 보관 노드의 측정값이며, 호출자가
    개봉일(opened_at) 이후 구간으로 잘라서 넘겨야 한다.
    개봉 전에는 밀봉 상태라 노화 속도가 다르기 때문이다.
    """
    hist = accumulate(readings, q10=q10, t_ref_c=t_ref_c, max_gap_hours=max_gap_hours)
    k = resolve_k(sensitivity)
    consumed = hist.effective_hours * k

    pao_hours = float(pao_months) * HOURS_PER_MONTH if pao_months else None
    ratio = (consumed / pao_hours) if pao_hours else None

    return ThermalLoad(
        history=hist,
        k=k,
        consumed_hours=consumed,
        pao_hours=pao_hours,
        consumed_ratio=ratio,
    )


if __name__ == "__main__":
    # 손으로 검산 가능한 자기 검증. DB 없이 바로 돌아간다.
    from datetime import timedelta

    def series(temps: list[float], step_min: int = 10) -> list[dict]:
        t0 = datetime(2026, 8, 1, tzinfo=timezone.utc)
        return [
            {"ts": t0 + timedelta(minutes=step_min * i), "temperature": t}
            for i, t in enumerate(temps)
        ]

    print("── AF 검산 ──")
    for t in (20, 25, 30, 40):
        print(f"  AF({t}℃) = {acceleration_factor(t):.4f}")

    print("\n── 항온 20℃ 24시간: 유효시간이 실시간과 같아야 함 ──")
    h = accumulate(series([20.0] * 145))
    print(f"  wall={h.wall_hours:.2f}h  eff={h.effective_hours:.2f}h  가속={h.acceleration:.3f}")

    print("\n── 항온 30℃ 24시간: 유효시간이 2배여야 함 ──")
    h = accumulate(series([30.0] * 145))
    print(f"  wall={h.wall_hours:.2f}h  eff={h.effective_hours:.2f}h  가속={h.acceleration:.3f}")

    print("\n── 옌센 부등식 확인: 평균은 같고 진폭만 다른 두 계열 ──")
    flat = accumulate(series([27.0] * 145))
    swing = accumulate(series([33.0 if (i // 72) % 2 == 0 else 21.0 for i in range(145)]))
    print(f"  항온 27℃     평균={flat.mean_temp_c:.1f}℃  가속={flat.acceleration:.3f}")
    print(f"  21↔33℃ 변동  평균={swing.mean_temp_c:.1f}℃  가속={swing.acceleration:.3f}")
    print("  → 평균이 같아도 변동이 큰 쪽이 더 빨리 늙는다")

    print("\n── 결측 구간: 3일 공백은 적산되지 않아야 함 ──")
    t0 = datetime(2026, 8, 1, tzinfo=timezone.utc)
    gapped = [{"ts": t0 + timedelta(minutes=10 * i), "temperature": 30.0} for i in range(7)]
    gapped += [{"ts": t0 + timedelta(days=3) + timedelta(minutes=10 * i), "temperature": 30.0}
               for i in range(7)]
    h = accumulate(gapped)
    print(f"  wall={h.wall_hours:.2f}h  gap={h.gap_hours:.2f}h  eff={h.effective_hours:.2f}h")

    print("\n── 설계서 §5-1 예시 재계산 (3개월 평균 26.8℃) ──")
    h = accumulate(series([26.8] * (6 * 24 * 90 + 1)))
    print(f"  실시간 {h.wall_hours / HOURS_PER_MONTH:.2f}개월"
          f" → 유효 {h.effective_months:.2f}개월 (가속 {h.acceleration:.3f})")
    print("  ※ 설계서는 4.2개월로 적혀 있으나 Q10=2, 기준 20℃로는 4.81개월이 맞다")

    print("\n── 제품별 소모 비율 ──")
    r90 = series([26.8] * (6 * 24 * 90 + 1))
    for name, sens, pao in [
        ("레티놀 세럼", "high", 6),
        ("수분 크림", "normal", 12),
        ("무기 자차", "low", 12),
    ]:
        load = thermal_load(r90, sensitivity=sens, pao_months=pao)
        print(f"  {name:12} k={load.k}  소모={load.consumed_months:.2f}개월"
              f"  PAO={pao}개월  비율={load.consumed_ratio:.1%}")