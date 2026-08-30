"""
IoT 노드 수집 API.

ESP32 노드가 Spring을 거치지 않고 직접 호출한다.
따라서 다른 라우터와 달리 /internal이 아닌 /api/iot 아래에 둔다.

인증:
    X-Node-Key 헤더로 공유 비밀키를 검증한다.
    settings.IOT_API_KEY가 비어 있으면 검증을 생략한다 (개발 편의).

엔드포인트:
    GET  /api/iot/ping                         펌웨어 브링업용 연결 확인
    POST /api/iot/readings                     측정값 적재 (단건·버퍼 일괄 공용)
    GET  /api/iot/nodes/{node_id}/session      측정 노드 일감 폴링
    POST /api/iot/sessions/{id}/samples        광학 측정값 전송 (백색 → 시료)

측정 세션:
    환경 노드(storage·ambient)는 시키지 않아도 10분마다 알아서 올린다.
    측정 노드(measure)는 반대다. 사람이 키오스크에서 "측정하기"를 눌러야
    비로소 잴 것이 생기고, 다 재면 그 결과를 기다리는 화면이 있다.
    그 한 번을 가리키는 것이 세션이다(015_create_measure_sessions).

        키오스크  POST /api/care/measure/sessions   → 세션 생성
        노드      GET  /api/iot/nodes/{id}/session  → 일감 발견, 버튼 대기
        노드      POST .../samples  step=white      → 백색 표준판
        노드      POST .../samples  step=sample     → 시료, 여기서 결과 확정
        키오스크  GET  /api/care/measure/sessions/{id} → 결과 표시
"""
from __future__ import annotations

import hmac
import logging

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field, field_validator

from config import settings
from db.iot.writer import (
    get_latest_reading, get_measure_session, get_node,
    get_open_measure_session, get_optical_baseline, insert_optical,
    insert_readings, update_measure_session,
)
from services.iot.optical import delta_pct, missing_channels

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/iot", tags=["iot"])

# NTP 동기화 실패 시 ESP32는 1970년 근처 시각을 붙인다.
# 열이력 적산이 통째로 망가지므로 수집 단계에서 잘라낸다.
_MIN_TS = datetime(2020, 1, 1, tzinfo=timezone.utc)


def _require_synced(v: datetime) -> datetime:
    """시각을 UTC aware로 맞추고, NTP 미동기로 보이면 거부한다."""
    if v.tzinfo is None:
        v = v.replace(tzinfo=timezone.utc)
    if v < _MIN_TS:
        raise ValueError("NTP 미동기 의심 시각. 노드의 시각 동기화를 확인하세요.")
    return v


class Reading(BaseModel):
    ts: datetime = Field(..., description="센서 측정 시각 (ISO8601, NTP 동기 필수)")
    temperature: Optional[float] = Field(None, ge=-40, le=125, description="℃")
    humidity: Optional[float] = Field(None, ge=0, le=100, description="%RH")
    pm25: Optional[float] = Field(None, ge=0, le=1000, description="μg/m³")
    gas_resistance: Optional[float] = Field(None, ge=0, description="Ω")

    @field_validator("ts")
    @classmethod
    def _reject_unsynced_clock(cls, v: datetime) -> datetime:
        return _require_synced(v)


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
def get_latest(
    node_id: str,
    x_node_key: Optional[str] = Header(None, alias="X-Node-Key"),
) -> LatestReading:
    _verify_key(x_node_key)
    if get_node(node_id) is None:
        raise HTTPException(status_code=404, detail=f"미등록 노드입니다: {node_id}")
    latest = get_latest_reading(node_id)
    if latest is None:
        raise HTTPException(status_code=404, detail="아직 수집된 데이터가 없습니다")
    return latest

# ── 측정 세션 (측정 노드) ──────────────────────────────────────────

# 세션 상태 → 노드가 지금 재야 할 것.
_STEP_OF = {"waiting_white": "white", "waiting_sample": "sample"}


class NodeSession(BaseModel):
    """노드가 폴링으로 받아 가는 일감. 없으면 status=idle."""
    session_id: Optional[str] = None
    status: str = Field(..., description="idle | waiting_white | waiting_sample")
    step: Optional[str] = Field(None, description="white | sample")
    target: Optional[str] = Field(None, description="product | skin")
    poll_sec: int = Field(..., description="다음 폴링까지 권장 대기 시간(초)")
    expires_at: Optional[datetime] = None


