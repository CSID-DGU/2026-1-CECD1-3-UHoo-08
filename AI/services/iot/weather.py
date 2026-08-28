"""
실외 날씨 조회.

── 실패해도 화면은 떠야 한다 ───────────────────────────────────────
외부 API는 우리가 통제할 수 없다. 시연 중 응답이 없으면 실외 값만 비우고
실내 값은 그대로 보여준다. 예외를 위로 던지면 탭4 전체가 오류 화면이 된다.
"""
from __future__ import annotations

import logging

from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
AIR_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"

SOURCE_LABEL = "Open-Meteo (기상 모델 격자값)"

# 외부 호출은 짧게 끊는다. 키오스크가 10분마다 부르므로 한 번 실패해도
# 다음 주기에 복구된다. 오래 기다리면 화면이 멈춘 것처럼 보인다.
TIMEOUT_S = 6.0

# 지역 좌표. 화면(EnvScreen)의 REGIONS와 같은 이름을 쓴다.
# 예선 장소와 본선 장소(광주)를 미리 넣어둔다.
REGIONS: Dict[str, tuple] = {
    "인천 부평": (37.5074, 126.7218),
    "서울 중구": (37.5636, 126.9976),
    "광주 서구": (35.1526, 126.8899),
}

DEFAULT_REGION = "인천 부평"


def resolve_region(name: Optional[str]) -> tuple:
    """지역 이름을 좌표로. 모르는 이름이면 기본 지역으로 떨어뜨린다."""
    key = (name or "").strip() or DEFAULT_REGION
    if key not in REGIONS:
        logger.warning("알 수 없는 지역 %r → %s", name, DEFAULT_REGION)
        key = DEFAULT_REGION
    return key, *REGIONS[key]


def fetch_outdoor(region: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    실외 현재값. 실패하면 None을 돌려주고 예외를 던지지 않는다.

    두 엔드포인트를 부른다. 기상(온습도·자외선)과 대기질(미세먼지)이
    서로 다른 서비스이기 때문이다. 둘 중 하나만 실패하면 그쪽만 비운다.
    """
    name, lat, lon = resolve_region(region)

    temp = humid = uv = None
    pm10 = pm25 = None
    observed: Optional[str] = None

    try:
        with httpx.Client(timeout=TIMEOUT_S) as client:
            r = client.get(FORECAST_URL, params={
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,relative_humidity_2m,uv_index",
                "timezone": "Asia/Seoul",
            })
            r.raise_for_status()
            cur = (r.json() or {}).get("current") or {}
            temp = cur.get("temperature_2m")
            humid = cur.get("relative_humidity_2m")
            uv = cur.get("uv_index")
            observed = cur.get("time")
    except Exception:
        logger.exception("실외 기상 조회 실패 region=%s", name)

    try:
        with httpx.Client(timeout=TIMEOUT_S) as client:
            r = client.get(AIR_URL, params={
                "latitude": lat,
                "longitude": lon,
                "current": "pm10,pm2_5",
                "timezone": "Asia/Seoul",
            })
            r.raise_for_status()
            cur = (r.json() or {}).get("current") or {}
            pm10 = cur.get("pm10")
            pm25 = cur.get("pm2_5")
            observed = observed or cur.get("time")
    except Exception:
        logger.exception("실외 대기질 조회 실패 region=%s", name)

    # 하나도 못 받았으면 아예 없는 것으로 돌려준다. 전부 null인 카드를
    # 보여주느니 "불러오지 못했습니다"가 낫다.
    if temp is None and pm25 is None:
        return None

    # Open-Meteo는 timezone=Asia/Seoul일 때 tz 없는 지역시각을 준다.
    # 그대로 두면 프론트가 UTC로 해석해 9시간 어긋난다.
    observed_iso = None
    if observed:
        try:
            dt = datetime.fromisoformat(str(observed))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone(_kst_offset()))
            observed_iso = dt.isoformat()
        except ValueError:
            logger.warning("관측 시각 파싱 실패 %r", observed)

    return {
        "region": name,
        "observed_at": observed_iso,
        "temperature": temp,
        "humidity": humid,
        "uv_index": uv,
        "pm10": pm10,
        "pm25": pm25,
        "source": SOURCE_LABEL,
    }


def _kst_offset():
    from datetime import timedelta
    return timedelta(hours=9)