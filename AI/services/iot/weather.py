"""
실외 날씨 조회.
"""
from __future__ import annotations

import logging
import math

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

import httpx

from config import settings

logger = logging.getLogger(__name__)

KMA_URL = "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getUltraSrtNcst"
OPEN_METEO_FORECAST = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_AIR = "https://air-quality-api.open-meteo.com/v1/air-quality"

# 외부 호출은 짧게 끊는다. 키오스크가 10분마다 부르므로 한 번 실패해도
# 다음 주기에 복구된다. 오래 기다리면 화면이 멈춘 것처럼 보인다.
TIMEOUT_S = 6.0

KST = timezone(timedelta(hours=9))

REGIONS: Dict[str, Tuple[float, float]] = {
    "인천 부평": (37.5074, 126.7218),
    "서울 중구": (37.5636, 126.9976),
    "광주 서구": (35.1526, 126.8899),
}

DEFAULT_REGION = "인천 부평"


def resolve_region(name: Optional[str]) -> Tuple[str, float, float]:
    key = (name or "").strip() or DEFAULT_REGION
    if key not in REGIONS:
        logger.warning("알 수 없는 지역 %r → %s", name, DEFAULT_REGION)
        key = DEFAULT_REGION
    lat, lon = REGIONS[key]
    return key, lat, lon


# ── 격자 좌표 변환 ───────────────────────────────────────────────

def dfs_xy_conv(lat: float, lon: float) -> Tuple[int, int]:
    """
    위경도 → 기상청 격자(nx, ny).

    기상청이 배포한 변환 공식 그대로다. 람베르트 정각원뿔 도법이며,
    상수는 기상청 격자 정의에 고정되어 있어 바꾸면 안 된다.

    검증: 서울 중구(37.5636, 126.9976) → nx=60, ny=127.
    기상청 예제에 나오는 값과 일치한다.
    """
    RE, GRID = 6371.00877, 5.0          # 지구 반경 km, 격자 간격 km
    SLAT1, SLAT2 = 30.0, 60.0           # 표준 위도
    OLON, OLAT = 126.0, 38.0            # 기준점 경위도
    XO, YO = 43, 136                    # 기준점 격자 번호

    D = math.pi / 180.0
    re = RE / GRID
    s1, s2 = SLAT1 * D, SLAT2 * D
    olon, olat = OLON * D, OLAT * D

    sn = math.tan(math.pi * 0.25 + s2 * 0.5) / math.tan(math.pi * 0.25 + s1 * 0.5)
    sn = math.log(math.cos(s1) / math.cos(s2)) / math.log(sn)
    sf = math.tan(math.pi * 0.25 + s1 * 0.5)
    sf = (sf ** sn) * math.cos(s1) / sn
    ro = math.tan(math.pi * 0.25 + olat * 0.5)
    ro = re * sf / (ro ** sn)

    ra = math.tan(math.pi * 0.25 + lat * D * 0.5)
    ra = re * sf / (ra ** sn)
    theta = lon * D - olon
    if theta > math.pi:
        theta -= 2.0 * math.pi
    if theta < -math.pi:
        theta += 2.0 * math.pi
    theta *= sn

    nx = int(ra * math.sin(theta) + XO + 0.5)
    ny = int(ro - ra * math.cos(theta) + YO + 0.5)
    return nx, ny


def _base_datetime(now: Optional[datetime] = None) -> Tuple[str, str]:
    """
    초단기실황의 발표일시.

    매시각 정시에 관측하고 **40분 이후**에 제공된다. 40분 전에 부르면
    아직 없는 자료를 요구하는 셈이라 빈 응답이 온다. 그래서 40분 전이면
    한 시간 전 자료를 쓴다.

    발표 시각은 KST 기준이다. 서버가 UTC로 돌아가므로 반드시 변환한다.
    """
    n = (now or datetime.now(timezone.utc)).astimezone(KST)
    if n.minute < 40:
        n -= timedelta(hours=1)
    return n.strftime("%Y%m%d"), n.strftime("%H00")


# ── 기상청 ───────────────────────────────────────────────────────

def fetch_kma_current(lat: float, lon: float) -> Optional[Dict[str, Any]]:
    """
    초단기실황에서 기온·습도. 실패하면 None.

    응답의 category 코드
        T1H  기온 ℃
        REH  습도 %
        RN1  1시간 강수량 mm
        WSD  풍속 m/s
    지금은 앞의 둘만 쓴다.
    """
    key = (settings.KMA_SERVICE_KEY or "").strip()
    if not key:
        return None

    nx, ny = dfs_xy_conv(lat, lon)
    base_date, base_time = _base_datetime()

    try:
        with httpx.Client(timeout=TIMEOUT_S) as client:
            r = client.get(KMA_URL, params={
                # httpx가 알아서 URL 인코딩한다. 포털의 '인코딩된 키'를
                # 넣으면 두 번 인코딩되어 인증에 실패한다.
                "serviceKey": key,
                "pageNo": 1,
                "numOfRows": 10,
                "dataType": "JSON",
                "base_date": base_date,
                "base_time": base_time,
                "nx": nx,
                "ny": ny,
            })
            r.raise_for_status()
            body = r.json()
    except Exception:
        # 키가 잘못됐거나 XML 오류 문서가 오면 JSON 파싱에서 터진다.
        logger.exception("기상청 조회 실패 nx=%s ny=%s %s %s",
                         nx, ny, base_date, base_time)
        return None

    header = (body.get("response") or {}).get("header") or {}
    if str(header.get("resultCode")) not in ("00", "0"):
        logger.warning("기상청 응답 코드 %s %s",
                       header.get("resultCode"), header.get("resultMsg"))
        return None

    items = (((body.get("response") or {}).get("body") or {})
             .get("items") or {}).get("item") or []

    values: Dict[str, float] = {}
    for it in items:
        cat = it.get("category")
        raw = it.get("obsrValue")
        if cat is None or raw is None:
            continue
        try:
            values[cat] = float(raw)
        except (TypeError, ValueError):
            continue

    if "T1H" not in values and "REH" not in values:
        return None

    observed = None
    try:
        observed = datetime.strptime(f"{base_date}{base_time}", "%Y%m%d%H%M") \
            .replace(tzinfo=KST).isoformat()
    except ValueError:
        logger.warning("발표일시 파싱 실패 %s %s", base_date, base_time)

    return {
        "temperature": values.get("T1H"),
        "humidity": values.get("REH"),
        "observed_at": observed,
        "grid": f"{nx},{ny}",
    }


