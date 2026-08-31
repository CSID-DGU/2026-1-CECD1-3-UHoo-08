"""
시연 상태 초기화.

    python -m scripts.reset_demo_state                  # 계획만
    python -m scripts.reset_demo_state --apply
    python -m scripts.reset_demo_state --events --apply    # 이벤트만
    python -m scripts.reset_demo_state --checks --apply    # 확인 이력만
    python -m scripts.reset_demo_state --optical --apply   # 색 측정만
    python -m scripts.reset_demo_state --skin --apply      # 피부 측정만
    python -m scripts.reset_demo_state --optical --product <id> --apply
    python -m scripts.reset_demo_state --optical --product <id> --wipe --apply

── 무엇을 되돌리는가 ───────────────────────────────────────────────
    risk_events           user_answer를 pending으로, answered_at을 비움
    user_feedback         확인 이력 삭제
    user_products         last_checked_at을 비움
    optical_measurements  실제로 잰 색 측정만 삭제 (시드 이력은 남긴다)
    skin_measurements     〃
    measure_sessions      측정 세션 삭제

측정값(sensor_readings)과 제품 목록은 건드리지 않는다. 그건 시드가
관리하는 영역이고, 여기서는 "사용자가 눌러서 생긴 것"만 되돌린다.

── 색 측정을 왜 함께 지우는가 ──────────────────────────────────────
색 변화율은 **그 제품의 가장 오래된 측정**과 비교해서 나온다
(db/iot/writer.get_optical_baseline). 그 첫 행이 기준값이 되고, 이후
측정은 전부 그것과 견준다.

문제는 seed_demo_timeseries가 넣는 채널값이 실제 센서에서 나온 값이
아니라는 것이다. 시드의 백색 기준은 채널마다 거의 같은 평평한 값인데
(4102·4230·4180·4225), 실제 AS7341로 흰 판을 재면 LED 스펙트럼과
채널별 감도 때문에 전혀 평평하지 않다(960·2697·2027·5945). 반사율의
자릿수 자체가 달라서, 시드 기준값에 실측을 견주면 수백 %가 나온다.

그래서 실측만 지우고 시드 이력은 그대로 둔다. 제품은 시드가 만들어 둔
상태(광학 변화 16.1% 등)로 돌아가고, 시연 화면의 근거도 그대로 남는다.

시드 행은 white_ref로 알아본다. seed_demo_timeseries.SEED_WHITE_REF는
채널마다 거의 같은 평평한 값이라, 실제 센서에서는 나올 수 없는 모양이다.
그 값을 그대로 가진 행이 시드가 만든 것이다.

시드 이력이 없는 제품(직접 등록한 것)은 실측을 지우면 비게 되고, 다음
측정이 새 기준값이 된다. 그것도 "원래대로"가 맞다.

── 피부 측정도 같다 ────────────────────────────────────────────────
seed_demo_timeseries.build_skin이 "손등 안쪽"으로 24건을 만들어 둔다.
그 Lab은 채널값에서 계산한 것이 아니라 그럴듯한 숫자를 직접 적은 것이라,
실측과는 만들어진 방식이 다르다. 절대값끼리 크게 어긋나지는 않지만
"직전 대비" 변화량은 시드 마지막 값과 실측을 빼는 것이라 의미가 없다.

시드 행은 channels가 비어 있는 것으로 알아본다. 실제 노드가 보낸 측정은
원본 채널값을 함께 남기기 때문이다(017_skin_measurement_channels).
"""
from __future__ import annotations

import argparse

from db.iot.reader import list_nodes
from db.supabase_client import get_supabase
from scripts.seed_demo_timeseries import SEED_WHITE_REF

DEFAULT_USER = "e3985354-0a60-4330-b7cb-b83b674c0eb0"
CHUNK = 100


def is_seeded(row: dict) -> bool:
    """
    시드가 만든 측정인지.

    white_ref가 SEED_WHITE_REF와 같으면 시드다. 실제 센서로 흰 판을 재서
    열 채널이 모두 이 값과 소수점 단위까지 맞을 확률은 없다.
    """
    white = row.get("white_ref") or {}
    if len(white) != len(SEED_WHITE_REF):
        return False
    for k, v in SEED_WHITE_REF.items():
        try:
            if abs(float(white[k]) - v) > 0.5:
                return False
        except (KeyError, TypeError, ValueError):
            return False
    return True


