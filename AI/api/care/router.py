"""
키오스크 조회 API.

키오스크가 Spring을 거치지 않고 직접 호출한다.
따라서 iot_router와 마찬가지로 /internal이 아닌 /api/care 아래에 둔다.

엔드포인트:
    GET  /api/care/priority?user_id=&limit=            점검 우선순위 (탭1)
    GET  /api/care/dashboard?user_id=                  노드별 현재 환경 (대기 화면·탭4)
    POST /api/care/measure/sessions?user_id=              광학 측정 시작
    POST /api/care/measure/sessions/{id}/capture         시료를 올렸다는 신호
    GET  /api/care/measure/sessions/{id}?user_id=        측정 진행·결과 조회
"""
from __future__ import annotations

import logging

from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from config import settings
from db.iot.reader import (
    get_care_products, get_readings, get_reading_span,
    get_thermal_profiles, list_nodes,
)
from db.iot.event_reader import (
    VALID_ANSWERS, answer_event, close_event_by_inspection, count_pending,
    get_event, get_event_findings, get_latest_feedback, get_risk_events,
)
from db.product_reader import (
    get_product_features, get_product_meta, search_products_by_category,
    search_products_by_name,
)
from db.iot.skin_reader import (
    count_site_measurements, get_skin_measurements, get_site_history, list_sites,
)
from db.iot.writer import (
    OPEN_SESSION_STATUS,
    create_measure_session, discard_user_product, get_latest_reading,
    get_measure_session, get_optical_baseline, insert_optical,
    insert_user_product, update_measure_session, update_user_product,
    upsert_thermal_profile,
)
from services.iot.care_rules import _josa, build_brief, compare_indoor
from services.iot.erl import T_REF_C, acceleration_factor
from services.iot.event_rules import (
    alert_line, describe, guidance, intro_lines, status_line, when,
)
from services.iot.inspection_rules import (
    ANSWERS, FEEDBACK_CODE, answer_guidance, build_protocol,
)
from services.iot.humidity import DRY_THRESHOLD_GM3, absolute_humidity, is_dry
from services.iot.optical import delta_pct, should_measure
from services.iot.priority import (
    FEEDBACK_LABEL, _finding_labels, _missing_reasons, build_priority,
)
from services.iot.psri import compute_psri, relation_sentence
from services.iot.thermal_profile import resolve_row
from services.iot.recommend_rules import (
    build_candidates, build_node_candidates, context_line, pick_products,
    product_blurb, summarize_history,
)
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

# 잴 수 있는 부위. 값이 그대로 skin_measurements.site에 쌓이고, 추이는
# 같은 문자열끼리만 묶인다. 화면이 자유 입력을 받으면 "손등"과 "손등 안쪽"이
# 다른 부위로 갈려 한 사람의 추이가 둘로 나뉜다. 그래서 서버가 목록을 쥔다.
SKIN_SITES = ("손등 안쪽", "볼", "이마", "팔 안쪽")


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


class InspectionRecord(BaseModel):
    """
    사용자가 직접 확인한 결과.

    점수(band)와는 별개다. 점수는 "확인해 볼 순서"이고 이쪽은 "사람이 실제로
    본 것"이다. 화면은 둘을 다른 색으로 그린다.
    """
    ts: Optional[str] = None
    findings: List[str] = Field(default_factory=list, description="발견된 이상 항목")
    clear: bool = Field(False, description="이상 항목 없이 확인을 마쳤는가")


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
    # 확인한 적이 없으면 None. 선언하지 않으면 response_model이 잘라내서
    # 화면까지 도달하지 않는다.
    inspection: Optional[InspectionRecord] = None
    # 근거 수치. 항목이 늘어날 수 있어 자유 dict로 둔다.
    detail: Dict[str, Any]


class PrioritySummary(BaseModel):
    total: int
    scored: int
    unscored: int
    high: int
    medium: int
    low: int
    # 아직 확인하지 않은 고위험 제품 수. high 밴드 개수가 아니다.
    needs_check: int
    # 고위험 중 이미 확인을 마친 수. needs_check와 합하면 high가 된다.
    checked_high: int = 0
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
    # 지금 보고 있는 부위와, 재 본 적 있는 부위 목록.
    # 부위가 다르면 값도 달라서, 어디를 잰 것인지 밝히지 않으면 화면의
    # 숫자가 무엇의 숫자인지 알 수 없다.
    site: Optional[str] = None
    sites: List[str] = []
    # 고를 수 있는 부위 전체. 측정 화면이 이 목록으로 버튼을 만든다.
    site_options: List[str] = []


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
    site: Optional[str] = Query(
        None, description="이 부위만 본다. 비우면 가장 최근에 잰 부위"),
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

    shown_site = None
    same: List[Dict[str, Any]] = []

    if rows:
        # 부위가 다르면 값도 다르다. 고른 부위만, 고르지 않았으면 가장 최근에
        # 잰 부위만 본다. 섞어서 그리면 부위를 옮긴 것이 피부 변화로 보인다.
        shown_site = site or rows[0].get("site")
        same = [r for r in rows if r.get("site") == shown_site]

    if rows and same:
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

    try:
        seen_sites = list_sites(user_id)
    except Exception:
        logger.exception("측정 부위 조회 실패 user_id=%s", user_id)
        seen_sites = []

    return SkinResponse(
        site=shown_site,
        sites=seen_sites,
        site_options=list(SKIN_SITES),
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
    # 앱 목록이 가격을 함께 보여준다. 없으면 그 자리를 비운다.
    price: Optional[int] = None
    reason: str


class RecoGroup(BaseModel):
    """추천 한 묶음. 앱의 '더보기'가 이 단위로 나눠 보여준다."""
    key: str
    title: str = Field(..., description="묶음 제목. 그대로 화면에 쓴다")
    note: Optional[str] = Field(None, description="왜 이 묶음인지 한 줄")
    items: List["RecommendedProduct"]


class FullRecommendationsResponse(BaseModel):
    generated_at: str
    context: Optional[str] = None
    # 섞지 않고 나눠 준다. 섞으면 왜 추천됐는지가 흐려진다.
    groups: List[RecoGroup]


class RecommendationsResponse(BaseModel):
    generated_at: str
    context: Optional[str] = None
    items: List[RecommendedProduct]
    # 이상이 발견된 제품을 대신할 후보를 보여주는 중이면 그 제품 이름.
    # 화면이 "무엇을 대신하는 추천인지" 밝히기 위해 쓴다.
    replacing: Optional[str] = None
    qr_url: str


# 휴대폰에서 이어보는 주소. 키오스크에서 요약을 보고 자세한 것은
# 각자 폰에서 본다. 환경변수로 빼지 않은 이유는 배포 도메인이 하나뿐이고,
# 바뀌면 이 상수만 고치면 되기 때문이다.
APP_URL = "https://2026-1-cecd-1-3-u-hoo-08.vercel.app"


def _replacement_reason(
    meta: Dict[str, Any],
    prof: Optional[Dict[str, Any]],
    feat: Optional[Dict[str, Any]],
    target: Dict[str, Any],
    target_price: Optional[int],
) -> str:
    """
    대체 후보 한 칸에 붙일 이유.

    셋이 같은 문장이면 "왜 하필 이것인가"에 답하지 못한다. 지어내지 않고
    DB에 있는 값만 쓴다.

    순서는 지금 상황에서 중요한 것부터다. 열 때문에 상한 제품을 바꾸는
    자리이므로 열에 덜 민감한지가 먼저고, 그다음이 개봉 후 기한이다.
    그 둘이 없으면 이 제품이 어떤 제품인지(촉촉한지 매트한지)를 말한다.
    브랜드만 말하는 것은 근거가 아니라서 맨 뒤로 뺐다.
    """
    k = (prof or {}).get("sensitivity_k")
    pao = (prof or {}).get("pao_months")
    tk = target.get("sensitivity_k")
    tpao = target.get("pao_months")
    brand = (meta.get("brand") or "").strip()
    price = meta.get("price")
    blurb = product_blurb(feat)

    if k is not None and tk is not None and k < tk:
        head = f"열에 덜 민감한 제형입니다 (민감도 {k} · 쓰시던 것 {tk})"
        return f"{head} · {blurb}" if blurb else head

    if pao is not None and tpao is not None and pao > tpao:
        head = f"개봉 후 {pao}개월까지 쓸 수 있습니다 (쓰시던 것 {tpao}개월)"
        return f"{head} · {blurb}" if blurb else head

    if blurb:
        return blurb

    if price is not None and target_price is not None and price < target_price:
        return f"쓰시던 것보다 {target_price - price:,}원 저렴합니다"

    if brand:
        return f"{brand} 제품입니다"

    return "같은 용도로 쓰실 수 있습니다"


def _replacement_picks(
    user_id: str,
    user_product_id: str,
    limit: int,
) -> tuple[Optional[str], List[Dict[str, Any]]]:
    """
    이상이 발견된 제품을 대신할 후보.

    같은 카테고리에서 고른다. 이름이 아니라 카테고리로 찾는 이유는, "선크림"
    처럼 카테고리 단어가 상품명에 안 들어간 제품을 이름 검색으로는 놓치기
    때문이다.

    확인 결과가 없거나 이상이 없었으면 대체를 권하지 않는다. 사용자가
    "이상 없음"으로 답한 제품을 바꾸라고 할 근거가 없다.
    """
    target = next(
        (p for p in get_care_products(user_id)
         if str(p.get("user_product_id")) == str(user_product_id)),
        None,
    )
    if not target:
        return None, []

    # 이상이 발견된 제품만 대상으로 한다.
    fb = get_latest_feedback([str(user_product_id)]).get(str(user_product_id))
    findings = _finding_labels(fb["answers"]) if fb else []
    if not findings:
        return None, []

    name = target.get("name") or "확인한 제품"
    metas = search_products_by_category(
        target.get("category") or "",
        limit=limit + 3,
        exclude_product_id=target.get("product_id"),
    )
    if not metas:
        return name, []

    found_text = " · ".join(findings)
    # 조사는 앞 글자의 받침에 따라 달라진다. 고정하면 "질감 변화이"처럼 어긋난다.
    # 카드마다 다른 이유를 붙인다. 셋 다 같은 문장이면 고를 근거가 못 된다.
    # 공통 사유(무엇이 확인됐는지)는 목록 위 한 줄이 이미 말하고 있다.
    chosen = metas[:limit]
    ids = [m["id"] for m in chosen]
    profs = get_thermal_profiles(ids)
    feats = get_product_features(ids)
    tmeta = get_product_meta(target.get("product_id") or "") or {}
    target_price = tmeta.get("price")

    picks = [
        {
            "product_id": m["id"],
            "name": m["name"],
            "brand": m.get("brand"),
            "image_url": m.get("image_url"),
            "price": m.get("price"),
            "reason": _replacement_reason(
                m, profs.get(m["id"]), feats.get(m["id"]), target, target_price),
        }
        for m in chosen
    ]
    return name, picks


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
    replace_for: Optional[str] = Query(
        None,
        description=(
            "확인 결과 이상이 발견된 user_product_id. 주면 그 제품과 같은 "
            "카테고리의 대체 후보를 먼저 보여준다."
        ),
    ),
) -> RecommendationsResponse:
    now = datetime.now(timezone.utc)

    # ── 대체 후보 ────────────────────────────────────────────────
    # 점검 화면이 "새 제품으로 바꾸시는 편이 좋겠습니다"라고 안내한 뒤
    # 넘어오는 흐름이다. 그 안내가 빈말이 되지 않으려면 여기서 실제로
    # 그 제품을 대신할 것을 보여줘야 한다.
    replacing: Optional[str] = None
    replacements: List[Dict[str, Any]] = []
    if replace_for and user_id:
        try:
            replacing, replacements = _replacement_picks(user_id, replace_for, limit)
        except Exception:
            logger.exception("대체 제품 조회 실패 user_product_id=%s", replace_for)

    try:
        indoor = _indoor_nodes(user_id)
    except Exception:
        logger.exception("실내 노드 조회 실패 user_id=%s", user_id)
        raise HTTPException(status_code=500, detail="추천을 만들지 못했습니다")

    outdoor = fetch_outdoor(region)
    candidates = build_candidates(outdoor, indoor)

    remaining = max(limit - len(replacements), 0)
    try:
        # 대체 후보로 이미 고른 제품은 환경 추천에서 다시 뽑지 않는다.
        items = pick_products(
            candidates,
            limit=remaining,
            exclude_ids={r["product_id"] for r in replacements},
        ) if remaining else []
    except Exception:
        logger.exception("추천 제품 선정 실패")
        items = []

    return RecommendationsResponse(
        generated_at=now.isoformat(),
        context=context_line(outdoor, indoor),
        items=[RecommendedProduct(**i) for i in replacements + items],
        replacing=replacing,
        qr_url=APP_URL,
    )

