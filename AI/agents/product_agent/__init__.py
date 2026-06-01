from models.extracted_product import ExtractedProduct
from models.product_response import ProductResponse
from agents.product_agent.gemini_enricher import enrich_product

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
        ingredients = enriched.get("ingredients") or []
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
