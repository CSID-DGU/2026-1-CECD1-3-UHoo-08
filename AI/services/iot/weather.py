"""
실외 날씨 조회.

── 공공데이터포털 세 서비스를 쓴다 ────────────────────────────────
    기온·습도    기상청 초단기실황 getUltraSrtNcst      — 관측값
    자외선 지수  기상청 생활기상지수 getUVIdxV5          — 3시간 단위 예측값
    미세먼지     에어코리아 getMsrstnAcctoRltmMesureDnsty — 측정소 실측값

── 실패해도 화면은 떠야 한다 ───────────────────────────────────────
외부 API는 우리가 통제할 수 없다. 항목별로 따로 부르고, 실패한 항목만
비운다. 기온·습도가 실패하면 Open-Meteo로 대신한다(키 없이 되는 곳이라
최후의 안전망으로 남겨둔다). 예외를 위로 던지면 탭4 전체가 오류 화면이 된다.
"""
from __future__ import annotations

import logging
import math

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

import httpx

from config import settings

logger = logging.getLogger(__name__)

KMA_NCST_URL = "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getUltraSrtNcst"
KMA_UV_URL = "https://apis.data.go.kr/1360000/LivingWthrIdxServiceV5/getUVIdxV5"
AIRKOREA_URL = "https://apis.data.go.kr/B552584/ArpltnInforInqireSvc/getMsrstnAcctoRltmMesureDnsty"
OPEN_METEO_FORECAST = "https://api.open-meteo.com/v1/forecast"

# 외부 호출은 짧게 끊는다. 세 곳을 순차로 부르므로 최악의 경우 이 값의
# 세 배를 기다린다. 캐시를 넣으면 체감 지연이 사라진다.
TIMEOUT_S = 6.0

KST = timezone(timedelta(hours=9))

# 지역별 좌표·코드.
#   lat/lon    기상청 격자 변환용
#   area_no    생활기상지수 행정구역 코드
#   station    에어코리아 측정소 이름
#
# area_no와 station은 실제 호출로 확인한 값이다. 지역을 추가할 때는
# scripts/check_gov_api.py로 응답이 오는지 먼저 확인해야 한다.
REGIONS: Dict[str, Dict[str, Any]] = {
    "인천 부평": {"lat": 37.5074, "lon": 126.7218,
                  "area_no": "2823700000", "station": "부평"},
    "서울 중구": {"lat": 37.5636, "lon": 126.9976,
                  "area_no": "1114000000", "station": "중구"},
    "광주 서구": {"lat": 35.1526, "lon": 126.8899,
                  "area_no": "2914000000", "station": "서구"},
}

DEFAULT_REGION = "인천 부평"


def resolve_region(name: Optional[str]) -> Tuple[str, Dict[str, Any]]:
    key = (name or "").strip() or DEFAULT_REGION
    if key not in REGIONS:
        logger.warning("알 수 없는 지역 %r → %s", name, DEFAULT_REGION)
        key = DEFAULT_REGION
    return key, REGIONS[key]


def _key() -> str:
    return (settings.KMA_SERVICE_KEY or "").strip()


