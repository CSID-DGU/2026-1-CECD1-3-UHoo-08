"""
제품별 점검 우선순위 점수.

"같은 서랍에 있어도 성분과 개봉 시점이 달라 점수가 갈린다" — 선별의 근거다.

    risk_score = w1 × (t_consumed / PAO)
               + w2 × excursion_count
               + w3 × days_since_last_check
               + w4 × optical_delta

그런데 각 항의 단위와 범위가 전부 다르다.

    t_consumed / PAO        0 ~ 3      (비율)
    excursion_count         0 ~ 50     (횟수)
    days_since_last_check   0 ~ 300    (일)
    optical_delta           0 ~ 20     (%)

이대로 더하면 days 항이 점수를 독점한다. 그래서 각 항을 먼저 0~1로
정규화하고, 가중합한 뒤 100을 곱한다. 정규화 기준(_FULL 상수)은
"이 값에 도달하면 그 항목만으로 만점"이라는 뜻이다.

── 판정이 아니라 우선순위다 ──────────────────────────────────────
이 점수는 "이 제품이 변질되었다"는 판정이 아니다. 미생물·pH·점도 시험
없이 그런 판정은 불가능하다. 보유 제품 중 어떤 것부터 눈으로 확인할지
순서를 정하는 값이며, UI 문구도 그 범위를 넘지 않아야 한다.

── 측정 이력이 없는 제품에 불이익을 주지 않는다 ────────────────────
광학 측정을 아직 안 한 제품은 w4 항이 빠지고, 남은 가중치로 다시
정규화한다. 그냥 0으로 두면 "측정 안 한 제품이 안전해 보이는" 역전이
생긴다. optical_grade가 unsuitable(투명 토너 등)인 경우도 같다.

같은 원칙을 이탈 항(w2)에도 적용한다. 노드가 여섯 시간만 측정했다면
"이탈 0회"는 안전하다는 뜻이 아니라 모른다는 뜻이다. 그것을 0으로
넣으면 모든 제품의 점수가 일률적으로 눌린다. 실측 구간이
MIN_MEASURED_HOURS_FOR_EXCURSION 미만이면 이 항도 분모에서 뺀다.
"""
from __future__ import annotations

import logging

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Optional, Sequence

from services.iot.erl import ThermalLoad, thermal_load

logger = logging.getLogger(__name__)

# ── 가중치 (합이 1.0) ─────────────────────────────────────────────
# 설계서에 실제 값이 명시되어 있지 않아 여기서 정한다.
# 열이력 소모가 가장 직접적인 노화 지표이므로 절반을 준다.
W_CONSUMED = 0.50   # w1  열이력 소모 비율
W_EXCURSION = 0.20  # w2  고온·고습 노출 횟수
W_LAST_CHECK = 0.15 # w3  마지막 점검 경과
W_OPTICAL = 0.15    # w4  광학 변화율

# ── 정규화 기준 ("이 값이면 해당 항목 만점") ──────────────────────
RATIO_FULL = 1.0       # PAO를 100% 소모하면 만점
EXCURSION_FULL = 60.0  # 이탈 이벤트 60회
LAST_CHECK_FULL = 180.0  # 마지막 점검 후 180일
OPTICAL_FULL = 10.0    # 광학 변화율 10%

# ── 이탈 판정 (설계서 §5-3) ───────────────────────────────────────
EXC_TEMP_C = 30.0        # 이 온도 이상이
EXC_HUMID_PCT = 70.0     # 또는 이 습도 이상이
EXC_MIN_MINUTES = 30.0   # 이만큼 지속되면 이벤트 1회

# 이탈 판정 시 허용하는 측정 공백. 10분 주기 기준 3배까지는 이어진 것으로 본다.
EXC_MAX_GAP_MINUTES = 35.0

