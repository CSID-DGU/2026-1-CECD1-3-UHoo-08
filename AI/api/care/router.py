"""
키오스크 조회 API.

키오스크가 Spring을 거치지 않고 직접 호출한다.
따라서 iot_router와 마찬가지로 /internal이 아닌 /api/care 아래에 둔다.

엔드포인트:
    GET /api/care/priority?user_id=&limit=     점검 우선순위 (탭1)
    GET /api/care/dashboard?user_id=           노드별 현재 환경 (대기 화면·탭4)
"""
from __future__ import annotations

import logging

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from db.iot.reader import get_readings, get_reading_span, list_nodes
from db.iot.skin_reader import get_skin_measurements
from db.iot.writer import get_latest_reading
from services.iot.care_rules import build_brief, compare_indoor
from services.iot.erl import T_REF_C, acceleration_factor
from services.iot.humidity import DRY_THRESHOLD_GM3, absolute_humidity, is_dry
from services.iot.priority import build_priority
from services.iot.psri import compute_psri, relation_sentence
from services.iot.recommend_rules import build_candidates, context_line, pick_products
from services.iot.weather import DEFAULT_REGION, fetch_outdoor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/care", tags=["care"])

# 이 시간 동안 측정이 없으면 오프라인으로 본다.
# 펌웨어 전송 주기가 10분이므로 3회 연속 실패에 해당한다.
DEFAULT_STALE_MINUTES = 30

# PSRI 적분 구간. 이보다 넓게 읽어도 psri가 알아서 자른다.
SKIN_WINDOW_HOURS = 24

# 피부 추이에 보여줄 측정 횟수. 화면이 2주 추이를 그린다.
SKIN_TREND_N = 14


# ── 응답 모델 ─────────────────────────────────────────────────────

class MissingInfo(BaseModel):
    field: str
    title: str
    action: str


class SkippedProduct(BaseModel):
    user_product_id: str
    product_id: Optional[str] = None
    name: Optional[str] = None
    brand: Optional[str] = None
    category: Optional[str] = None
    missing: List[MissingInfo]


class PriorityItem(BaseModel):
    user_product_id: str
    product_id: Optional[str] = None
    name: Optional[str] = None
    brand: Optional[str] = None
    category: Optional[str] = None
    storage_node_id: Optional[str] = None
    opened_at: Optional[str] = None
    last_checked_at: Optional[str] = None
    score: float
    band: str = Field(..., description="high | medium | low")
    reasons: List[str]
    # 근거 수치. 항목이 늘어날 수 있어 자유 dict로 둔다.
    detail: Dict[str, Any]


class PrioritySummary(BaseModel):
    total: int
    scored: int
    unscored: int
    high: int
    medium: int
    low: int
    needs_check: int
    band_thresholds: Dict[str, float]


class NodeUsage(BaseModel):
    node_id: str
    readings: int
    first_ts: Optional[str] = None
    last_ts: Optional[str] = None


class PriorityResponse(BaseModel):
    user_id: str
    generated_at: str
    summary: PrioritySummary
    items: List[PriorityItem]
    skipped: List[SkippedProduct]
    nodes_used: List[NodeUsage]


class NodeStatus(BaseModel):
    node_id: str
    node_type: Optional[str] = None
    location_label: Optional[str] = None
    online: bool
    last_ts: Optional[str] = None
    minutes_since: Optional[float] = None
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    pm25: Optional[float] = None
    absolute_humidity: Optional[float] = Field(None, description="g/m³")
    dry: Optional[bool] = None
    aging_factor: Optional[float] = Field(
        None, description="20℃ 보관 대비 노화 속도 배율"
    )
    aging_text: Optional[str] = None
    readings_total: Optional[int] = None
    first_ts: Optional[str] = None
    days_collected: Optional[float] = None


class DashboardResponse(BaseModel):
    generated_at: str
    reference_temp_c: float
    stale_minutes: int
    dry_threshold_gm3: float
    nodes: List[NodeStatus]
    totals: Dict[str, Any]


# ── 점검 우선순위 ─────────────────────────────────────────────────

