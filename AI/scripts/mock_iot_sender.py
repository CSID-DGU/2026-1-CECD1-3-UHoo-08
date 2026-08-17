"""
ESP32 없이 수집 파이프라인을 검증하는 mock 전송기.

부품 도착 전에 서버·DB 경로를 끝까지 확인하기 위한 개발 스크립트다.
실제 펌웨어와 동일한 JSON 형식·헤더를 사용하므로, 이 스크립트가 통과하면
ESP32 쪽에서 남는 변수는 Wi-Fi 연결과 센서 값뿐이다.

사용법:
    # 단건 전송 (지금 시각)
    python -m scripts.mock_iot_sender --node storage-01

    # 과거 3일치를 10분 간격으로 생성해 일괄 전송 (버퍼 재전송 시뮬레이션)
    python -m scripts.mock_iot_sender --node storage-01 --days 3

    # 중복 무시 동작 확인 — 같은 명령을 두 번 실행하면 두 번째는 inserted=0
"""
from __future__ import annotations

import argparse
import math
import random
from datetime import datetime, timedelta, timezone
from config import settings

import httpx

DEFAULT_URL = "http://localhost:8000/api/iot/readings"
INTERVAL_MIN = 10


def _synthesize(node_type: str, ts: datetime) -> dict:
    """
    시각에 따라 그럴듯한 값을 만든다.

    일주기를 sin으로 넣어 낮에 덥고 밤에 서늘한 패턴을 만든다.
    ERL 열이력 적산이 실제로 동작하는지 보려면 온도가 흔들려야 하기 때문이다.
    """
    hour = ts.hour + ts.minute / 60
    daily = math.sin((hour - 9) / 24 * 2 * math.pi)

    reading = {"ts": ts.isoformat()}

    if node_type == "storage":
        reading["temperature"] = round(26.0 + daily * 4.0 + random.uniform(-0.3, 0.3), 2)
        reading["humidity"] = round(45.0 - daily * 6.0 + random.uniform(-1, 1), 2)
        # 가스 저항은 온도가 오르면 내려간다. 회귀 보정 대상이 되는 그 관계.
        reading["gas_resistance"] = round(
            90000 - (reading["temperature"] - 26.0) * 3000 + random.uniform(-800, 800), 1
        )
    elif node_type == "ambient":
        reading["temperature"] = round(24.0 + daily * 3.0 + random.uniform(-0.3, 0.3), 2)
        reading["humidity"] = round(38.0 - daily * 5.0 + random.uniform(-1, 1), 2)
        reading["pm25"] = round(max(0, 18 + daily * 10 + random.uniform(-5, 5)), 1)
    else:
        reading["temperature"] = round(24.5 + random.uniform(-0.5, 0.5), 2)
        reading["humidity"] = round(40.0 + random.uniform(-2, 2), 2)

    return reading


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--node", required=True, help="node_id (예: storage-01)")
    p.add_argument("--type", default=None, help="storage | ambient | measure (기본: node_id에서 추론)")
    p.add_argument("--days", type=float, default=0, help="과거 N일치 생성. 0이면 현재 1건")
    p.add_argument("--url", default=DEFAULT_URL)
    p.add_argument("--key", default="", help="X-Node-Key 값")
    p.add_argument(
        "--max-batch", type=int, default=settings.IOT_MAX_BATCH,
        help="1회 전송 최대 건수 (기본값: 서버 IOT_MAX_BATCH)",
    )
    args = p.parse_args()

    node_type = args.type or args.node.split("-")[0]

    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    now -= timedelta(minutes=now.minute % INTERVAL_MIN)

    if args.days > 0:
        count = int(args.days * 24 * 60 / INTERVAL_MIN)
        stamps = [now - timedelta(minutes=INTERVAL_MIN * i) for i in range(count - 1, -1, -1)]
    else:
        stamps = [now]

    readings = [_synthesize(node_type, ts) for ts in stamps]

    headers = {"X-Node-Key": args.key} if args.key else {}

    # 서버 배치 상한(IOT_MAX_BATCH)에 맞춰 나눠 보낸다.
    total_recv = total_ins = 0
    with httpx.Client(timeout=30) as client:
        for i in range(0, len(readings), args.max_batch):
            chunk = readings[i : i + args.max_batch]
            res = client.post(
                args.url,
                json={"node_id": args.node, "readings": chunk},
                headers=headers,
            )
            if res.status_code != 200:
                print(f"[{res.status_code}] {res.text}")
                return
            data = res.json()
            total_recv += data["received"]
            total_ins += data["inserted"]
            print(
                f"  batch {i // args.max_batch + 1}: "
                f"received={data['received']} inserted={data['inserted']}"
            )

    print(
        f"\n{args.node} ({node_type})  received={total_recv}  "
        f"inserted={total_ins}  duplicates={total_recv - total_ins}"
    )

if __name__ == "__main__":
    main()