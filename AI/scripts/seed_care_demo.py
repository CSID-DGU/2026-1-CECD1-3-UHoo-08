"""
점검 시연용 데이터 보완 시드.

inspect_care_data가 "점수 계산 가능 0/2개"를 내는 원인은 셋이다.
    ① user_products.opened_at 이 비어 있다
    ② user_products.storage_node_id 가 비어 있다
    ③ product_thermal_profile 행이 없다

이 스크립트는 셋을 채운다. 기존 user_products 행은 지우지도 바꾸지도
않고 비어 있는 칸만 채우며, 제품 수가 모자랄 때만 products에서
골라 추가한다.

    python -m scripts.seed_care_demo                  # 계획만 출력 (기본)
    python -m scripts.seed_care_demo --apply          # 실제 반영
    python -m scripts.seed_care_demo --target 6 --seed 7
    python -m scripts.seed_care_demo --apply --refresh-profiles

── 왜 SQL 마이그레이션이 아니라 파이썬인가 ─────────────────────────
products.product_id가 UUID다. 마이그레이션 파일에 제품 UUID를 적어 넣으면
그 UUID가 존재하는 DB에서만 동작한다. 로컬·EC2·팀원 환경의 products가
서로 다르게 채워져 있으므로, 어느 한 곳에서 뽑은 UUID는 다른 곳에서
FK 위반이 된다. 그래서 지금 이 DB에 실제로 있는 제품을 조회해서 고르는
방식으로 간다.

── dry-run이 기본인 이유 ───────────────────────────────────────────
--apply 없이는 아무것도 쓰지 않는다. 시드는 성격상 되돌리기 번거로운
작업이고(특히 새 user_products 행), 무엇이 들어갈지 눈으로 본 뒤
실행하는 편이 안전하다.

── 개봉일은 임의로 배정한다 ────────────────────────────────────────
실제 개봉일을 모르므로 20~240일 범위에 고르게 벌려 배정한다. 배정은
--seed로 고정되는 난수이며, 점수가 잘 갈리도록 "고민감 제품에 오래된
날짜를 몰아주는" 식의 조작은 하지 않는다. 결과가 밋밋하면 seed를 바꿔
다시 뽑는 것이 정직한 방법이다.
"""
from __future__ import annotations

import argparse
import random
import uuid

from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from db.iot.reader import get_care_products, get_reading_span, list_nodes
from db.supabase_client import get_supabase
from services.iot.thermal_profile import CATEGORIES, resolve_profile

# 011 시드로 만든 테스트 사용자
DEFAULT_USER = "aa000000-0000-0000-0000-000000000001"

# 시연 목표 제품 수. 탭1에서 점수가 갈리는 모습을 보여주려면 최소 3개,
# 밴드(🔴🟡🟢)가 모두 나오려면 5개 정도가 적당하다.
DEFAULT_TARGET = 5

# 개봉 경과일 범위
MIN_OPENED_DAYS = 20
MAX_OPENED_DAYS = 240

# 새로 추가할 행의 사용 상태. reader.get_care_products가 USING/USED만
# 점검 대상으로 보므로 여기에 맞춘다. VIEWED(단순 조회)는 대상이 아니다.
SEED_USAGE_TYPE = "USING"

# 카테고리별 후보 조회 상한
POOL_PER_CATEGORY = 200


# ── 출력 도우미 ───────────────────────────────────────────────────

def _s(v: Any, width: int, dash: str = "-") -> str:
    text = dash if v in (None, "") else str(v)
    if len(text) > width:
        text = text[: width - 1] + "…"
    return text.ljust(width)


def _label(item: Dict[str, Any]) -> str:
    return f"{item.get('brand') or ''} {item.get('name') or '(이름없음)'}".strip()


def _rule(title: str) -> None:
    print()
    print("=" * 96)
    print(title)
    print("=" * 96)


# ── 노드 확인 ─────────────────────────────────────────────────────

