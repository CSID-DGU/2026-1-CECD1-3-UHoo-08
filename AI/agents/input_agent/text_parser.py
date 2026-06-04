import json
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

from config import settings
from models.extracted_product import ExtractedProduct

PROMPT = """너는 화장품 상품 정보 추출 전문가이다.

주어진 텍스트에서 언급된 정보만 근거로 상품 정보를 추출하라.
텍스트에 없는 정보는 절대 추측하지 말고 null로 출력하라.

반드시 유효한 JSON만 출력하라.
설명 문장, 마크다운, 코드블록은 출력하지 마라.

[추출 대상]

{
  "product_name": null,
  "brand": null,
  "category": {
    "main": null,
    "sub": null
  },
  "attributes": {
    "shade": null,
    "type": null,
    "volume": null,
    "unit": null
  }
}

[카테고리 분류 기준]
category.main은 아래 4개 코드 중 하나로만 입력하라.
category.sub는 해당 main에 속하는 세부 제품 유형(한국어)을 입력하라.

- main=base → sub: 쿠션, 파운데이션, 프라이머, 컨실러 중 하나
- main=sun  → sub: 선크림, 선스틱, 선쿠션, 선스프레이 중 하나
- main=lip  → sub: 틴트, 립스틱, 립글로스, 립밤 중 하나
- main=skincare → sub: 토너, 에센스, 세럼, 크림, 오일, 로션 중 하나

[규칙]
- brand: 텍스트 맨 앞 단어는 화장품 브랜드일 가능성이 매우 높다. 반드시 추출하라.
  한글 브랜드는 영문으로 변환하라 (예: 달바→DALBA, 라운드랩→ROUNDLAB, 롬앤→ROMAND, 클리오→CLIO, 헤라→HERA, 미샤→MISSHA, 토니모리→TONYMOLY, 이니스프리→INNISFREE, 에뛰드→ETUDE).
  영문 브랜드는 대문자로 표기 (예: HERA, LANEIGE, PRETTYSKIN).
  product_name에서 브랜드명은 제외하라.
- volume: 숫자만 추출 (예: "15g" → 15, "100mL" → 100)
- unit: g 또는 ml 중 하나만
- 모르는 값은 null."""

_client = ChatOpenAI(
    model=settings.QWEN_LLM_MODEL,
    api_key=settings.QWEN_LLM_API_KEY,
    base_url=settings.QWEN_LLM_BASE_URL,
    temperature=0,
    max_tokens=1024,
)


def parse_text(text: str) -> ExtractedProduct:
    message = HumanMessage(content=f"{PROMPT}\n\n[입력 텍스트]\n{text}")
    response = _client.invoke([message])

    raw = response.content.strip()
    if raw.startswith("```"):
        raw = raw.strip("`").removeprefix("json").strip()

    return ExtractedProduct(**json.loads(raw))
