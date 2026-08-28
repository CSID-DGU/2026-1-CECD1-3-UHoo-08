"""
REGIONS에 등록된 지역 코드가 실제로 통하는지 한 번에 확인한다.

    python -m scripts.check_region_codes
    python -m scripts.check_region_codes --only 강원,전북

에어코리아는 일 500회 제한이다. 지역 하나당 1회를 쓴다.
"""
from __future__ import annotations

import argparse
import time

from services.iot.weather import (
    REGIONS, dfs_xy_conv, fetch_air, fetch_kma_current, fetch_uv,
)
from config import settings


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=None, help="쉼표로 구분한 지역 이름")
    ap.add_argument("--skip-air", action="store_true",
                    help="에어코리아 호출을 건너뛴다 (일 500회 제한 절약)")
    args = ap.parse_args()

    if not (settings.KMA_SERVICE_KEY or "").strip():
        print("KMA_SERVICE_KEY가 비어 있습니다.")
        return

    names = ([n.strip() for n in args.only.split(",")] if args.only
             else list(REGIONS))

    print(f"  {'지역':<6}{'격자':<12}{'기온':<10}{'자외선':<12}{'미세먼지':<20}")
    print("  " + "-" * 62)

    bad = []
    for name in names:
        cfg = REGIONS.get(name)
        if not cfg:
            print(f"  {name:<6} 표에 없는 지역")
            continue

        # 조회에는 공식 파일의 격자를 쓴다. 변환식 결과와 다르면 표에
        # 함께 찍는다. 좌표를 잘못 적어 넣은 경우가 그렇게 드러난다.
        nx, ny = cfg["grid"]
        calc = dfs_xy_conv(cfg["lat"], cfg["lon"])
        grid_txt = f"{nx},{ny}" if calc == (nx, ny) else f"{nx},{ny}≠{calc[0]},{calc[1]}"

        kma = fetch_kma_current(cfg["grid"])
        temp = f"{kma['temperature']:.0f}℃" if kma and kma.get("temperature") is not None else "실패"

        uv = fetch_uv(cfg["area_no"])
        uv_txt = f"{uv['uv_index']:.0f} ({uv['slot']})" if uv else "실패"

        if args.skip_air:
            air_txt = "건너뜀"
        else:
            air = fetch_air(cfg["sido"])
            air_txt = (f"{air['pm25']:.0f} ㎍/m³ ({air['station_n']}곳)"
                       if air else "실패")
            # 연속 호출로 서버에 부담을 주지 않는다. 504가 잦은 API다.
            time.sleep(0.4)

        if not kma or not uv or (not args.skip_air and air_txt == "실패"):
            bad.append(name)

        print(f"  {name:<6}{grid_txt:<12}{temp:<10}{uv_txt:<12}{air_txt:<20}")

    print()
    if bad:
        print(f"  확인이 필요한 지역: {', '.join(bad)}")
        print("  · 자외선 실패 → areaNo가 틀렸다. 기상청 지역코드표에서 다시 찾는다")
        print("  · 미세먼지 실패 → sidoName 표기이거나 서버 지연이다. 다시 실행해 본다")
    else:
        print(f"  {len(names)}곳 모두 정상입니다.")


if __name__ == "__main__":
    main()