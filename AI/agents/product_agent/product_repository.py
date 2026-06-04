from datetime import datetime, timezone, timedelta
from typing import Optional

from db.supabase_client import get_supabase

_STALE_HOURS = 6


def find_by_name_brand(name: str, brand: str) -> Optional[dict]:
    """products 단일 조회 후 product_agent용 dict 반환."""
    sb = get_supabase()

    res = (
        sb.table("products")
        .select(
            "product_id, name, brand, category, original_price, "
            "lowest_price, savings, stores, review_summary, "
            "average_score, review_count, skin_type_satisfaction, "
            "feature_json, last_updated_at"
        )
        .ilike("name", name)
        .ilike("brand", brand)
        .limit(1)
        .execute()
    )
    if not res.data:
        return None

    row = res.data[0]
    feature_json = row.get("feature_json") or {}
    if isinstance(feature_json, str):
        import json
        try:
            feature_json = json.loads(feature_json)
        except Exception:
            feature_json = {}

    price_data = {
        "lowestPrice": row.get("lowest_price"),
        "savings": row.get("savings"),
        "stores": row.get("stores") or [],
        "cachedAt": str(row.get("last_updated_at") or ""),
    }

    review_summary = {
        "aiSummary": row.get("review_summary") or "",
        "averageScore": row.get("average_score"),
        "totalCount": row.get("review_count"),
        "skinTypeSatisfaction": row.get("skin_type_satisfaction"),
    }

    ingredients = feature_json.get("key_ingredient") or []

    return {
        "product_id": row["product_id"],
        "name": row["name"],
        "brand": row["brand"],
        "category": row["category"],
        "original_price": row.get("original_price"),
        "price_data": price_data,
        "review_summary": review_summary,
        "ingredients": ingredients,
    }


def is_stale(product_id: str) -> bool:
    """products.last_updated_at 기준 6시간 초과면 True."""
    sb = get_supabase()
    res = (
        sb.table("products")
        .select("last_updated_at")
        .eq("product_id", product_id)
        .limit(1)
        .execute()
    )
    if not res.data or not res.data[0].get("last_updated_at"):
        return True

    last_updated = datetime.fromisoformat(res.data[0]["last_updated_at"])
    if last_updated.tzinfo is None:
        last_updated = last_updated.replace(tzinfo=timezone.utc)

    return datetime.now(timezone.utc) - last_updated > timedelta(hours=_STALE_HOURS)


def save_new_product(product: dict) -> str:
    """products 테이블에 신규 상품 INSERT. 생성된 product_id(UUID) 반환."""
    sb = get_supabase()
    res = (
        sb.table("products")
        .insert({
            "name": product.get("name") or "",
            "brand": product.get("brand") or "",
            "category": product.get("category") or "",
            "original_price": product.get("original_price"),
            "image_url": product.get("image_url"),
        })
        .execute()
    )
    return res.data[0]["product_id"]


def save_enriched(product_id: str, enriched: dict) -> None:
    """Gemini 보강 결과를 products 테이블에 upsert."""
    import json as _json
    sb = get_supabase()

    price_data = enriched.get("price_data") or {}
    best = price_data.get("best_option") or {}
    options = price_data.get("options") or []
    lowest_price = best.get("final_price")
    original_price = price_data.get("original_price") or None
    savings = (original_price - lowest_price) if (original_price and lowest_price) else None

    best_platform = best.get("platform", "")
    stores = [
        {
            "storeName": opt.get("platform", ""),
            "price": opt.get("final_price"),
            "shippingInfo": "무료배송" if not opt.get("shipping_fee") else f"배송비 {opt['shipping_fee']}원",
            "isLowest": opt.get("platform") == best_platform,
        }
        for opt in options
    ]

    review_data = enriched.get("review_data") or {}
    feature_json = enriched.get("product_features") or {}

    payload: dict = {
        "product_id": product_id,
        "lowest_price": lowest_price,
        "savings": savings,
        "stores": stores,
        "review_summary": review_data.get("summary") or "",
        "average_score": review_data.get("average_score"),
        "review_count": review_data.get("review_count"),
        "skin_type_satisfaction": review_data.get("skin_type_satisfaction"),
        "last_updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if original_price:
        payload["original_price"] = original_price
    if feature_json:
        payload["feature_json"] = _json.dumps(feature_json, ensure_ascii=False)

    sb.table("products").update(payload).eq("product_id", product_id).execute()

    # review_embeddings 저장 (백그라운드 처리, 실패해도 무시)
    if review_data:
        _save_review_embeddings(product_id, review_data)


def _save_review_embeddings(product_id: str, review_data: dict) -> None:
    """Gemini 리뷰 데이터 → 청킹 → bge-m3 임베딩 → review_embeddings 저장."""
    try:
        from services.review_chunker import chunk_review
        from services.embedding_service import EmbeddingService

        sb = get_supabase()
        sb.table("review_embeddings").delete().eq("product_id", product_id).execute()

        texts: list = []
        for item in (review_data.get("positive") or []):
            texts.extend(chunk_review(item))
        for item in (review_data.get("negative") or []):
            texts.extend(chunk_review(item))
        summary = review_data.get("summary") or ""
        if summary:
            texts.extend(chunk_review(summary))

        if not texts:
            return

        emb = EmbeddingService.get()
        vecs = emb.embed_batch(texts)
        rows = [
            {
                "product_id": product_id,
                "review_text": text,
                "embedding": vec,
                "source": "GEMINI_EXTRACTED",
            }
            for text, vec in zip(texts, vecs)
        ]
        sb.table("review_embeddings").insert(rows).execute()
    except Exception:
        pass