@router.get(
    "/priority",
    response_model=PriorityResponse,
    summary="점검 우선순위 목록",
    description=(
        "보유 제품을 점검 우선순위 순으로 정렬해 돌려준다. "
        "limit은 표시 개수만 자르며 요약 수치는 전체 기준이다. "
        "개봉일·보관 위치·제품 정보가 없어 점수를 낼 수 없는 제품은 "
        "목록에서 빼지 않고 skipped로 분리해 무엇이 필요한지 함께 알린다. "
        "이 점수는 변질 판정이 아니라 확인 순서를 정하는 값이다."
    ),
)
def get_priority(
    user_id: str = Query(..., description="예선 한정. 본선에서는 토큰에서 추출한다."),
    limit: Optional[int] = Query(None, ge=1, le=50, description="표시 개수 상한"),
    include_components: bool = Query(False, description="항목별 기여도 포함 (디버깅용)"),
) -> PriorityResponse:
    try:
        result = build_priority(
            user_id, limit=limit, include_components=include_components
        )
    except Exception:
        logger.exception("점검 우선순위 계산 실패 user_id=%s", user_id)
        raise HTTPException(status_code=500, detail="점검 우선순위를 계산하지 못했습니다")

    return PriorityResponse(**result)


# ── 환경 대시보드 ─────────────────────────────────────────────────

def _aging_text(af: Optional[float]) -> Optional[str]:
    """
    가속 배율을 사람이 읽는 문장으로.

    "26.8℃ / 52%"만 보여주면 그게 좋은지 나쁜지 알 수 없다.
    Q10 모델의 기준 온도(20℃)와 비교해 "시간이 몇 배로 흐르는가"로
    바꾸면 비전공 심사위원도 바로 이해한다.

    단정하지 않는 표현을 쓴다. 이 배율은 화학적 노화 속도의 모델값이지
    제품이 상했다는 뜻이 아니다.
    """
    if af is None:
        return None
    if af < 0.95:
        return f"20℃ 보관보다 느리게 시간이 흐릅니다 ({af:.1f}배)"
    if af < 1.05:
        return f"20℃ 보관과 비슷한 속도입니다 ({af:.1f}배)"
    return f"20℃ 보관보다 약 {af:.1f}배 빠르게 시간이 흐릅니다"


@router.get(
    "/dashboard",
    response_model=DashboardResponse,
    summary="노드별 현재 환경",
    description=(
        "각 노드의 최신 측정값과 누적 수집량. 온습도 숫자만으로는 의미가 "
        "전달되지 않으므로 절대습도와 노화 가속 배율(20℃ 기준)을 함께 준다. "
        f"최근 {DEFAULT_STALE_MINUTES}분간 측정이 없는 노드는 오프라인으로 표시한다."
    ),
)
def get_dashboard(
    user_id: Optional[str] = Query(None, description="지정하면 해당 사용자의 노드만"),
    stale_minutes: int = Query(
        DEFAULT_STALE_MINUTES, ge=1, le=1440, description="오프라인 판정 기준(분)"
    ),
) -> DashboardResponse:
    now = datetime.now(timezone.utc)

    try:
        nodes = list_nodes()
    except Exception:
        logger.exception("노드 목록 조회 실패")
        raise HTTPException(status_code=500, detail="노드 정보를 불러오지 못했습니다")

    if user_id:
        nodes = [n for n in nodes if n.get("user_id") == user_id]

    out: List[NodeStatus] = []
    total_readings = 0
    online_count = 0

    for n in nodes:
        node_id = n["node_id"]

        # 노드 하나가 실패해도 대시보드 전체가 죽지 않게 한다.
        # 키오스크는 대기 화면에서 이걸 계속 부르므로, 부분 실패는
        # 그 카드만 비우고 나머지를 보여주는 편이 낫다.
        try:
            latest = get_latest_reading(node_id)
            span = get_reading_span(node_id)
        except Exception:
            logger.exception("노드 조회 실패 node_id=%s", node_id)
            latest, span = None, None

        last_ts = None
        minutes_since = None
        temp = humid = pm25 = None

        if latest:
            raw = latest.get("ts")
            try:
                s = str(raw).replace("Z", "+00:00")
                dt = datetime.fromisoformat(s)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                last_ts = dt.astimezone(timezone.utc)
                minutes_since = (now - last_ts).total_seconds() / 60.0
            except ValueError:
                logger.warning("ts 파싱 실패 node_id=%s ts=%r", node_id, raw)

            temp = latest.get("temperature")
            humid = latest.get("humidity")
            pm25 = latest.get("pm25")

        online = minutes_since is not None and minutes_since <= stale_minutes
        if online:
            online_count += 1

        ah = absolute_humidity(temp, humid)
        af = acceleration_factor(float(temp)) if temp is not None else None

        first_ts = None
        days_collected = None
        if span and span.get("first_ts"):
            try:
                s = str(span["first_ts"]).replace("Z", "+00:00")
                fdt = datetime.fromisoformat(s)
                if fdt.tzinfo is None:
                    fdt = fdt.replace(tzinfo=timezone.utc)
                first_ts = fdt.astimezone(timezone.utc)
                days_collected = round((now - first_ts).total_seconds() / 86400.0, 1)
            except ValueError:
                logger.warning("first_ts 파싱 실패 node_id=%s", node_id)

        count = (span or {}).get("count") or 0
        total_readings += count

        out.append(NodeStatus(
            node_id=node_id,
            node_type=n.get("node_type"),
            location_label=n.get("location_label"),
            online=online,
            last_ts=last_ts.isoformat() if last_ts else None,
            minutes_since=round(minutes_since, 1) if minutes_since is not None else None,
            temperature=temp,
            humidity=humid,
            pm25=pm25,
            absolute_humidity=round(ah, 2) if ah is not None else None,
            dry=is_dry(ah),
            aging_factor=round(af, 2) if af is not None else None,
            aging_text=_aging_text(af),
            readings_total=count,
            first_ts=first_ts.isoformat() if first_ts else None,
            days_collected=days_collected,
        ))

    # 오프라인 노드가 먼저 눈에 띄도록 정렬한다.
    out.sort(key=lambda x: (x.online, x.node_id))

    return DashboardResponse(
        generated_at=now.isoformat(),
        reference_temp_c=T_REF_C,
        stale_minutes=stale_minutes,
        dry_threshold_gm3=DRY_THRESHOLD_GM3,
        nodes=out,
        totals={
            "nodes": len(out),
            "online": online_count,
            "offline": len(out) - online_count,
            "readings": total_readings,
        },
    )

