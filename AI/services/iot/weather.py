"""
실외 날씨 조회.

── 공공데이터포털 세 서비스를 쓴다 ────────────────────────────────
    기온·습도    기상청 초단기실황 getUltraSrtNcst      — 관측값
    자외선 지수  기상청 생활기상지수 getUVIdxV5          — 3시간 단위 예측값
    미세먼지     에어코리아 getCtprvnRltmMesureDnsty — 시도 측정소 실측값

── 실패해도 화면은 떠야 한다 ───────────────────────────────────────
외부 API는 우리가 통제할 수 없다. 항목별로 따로 부르고, 실패한 항목만
비운다. 기온·습도가 실패하면 Open-Meteo로 대신한다(키 없이 되는 곳이라
최후의 안전망으로 남겨둔다). 예외를 위로 던지면 탭4 전체가 오류 화면이 된다.
"""
from __future__ import annotations

import logging
import math
import time

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import httpx

from config import settings
from services.iot.cache import TTLCache

logger = logging.getLogger(__name__)

KMA_NCST_URL = "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getUltraSrtNcst"
KMA_UV_URL = "https://apis.data.go.kr/1360000/LivingWthrIdxServiceV5/getUVIdxV5"
# 측정소별(getMsrstnAcctoRltmMesureDnsty)이 아니라 시도별이다.
# fetch_air가 sidoName으로 부르므로 엔드포인트도 시도별이어야 한다.
# 측정소별 URL에 sidoName을 보내면 NO_MANDATORY_REQUEST_PARAMETERS_ERROR가 난다.
AIRKOREA_URL = "https://apis.data.go.kr/B552584/ArpltnInforInqireSvc/getCtprvnRltmMesureDnsty"
OPEN_METEO_FORECAST = "https://api.open-meteo.com/v1/forecast"

# 외부 호출은 짧게 끊는다. 세 곳을 순차로 부르므로 최악의 경우 이 값의
# 세 배를 기다린다. 캐시를 넣으면 체감 지연이 사라진다.
TIMEOUT_S = 6.0

KST = timezone(timedelta(hours=9))

# 실외 값 캐시.
#
# 10분인 이유: 초단기실황이 매시 갱신되고 에어코리아도 1시간 단위다.
# 그보다 자주 불러도 같은 값이 온다. 키오스크 폴링 주기(10분)와 맞췄다.
#
# 갱신에 실패하면 만료된 값이라도 계속 쓴다. 응답의 cache_age_s로 언제
# 받은 값인지 알 수 있다.
OUTDOOR_TTL_S = 600.0
_outdoor_cache = TTLCache(OUTDOOR_TTL_S, name="outdoor")

# 시도 16곳.
#
# 기상청이 배포하는 지역코드 파일(dfs-zone-tree, 2026-07-01 기준)에서
# 1단계만 있고 2·3단계가 빈 행, 즉 시도 단위 행을 그대로 옮겼다.
# 격자(nx, ny)도 파일에 있는 값을 쓴다. 계산해도 같은 값이 나오지만,
# 공식 파일 값을 쓰면 변환식 오차를 걱정할 필요가 없다.
#
# ── areaNo는 시도 단위 코드가 정식이다 ───────────────────────────
# 생활기상지수 API 문서의 샘플이 1100000000(서울)이다. 처음에는 구 단위
# 코드(1114000000 서울 중구)를 썼는데, 그것도 통하지만 시도 단위가 맞다.
#
#   lat/lon    참고용. 조회에는 grid를 쓴다
#   grid       기상청 격자 (nx, ny)
#   area_no    생활기상지수 지점코드
#   sido       에어코리아 시도명
REGIONS: Dict[str, Dict[str, Any]] = {
    "서울": {"lat": 37.5636, "lon": 126.9800, "grid": (60, 127),
             "area_no": "1100000000", "sido": "서울"},
    "부산": {"lat": 35.1770, "lon": 129.0770, "grid": (98, 76),
             "area_no": "2600000000", "sido": "부산"},
    "대구": {"lat": 35.8685, "lon": 128.6036, "grid": (89, 90),
             "area_no": "2700000000", "sido": "대구"},
    "인천": {"lat": 37.4532, "lon": 126.7074, "grid": (55, 124),
             "area_no": "2800000000", "sido": "인천"},
    "대전": {"lat": 36.3471, "lon": 127.3866, "grid": (67, 100),
             "area_no": "3000000000", "sido": "대전"},
    "울산": {"lat": 35.5354, "lon": 129.3137, "grid": (102, 84),
             "area_no": "3100000000", "sido": "울산"},
    "세종": {"lat": 36.4800, "lon": 127.2891, "grid": (66, 103),
             "area_no": "3600000000", "sido": "세종"},
    "경기": {"lat": 37.2718, "lon": 127.0117, "grid": (60, 120),
             "area_no": "4100000000", "sido": "경기"},
    "강원": {"lat": 37.8827, "lon": 127.7320, "grid": (73, 134),
             "area_no": "5100000000", "sido": "강원"},
    "충북": {"lat": 36.6325, "lon": 127.4936, "grid": (69, 107),
             "area_no": "4300000000", "sido": "충북"},
    "충남": {"lat": 36.6588, "lon": 126.6728, "grid": (55, 107),
             "area_no": "4400000000", "sido": "충남"},
    "전북": {"lat": 35.8173, "lon": 127.1111, "grid": (63, 89),
             "area_no": "5200000000", "sido": "전북"},
    # 통합 이전 명칭으로는 에어코리아가 여전히 광주·전남을 따로 다룰 수
    # 있다. sido 값은 check_region_codes.py로 확인한 뒤 확정한다.
    "전남광주": {"lat": 34.8130, "lon": 126.4650, "grid": (51, 67),
                 "area_no": "1200000000", "sido": "전남"},
    "경북": {"lat": 36.5760, "lon": 128.5058, "grid": (87, 106),
             "area_no": "4700000000", "sido": "경북"},
    "경남": {"lat": 35.2347, "lon": 128.6942, "grid": (91, 77),
             "area_no": "4800000000", "sido": "경남"},
    "제주": {"lat": 33.4857, "lon": 126.5003, "grid": (52, 38),
             "area_no": "5000000000", "sido": "제주"},
}

