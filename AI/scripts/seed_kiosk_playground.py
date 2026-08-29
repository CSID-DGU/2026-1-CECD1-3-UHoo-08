"""
키오스크 시연·연습용 제품 대량 시드.

    python -m scripts.seed_kiosk_playground                    # 계획만
    python -m scripts.seed_kiosk_playground --apply
    python -m scripts.seed_kiosk_playground --high 20 --low 20 --apply
    python -m scripts.seed_kiosk_playground --reset --apply    # 시드분만 제거

── 밴드를 어떻게 맞추는가 ──────────────────────────────────────────
점수를 직접 쓰지 않는다. risk_score가 계산하는 값이므로, 원하는 밴드가
나오도록 개봉일과 제품 종류를 거꾸로 잡는다.

    high    소모율이 100%를 넘도록 개봉일을 멀리 잡는다 (PAO × 1.2배 이상)
    medium  PAO의 50~80% 구간
    low     PAO의 10~30% 구간

같은 열이력을 공유하므로 개봉 경과가 곧 소모율이 된다. 실제 점수는
이탈 이벤트와 광학 측정도 함께 보므로 정확히 맞지는 않는다. 계획 출력에
예상 소모율을 함께 찍으니, 원하는 분포가 아니면 --seed를 바꿔 다시 뽑는다.

── 되돌릴 수 있게 만든다 ───────────────────────────────────────────
연습용 제품이 실제 시연에 섞이면 곤란하다. usage_type을 USING으로 넣되
opened_at을 기준으로 --reset이 이 스크립트가 넣은 것만 지운다.
사용자가 앱에서 등록한 제품은 건드리지 않는다.
"""
from __future__ import annotations

import argparse
import random
import uuid

from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from db.iot.reader import get_care_products, list_nodes
from db.supabase_client import get_supabase
from services.iot.thermal_profile import resolve_profile

DEFAULT_USER = "e3985354-0a60-4330-b7cb-b83b674c0eb0"

SEED_USAGE_TYPE = "USING"
CHUNK = 100

# 이 스크립트가 넣은 행을 알아보기 위한 표시.
#
# user_products에 메모 컬럼이 없어서, 개봉일의 "일" 자리를 고정한다.
# 28일로 넣은 것만 이 스크립트가 만든 것으로 본다. 완벽한 방법은 아니지만
# 스키마를 건드리지 않고 되돌릴 수 있는 가장 간단한 방법이다.
MARKER_DAY = 28


def _target_days(band: str, pao_months: int, k: float, rng: random.Random) -> int:
    """
    원하는 밴드가 나오도록 개봉 경과일을 정한다.

    소모율 ≈ (경과일 / 30) × k / PAO 이므로, 원하는 소모율에서 역산한다.
    열이력이 20℃보다 높으면 실제 소모율은 이보다 커진다.
    """
    ratio = {
        "high": rng.uniform(1.15, 1.9),
        "medium": rng.uniform(0.55, 0.85),
        "low": rng.uniform(0.08, 0.3),
    }[band]
    days = ratio * pao_months * 30.0 / max(k, 0.1)
    return max(3, int(days))


def _pick_products(
    need: int,
    exclude: set,
    rng: random.Random,
) -> List[Dict[str, Any]]:
    """products에서 아직 안 쓴 제품을 고른다."""
    sb = get_supabase()
    rows = (
        sb.table("products")
        .select("product_id, name, brand, category")
        .limit(600)
        .execute()
    ).data or []

    pool = [r for r in rows if r["product_id"] not in exclude]
    rng.shuffle(pool)
    return pool[:need]


def build_plan(
    user_id: str,
    counts: Dict[str, int],
    node_id: str,
    rng: random.Random,
) -> Dict[str, Any]:
    sb = get_supabase()

    owned = (
        sb.table("user_products")
        .select("product_id")
        .eq("user_id", user_id)
        .execute()
    ).data or []
    exclude = {r["product_id"] for r in owned if r.get("product_id")}

    total = sum(counts.values())
    picked = _pick_products(total, exclude, rng)

    if len(picked) < total:
        print(f"  ! products에서 {len(picked)}개만 찾았습니다 (요청 {total}개).")

    today = date.today()
    now_iso = datetime.now(timezone.utc).isoformat()

    rows: List[Dict[str, Any]] = []
    profiles: List[Dict[str, Any]] = []
    preview: List[tuple] = []

    idx = 0
    for band, n in counts.items():
        for _ in range(n):
            if idx >= len(picked):
                break
            p = picked[idx]
            idx += 1

            prof = resolve_profile(p.get("name"), category=p.get("category"),
                                   brand=p.get("brand"))
            days = _target_days(band, prof.pao_months, prof.sensitivity_k, rng)

            # 개봉일의 "일"을 마커로 고정한다. 월을 조정해 경과일을 맞춘다.
            opened = today - timedelta(days=days)
            try:
                opened = opened.replace(day=MARKER_DAY)
            except ValueError:
                opened = opened.replace(day=MARKER_DAY - 1)

            rows.append({
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "product_id": p["product_id"],
                "usage_type": SEED_USAGE_TYPE,
                "created_at": now_iso,
                "opened_at": opened.isoformat(),
                "storage_node_id": node_id,
            })
            profiles.append(prof.as_row(p["product_id"]))

            consumed = (today - opened).days / 30.0 * prof.sensitivity_k / prof.pao_months
            preview.append((band, p.get("brand"), p.get("name"),
                            prof.sensitivity_k, prof.pao_months,
                            (today - opened).days, consumed * 100))

    return {"rows": rows, "profiles": profiles, "preview": preview}