# ── Open-Meteo ───────────────────────────────────────────────────

def fetch_uv_and_air(lat: float, lon: float) -> Dict[str, Any]:
    """
    자외선 지수와 미세먼지.

    기상청 생활기상지수·에어코리아를 신청하면 이 함수만 갈아끼우면 된다.
    반환 형태를 유지하면 나머지 코드는 손대지 않아도 된다.
    """
    out: Dict[str, Any] = {"uv_index": None, "pm10": None, "pm25": None,
                           "observed_at": None}

    try:
        with httpx.Client(timeout=TIMEOUT_S) as client:
            r = client.get(OPEN_METEO_FORECAST, params={
                "latitude": lat, "longitude": lon,
                "current": "uv_index", "timezone": "Asia/Seoul",
            })
            r.raise_for_status()
            cur = (r.json() or {}).get("current") or {}
            out["uv_index"] = cur.get("uv_index")
            out["observed_at"] = _kst_iso(cur.get("time"))
    except Exception:
        logger.exception("자외선 조회 실패")

    try:
        with httpx.Client(timeout=TIMEOUT_S) as client:
            r = client.get(OPEN_METEO_AIR, params={
                "latitude": lat, "longitude": lon,
                "current": "pm10,pm2_5", "timezone": "Asia/Seoul",
            })
            r.raise_for_status()
            cur = (r.json() or {}).get("current") or {}
            out["pm10"] = cur.get("pm10")
            out["pm25"] = cur.get("pm2_5")
            out["observed_at"] = out["observed_at"] or _kst_iso(cur.get("time"))
    except Exception:
        logger.exception("대기질 조회 실패")

    return out


def _kst_iso(v: Any) -> Optional[str]:
    """
    Open-Meteo는 timezone=Asia/Seoul일 때 tz 없는 지역시각을 준다.
    그대로 두면 프론트가 UTC로 읽어 9시간 어긋난다.
    """
    if not v:
        return None
    try:
        dt = datetime.fromisoformat(str(v))
    except ValueError:
        return None
    return (dt if dt.tzinfo else dt.replace(tzinfo=KST)).isoformat()


# ── 조립 ─────────────────────────────────────────────────────────

def fetch_outdoor(region: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    실외 현재값. 실패해도 예외를 던지지 않는다.

    기상청이 실패하면 Open-Meteo의 기온·습도로 대신한다. 둘 다 실패하고
    미세먼지도 없으면 None을 돌려주며, 화면은 "실외를 불러오지 못했습니다"를
    표시한다. 전부 null인 카드를 보여주는 것보다 낫다.
    """
    name, lat, lon = resolve_region(region)

    air = fetch_uv_and_air(lat, lon)
    kma = fetch_kma_current(lat, lon)

    temp = humid = None
    observed = None
    sources = []

    if kma:
        temp = kma.get("temperature")
        humid = kma.get("humidity")
        observed = kma.get("observed_at")
        sources.append(f"기상청 초단기실황 (격자 {kma.get('grid')})")
    else:
        # 기상청이 안 되면 Open-Meteo에서 기온·습도까지 받아 온다.
        try:
            with httpx.Client(timeout=TIMEOUT_S) as client:
                r = client.get(OPEN_METEO_FORECAST, params={
                    "latitude": lat, "longitude": lon,
                    "current": "temperature_2m,relative_humidity_2m",
                    "timezone": "Asia/Seoul",
                })
                r.raise_for_status()
                cur = (r.json() or {}).get("current") or {}
                temp = cur.get("temperature_2m")
                humid = cur.get("relative_humidity_2m")
                observed = _kst_iso(cur.get("time"))
                sources.append("Open-Meteo 기온·습도")
        except Exception:
            logger.exception("Open-Meteo 기온·습도 조회 실패")

    if air.get("uv_index") is not None or air.get("pm25") is not None:
        sources.append("Open-Meteo 자외선·미세먼지")

    if temp is None and air.get("pm25") is None:
        return None

    return {
        "region": name,
        "observed_at": observed or air.get("observed_at"),
        "temperature": temp,
        "humidity": humid,
        "uv_index": air.get("uv_index"),
        "pm10": air.get("pm10"),
        "pm25": air.get("pm25"),
        "source": " · ".join(sources) if sources else None,
    }


if __name__ == "__main__":
    # 네트워크 없이 격자 변환만 확인한다.
    print("  지역          위도      경도      격자")
    for _name, (la, lo) in REGIONS.items():
        _nx, _ny = dfs_xy_conv(la, lo)
        print(f"  {_name:<12}{la:>8.4f}{lo:>10.4f}   nx={_nx} ny={_ny}")
    print()
    print("  서울 중구가 nx=60 ny=127이면 변환식이 맞습니다 (기상청 예제값).")
    print(f"  발표일시: {_base_datetime()}")
    print(f"  기상청 키: {'설정됨' if settings.KMA_SERVICE_KEY else '없음 — Open-Meteo로 대체'}")