"""
ESP32 없이 수집 파이프라인을 검증하는 mock 전송기.

부품 도착 전에 서버·DB 경로를 끝까지 확인하기 위한 개발 스크립트다.
실제 펌웨어와 동일한 JSON 형식·헤더를 사용하므로, 이 스크립트가 통과하면
ESP32 쪽에서 남는 변수는 Wi-Fi 연결과 센서 값뿐이다.

환경 노드(storage·ambient):
    # 단건 전송 (지금 시각)
    python -m scripts.mock_iot_sender --node storage-01

    # 과거 3일치를 10분 간격으로 생성해 일괄 전송 (버퍼 재전송 시뮬레이션)
    python -m scripts.mock_iot_sender --node storage-01 --days 3

    # 중복 무시 동작 확인 — 같은 명령을 두 번 실행하면 두 번째는 inserted=0

측정 노드(measure) — 광학 측정 한 번을 끝까지:
    # 세션 생성부터 결과 확인까지 혼자 한다 (노드도 키오스크도 없이)
    python -m scripts.mock_iot_sender --node measure-01 --optical \
        --user <user_id> --product <user_product_id>

    # 같은 명령을 한 번 더 실행하면 두 번째부터는 변화율이 나온다.
    # --drift 8 을 주면 처음 잰 색보다 8% 누렇게 변한 시료를 흉내 낸다.

    # 노드 역할만 한다. 사람이 키오스크에서 "측정"을 누르기를 기다린다
    python -m scripts.mock_iot_sender --node measure-01 --optical

    # 포화 거부 동작 확인 — 세션이 failed로 닫히는지 본다
    python -m scripts.mock_iot_sender --node measure-01 --optical \
        --user <user_id> --product <user_product_id> --saturate
"""
from __future__ import annotations

import argparse
import math
import random
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from config import settings

import httpx

DEFAULT_BASE = "http://localhost:8000"
INTERVAL_MIN = 10

# 백색 표준판을 잰 값. AS7341 게인 64x·LED 10mA에서 포화(65535)에 닿지 않는
# 수준으로 잡았다. 채널별로 값이 다른 것은 표준판이 아니라 LED의 스펙트럼과
# 센서 감도 때문이다. 그래서 시료를 이 값으로 나누면 둘 다 상쇄된다.
_WHITE = {
    "F1": 18000, "F2": 21000, "F3": 24000, "F4": 26000,
    "F5": 27000, "F6": 26000, "F7": 25000, "F8": 23000,
    "CLEAR": 52000, "NIR": 16000,
}

# 시료의 반사율. 살구빛 크림을 가정했다. 파란 쪽(F1~F3)이 낮고
# 붉은 쪽(F6~F8)이 높은 것이 색이 있는 제형의 전형적인 모양이다.
_REFLECT = {
    "F1": 0.62, "F2": 0.66, "F3": 0.71, "F4": 0.78,
    "F5": 0.83, "F6": 0.86, "F7": 0.88, "F8": 0.89,
    "CLEAR": 0.80, "NIR": 0.85,
}

# 재장착 반복성 실측(AS7341_BringUp의 m 명령)에서 나온 수준의 흔들림.
# 이것보다 작은 변화는 측정으로 구분할 수 없으므로, 여기서도 넣어 둔다.
_NOISE_PCT = 0.8

# 노화는 파란 쪽 반사율이 먼저 떨어진다(누레진다). --drift를 그 방향으로 준다.
_DRIFT_WEIGHT = {"F1": 1.0, "F2": 0.9, "F3": 0.7, "F4": 0.4,
                 "F5": 0.2, "F6": 0.0, "F7": 0.0, "F8": 0.0}


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


# ── 광학 측정 ────────────────────────────────────────────────────

def _jitter(value: float) -> float:
    """측정 흔들림. 실제 노드에서 재장착할 때 생기는 만큼 흔든다."""
    return value * (1.0 + random.uniform(-_NOISE_PCT, _NOISE_PCT) / 100.0)


def _white_channels() -> Dict[str, float]:
    return {k: round(_jitter(v), 1) for k, v in _WHITE.items()}


