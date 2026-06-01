import os

from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from config import settings
from agents.tools import ALL_TOOLS
from graph.state import GraphState

# LangSmith 트레이싱 설정
if settings.LANGSMITH_API_KEY:
    os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
    os.environ.setdefault("LANGCHAIN_API_KEY", settings.LANGSMITH_API_KEY)
    os.environ.setdefault("LANGCHAIN_PROJECT", settings.LANGSMITH_PROJECT)

_llm = ChatOpenAI(
    model=settings.QWEN_TEXT_MODEL,
    api_key=settings.DASHSCOPE_API_KEY,
    base_url=settings.QWEN_TEXT_BASE_URL,
    temperature=0,
)

SYSTEM_PROMPT = """당신은 화장품 추천 에이전트입니다.

## 사용 가능한 도구

- run_discovery_agent: 사용자 프로필과 RAG 컨텍스트로 후보 상품을 탐색합니다. candidates와 intent_vector를 반환합니다.
- run_score_agent: 후보 상품에 예산·가격·리뷰·개인화 점수를 계산합니다. candidates와 intent_vector가 있어야 실행할 수 있습니다.
- run_alternative_agent: 기준 상품과 유사한 대체 상품을 벡터 검색으로 찾습니다. base_product_id가 있을 때 사용합니다.
- run_collaborative_agent: 유사한 피부 조건의 사용자들이 선호한 상품을 추천합니다. 언제든 실행할 수 있습니다.

## 최종 출력
모든 도구 호출이 끝나면 반드시 아래 JSON만 출력하라. 설명, 마크다운, 코드블록 없이 순수 JSON만.

{
  "matchScore": <score_agent 최고 점수 또는 0~100 정수>,
  "matchLabel": <"인생템 확률 매칭"|"높은 적합도"|"괜찮은 선택"|"추천 상품">,
  "aiReason": <사용자 피부·예산 조건 기반 추천 이유 1~2문장, 한국어>,
  "similarUserProducts": <run_collaborative_agent 결과 배열>,
  "alternativeProducts": <run_alternative_agent 결과 배열>
}
"""

agent_graph = create_react_agent(
    model=_llm,
    tools=ALL_TOOLS,
    prompt=SYSTEM_PROMPT,
)
