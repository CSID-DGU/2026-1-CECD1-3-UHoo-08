"""
IoT 노드 수집 API.

ESP32 노드가 Spring을 거치지 않고 직접 호출한다.
따라서 다른 라우터와 달리 /internal이 아닌 /api/iot 아래에 둔다.

인증:
    X-Node-Key 헤더로 공유 비밀키를 검증한다.
    settings.IOT_API_KEY가 비어 있으면 검증을 생략한다 (개발 편의).

엔드포인트:
    GET  /api/iot/ping             펌웨어 브링업용 연결 확인
    POST /api/iot/readings         측정값 적재 (단건·버퍼 일괄 공용)
"""
import hmac

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field, field_validator

from config import settings
from db.iot_writer import get_latest_reading, get_node, insert_readings

router = APIRouter(prefix="/api/iot", tags=["iot"])

# NTP 동기화 실패 시 ESP32는 1970년 근처 시각을 붙인다.
# 열이력 적산이 통째로 망가지므로 수집 단계에서 잘라낸다.
_MIN_TS = datetime(2020, 1, 1, tzinfo=timezone.utc)


class Reading(BaseModel):
    ts: datetime = Field(..., description="센서 측정 시각 (ISO8601, NTP 동기 필수)")
    temperature: Optional[float] = Field(None, ge=-40, le=125, description="℃")
    humidity: Optional[float] = Field(None, ge=0, le=100, description="%RH")
    pm25: Optional[float] = Field(None, ge=0, le=1000, description="μg/m³")
    gas_resistance: Optional[float] = Field(None, ge=0, description="Ω")

    @field_validator("ts")
    @classmethod
    def _reject_unsynced_clock(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        if v < _MIN_TS:
            raise ValueError("NTP 미동기 의심 시각. 노드의 시각 동기화를 확인하세요.")
        return v


class ReadingsRequest(BaseModel):
    node_id: str = Field(..., min_length=1, max_length=64)
    readings: List[Reading] = Field(..., min_length=1)


class ReadingsResponse(BaseModel):
    node_id: str
    node_type: str
    received: int
    inserted: int
    duplicates: int


class PingResponse(BaseModel):
    status: str
    server_time: datetime


class LatestReading(BaseModel):
    node_id: str
    ts: datetime
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    pm25: Optional[float] = None
    gas_resistance: Optional[float] = None


def _verify_key(node_key: Optional[str]) -> None:
    if not settings.IOT_API_KEY:
        return
    if not node_key or not hmac.compare_digest(node_key, settings.IOT_API_KEY):
        raise HTTPException(status_code=401, detail="유효하지 않은 노드 키")


@router.get(
    "/ping",
    response_model=PingResponse,
    summary="노드 연결 확인",
    description="ESP32 펌웨어 브링업 시 Wi-Fi·HTTPS 경로가 살아 있는지 확인한다.",
)
def ping() -> PingResponse:
    return PingResponse(status="ok", server_time=datetime.now(timezone.utc))


@router.post(
    "/readings",
    response_model=ReadingsResponse,
    summary="센서 측정값 적재",
    description=(
        "ESP32 노드가 10분 주기로 호출한다. readings는 항상 배열이며, "
        "정상 상황에서는 1건, Wi-Fi 복구 후 버퍼 재전송 시에는 다건이 들어온다. "
        "동일 (node_id, ts)는 중복으로 간주해 무시하므로 재전송이 안전하다."
    ),
)
def post_readings(
    body: ReadingsRequest,
    x_node_key: Optional[str] = Header(None, alias="X-Node-Key"),
) -> ReadingsResponse:
    _verify_key(x_node_key)

    if len(body.readings) > settings.IOT_MAX_BATCH:
        raise HTTPException(
            status_code=413,
            detail=f"배치 최대 {settings.IOT_MAX_BATCH}건. 나눠서 전송하세요.",
        )

    node = get_node(body.node_id)
    if node is None:
        raise HTTPException(
            status_code=404,
            detail=f"미등록 노드입니다: {body.node_id}. iot_nodes에 먼저 등록하세요.",
        )

    rows = [
        {
            "node_id": body.node_id,
            "ts": r.ts.isoformat(),
            "temperature": r.temperature,
            "humidity": r.humidity,
            "pm25": r.pm25,
            "gas_resistance": r.gas_resistance,
        }
        for r in body.readings
    ]

    try:
        inserted = insert_readings(rows)
    except Exception as e:
        logger.exception(
            "sensor_readings 적재 실패 node_id=%s count=%d", body.node_id, len(rows)
        )
        raise HTTPException(status_code=500, detail="적재 실패")

    received = len(rows)
    return ReadingsResponse(
        node_id=body.node_id,
        node_type=node["node_type"],
        received=received,
        inserted=inserted,
        duplicates=received - inserted,
    )


@router.get(
    "/nodes/{node_id}/latest",
    response_model=LatestReading,
    summary="노드 최신 측정값",
    description="수집이 살아 있는지 확인하는 용도. 대시보드 연동 전 임시 조회.",
)
def get_latest(node_id: str) -> LatestReading:
    if get_node(node_id) is None:
        raise HTTPException(status_code=404, detail=f"미등록 노드입니다: {node_id}")
    latest = get_latest_reading(node_id)
    if latest is None:
        raise HTTPException(status_code=404, detail="아직 수집된 데이터가 없습니다")
    return latest