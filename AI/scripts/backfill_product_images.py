"""
products.image_url 백필.

이미지가 비어 있거나 우리 Storage 사본이 아닌(=외부 CDN 직링크라 깨질 수 있는) 상품을
찾아 실제 이미지를 확보한 뒤 Storage에 올리고 image_url을 갱신한다.

    PYTHONPATH=. ./venv/bin/python scripts/backfill_product_images.py
    PYTHONPATH=. ./venv/bin/python scripts/backfill_product_images.py --dry-run
    PYTHONPATH=. ./venv/bin/python scripts/backfill_product_images.py --limit 10 --workers 2
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List

from db.supabase_client import get_supabase
from services.product_image import STORAGE_BUCKET, ensure_product_image

_STORAGE_MARKER = f"/storage/v1/object/public/{STORAGE_BUCKET}/"


def _needs_image(row: dict) -> bool:
    image_url = (row.get("image_url") or "").strip()
    return _STORAGE_MARKER not in image_url


def _targets(include_ok: bool) -> List[dict]:
    res = (
        get_supabase()
        .table("products")
        .select("product_id, name, brand, image_url")
        .order("name")
        .execute()
    )
    rows = res.data or []
    return rows if include_ok else [r for r in rows if _needs_image(r)]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="대상만 출력하고 끝낸다")
    parser.add_argument("--limit", type=int, default=0, help="처리할 최대 상품 수 (0=전체)")
    parser.add_argument("--workers", type=int, default=4, help="동시 처리 수")
    parser.add_argument("--all", action="store_true", help="이미 Storage 사본이 있는 상품까지 재수집")
    args = parser.parse_args()

    targets = _targets(include_ok=args.all)
    if args.limit:
        targets = targets[: args.limit]

    print(f"대상 {len(targets)}건")
    if args.dry_run:
        for row in targets:
            print(f"  {row['product_id']}  {row['brand']} {row['name']}  현재={row.get('image_url')}")
        return
    if not targets:
        return

    succeeded = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(
                ensure_product_image,
                row["product_id"],
                row.get("brand") or "",
                row.get("name") or "",
            ): row
            for row in targets
        }
        for done in as_completed(futures):
            row = futures[done]
            try:
                public_url = done.result()
            except Exception as e:
                print(f"  ✗ {row['brand']} {row['name']}: {type(e).__name__} {e}")
                continue
            if public_url:
                succeeded += 1
                print(f"  ✓ {row['brand']} {row['name']}")
            else:
                print(f"  ✗ {row['brand']} {row['name']}: 이미지 확보 실패")

    print(f"\n완료: {succeeded}/{len(targets)}")


if __name__ == "__main__":
    main()
