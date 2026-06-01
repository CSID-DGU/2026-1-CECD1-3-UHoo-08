import json
import re
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage

from config import settings
from models.extracted_product import ExtractedProduct
from prompts.gemini_extraction import build_prompt

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

    response = _client.invoke([HumanMessage(content=prompt)])

    raw = response.content or ""
    match = re.search(r"```json\s*([\s\S]+?)\s*```", raw)
    if match:
        raw = match.group(1)
    elif raw.strip().startswith("{"):
        raw = raw.strip()

    return json.loads(raw)