# ── 공통 조립 ─────────────────────────────────────────────────────

def _indoor_nodes(user_id: Optional[str]) -> List[Dict[str, Any]]:
    """
    실내 노드의 현재값.

    환경·피부·추천 세 엔드포인트가 모두 이 형태를 쓴다. 각자 만들면
    한쪽만 고치는 사고가 난다.

    measure(휴대형) 노드는 뺀다. 사람이 손에 들고 다니는 것이라
    "그 공간의 환경"을 대표하지 않는다.
    """
    out: List[Dict[str, Any]] = []

    for n in list_nodes():
        if user_id and n.get("user_id") != user_id:
            continue
        if n.get("node_type") == "measure":
            continue

        node_id = n["node_id"]
        try:
            latest = get_latest_reading(node_id)
        except Exception:
            logger.exception("최신값 조회 실패 node_id=%s", node_id)
            latest = None

        temp = latest.get("temperature") if latest else None
        humid = latest.get("humidity") if latest else None
        pm25 = latest.get("pm25") if latest else None
        ah = absolute_humidity(temp, humid)

        online = False
        if latest and latest.get("ts"):
            try:
                s = str(latest["ts"]).replace("Z", "+00:00")
                dt = datetime.fromisoformat(s)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                age_min = (datetime.now(timezone.utc) - dt).total_seconds() / 60.0
                online = age_min <= DEFAULT_STALE_MINUTES
            except ValueError:
                logger.warning("ts 파싱 실패 node_id=%s", node_id)

        out.append({
            "node_id": node_id,
            "label": n.get("location_label") or node_id,
            "node_type": n.get("node_type"),
            "online": online,
            "temperature": temp,
            "humidity": humid,
            "absolute_humidity": round(ah, 2) if ah is not None else None,
            "pm25": pm25,
        })

    return out


# ── 오늘의 환경 ───────────────────────────────────────────────────

class OutdoorWeather(BaseModel):
    region: str
    observed_at: Optional[str] = None
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    uv_index: Optional[float] = None
    pm10: Optional[float] = None
    pm25: Optional[float] = None
    source: Optional[str] = None


class IndoorNode(BaseModel):
    node_id: str
    label: str
    online: bool
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    absolute_humidity: Optional[float] = None
    pm25: Optional[float] = None


class CareBriefModel(BaseModel):
    headline: str
    lines: List[str]
    rules: List[str]


class EnvironmentResponse(BaseModel):
    generated_at: str
    outdoor: Optional[OutdoorWeather] = None
    indoor: List[IndoorNode]
    brief: CareBriefModel
    comparison: Optional[str] = None