class OpticalSample(BaseModel):
    """
    노드가 한 번 잰 결과.

    channels는 암전류를 뺀 값이다. 암전류(LED를 끈 상태의 출력)에는 센서
    누설과 새어 들어온 외부광이 섞여 있어, 빼지 않으면 그 몫이 그대로
    시료의 색인 것처럼 계산된다.
    """
    node_id: str = Field(..., min_length=1, max_length=64)
    step: Literal["white", "sample"]
    ts: datetime = Field(..., description="측정 시각 (ISO8601, NTP 동기 필수)")
    channels: Dict[str, float] = Field(
        ..., description="F1~F8 필수. CLEAR·NIR은 진단용으로 함께 보낸다")

    # 포화하면 값이 천장에서 잘린다. 잘린 값끼리 나눈 비는 실제 반사율이
    # 아니므로, 이 건은 결과로 만들지 않고 다시 재게 한다.
    saturated: bool = Field(False, description="ADC 포화 발생 여부")

    # 백색과 시료를 같은 조건에서 재야 나눗셈이 성립한다. 게인이 다르면
    # 두 값의 축척이 달라 반사율이 게인 비만큼 통째로 어긋난다.
    gain: Optional[str] = Field(None, description="예: 64x")
    led_ma: Optional[int] = Field(None, ge=0, le=258, description="LED 전류 mA")
    dark_applied: bool = Field(False, description="암전류 보정 적용 여부")
    fw: Optional[str] = Field(None, max_length=32, description="펌웨어 식별자")

    @field_validator("ts")
    @classmethod
    def _reject_unsynced_clock(cls, v: datetime) -> datetime:
        return _require_synced(v)


class SampleAck(BaseModel):
    session_id: str
    status: str
    next_step: Optional[str] = Field(None, description="다음에 재야 할 것")
    message: str


@router.get(
    "/nodes/{node_id}/session",
    response_model=NodeSession,
    summary="측정 노드 일감 폴링",
    description=(
        "측정 노드가 짧은 간격으로 호출한다. 키오스크가 연 세션이 있으면 "
        "그 세션과 지금 재야 할 단계를 돌려주고, 없으면 status=idle이다. "
        "노드는 일감이 있을 때만 버튼 입력을 받는다."
    ),
)
def get_node_session(
    node_id: str,
    x_node_key: Optional[str] = Header(None, alias="X-Node-Key"),
) -> NodeSession:
    _verify_key(x_node_key)

    node = get_node(node_id)
    if node is None:
        raise HTTPException(status_code=404, detail=f"미등록 노드입니다: {node_id}")
    if node["node_type"] != "measure":
        raise HTTPException(
            status_code=400,
            detail=f"측정 노드가 아닙니다: {node_id} (node_type={node['node_type']})",
        )

    try:
        session = get_open_measure_session(node_id)
    except Exception:
        logger.exception("세션 조회 실패 node_id=%s", node_id)
        raise HTTPException(status_code=500, detail="세션을 조회하지 못했습니다")

    if session is None:
        return NodeSession(status="idle", poll_sec=settings.MEASURE_POLL_SEC)

    return NodeSession(
        session_id=str(session["id"]),
        status=session["status"],
        step=_STEP_OF.get(session["status"]),
        target=session.get("target"),
        poll_sec=settings.MEASURE_POLL_SEC,
        expires_at=session.get("expires_at"),
    )


def _fail(session_id: str, message: str) -> SampleAck:
    """
    세션을 실패로 닫는다.

    측정을 중간에 버리는 경우는 전부 여기를 지난다. 실패한 채로 열어 두면
    노드가 계속 그 세션을 붙들고, 키오스크는 영영 결과를 기다린다.
    """
    update_measure_session(session_id, {"status": "failed", "message": message})
    return SampleAck(
        session_id=session_id, status="failed", next_step=None, message=message)


