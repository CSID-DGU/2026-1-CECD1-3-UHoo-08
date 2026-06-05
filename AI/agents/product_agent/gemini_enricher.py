import json
import logging
import re
import time

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage

from config import settings
from models.extracted_product import ExtractedProduct
from prompts.gemini_extraction import build_prompt

logger = logging.getLogger(__name__)

_client = ChatGoogleGenerativeAI(
    model=settings.GEMINI_MODEL,
    google_api_key=settings.GEMINI_API_KEY,
    temperature=0,
    tools=[{"google_search": {}}],
)


def enrich_product(product: ExtractedProduct) -> dict:
    """
    Gemini 2.0 Flash로 상품 가격/리뷰/성분/feature 정보를 수집·보강한다.
    반환값: price_data, review_data, product_features, ingredient_data, analysis
    DB 저장은 product_repository에서 담당.
    """
    category = product.category or {}
    attrs = product.attributes or {}

    prompt = build_prompt(
        product_name=product.product_name or "",
        brand=product.brand or "",
        category_main=category.get("main") or "skincare",
        category_sub=category.get("sub") or "",
        shade=attrs.get("shade"),
        volume=attrs.get("volume"),
        unit=attrs.get("unit") or "",
    )

    logger.info("[gemini_enricher] Gemini API 호출 | model=%s | name=%s | brand=%s", settings.GEMINI_MODEL, product.product_name, product.brand)
    t0 = time.perf_counter()
    response = _client.invoke([HumanMessage(content=prompt)])
    logger.info("[gemini_enricher] Gemini API 응답 | %.2fs | 응답길이=%d자", time.perf_counter() - t0, len(response.content or ""))

    raw = response.content or ""
    match = re.search(r"```json\s*([\s\S]+?)\s*```", raw)
    if match:
        raw = match.group(1)
    elif raw.strip().startswith("{"):
        raw = raw.strip()

    try:
        result = json.loads(raw)
        logger.info(
            "[gemini_enricher] JSON 파싱 성공 | keys=%s",
            list(result.keys()),
        )
        return result
    except json.JSONDecodeError as e:
        logger.error("[gemini_enricher] JSON 파싱 실패 | error=%s | raw_preview=%s", e, raw[:200])
        raise
