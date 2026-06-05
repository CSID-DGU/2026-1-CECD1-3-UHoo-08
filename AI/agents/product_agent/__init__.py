import logging
import time

from models.extracted_product import ExtractedProduct
from models.product_response import ProductResponse
from agents.product_agent.gemini_enricher import enrich_product

logger = logging.getLogger(__name__)


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
        logger.info("[product_agent] 임베딩 저장 완료 | productId=%s", product_id)
    except Exception as e:
        logger.warning("[product_agent] 임베딩 저장 실패 (무시) | %s", e)


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

    # ── DB 조회 ──────────────────────────────────────────────────────
    if _REPO_AVAILABLE:
        t0 = time.perf_counter()
        db_product = find_by_name_brand(
            name=product.product_name or "",
            brand=product.brand or "",
        )
        if db_product:
            stale = is_stale(db_product["product_id"])
            needs_enrich = stale
            logger.info(
                "[product_agent] DB 조회 히트 | %.2fs | productId=%s | stale=%s",
                time.perf_counter() - t0,
                db_product["product_id"],
                stale,
            )
        else:
            logger.info(
                "[product_agent] DB 조회 미스 (신규 상품) | %.2fs | name=%s | brand=%s",
                time.perf_counter() - t0,
                product.product_name,
                product.brand,
            )

    # ── Gemini 보강 ───────────────────────────────────────────────────
    enriched = None
    if needs_enrich:
        logger.info("[product_agent] Gemini 보강 시작 | name=%s | brand=%s", product.product_name, product.brand)
        t0 = time.perf_counter()
        enriched = enrich_product(product)
        elapsed = time.perf_counter() - t0

        price_data = enriched.get("price_data") or {}
        review_data = enriched.get("review_data") or {}
        logger.info(
            "[product_agent] Gemini 보강 완료 | %.2fs | original_price=%s | lowest_price=%s | avg_score=%s | review_count=%s",
            elapsed,
            price_data.get("original_price"),
            (price_data.get("best_option") or {}).get("final_price"),
            review_data.get("average_score"),
            review_data.get("review_count"),
        )

        # ── DB 저장 ──────────────────────────────────────────────────
        if _REPO_AVAILABLE:
            category_val = (product.category or {}).get("main") if isinstance(product.category, dict) else product.category

            if db_product:
                t0 = time.perf_counter()
                save_enriched(db_product["product_id"], enriched)
                logger.info("[product_agent] 기존 상품 보강 저장 | %.2fs | productId=%s", time.perf_counter() - t0, db_product["product_id"])

                feature_json = enriched.get("product_features")
                if feature_json and category_val:
                    _embed_and_save(db_product["product_id"], category_val, feature_json)
            else:
                original_price = (enriched.get("price_data") or {}).get("original_price")
                image_url = enriched.get("image_url") or None

                t0 = time.perf_counter()
                new_id = save_new_product({
                    "name": product.product_name,
                    "brand": product.brand,
                    "category": category_val,
                    "original_price": original_price,
                    "image_url": image_url,
                })
                logger.info("[product_agent] 신규 상품 INSERT | %.2fs | productId=%s", time.perf_counter() - t0, new_id)

                db_product = {"product_id": new_id}

                t0 = time.perf_counter()
                save_enriched(new_id, enriched)
                logger.info("[product_agent] 신규 상품 보강 저장 | %.2fs | productId=%s", time.perf_counter() - t0, new_id)

                feature_json = enriched.get("product_features")
                if feature_json and category_val:
                    _embed_and_save(new_id, category_val, feature_json)

    # ── 응답 조립 ─────────────────────────────────────────────────────
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
