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
  },
  "package_claims": [],
  "detected_objects": []
}

[카테고리 분류 기준]
- base: 쿠션, 파운데이션, 프라이머, 컨실러
- sun: 선크림, 선스틱, 선쿠션, 선스프레이
- lip: 틴트, 립스틱, 립글로스, 립밤
- skincare: 토너, 에센스, 세럼, 크림, 오일, 로션, 핸드크림 등 기타 스킨케어
category.sub에는 위 세부 제품 유형을 그대로 입력하라.

[규칙]
- detected_objects: 텍스트에서 언급된 상품명, 성분, 특징 등 주요 키워드를 넣어라.
- package_claims: 텍스트에서 언급된 효능/특징 문구만 넣어라.
- brand: 영문 대문자로 표기 (예: HERA, LANEIGE, PRETTYSKIN)
- volume: 숫자만 추출 (예: "15g" → 15, "100mL" → 100)
- unit: g 또는 ml 중 하나만
- 모르는 값은 null. 배열 정보가 없으면 빈 배열 []."""

_client = ChatOpenAI(
    model=settings.QWEN_TEXT_MODEL,
    api_key=settings.DASHSCOPE_API_KEY,
    base_url=settings.QWEN_TEXT_BASE_URL,
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
