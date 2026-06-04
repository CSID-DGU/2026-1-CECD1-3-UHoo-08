"""
products 테이블에 feature_json이 있지만 product_embeddings가 없는 상품에
임베딩을 일괄 생성한다.
"""
import sys
import os
import json as _json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from db.supabase_client import get_supabase
from services.feature_text_builder import build_product_text
from services.embedding_service import EmbeddingService


def backfill():
    sb = get_supabase()

    # products 테이블에서 feature_json 있는 상품 전체 조회
    products_res = sb.table("products").select("product_id, category, feature_json").execute()
    if not products_res.data:
        print("products 테이블이 비어있습니다.")
        return

    targets_all = [r for r in products_res.data if r.get("feature_json")]
    print(f"feature_json 있는 상품: {len(targets_all)}개")

    # 이미 임베딩 있는 상품 ID 집합
    emb_res = sb.table("product_embeddings").select("product_id").execute()
    already = {row["product_id"] for row in (emb_res.data or [])}
    print(f"이미 임베딩 있는 상품: {len(already)}개")

    targets = [r for r in targets_all if r["product_id"] not in already]
    print(f"임베딩 대상: {len(targets)}개\n")

    if not targets:
        print("모두 임베딩이 있습니다.")
        return

    emb = EmbeddingService.get()
    print("bge-m3 모델 로딩 중...")

    ok, fail = 0, 0
    for row in targets:
        pid = row["product_id"]
        raw = row.get("feature_json") or {}

        # 이중 인코딩 처리: str → dict (최대 2회)
        for _ in range(2):
            if isinstance(raw, str):
                try:
                    raw = _json.loads(raw)
                except Exception:
                    break

        feature_json = raw if isinstance(raw, dict) else {}
        category = row.get("category", "")

        try:
            text = build_product_text(category, feature_json)
            if not text:
                print(f"  SKIP {pid}: feature_text 생성 실패")
                continue
            vec = emb.embed(text)
            sb.table("product_embeddings").upsert({
                "product_id": pid,
                "feature_vec": vec,
                "model_version": emb.model_version,
            }).execute()
            print(f"  OK   {pid} ({row.get('category', '')})")
            ok += 1
        except Exception as e:
            print(f"  FAIL {pid}: {e}")
            fail += 1

    print(f"\n완료: 성공 {ok}개, 실패 {fail}개")


if __name__ == "__main__":
    backfill()