def apply_plan(plan: Dict[str, Any]) -> None:
    sb = get_supabase()

    rows = plan["rows"]
    for i in range(0, len(rows), CHUNK):
        sb.table("user_products").insert(rows[i:i + CHUNK]).execute()
    print(f"  user_products {len(rows)}건 완료")

    profs = plan["profiles"]
    for i in range(0, len(profs), CHUNK):
        (sb.table("product_thermal_profile")
         .upsert(profs[i:i + CHUNK], on_conflict="product_id").execute())
    print(f"  product_thermal_profile {len(profs)}건 완료")


def reset(user_id: str) -> None:
    """
    이 스크립트가 넣은 것만 지운다.

    개봉일이 MARKER_DAY인 행만 지우므로, 사용자가 앱에서 등록한 제품이나
    seed_care_demo가 승격한 제품은 남는다.
    """
    sb = get_supabase()
    rows = (
        sb.table("user_products")
        .select("id, opened_at")
        .eq("user_id", user_id)
        .eq("usage_type", SEED_USAGE_TYPE)
        .execute()
    ).data or []

    targets = [r["id"] for r in rows
               if r.get("opened_at") and str(r["opened_at"])[8:10] == f"{MARKER_DAY:02d}"]

    if not targets:
        print("  지울 연습용 제품이 없습니다.")
        return

    for i in range(0, len(targets), CHUNK):
        chunk = targets[i:i + CHUNK]
        # 확인 이력이 FK로 걸려 있으면 먼저 지운다.
        sb.table("user_feedback").delete().in_("user_product_id", chunk).execute()
        sb.table("optical_measurements").delete().in_("user_product_id", chunk).execute()
        sb.table("optical_baselines").delete().in_("user_product_id", chunk).execute()
        sb.table("user_products").delete().in_("id", chunk).execute()

    print(f"  연습용 제품 {len(targets)}건 삭제 완료")


def main() -> None:
    ap = argparse.ArgumentParser(description="키오스크 연습용 제품 대량 시드")
    ap.add_argument("--user", default=DEFAULT_USER)
    ap.add_argument("--node", default=None, help="보관 노드. 생략하면 첫 storage 노드")
    ap.add_argument("--high", type=int, default=20, help="확인 필요 밴드 개수")
    ap.add_argument("--medium", type=int, default=15, help="지켜보기 밴드 개수")
    ap.add_argument("--low", type=int, default=20, help="정상 범위 개수")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--reset", action="store_true")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    rng = random.Random(args.seed)

    if args.reset:
        print(f"사용자 {args.user}")
        if not args.apply:
            print("  --apply 를 함께 붙여야 삭제합니다.")
            return
        reset(args.user)
        return

    nodes = list_nodes()
    node_id = args.node
    if not node_id:
        storage = [n for n in nodes if n.get("node_type") == "storage"]
        if not storage:
            print("storage 노드가 없습니다. --node로 지정하세요.")
            return
        node_id = storage[0]["node_id"]

    counts = {"high": args.high, "medium": args.medium, "low": args.low}

    print(f"사용자   {args.user}")
    print(f"보관노드 {node_id}")
    print(f"목표     확인 필요 {args.high} · 지켜보기 {args.medium} · 정상 {args.low}")
    print(f"모드     {'APPLY' if args.apply else 'DRY-RUN'}")

    existing = len(get_care_products(args.user))
    print(f"현재     점검 대상 {existing}개")

    plan = build_plan(args.user, counts, node_id, rng)

    print()
    print("=" * 92)
    print("생성할 제품")
    print("=" * 92)
    print(f"  {'밴드':<8}{'제품':<38}{'k':>5}{'PAO':>5}{'개봉':>7}{'예상 소모율':>12}")
    print("  " + "-" * 88)

    by_band: Dict[str, int] = {}
    for band, brand, name, k, pao, days, consumed in plan["preview"]:
        by_band[band] = by_band.get(band, 0) + 1
        label = f"{brand or ''} {name or ''}".strip()
        if len(label) > 36:
            label = label[:35] + "…"
        print(f"  {band:<8}{label:<38}{k:>5}{pao:>5}{days:>6}일{consumed:>11.0f}%")

    print()
    print(f"  밴드별 {by_band}")
    print()
    print("  예상 소모율은 20℃ 항온 가정입니다. 실제 점수는 이탈 이벤트와")
    print("  광학 측정도 함께 보므로 이보다 높게 나옵니다.")

    if not args.apply:
        print()
        print("=" * 92)
        print("DRY-RUN — 아무것도 쓰지 않았습니다")
        print("=" * 92)
        print(f"  반영할 제품 {len(plan['rows'])}개")
        print("  실행하려면 --apply 를 붙이세요.")
        return

    print()
    print("=" * 92)
    print("적용")
    print("=" * 92)
    apply_plan(plan)
    print()
    print("  다음으로 시계열을 다시 돌려 광학 데이터를 채우세요.")
    print(f"    python -m scripts.seed_demo_timeseries --user {args.user} --apply")


if __name__ == "__main__":
    main()