@router.get(
    "/recommendations/full",
    response_model=FullRecommendationsResponse,
    summary="추천 전체 (묶음별)",
    description=(
        "키오스크 QR로 넘어온 앱이 쓰는 목록. 왜 추천됐는지가 흐려지지 않도록 "
        "섞지 않고 근거별로 나눠 준다. 확인 결과 이상이 있던 제품의 대체 후보가 "
        "먼저 오고, 그다음이 보관 장소별 환경 추천이다."
    ),
)
def get_recommendations_full(
    user_id: str = Query(..., description="예선 한정. 본선에서는 토큰에서 추출한다."),
    region: str = Query(DEFAULT_REGION, description="외출 지역"),
    per_group: int = Query(3, ge=1, le=6, description="묶음당 제품 수"),
) -> FullRecommendationsResponse:
    now = datetime.now(timezone.utc)
    groups: List[RecoGroup] = []

    # ── 1. 확인 결과 이상이 있던 제품 대신 ───────────────────────
    try:
        pr = build_priority(user_id, include_components=False)
        flagged = [
            i for i in pr["items"]
            if (i.get("inspection") or {}).get("findings")
        ]
    except Exception:
        logger.exception("점검 목록 조회 실패 user_id=%s", user_id)
        flagged = []

    for it in flagged:
        try:
            name, picks = _replacement_picks(
                user_id, it["user_product_id"], per_group)
        except Exception:
            logger.exception("대체 제품 조회 실패 %s", it.get("user_product_id"))
            continue
        if not picks:
            continue
        found = " · ".join(it["inspection"]["findings"])
        groups.append(RecoGroup(
            key=f"replace:{it['user_product_id']}",
            title=f"{name} 대신 쓰실 만한 제품",
            note=f"직접 확인에서 {found}{_josa(found, '이', '가')} 확인됐습니다",
            items=[RecommendedProduct(**p) for p in picks],
        ))

    # ── 2. 보관 장소별 환경 추천 ─────────────────────────────────
    # 노드를 하나씩 따로 넣는다. 한꺼번에 넣으면 어느 장소 때문에 골랐는지
    # 알 수 없어, 사용자가 납득할 근거가 사라진다.
    outdoor = fetch_outdoor(region)
    try:
        indoor = _indoor_nodes(user_id)
    except Exception:
        logger.exception("실내 노드 조회 실패 user_id=%s", user_id)
        indoor = []

    used = {p.product_id for g in groups for p in g.items}
    for node in indoor:
        # 지금 값이 아니라 쌓인 이력으로 고른다. 보관 장소는 몇 주씩 고정해
        # 두고 쓰는 자리라, 오늘 하루가 그 자리를 대표하지 못한다.
        label = node.get("label") or node.get("node_id")
        try:
            hist = summarize_history(get_readings(node["node_id"]))
        except Exception:
            logger.exception("측정 이력 조회 실패 node=%s", node.get("node_id"))
            hist = None

        cands = (build_node_candidates(hist, label) if hist
                 else build_candidates(outdoor, [node]))
        try:
            picks = pick_products(cands, limit=per_group, exclude_ids=set(used))
        except Exception:
            logger.exception("환경 추천 실패 node=%s", node.get("node_id"))
            continue
        if not picks:
            continue
        used |= {p["product_id"] for p in picks}

        groups.append(RecoGroup(
            key=f"node:{node.get('node_id')}",
            title=f"{label} 환경에 맞춘 제품",
            note=_node_note(node, hist),
            items=[RecommendedProduct(**p) for p in picks],
        ))

    return FullRecommendationsResponse(
        generated_at=now.isoformat(),
        context=context_line(outdoor, indoor),
        groups=groups,
    )


def _node_note(node: Dict[str, Any], hist: Optional[Any]) -> Optional[str]:
    """
    묶음 아래 한 줄.

    이력이 있으면 그 요약을 쓴다. 추천 근거가 누적값인데 부제만 지금 온도를
    보여주면 둘이 어긋나 보인다. 이력이 없을 때만 현재값으로 대체한다.
    """
    if hist is not None:
        parts: List[str] = [f"최근 {hist.days}일"]
        if hist.mean_temp is not None:
            parts.append(f"평균 {hist.mean_temp:.1f}℃")
        if hist.max_temp is not None:
            parts.append(f"최고 {hist.max_temp:.1f}℃")
        if hist.mean_ah is not None:
            parts.append(f"절대습도 {hist.mean_ah:.1f} g/m³")
        return " · ".join(parts)

    parts = []
    t = node.get("temperature")
    if t is not None:
        parts.append(f"지금 {t:.1f}℃")
    ah = node.get("absolute_humidity")
    if ah is not None:
        parts.append(f"절대습도 {ah:.1f} g/m³")
    return " · ".join(parts) or None