def resolve_storage_node(preferred: Optional[str]) -> Tuple[Optional[str], Optional[dict]]:
    """
    보관 노드를 정한다.

    지정한 노드가 없으면 그냥 실패시킨다. storage_node_id에 존재하지 않는
    노드를 넣으면 FK가 없는 컬럼이라 삽입은 되지만, 나중에 readings 조회가
    0건이 되어 "왜 점수가 안 나오지"로 되돌아온다.
    """
    nodes = list_nodes()
    if not nodes:
        return None, None

    by_id = {n["node_id"]: n for n in nodes}

    if preferred:
        if preferred not in by_id:
            print(f"  ! 노드 '{preferred}'가 iot_nodes에 없습니다.")
            print(f"    등록된 노드: {', '.join(sorted(by_id))}")
            return None, None
        return preferred, by_id[preferred]

    storages = [n for n in nodes if n.get("node_type") == "storage"]
    if not storages:
        print("  ! node_type='storage'인 노드가 없습니다. --node로 직접 지정하세요.")
        return None, None
    n = storages[0]
    return n["node_id"], n


# ── 후보 제품 선정 ────────────────────────────────────────────────

def _signature(prof) -> tuple:
    """다양성 판단 기준. 이 셋이 다르면 점수 계산 결과도 갈린다."""
    return (prof.sensitivity_k, prof.pao_months, prof.optical_grade)


def pick_candidates(
    need: int,
    exclude_product_ids: set,
    already: List[tuple],
    rng: random.Random,
) -> List[Dict[str, Any]]:
    """
    products에서 need개를 고른다.

    카테고리별로 후보를 모은 뒤, 이미 가진 제품과 프로파일이 겹치지 않는
    것을 우선한다. 전부 같은 (k, PAO, 광학등급)이면 개봉일 차이만 남아
    "성분에 따라 점수가 갈린다"는 시연의 요지가 흐려지기 때문이다.
    """
    sb = get_supabase()
    pool: List[Dict[str, Any]] = []

    for cat in CATEGORIES:
        rows = (
            sb.table("products")
            .select("product_id, name, brand, category")
            .eq("category", cat)
            .limit(POOL_PER_CATEGORY)
            .execute()
        ).data or []
        pool.extend(r for r in rows if r["product_id"] not in exclude_product_ids)

    if not pool:
        return []

    rng.shuffle(pool)

    for r in pool:
        r["_profile"] = resolve_profile(
            r.get("name"), category=r.get("category"), brand=r.get("brand")
        )

    seen = dict.fromkeys(already, 1)
    picked: List[Dict[str, Any]] = []

    # 시그니처가 덜 등장한 후보부터 고른다. 같은 등급이면 순서는 셔플된
    # 상태를 그대로 따르므로 seed로 재현된다.
    while len(picked) < need and pool:
        pool.sort(key=lambda r: seen.get(_signature(r["_profile"]), 0))
        chosen = pool.pop(0)
        sig = _signature(chosen["_profile"])
        seen[sig] = seen.get(sig, 0) + 1
        picked.append(chosen)

    return picked


# ── 개봉일 배정 ───────────────────────────────────────────────────

def assign_opened_days(n: int, rng: random.Random) -> List[int]:
    """
    20~240일 사이에 n개를 고르게 벌린 뒤 순서를 섞는다.

    균등 분할 후 각 구간 안에서 흔들어, 겹치지 않으면서도 매번 같은
    숫자가 나오지 않게 한다. 반환 순서는 무작위이므로 어떤 제품이
    어떤 날짜를 받을지는 seed에만 달려 있다.
    """
    if n <= 0:
        return []
    if n == 1:
        return [rng.randint(MIN_OPENED_DAYS, MAX_OPENED_DAYS)]

    span = (MAX_OPENED_DAYS - MIN_OPENED_DAYS) / n
    days = []
    for i in range(n):
        lo = MIN_OPENED_DAYS + span * i
        hi = MIN_OPENED_DAYS + span * (i + 1)
        days.append(int(round(rng.uniform(lo, hi))))
    rng.shuffle(days)
    return days


