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
    model=settings.QWEN_TEXT_MODEL,
    api_key=settings.DASHSCOPE_API_KEY,
    base_url=settings.QWEN_TEXT_BASE_URL,
    temperature=0,
)

SYSTEM_PROMPT = """당신은 화장품 추천 에이전트입니다. 주어진 도구를 자율적으로 판단해 호출하세요.

## 사용 가능한 도구

- run_discovery_agent: 사용자 프로필과 RAG 컨텍스트로 후보 상품을 탐색합니다. candidates를 반환합니다.
- run_score_agent: 후보 상품의 예산·가격·리뷰·개인화 점수를 계산합니다.
- run_alternative_agent: 기준 상품과 유사한 대체 상품을 벡터 검색으로 찾습니다.
- run_collaborative_agent: 유사한 피부 조건의 사용자들이 선호한 상품을 추천합니다.

## 도구 의존 관계

- run_discovery_agent: 후보 상품(candidates)과 intent_vector를 생성합니다. run_score_agent보다 먼저 실행해야 합니다.
- run_score_agent: run_discovery_agent의 candidates가 필요합니다. discovery 완료 후 호출하세요.
- run_alternative_agent: discovery와 무관하게 독립 실행 가능합니다.
- run_collaborative_agent: discovery와 무관하게 독립 실행 가능합니다.

## 필수 규칙

1. 모든 도구 호출 시 컨텍스트의 "작업 ID" 값을 job_id 파라미터로 반드시 전달하세요.
2. run_collaborative_agent와 run_alternative_agent 호출 시 "기준 상품 ID"를 exclude_product_ids에 반드시 포함하세요. (예: exclude_product_ids='["기준상품ID"]')
3. 도구가 반환한 배열은 절대 수정하지 마세요. 상품 이름·브랜드·가격 등 모든 필드를 도구 반환값 그대로 복사하세요.

## 최종 출력
모든 도구 호출이 끝나면 반드시 아래 JSON만 출력하라. 설명, 마크다운, 코드블록 없이 순수 JSON만.

{
  "matchScore": <run_score_agent 최고 점수 또는 0~100 정수>,
  "matchLabel": <"인생템 확률 매칭"|"높은 적합도"|"괜찮은 선택"|"추천 상품">,
  "aiReason": <사용자 피부·예산 조건 기반 추천 이유 1~2문장, 한국어>,
  "similarUserProducts": <run_collaborative_agent 반환값 그대로>,
  "alternativeProducts": <run_alternative_agent 반환값 그대로>
}
"""

agent_graph = create_react_agent(
    model=_llm,
    tools=ALL_TOOLS,
    prompt=SYSTEM_PROMPT,
)