# ── 보유 제품 등록 ────────────────────────────────────────────────

class ProductSearchItem(BaseModel):
    product_id: str
    name: str
    brand: Optional[str] = None
    category: Optional[str] = None
    image_url: Optional[str] = None
    price: Optional[int] = None


class StorageOption(BaseModel):
    node_id: str
    label: str
    # 화장품은 대개 화장대에 둔다. 매번 고르게 하지 않고 기본으로 잡아두고
    # 다른 곳이면 바꾸게 한다.
    default: bool = False


class RegisterOptions(BaseModel):
    """등록 화면이 고르게 할 선택지."""
    storages: List[StorageOption]


class RegisterProductRequest(BaseModel):
    product_id: str
    # 개봉일은 필수다. 이 값이 없으면 열이력 소모를 계산할 시작점이 없어
    # 점검 순위 자체가 나오지 않는다.
    #
    # 일(day)은 모를 수 있어 "YYYY-MM"도 받는다. 그 경우 월 중간(15일)으로
    # 잡는다. 1일로 잡으면 실제보다 최대 30일 오래된 것으로 계산되고,
    # 말일로 잡으면 그 반대다. 중간이 오차가 가장 작다.
    opened_at: str = Field(..., description="개봉일 YYYY-MM 또는 YYYY-MM-DD")
    storage_node_id: Optional[str] = Field(None, description="보관 위치 노드")

    # 구매일은 받지 않는다. 위험도 계산에 쓰이는 곳이 없어, 물어봐야
    # 사용자 손만 더 가고 화면만 길어진다.


class OpticalGuide(BaseModel):
    """이 제품을 색으로 재는 게 의미 있는지."""
    recommended: bool
    note: str
    has_baseline: bool = False


class RegisterProductResponse(BaseModel):
    user_product_id: Optional[str] = None
    name: Optional[str] = None
    opened_at: Optional[str] = None
    # 일을 모른다고 해서 서버가 월 중간으로 잡았는지. 화면이 이 사실을 밝힌다.
    opened_estimated: bool = False
    # 색 기준값을 재두면 좋은 제품인지. 키오스크에서 안내한다.
    optical: Optional[OpticalGuide] = None
    # 점검 순위에 들어가려면 아직 무엇이 더 필요한지. 등록 직후 바로 알려준다.
    missing: List[MissingInfo]
    message: str


def _normalize_opened(value: str) -> tuple[str, bool]:
    """
    "YYYY-MM" 또는 "YYYY-MM-DD"를 날짜 문자열로 맞춘다.

    일을 모르면 월 중간(15일)으로 잡고 estimated=True를 함께 돌려준다.
    추정했다는 사실을 화면이 숨기지 않도록 하기 위해서다.
    """
    v = (value or "").strip()
    try:
        if len(v) == 7:  # YYYY-MM
            y, m = v.split("-")
            date(int(y), int(m), 15)  # 유효성만 확인
            return f"{int(y):04d}-{int(m):02d}-15", True
        date.fromisoformat(v)
        return v, False
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=400,
            detail="개봉일 형식이 올바르지 않습니다 (YYYY-MM 또는 YYYY-MM-DD)",
        )


@router.get(
    "/products/search",
    response_model=List[ProductSearchItem],
    summary="제품 검색 (등록용)",
    description="보유 제품을 등록할 때 쓰는 이름·브랜드 부분일치 검색.",
)
def search_products_for_register(
    q: str = Query(..., min_length=1, description="제품명 또는 브랜드"),
    limit: int = Query(20, ge=1, le=50),
) -> List[ProductSearchItem]:
    try:
        metas = search_products_by_name(q, limit=limit)
    except Exception:
        logger.exception("제품 검색 실패 q=%s", q)
        raise HTTPException(status_code=500, detail="제품을 찾지 못했습니다")

    return [
        ProductSearchItem(
            product_id=m["id"], name=m["name"], brand=m.get("brand"),
            category=m.get("category"), image_url=m.get("image_url"),
            price=m.get("price"),
        )
        for m in metas
    ]


@router.get(
    "/products/register-options",
    response_model=RegisterOptions,
    summary="등록 화면 선택지",
    description="보관 위치로 고를 수 있는 노드 목록.",
)
def get_register_options(
    user_id: str = Query(..., description="예선 한정. 본선에서는 토큰에서 추출한다."),
) -> RegisterOptions:
    try:
        nodes = _indoor_nodes(user_id)
    except Exception:
        logger.exception("노드 조회 실패 user_id=%s", user_id)
        nodes = []
    # storage 타입 노드(보관함)를 기본으로 잡는다. 없으면 첫 번째.
    default_id = next((n["node_id"] for n in nodes
                       if n.get("node_type") == "storage"), None)
    if default_id is None and nodes:
        default_id = nodes[0]["node_id"]

    return RegisterOptions(storages=[
        StorageOption(
            node_id=n["node_id"],
            label=n.get("label") or n["node_id"],
            default=(n["node_id"] == default_id),
        )
        for n in nodes
    ])


@router.post(
    "/products",
    response_model=RegisterProductResponse,
    summary="보유 제품 등록",
    description=(
        "사용자가 가진 제품을 점검 대상으로 등록한다. 개봉일과 보관 위치는 "
        "선택이지만, 둘이 없으면 점검 순위를 낼 수 없어 응답의 missing으로 "
        "무엇이 더 필요한지 함께 알려준다."
    ),
)
def register_product(
    body: RegisterProductRequest,
    user_id: str = Query(..., description="예선 한정. 본선에서는 토큰에서 추출한다."),
) -> RegisterProductResponse:
    meta = get_product_meta(body.product_id)
    if not meta:
        raise HTTPException(status_code=404, detail="제품을 찾지 못했습니다")

    opened_at, estimated = _normalize_opened(body.opened_at)

    try:
        row = insert_user_product(
            user_id,
            body.product_id,
            opened_at=opened_at,
            storage_node_id=body.storage_node_id,
        )
    except Exception:
        logger.exception("보유 제품 등록 실패 user=%s product=%s",
                         user_id, body.product_id)
        raise HTTPException(status_code=500, detail="등록하지 못했습니다")

    # 열 프로파일이 없으면 여기서 만든다.
    #
    # 이 값(성분 민감도·PAO·광학 등급)은 제품 자체의 성질이라 사용자가 넣을
    # 수 있는 것이 아니다. 그런데 없으면 "제품 정보 미등록"이라고만 뜨고,
    # 사용자는 어디서 넣어야 할지 모른 채 점검 목록에서도 빠진다.
    # 규칙(services/iot/thermal_profile)으로 만들 수 있으므로 등록하는 김에
    # 채운다. 사람이 검수해 넣은 값이 이미 있으면 건드리지 않는다.
    prof = get_thermal_profiles([body.product_id]).get(body.product_id) or {}
    if not prof:
        try:
            upsert_thermal_profile(resolve_row(dict(meta, product_id=body.product_id)))
            prof = get_thermal_profiles([body.product_id]).get(body.product_id) or {}
        except Exception:
            logger.exception("열 프로파일 생성 실패 product=%s", body.product_id)
    missing = _missing_reasons({
        "opened_at": opened_at,
        "storage_node_id": body.storage_node_id,
        "has_profile": bool(prof),
        "pao_months": prof.get("pao_months"),
    })

    if missing:
        message = "등록했습니다. 아래 정보를 더 넣으면 점검 순서에 포함됩니다."
        # missing에는 사용자가 못 채우는 항목이 섞이지 않는다. 등록 시점에
        # 열 프로파일을 만들어 두기 때문이다.
    elif estimated:
        # 추정했다는 사실을 숨기지 않는다. 나중에 정확한 날짜를 알게 되면
        # 보유 화장품 목록에서 고칠 수 있다.
        message = (f"등록했습니다.")
    else:
        message = "등록했습니다. 점검 목록에서 확인하실 수 있습니다."

    upid = str(row.get("id")) if row.get("id") else None
    rec, note = should_measure(prof.get("optical_grade"))
    has_base = bool(get_optical_baseline(upid)) if upid else False

    return RegisterProductResponse(
        user_product_id=upid,
        name=meta.get("name"),
        opened_at=opened_at,
        opened_estimated=estimated,
        optical=OpticalGuide(recommended=rec, note=note, has_baseline=has_base),
        missing=[MissingInfo(**m) for m in missing],
        message=message,
    )


