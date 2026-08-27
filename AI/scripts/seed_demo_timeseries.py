"""
시연용 시계열 데이터 시딩.

노드가 몇 주 돌아간 것처럼 sensor_readings를 채우고, 거기서 파생되는
risk_events · storage_baseline · optical_measurements · skin_measurements를
함께 만든다.

    python -m scripts.seed_demo_timeseries                 # 계획만 출력
    python -m scripts.seed_demo_timeseries --apply
    python -m scripts.seed_demo_timeseries --days 30 --seed 7 --apply
    python -m scripts.seed_demo_timeseries --reset --apply  # 시드 구간 삭제

── 이 데이터는 실측이 아니다 ───────────────────────────────────────
sensor_readings에는 "시드로 만든 행"이라는 표시가 없다. 실제 노드가 올린
값과 컬럼이 같기 때문이다. 즉 한 번 넣으면 실측과 구분할 수 없다.

그래서 두 가지를 지켜야 한다.
  · 실제 노드를 돌릴 노드에는 시드를 넣지 않거나, 넣었다면 --reset으로
    지운 뒤에 실측을 시작한다

── 값을 어떻게 만드는가 ────────────────────────────────────────────
난수를 그냥 뿌리면 그래프가 톱니처럼 보이고, 열이력 적산도 이상해진다.
실제 실내 환경이 갖는 성질을 따라간다.

  · 하루 주기  — 낮에 오르고 새벽에 낮아지는 사인파
  · 느린 표류  — 며칠에 걸친 계절성 변화
  · 짧은 잡음  — 센서 분해능 수준의 흔들림
  · 이벤트     — 창가 서랍이 오후에 30℃를 넘는 날, 향수를 뿌린 순간

가스 저항은 온습도에 크게 의존한다(설계서의 회귀 모델이 존재하는 이유다).
그래서 log(R) = a + b·T + c·RH + 잔차 형태로 만들고, 시딩이 끝나면 그
데이터로 회귀를 돌려 storage_baseline에 계수를 넣는다. 만들 때 쓴 계수를
그대로 적어 넣지 않는 이유는, 회귀 코드가 실제로 동작하는지 함께
확인하기 위해서다.
"""
from __future__ import annotations

import argparse
import math
import random

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from db.iot.reader import get_care_products, list_nodes
from db.supabase_client import get_supabase

DEFAULT_USER = "aa000000-0000-0000-0000-000000000001"

# 펌웨어 전송 주기와 같게 맞춘다. 다르게 하면 화면의 "N건" 표시가
# 실제 운영과 어긋난다.
INTERVAL_MIN = 10
PER_DAY = 24 * 60 // INTERVAL_MIN          # 144

# 한 번에 보내는 행 수. 너무 크면 요청이 실패하고, 너무 작으면 느리다.
CHUNK = 500

# ── 노드별 환경 성격 ─────────────────────────────────────────────
# 화장대 서랍은 창가라 낮에 데워지고, 사무실은 에어컨 때문에 건조하다.
# 이 차이가 있어야 "어디에 두느냐가 다르다"는 이야기가 화면에서 보인다.
NODE_PROFILE: Dict[str, Dict[str, Any]] = {
    "storage-01": {
        "temp_mean": 26.5, "temp_amp": 3.2,
        "rh_mean": 52.0, "rh_amp": 6.0,
        "pm25": None,
        "gas": True,
        # 오후에 직사광이 드는 날. 이 날들만 30℃를 넘긴다.
        "hot_days": [3, 4, 11, 17, 18],
        "hot_bonus": 5.5,
    },
    "ambient-01": {
        "temp_mean": 24.1, "temp_amp": 2.0,
        "rh_mean": 47.0, "rh_amp": 5.0,
        "pm25": 18.0,
        "gas": False,
        "hot_days": [],
        "hot_bonus": 0.0,
    },
    "ambient-02": {
        "temp_mean": 22.6, "temp_amp": 1.6,
        "rh_mean": 31.0, "rh_amp": 4.0,   # 에어컨으로 건조
        "pm25": 24.0,
        "gas": False,
        "hot_days": [],
        "hot_bonus": 0.0,
    },
}