def _sample_channels(drift_pct: float) -> Dict[str, float]:
    """
    시료 채널값. drift_pct만큼 파란 쪽 반사율이 떨어진 것으로 만든다.

    모든 채널을 똑같이 줄이지 않는 이유: 그렇게 하면 반사율 비가 그대로
    유지되어 delta_pct가 0에 가깝게 나온다. 실제 변색은 스펙트럼의
    모양이 바뀌는 것이고, 우리가 잡으려는 것도 그 모양 변화다.
    """
    out: Dict[str, float] = {}
    for k, white in _WHITE.items():
        r = _REFLECT[k] * (1.0 - drift_pct / 100.0 * _DRIFT_WEIGHT.get(k, 0.0))
        out[k] = round(_jitter(white * r), 1)
    return out


def _open_session(
    client: httpx.Client, base: str, user_id: str, product_id: str, node_id: str
) -> str:
    """키오스크가 하는 일 ①. 세션을 열고 id를 받는다."""
    res = client.post(
        f"{base}/api/care/measure/sessions",
        params={"user_id": user_id},
        json={"user_product_id": product_id, "node_id": node_id},
    )
    if res.status_code != 200:
        raise SystemExit(f"세션 생성 실패 [{res.status_code}] {res.text}")
    data = res.json()
    print(f"  세션 {data['session_id']}  노드={data['node_id']}")
    print(f"  {'첫 측정입니다 (기준값이 됩니다)' if not data['has_baseline'] else '기준값이 있습니다'}")
    print(f"  {data['optical_note']}")
    return data["session_id"]


def _capture(
    client: httpx.Client, base: str, user_id: str, session_id: str
) -> None:
    """
    키오스크가 하는 일 ②. "올려놓았으니 재세요".

    노드는 측정부에 무엇이 올라와 있는지 알 수 없다. 이 신호가 있어야
    비로소 잰다. 한 세션에 백색·시료 두 번 부른다.
    """
    res = client.post(
        f"{base}/api/care/measure/sessions/{session_id}/capture",
        params={"user_id": user_id},
    )
    if res.status_code != 200:
        raise SystemExit(f"측정 지시 실패 [{res.status_code}] {res.text}")
    print(f"  [키오스크] 측정 누름 → {res.json()['status']}")


def _wait_for_step(
    client: httpx.Client, base: str, node_id: str, headers: Dict[str, str],
    timeout_sec: int,
) -> tuple:
    """
    노드가 하는 일. 지시가 내려올 때까지 폴링한다.

    세션이 열려 있어도 사용자가 아직 누르지 않았으면 step이 비어 있고,
    그동안 노드는 아무것도 하지 않는다.
    """
    deadline = time.time() + timeout_sec
    poll = 2
    announced = False
    while time.time() < deadline:
        res = client.get(f"{base}/api/iot/nodes/{node_id}/session", headers=headers)
        if res.status_code != 200:
            raise SystemExit(f"세션 폴링 실패 [{res.status_code}] {res.text}")
        data = res.json()
        poll = data.get("poll_sec") or poll
        if data.get("step"):
            return data["session_id"], data["step"]
        if not announced:
            print(f"  [노드] 지시 대기 중… (최대 {timeout_sec}초)")
            announced = True
        time.sleep(poll)
    raise SystemExit("측정 지시가 오지 않아 종료합니다.")


def _post_sample(
    client: httpx.Client, base: str, session_id: str, node_id: str,
    step: str, channels: Dict[str, float], headers: Dict[str, str],
    saturated: bool = False,
) -> Dict[str, Any]:
    body = {
        "node_id": node_id,
        "step": step,
        "ts": datetime.now(timezone.utc).isoformat(),
        "channels": channels,
        "saturated": saturated,
        # 백색과 시료는 같은 조건이어야 한다. 서버가 이 둘을 대조해
        # 다르면 세션을 실패로 닫는다.
        "gain": "64x",
        "led_ma": 10,
        "dark_applied": True,
        "fw": "mock",
    }
    res = client.post(
        f"{base}/api/iot/sessions/{session_id}/samples", json=body, headers=headers)
    if res.status_code != 200:
        raise SystemExit(f"{step} 전송 실패 [{res.status_code}] {res.text}")
    data = res.json()
    print(f"  {step:<6} → status={data['status']}  {data['message']}")
    return data