class MyProduct(BaseModel):
    user_product_id: str
    product_id: Optional[str] = None
    name: Optional[str] = None
    brand: Optional[str] = None
    opened_at: Optional[str] = None
    storage_node_id: Optional[str] = None
    storage_label: Optional[str] = None
    # 점검 순위에 들어가려면 아직 무엇이 빠졌는지. 목록에서 바로 보인다.
    missing: List[MissingInfo]


class UpdateProductRequest(BaseModel):
    """수정. 보낸 항목만 바꾼다."""
    opened_at: Optional[str] = Field(None, description="YYYY-MM 또는 YYYY-MM-DD")
    storage_node_id: Optional[str] = Field(None, description="보관 위치 노드")


@router.get(
    "/products/mine",
    response_model=List[MyProduct],
    summary="등록한 보유 제품 목록",
    description=(
        "사용자가 등록한 제품과 그 정보. 무엇이 빠졌는지도 함께 준다. "
        "등록만 해두고 개봉일을 안 넣으면 점검 목록에 안 뜨는데, 그 이유를 "
        "여기서 볼 수 있어야 한다."
    ),
)
def get_my_products(
    user_id: str = Query(..., description="예선 한정. 본선에서는 토큰에서 추출한다."),
) -> List[MyProduct]:
    try:
        products = get_care_products(user_id)
        labels = {n["node_id"]: n.get("label") or n["node_id"]
                  for n in _indoor_nodes(user_id)}
    except Exception:
        logger.exception("보유 제품 조회 실패 user_id=%s", user_id)
        raise HTTPException(status_code=500, detail="목록을 불러오지 못했습니다")

    out: List[MyProduct] = []
    for p in products:
        node_id = p.get("storage_node_id")
        out.append(MyProduct(
            user_product_id=str(p["user_product_id"]),
            product_id=p.get("product_id"),
            name=p.get("name"),
            brand=p.get("brand"),
            opened_at=str(p["opened_at"]) if p.get("opened_at") else None,
            storage_node_id=node_id,
            storage_label=labels.get(node_id) if node_id else None,
            missing=[MissingInfo(**m) for m in _missing_reasons(p)],
        ))
    return out


@router.patch(
    "/products/{user_product_id}",
    response_model=MyProduct,
    summary="등록한 제품 정보 수정",
    description="개봉일과 보관 위치를 고친다. 보낸 항목만 바뀐다.",
)
def update_my_product(
    user_product_id: str,
    body: UpdateProductRequest,
    user_id: str = Query(..., description="예선 한정. 본선에서는 토큰에서 추출한다."),
) -> MyProduct:
    # 남의 제품을 고치지 못하도록 소유부터 확인한다.
    try:
        products = get_care_products(user_id)
    except Exception:
        logger.exception("보유 제품 조회 실패 user_id=%s", user_id)
        raise HTTPException(status_code=500, detail="수정하지 못했습니다")

    target = next((p for p in products
                   if str(p.get("user_product_id")) == str(user_product_id)), None)
    if not target:
        raise HTTPException(status_code=404, detail="등록한 제품이 아닙니다")

    patch: Dict[str, Any] = {}
    if body.opened_at is not None:
        patch["opened_at"], _ = _normalize_opened(body.opened_at)
    if body.storage_node_id is not None:
        # 빈 문자열은 "지정 해제"로 본다.
        patch["storage_node_id"] = body.storage_node_id or None

    if not patch:
        raise HTTPException(status_code=400, detail="바꿀 내용이 없습니다")

    try:
        update_user_product(user_product_id, patch)
        products = get_care_products(user_id)
        labels = {n["node_id"]: n.get("label") or n["node_id"]
                  for n in _indoor_nodes(user_id)}
    except Exception:
        logger.exception("제품 수정 실패 %s", user_product_id)
        raise HTTPException(status_code=500, detail="수정하지 못했습니다")

    p = next((x for x in products
              if str(x.get("user_product_id")) == str(user_product_id)), target)
    node_id = p.get("storage_node_id")
    return MyProduct(
        user_product_id=str(p["user_product_id"]),
        product_id=p.get("product_id"),
        name=p.get("name"),
        brand=p.get("brand"),
        opened_at=str(p["opened_at"]) if p.get("opened_at") else None,
        storage_node_id=node_id,
        storage_label=labels.get(node_id) if node_id else None,
        missing=[MissingInfo(**m) for m in _missing_reasons(p)],
    )


class OpticalRequest(BaseModel):
    channels: Dict[str, float] = Field(..., description="AS7341 F1~F8 등 채널값")
    white_ref: Optional[Dict[str, float]] = Field(
        None, description="흰 기준판 측정값. 조명 차이를 없애는 데 쓴다")


class OpticalResponse(BaseModel):
    baseline: bool = Field(..., description="이번이 기준값 측정이었는지")
    delta_pct: Optional[float] = Field(None, description="기준값 대비 색 변화율")
    message: str


@router.post(
    "/products/{user_product_id}/optical",
    response_model=OpticalResponse,
    summary="색 측정 기록 (AS7341)",
    description=(
        "첫 측정은 기준값이 되고, 이후 측정은 그 기준과 비교한 변화율을 낸다. "
        "변화율만 돌려주며 상했는지 여부는 판정하지 않는다.\n\n"
        "채널값을 이미 손에 쥔 쪽(시드 스크립트·테스트)이 직접 기록할 때 쓴다. "
        "측정 노드로 재는 경로는 POST /api/care/measure/sessions다."
    ),
)
def post_optical(
    user_product_id: str,
    body: OpticalRequest,
    user_id: str = Query(..., description="예선 한정. 본선에서는 토큰에서 추출한다."),
) -> OpticalResponse:
    try:
        products = get_care_products(user_id)
    except Exception:
        logger.exception("보유 제품 조회 실패 user_id=%s", user_id)
        raise HTTPException(status_code=500, detail="기록하지 못했습니다")

    if not any(str(p.get("user_product_id")) == str(user_product_id)
               for p in products):
        raise HTTPException(status_code=404, detail="등록한 제품이 아닙니다")

    now = datetime.now(timezone.utc).isoformat()

    try:
        base = get_optical_baseline(user_product_id)
        delta = None
        if base:
            delta = delta_pct(base.get("channels") or {}, base.get("white_ref"),
                              body.channels, body.white_ref)
        insert_optical(user_product_id, body.channels, body.white_ref, delta, now)
    except Exception:
        logger.exception("색 측정 기록 실패 %s", user_product_id)
        raise HTTPException(status_code=500, detail="기록하지 못했습니다")

    if not base:
        return OpticalResponse(
            baseline=True, delta_pct=None,
            message="첫 색을 기록했습니다. 다음 측정부터 이 값과 비교합니다.",
        )
    if delta is None:
        return OpticalResponse(
            baseline=False, delta_pct=None,
            message="비교할 채널이 부족해 변화율을 내지 못했습니다.",
        )
    return OpticalResponse(
        baseline=False, delta_pct=delta,
        message=f"처음 잰 색과 {delta:.1f}% 다릅니다.",
    )


# ── 측정 세션 (키오스크) ──────────────────────────────────────────
#
# 위의 /optical은 채널값을 이미 손에 쥔 쪽이 부르는 것이다. 키오스크는
# 센서를 읽을 수 없어 그 값을 만들 수 없다. 측정 노드가 대신 재는데,
# 노드에는 화면도 입력도 없어서 "지금 무엇을 재라"를 알려줄 방법이 필요하다.
# 그 약속이 세션이다. 키오스크가 열고, 노드가 채우고, 키오스크가 읽는다.
#
# 흐름과 노드 쪽 엔드포인트는 api/iot/router.py 상단에 정리해 두었다.

# 상태별 화면 문구. done·failed는 세션에 남은 message를 그대로 쓴다.
#
# 시료 단계의 문구는 무엇을 재느냐에 따라 다르다. 피부를 재는데 "제품을
# 올려 주세요"라고 하면 화면 제목과 안내가 서로 다른 말을 하게 된다.
_MEASURE_PROMPT = {
    "waiting_white": "백색 표준판을 측정부에 올린 뒤 측정을 눌러 주세요.",
    "capturing_white": "백색 기준을 재고 있습니다. 그대로 두세요.",
    "expired": "측정 시간이 지났습니다. 다시 시작해 주세요.",
    "cancelled": "측정을 취소했습니다.",
}