def _num(v: Any) -> Optional[float]:
    """
    공공 API는 결측을 빈 문자열이나 '-'로 준다. 그대로 float()에 넣으면
    예외가 나므로 여기서 걸러 None으로 만든다.
    """
    if v is None:
        return None
    s = str(v).strip()
    if s in ("", "-", "N/A"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


# ── 격자 좌표 변환 ───────────────────────────────────────────────

def dfs_xy_conv(lat: float, lon: float) -> Tuple[int, int]:
    """
    위경도 → 기상청 격자(nx, ny).

    기상청이 배포한 변환 공식 그대로다. 람베르트 정각원뿔 도법이며
    상수는 격자 정의에 고정되어 있어 바꾸면 안 된다.

    검증: 서울 중구(37.5636, 126.9976) → nx=60, ny=127 (기상청 예제값과 일치)
    """
    RE, GRID = 6371.00877, 5.0
    SLAT1, SLAT2 = 30.0, 60.0
    OLON, OLAT = 126.0, 38.0
    XO, YO = 43, 136

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

    return (int(ra * math.sin(theta) + XO + 0.5),
            int(ro - ra * math.cos(theta) + YO + 0.5))


def _ncst_base(now: Optional[datetime] = None) -> Tuple[str, str]:
    """
    초단기실황 발표일시.

    매시각 관측하고 40분 이후 제공된다. 40분 전에 부르면 아직 없는 자료를
    요구하는 셈이라 빈 응답이 온다. 자정 직후에는 전날 23시로 넘어간다.
    """
    n = (now or datetime.now(timezone.utc)).astimezone(KST)
    if n.minute < 40:
        n -= timedelta(hours=1)
    return n.strftime("%Y%m%d"), n.strftime("%H00")


def _uv_base(now: Optional[datetime] = None) -> str:
    """
    생활기상지수 발표시각. 하루 두 번(06시·18시)이다.

    06시 전이면 전날 18시 발표가 가장 최근이다.
    """
    n = (now or datetime.now(timezone.utc)).astimezone(KST)
    if n.hour >= 18:
        return f"{n:%Y%m%d}18"
    if n.hour >= 6:
        return f"{n:%Y%m%d}06"
    return f"{n - timedelta(days=1):%Y%m%d}18"


# ── 기상청 초단기실황 ────────────────────────────────────────────

def fetch_kma_current(lat: float, lon: float) -> Optional[Dict[str, Any]]:
    """
    기온(T1H)과 습도(REH). 실패하면 None.

    응답은 items.item 배열이고 category로 값이 구분된다.
    PTY·RN1·WSD 등도 함께 오지만 지금은 쓰지 않는다.
    """
    key = _key()
    if not key:
        return None

    nx, ny = dfs_xy_conv(lat, lon)
    base_date, base_time = _ncst_base()

    try:
        with httpx.Client(timeout=TIMEOUT_S) as client:
            r = client.get(KMA_NCST_URL, params={
                "serviceKey": key, "pageNo": 1, "numOfRows": 10,
                "dataType": "JSON", "base_date": base_date,
                "base_time": base_time, "nx": nx, "ny": ny,
            })
            r.raise_for_status()
            body = r.json()
    except Exception:
        # 인증 오류는 XML로 오므로 JSON 파싱에서 터진다.
        logger.exception("초단기실황 조회 실패 nx=%s ny=%s %s %s",
                         nx, ny, base_date, base_time)
        return None

    resp = body.get("response") or {}
    header = resp.get("header") or {}
    if str(header.get("resultCode")) not in ("00", "0"):
        logger.warning("초단기실황 코드 %s %s",
                       header.get("resultCode"), header.get("resultMsg"))
        return None

    items = ((resp.get("body") or {}).get("items") or {}).get("item") or []
    values = {it.get("category"): _num(it.get("obsrValue")) for it in items}

    if values.get("T1H") is None and values.get("REH") is None:
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


# ── 기상청 생활기상지수 (자외선) ─────────────────────────────────

def fetch_uv(area_no: str) -> Optional[Dict[str, Any]]:
    """
    자외선 지수. 실패하면 None.

    응답은 발표시각 기준 3시간 간격 예측값이다.

        {"date": "2026082806", "h0": "1", "h3": "5", "h6": "7", "h9": "3", ...}

    h0이 발표 시각(06시)이므로, 지금이 15시라면 h9를 봐야 한다. h0을 그냥
    쓰면 오전 6시 값을 현재값으로 보여주게 된다.

    뒤쪽 칸(h66 이후)은 빈 문자열로 오는 경우가 있어, 비어 있으면 한 칸씩
    뒤로 물러나 마지막 유효값을 쓴다.
    """
    key = _key()
    if not key:
        return None

    base = _uv_base()

    try:
        with httpx.Client(timeout=TIMEOUT_S) as client:
            r = client.get(KMA_UV_URL, params={
                "serviceKey": key, "pageNo": 1, "numOfRows": 10,
                "dataType": "JSON", "areaNo": area_no, "time": base,
            })
            r.raise_for_status()
            body = r.json()
    except Exception:
        logger.exception("자외선지수 조회 실패 areaNo=%s time=%s", area_no, base)
        return None

    resp = body.get("response") or {}
    header = resp.get("header") or {}
    if str(header.get("resultCode")) not in ("00", "0"):
        logger.warning("자외선지수 코드 %s %s",
                       header.get("resultCode"), header.get("resultMsg"))
        return None

    items = ((resp.get("body") or {}).get("items") or {}).get("item") or []
    if not items:
        # areaNo가 틀리면 여기가 빈다.
        logger.warning("자외선지수 항목 없음. areaNo=%s 확인 필요", area_no)
        return None

    item = items[0]
    try:
        base_dt = datetime.strptime(str(item.get("date")), "%Y%m%d%H").replace(tzinfo=KST)
    except (ValueError, TypeError):
        logger.warning("자외선 발표시각 파싱 실패 %r", item.get("date"))
        return None

    now = datetime.now(KST)
    hours = (now - base_dt).total_seconds() / 3600.0
    if hours < 0:
        return None

    offset = min(int(hours // 3) * 3, 75)
    while offset >= 0:
        v = _num(item.get(f"h{offset}"))
        if v is not None:
            return {
                "uv_index": v,
                "slot": f"h{offset}",
                "base": base_dt.isoformat(),
                # 예측값이라는 사실을 위로 올린다. 화면에서 감추지 않는다.
                "forecast": True,
            }
        offset -= 3

    return None


# ── 에어코리아 (미세먼지) ────────────────────────────────────────

def fetch_air(station: str) -> Optional[Dict[str, Any]]:
    """
    측정소 실시간 PM2.5·PM10. 실패하면 None.

    기상청과 응답 구조가 다르다. items가 곧바로 배열이며 item 키가 없다.
    최신 항목이 앞에 온다.

    pm25Flag가 null이 아니면 통신 장애·점검 중이라 값을 믿을 수 없다.
    그런 항목은 건너뛰고 다음(한 시간 전) 값을 쓴다.
    """
    key = _key()
    if not key:
        return None

    try:
        with httpx.Client(timeout=TIMEOUT_S) as client:
            r = client.get(AIRKOREA_URL, params={
                "serviceKey": key, "returnType": "json",
                "numOfRows": 5, "pageNo": 1,
                "stationName": station, "dataTerm": "DAILY", "ver": "1.3",
            })
            r.raise_for_status()
            body = r.json()
    except Exception:
        logger.exception("대기오염 조회 실패 station=%s", station)
        return None

    resp = body.get("response") or {}
    header = resp.get("header") or {}
    if header and str(header.get("resultCode")) not in ("00", "0"):
        logger.warning("대기오염 코드 %s %s",
                       header.get("resultCode"), header.get("resultMsg"))
        return None

    items = (resp.get("body") or {}).get("items") or []
    if not items:
        # 측정소 이름이 틀리면 여기가 빈다.
        logger.warning("대기오염 항목 없음. stationName=%s 확인 필요", station)
        return None

    for it in items:
        if it.get("pm25Flag") is not None:
            # 통신 장애·점검 중. 다음 시각으로 넘어간다.
            continue
        pm25 = _num(it.get("pm25Value"))
        if pm25 is None:
            continue

        observed = None
        raw = it.get("dataTime")
        if raw:
            try:
                observed = datetime.strptime(str(raw).strip(), "%Y-%m-%d %H:%M") \
                    .replace(tzinfo=KST).isoformat()
            except ValueError:
                # 24:00 표기가 오는 경우가 있다. 그때는 시각을 비운다.
                logger.warning("측정시각 파싱 실패 %r", raw)

        return {
            "pm25": pm25,
            "pm10": _num(it.get("pm10Value")),
            "observed_at": observed,
            "station": station,
        }

    logger.warning("대기오염 유효값 없음 station=%s", station)
    return None


# ── Open-Meteo (기온·습도 최후 대체) ─────────────────────────────

def fetch_open_meteo(lat: float, lon: float) -> Optional[Dict[str, Any]]:
    """
    기상청이 실패했을 때만 쓴다. 키가 필요 없어 안전망으로 남겨둔다.
    모델 격자값이라 관측값이 아니며, 출처에 그대로 표시된다.
    """
    try:
        with httpx.Client(timeout=TIMEOUT_S) as client:
            r = client.get(OPEN_METEO_FORECAST, params={
                "latitude": lat, "longitude": lon,
                "current": "temperature_2m,relative_humidity_2m",
                "timezone": "Asia/Seoul",
            })
            r.raise_for_status()
            cur = (r.json() or {}).get("current") or {}
    except Exception:
        logger.exception("Open-Meteo 조회 실패")
        return None

    observed = None
    if cur.get("time"):
        try:
            dt = datetime.fromisoformat(str(cur["time"]))
            observed = (dt if dt.tzinfo else dt.replace(tzinfo=KST)).isoformat()
        except ValueError:
            pass

    return {
        "temperature": cur.get("temperature_2m"),
        "humidity": cur.get("relative_humidity_2m"),
        "observed_at": observed,
    }


# ── 조립 ─────────────────────────────────────────────────────────

def fetch_outdoor(region: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    실외 현재값. 항목별로 따로 부르고, 실패한 것만 비운다.

    기온과 미세먼지가 둘 다 없으면 None을 돌려준다. 전부 null인 카드를
    보여주느니 "불러오지 못했습니다"가 낫다.
    """
    name, cfg = resolve_region(region)

    kma = fetch_kma_current(cfg["lat"], cfg["lon"])
    uv = fetch_uv(cfg["area_no"])
    air = fetch_air(cfg["station"])

    sources = []
    temp = humid = None
    observed = None

    if kma:
        temp, humid = kma.get("temperature"), kma.get("humidity")
        observed = kma.get("observed_at")
        sources.append(f"기상청 초단기실황(격자 {kma['grid']})")
    else:
        fallback = fetch_open_meteo(cfg["lat"], cfg["lon"])
        if fallback:
            temp, humid = fallback.get("temperature"), fallback.get("humidity")
            observed = fallback.get("observed_at")
            sources.append("Open-Meteo 기온·습도(모델값)")

    if uv:
        sources.append("기상청 생활기상지수 예보")

    if air:
        sources.append(f"에어코리아 {air['station']} 측정소")
        observed = observed or air.get("observed_at")

    if temp is None and (air is None or air.get("pm25") is None):
        return None

    return {
        "region": name,
        "observed_at": observed,
        "temperature": temp,
        "humidity": humid,
        "uv_index": (uv or {}).get("uv_index"),
        "pm10": (air or {}).get("pm10"),
        "pm25": (air or {}).get("pm25"),
        "source": " · ".join(sources) if sources else None,
    }


if __name__ == "__main__":
    import json

    print("지역별 좌표·코드")
    for _name, _cfg in REGIONS.items():
        _nx, _ny = dfs_xy_conv(_cfg["lat"], _cfg["lon"])
        print(f"  {_name:<12} nx={_nx} ny={_ny}  "
              f"areaNo={_cfg['area_no']}  측정소={_cfg['station']}")

    print()
    print(f"초단기실황 발표  {_ncst_base()}")
    print(f"자외선 발표      {_uv_base()}")
    print(f"인증키           {'설정됨' if _key() else '없음'}")

    if _key():
        print()
        print("실제 호출 (에어코리아 일 500회 제한에 유의)")
        print(json.dumps(fetch_outdoor(), ensure_ascii=False, indent=1))