def run_optical(args: argparse.Namespace) -> None:
    """
    광학 측정 한 번을 처음부터 끝까지 흉내 낸다.

    --user/--product를 주면 키오스크 역할까지 겸해 세션을 열고 측정도 지시한다.
    주지 않으면 노드 역할만 하고, 사람이 키오스크에서 누르기를 기다린다.
    """
    base = args.base.rstrip("/")
    headers = {"X-Node-Key": args.key} if args.key else {}
    kiosk = bool(args.user and args.product)

    with httpx.Client(timeout=30) as client:
        session_id = None
        if kiosk:
            session_id = _open_session(
                client, base, args.user, args.product, args.node)
        elif args.user or args.product:
            raise SystemExit("--user와 --product는 함께 주어야 합니다.")

        # 백색 표준판 → 시료. 각 단계는 사용자가 키오스크에서 누를 때 시작된다.
        for expected in ("white", "sample"):
            if kiosk:
                _capture(client, base, args.user, session_id)

            session_id, step = _wait_for_step(
                client, base, args.node, headers, args.wait)
            if step != expected:
                raise SystemExit(f"{expected} 차례인데 서버는 {step}을 요구합니다.")

            if step == "white":
                channels = _white_channels()
            else:
                channels = _sample_channels(args.drift)
                if args.saturate:
                    # 포화한 측정을 흉내 낸다. 서버가 세션을 failed로 닫아야 한다.
                    channels = {k: 65535.0 for k in channels}

            ack = _post_sample(client, base, session_id, args.node, step,
                               channels, headers, saturated=args.saturate)
            if ack["status"] == "failed":
                break

        if not kiosk:
            return

        # 키오스크가 결과를 읽는 자리.
        res = client.get(f"{base}/api/care/measure/sessions/{session_id}",
                         params={"user_id": args.user})
        if res.status_code != 200:
            raise SystemExit(f"결과 조회 실패 [{res.status_code}] {res.text}")
        data = res.json()
        print(f"\n  결과  status={data['status']}")
        if data.get("baseline"):
            print("  이번 측정이 기준값이 되었습니다. 변화율은 다음 측정부터 나옵니다.")
        elif data.get("delta_pct") is not None:
            print(f"  변화율 {data['delta_pct']}%")
        print(f"  {data['message']}")


# ── 환경 측정값 ──────────────────────────────────────────────────

def run_readings(args: argparse.Namespace) -> None:
    node_type = args.type or args.node.split("-")[0]
    url = args.url or f"{args.base.rstrip('/')}/api/iot/readings"

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
                url,
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


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--node", required=True, help="node_id (예: storage-01)")
    p.add_argument("--type", default=None, help="storage | ambient | measure (기본: node_id에서 추론)")
    p.add_argument("--days", type=float, default=0, help="과거 N일치 생성. 0이면 현재 1건")
    p.add_argument("--base", default=DEFAULT_BASE, help="서버 주소")
    p.add_argument("--url", default=None, help="readings 엔드포인트 직접 지정 (기본: --base에서 유도)")
    p.add_argument("--key", default="", help="X-Node-Key 값")
    p.add_argument(
        "--max-batch", type=int, default=settings.IOT_MAX_BATCH,
        help="1회 전송 최대 건수 (기본값: 서버 IOT_MAX_BATCH)",
    )

    g = p.add_argument_group("광학 측정 (measure 노드)")
    g.add_argument("--optical", action="store_true", help="광학 측정 세션을 수행한다")
    g.add_argument("--user", default=None, help="세션을 직접 열 때의 user_id")
    g.add_argument("--product", default=None, help="세션을 직접 열 때의 user_product_id")
    g.add_argument("--drift", type=float, default=0.0,
                   help="파란 쪽 반사율을 몇 %% 떨어뜨릴지 (누레짐, 기본 0). "
                        "delta_pct는 여덟 채널 평균이라 이 값보다 작게 나온다")
    g.add_argument("--saturate", action="store_true",
                   help="포화한 측정을 보내 세션이 거부되는지 확인")
    g.add_argument("--wait", type=int, default=120,
                   help="키오스크에서 측정을 누를 때까지 기다릴 시간(초)")

    args = p.parse_args()

    if args.optical:
        run_optical(args)
    else:
        run_readings(args)


if __name__ == "__main__":
    main()
