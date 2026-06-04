from models.extracted_product import ExtractedProduct
from models.product_response import ProductResponse
from agents.product_agent.gemini_enricher import enrich_product


def _embed_and_save(product_id: str, category: str, feature_json: dict) -> None:
    """feature_json → bge-m3 임베딩 → product_embeddings 저장. 실패해도 무시."""
    try:
        from services.feature_text_builder import build_product_text
        from services.embedding_service import EmbeddingService
        from db.supabase_client import get_supabase

        text = build_product_text(category, feature_json)
        if not text:
            return
        emb = EmbeddingService.get()
        vec = emb.embed(text)
        get_supabase().table("product_embeddings").upsert({
            "product_id": product_id,
            "feature_vec": vec,
            "model_version": emb.model_version,
        }).execute()
    except Exception:
        pass

try:
    from agents.product_agent.product_repository import (
        find_by_name_brand,
        is_stale,
        save_enriched,
        save_new_product,
    )
    _REPO_AVAILABLE = True
except ImportError:
    _REPO_AVAILABLE = False


def run(product: ExtractedProduct) -> ProductResponse:
    """
    1. product_repository로 DB 조회 (name + brand)
    2. stale(6h 초과)이거나 신규이면 Gemini로 가격·리뷰 보강
    3. ProductResponse 반환
    """
    db_product = None
    needs_enrich = True

    if _REPO_AVAILABLE:
        db_product = find_by_name_brand(
            name=product.product_name or "",
            brand=product.brand or "",
        )
        if db_product:
            needs_enrich = is_stale(db_product["product_id"])

    enriched = None
    if needs_enrich:
        enriched = enrich_product(product)
        if _REPO_AVAILABLE:
            if db_product:
                save_enriched(db_product["product_id"], enriched)
                category_val = (product.category or {}).get("main") if isinstance(product.category, dict) else product.category
                feature_json = enriched.get("product_features")
                if feature_json and category_val:
                    _embed_and_save(db_product["product_id"], category_val, feature_json)
            else:
                category_val = (product.category or {}).get("main") if isinstance(product.category, dict) else product.category
                original_price = (enriched.get("price_data") or {}).get("original_price")
                image_url = enriched.get("image_url") or None
                new_id = save_new_product({
                    "name": product.product_name,
                    "brand": product.brand,
                    "category": category_val,
                    "original_price": original_price,
                    "image_url": image_url,
                })
                db_product = {"product_id": new_id}
                save_enriched(new_id, enriched)
                feature_json = enriched.get("product_features")
                if feature_json and category_val:
                    _embed_and_save(new_id, category_val, feature_json)

    # 가격·리뷰·성분 결정: DB 캐시 우선, 없으면 Gemini 결과
    if db_product and not needs_enrich:
        gemini_price   = db_product.get("price_data") or {}
        review_summary = db_product.get("review_summary") or {}
        ingredients    = db_product.get("ingredients") or []
    elif enriched:
        gemini_price = enriched.get("price_data") or {}
        review_data  = enriched.get("review_data") or {}
        review_summary = {
            "aiSummary": review_data.get("summary", ""),
            "positive":  review_data.get("positive", []),
            "negative":  review_data.get("negative", []),
        }
        ingredients = (enriched.get("ingredient_data") or {}).get("key_ingredients") or []
    else:
        gemini_price = review_summary = {}
        ingredients = []

    category_main = (product.category or {}).get("main") if isinstance(product.category, dict) else product.category

    return ProductResponse(
        productId=db_product["product_id"] if db_product else None,
        name=product.product_name,
        brand=product.brand,
        category=category_main,
        geminiPrice=gemini_price,
        reviewSummary=review_summary,
        ingredients=ingredients,
    )