# ── 측정 이전 구간의 가속 계수 ───────────────────────────────────
# 노드를 설치하기 전에 개봉된 제품은 그 구간의 온도를 알 수 없다.
# 그렇다고 무시하면 "8개월 전 개봉했지만 열이력은 3주치"가 되어
# 오래된 제품이 실제보다 안전해 보인다.
#
# 알 수 없는 구간은 기준 온도(20℃, AF=1.0)에서 보관된 것으로 친다.
# 즉 "적어도 이만큼은 늙었다"는 하한이며, 과장하지 않는 쪽으로 틀린다.
# 이 구간은 measured_hours와 분리해 보고하므로 UI·발표에서 구분할 수 있다.
ASSUMED_AF_BEFORE_NODE = 1.0

# ── 이탈 통계를 신뢰할 수 있는 최소 실측 구간 ────────────────────
# 이보다 짧게 측정한 구간에서 나온 "이탈 0회"는 안전의 근거가 아니라
# 정보 부족이다. 하루를 기준으로 삼는 이유는 이탈이 주로 낮 시간대에
# 발생하므로 최소한 하루의 온도 주기는 관측해야 의미가 있기 때문이다.
#
# 이 문턱을 넘겨도 한계는 남는다. 8개월 보관 중 9일만 측정했다면 그
# 9일에서 센 이탈 횟수일 뿐이다. measured_hours를 함께 보고하므로
# UI·발표에서 어느 구간의 통계인지 밝힐 수 있다.
MIN_MEASURED_HOURS_FOR_EXCURSION = 24.0

# 광학 등급별 w4 배율 (설계서 §5-2)
OPTICAL_GRADE_FACTOR = {
    "suitable": 1.0,
    "conditional": 0.4,
    "unsuitable": 0.0,
}

# 표시 밴드
BAND_HIGH = 70.0    # 🔴 확인 필요
BAND_MEDIUM = 40.0  # 🟡 주의


@dataclass(frozen=True)
class ExcursionStats:
    """고온·고습 이탈 통계."""

    temp_events: int
    humid_events: int
    hours_above_temp: float
    hours_above_humid: float
    max_temp_c: Optional[float]
    max_humid_pct: Optional[float]

    @property
    def total_events(self) -> int:
        return self.temp_events + self.humid_events


@dataclass(frozen=True)
class RiskScore:
    """제품 하나의 점검 우선순위 점수와 그 근거."""

    score: float                  # 0 ~ 100
    band: str                     # high | medium | low
    components: dict              # 항목별 정규화 점수와 기여도
    load: ThermalLoad
    excursions: ExcursionStats
    measured_hours: float         # 노드가 실제로 측정한 구간
    assumed_hours: float          # 개봉~노드 설치 사이의 미측정 구간
    excursion_counted: bool       # 이탈 항을 점수에 반영했는지
    consumed_ratio: Optional[float]   # 두 구간을 합친 최종 소모 비율
    days_since_last_check: Optional[float]
    optical_delta_pct: Optional[float]
    optical_grade: Optional[str]
    reasons: list = field(default_factory=list)   # UI 표시용 근거 문구