def main() -> None:
    ap = argparse.ArgumentParser(description="시연 상태 초기화")
    ap.add_argument("--user", default=DEFAULT_USER)
    ap.add_argument("--events", action="store_true", help="이벤트만 되돌린다")
    ap.add_argument("--checks", action="store_true", help="확인 이력만 지운다")
    ap.add_argument("--optical", action="store_true", help="색 측정만 지운다")
    ap.add_argument("--skin", action="store_true", help="피부 측정만 지운다")
    # 제품 하나만 되돌리는 쪽이 대개 맞다. 시드 이력과 실측이 섞이면 안 되는
    # 것은 같은 제품 안에서지, 제품끼리는 서로 무관하다. 실제로 잴 제품만
    # 비우면 나머지 제품의 시연용 이력은 그대로 남는다.
    ap.add_argument("--product", default=None,
                    help="이 user_product_id의 색 측정만 지운다")
    # 되돌리기와 비우기는 목적이 다르다.
    #   기본   시연 상태로 되돌린다 — 실측만 지우고 시드 이력은 남긴다
    #   --wipe 실제로 재려고 자리를 비운다 — 시드 기준값까지 지운다
    # 시드 기준값을 남긴 채 실제로 재면 백색 기준의 모양이 달라 수백 %가
    # 나온다. 그럴 제품은 비워야 다음 측정이 새 기준값이 된다.
    ap.add_argument("--wipe", action="store_true",
                    help="시드 이력까지 모두 지운다 (실제 측정을 시작할 때)")
    ap.add_argument("--site", default=None,
                    help="이 부위의 피부 측정만 지운다 (예: \"손등 안쪽\")")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    # 아무것도 지정하지 않으면 전부.
    picked = args.events or args.checks or args.optical or args.skin
    do_events = args.events or not picked
    do_checks = args.checks or not picked
    do_optical = args.optical or not picked
    do_skin = args.skin or not picked

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

    # ── 색 측정 ──────────────────────────────────────────────────
    #
    # 보유 제품 목록은 확인 이력 쪽에서 이미 읽었을 수도 있고 아닐 수도
    # 있다. --optical만 준 경우를 위해 여기서 한 번 더 확보한다.
    opt_rows = []
    opt_ups: list = []
    sessions = 0
    if do_optical:
        if not ups:
            ups = [r["id"] for r in (
                sb.table("user_products").select("id")
                .eq("user_id", args.user).execute()
            ).data or []]

        # --product를 주면 그 제품만. 남의 제품을 지우지 않도록 보유 목록
        # 안에 있는지 먼저 확인한다.
        if args.product:
            if args.product not in ups:
                print(f"\n  ! {args.product}는 이 사용자의 제품이 아닙니다.")
                return
            opt_ups = [args.product]
        else:
            opt_ups = ups

        for i in range(0, len(opt_ups), CHUNK):
            opt_rows += (
                sb.table("optical_measurements")
                .select("id, user_product_id, ts, delta_pct, white_ref")
                .in_("user_product_id", opt_ups[i:i + CHUNK])
                .order("ts")
                .execute()
            ).data or []

        seeded = [r for r in opt_rows if is_seeded(r)]
        real = [r for r in opt_rows if not is_seeded(r)]
        # --wipe면 시드도 지울 대상이다.
        doomed = opt_rows if args.wipe else real
        kept = [] if args.wipe else seeded

        # 세션은 제품별로 나누지 않는다. 끝난 세션은 결과가 이미
        # optical_measurements로 옮겨져 있어 남겨 둘 값이 없다.
        sessions = (
            sb.table("measure_sessions").select("id", count="exact")
            .eq("user_id", args.user).execute()
        ).count or 0

        scope = f"제품 {args.product[:8]}…" if args.product else "전체 제품"
        mode = "비우기(WIPE)" if args.wipe else "시연 상태로 되돌리기"
        print()
        print("=" * 78)
        print(f"③ 색 측정 ({scope}) — {mode}")
        print("=" * 78)
        print(f"  삭제  {len(doomed)}건"
              + (f"  (실측 {len(real)} + 시드 {len(seeded)})" if args.wipe
                 else f"  (실측만. 시드 {len(seeded)}건은 남긴다)"))
        print(f"  측정 세션 {sessions}건 삭제")

        if doomed:
            print(f"  기간  {str(doomed[0]['ts'])[:16]} ~ "
                  f"{str(doomed[-1]['ts'])[:16]}")

        # 지운 뒤 각 제품이 어떤 상태가 되는지 미리 보여준다.
        by_product: dict = {}
        for r in kept:
            by_product[str(r["user_product_id"])] = r

        if by_product:
            print(f"  되돌아갈 상태 — 제품 {len(by_product)}개")
            for up, r in list(by_product.items())[:5]:
                d = r.get("delta_pct")
                print(f"    {up[:8]}…  {str(r['ts'])[:10]}  "
                      f"광학 변화 {d if d is not None else '-'}%")
            if len(by_product) > 5:
                print(f"    … 외 {len(by_product) - 5}개")

        # 남는 측정이 하나도 없는 제품은 기준값이 사라진다.
        emptied = ({str(r["user_product_id"]) for r in doomed}
                   - set(by_product))
        if emptied:
            print(f"  기준값이 사라지는 제품 {len(emptied)}개 "
                  f"— 다음 측정이 새 기준값이 됩니다")

    # ── 피부 측정 ────────────────────────────────────────────────
    #
    # 색 측정과 같은 구조다. 시드 행은 channels가 비어 있는 것으로 알아본다.
    # 실제 노드가 보낸 측정은 원본 채널값을 함께 남기기 때문이다.
    skin_rows: list = []
    skin_doomed: list = []
    skin_kept: list = []
    if do_skin:
        q = (sb.table("skin_measurements")
             .select("id, ts, site, lab_l, lab_a, lab_b, channels")
             .eq("user_id", args.user).order("ts"))
        if args.site:
            q = q.eq("site", args.site)
        skin_rows = (q.execute()).data or []

        skin_seeded = [r for r in skin_rows if not r.get("channels")]
        skin_real = [r for r in skin_rows if r.get("channels")]
        skin_doomed = skin_rows if args.wipe else skin_real
        skin_kept = [] if args.wipe else skin_seeded

        scope = f"부위 {args.site}" if args.site else "전체 부위"
        mode = "비우기(WIPE)" if args.wipe else "시연 상태로 되돌리기"
        print()
        print("=" * 78)
        print(f"④ 피부 측정 ({scope}) — {mode}")
        print("=" * 78)
        print(f"  삭제  {len(skin_doomed)}건"
              + (f"  (실측 {len(skin_real)} + 시드 {len(skin_seeded)})" if args.wipe
                 else f"  (실측만. 시드 {len(skin_seeded)}건은 남긴다)"))

        if skin_doomed:
            print(f"  기간  {str(skin_doomed[0]['ts'])[:16]} ~ "
                  f"{str(skin_doomed[-1]['ts'])[:16]}")
        else:
            print("  지울 실측  없음")

        # 부위별로 몇 건이 남는지. 남는 것이 없으면 다음 측정이 기준선이다.
        left: dict = {}
        for r in skin_kept:
            left[r.get("site") or "(부위 없음)"] = left.get(r.get("site") or "(부위 없음)", 0) + 1
        for site, n in left.items():
            print(f"  {site}  {n}건 유지")

        emptied = ({r.get("site") for r in skin_doomed} - set(left))
        for site in sorted(x for x in emptied if x):
            print(f"  {site}  비워짐 — 다음 측정이 기준선이 됩니다")

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

    if do_optical and opt_ups:
        # 남길 행은 건드리지 않는다. id를 하나씩 짚어 지운다.
        ids = [r["id"] for r in doomed]
        for i in range(0, len(ids), CHUNK):
            (sb.table("optical_measurements").delete()
             .in_("id", ids[i:i + CHUNK]).execute())

        if args.wipe:
            # optical_baselines에는 시드만 들어간다(코드가 쓰지 않는 구 스키마).
            # 비울 때는 이쪽도 함께 지워야 흔적이 남지 않는다.
            for i in range(0, len(opt_ups), CHUNK):
                (sb.table("optical_baselines").delete()
                 .in_("user_product_id", opt_ups[i:i + CHUNK]).execute())

        (sb.table("measure_sessions").delete()
         .eq("user_id", args.user).execute())
        print(f"  색 측정 {len(ids)}건 삭제 · {len(kept)}건 유지 · "
              f"측정 세션 {sessions}건 삭제")

    if do_skin and skin_doomed:
        ids = [r["id"] for r in skin_doomed]
        for i in range(0, len(ids), CHUNK):
            (sb.table("skin_measurements").delete()
             .in_("id", ids[i:i + CHUNK]).execute())
        print(f"  피부 측정 {len(ids)}건 삭제 · {len(skin_kept)}건 유지")

    print()
    print("  키오스크를 새로고침하면 질문이 다시 나타납니다.")
    if do_skin and not args.wipe:
        print("  피부 측정도 시드가 만든 상태로 돌아갔습니다.")
        print("  실제로 잴 부위는 --skin --site 로 비우거나, 시드가 쓰지 않는")
        print("  부위(볼·이마·팔 안쪽)를 고르면 깨끗한 기준선에서 시작합니다.")

    if do_optical and not args.wipe:
        print("  색 측정은 시드가 만든 상태로 돌아갔습니다.")
        print("  이 상태에서 실제로 재면 다시 수백 %가 나옵니다. 시드 기준값과")
        print("  실측은 백색 기준의 모양이 달라 비교가 성립하지 않기 때문입니다.")
        print("  실제로 잴 제품은 --wipe로 비우세요.")
    elif do_optical or do_skin:
        print("  측정을 비웠습니다. 다음 측정이 새 기준값이 됩니다.")
        print("  백색 표준판과 제품을 각각 올려 두 번 재야 한 건이 됩니다.")


if __name__ == "__main__":
    main()