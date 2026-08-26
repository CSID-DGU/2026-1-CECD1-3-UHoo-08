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

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from db.iot.reader import get_reading_span, list_nodes
from db.iot.writer import get_latest_reading
from services.iot.erl import T_REF_C, acceleration_factor
from services.iot.humidity import DRY_THRESHOLD_GM3, absolute_humidity, is_dry
from services.iot.priority import build_priority

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/care", tags=["care"])

# 이 시간 동안 측정이 없으면 오프라인으로 본다.
# 펌웨어 전송 주기가 10분이므로 3회 연속 실패에 해당한다.
DEFAULT_STALE_MINUTES = 30


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