def _as_utc(v: Any) -> Optional[datetime]:
    """DB에서 온 날짜/시각을 tz-aware UTC datetime으로 정규화한다."""
    if v is None:
        return None
    if isinstance(v, datetime):
        dt = v
    elif isinstance(v, date):
        dt = datetime(v.year, v.month, v.day)
    else:
        s = str(v)
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(s)
        except ValueError:
            logger.warning("날짜 파싱 실패: %r", v)
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def count_excursions(
    readings: Sequence[dict],
    *,
    temp_c: float = EXC_TEMP_C,
    humid_pct: float = EXC_HUMID_PCT,
    min_minutes: float = EXC_MIN_MINUTES,
    max_gap_minutes: float = EXC_MAX_GAP_MINUTES,
) -> ExcursionStats:
    """
    임계 초과가 일정 시간 지속된 구간을 이벤트 1회로 센다.

    순간값 초과를 매번 세지 않는 이유: 서랍을 여닫는 순간이나 센서 노이즈로
    30.1℃가 한 번 찍히는 것과, 한낮에 세 시간 동안 34℃였던 것은 다르다.
    설계서 §5-3의 "30℃ 이상 30분 지속"을 그대로 따른다.

    누적 시간(hours_above_*)은 지속 조건과 무관하게 임계를 넘은 모든 구간의
    합이다. UI에서 "34℃ 노출 42시간" 같은 문구에 쓴다.
    """
    rows: list[tuple[datetime, Optional[float], Optional[float]]] = []
    for r in readings:
        ts = _as_utc(r.get("ts"))
        if ts is None:
            continue
        t = r.get("temperature")
        h = r.get("humidity")
        rows.append((ts, float(t) if t is not None else None,
                     float(h) if h is not None else None))

    if not rows:
        return ExcursionStats(0, 0, 0.0, 0.0, None, None)

    rows.sort(key=lambda x: x[0])
    max_gap_s = max_gap_minutes * 60.0
    min_s = min_minutes * 60.0

    def scan(index: int, threshold: float) -> tuple[int, float]:
        events = 0
        hours = 0.0
        run_start: Optional[datetime] = None
        run_last: Optional[datetime] = None
        counted = False

        for row in rows:
            ts = row[0]
            v = row[index]
            over = v is not None and v >= threshold

            if over:
                if run_start is None:
                    run_start, run_last, counted = ts, ts, False
                else:
                    gap = (ts - run_last).total_seconds()
                    if gap > max_gap_s:
                        # 측정이 끊긴 구간. 이어진 것으로 볼 수 없어 새 구간으로 연다.
                        run_start, run_last, counted = ts, ts, False
                    else:
                        hours += gap / 3600.0
                        run_last = ts
                        if not counted and (run_last - run_start).total_seconds() >= min_s:
                            events += 1
                            counted = True
            else:
                run_start = run_last = None
                counted = False

        return events, hours

    temp_events, temp_hours = scan(1, temp_c)
    humid_events, humid_hours = scan(2, humid_pct)

    temps = [t for _, t, _ in rows if t is not None]
    hums = [h for _, _, h in rows if h is not None]

    return ExcursionStats(
        temp_events=temp_events,
        humid_events=humid_events,
        hours_above_temp=temp_hours,
        hours_above_humid=humid_hours,
        max_temp_c=max(temps) if temps else None,
        max_humid_pct=max(hums) if hums else None,
    )


def _clamp01(v: float) -> float:
    return 0.0 if v < 0 else (1.0 if v > 1 else v)


