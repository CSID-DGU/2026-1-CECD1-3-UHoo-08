import json
import re
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage

from config import settings
from models.extracted_product import ExtractedProduct
from prompts.gemini_extraction import build_prompt

def _make_client(temperature: float) -> ChatGoogleGenerativeAI:
    # 요구하는 JSON이 가격·리뷰·성분·feature까지 한 덩어리라 기본 출력 한도로는
    # 문장 중간에서 잘린다("Unterminated string"). 넉넉히 잡는다.
    return ChatGoogleGenerativeAI(
        model=settings.GEMINI_MODEL,
        google_api_key=settings.GEMINI_API_KEY,
        temperature=temperature,
        max_output_tokens=8192,
        tools=[{"google_search": {}}],
    )


_client = _make_client(0)

# 재시도는 온도를 올려서 한다. 온도 0에서는 같은 프롬프트가 같은 실패를
# 그대로 되풀이한다. 실제로 특정 제품에서 모델이 "0"만 수천 자 뱉다가
# MAX_TOKENS로 끝나는 퇴화 루프에 빠졌고, 같은 온도로는 몇 번을 해도 같았다.
_RETRY_TEMPERATURES = (0.0, 0.4, 0.8)


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

    # 검색 그라운딩이 붙으면 JSON 대신 산문만 돌려주거나 응답이 잘리는 일이
    # 이따금 있다. 온도를 바꿔가며 다시 물으면 대개 통과한다.
    last_error: Exception | None = None
    for temperature in _RETRY_TEMPERATURES:
        client = _client if temperature == 0 else _make_client(temperature)
        response = client.invoke([HumanMessage(content=prompt)])
        try:
            return _parse_json(response.content or "")
        except (ValueError, json.JSONDecodeError) as e:
            last_error = e
    raise last_error


def _parse_json(raw: str) -> dict:
    """
    Gemini 응답에서 JSON 객체를 꺼낸다.

    검색 도구를 붙이면 JSON 뒤에 설명 문장이나 두 번째 블록이 붙어 오는 일이
    있어 json.loads가 "Extra data"로 실패한다. 첫 번째 객체만 읽고 뒤는 버린다.
    """
    match = re.search(r"```json\s*([\s\S]+?)\s*```", raw)
    if match:
        raw = match.group(1)

    start = raw.find("{")
    if start == -1:
        raise ValueError("응답에 JSON 객체가 없습니다")

    # raw_decode는 첫 객체만 읽고 나머지 텍스트를 무시한다.
    return json.JSONDecoder().raw_decode(raw, start)[0]
