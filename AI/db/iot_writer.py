"""
IoT 센서 수집 DB 레이어.

ESP32 노드가 보낸 측정값을 sensor_readings에 적재하고, 노드 메타를 조회한다.
읽기 전용인 product_reader·score_reader와 달리 쓰기를 담당하므로 파일명을 writer로 둔다.

중복 수신 처리:
    ESP32는 Wi-Fi 장애 시 측정값을 로컬 버퍼에 쌓았다가 복구 시점에 재전송한다.
    이때 이미 적재된 구간이 다시 올라올 수 있으므로 (node_id, ts) 유니크 인덱스
    (012_unique_sensor_readings.sql)를 전제로 upsert-ignore를 사용한다.
    같은 요청을 몇 번 보내도 결과가 같다.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict

from db.supabase_client import get_supabase


class NodeRow(TypedDict):
    node_id: str
    user_id: Optional[str]
    node_type: str
    location_label: Optional[str]


def get_node(node_id: str) -> Optional[NodeRow]:
    """단일 노드 메타 조회. 미등록 노드면 None."""
    sb = get_supabase()
    res = (
        sb.table("iot_nodes")
        .select("node_id, user_id, node_type, location_label")
        .eq("node_id", node_id)
        .limit(1)
        .execute()
    )
    if not res.data:
        return None
    row = res.data[0]
    return NodeRow(
        node_id=row["node_id"],
        user_id=row.get("user_id"),
        node_type=row["node_type"],
        location_label=row.get("location_label"),
    )


def insert_readings(rows: List[Dict[str, Any]]) -> int:
    """
    센서 측정값 일괄 적재. 이미 존재하는 (node_id, ts)는 무시한다.

    rows 각 항목은 sensor_readings 컬럼명을 그대로 사용하며,
    ts는 ISO8601 문자열이어야 한다 (PostgREST가 timestamptz로 캐스팅).

    반환값은 실제로 삽입된 행 수. 중복이 걸러지면 요청 건수보다 작다.
    """
    if not rows:
        return 0

    sb = get_supabase()
    res = (
        sb.table("sensor_readings")
        .upsert(rows, on_conflict="node_id,ts", ignore_duplicates=True)
        .execute()
    )
    return len(res.data or [])


def get_latest_reading(node_id: str) -> Optional[Dict[str, Any]]:
    """노드별 최신 측정값 1건. 수집 상태 확인·대시보드용."""
    sb = get_supabase()
    res = (
        sb.table("sensor_readings")
        .select("node_id, ts, temperature, humidity, pm25, gas_resistance, created_at")
        .eq("node_id", node_id)
        .order("ts", desc=True)
        .limit(1)
        .execute()
    )
    return res.data[0] if res.data else None