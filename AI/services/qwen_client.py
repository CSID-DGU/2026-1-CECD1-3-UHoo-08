"""
Qwen-Plus 호출용 싱글톤 클라이언트.

DashScope의 OpenAI-compatible 엔드포인트를 사용하므로 openai SDK 그대로 사용 가능.
LLM/VLM 담당의 VLM 호출 패턴과 키·base_url 분리 (QWEN_LLM_* 환경변수).

사용 예:
    from services.qwen_client import get_qwen_llm

    client = get_qwen_llm()
    resp = await client.chat(
        system="당신은 ...",
        user="...",
        response_json=True,
    )
"""
from __future__ import annotations

import asyncio
import json
from functools import lru_cache
from typing import Any, Dict, Optional

from openai import OpenAI

from config import settings


class QwenLLMClient:
    """Qwen-Plus 호출 래퍼. 동기 SDK를 to_thread로 감싸 async 노출."""

    def __init__(self) -> None:
        self._client = OpenAI(
            api_key=settings.DASHSCOPE_API_KEY,
            base_url=settings.QWEN_TEXT_BASE_URL,
        )
        self._model = settings.QWEN_TEXT_MODEL

    async def chat(
        self,
        system: str,
        user: str,
        response_json: bool = False,
        temperature: float = 0.0,
    ) -> str:
        """
        chat completion 호출.

        response_json=True면 response_format을 json_object로 강제하고
        파싱 가능한 JSON 문자열만 반환.
        """
        def _do_call() -> str:
            kwargs: Dict[str, Any] = {
                "model": self._model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": temperature,
            }
            if response_json:
                kwargs["response_format"] = {"type": "json_object"}
            resp = self._client.chat.completions.create(**kwargs)
            return resp.choices[0].message.content or ""

        return await asyncio.to_thread(_do_call)

    async def chat_json(
        self,
        system: str,
        user: str,
        temperature: float = 0.0,
    ) -> Optional[Dict[str, Any]]:
        """JSON 응답 호출 + 파싱. 파싱 실패 시 None."""
        raw = await self.chat(system, user, response_json=True, temperature=temperature)
        if not raw:
            return None
        # 코드블록 펜스 방어
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`").removeprefix("json").strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return None


@lru_cache(maxsize=1)
def get_qwen_llm() -> QwenLLMClient:
    """싱글톤 인스턴스 반환."""
    return QwenLLMClient()