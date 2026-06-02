"""
자연어 검색 쿼리 처리.

1. classify_intent: 쿼리 의도 분류 (PRODUCT_NAME | RECOMMENDATION)
2. parse_query    : 추천 의도일 때 카테고리 + feature 추출

input_agent.text_parser와 구분:
- text_parser : "라네즈 네오쿠션 21호" → 특정 상품 식별 (입력 파이프라인, LLM/VLM)
- query_parser: "여름 가벼운 쿠션" or "라네즈 네오쿠션 21호" → 검색 의도 해석 (추천 파이프라인, 본 모듈)

Qwen 호출은 공통 qwen_client를 재사용한다.
"""
from typing import Any, Dict, Optional, TypedDict

from prompts.intent_classification import INTENT_CLASSIFICATION_SYSTEM
from prompts.query_extraction import QUERY_EXTRACTION_SYSTEM
from services.qwen_client import get_qwen_llm

_VALID_CATEGORIES = {"base", "sun", "lip", "skincare"}
_VALID_INTENTS = {"PRODUCT_NAME", "RECOMMENDATION"}


class ParsedQuery(TypedDict):
    category: Optional[str]
    features: Dict[str, Any]


async def classify_intent(query: str) -> str:
    """
    쿼리 의도 분류 → "PRODUCT_NAME" | "RECOMMENDATION".

    분류 실패·애매한 경우는 RECOMMENDATION으로 폴백 (조건 검색이 더 안전).
    """
    if not query or not query.strip():
        return "RECOMMENDATION"

    llm = get_qwen_llm()
    result = await llm.chat_json(system=INTENT_CLASSIFICATION_SYSTEM, user=query)

    if not result or not isinstance(result, dict):
        return "RECOMMENDATION"

    intent = result.get("intent")
    if intent not in _VALID_INTENTS:
        return "RECOMMENDATION"
    return intent


async def parse_query(query: str) -> ParsedQuery:
    """
    추천 의도일 때만 호출!
    자연어 쿼리 → {category, features}.

    파싱 실패·잘못된 카테고리는 category=None, features={}로 안전 처리.
    category가 None이면 search_service가 전체 카테고리 검색으로 폴백.
    """
    if not query or not query.strip():
        return ParsedQuery(category=None, features={})

    llm = get_qwen_llm()
    result = await llm.chat_json(system=QUERY_EXTRACTION_SYSTEM, user=query)

    if not result or not isinstance(result, dict):
        return ParsedQuery(category=None, features={})

    category = result.get("category")
    if category not in _VALID_CATEGORIES:
        category = None

    features = result.get("features")
    if not isinstance(features, dict):
        features = {}

    return ParsedQuery(category=category, features=features)
