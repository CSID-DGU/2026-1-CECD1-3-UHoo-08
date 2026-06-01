from datetime import datetime, timezone, timedelta
from typing import Optional

from db.supabase_client import get_supabase

_STALE_HOURS = 6


def find_by_name_brand(name: str, brand: str) -> Optional[dict]:
    """products + product_insights + product_features 조회 후 product_agent용 dict 반환."""
    sb = get_supabase()

    product_res = (
        sb.table("products")
        .select("product_id, name, brand, category, original_price")
        .ilike("name", name)
        .ilike("brand", brand)
        .limit(1)
        .execute()
    )
    if not product_res.data:
        return None

    row = product_res.data[0]
    product_id = row["product_id"]

    insights_res = (
        sb.table("product_insights")
        .select("lowest_price, savings, stores, review_summary, average_score, review_count, skin_type_satisfaction, last_updated_at")
        .eq("product_id", product_id)
        .limit(1)
        .execute()
    )
    insights = insights_res.data[0] if insights_res.data else {}

    features_res = (
        sb.table("product_features")
        .select("feature_json")
        .eq("product_id", product_id)
        .limit(1)
        .execute()
    )
    feature_json = (features_res.data[0].get("feature_json") or {}) if features_res.data else {}

    # AI 아키텍처 명세 geminiPrice 구조로 조립
    price_data = {
        "lowestPrice": insights.get("lowest_price"),
        "savings": insights.get("savings"),
        "stores": insights.get("stores") or [],
        "cachedAt": str(insights.get("last_updated_at") or ""),
    }

    # AI 아키텍처 명세 reviewSummary 구조로 조립
    review_summary = {
        "aiSummary": insights.get("review_summary") or "",
        "averageScore": insights.get("average_score"),
        "totalCount": insights.get("review_count"),
        "skinTypeSatisfaction": insights.get("skin_type_satisfaction"),
    }

    ingredients = feature_json.get("key_ingredient") or []

    return {
        **row,
        "price_data": price_data,
        "review_summary": review_summary,
        "ingredients": ingredients,
    }


def is_stale(product_id: str) -> bool:
    """product_insights.last_updated_at 기준 6시간 초과면 True."""
    sb = get_supabase()
    res = (
        sb.table("product_insights")
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
    """Gemini 보강 결과를 product_insights 테이블에 upsert."""
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

    payload = {
        "product_id": product_id,
        "lowest_price": lowest_price,
        "savings": savings,
        "stores": stores,
        "review_summary": review_data.get("summary") or "",
        "average_score": review_data.get("average_score"),
        "review_count": review_data.get("review_count"),
        "skin_type_satisfaction": review_data.get("skin_type_satisfaction"),
        "original_price": original_price or None,
        "last_updated_at": datetime.now(timezone.utc).isoformat(),
    }

    sb.table("product_insights").upsert(payload, on_conflict="product_id").execute()
