"""
자연어 쿼리에서 카테고리 + feature_json 추출.

qwen_client 싱글톤을 재사용해 별도 OpenAI 클라이언트를 생성하지 않는다.
"""
from __future__ import annotations

from prompts.query_extraction import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from services.qwen_client import get_qwen_llm


async def parse_query(query: str) -> dict:
    """자연어 쿼리 → { category, features } 딕셔너리 반환."""
    client = get_qwen_llm()
    result = await client.chat_json(
        system=SYSTEM_PROMPT,
        user=USER_PROMPT_TEMPLATE.format(query=query),
    )
    return result or {}
