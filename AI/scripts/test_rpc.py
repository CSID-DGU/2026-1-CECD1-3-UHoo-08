"""
match_alternatives RPC 동작 확인 스크립트
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from db.supabase_client import get_supabase

BASE_PRODUCT_ID = "cb4cc8ac-17a9-4a63-a5b6-f00164c91f3f"

sb = get_supabase()

# 1. lip 카테고리 임베딩 상품 수 확인
print("=== lip 카테고리 임베딩 상품 ===")
res = sb.table("product_embeddings").select("product_id, products(category)").execute()
lip_embs = [r for r in (res.data or []) if (r.get("products") or {}).get("category") == "lip"]
print(f"lip 임베딩 수: {len(lip_embs)}")
for r in lip_embs[:5]:
    print(f"  {r['product_id']}")

# 2. match_alternatives RPC 직접 호출
print("\n=== match_alternatives RPC ===")
try:
    res2 = sb.rpc("match_alternatives", {
        "base_product_id": BASE_PRODUCT_ID,
        "match_count": 5,
        "exclude_ids": []
    }).execute()
    print(f"결과 {len(res2.data)}개:", res2.data)
except Exception as e:
    print(f"RPC 오류: {e}")