# ── 계획 수립 ─────────────────────────────────────────────────────

def build_plan(
    user_id: str,
    node_id: str,
    target: int,
    rng: random.Random,
    refresh_profiles: bool,
) -> Dict[str, Any]:
    """무엇을 바꿀지 계산만 한다. 이 함수는 DB에 쓰지 않는다."""
    existing = get_care_products(user_id)
    owned_ids = {it["product_id"] for it in existing if it.get("product_id")}

    already_sigs = [
        (it["sensitivity_k"], it["pao_months"], it["optical_grade"])
        for it in existing if it["has_profile"]
    ]

    need = max(0, target - len(existing))
    new_products = pick_candidates(need, owned_ids, already_sigs, rng) if need else []

    # 개봉일이 비어 있는 기존 행 + 새로 추가할 행 전부에 날짜를 배정한다.
    need_opened = [it for it in existing if not it.get("opened_at")]
    days = assign_opened_days(len(need_opened) + len(new_products), rng)
    today = date.today()

    updates: List[Dict[str, Any]] = []
    for it in existing:
        patch: Dict[str, Any] = {}
        if not it.get("opened_at"):
            d = days.pop()
            patch["opened_at"] = (today - timedelta(days=d)).isoformat()
            patch["_days"] = d
        if not it.get("storage_node_id"):
            patch["storage_node_id"] = node_id
        if patch:
            updates.append({"item": it, "patch": patch})

    now_iso = datetime.now(timezone.utc).isoformat()
    inserts: List[Dict[str, Any]] = []
    for p in new_products:
        d = days.pop()
        inserts.append({
            "product": p,
            "days": d,
            "row": {
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "product_id": p["product_id"],
                "usage_type": SEED_USAGE_TYPE,
                "created_at": now_iso,
                "opened_at": (today - timedelta(days=d)).isoformat(),
                "storage_node_id": node_id,
            },
        })

    # ── thermal_profile ──────────────────────────────────────────
    # 기존 제품은 프로파일이 없을 때만 만든다. 이미 있는 값을 덮으면
    # 손으로 교정해 둔 k값이 조용히 사라진다. --refresh-profiles로만 덮는다.
    profile_targets: List[Dict[str, Any]] = []
    for it in existing:
        if it["has_profile"] and not refresh_profiles:
            continue
        profile_targets.append({
            "product_id": it["product_id"],
            "name": it.get("name"),
            "brand": it.get("brand"),
            "category": it.get("category"),
            "existing": it["has_profile"],
        })
    for p in new_products:
        profile_targets.append({
            "product_id": p["product_id"],
            "name": p.get("name"),
            "brand": p.get("brand"),
            "category": p.get("category"),
            "existing": False,
        })

    profiles = []
    for t in profile_targets:
        prof = resolve_profile(t["name"], category=t["category"], brand=t["brand"])
        profiles.append({"target": t, "profile": prof,
                         "row": prof.as_row(t["product_id"])})

    return {
        "existing": existing,
        "updates": updates,
        "inserts": inserts,
        "profiles": profiles,
        "node_id": node_id,
    }


# ── 계획 출력 ─────────────────────────────────────────────────────

def _consumed_preview(k: float, pao: int, days: int) -> float:
    """
    20℃ 항온을 가정한 대략적인 PAO 소모율(%).

    실제 점수가 아니다. risk_score는 실측 온도로 적산하므로 보통 이보다
    크게 나온다. 여기서는 "제품 사이에 차이가 나는지"만 미리 본다.
    """
    if not pao:
        return 0.0
    return (days / 30.0) * k / pao * 100.0