def _finalize(session: Dict[str, Any], sample: OpticalSample) -> SampleAck:
    """
    시료까지 도착했다. 여기서 한 번의 측정이 완성된다.

    화장품이면 기준값과 비교해 optical_measurements에 기록한다. 첫 측정은
    비교 대상이 없어 그 자체가 기준값이 되고, delta는 남기지 않는다.
    """
    session_id = str(session["id"])
    white = session.get("white_ref") or {}
    channels = sample.channels

    if session.get("target") != "product" or not session.get("user_product_id"):
        # 피부 측정. 채널만 남기고 세션을 닫는다.
        # AS7341 채널을 CIE Lab으로 바꾸는 변환과 skin_measurements 적재는
        # 이슈 #3에서 services/iot/skin_color.py로 들어온다.
        update_measure_session(session_id, {
            "channels": channels,
            "status": "done",
            "message": "측정을 마쳤습니다.",
        })
        return SampleAck(session_id=session_id, status="done", next_step=None,
                         message="측정을 마쳤습니다.")

    upid = str(session["user_product_id"])
    now = sample.ts.isoformat()

    base = get_optical_baseline(upid)
    delta = None
    if base:
        delta = delta_pct(base.get("channels") or {}, base.get("white_ref"),
                          channels, white)

    insert_optical(upid, channels, white or None, delta, now)

    if not base:
        message = "첫 색을 기록했습니다. 다음 측정부터 이 값과 비교합니다."
    elif delta is None:
        message = "비교할 채널이 부족해 변화율을 내지 못했습니다."
    else:
        message = f"처음 잰 색과 {delta:.1f}% 다릅니다."

    update_measure_session(session_id, {
        "channels": channels,
        "status": "done",
        "baseline": base is None,
        "delta_pct": delta,
        "message": message,
    })
    return SampleAck(session_id=session_id, status="done", next_step=None,
                     message=message)


@router.post(
    "/sessions/{session_id}/samples",
    response_model=SampleAck,
    summary="광학 측정값 전송",
    description=(
        "측정 노드가 버튼을 누를 때마다 한 번 호출한다. step=white(백색 "
        "표준판) → step=sample(시료) 순서로 두 번 올려야 한 건의 측정이 "
        "완성된다. 순서가 어긋나면 409로 거부한다."
    ),
)
def post_optical_sample(
    session_id: str,
    body: OpticalSample,
    x_node_key: Optional[str] = Header(None, alias="X-Node-Key"),
) -> SampleAck:
    _verify_key(x_node_key)

    try:
        session = get_measure_session(session_id)
    except Exception:
        logger.exception("세션 조회 실패 session_id=%s", session_id)
        raise HTTPException(status_code=500, detail="세션을 조회하지 못했습니다")

    if session is None:
        raise HTTPException(status_code=404, detail="없는 측정 세션입니다")

    # 노드를 함께 확인한다. 노드가 둘 이상 붙었을 때 남의 세션에
    # 값을 넣으면, 화면에는 정상 결과처럼 보이는 다른 기기의 측정이 남는다.
    if str(session["node_id"]) != body.node_id:
        raise HTTPException(
            status_code=403,
            detail=f"이 세션의 노드가 아닙니다 (세션={session['node_id']})",
        )

    if session["status"] not in _STEP_OF:
        raise HTTPException(
            status_code=409,
            detail=f"이미 닫힌 세션입니다 (status={session['status']})",
        )

    expected = _STEP_OF[session["status"]]
    if body.step != expected:
        raise HTTPException(
            status_code=409,
            detail=f"지금 필요한 것은 {expected}입니다 (받은 값: {body.step})",
        )

    if body.saturated:
        return _fail(session_id,
                     "빛이 너무 밝아 값이 잘렸습니다. 게인을 낮추고 다시 재 주세요.")

    lost = missing_channels(body.channels)
    if lost:
        return _fail(session_id, f"채널이 빠졌습니다: {', '.join(lost)}")

    meta = {
        "gain": body.gain,
        "led_ma": body.led_ma,
        "dark_applied": body.dark_applied,
        "fw": body.fw,
    }

    try:
        if body.step == "white":
            update_measure_session(session_id, {
                "white_ref": body.channels,
                "meta": meta,
                "status": "waiting_sample",
            })
            return SampleAck(
                session_id=session_id, status="waiting_sample",
                next_step="sample",
                message="백색 기준을 잡았습니다. 이제 시료를 올려 주세요.",
            )

        # 시료. 백색과 같은 조건에서 잰 것이어야 나눗셈이 성립한다.
        prev = session.get("meta") or {}
        if (prev.get("gain"), prev.get("led_ma")) != (body.gain, body.led_ma):
            return _fail(
                session_id,
                "백색 기준과 시료의 측정 조건이 달라 비교할 수 없습니다. "
                "다시 재 주세요.",
            )
        return _finalize(session, body)
    except Exception:
        logger.exception("측정값 처리 실패 session_id=%s step=%s",
                         session_id, body.step)
        raise HTTPException(status_code=500, detail="측정값을 기록하지 못했습니다")