# 가스 저항 생성 계수. log10(R) 기준.
# 온도가 오르면 저항이 내려가고, 습도가 오르면 더 크게 내려간다.
GAS_A = 5.35          # 기준 절편 (약 224 kΩ)
GAS_B_TEMP = -0.018   # ℃당
GAS_C_HUMID = -0.011  # %RH당
GAS_NOISE_SD = 0.012

# 향수·헤어스프레이를 뿌린 순간. (일차, 시각) — 저항이 급락한다.
VOC_SPIKES = [(6, 20), (14, 8), (20, 21)]
VOC_DROP = 0.45       # log10 기준 낙폭 (약 65% 하락)
VOC_DECAY_MIN = 90    # 원래대로 돌아오는 시간

# 이탈 판정 기준. risk_score.py와 같은 값을 쓴다.
EXCURSION_TEMP_C = 30.0
EXCURSION_MIN_MIN = 30


# ── 시계열 생성 ──────────────────────────────────────────────────

def _diurnal(minute_of_day: int) -> float:
    """하루 주기. 새벽 5시 최저, 오후 3시 최고."""
    phase = (minute_of_day / 1440.0) - (5 / 24.0)
    return math.sin(2 * math.pi * phase - math.pi / 2)


def build_series(
    node_id: str,
    days: int,
    end: datetime,
    rng: random.Random,
) -> List[Dict[str, Any]]:
    p = NODE_PROFILE[node_id]
    start = end - timedelta(days=days)
    rows: List[Dict[str, Any]] = []

    # 며칠에 걸친 느린 표류. 매 스텝 조금씩 움직이는 임의보행이지만
    # 너무 멀리 가지 않도록 평균으로 당긴다(평균회귀).
    drift_t = 0.0
    drift_h = 0.0

    total = days * PER_DAY
    for i in range(total):
        ts = start + timedelta(minutes=INTERVAL_MIN * i)
        day_idx = (ts - start).days
        mod = ts.hour * 60 + ts.minute

        drift_t += rng.gauss(0, 0.05) - drift_t * 0.01
        drift_h += rng.gauss(0, 0.12) - drift_h * 0.01

        wave = _diurnal(mod)
        temp = p["temp_mean"] + p["temp_amp"] * wave + drift_t + rng.gauss(0, 0.08)
        rh = p["rh_mean"] - p["rh_amp"] * wave + drift_h + rng.gauss(0, 0.3)

        # 직사광이 드는 날의 오후. 종 모양으로 얹는다.
        if day_idx in p["hot_days"] and 12 * 60 <= mod <= 18 * 60:
            x = (mod - 15 * 60) / (180.0)     # 15시 중심
            temp += p["hot_bonus"] * math.exp(-4 * x * x)
            rh -= 4.0 * math.exp(-4 * x * x)

        rh = max(15.0, min(85.0, rh))

        row: Dict[str, Any] = {
            "node_id": node_id,
            "ts": ts.isoformat(),
            "temperature": round(temp, 2),
            "humidity": round(rh, 2),
        }

        if p["pm25"] is not None:
            # 미세먼지는 하루 주기보다 며칠 단위 기단 영향이 크다.
            base = p["pm25"] * (1.0 + 0.35 * math.sin(2 * math.pi * day_idx / 6.0))
            row["pm25"] = round(max(2.0, base + rng.gauss(0, 3.0)), 1)

        if p["gas"]:
            log_r = (GAS_A + GAS_B_TEMP * temp + GAS_C_HUMID * rh
                     + rng.gauss(0, GAS_NOISE_SD))

            # VOC 유입. 급락 후 지수적으로 회복한다.
            for (d, hour) in VOC_SPIKES:
                spike_at = start + timedelta(days=d, hours=hour)
                dt_min = (ts - spike_at).total_seconds() / 60.0
                if 0 <= dt_min <= VOC_DECAY_MIN * 4:
                    log_r -= VOC_DROP * math.exp(-dt_min / VOC_DECAY_MIN)

            row["gas_resistance"] = round(10 ** log_r, 1)

        rows.append(row)

    return rows


