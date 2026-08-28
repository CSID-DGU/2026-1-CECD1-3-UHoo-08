"""
점검 우선순위 계산에 필요한 데이터가 갖춰졌는지 진단한다.

risk_score는 세 가지가 다 있어야 계산된다.
    ① user_products 행 (opened_at, storage_node_id)
    ② product_thermal_profile 행 (sensitivity_k, pao_months)
    ③ storage_node_id가 가리키는 노드의 sensor_readings

하나라도 없으면 점수가 안 나오거나 왜곡된다. 시드를 쓰기 전에
지금 뭐가 있고 뭐가 비었는지부터 눈으로 확인한다.

사용:
    cd AI
    python -m scripts.inspect_care_data
    python -m scripts.inspect_care_data --user <uuid>
"""
from __future__ import annotations

import argparse

from db.iot.reader import get_care_products, get_reading_span, list_nodes

# 011 시드로 만든 테스트 사용자
DEFAULT_USER = "e3985354-0a60-4330-b7cb-b83b674c0eb0"


def _s(v, width: int, dash: str = "-") -> str:
    text = dash if v is None else str(v)
    if len(text) > width:
        text = text[: width - 1] + "…"
    return text.ljust(width)


def main() -> None:
    ap = argparse.ArgumentParser(description="점검 데이터 준비 상태 진단")
    ap.add_argument("--user", default=DEFAULT_USER)
    args = ap.parse_args()

    print("=" * 96)
    print("① 노드와 수집 현황")
    print("=" * 96)
    nodes = list_nodes()
    if not nodes:
        print("  등록된 노드가 없습니다.")
    for n in nodes:
        span = get_reading_span(n["node_id"])
        if span is None:
            print(f"  {_s(n['node_id'], 14)}{_s(n['node_type'], 10)}"
                  f"{_s(n.get('location_label'), 12)}  데이터 없음")
        else:
            print(f"  {_s(n['node_id'], 14)}{_s(n['node_type'], 10)}"
                  f"{_s(n.get('location_label'), 12)}"
                  f"{span['count']:>7}건  "
                  f"{str(span['first_ts'])[:16]} ~ {str(span['last_ts'])[:16]}")

    print()
    print("=" * 96)
    print(f"② 보유 제품 (user_id={args.user})")
    print("=" * 96)

    items = get_care_products(args.user)
    if not items:
        print("  user_products에 행이 없습니다.")
        print("  → 점검 우선순위를 계산할 대상이 없습니다. 제품 등록이 먼저입니다.")
        return

    header = (f"  {_s('제품', 22)}{_s('카테고리', 14)}{_s('개봉일', 12)}"
              f"{_s('보관노드', 12)}{_s('k', 6)}{_s('PAO', 6)}{_s('광학', 12)}")
    print(header)
    print("  " + "-" * (len(header) - 2))

    missing_profile, missing_opened, missing_node = [], [], []

    for it in items:
        label = f"{it.get('brand') or ''} {it.get('name') or '(이름없음)'}".strip()
        print(f"  {_s(label, 22)}{_s(it.get('category'), 14)}"
              f"{_s(it.get('opened_at'), 12)}{_s(it.get('storage_node_id'), 12)}"
              f"{_s(it.get('sensitivity_k'), 6)}{_s(it.get('pao_months'), 6)}"
              f"{_s(it.get('optical_grade'), 12)}")

        if not it["has_profile"]:
            missing_profile.append(label)
        if it.get("opened_at") is None:
            missing_opened.append(label)
        if it.get("storage_node_id") is None:
            missing_node.append(label)

    print()
    print("=" * 96)
    print("③ 계산 가능 여부")
    print("=" * 96)
    print(f"  보유 제품            {len(items)}개")
    print(f"  thermal_profile 없음  {len(missing_profile)}개"
          + (f"  → {', '.join(missing_profile[:5])}" if missing_profile else ""))
    print(f"  opened_at 없음        {len(missing_opened)}개"
          + (f"  → {', '.join(missing_opened[:5])}" if missing_opened else ""))
    print(f"  storage_node_id 없음  {len(missing_node)}개"
          + (f"  → {', '.join(missing_node[:5])}" if missing_node else ""))

    ready = [
        it for it in items
        if it["has_profile"] and it.get("opened_at") and it.get("storage_node_id")
    ]
    print()
    print(f"  → 지금 바로 점수 계산 가능: {len(ready)} / {len(items)}개")
    if len(ready) < 3:
        print("  → 탭1 시연에는 점수가 갈리는 제품이 최소 3개 필요합니다.")


if __name__ == "__main__":
    main()