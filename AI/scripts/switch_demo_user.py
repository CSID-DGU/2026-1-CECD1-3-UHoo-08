"""
시연 데이터를 다른 사용자로 옮긴다.
"""
from __future__ import annotations

import argparse

from db.supabase_client import get_supabase

OLD_USER = "aa000000-0000-0000-0000-000000000001"


def main() -> None:
    ap = argparse.ArgumentParser(description="시연 데이터 사용자 이전")
    ap.add_argument("--from", dest="src", default=OLD_USER)
    ap.add_argument("--to", dest="dst", required=True)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    sb = get_supabase()

    # 대상 사용자가 실제로 있는지 먼저 본다. 없는 id로 옮기면 FK 위반이
    # 나거나, 더 나쁘게는 조용히 0행이 바뀌고 성공한 것처럼 보인다.
    user = (sb.table("users").select("id, name, provider")
            .eq("id", args.dst).limit(1).execute()).data
    if not user:
        print(f"users에 {args.dst} 가 없습니다.")
        print("카카오 로그인을 한 번 하면 users에 행이 생깁니다.")
        return

    u = user[0]
    print(f"이전 대상  {u['id']}")
    print(f"           {u.get('name')} ({u.get('provider')})")
    print(f"출발       {args.src}")
    print(f"모드       {'APPLY' if args.apply else 'DRY-RUN'}")

    nodes = (sb.table("iot_nodes").select("node_id, node_type, location_label")
             .eq("user_id", args.src).execute()).data or []
    skins = (sb.table("skin_measurements").select("id", count="exact")
             .eq("user_id", args.src).execute())
    skin_n = skins.count or 0

    print()
    print("=" * 70)
    print(f"① 노드 {len(nodes)}개")
    print("=" * 70)
    for n in nodes:
        print(f"  {n['node_id']:<14}{n.get('node_type'):<10}{n.get('location_label')}")
    if not nodes:
        print("  없음")

    print()
    print("=" * 70)
    print(f"② 피부 측정 {skin_n}건")
    print("=" * 70)

    # 새 사용자가 이미 가진 것도 보여준다. 겹치면 목록이 두 배가 된다.
    own_nodes = (sb.table("iot_nodes").select("node_id", count="exact")
                 .eq("user_id", args.dst).execute()).count or 0
    own_products = (sb.table("user_products").select("id", count="exact")
                    .eq("user_id", args.dst).execute()).count or 0
    print()
    print("=" * 70)
    print("③ 대상 사용자가 이미 가진 것")
    print("=" * 70)
    print(f"  노드 {own_nodes}개 · 보유 제품 {own_products}개")
    if own_products:
        print("  → 제품이 이미 있습니다. seed_care_demo는 빈 칸만 채우므로")
        print("     기존 제품을 지우지 않습니다.")

    if not args.apply:
        print()
        print("=" * 70)
        print("DRY-RUN — 아무것도 바꾸지 않았습니다")
        print("=" * 70)
        print("  --apply 를 붙이면 노드와 피부 측정의 소유자를 바꿉니다.")
        return

    print()
    print("=" * 70)
    print("적용")
    print("=" * 70)

    if nodes:
        (sb.table("iot_nodes").update({"user_id": args.dst})
         .eq("user_id", args.src).execute())
        print(f"  iot_nodes {len(nodes)}개 이전 완료")

    if skin_n:
        (sb.table("skin_measurements").update({"user_id": args.dst})
         .eq("user_id", args.src).execute())
        print(f"  skin_measurements {skin_n}건 이전 완료")

    print()
    print("  다음 순서로 제품과 시계열을 채우세요.")
    print(f"    python -m scripts.seed_care_demo --user {args.dst} --apply")
    print(f"    python -m scripts.seed_demo_timeseries --user {args.dst} --apply")
    print(f"    python -m scripts.inspect_care_data --user {args.dst}")


if __name__ == "__main__":
    main()