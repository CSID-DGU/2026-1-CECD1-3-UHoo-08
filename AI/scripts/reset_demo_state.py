"""
시연 상태 초기화.

    python -m scripts.reset_demo_state                 # 계획만
    python -m scripts.reset_demo_state --apply
    python -m scripts.reset_demo_state --events --apply   # 이벤트만
    python -m scripts.reset_demo_state --checks --apply   # 확인 이력만

── 무엇을 되돌리는가 ───────────────────────────────────────────────
    risk_events        user_answer를 pending으로, answer_note를 비움
    user_feedback      확인 이력 삭제
    user_products      last_checked_at을 비움

측정값(sensor_readings)과 제품 목록은 건드리지 않는다. 그건 시드가
관리하는 영역이고, 여기서는 "사용자가 눌러서 생긴 것"만 되돌린다.
"""
from __future__ import annotations

import argparse

from db.iot.reader import list_nodes
from db.supabase_client import get_supabase

DEFAULT_USER = "e3985354-0a60-4330-b7cb-b83b674c0eb0"
CHUNK = 100


def main() -> None:
    ap = argparse.ArgumentParser(description="시연 상태 초기화")
    ap.add_argument("--user", default=DEFAULT_USER)
    ap.add_argument("--events", action="store_true", help="이벤트만 되돌린다")
    ap.add_argument("--checks", action="store_true", help="확인 이력만 지운다")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    # 아무것도 지정하지 않으면 둘 다.
    do_events = args.events or not args.checks
    do_checks = args.checks or not args.events

    sb = get_supabase()

    node_ids = [n["node_id"] for n in list_nodes()
                if n.get("user_id") == args.user]

    print(f"사용자 {args.user}")
    print(f"노드   {', '.join(node_ids) if node_ids else '없음'}")
    print(f"모드   {'APPLY' if args.apply else 'DRY-RUN'}")

    # ── 이벤트 ───────────────────────────────────────────────────
    answered = []
    if do_events and node_ids:
        answered = (
            sb.table("risk_events")
            .select("id, ts, event_type, user_answer, answered_at")
            .in_("node_id", node_ids)
            .neq("user_answer", "pending")
            .order("ts", desc=True)
            .execute()
        ).data or []

        print()
        print("=" * 78)
        print(f"① 답변한 이벤트 {len(answered)}건 → pending으로")
        print("=" * 78)
        for e in answered:
            when = f" · {str(e['answered_at'])[:16]}" if e.get("answered_at") else ""
            print(f"  {e['id']:>5}  {str(e['ts'])[:16]}  {e['event_type']:<16}"
                  f"{e['user_answer']}{when}")
        if not answered:
            print("  없음")

    # ── 확인 이력 ────────────────────────────────────────────────
    ups = []
    fb_count = 0
    if do_checks:
        rows = (
            sb.table("user_products")
            .select("id, last_checked_at")
            .eq("user_id", args.user)
            .execute()
        ).data or []
        ups = [r["id"] for r in rows]
        checked = [r for r in rows if r.get("last_checked_at")]

        if ups:
            fb = (
                sb.table("user_feedback")
                .select("id", count="exact")
                .in_("user_product_id", ups[:CHUNK])
                .execute()
            )
            fb_count = fb.count or 0

        print()
        print("=" * 78)
        print(f"② 확인 이력 {fb_count}건 · 확인한 제품 {len(checked)}개")
        print("=" * 78)
        if not checked and not fb_count:
            print("  없음")

    if not args.apply:
        print()
        print("=" * 78)
        print("DRY-RUN — 아무것도 바꾸지 않았습니다")
        print("=" * 78)
        print("  --apply 를 붙이면 되돌립니다.")
        return

    print()
    print("=" * 78)
    print("적용")
    print("=" * 78)

    if do_events and answered:
        ids = [e["id"] for e in answered]
        for i in range(0, len(ids), CHUNK):
            (sb.table("risk_events")
             .update({"user_answer": "pending", "excluded": False,
                      "answered_at": None})
             .in_("id", ids[i:i + CHUNK]).execute())
        print(f"  이벤트 {len(ids)}건 되돌림")

    if do_checks and ups:
        for i in range(0, len(ups), CHUNK):
            chunk = ups[i:i + CHUNK]
            sb.table("user_feedback").delete().in_("user_product_id", chunk).execute()
            (sb.table("user_products")
             .update({"last_checked_at": None})
             .in_("id", chunk).execute())
        print(f"  확인 이력 삭제 · last_checked_at 초기화 ({len(ups)}개 제품)")

    print()
    print("  키오스크를 새로고침하면 질문이 다시 나타납니다.")


if __name__ == "__main__":
    main()