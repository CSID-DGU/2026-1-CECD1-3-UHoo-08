import os

from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from config import settings
from agents.tools import ALL_TOOLS

# LangSmith 트레이싱 설정
if settings.LANGSMITH_API_KEY:
    os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
    os.environ.setdefault("LANGCHAIN_API_KEY", settings.LANGSMITH_API_KEY)
    os.environ.setdefault("LANGCHAIN_PROJECT", settings.LANGSMITH_PROJECT)

_llm = ChatOpenAI(
    model=settings.QWEN_LLM_MODEL,
    api_key=settings.QWEN_LLM_API_KEY,
    base_url=settings.QWEN_LLM_BASE_URL,
    temperature=0,
)

SYSTEM_PROMPT = """당신은 화장품 추천 에이전트입니다. 주어진 도구를 자율적으로 판단해 호출하세요.

## 사용 가능한 도구

- run_discovery_agent: 후보 상품 탐색. candidates, base_product_id, exclude_product_ids를 반환합니다.
- run_alternative_agent: 대체 상품 탐색. run_discovery_agent가 반환한 base_product_id와 exclude_product_ids를 그대로 전달하세요.
- run_collaborative_agent: 유사 사용자 선호 상품 추천.
- run_score_agent: 후보 상품 점수 계산. run_discovery_agent가 반환한 candidates를 그대로 전달하세요.

## 실행 순서

1. run_discovery_agent 호출
2. run_discovery_agent 결과의 base_product_id, exclude_product_ids를 run_alternative_agent에 그대로 전달
3. run_discovery_agent 결과의 base_product_id, exclude_product_ids를 run_collaborative_agent에 그대로 전달
4. run_discovery_agent 결과의 candidates를 run_score_agent에 그대로 전달

⚠️ 4개 도구를 모두 호출하기 전에는 절대 JSON을 출력하지 마세요.

## 필수 규칙

1. 모든 도구 호출 시 컨텍스트의 "작업 ID" 값을 job_id 파라미터로 반드시 전달하세요.
2. 도구가 반환한 값은 절대 수정하지 마세요. 그대로 다음 도구에 전달하세요.

## 최종 출력
모든 도구 호출이 끝나면 반드시 아래 JSON만 출력하라. 설명, 마크다운, 코드블록 없이 순수 JSON만.
도구가 빈 배열이나 오류를 반환해도 반드시 아래 형식의 JSON을 출력하라.

{"matchScore": <run_score_agent 최고 점수, 없으면 0>, "matchLabel": <점수 기반: 90이상="인생템 확률 매칭", 70이상="높은 적합도", 50이상="괜찮은 선택", 나머지="추천 상품">, "aiReason": <사용자 피부·예산 조건 기반 추천 이유 1~2문장 한국어>, "similarUserProducts": <run_collaborative_agent 반환값, 없으면 []>, "alternativeProducts": <run_alternative_agent 반환값, 없으면 []>}
"""

agent_graph = create_react_agent(
    model=_llm,
    tools=ALL_TOOLS,
    prompt=SYSTEM_PROMPT,
)
