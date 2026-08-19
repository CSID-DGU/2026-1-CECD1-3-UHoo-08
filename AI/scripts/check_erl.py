"""
실측 sensor_readings로 열이력 적산을 검산한다.

화장대 노드가 상시 가동 중이므로, 합성 데이터가 아니라 진짜 데이터에서
숫자가 말이 되는지 눈으로 확인하는 것이 목적이다.

사용:
    cd AI
    python -m scripts.check_erl                     # 전체 노드 요약
    python -m scripts.check_erl --node storage-01   # 특정 노드 상세
    python -m scripts.check_erl --node storage-01 --days 3
"""
from __future__ import annotations

import argparse

from datetime import datetime, timedelta, timezone

from db.iot.reader import get_reading_span, get_readings, list_nodes
from services.iot.erl import HOURS_PER_MONTH, accumulate, thermal_load


def _fmt_ts(v) -> str:
    return str(v).replace("T", " ")[:16] if v else "-"


def summarize_nodes() -> None:
    nodes = list_nodes()
    if not nodes:
        print("등록된 노드가 없습니다. 011_seed_iot_nodes.sql을 확인하세요.")
        return

    print(f"{'node_id':<14}{'type':<10}{'위치':<12}{'건수':>7}  수집 구간")
    print("-" * 78)
    for n in nodes:
        span = get_reading_span(n["node_id"])
        if span is None:
            print(f"{n['node_id']:<14}{n['node_type']:<10}"
                  f"{(n.get('location_label') or '-'):<12}{0:>7}  (데이터 없음)")
            continue
        print(f"{n['node_id']:<14}{n['node_type']:<10}"
              f"{(n.get('location_label') or '-'):<12}{span['count']:>7}  "
              f"{_fmt_ts(span['first_ts'])} ~ {_fmt_ts(span['last_ts'])}")


def detail(node_id: str, days: int | None) -> None:
    since = None
    if days:
        since = datetime.now(timezone.utc) - timedelta(days=days)

    rows = get_readings(node_id, since=since)
    if not rows:
        print(f"{node_id}: 해당 구간에 데이터가 없습니다.")
        return

    hist = accumulate(rows)

    print(f"\n=== {node_id} 열이력 ===")
    print(f"  측정 건수      {hist.sample_n}")
    print(f"  구간           {_fmt_ts(hist.first_ts)} ~ {_fmt_ts(hist.last_ts)}")
    print(f"  온도           평균 {hist.mean_temp_c:.1f}℃  "
          f"최저 {hist.min_temp_c:.1f}℃  최고 {hist.max_temp_c:.1f}℃")
    print(f"  적산 실시간    {hist.wall_hours:.1f}h ({hist.wall_hours / 24:.2f}일)")
    print(f"  결측 제외      {hist.gap_hours:.1f}h ({hist.gap_hours / 24:.2f}일)")
    print(f"  유효 경과      {hist.effective_hours:.1f}h ({hist.effective_days:.2f}일)")
    print(f"  가속 계수      {hist.acceleration:.3f}배")

    # 평균 온도로만 계산했을 때와의 차이 — 적산이 필요한 이유의 실측 근거
    from services.iot.erl import acceleration_factor
    naive = acceleration_factor(hist.mean_temp_c)
    print(f"  평균온도 근사  {naive:.3f}배  → 적산 대비 "
          f"{(hist.acceleration / naive - 1) * 100:+.2f}% 차이")

    print("\n  성분군별 소모 (이 구간만)")
    print(f"    {'성분군':<8}{'k':>5}{'소모(개월)':>12}")
    for label, sens in [("고민감", "high"), ("중민감", "medium"),
                        ("일반", "normal"), ("저민감", "low")]:
        load = thermal_load(rows, sensitivity=sens)
        print(f"    {label:<8}{load.k:>5.1f}{load.consumed_hours / HOURS_PER_MONTH:>12.3f}")


def main() -> None:
    ap = argparse.ArgumentParser(description="열이력 적산 실측 검산")
    ap.add_argument("--node", help="노드 ID. 생략하면 전체 요약")
    ap.add_argument("--days", type=int, help="최근 N일만")
    args = ap.parse_args()

    if args.node:
        detail(args.node, args.days)
    else:
        summarize_nodes()


if __name__ == "__main__":
    main()