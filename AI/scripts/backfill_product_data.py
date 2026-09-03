"""
products 가격·리뷰 데이터 백필.

lowest_price·stores·review_summary 등이 비어 있는 상품을 찾아 Gemini 보강을
돌리고 저장한다. 상품 상세 화면에서 최저가·할인·리뷰 요약이 통째로 비어 보이는
것은 시딩 당시 이 값들이 채워지지 않았기 때문이다.

    PYTHONPATH=. ./venv/bin/python scripts/backfill_product_data.py --dry-run
    PYTHONPATH=. ./venv/bin/python scripts/backfill_product_data.py
    PYTHONPATH=. ./venv/bin/python scripts/backfill_product_data.py --limit 10 --workers 2
"""
from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional

from agents.product_agent.gemini_enricher import enrich_product
from agents.product_agent.product_repository import save_enriched
from db.supabase_client import get_supabase
from models.extracted_product import ExtractedProduct

# 이 중 하나라도 비어 있으면 상세 화면에 빈칸이 생긴다.
_REQUIRED = ("lowest_price", "stores", "review_summary", "average_score")


def _is_blank(value) -> bool:
    return value in (None, "", [], {})


def _needs_data(row: dict) -> bool:
    return any(_is_blank(row.get(f)) for f in _REQUIRED)


def _product_type(row: dict) -> Optional[str]:
    feat = row.get("feature_json")
    if isinstance(feat, str):
        try:
            feat = json.loads(feat)
        except (ValueError, TypeError):
            return None
    return (feat or {}).get("product_type") if isinstance(feat, dict) else None


def _targets(include_all: bool) -> List[dict]:
    res = (
        get_supabase()
        .table("products")
        .select(
            "product_id, name, brand, category, feature_json, "
            "lowest_price, stores, review_summary, average_score"
        )
        .order("name")
        .execute()
    )
    rows = res.data or []
    return rows if include_all else [r for r in rows if _needs_data(r)]


def _enrich_one(row: dict) -> None:
    extracted = ExtractedProduct(
        product_name=row.get("name"),
        brand=row.get("brand"),
        category={
            "main": row.get("category") or "skincare",
            "sub": _product_type(row) or "",
        },
    )
    save_enriched(row["product_id"], enrich_product(extracted))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="대상만 출력하고 끝낸다")
    parser.add_argument("--limit", type=int, default=0, help="처리할 최대 상품 수 (0=전체)")
    parser.add_argument("--workers", type=int, default=3, help="동시 처리 수")
    parser.add_argument("--all", action="store_true", help="이미 채워진 상품까지 다시 수집")
    args = parser.parse_args()

    targets = _targets(include_all=args.all)
    if args.limit:
        targets = targets[: args.limit]

    print(f"대상 {len(targets)}건")
    if args.dry_run:
        for row in targets:
            missing = [f for f in _REQUIRED if _is_blank(row.get(f))]
            print(f"  {row['brand']} {row['name']} — 없음: {', '.join(missing) or '없음'}")
        return
    if not targets:
        return

    # 리뷰 임베딩 모델을 미리 한 번 올린다. 워커들이 동시에 처음 로드하면
    # 경쟁 상태로 세그폴트가 난다(실제로 워커 4개에서 exit 139로 죽었다).
    try:
        from services.embedding_service import EmbeddingService
        EmbeddingService.get()
    except Exception as e:
        print(f"임베딩 모델 준비 실패(계속 진행): {type(e).__name__} {e}")

    succeeded = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(_enrich_one, row): row for row in targets}
        for done in as_completed(futures):
            row = futures[done]
            try:
                done.result()
            except Exception as e:
                print(f"  ✗ {row['brand']} {row['name']}: {type(e).__name__} {e}")
                continue
            succeeded += 1
            print(f"  ✓ {row['brand']} {row['name']}")

    print(f"\n완료: {succeeded}/{len(targets)}")


if __name__ == "__main__":
    main()