def print_plan(plan: Dict[str, Any], span: Optional[dict]) -> None:
    existing = plan["existing"]

    _rule(f"① 현재 보유 제품 {len(existing)}개")
    if not existing:
        print("  없음 — 전부 새로 추가합니다.")
    else:
        print(f"  {_s('제품', 26)}{_s('카테고리', 12)}{_s('개봉일', 12)}"
              f"{_s('보관노드', 12)}{_s('프로파일', 10)}")
        print("  " + "-" * 90)
        for it in existing:
            print(f"  {_s(_label(it), 26)}{_s(it.get('category'), 12)}"
                  f"{_s(it.get('opened_at'), 12)}{_s(it.get('storage_node_id'), 12)}"
                  f"{_s('있음' if it['has_profile'] else '없음', 10)}")

    _rule(f"② 기존 행의 빈 칸 채우기 — {len(plan['updates'])}건")
    if not plan["updates"]:
        print("  채울 빈 칸이 없습니다.")
    for u in plan["updates"]:
        fields = []
        if "opened_at" in u["patch"]:
            fields.append(f"opened_at={u['patch']['opened_at']} ({u['patch']['_days']}일 전)")
        if "storage_node_id" in u["patch"]:
            fields.append(f"storage_node_id={u['patch']['storage_node_id']}")
        print(f"  {_s(_label(u['item']), 26)}{' · '.join(fields)}")

    _rule(f"③ 새로 추가할 제품 — {len(plan['inserts'])}건")
    if not plan["inserts"]:
        print("  추가 없음 (목표 개수를 이미 채웠습니다).")
    for ins in plan["inserts"]:
        p = ins["product"]
        prof = p["_profile"]
        print(f"  {_s(_label(p), 26)}{_s(p.get('category'), 12)}"
              f"개봉 {ins['days']:>3}일 전  k={prof.sensitivity_k}  "
              f"PAO={prof.pao_months:>2}  {prof.optical_grade}")

    _rule(f"④ product_thermal_profile — {len(plan['profiles'])}건")
    if not plan["profiles"]:
        print("  변경 없음.")
    for pr in plan["profiles"]:
        t, prof = pr["target"], pr["profile"]
        mark = "덮어씀" if t["existing"] else "신규"
        name = _label(t)
        print(f"  {_s(name, 26)}"
              f"{_s(mark, 8)}k={prof.sensitivity_k}  PAO={prof.pao_months:>2}  "
              f"{_s(prof.optical_grade, 13)}{prof.matched['sensitivity']}")

    # ── 예상 결과 미리보기 ───────────────────────────────────────
    _rule("⑤ 적용 후 예상 (20℃ 항온 가정 — 실제 점수는 이보다 높게 나온다)")
    pmap = {pr["target"]["product_id"]: pr["profile"] for pr in plan["profiles"]}
    upatch = {u["item"]["user_product_id"]: u["patch"] for u in plan["updates"]}

    rows = []
    for it in existing:
        patch = upatch.get(it["user_product_id"], {})
        opened = patch.get("opened_at") or it.get("opened_at")
        days = patch.get("_days")
        if days is None and opened:
            days = (date.today() - date.fromisoformat(str(opened)[:10])).days
        prof = pmap.get(it["product_id"])
        k = prof.sensitivity_k if prof else it.get("sensitivity_k")
        pao = prof.pao_months if prof else it.get("pao_months")
        rows.append((_label(it), k, pao, days))
    for ins in plan["inserts"]:
        prof = ins["product"]["_profile"]
        rows.append((_label(ins["product"]), prof.sensitivity_k,
                     prof.pao_months, ins["days"]))

    rows = [r for r in rows if r[1] and r[2] and r[3] is not None]
    rows.sort(key=lambda r: _consumed_preview(r[1], r[2], r[3]), reverse=True)

    print(f"  {_s('제품', 26)}{_s('k', 6)}{_s('PAO', 6)}{_s('개봉', 8)}소모율(개략)")
    print("  " + "-" * 70)
    for name, k, pao, days in rows:
        print(f"  {_s(name, 26)}{_s(k, 6)}{_s(pao, 6)}{_s(f'{days}일', 8)}"
              f"{_consumed_preview(k, pao, days):>6.1f}%")

    if len(rows) >= 2:
        top = _consumed_preview(*rows[0][1:])
        bottom = _consumed_preview(*rows[-1][1:])
        print(f"\n  최고 {top:.1f}% / 최저 {bottom:.1f}%  "
              f"— 차이가 작으면 --seed를 바꿔 다시 뽑으세요.")

    # ── 측정 구간 경고 ───────────────────────────────────────────
    if span and span.get("first_ts"):
        first = str(span["first_ts"])[:10]
        print(f"\n  노드 {plan['node_id']} 최초 측정 {first} · {span['count']}건")
        print("  개봉일이 이보다 앞서면 그 구간은 20℃ 상당으로 가정 적산됩니다")
        print("  (risk_score의 assumed_hours). 시연에서 구분해 설명할 것.")
    else:
        print(f"\n  ! 노드 {plan['node_id']}에 sensor_readings가 없습니다.")
        print("    열이력 항목이 빠진 채 점수가 계산됩니다.")


