"""
IoT 센서 조회 DB 레이어.

writer.py가 ESP32의 쓰기를 담당하는 것과 짝을 이루어,
연산 계층(services/iot/*)이 필요로 하는 읽기를 담당한다.

PostgREST는 한 번에 최대 1000행을 준다. 10분 주기면 하루 144행이므로
일주일치까지는 단일 호출로 들어오지만, 개봉 후 3개월치를 뽑으면
약 13,000행이 되어 잘린다. 따라서 range로 페이지를 넘겨 전부 가져온다.
조용히 잘린 데이터로 열이력을 적산하면 실제보다 짧게 나온다.
"""
from __future__ import annotations

import logging

from datetime import datetime
from typing import Any, Dict, List, Optional

from db.supabase_client import get_supabase

logger = logging.getLogger(__name__)

# PostgREST 기본 상한. 한 페이지 크기.
_PAGE = 1000

# 안전장치. 이보다 많이 필요하면 집계 쿼리를 따로 만들어야 한다는 신호다.
_MAX_ROWS = 60_000


def _iso(v: Any) -> Optional[str]:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.isoformat()
    return str(v)


def get_readings(
    node_id: str,
    *,
    since: Optional[datetime | str] = None,
    until: Optional[datetime | str] = None,
    columns: str = "ts, temperature, humidity, pm25, gas_resistance",
) -> List[Dict[str, Any]]:
    """
    노드의 측정값을 ts 오름차순으로 전부 가져온다.

    since / until 은 tz-aware datetime 또는 ISO8601 문자열.
    since를 생략하면 전체 기간이므로, 열이력 계산 시에는 반드시
    개봉일(opened_at)을 넘겨야 한다.
    """
    sb = get_supabase()
    out: List[Dict[str, Any]] = []
    offset = 0

    while True:
        q = (
            sb.table("sensor_readings")
            .select(columns)
            .eq("node_id", node_id)
            .order("ts", desc=False)
            .range(offset, offset + _PAGE - 1)
        )
        if since is not None:
            q = q.gte("ts", _iso(since))
        if until is not None:
            q = q.lte("ts", _iso(until))

        rows = q.execute().data or []
        out.extend(rows)

        if len(rows) < _PAGE:
            break

        offset += _PAGE
        if offset >= _MAX_ROWS:
            logger.warning(
                "get_readings 상한 도달 node_id=%s rows=%d — 구간을 좁히거나 집계로 전환할 것",
                node_id, len(out),
            )
            break

    return out


def get_reading_span(node_id: str) -> Optional[Dict[str, Any]]:
    """
    노드의 수집 구간 요약. 데이터가 얼마나 쌓였는지 빠르게 확인하는 용도.
    전체를 끌어오지 않고 양 끝 한 행씩만 읽는다.
    """
    sb = get_supabase()

    first = (
        sb.table("sensor_readings").select("ts")
        .eq("node_id", node_id).order("ts", desc=False).limit(1).execute()
    ).data
    if not first:
        return None

    last = (
        sb.table("sensor_readings").select("ts")
        .eq("node_id", node_id).order("ts", desc=True).limit(1).execute()
    ).data

    count = (
        sb.table("sensor_readings").select("id", count="exact")
        .eq("node_id", node_id).limit(1).execute()
    ).count

    return {
        "node_id": node_id,
        "first_ts": first[0]["ts"],
        "last_ts": last[0]["ts"] if last else None,
        "count": count,
    }


def list_nodes() -> List[Dict[str, Any]]:
    """등록된 노드 전체. 스크립트·대시보드용."""
    sb = get_supabase()
    res = (
        sb.table("iot_nodes")
        .select("node_id, user_id, node_type, location_label, installed_at")
        .order("node_id")
        .execute()
    )
    return res.data or []