DEFAULT_REGION = "인천"


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

    지금은 조회에 쓰지 않는다. REGIONS에 기상청 공식 파일의 격자를 그대로
    넣었기 때문이다. 지역을 새로 추가할 때 파일에 없는 좌표를 격자로
    바꾸거나, 표의 값이 맞는지 대조할 때 쓴다.

    검증: 서울(37.5636, 126.9800) → nx=60, ny=127 (공식 파일과 일치)
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

def fetch_kma_current(grid: Tuple[int, int]) -> Optional[Dict[str, Any]]:
    """
    기온(T1H)과 습도(REH). 실패하면 None.

    응답은 items.item 배열이고 category로 값이 구분된다.
    PTY·RN1·WSD 등도 함께 오지만 지금은 쓰지 않는다.
    """
    key = _key()
    if not key:
        return None

    nx, ny = grid
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

# 이 API는 응답이 느릴 때가 잦다. 실제로 504 Gateway Timeout이 관측됐다.
# 그래서 다른 곳보다 넉넉히 기다리고 한 번 더 시도한다.
AIR_TIMEOUT_S = 10.0
AIR_RETRY = 2


def _median(values: List[float]) -> Optional[float]:
    if not values:
        return None
    s = sorted(values)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


def fetch_air(sido: str) -> Optional[Dict[str, Any]]:
    """
    시도별 실시간 측정정보. 실패하면 None.

    측정소 하나가 아니라 시도 전체를 받아 **중앙값**을 쓴다. 이유는 둘이다.

      · 측정소 이름을 지역마다 관리하지 않아도 된다
      · 측정소 하나가 점검 중이어도 나머지로 값이 나온다

    평균이 아니라 중앙값인 이유는, 공사장 옆 측정소처럼 유난히 높은 값이
    하나 섞여도 전체가 끌려가지 않게 하기 위해서다.

    응답 구조가 기상청과 다르다. items가 곧바로 배열이며 item 키가 없다.
    pm25Flag가 null이 아니면 통신 장애·점검 중이라 값을 믿을 수 없다.
    """
    key = _key()
    if not key:
        return None

    body = None
    for attempt in range(AIR_RETRY):
        try:
            with httpx.Client(timeout=AIR_TIMEOUT_S) as client:
                # 파라미터가 까다롭다. numOfRows·pageNo를 넣으면 헤더 없는
                # 빈 응답이 온다. 실제로 통하는 조합은 아래 셋뿐이다.
                # 그래서 기본 페이지 크기(10곳)만 받는다. 중앙값을 내기에는
                # 충분하고, 늘릴 방법도 없다.
                r = client.get(AIRKOREA_URL, params={
                    "serviceKey": key,
                    "returnType": "json",
                    "sidoName": sido,
                    "ver": "1.3",
                })
                r.raise_for_status()
                body = r.json()
            break
        except Exception as e:
            # 타임아웃·504는 흔한 일이라 예외 전문을 찍지 않는다.
            # 지역 17곳을 도는 스크립트에서 스택 트레이스가 화면을 덮어
            # 정작 어느 지역이 실패했는지 안 보였다.
            logger.warning("대기오염 조회 실패 sido=%s (%d/%d) %s",
                           sido, attempt + 1, AIR_RETRY, type(e).__name__)
            if attempt == AIR_RETRY - 1:
                return None
            time.sleep(0.6)

    if body is None:
        return None

    resp = body.get("response") or {}
    header = resp.get("header") or {}
    if header and str(header.get("resultCode")) not in ("00", "0"):
        logger.warning("대기오염 코드 %s %s",
                       header.get("resultCode"), header.get("resultMsg"))
        return None

    items = (resp.get("body") or {}).get("items") or []
    if not items:
        logger.warning("대기오염 항목 없음. sidoName=%s 확인 필요", sido)
        return None

    pm25_vals: List[float] = []
    pm10_vals: List[float] = []
    latest_time = None

    for it in items:
        if it.get("pm25Flag") is None:
            v = _num(it.get("pm25Value"))
            if v is not None:
                pm25_vals.append(v)
        if it.get("pm10Flag") is None:
            v = _num(it.get("pm10Value"))
            if v is not None:
                pm10_vals.append(v)

        raw = it.get("dataTime")
        if raw and latest_time is None:
            try:
                latest_time = datetime.strptime(str(raw).strip(), "%Y-%m-%d %H:%M") \
                    .replace(tzinfo=KST).isoformat()
            except ValueError:
                # 24:00 표기가 오는 경우가 있다.
                pass

    pm25 = _median(pm25_vals)
    if pm25 is None:
        logger.warning("대기오염 유효값 없음 sido=%s", sido)
        return None

    return {
        "pm25": pm25,
        "pm10": _median(pm10_vals),
        "observed_at": latest_time,
        "sido": sido,
        "station_n": len(pm25_vals),
    }


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