def compute_risk_score(
    readings: Sequence[dict],
    *,
    sensitivity: Any = "normal",
    pao_months: Optional[float] = None,
    opened_at: Any = None,
    last_checked_at: Any = None,
    optical_delta_pct: Optional[float] = None,
    optical_grade: Optional[str] = None,
    now: Optional[datetime] = None,
) -> RiskScore:
    """
    제품 하나의 점검 우선순위 점수를 계산한다.

    readings는 그 제품이 놓인 보관 노드의 측정값이며,
    호출자가 개봉일 이후 구간으로 잘라서 넘겨야 한다.
    """
    now = now or datetime.now(timezone.utc)

    load = thermal_load(readings, sensitivity=sensitivity, pao_months=pao_months)
    exc = count_excursions(readings)

    # ── 노드 설치 이전 구간 보정 ──────────────────────────────────
    # 개봉일이 첫 측정보다 앞서면 그 사이는 측정 기록이 없다.
    # AF = 1.0(20℃ 상당)으로 채워 하한을 잡는다. 실제로는 더 더웠을
    # 가능성이 크므로 이 값은 과소평가 방향이다.
    opened_dt = _as_utc(opened_at)
    measured_hours = load.history.wall_hours
    assumed_hours = 0.0
    if opened_dt and load.history.first_ts and opened_dt < load.history.first_ts:
        assumed_hours = (load.history.first_ts - opened_dt).total_seconds() / 3600.0

    consumed_hours = load.consumed_hours + assumed_hours * ASSUMED_AF_BEFORE_NODE * load.k
    consumed_ratio = (consumed_hours / load.pao_hours) if load.pao_hours else None

    # ── 각 항을 0~1로 정규화 ──────────────────────────────────────
    # PAO를 모르면 소모 비율을 계산할 수 없다. 임의로 0을 넣으면
    # "PAO 미등록 제품이 안전해 보이는" 역전이 생기므로 항목 자체를 뺀다.
    s_consumed = (_clamp01(consumed_ratio / RATIO_FULL)
                  if consumed_ratio is not None else None)

    # 실측이 너무 짧으면 이탈 통계 자체가 정보가 아니다. 광학과 같은
    # 규칙으로 항목을 통째로 뺀다. 0을 넣으면 "안전"으로 오독된다.
    excursion_counted = measured_hours >= MIN_MEASURED_HOURS_FOR_EXCURSION
    s_excursion = (_clamp01(exc.total_events / EXCURSION_FULL)
                   if excursion_counted else None)

    ref = _as_utc(last_checked_at) or _as_utc(opened_at)
    days_since = (now - ref).total_seconds() / 86400.0 if ref else None
    s_last_check = (_clamp01(days_since / LAST_CHECK_FULL)
                    if days_since is not None else None)

    grade_factor = OPTICAL_GRADE_FACTOR.get((optical_grade or "").lower(), 0.0)
    s_optical = None
    if optical_delta_pct is not None and grade_factor > 0:
        s_optical = _clamp01(optical_delta_pct / OPTICAL_FULL) * grade_factor

    # ── 가중합. 값이 없는 항목은 분모에서도 뺀다 ──────────────────
    parts = [
        ("consumed", W_CONSUMED, s_consumed),
        ("excursion", W_EXCURSION, s_excursion),
        ("last_check", W_LAST_CHECK, s_last_check),
        ("optical", W_OPTICAL, s_optical),
    ]
    active = [(name, w, s) for name, w, s in parts if s is not None]
    total_w = sum(w for _, w, _ in active)

    score = 100.0 * sum(w * s for _, w, s in active) / total_w if total_w else 0.0

    components = {
        name: {
            "normalized": round(s, 4) if s is not None else None,
            "weight": w,
            "contribution": round(100.0 * w * s / total_w, 2)
            if (s is not None and total_w) else None,
        }
        for name, w, s in parts
    }

    band = "high" if score >= BAND_HIGH else ("medium" if score >= BAND_MEDIUM else "low")

    # ── UI 표시용 근거 ────────────────────────────────────────────
    reasons: list[str] = []
    opened = _as_utc(opened_at)
    if opened:
        months = (now - opened).days / 30.0
        reasons.append(f"개봉 {months:.0f}개월")
    if exc.hours_above_temp >= 1.0 and exc.max_temp_c is not None:
        reasons.append(f"{exc.max_temp_c:.0f}℃ 노출 {exc.hours_above_temp:.0f}시간")
    if consumed_ratio is not None:
        reasons.append(f"열이력 소모 {consumed_ratio * 100:.0f}%")
    if optical_delta_pct is not None and grade_factor > 0:
        reasons.append(f"광학 변화 {optical_delta_pct:.1f}%")

    return RiskScore(
        score=round(score, 1),
        band=band,
        components=components,
        load=load,
        excursions=exc,
        measured_hours=measured_hours,
        assumed_hours=assumed_hours,
        excursion_counted=excursion_counted,
        consumed_ratio=consumed_ratio,
        days_since_last_check=days_since,
        optical_delta_pct=optical_delta_pct,
        optical_grade=optical_grade,
        reasons=reasons,
    )