# ── 적용 ──────────────────────────────────────────────────────────

def apply_plan(plan: Dict[str, Any]) -> None:
    sb = get_supabase()

    _rule("적용")

    for u in plan["updates"]:
        patch = {k: v for k, v in u["patch"].items() if not k.startswith("_")}
        (sb.table("user_products")
           .update(patch)
           .eq("id", u["item"]["user_product_id"])
           .execute())
        print(f"  update user_products {u['item']['user_product_id'][:8]}… {patch}")

    if plan["inserts"]:
        rows = [ins["row"] for ins in plan["inserts"]]
        sb.table("user_products").insert(rows).execute()
        print(f"  insert user_products {len(rows)}건")

    if plan["profiles"]:
        rows = [pr["row"] for pr in plan["profiles"]]
        (sb.table("product_thermal_profile")
           .upsert(rows, on_conflict="product_id")
           .execute())
        print(f"  upsert product_thermal_profile {len(rows)}건")

    print("\n  완료. python -m scripts.inspect_care_data 로 확인하세요.")


# ── 진입점 ────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description="점검 시연용 데이터 보완 시드")
    ap.add_argument("--user", default=DEFAULT_USER)
    ap.add_argument("--node", default=None,
                    help="보관 노드 id. 생략하면 node_type='storage' 중 첫 번째")
    ap.add_argument("--target", type=int, default=DEFAULT_TARGET,
                    help=f"목표 제품 수 (기본 {DEFAULT_TARGET})")
    ap.add_argument("--seed", type=int, default=42,
                    help="개봉일·제품 선정 난수 seed. 같은 값이면 같은 결과")
    ap.add_argument("--refresh-profiles", action="store_true",
                    help="이미 있는 thermal_profile도 규칙 테이블 값으로 덮어씀")
    ap.add_argument("--apply", action="store_true",
                    help="실제로 DB에 반영 (없으면 계획만 출력)")
    args = ap.parse_args()

    rng = random.Random(args.seed)

    node_id, node = resolve_storage_node(args.node)
    if node_id is None:
        print("보관 노드를 정할 수 없어 중단합니다.")
        return

    span = get_reading_span(node_id)

    print(f"사용자   {args.user}")
    print(f"보관노드 {node_id}"
          + (f" ({node.get('location_label')})" if node and node.get('location_label') else ""))
    print(f"목표     {args.target}개   seed={args.seed}   "
          f"모드={'APPLY' if args.apply else 'DRY-RUN'}")

    plan = build_plan(args.user, node_id, args.target, rng, args.refresh_profiles)
    print_plan(plan, span)

    changes = len(plan["updates"]) + len(plan["inserts"]) + len(plan["profiles"])
    if not args.apply:
        _rule("DRY-RUN — 아무것도 쓰지 않았습니다")
        print(f"  반영할 변경 {changes}건")
        print("  실행하려면 --apply 를 붙이세요.")
        return

    if changes == 0:
        print("\n  변경할 것이 없습니다.")
        return

    apply_plan(plan)


if __name__ == "__main__":
    main()