def _fetch_outdoor_uncached(name: str, cfg: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    실외 현재값을 실제로 조회한다. 항목별로 따로 부르고 실패한 것만 비운다.

    기온과 미세먼지가 둘 다 없으면 None을 돌려준다. 전부 null인 카드를
    보여주느니 "불러오지 못했습니다"가 낫다. None을 돌려주면 캐시가
    이전 값을 계속 쓰게 된다.
    """

    kma = fetch_kma_current(cfg["grid"])
    uv = fetch_uv(cfg["area_no"])
    air = fetch_air(cfg["sido"])

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
        sources.append(f"에어코리아 {air['sido']} 측정소 {air['station_n']}곳 중앙값")
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


def fetch_outdoor(
    region: Optional[str] = None,
    *,
    force: bool = False,
) -> Optional[Dict[str, Any]]:
    """
    실외 현재값. 10분간 캐시한다.

    force=True면 캐시를 무시하고 다시 부른다. 시연 직전에 값을 새로
    받아두고 싶을 때 쓴다.

    응답에 cache_age_s를 넣어, 몇 초 전에 받은 값인지 화면이 알 수 있게 한다.
    """
    name, cfg = resolve_region(region)

    if force:
        _outdoor_cache.invalidate(name)

    value, age, from_cache = _outdoor_cache.get_or_load(
        name, lambda: _fetch_outdoor_uncached(name, cfg)
    )

    if value is None:
        return None

    # 캐시된 dict를 그대로 돌려주면 호출한 쪽에서 고쳤을 때 캐시가 오염된다.
    out = dict(value)
    out["cache_age_s"] = round(age, 1)
    out["from_cache"] = from_cache
    return out


if __name__ == "__main__":
    import json

    print("지역별 좌표·코드")
    for _name, _cfg in REGIONS.items():
        _nx, _ny = dfs_xy_conv(_cfg["lat"], _cfg["lon"])
        print(f"  {_name:<6} nx={_nx:>3} ny={_ny:>3}  "
              f"areaNo={_cfg['area_no']}  시도={_cfg['sido']}")

    print()
    print(f"초단기실황 발표  {_ncst_base()}")
    print(f"자외선 발표      {_uv_base()}")
    print(f"인증키           {'설정됨' if _key() else '없음'}")

    if _key():
        print()
        print("실제 호출 (에어코리아 일 500회 제한에 유의)")
        print(json.dumps(fetch_outdoor(), ensure_ascii=False, indent=1))