def rank_products(items: Sequence[dict]) -> list:
    """
    여러 제품의 점수를 계산해 높은 순으로 정렬한다.

    items의 각 원소는 compute_risk_score의 키워드 인자에 더해
    식별·표시용 필드(user_product_id, name 등)를 담은 dict다.
    계산에 쓰이지 않는 키는 결과에 그대로 실어 보낸다.
    """
    # now를 포함시키는 이유: 넣지 않으면 각 항목이 실제 현재 시각을 쓰게 되어
    # 고정 시나리오의 결과가 실행일마다 달라진다. (자체 테스트 대조값이 흔들렸다)
    kw = {"readings", "sensitivity", "pao_months", "opened_at",
          "last_checked_at", "optical_delta_pct", "optical_grade", "now"}

    out = []
    for item in items:
        args = {k: v for k, v in item.items() if k in kw}
        rs = compute_risk_score(**args)
        meta = {k: v for k, v in item.items() if k not in kw}
        out.append({"risk": rs, **meta})

    out.sort(key=lambda x: x["risk"].score, reverse=True)
    return out


if __name__ == "__main__":
    # 설계서 §5-1 시나리오를 그대로 넣어 실제 점수를 확인한다.
    from datetime import timedelta

    now = datetime(2026, 8, 19, tzinfo=timezone.utc)

    def drawer_series(days: int) -> list[dict]:
        """
        화장대를 모사한 일교차 시계열. 10분 간격.
        낮 33℃ / 밤 25℃, 습도는 온도와 반대로 움직인다.
        """
        import math
        start = now - timedelta(days=days)
        rows = []
        for i in range(days * 144):
            ts = start + timedelta(minutes=10 * i)
            phase = (i % 144) / 144.0
            t = 29.0 + 4.0 * math.sin(2 * math.pi * (phase - 0.25))
            h = 62.0 - 8.0 * math.sin(2 * math.pi * (phase - 0.25))
            rows.append({"ts": ts, "temperature": round(t, 2), "humidity": round(h, 2)})
        return rows

    print("── 이탈 통계 (최근 30일, 낮 33℃ / 밤 25℃) ──")
    e = count_excursions(drawer_series(30))
    print(f"  온도 이벤트 {e.temp_events}회  누적 {e.hours_above_temp:.1f}h  최고 {e.max_temp_c:.1f}℃")
    print(f"  습도 이벤트 {e.humid_events}회  누적 {e.hours_above_humid:.1f}h  최고 {e.max_humid_pct:.1f}%")

    print("\n── 설계서 §5-1 시나리오 ──")
    scenarios = [
        ("레티놀 세럼", "high", 6, 240),
        ("수분 크림", "normal", 12, 90),
        ("무기 자차", "low", 12, 30),
    ]

    items = []
    for name, sens, pao, opened_days in scenarios:
        items.append({
            "name": name,
            "readings": drawer_series(min(opened_days, 60)),  # 노드 가동 구간만
            "sensitivity": sens,
            "pao_months": pao,
            "opened_at": now - timedelta(days=opened_days),
            "now": now,
        })

    print(f"  {'제품':<12}{'점수':>7}{'밴드':>8}   근거")
    for row in rank_products(items):
        r = row["risk"]
        print(f"  {row['name']:<12}{r.score:>7.1f}{r.band:>8}   {' · '.join(r.reasons)}")

    print("\n  기여도 분해 (1위 제품)")
    top = rank_products(items)[0]
    for k, v in top["risk"].components.items():
        if v["normalized"] is None:
            print(f"    {k:<12} (해당 없음 — 분모에서 제외)")
        else:
            print(f"    {k:<12} 정규화={v['normalized']:.3f}  기여={v['contribution']:.1f}점")

    print("\n── 광학 측정 유무 비교 (같은 제품) ──")
    base = {
        "readings": drawer_series(30),
        "sensitivity": "normal",
        "pao_months": 12,
        "opened_at": now - timedelta(days=90),
    }
    base["now"] = now
    a = compute_risk_score(**base)
    b = compute_risk_score(**base, optical_delta_pct=6.0, optical_grade="suitable")
    c = compute_risk_score(**base, optical_delta_pct=6.0, optical_grade="unsuitable")
    print(f"  측정 없음                  {a.score:.1f}")
    print(f"  변화 6% / suitable        {b.score:.1f}")
    print(f"  변화 6% / unsuitable      {c.score:.1f}  ← 측정 없음과 같아야 정상")