@router.get(
    "/environment",
    response_model=EnvironmentResponse,
    summary="오늘의 환경과 케어 안내",
    description=(
        "실내는 센서 값, 실외는 외부 날씨 API에서 온다. 출처가 다르므로 "
        "source를 함께 준다. 케어 안내는 규칙 테이블이 고른 문장이며 "
        "LLM을 쓰지 않는다. 어떤 규칙이 걸렸는지 rules로 함께 돌려준다."
    ),
)
def get_environment(
    user_id: Optional[str] = Query(None, description="지정하면 해당 사용자의 노드만"),
    region: str = Query(DEFAULT_REGION, description="외출 지역"),
) -> EnvironmentResponse:
    now = datetime.now(timezone.utc)

    try:
        indoor = _indoor_nodes(user_id)
    except Exception:
        logger.exception("실내 노드 조회 실패 user_id=%s", user_id)
        raise HTTPException(status_code=500, detail="실내 환경을 불러오지 못했습니다")

    # 외부 API는 우리가 통제할 수 없다. 실패해도 실내 값은 보여준다.
    outdoor = fetch_outdoor(region)

    brief = build_brief(outdoor, indoor)

    return EnvironmentResponse(
        generated_at=now.isoformat(),
        outdoor=OutdoorWeather(**outdoor) if outdoor else None,
        indoor=[IndoorNode(**{k: v for k, v in n.items() if k != "node_type"})
                for n in indoor],
        brief=CareBriefModel(**brief.as_dict()),
        comparison=compare_indoor(indoor),
    )


# ── 피부 ──────────────────────────────────────────────────────────

class PsriBreakdown(BaseModel):
    score: float
    band: str = Field(..., description="good | caution | check")
    dryness: float
    irritation: float
    personal_weight: float
    personal_label: Optional[str] = None
    window_hours: int


class SkinMeasurementModel(BaseModel):
    measured_at: str
    ita: Optional[float] = None
    ita_class: Optional[str] = None
    erythema: Optional[float] = None
    erythema_delta: Optional[float] = None


class SkinTrendPoint(BaseModel):
    date: str
    erythema: Optional[float] = None
    ita: Optional[float] = None


class SkinResponse(BaseModel):
    generated_at: str
    psri: PsriBreakdown
    relation: Optional[str] = None
    latest: Optional[SkinMeasurementModel] = None
    trend: List[SkinTrendPoint]
    trend_note: Optional[str] = None


def _worst_psri(indoor: List[Dict[str, Any]], now: datetime) -> Dict[str, Any]:
    """
    노드별로 PSRI를 계산해 가장 나쁜 것을 고른다.

    평균을 내지 않는 이유: 침실이 쾌적해도 하루의 절반을 건조한 사무실에서
    보냈다면 피부가 받은 부담은 사무실 쪽이다. 평균을 내면 그게 묻힌다.
    체류 시간을 알면 가중할 수 있지만 지금은 그 정보가 없다.
    """
    since = now - timedelta(hours=SKIN_WINDOW_HOURS)
    best: Optional[Dict[str, Any]] = None

    for n in indoor:
        try:
            rows = get_readings(n["node_id"], since=since)
        except Exception:
            logger.exception("측정값 조회 실패 node_id=%s", n["node_id"])
            continue

        p = compute_psri(rows, now=now)
        if not p.get("computable"):
            continue
        if best is None or p["score"] > best["score"]:
            best = p

    if best is None:
        # 측정이 없으면 0점이 아니라 "계산 불가"다. 다만 화면이 항상
        # 무언가를 그려야 하므로 0으로 채우고 sample_n으로 구분하게 한다.
        return compute_psri([], now=now)
    return best


@router.get(
    "/skin",
    response_model=SkinResponse,
    summary="피부 환경 지수와 측정 추이",
    description=(
        "PSRI는 지난 24시간의 환경(절대습도·초미세먼지)을 적분한 값으로, "
        "피부 상태가 아니라 피부에 작용한 환경을 나타낸다. "
        "ITA°와 홍반 지수는 측정 이력에서 계산하며, 절대값으로 판정하지 않고 "
        "같은 부위의 변화 추이만 보여준다."
    ),
)
def get_skin(
    user_id: str = Query(..., description="예선 한정. 본선에서는 토큰에서 추출한다."),
) -> SkinResponse:
    now = datetime.now(timezone.utc)

    try:
        indoor = _indoor_nodes(user_id)
        psri = _worst_psri(indoor, now)
    except Exception:
        logger.exception("PSRI 계산 실패 user_id=%s", user_id)
        raise HTTPException(status_code=500, detail="피부 환경 지수를 계산하지 못했습니다")

    try:
        rows = get_skin_measurements(user_id, limit=40)
    except Exception:
        logger.exception("피부 측정 조회 실패 user_id=%s", user_id)
        rows = []

    latest_model = None
    trend: List[SkinTrendPoint] = []
    note = None

    if rows:
        # 부위가 다르면 값도 다르다. 최신 측정의 부위로만 추이를 그린다.
        site = rows[0].get("site")
        same = [r for r in rows if r.get("site") == site]

        # 최신순으로 왔으므로 뒤집어 시간순으로 만든다
        asc = list(reversed(same))[-SKIN_TREND_N:]

        cur = same[0]
        prev = same[1] if len(same) > 1 else None
        delta = None
        if prev and cur.get("erythema") is not None and prev.get("erythema") is not None:
            delta = round(float(cur["erythema"]) - float(prev["erythema"]), 2)

        latest_model = SkinMeasurementModel(
            measured_at=str(cur.get("ts")),
            ita=cur.get("ita"),
            ita_class=cur.get("ita_class"),
            erythema=cur.get("erythema"),
            erythema_delta=delta,
        )

        for r in asc:
            try:
                d = datetime.fromisoformat(str(r["ts"]).replace("Z", "+00:00"))
                label = f"{d.month}/{d.day}"
            except (ValueError, KeyError):
                label = "—"
            trend.append(SkinTrendPoint(
                date=label,
                erythema=r.get("erythema"),
                ita=r.get("ita"),
            ))

        note = _trend_note(asc)

    return SkinResponse(
        generated_at=now.isoformat(),
        psri=PsriBreakdown(
            score=psri["score"],
            band=psri["band"],
            dryness=psri["dryness"],
            irritation=psri["irritation"],
            personal_weight=psri["personal_weight"],
            personal_label=psri.get("personal_label"),
            window_hours=psri["window_hours"],
        ),
        relation=relation_sentence(indoor),
        latest=latest_model,
        trend=trend,
        trend_note=note,
    )


