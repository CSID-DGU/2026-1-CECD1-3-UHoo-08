"""
공공데이터포털 API 세 개를 실제로 불러 응답 형태를 확인한다.

코드를 확정하기 전에 한 번 돌려보는 용도다. 특히 두 가지가 불확실하다.
  · 자외선지수의 areaNo (행정구역 코드)
  · 미세먼지의 stationName (측정소 이름)

    python -m scripts.check_gov_api
    python -m scripts.check_gov_api --station 부평
"""
from __future__ import annotations

import argparse
import json

from datetime import datetime, timedelta, timezone

import httpx

from config import settings
from services.iot.weather import REGIONS, dfs_xy_conv, _base_datetime

KST = timezone(timedelta(hours=9))
TIMEOUT = 10.0

KMA_NCST = "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getUltraSrtNcst"
KMA_UV = "https://apis.data.go.kr/1360000/LivingWthrIdxServiceV5/getUVIdxV5"
AIR = "https://apis.data.go.kr/B552584/ArpltnInforInqireSvc/getMsrstnAcctoRltmMesureDnsty"

# 확인이 필요한 값들. 틀렸으면 응답에 그대로 드러난다.
AREA_NO = {
    "인천 부평": "2823700000",
    "서울 중구": "1114000000",
    "광주 서구": "2914000000",
}
STATION = {
    "인천 부평": "부평",
    "서울 중구": "중구",
    "광주 서구": "서구",
}


def show(title: str, url: str, params: dict) -> None:
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)
    safe = {k: ("***" if k == "serviceKey" else v) for k, v in params.items()}
    print(f"  {url}")
    print(f"  {safe}")

    try:
        r = httpx.get(url, params=params, timeout=TIMEOUT)
    except Exception as e:
        print(f"  요청 실패: {type(e).__name__}: {e}")
        return

    print(f"  HTTP {r.status_code}  ({len(r.text)} bytes)")

    text = r.text.strip()
    if not text.startswith("{"):
        # 인증 오류는 XML로 온다. 앞부분만 보면 원인이 보인다.
        print("  JSON이 아닙니다. 응답 앞부분:")
        print("  " + text[:400].replace("\n", "\n  "))
        return

    try:
        body = r.json()
    except Exception:
        print("  JSON 파싱 실패")
        print("  " + text[:400])
        return

    print(json.dumps(body, ensure_ascii=False, indent=1)[:1800])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", default="인천 부평", choices=list(REGIONS))
    ap.add_argument("--station", default=None, help="측정소 이름을 직접 지정")
    ap.add_argument("--area", default=None, help="자외선 areaNo를 직접 지정")
    args = ap.parse_args()

    key = (settings.KMA_SERVICE_KEY or "").strip()
    if not key:
        print("KMA_SERVICE_KEY가 비어 있습니다. .env를 확인하세요.")
        return

    region = args.region
    lat, lon = REGIONS[region]
    nx, ny = dfs_xy_conv(lat, lon)
    base_date, base_time = _base_datetime()

    print(f"지역   {region}  ({lat}, {lon})")
    print(f"격자   nx={nx} ny={ny}")
    print(f"발표   {base_date} {base_time}")
    print(f"키     {key[:8]}… (길이 {len(key)})")

    # ① 기상청 초단기실황 — 기온·습도
    show("① 초단기실황 (기온 T1H, 습도 REH)", KMA_NCST, {
        "serviceKey": key, "pageNo": 1, "numOfRows": 10, "dataType": "JSON",
        "base_date": base_date, "base_time": base_time, "nx": nx, "ny": ny,
    })

    # ② 생활기상지수 자외선
    #
    # 발표는 하루 두 번(06시, 18시)이다. 지금 시각 기준으로 가장 최근
    # 발표를 고른다. 응답은 h0(현재), h3, h6 … 형태의 예측값이다.
    now = datetime.now(KST)
    hour = 18 if now.hour >= 18 else (6 if now.hour >= 6 else 18)
    day = now if now.hour >= 6 else now - timedelta(days=1)
    uv_time = f"{day:%Y%m%d}{hour:02d}"

    show(f"② 자외선지수 (time={uv_time})", KMA_UV, {
        "serviceKey": key, "pageNo": 1, "numOfRows": 10, "dataType": "JSON",
        "areaNo": args.area or AREA_NO[region],
        "time": uv_time,
    })

    # ③ 에어코리아 측정소별 실시간
    show("③ 대기오염 측정소별 실시간 (pm25Value)", AIR, {
        "serviceKey": key, "returnType": "json", "numOfRows": 3, "pageNo": 1,
        "stationName": args.station or STATION[region],
        "dataTerm": "DAILY", "ver": "1.3",
    })

    print()
    print("=" * 78)
    print("확인할 것")
    print("=" * 78)
    print("  ① items.item 안에 category T1H / REH 가 있는가")
    print("  ② item 안에 h0 (또는 today0) 같은 시간별 자외선 값이 있는가")
    print("     areaNo가 틀리면 items가 비거나 오류 코드가 온다")
    print("  ③ item[0]에 pm25Value / pm10Value 가 있는가")
    print("     측정소 이름이 틀리면 items가 빈다. --station 으로 다시 시도")
    print()
    print("  인증 오류(SERVICE_KEY_IS_NOT_REGISTERED_ERROR)가 나면")
    print("  .env의 키가 '인코딩된 키'일 가능성이 크다. 디코딩된 키를 넣는다.")


if __name__ == "__main__":
    main()