_SAMPLE_PROMPT = {
    "product": {
        "waiting_sample": "제품을 측정부에 올린 뒤 측정을 눌러 주세요.",
        "capturing_sample": "제품을 재고 있습니다. 그대로 두세요.",
    },
    "skin": {
        "waiting_sample": "측정부를 피부에 밀착시킨 뒤 측정을 눌러 주세요.",
        "capturing_sample": "피부를 재고 있습니다. 그대로 대고 계세요.",
    },
}

# 화면이 어느 단계를 안내해야 하는지. 누르기 전과 재는 중이 같은 단계다.
_STAGE = {
    "waiting_white": "white", "capturing_white": "white",
    "waiting_sample": "sample", "capturing_sample": "sample",
}

# 사용자가 눌러야 진행되는 상태 → 눌렀을 때 넘어갈 상태.
_ARM = {"waiting_white": "capturing_white",
        "waiting_sample": "capturing_sample"}


class MeasureStartRequest(BaseModel):
    target: Literal["product", "skin"] = "product"
    # 화장품을 잴 때 필수.
    user_product_id: Optional[str] = None
    # 피부를 잴 때 필수. 같은 부위끼리만 비교가 성립한다.
    site: Optional[str] = None
    # 측정 노드가 여러 대일 때만 지정한다. 비우면 사용자의 measure 노드를 쓴다.
    node_id: Optional[str] = None


class MeasureSessionResponse(BaseModel):
    session_id: str
    status: str = Field(
        ..., description="waiting_white | waiting_sample | done | failed | "
                         "expired | cancelled")
    step: Optional[str] = Field(
        None, description="지금 다루는 단계: white | sample")
    # 노드가 재고 있는 중인지. 화면이 버튼을 감추고 기다리게 하는 신호다.
    capturing: bool = False
    # 사용자가 "측정"을 눌러야 다음으로 넘어가는 상태인지.
    awaiting_tap: bool = False
    node_id: str
    node_label: Optional[str] = None
    target: str = "product"
    user_product_id: Optional[str] = None
    site: Optional[str] = None
    # 결과. done일 때만 채워진다.
    baseline: Optional[bool] = Field(
        None, description="이번 측정이 기준값이 되었는지")
    delta_pct: Optional[float] = None
    message: str
    poll_sec: int = Field(..., description="다음 조회까지 권장 대기 시간(초)")
    expires_at: Optional[datetime] = None
    # 피부 측정이 끝났을 때만 채워진다.
    skin: Optional[SkinResult] = None


class SkinResult(BaseModel):
    """
    피부 측정 결과.

    화장품의 delta_pct 자리에 들어가는 것. 화장품은 "처음과 몇 % 다른가"
    하나면 되지만, 피부는 밝기(ITA°)와 붉은기(홍반)가 따로 움직여
    두 값을 함께 봐야 한다.
    """
    site: Optional[str] = None
    lab_l: Optional[float] = None
    lab_a: Optional[float] = None
    lab_b: Optional[float] = None
    ita: Optional[float] = Field(None, description="Individual Typology Angle")
    ita_class: Optional[str] = None
    erythema: Optional[float] = Field(None, description="홍반 지수 (a*)")
    # 같은 부위의 직전 측정과 비교. 첫 측정이면 비어 있다.
    ita_delta: Optional[float] = None
    erythema_delta: Optional[float] = None
    # 이 부위를 몇 번 쟀는지. 1이면 기준선이다.
    measured_n: int = 0


class MeasureStartResponse(MeasureSessionResponse):
    # 시작 화면이 "이번이 첫 측정입니다"를 미리 말할 수 있게 한다.
    # 첫 측정은 비교 대상이 없어 결과 화면이 다르다.
    has_baseline: bool
    # 화장품은 제형의 한계, 피부는 부위 안내. 둘 다 한 줄이라 같은 칸을 쓴다.
    optical_note: str = Field(..., description="이 측정에 대해 미리 알려야 할 한 줄")


def _check_product(user_id: str, user_product_id: Optional[str]) -> str:
    """화장품을 잴 수 있는지. 잴 수 있으면 미리 알려줄 한 줄을 돌려준다."""
    if not user_product_id:
        raise HTTPException(status_code=422, detail="측정할 제품을 지정해 주세요")

    try:
        products = get_care_products(user_id)
    except Exception:
        logger.exception("보유 제품 조회 실패 user_id=%s", user_id)
        raise HTTPException(status_code=500, detail="측정을 시작하지 못했습니다")

    item = next((p for p in products
                 if str(p.get("user_product_id")) == str(user_product_id)), None)
    if item is None:
        raise HTTPException(status_code=404, detail="등록한 제품이 아닙니다")

    # 투명한 제형은 재봐야 조명 잡음만 남는다. 측정을 시켜 놓고 나중에
    # 그 숫자를 근거처럼 보여주는 것이 더 나쁘므로 시작 전에 끊는다.
    recommended, note = should_measure(item.get("optical_grade"))
    if not recommended:
        raise HTTPException(status_code=422, detail=note)
    return note


def _check_skin_site(site: Optional[str]) -> str:
    """
    부위를 확인한다.

    목록 밖의 값을 받지 않는 이유: site는 그대로 DB에 쌓이고, 추이는 같은
    문자열끼리만 묶인다. "손등"과 "손등 안쪽"이 섞이면 한 사람의 추이가
    둘로 갈라져 둘 다 점이 부족해진다.
    """
    if not site:
        raise HTTPException(status_code=422, detail="측정할 부위를 골라 주세요")
    if site not in SKIN_SITES:
        raise HTTPException(
            status_code=422,
            detail=f"고를 수 있는 부위: {', '.join(SKIN_SITES)}",
        )
    return (f"{site}{_josa(site, '을', '를')} 잽니다. "
            f"다음에도 같은 자리를 재야 비교가 됩니다.")


def _measure_node(user_id: str, node_id: Optional[str]) -> Dict[str, Any]:
    """
    측정을 맡길 노드. 없으면 409로 끊는다.

    404가 아니라 409인 이유: 요청한 자원이 없는 것이 아니라 측정할 장비가
    아직 연결되지 않은 상태다. 화면이 "노드를 먼저 연결하세요"라고 말할 수
    있어야 한다.
    """
    try:
        nodes = list_nodes()
    except Exception:
        logger.exception("노드 조회 실패 user_id=%s", user_id)
        raise HTTPException(status_code=500, detail="노드를 조회하지 못했습니다")

    mine = [n for n in nodes
            if n.get("node_type") == "measure" and n.get("user_id") == user_id]

    if node_id:
        found = next((n for n in mine if n["node_id"] == node_id), None)
        if found is None:
            raise HTTPException(
                status_code=404, detail=f"측정 노드가 아닙니다: {node_id}")
        return found

    if not mine:
        raise HTTPException(
            status_code=409,
            detail="연결된 측정 노드가 없습니다. iot_nodes에 measure 노드를 등록하세요.",
        )
    return mine[0]


def _skin_result(user_id: str, site: Optional[str]) -> Optional[SkinResult]:
    """
    방금 잰 피부 측정과 직전 측정의 차이.

    세션 테이블에 넣지 않고 읽을 때 계산한다. ITA°와 홍반 지수는
    skin_measurements의 Lab에서 나오는 파생값이고, 그 계산이 바뀌면
    세션에 굳어 있던 숫자만 옛 식으로 남는다.
    """
    if not site:
        return None
    try:
        rows = get_site_history(user_id, site, limit=2)
    except Exception:
        logger.exception("피부 측정 조회 실패 user=%s site=%s", user_id, site)
        return None
    if not rows:
        return None

    cur = rows[0]
    prev = rows[1] if len(rows) > 1 else None

    def diff(key: str) -> Optional[float]:
        if not prev or cur.get(key) is None or prev.get(key) is None:
            return None
        return round(float(cur[key]) - float(prev[key]), 2)

    try:
        n = count_site_measurements(user_id, site)
    except Exception:
        n = len(rows)

    return SkinResult(
        site=site,
        lab_l=cur.get("lab_l"), lab_a=cur.get("lab_a"), lab_b=cur.get("lab_b"),
        ita=cur.get("ita"), ita_class=cur.get("ita_class"),
        erythema=cur.get("erythema"),
        ita_delta=diff("ita"), erythema_delta=diff("erythema"),
        measured_n=n,
    )