# ── 파생 데이터 ──────────────────────────────────────────────────

def detect_events(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    생성한 시계열에서 이벤트를 찾는다.

    값을 만들 때 "여기에 이벤트가 있다"고 적어두지 않고 굳이 다시 찾는
    이유는, 탐지 기준(30℃ 30분 지속)이 실제로 걸리는지 확인하기 위해서다.
    적어둔 대로 넣으면 기준이 틀려도 알 수 없다.
    """
    events: List[Dict[str, Any]] = []

    # 온도 이탈: 30℃ 이상이 30분 넘게 이어진 구간
    run_start: Optional[datetime] = None
    peak = 0.0
    need = EXCURSION_MIN_MIN // INTERVAL_MIN

    seq: List[Dict[str, Any]] = []
    for r in rows:
        t = r.get("temperature")
        ts = datetime.fromisoformat(r["ts"])
        if t is not None and t >= EXCURSION_TEMP_C:
            if run_start is None:
                run_start, peak = ts, t
                seq = [r]
            else:
                peak = max(peak, t)
                seq.append(r)
        else:
            if run_start is not None and len(seq) >= need:
                events.append({
                    "node_id": r["node_id"],
                    "ts": run_start.isoformat(),
                    "event_type": "temp_excursion",
                    "magnitude": round(peak, 2),
                    "user_answer": "none",
                    "excluded": False,
                })
            run_start, seq = None, []

    # VOC 급락: 직전 6시간 중앙값 대비 40% 이상 하락
    gas = [(datetime.fromisoformat(r["ts"]), r["gas_resistance"], r["node_id"])
           for r in rows if r.get("gas_resistance") is not None]
    window = 6 * 60 // INTERVAL_MIN
    last_ts: Optional[datetime] = None

    for i in range(window, len(gas)):
        ts, val, node = gas[i]
        prev = sorted(v for _, v, _ in gas[i - window:i])
        med = prev[len(prev) // 2]
        if med <= 0:
            continue
        drop = (med - val) / med
        if drop >= 0.40:
            # 같은 사건이 여러 번 잡히지 않게 2시간 안쪽은 건너뛴다
            if last_ts and (ts - last_ts).total_seconds() < 7200:
                continue
            last_ts = ts
            events.append({
                "node_id": node,
                "ts": ts.isoformat(),
                "event_type": "voc_spike",
                "magnitude": round(drop * 100, 1),
                # 첫 건은 사용자가 아직 답하지 않은 상태로 둔다.
                # 키오스크의 "질문" 흐름을 시연하려면 pending이 하나 필요하다.
                "user_answer": "pending",
                "excluded": False,
            })

    # 두 번째 VOC 건부터는 사용자가 이미 답한 것으로 둔다.
    voc_seen = 0
    for e in events:
        if e["event_type"] != "voc_spike":
            continue
        voc_seen += 1
        if voc_seen == 2:
            # "향수를 뿌렸다"고 답한 경우 → 분석에서 제외
            e["user_answer"] = "external_source"
            e["excluded"] = True
        elif voc_seen >= 3:
            e["user_answer"] = "none"

    return events


def fit_baseline(rows: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    log10(R) ≈ a + b·T + c·RH 회귀.

    이벤트 구간(급락)은 빼고 적합한다. 넣으면 기울기가 그쪽으로 끌려가
    정상 상태를 설명하지 못한다. 실제 운영에서도 같은 이유로 excluded
    이벤트 구간을 학습에서 제외한다.

    정규방정식을 직접 푼다. numpy를 쓰지 않는 이유는 3×3이라 손으로 푸는
    편이 의존성 없이 간단하기 때문이다.
    """
    pts = []
    for r in rows:
        g = r.get("gas_resistance")
        if not g or g <= 0:
            continue
        pts.append((r["temperature"], r["humidity"], math.log10(g)))

    if len(pts) < 100:
        return None

    # 1차로 적합한 뒤 잔차가 큰 점(이벤트)을 빼고 다시 적합한다.
    def solve(sample):
        n = len(sample)
        sx = sy = sz = sxx = syy = sxy = sxz = syz = 0.0
        for x, y, z in sample:
            sx += x; sy += y; sz += z
            sxx += x * x; syy += y * y; sxy += x * y
            sxz += x * z; syz += y * z

        # [n sx sy; sx sxx sxy; sy sxy syy] [a b c]^T = [sz sxz syz]^T
        m = [[n, sx, sy], [sx, sxx, sxy], [sy, sxy, syy]]
        v = [sz, sxz, syz]

        # 가우스 소거
        for i in range(3):
            piv = m[i][i]
            if abs(piv) < 1e-12:
                return None
            for j in range(i + 1, 3):
                f = m[j][i] / piv
                for k in range(i, 3):
                    m[j][k] -= f * m[i][k]
                v[j] -= f * v[i]
        out = [0.0, 0.0, 0.0]
        for i in (2, 1, 0):
            s = v[i] - sum(m[i][k] * out[k] for k in range(i + 1, 3))
            out[i] = s / m[i][i]
        return out

    coef = solve(pts)
    if coef is None:
        return None

    a, b, c = coef
    resid = [z - (a + b * x + c * y) for x, y, z in pts]
    sd = math.sqrt(sum(r * r for r in resid) / (len(resid) - 3))

    # 잔차가 3σ를 넘는 점(VOC 구간)을 빼고 재적합
    clean = [p for p, r in zip(pts, resid) if abs(r) <= 3 * sd]
    coef2 = solve(clean) or coef
    a, b, c = coef2
    resid2 = [z - (a + b * x + c * y) for x, y, z in clean]
    sd2 = math.sqrt(sum(r * r for r in resid2) / max(1, len(resid2) - 3))

    return {
        "coef_a": round(a, 6),
        "coef_temp": round(b, 6),
        "coef_humid": round(c, 6),
        "residual_sd": round(sd2, 6),
        "sample_n": len(clean),
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "_excluded": len(pts) - len(clean),
    }


def build_skin(user_id: str, days: int, end: datetime,
               office_dry_days: List[int], rng: random.Random) -> List[Dict[str, Any]]:
    """
    피부 측정 이력.

    격일로 12회 잰 것으로 만든다. 실제로 매일 재는 사람은 드물고,
    화면도 2주 추이를 보여준다.

    건조한 날이 이어진 뒤 홍반(a*)이 오르는 형태로 만든다. 그래야 탭2의
    "환경과의 관계" 문장이 데이터와 맞는다. 반대로 만들면 화면 문구와
    그래프가 어긋나 보는 사람이 먼저 알아챈다.
    """
    out = []
    n = 12
    for i in range(n):
        ts = end - timedelta(days=(n - 1 - i) * 2, hours=rng.uniform(0, 4))
        # 뒤로 갈수록 조금씩 오른다
        a = 10.3 + 0.22 * i + rng.gauss(0, 0.18)
        l = 63.5 - 0.09 * i + rng.gauss(0, 0.25)
        b = 15.2 + 0.05 * i + rng.gauss(0, 0.2)
        out.append({
            "user_id": user_id,
            "ts": ts.isoformat(),
            "lab_l": round(l, 2),
            "lab_a": round(a, 2),
            "lab_b": round(b, 2),
            "gloss": round(rng.uniform(0.28, 0.42), 3),
            "site": "손등 안쪽",
        })
    return out


def build_optical(products: List[Dict[str, Any]], end: datetime,
                  rng: random.Random) -> Dict[str, List[Dict[str, Any]]]:
    """
    광학 기준값과 측정 이력.

    optical_grade가 unsuitable(투명 토너 등)인 제품은 만들지 않는다.
    측정 대상이 아니라고 판정해 놓고 측정값이 있으면 앞뒤가 안 맞는다.
    """
    baselines: List[Dict[str, Any]] = []
    measurements: List[Dict[str, Any]] = []

    for p in products:
        grade = (p.get("optical_grade") or "").lower()
        if grade not in ("suitable", "conditional"):
            continue
        if not p.get("opened_at"):
            continue

        opened = datetime.fromisoformat(str(p["opened_at"])[:10]).replace(tzinfo=timezone.utc)
        base_ts = opened + timedelta(days=1)
        if base_ts >= end:
            continue

        # 8채널 + Clear + NIR. 실제 AS7341 출력 형태를 흉내낸다.
        def channels(scale: float) -> Dict[str, float]:
            base = {"F1": 149, "F2": 762, "F3": 393, "F4": 1315,
                    "F5": 2091, "F6": 1813, "F7": 1283, "F8": 518,
                    "CLEAR": 3804, "NIR": 198}
            # 황변은 단파장(F1~F3)이 먼저 줄어드는 형태로 나타난다
            weight = {"F1": 1.8, "F2": 1.5, "F3": 1.3, "F4": 1.0,
                      "F5": 0.7, "F6": 0.5, "F7": 0.4, "F8": 0.3,
                      "CLEAR": 0.6, "NIR": 0.2}
            return {k: round(v * (1 - scale * weight[k] / 100.0)
                             * (1 + rng.gauss(0, 0.004)), 1)
                    for k, v in base.items()}

        white = {"F1": 4102, "F2": 4230, "F3": 4180, "F4": 4225,
                 "F5": 4260, "F6": 4198, "F7": 4176, "F8": 4133,
                 "CLEAR": 12480, "NIR": 3920}

        baselines.append({
            "user_product_id": p["user_product_id"],
            "ts": base_ts.isoformat(),
            "channels": channels(0.0),
            "white_ref": white,
        })

        # 개봉 후 경과에 비례해 변화가 쌓인다. 2주 간격으로 잰 것으로 둔다.
        step = timedelta(days=14)
        t = base_ts + step
        idx = 1
        while t < end:
            months = (t - opened).days / 30.0
            k = float(p.get("sensitivity_k") or 1.0)
            delta = min(18.0, months * 0.9 * k + rng.gauss(0, 0.3))
            measurements.append({
                "user_product_id": p["user_product_id"],
                "ts": t.isoformat(),
                "channels": channels(delta),
                "white_ref": white,
                "delta_pct": round(delta, 2),
            })
            t += step
            idx += 1

    return {"baselines": baselines, "measurements": measurements}


# ── 쓰기 ─────────────────────────────────────────────────────────

def chunked(rows: List[Dict[str, Any]], size: int = CHUNK):
    for i in range(0, len(rows), size):
        yield rows[i:i + size]


def apply_all(plan: Dict[str, Any]) -> None:
    sb = get_supabase()

    readings = plan["readings"]
    print(f"  sensor_readings {len(readings)}건 …", end="", flush=True)
    for part in chunked(readings):
        # (node_id, ts) 유니크 인덱스가 있으므로 재실행해도 중복되지 않는다.
        sb.table("sensor_readings").upsert(part, on_conflict="node_id,ts").execute()
        print(".", end="", flush=True)
    print(" 완료")

    if plan["events"]:
        sb.table("risk_events").insert(plan["events"]).execute()
        print(f"  risk_events {len(plan['events'])}건 완료")

    if plan["baseline"]:
        row = {k: v for k, v in plan["baseline"].items() if not k.startswith("_")}
        row["node_id"] = plan["gas_node"]
        sb.table("storage_baseline").upsert(row, on_conflict="node_id").execute()
        print("  storage_baseline 완료")

    if plan["skin"]:
        sb.table("skin_measurements").insert(plan["skin"]).execute()
        print(f"  skin_measurements {len(plan['skin'])}건 완료")

    opt = plan["optical"]
    if opt["baselines"]:
        sb.table("optical_baselines").insert(opt["baselines"]).execute()
        print(f"  optical_baselines {len(opt['baselines'])}건 완료")
    if opt["measurements"]:
        sb.table("optical_measurements").insert(opt["measurements"]).execute()
        print(f"  optical_measurements {len(opt['measurements'])}건 완료")


def reset_all(nodes: List[str], user_id: str, since: datetime) -> None:
    """시드 구간을 지운다. 실측을 시작하기 전에 반드시 한 번 돌린다."""
    sb = get_supabase()
    iso = since.isoformat()

    for n in nodes:
        sb.table("sensor_readings").delete().eq("node_id", n).gte("ts", iso).execute()
        sb.table("risk_events").delete().eq("node_id", n).gte("ts", iso).execute()
        sb.table("storage_baseline").delete().eq("node_id", n).execute()
        print(f"  {n} 삭제 완료")

    sb.table("skin_measurements").delete().eq("user_id", user_id).gte("ts", iso).execute()
    print("  skin_measurements 삭제 완료")

    ups = [p["user_product_id"] for p in get_care_products(user_id)]
    for up in ups:
        sb.table("optical_measurements").delete().eq("user_product_id", up).execute()
        sb.table("optical_baselines").delete().eq("user_product_id", up).execute()
    print(f"  광학 데이터 삭제 완료 ({len(ups)}개 제품)")


# ── 진입점 ───────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description="시연용 시계열 데이터 시딩")
    ap.add_argument("--user", default=DEFAULT_USER)
    ap.add_argument("--days", type=int, default=23, help="며칠치를 만들지 (기본 23)")
    ap.add_argument("--seed", type=int, default=42, help="난수 seed. 같으면 같은 결과")
    ap.add_argument("--nodes", default="storage-01,ambient-01,ambient-02")
    ap.add_argument("--reset", action="store_true", help="시드 구간을 삭제한다")
    ap.add_argument("--apply", action="store_true", help="실제 반영 (없으면 계획만)")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    end = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    end -= timedelta(minutes=end.minute % INTERVAL_MIN)
    start = end - timedelta(days=args.days)

    wanted = [n.strip() for n in args.nodes.split(",") if n.strip()]
    known = {n["node_id"] for n in list_nodes()}
    missing = [n for n in wanted if n not in known]
    if missing:
        print(f"iot_nodes에 없는 노드: {', '.join(missing)}")
        print(f"등록된 노드: {', '.join(sorted(known))}")
        return

    print(f"사용자 {args.user}")
    print(f"구간   {start:%Y-%m-%d %H:%M} ~ {end:%Y-%m-%d %H:%M} ({args.days}일)")
    print(f"노드   {', '.join(wanted)}   seed={args.seed}")
    print(f"모드   {'RESET' if args.reset else ('APPLY' if args.apply else 'DRY-RUN')}")

    if args.reset:
        print()
        if not args.apply:
            print("  --apply 를 함께 붙여야 삭제합니다.")
            return
        reset_all(wanted, args.user, start)
        return

    # ── 생성 ─────────────────────────────────────────────────────
    readings: List[Dict[str, Any]] = []
    events: List[Dict[str, Any]] = []
    baseline = None
    gas_node = None

    print()
    print("=" * 78)
    print("① 시계열")
    print("=" * 78)
    print(f"  {'노드':<12}{'건수':>7}{'온도':>18}{'습도':>16}{'가스':>16}")
    print("  " + "-" * 74)

    for node in wanted:
        rows = build_series(node, args.days, end, rng)
        readings.extend(rows)

        temps = [r["temperature"] for r in rows]
        hums = [r["humidity"] for r in rows]
        gases = [r["gas_resistance"] for r in rows if r.get("gas_resistance")]

        gas_txt = (f"{min(gases)/1000:.0f}~{max(gases)/1000:.0f} kΩ" if gases else "—")
        print(f"  {node:<12}{len(rows):>7}"
              f"{min(temps):>9.1f}~{max(temps):<8.1f}"
              f"{min(hums):>7.0f}~{max(hums):<8.0f}"
              f"{gas_txt:>16}")

        ev = detect_events(rows)
        events.extend(ev)

        if gases:
            gas_node = node
            baseline = fit_baseline(rows)

    print()
    print("=" * 78)
    print(f"② 이벤트 — {len(events)}건")
    print("=" * 78)
    for e in events:
        mark = " (제외)" if e["excluded"] else ""
        print(f"  {e['ts'][:16]}  {e['event_type']:<16}"
              f"{e['magnitude']:>7.1f}  {e['user_answer']}{mark}")
    if not events:
        print("  없음 — hot_days나 VOC_SPIKES 설정을 확인하세요.")

    print()
    print("=" * 78)
    print("③ VOC 기준선 회귀")
    print("=" * 78)
    if baseline:
        print(f"  log10(R) = {baseline['coef_a']:.4f} "
              f"{baseline['coef_temp']:+.5f}·T {baseline['coef_humid']:+.5f}·RH")
        print(f"  잔차 표준편차 {baseline['residual_sd']:.5f}  ·  표본 {baseline['sample_n']}건")
        print(f"  이벤트로 제외한 표본 {baseline['_excluded']}건")
        print()
        print(f"  생성에 쓴 계수  a={GAS_A} b={GAS_B_TEMP} c={GAS_C_HUMID}")
        print("  → 회귀가 원래 계수를 되찾으면 계산이 맞는 것입니다.")
    else:
        print("  가스 데이터가 없어 건너뜁니다.")

    products = get_care_products(args.user)
    skin = build_skin(args.user, args.days, end, [], rng)
    optical = build_optical(products, end, rng)

    print()
    print("=" * 78)
    print("④ 피부·광학")
    print("=" * 78)
    print(f"  skin_measurements   {len(skin)}건 "
          f"(a* {skin[0]['lab_a']:.1f} → {skin[-1]['lab_a']:.1f})")
    print(f"  optical_baselines   {len(optical['baselines'])}건")
    print(f"  optical_measurements {len(optical['measurements'])}건")
    for m in optical["measurements"][-3:]:
        print(f"    {m['ts'][:10]}  변화 {m['delta_pct']:.1f}%")
    skipped = [p for p in products
               if (p.get("optical_grade") or "").lower() == "unsuitable"]
    if skipped:
        print(f"  광학 제외 {len(skipped)}개 (unsuitable — 측정 대상 아님)")

    plan = {
        "readings": readings,
        "events": events,
        "baseline": baseline,
        "gas_node": gas_node,
        "skin": skin,
        "optical": optical,
    }

    total = (len(readings) + len(events) + len(skin)
             + len(optical["baselines"]) + len(optical["measurements"])
             + (1 if baseline else 0))

    print()
    if not args.apply:
        print("=" * 78)
        print("DRY-RUN — 아무것도 쓰지 않았습니다")
        print("=" * 78)
        print(f"  반영할 행 {total}건")
        print("  실행하려면 --apply 를 붙이세요.")
        return

    print("=" * 78)
    print("적용")
    print("=" * 78)
    apply_all(plan)
    print()
    print("  완료. python -m scripts.inspect_care_data 로 확인하세요.")


if __name__ == "__main__":
    main()