def _trend_note(asc: List[Dict[str, Any]]) -> Optional[str]:
    """
    추이를 한 줄로. 앞 절반과 뒤 절반의 평균을 비교한다.

    마지막 두 점만 보면 잡음에 흔들린다. 절반씩 나눠 비교하면 방향이
    안정적으로 잡힌다. 변화가 작으면 굳이 "올랐다"고 말하지 않는다.
    """
    vals = [float(r["erythema"]) for r in asc if r.get("erythema") is not None]
    if len(vals) < 4:
        return None

    half = len(vals) // 2
    first = sum(vals[:half]) / half
    second = sum(vals[half:]) / (len(vals) - half)
    diff = second - first

    if abs(diff) < 0.3:
        return "최근 2주간 큰 변화 없음"
    direction = "상승" if diff > 0 else "하락"
    return f"최근 2주간 {direction} 경향 (평균 {abs(diff):.1f} 차이)"


# ── 추천 ──────────────────────────────────────────────────────────

class RecommendedProduct(BaseModel):
    product_id: str
    name: str
    brand: Optional[str] = None
    image_url: Optional[str] = None
    reason: str


class RecommendationsResponse(BaseModel):
    generated_at: str
    context: Optional[str] = None
    items: List[RecommendedProduct]
    qr_url: str


# 휴대폰에서 이어보는 주소. 키오스크에서 요약을 보고 자세한 것은
# 각자 폰에서 본다. 환경변수로 빼지 않은 이유는 배포 도메인이 하나뿐이고,
# 바뀌면 이 상수만 고치면 되기 때문이다.
APP_URL = "https://2026-1-cecd-1-3-u-hoo-08.vercel.app"


@router.get(
    "/recommendations",
    response_model=RecommendationsResponse,
    summary="환경 기반 제품 추천",
    description=(
        "지금 이 공간의 상태를 근거로 제품을 고른다. 카드마다 어떤 측정값 "
        "때문에 골랐는지를 함께 준다. 조건에 맞는 제품이 DB에 없으면 그 자리를 "
        "비우며, 이유와 맞지 않는 제품으로 채우지 않는다."
    ),
)
def get_recommendations(
    user_id: Optional[str] = Query(None, description="지정하면 해당 사용자의 노드만"),
    region: str = Query(DEFAULT_REGION, description="외출 지역"),
    limit: int = Query(3, ge=1, le=6),
) -> RecommendationsResponse:
    now = datetime.now(timezone.utc)

    try:
        indoor = _indoor_nodes(user_id)
    except Exception:
        logger.exception("실내 노드 조회 실패 user_id=%s", user_id)
        raise HTTPException(status_code=500, detail="추천을 만들지 못했습니다")

    outdoor = fetch_outdoor(region)
    candidates = build_candidates(outdoor, indoor)

    try:
        items = pick_products(candidates, limit=limit)
    except Exception:
        logger.exception("추천 제품 선정 실패")
        items = []

    return RecommendationsResponse(
        generated_at=now.isoformat(),
        context=context_line(outdoor, indoor),
        items=[RecommendedProduct(**i) for i in items],
        qr_url=APP_URL,
    )