def _session_view(
    session: Dict[str, Any], node_label: Optional[str] = None
) -> MeasureSessionResponse:
    status = session["status"]
    target = session.get("target") or "product"
    message = (
        _MEASURE_PROMPT.get(status)
        or _SAMPLE_PROMPT.get(target, _SAMPLE_PROMPT["product"]).get(status)
        or session.get("message")
        or "측정 중입니다."
    )
    return MeasureSessionResponse(
        session_id=str(session["id"]),
        status=status,
        step=_STAGE.get(status),
        capturing=status.startswith("capturing_"),
        awaiting_tap=status in _ARM,
        node_id=session["node_id"],
        node_label=node_label,
        target=target,
        user_product_id=(str(session["user_product_id"])
                         if session.get("user_product_id") else None),
        site=session.get("site"),
        baseline=session.get("baseline"),
        delta_pct=session.get("delta_pct"),
        message=message,
        poll_sec=settings.MEASURE_POLL_SEC,
        expires_at=session.get("expires_at"),
        skin=(_skin_result(str(session.get("user_id")), session.get("site"))
              if session.get("target") == "skin" and status == "done" else None),
    )


@router.post(
    "/measure/sessions",
    response_model=MeasureStartResponse,
    summary="광학 측정 시작",
    description=(
        "측정 노드에 이 제품을 재라고 알린다. 세션이 열려 있는 동안 노드는 "
        "버튼 입력을 받고, 백색 표준판 → 시료 순서로 두 번 전송한다. "
        "색으로 잴 수 없는 제형이면 열지 않고 그 사유를 돌려준다."
    ),
)
def start_measure_session(
    body: MeasureStartRequest,
    user_id: str = Query(..., description="예선 한정. 본선에서는 토큰에서 추출한다."),
) -> MeasureStartResponse:
    if body.target == "skin":
        note = _check_skin_site(body.site)
    else:
        note = _check_product(user_id, body.user_product_id)

    node = _measure_node(user_id, body.node_id)

    try:
        session = create_measure_session(
            node["node_id"],
            user_id=user_id,
            target=body.target,
            user_product_id=body.user_product_id if body.target == "product" else None,
            site=body.site if body.target == "skin" else None,
            ttl_sec=settings.MEASURE_SESSION_TTL_SEC,
        )
        has_base = (
            count_site_measurements(user_id, body.site or "") > 0
            if body.target == "skin"
            else bool(get_optical_baseline(str(body.user_product_id)))
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception("측정 세션 생성 실패 target=%s", body.target)
        raise HTTPException(status_code=500, detail="측정을 시작하지 못했습니다")

    view = _session_view(session, node.get("location_label"))
    return MeasureStartResponse(
        **view.model_dump(), has_baseline=has_base, optical_note=note)


@router.get(
    "/measure/sessions/{session_id}",
    response_model=MeasureSessionResponse,
    summary="측정 진행·결과 조회",
    description=(
        "키오스크가 측정이 끝날 때까지 짧은 간격으로 부른다. status가 "
        "waiting_*이면 아직 진행 중이고, done이면 결과가 함께 온다. "
        "변화율까지만 말하며 변질 여부는 판정하지 않는다."
    ),
)
def get_measure_session_status(
    session_id: str,
    user_id: str = Query(..., description="예선 한정. 본선에서는 토큰에서 추출한다."),
) -> MeasureSessionResponse:
    try:
        session = get_measure_session(session_id)
    except Exception:
        logger.exception("측정 세션 조회 실패 session_id=%s", session_id)
        raise HTTPException(status_code=500, detail="측정 상태를 확인하지 못했습니다")

    if session is None:
        raise HTTPException(status_code=404, detail="없는 측정 세션입니다")
    if str(session.get("user_id")) != str(user_id):
        raise HTTPException(status_code=404, detail="없는 측정 세션입니다")

    return _session_view(session)


@router.post(
    "/measure/sessions/{session_id}/capture",
    response_model=MeasureSessionResponse,
    summary="측정 지시",
    description=(
        "시료를 올려놓았다는 신호. 이것을 받아야 노드가 잰다.\n\n"
        "노드는 측정부에 무엇이 올라와 있는지 알 수 없다. 그것을 아는 사람은 "
        "방금 손으로 올려놓은 사용자뿐이라, 화면에서 누른 것이 측정 신호가 "
        "된다. 백색 표준판과 제품에 각각 한 번씩, 한 세션에 두 번 부른다."
    ),
)
def capture_measure_session(
    session_id: str,
    user_id: str = Query(..., description="예선 한정. 본선에서는 토큰에서 추출한다."),
) -> MeasureSessionResponse:
    try:
        session = get_measure_session(session_id)
    except Exception:
        logger.exception("측정 세션 조회 실패 session_id=%s", session_id)
        raise HTTPException(status_code=500, detail="측정을 지시하지 못했습니다")

    if session is None or str(session.get("user_id")) != str(user_id):
        raise HTTPException(status_code=404, detail="없는 측정 세션입니다")

    status = session["status"]

    # 이미 재고 있으면 그대로 둔다. 화면을 두 번 눌렀다고 해서 방금 시작한
    # 측정을 취소하거나 두 번 재게 만들 이유가 없다.
    if status.startswith("capturing_"):
        return _session_view(session)

    if status not in _ARM:
        raise HTTPException(
            status_code=409,
            detail=f"측정할 수 있는 상태가 아닙니다 (status={status})",
        )

    try:
        updated = update_measure_session(session_id, {"status": _ARM[status]})
    except Exception:
        logger.exception("측정 지시 실패 session_id=%s", session_id)
        raise HTTPException(status_code=500, detail="측정을 지시하지 못했습니다")

    return _session_view(updated or dict(session, status=_ARM[status]))


@router.delete(
    "/measure/sessions/{session_id}",
    status_code=204,
    summary="측정 취소",
    description=(
        "측정 화면에서 뒤로 나갈 때 부른다. 세션을 닫지 않으면 노드가 "
        "시한이 다 될 때까지 그 세션을 붙들고 있어 다음 측정을 시작할 수 없다."
    ),
)
def cancel_measure_session(
    session_id: str,
    user_id: str = Query(..., description="예선 한정. 본선에서는 토큰에서 추출한다."),
) -> None:
    try:
        session = get_measure_session(session_id)
    except Exception:
        logger.exception("측정 세션 조회 실패 session_id=%s", session_id)
        raise HTTPException(status_code=500, detail="측정을 취소하지 못했습니다")

    if session is None or str(session.get("user_id")) != str(user_id):
        raise HTTPException(status_code=404, detail="없는 측정 세션입니다")

    # 이미 끝난 세션이면 그냥 둔다. 끝난 측정의 결과를 지울 이유가 없다.
    if session["status"] not in OPEN_SESSION_STATUS:
        return

    try:
        update_measure_session(session_id, {
            "status": "cancelled", "message": "측정을 취소했습니다."})
    except Exception:
        logger.exception("측정 세션 취소 실패 session_id=%s", session_id)
        raise HTTPException(status_code=500, detail="측정을 취소하지 못했습니다")


@router.delete(
    "/products/{user_product_id}",
    status_code=204,
    summary="보유 제품 빼기",
    description=(
        "다 썼거나 잘못 등록한 제품을 목록에서 뺀다. 지난 측정·확인 이력은 "
        "남겨 두고 목록에서만 제외한다."
    ),
)
def delete_my_product(
    user_product_id: str,
    user_id: str = Query(..., description="예선 한정. 본선에서는 토큰에서 추출한다."),
) -> None:
    try:
        products = get_care_products(user_id)
    except Exception:
        logger.exception("보유 제품 조회 실패 user_id=%s", user_id)
        raise HTTPException(status_code=500, detail="빼지 못했습니다")

    if not any(str(p.get("user_product_id")) == str(user_product_id)
               for p in products):
        raise HTTPException(status_code=404, detail="등록한 제품이 아닙니다")

    try:
        discard_user_product(user_product_id)
    except Exception:
        logger.exception("보유 제품 제외 실패 %s", user_product_id)
        raise HTTPException(status_code=500, detail="빼지 못했습니다")


# ── 이벤트 이력 ───────────────────────────────────────────────────

class EventItem(BaseModel):
    id: int
    node_id: Optional[str] = None
    node_label: Optional[str] = None
    ts: str
    when: str = Field(..., description="화면에 그대로 쓰는 짧은 시각 표기")
    event_type: str
    magnitude: Optional[float] = None
    title: str
    detail: str
    question: Optional[str] = Field(None, description="답을 받아야 하면 문구, 아니면 null")
    user_answer: str
    excluded: bool
    status: Optional[str] = Field(
        None, description="답한 뒤 목록에 표시할 한 줄. 아직이면 null"
    )


class EventsSummary(BaseModel):
    total: int
    pending: int
    excluded: int
    alert: Optional[str] = Field(None, description="대기 화면 알림 바 문구")


class EventsResponse(BaseModel):
    generated_at: str
    summary: EventsSummary
    """목록 위에 한 번만 두는 설명. 칸마다 반복하지 않는다."""
    intro: List[str]
    items: List[EventItem]


def _node_labels(user_id: Optional[str]) -> Dict[str, str]:
    """node_id → 표시 이름. 없으면 node_id를 그대로 쓴다."""
    out: Dict[str, str] = {}
    for n in list_nodes():
        if user_id and n.get("user_id") != user_id:
            continue
        out[n["node_id"]] = n.get("location_label") or n["node_id"]
    return out


@router.get(
    "/events",
    response_model=EventsResponse,
    summary="이상 이벤트 이력",
    description=(
        "고온 노출과 공기 성분 변화 기록. VOC 급락은 원인을 알고리즘으로 "
        "가릴 수 없어 사용자에게 되묻는다. 아직 답하지 않은 건은 question이 "
        "채워져 오며, 화면은 그것을 질문으로 표시한다. 경고가 아니다."
    ),
)
def get_events(
    user_id: str = Query(..., description="예선 한정. 본선에서는 토큰에서 추출한다."),
    limit: int = Query(30, ge=1, le=100),
    pending_only: bool = Query(False, description="답을 기다리는 건만"),
) -> EventsResponse:
    now = datetime.now(timezone.utc)

    try:
        labels = _node_labels(user_id)
        node_ids = list(labels)
        rows = get_risk_events(node_ids, limit=limit, pending_only=pending_only)
        pending = count_pending(node_ids)
    except Exception:
        logger.exception("이벤트 조회 실패 user_id=%s", user_id)
        raise HTTPException(status_code=500, detail="이벤트 이력을 불러오지 못했습니다")

    # 확인 결과를 FK로 붙인다. 시각으로 추측하던 방식은 이벤트와 무관한
    # 확인까지 섞여 들어왔다.
    try:
        findings = get_event_findings([r["id"] for r in rows])
    except Exception:
        logger.exception("확인 결과 조회 실패")
        findings = {}

    items: List[EventItem] = []
    for r in rows:
        label = labels.get(r.get("node_id"))
        d = describe(r, label)
        # 이미 답한 건은 질문을 다시 띄우지 않는다.
        question = d["question"] if r.get("user_answer") == "pending" else None
        items.append(EventItem(
            status=status_line(r, findings.get(r["id"])),
            id=r["id"],
            node_id=r.get("node_id"),
            node_label=label,
            ts=str(r.get("ts")),
            when=when(r.get("ts")),
            event_type=r.get("event_type") or "unknown",
            magnitude=r.get("magnitude"),
            title=d["title"],
            detail=d["detail"],
            question=question,
            user_answer=r.get("user_answer") or "pending",
            excluded=bool(r.get("excluded")),
        ))

    return EventsResponse(
        generated_at=now.isoformat(),
        intro=intro_lines(),
        summary=EventsSummary(
            total=len(items),
            pending=pending,
            excluded=sum(1 for i in items if i.excluded),
            alert=alert_line(pending),
        ),
        items=items,
    )


# ── 확인 질문에 답하기 ────────────────────────────────────────────

class AnswerRequest(BaseModel):
    answer: str = Field(..., description="external_source | none")
    inspect: bool = Field(
        True,
        description=(
            "none일 때 제품 확인으로 이어갈지. "
            "False면 그 자리에서 답변을 확정하고 제품 목록을 주지 않는다. "
            "확인을 강요하지 않기 위한 것이다."
        ),
    )


class GuidanceProduct(BaseModel):
    user_product_id: str
    name: Optional[str] = None
    brand: Optional[str] = None
    score: float
    band: str


class GuidanceNext(BaseModel):
    action: str
    products: List[GuidanceProduct]


class AnswerResponse(BaseModel):
    event: EventItem
    headline: str
    lines: List[str]
    next: Optional[GuidanceNext] = None


# 답변 후 함께 보여줄 제품 수.
#
# 처음에는 2개만 줬는데, 사용자가 그 둘 중에서만 고를 수 있어 답답했다.
# 화면이 스크롤되는 목록이므로 전부 준다. 정상 범위 제품도 포함한다.
# 사용자가 "저건 왜 없지"라고 생각할 여지를 남기지 않는다.
GUIDANCE_PRODUCT_N = 20


@router.post(
    "/events/{event_id}/answer",
    response_model=AnswerResponse,
    summary="확인 질문에 답하기",
    description=(
        "external_source면 그 기록을 분석에서 제외하고, none이면 유효한 "
        "이벤트로 남긴다. none일 때는 같은 보관함의 확인 순위 상위 제품을 "
        "함께 돌려주어 다음 행동으로 이어지게 한다. "
        "이미 답한 건에 다시 답할 수 있다. 잘못 눌렀을 때 되돌릴 방법이 필요하다."
    ),
)
def post_event_answer(
    event_id: int,
    body: AnswerRequest,
    user_id: str = Query(..., description="예선 한정"),
) -> AnswerResponse:
    if body.answer not in VALID_ANSWERS:
        raise HTTPException(
            status_code=422,
            detail=f"answer는 {' 또는 '.join(VALID_ANSWERS)} 여야 합니다",
        )

    labels = _node_labels(user_id)

    before = get_event(event_id)
    if not before:
        raise HTTPException(status_code=404, detail="이벤트를 찾을 수 없습니다")

    # 남의 이벤트에 답하지 못하게 한다. 예선에는 사용자가 하나뿐이지만,
    # user_id를 쿼리로 받는 구조라 넘겨보면 그대로 통한다.
    if before.get("node_id") not in labels:
        raise HTTPException(status_code=404, detail="이벤트를 찾을 수 없습니다")

    # ── "아니요"를 언제 확정하는가 ───────────────────────────────
    #
    # 제품을 확인하겠다면(inspect=True) 지금은 저장하지 않는다. 확인이
    # 끝나야 무엇이 문제였는지 알 수 있고, 중간에 그만두면 아무것도
    # 확인하지 않았는데 질문만 사라지기 때문이다.
    #
    # 확인하지 않겠다면(inspect=False) 그 자리에서 확정한다. 사용자가
    # 판단을 마친 것이므로 질문을 계속 띄울 이유가 없다.
    if body.answer == "none" and body.inspect:
        updated = dict(before)
    else:
        try:
            updated = answer_event(event_id, body.answer)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        except Exception:
            logger.exception("이벤트 답변 저장 실패 id=%s", event_id)
            raise HTTPException(status_code=500, detail="답변을 저장하지 못했습니다")

        if not updated:
            raise HTTPException(status_code=500, detail="답변 후 이벤트를 읽지 못했습니다")

    # "아니요"이면서 확인을 이어가겠다고 할 때만 제품을 붙인다.
    top: List[Dict[str, Any]] = []
    if body.answer == "none" and body.inspect:
        try:
            pri = build_priority(user_id, limit=GUIDANCE_PRODUCT_N)
            node_id = updated.get("node_id")
            for it in pri["items"]:
                # 같은 보관함의 제품만 보여준다. 다른 방에 있던 제품을
                # 이 이벤트의 후보로 내밀면 근거가 어긋난다.
                if node_id and it.get("storage_node_id") != node_id:
                    continue
                top.append({
                    "user_product_id": it["user_product_id"],
                    "name": it.get("name"),
                    "brand": it.get("brand"),
                    "score": it["score"],
                    "band": it["band"],
                })
        except Exception:
            # 안내에 제품을 못 붙여도 답변 저장은 이미 끝났다.
            logger.exception("안내용 제품 조회 실패 user_id=%s", user_id)

    g = guidance(updated, body.answer, top or None)

    label = labels.get(updated.get("node_id"))
    d = describe(updated, label)

    return AnswerResponse(
        event=EventItem(
            status=status_line(updated),
            id=updated["id"],
            node_id=updated.get("node_id"),
            node_label=label,
            ts=str(updated.get("ts")),
            when=when(updated.get("ts")),
            event_type=updated.get("event_type") or "unknown",
            magnitude=updated.get("magnitude"),
            title=d["title"],
            detail=d["detail"],
            question=None,
            user_answer=updated.get("user_answer") or "pending",
            excluded=bool(updated.get("excluded")),
        ),
        headline=g["headline"],
        lines=g["lines"],
        next=(GuidanceNext(action=g["next"]["action"],
                           products=[GuidanceProduct(**p) for p in g["next"]["products"]])
              if g.get("next") else None),
    )


# ── 확인 절차 ─────────────────────────────────────────────────────
#
# "확인해 보세요"만으로는 사용자가 무엇을 봐야 할지 모른다. 설계서 §5-6은
# 식약처 화장품 안정성시험 가이드라인의 시험항목을 소비자가 확인 가능한
# 형태로 옮긴 표를 정의한다. 그 표를 규칙 테이블로 구현한 것이 여기다.

class CheckStepModel(BaseModel):
    order: int
    basis: str = Field(..., description="가이드라인 시험항목 (성상·색, 냄새 등)")
    text: str
    optical: bool = Field(False, description="AS7341 측정으로 도울 수 있는 항목")


class ProtocolResponse(BaseModel):
    user_product_id: str
    name: Optional[str] = None
    brand: Optional[str] = None
    label: str = Field(..., description="확인 유형 (오일·세럼 등)")
    score: Optional[float] = None
    band: Optional[str] = None
    reasons: List[str] = []
    steps: List[CheckStepModel]
    answers: List[str]
    caution: Optional[str] = None
    note: Optional[str] = None


@router.get(
    "/products/{user_product_id}/protocol",
    response_model=ProtocolResponse,
    summary="제품별 확인 절차",
    description=(
        "무엇을 어떻게 볼지 순서대로 알려준다. 항목은 식약처 화장품 "
        "안정성시험 가이드라인의 시험항목을 소비자가 확인 가능한 형태로 "
        "옮긴 것이며, 카테고리마다 순서가 다르다. "
        "판정하지 않는다. 확인은 사용자가 한다."
    ),
)
def get_protocol(
    user_product_id: str,
    user_id: str = Query(..., description="예선 한정"),
) -> ProtocolResponse:
    try:
        products = get_care_products(user_id)
    except Exception:
        logger.exception("보유 제품 조회 실패 user_id=%s", user_id)
        raise HTTPException(status_code=500, detail="제품 정보를 불러오지 못했습니다")

    item = next((p for p in products if p["user_product_id"] == user_product_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="제품을 찾을 수 없습니다")

    # 개봉 후 몇 달이 지났는지. PAO 초과 여부를 문구에 넣는 데 쓴다.
    opened_months = None
    if item.get("opened_at"):
        try:
            d = datetime.fromisoformat(str(item["opened_at"])[:10]).replace(tzinfo=timezone.utc)
            opened_months = (datetime.now(timezone.utc) - d).days / 30.0
        except ValueError:
            logger.warning("개봉일 파싱 실패 %r", item.get("opened_at"))

    proto = build_protocol(
        item.get("name"),
        item.get("category"),
        item.get("optical_grade"),
        pao_months=item.get("pao_months"),
        opened_months=opened_months,
    )

    # 점수와 근거를 함께 준다. 왜 이 제품을 확인하라는지 화면에 남아야 한다.
    score = band = None
    reasons: List[str] = []
    try:
        pri = build_priority(user_id)
        hit = next((i for i in pri["items"]
                    if i["user_product_id"] == user_product_id), None)
        if hit:
            # 키 하나가 빠졌다고 점수 전체를 잃지 않는다.
            score = hit.get("score")
            band = hit.get("band")
            reasons = hit.get("reasons") or []
    except Exception:
        logger.exception("점검 점수 조회 실패 user_product_id=%s", user_product_id)

    return ProtocolResponse(
        user_product_id=user_product_id,
        name=item.get("name"),
        brand=item.get("brand"),
        label=proto["label"],
        score=score,
        band=band,
        reasons=reasons,
        steps=[CheckStepModel(**s) for s in proto["steps"]],
        answers=proto["answers"],
        caution=proto["caution"],
        note=proto["note"],
    )


class InspectionRequest(BaseModel):
    answers: List[str] = Field(
        ...,
        description="확인한 항목들. 여러 개를 고를 수 있다.",
        min_length=1,
    )
    event_id: Optional[int] = Field(
        None,
        description=(
            "이 확인이 어느 이상 이벤트에서 이어진 것인지. "
            "이벤트 이력에서 들어왔다면 그 id를 보낸다. "
            "채워져 있으면 확인을 마칠 때 그 이벤트를 완료로 바꾼다."
        ),
    )


class GuidanceSection(BaseModel):
    label: str
    lines: List[str]


class InspectionResponse(BaseModel):
    user_product_id: str
    answers: List[str]
    headline: str
    """항목마다 하나씩. 고른 것이 여럿이면 여럿 나온다."""
    sections: List[GuidanceSection]
    lines: List[str]
    recommend_replace: bool = Field(
        False,
        description="교체를 권할 상황인지. 화면이 조용히 덧붙이는 데 쓴다",
    )
    findings: List[str] = Field(
        [],
        description="점검 목록에 표시할 짧은 항목명",
    )


@router.post(
    "/products/{user_product_id}/inspection",
    response_model=InspectionResponse,
    summary="확인 결과 기록",
    description=(
        "사용자가 확인한 항목들을 받는다. 여러 개를 고를 수 있다. "
        "설계서 §5-7의 피드백 루프 입력이며, last_checked_at을 갱신해 "
        "점검 점수의 '마지막 확인' 항목에 반영한다. "
        "여기서도 변질을 판정하지 않는다. 사용자가 확인한 사실을 옮길 뿐이다."
    ),
)
def post_inspection(
    user_product_id: str,
    body: InspectionRequest,
    user_id: str = Query(..., description="예선 한정"),
) -> InspectionResponse:
    unknown = [a for a in body.answers if a not in ANSWERS]
    if unknown:
        raise HTTPException(
            status_code=422,
            detail=f"알 수 없는 항목: {', '.join(unknown)}",
        )

    try:
        products = get_care_products(user_id)
    except Exception:
        logger.exception("보유 제품 조회 실패 user_id=%s", user_id)
        raise HTTPException(status_code=500, detail="제품 정보를 불러오지 못했습니다")

    item = next((p for p in products if p["user_product_id"] == user_product_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="제품을 찾을 수 없습니다")

    proto = build_protocol(item.get("name"), item.get("category"),
                           item.get("optical_grade"))

    # 이 제품의 항목이 아닌 답은 막는다. 화면은 버튼으로만 고르지만
    # 서버가 자기 규칙을 지켜야 한다.
    invalid = [a for a in body.answers if a not in proto["answers"]]
    if invalid:
        raise HTTPException(
            status_code=422,
            detail=(f"이 제품({proto['label']})의 확인 항목이 아닙니다: "
                    f"{', '.join(invalid)}. "
                    f"가능한 답: {', '.join(proto['answers'])}"),
        )

    g = answer_guidance(body.answers, proto["category"])

    # ── 저장 ─────────────────────────────────────────────────────
    # 확인했다는 사실과 무엇을 봤는지를 남긴다. 실패해도 안내는 돌려준다.
    # 사용자는 이미 확인을 마쳤고, 저장 실패는 사용자 문제가 아니다.
    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        from db.supabase_client import get_supabase
        sb = get_supabase()

        (sb.table("user_products")
         .update({"last_checked_at": now_iso})
         .eq("id", user_product_id).execute())

        # 피드백은 항목마다 한 행. 나중에 "변화율 몇 %에서 사람이 알아채는가"를
        # 집계하려면 항목별로 나뉘어 있어야 한다.
        rows = []
        for a in body.answers:
            code = FEEDBACK_CODE.get(a)
            if not code:
                continue
            rows.append({
                "user_product_id": user_product_id,
                "ts": now_iso,
                "risk_score": None,
                "delta_pct": (item.get("optical_delta_pct")
                              if isinstance(item, dict) else None),
                "answer": code,
                # 이벤트에서 이어진 확인이면 그 id를 남긴다. 아니면 NULL.
                "event_id": body.event_id,
            })
        if rows:
            sb.table("user_feedback").insert(rows).execute()
    except Exception:
        logger.exception("확인 결과 저장 실패 %s", user_product_id)

    # 이벤트에서 이어진 확인이면 그 이벤트를 닫는다.
    #
    # "짚이는 외부 요인이 없다"고 답한 뒤 제품을 확인한 흐름의 끝이다.
    # 확인 결과는 user_feedback에 FK로 이어져 있으므로, 목록을 그릴 때
    # 그쪽에서 읽어온다. 여기서 문구를 따로 저장하지 않는다.
    if body.event_id is not None:
        try:
            close_event_by_inspection(body.event_id)
        except Exception:
            logger.exception("이벤트 마감 실패 event_id=%s", body.event_id)

    return InspectionResponse(
        user_product_id=user_product_id,
        answers=body.answers,
        headline=g["headline"],
        sections=[GuidanceSection(**sec) for sec in g["sections"]],
        lines=g["lines"],
        recommend_replace=g["recommend_replace"],
        findings=g["findings"],
    )