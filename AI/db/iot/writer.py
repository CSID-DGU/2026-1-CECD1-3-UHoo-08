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

from datetime import datetime, timedelta, timezone
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

def insert_user_product(
    user_id: str,
    product_id: str,
    *,
    usage_type: str = "USING",
    opened_at: Optional[str] = None,
    purchased_at: Optional[str] = None,
    storage_node_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    보유 제품 등록.

    BE(Spring)의 UserProduct 엔티티에는 opened_at·storage_node_id가 없다.
    그 값들은 점검 순위를 내는 데 반드시 필요한데(services/iot/priority의
    _REQUIRED) BE를 거치면 넣을 방법이 없어, 이 값을 실제로 쓰는 쪽에서
    직접 쓴다.

    같은 제품을 이미 등록했으면 새로 만들지 않고 갱신한다. 중복 등록은
    점검 목록에 같은 제품이 두 번 뜨게 만든다.
    """
    sb = get_supabase()

    existing = (
        sb.table("user_products")
        .select("id")
        .eq("user_id", user_id)
        .eq("product_id", product_id)
        .in_("usage_type", ["USING", "USED"])
        .limit(1)
        .execute()
    ).data or []

    payload: Dict[str, Any] = {"usage_type": usage_type}
    # None은 넣지 않는다. 나중에 채우기로 한 값을 덮어써 지우면 안 된다.
    if opened_at is not None:
        payload["opened_at"] = opened_at
    if purchased_at is not None:
        payload["purchased_at"] = purchased_at
    if storage_node_id is not None:
        payload["storage_node_id"] = storage_node_id

    if existing:
        row = (
            sb.table("user_products")
            .update(payload)
            .eq("id", existing[0]["id"])
            .execute()
        ).data
        return (row or [{}])[0]

    payload.update({"user_id": user_id, "product_id": product_id})
    row = (sb.table("user_products").insert(payload).execute()).data
    return (row or [{}])[0]


def update_user_product(user_product_id: str, patch: Dict[str, Any]) -> None:
    """보유 제품의 일부 필드만 갱신. 호출자가 소유 확인을 마친 뒤 부른다."""
    if not patch:
        return
    get_supabase().table("user_products").update(patch).eq(
        "id", user_product_id).execute()


def discard_user_product(user_product_id: str) -> None:
    """
    보유 제품 목록에서 뺀다.

    행을 지우지 않고 usage_type만 바꾼다. optical_measurements·user_feedback·
    risk_events가 이 id를 참조하고 있어, 실제로 지우면 그동안 쌓인 측정과
    확인 이력이 함께 사라지거나 끊긴다. 잘못 등록해서 빼는 경우든 다 써서
    버리는 경우든, 지난 기록까지 없앨 이유는 없다.

    DISCARDED는 _OWNED_USAGE에 없으므로 점검 목록과 보유 목록에서 빠진다.
    """
    get_supabase().table("user_products").update(
        {"usage_type": "DISCARDED"}).eq("id", user_product_id).execute()


def get_optical_baseline(user_product_id: str) -> Optional[Dict[str, Any]]:
    """가장 처음 잰 색. 이후 측정은 전부 이것과 비교한다."""
    rows = (
        get_supabase().table("optical_measurements")
        .select("ts, channels, white_ref")
        .eq("user_product_id", user_product_id)
        .order("ts", desc=False)
        .limit(1)
        .execute()
    ).data or []
    return rows[0] if rows else None


def insert_optical(
    user_product_id: str,
    channels: Dict[str, Any],
    white_ref: Optional[Dict[str, Any]],
    delta: Optional[float],
    ts: str,
) -> Dict[str, Any]:
    """색 측정 한 건 기록. 기준값이면 delta는 None으로 둔다."""
    row = (
        get_supabase().table("optical_measurements").insert({
            "user_product_id": user_product_id,
            "ts": ts,
            "channels": channels,
            "white_ref": white_ref,
            "delta_pct": delta,
        }).execute()
    ).data
    return (row or [{}])[0]


def upsert_thermal_profile(row: Dict[str, Any]) -> None:
    """
    제품 열 프로파일을 넣는다. 이미 있으면 건드리지 않는다.

    사람이 검수해 넣은 값을 규칙으로 만든 값이 덮어쓰면 안 된다.
    """
    sb = get_supabase()
    pid = row.get("product_id")
    exists = (
        sb.table("product_thermal_profile")
        .select("product_id").eq("product_id", pid).limit(1).execute()
    ).data
    if exists:
        return
    sb.table("product_thermal_profile").insert(row).execute()


# ── 측정 세션 ──────────────────────────────────────────────────
#
# 세션은 한 번의 광학 측정을 가리키는 실체다(015_create_measure_sessions).
# 키오스크가 열고, 노드가 두 번에 나눠 채우고, 키오스크가 읽어 간다.

# 아직 채워지는 중인 상태. 노드는 이 상태의 세션만 자기 일감으로 본다.
OPEN_SESSION_STATUS = ("waiting_white", "waiting_sample")

_SESSION_COLS = (
    "id, node_id, user_id, target, user_product_id, site, status, "
    "white_ref, channels, meta, saturated, baseline, delta_pct, message, "
    "created_at, updated_at, expires_at"
)


def _parse_ts(value: Any) -> Optional[datetime]:
    """PostgREST가 준 timestamptz 문자열을 aware datetime으로."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _expire_if_stale(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    시한이 지난 열린 세션을 만료로 바꾼다.

    별도의 정리 작업을 두지 않고 읽을 때 처리한다. 세션을 읽는 쪽은
    노드 폴링과 키오스크 조회 둘뿐이고, 둘 중 하나는 반드시 지나가기
    때문이다. 만료를 미뤄 두면 사용자가 자리를 뜬 세션이 노드를 계속
    붙잡아 다음 측정을 시작할 수 없게 된다.
    """
    if not row or row.get("status") not in OPEN_SESSION_STATUS:
        return row

    expires = _parse_ts(row.get("expires_at"))
    if expires is None or datetime.now(timezone.utc) <= expires:
        return row

    return update_measure_session(row["id"], {
        "status": "expired",
        "message": "측정 시간이 지났습니다. 다시 시작해 주세요.",
    })


def create_measure_session(
    node_id: str,
    *,
    user_id: Optional[str],
    target: str = "product",
    user_product_id: Optional[str] = None,
    site: Optional[str] = None,
    ttl_sec: int = 300,
) -> Dict[str, Any]:
    """
    측정 세션을 연다. 백색 표준판을 기다리는 상태로 시작한다.

    같은 노드에 열린 세션이 남아 있으면 먼저 취소한다. 노드는 세션을
    하나만 들고 갈 수 있어서, 남은 세션이 있으면 방금 누른 "측정하기"가
    아니라 이전 것을 재게 된다.
    """
    close_open_measure_sessions(node_id, status="cancelled")

    expires = datetime.now(timezone.utc) + timedelta(seconds=ttl_sec)
    row = (
        get_supabase().table("measure_sessions").insert({
            "node_id": node_id,
            "user_id": user_id,
            "target": target,
            "user_product_id": user_product_id,
            "site": site,
            "status": "waiting_white",
            "expires_at": expires.isoformat(),
        }).execute()
    ).data
    return (row or [{}])[0]


def get_measure_session(session_id: str) -> Optional[Dict[str, Any]]:
    """세션 1건. 시한이 지났으면 만료 처리한 결과를 돌려준다."""
    rows = (
        get_supabase().table("measure_sessions")
        .select(_SESSION_COLS)
        .eq("id", session_id)
        .limit(1)
        .execute()
    ).data or []
    return _expire_if_stale(rows[0]) if rows else None


def get_open_measure_session(node_id: str) -> Optional[Dict[str, Any]]:
    """
    노드가 지금 처리해야 할 세션. 없으면 None.

    노드는 이것을 2초 간격으로 묻는다. 열린 세션이 여럿일 일은 없지만
    (생성 시 이전 것을 닫는다) 최신 하나만 본다.
    """
    rows = (
        get_supabase().table("measure_sessions")
        .select(_SESSION_COLS)
        .eq("node_id", node_id)
        .in_("status", list(OPEN_SESSION_STATUS))
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    ).data or []
    if not rows:
        return None
    row = _expire_if_stale(rows[0])
    return row if row and row.get("status") in OPEN_SESSION_STATUS else None


def update_measure_session(
    session_id: str, patch: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """세션 일부 필드 갱신. updated_at은 여기서 붙인다."""
    if not patch:
        return get_measure_session(session_id)

    payload = dict(patch)
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    rows = (
        get_supabase().table("measure_sessions")
        .update(payload)
        .eq("id", session_id)
        .execute()
    ).data or []
    return rows[0] if rows else None


def close_open_measure_sessions(node_id: str, *, status: str = "cancelled") -> int:
    """노드에 열려 있는 세션을 모두 닫는다. 닫은 건수를 돌려준다."""
    rows = (
        get_supabase().table("measure_sessions")
        .update({
            "status": status,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        .eq("node_id", node_id)
        .in_("status", list(OPEN_SESSION_STATUS))
        .execute()
    ).data or []
    return len(rows)
