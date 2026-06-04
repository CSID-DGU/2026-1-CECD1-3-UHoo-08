import json
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

from config import settings
from models.extracted_product import ExtractedProduct
from agents.input_agent.brand_map import BRAND_MAP

PROMPT = """너는 화장품 상품 정보 추출 전문가이다.
텍스트에서 아래 JSON 형식으로만 응답하라. 설명, 마크다운, 코드블록 금지.
텍스트에 없는 정보는 null로 출력하라.

[출력 형식]
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

[규칙]
1. brand: 텍스트 첫 단어가 브랜드다. 한글이면 영문으로, 영문이면 대문자로 표기.
2. product_name: 브랜드명 제외한 나머지
3. category.main / category.sub 매핑:
   - main=base  → sub: 쿠션, 파운데이션, 프라이머, 컨실러 중 하나
   - main=sun   → sub: 선크림, 선스틱, 선쿠션, 선스프레이 중 하나
   - main=lip   → sub: 틴트, 립스틱, 립글로스, 립밤 중 하나 (밤스틱→립밤)
   - main=skincare → sub: 토너, 에센스, 세럼, 크림, 오일, 로션 중 하나
4. volume: 숫자만 (15g→15), unit: g 또는 ml

[예시]
입력: 웨이크메이크 소프트 블러링 밤 스틱
출력:
{
  "product_name": "소프트 블러링 밤 스틱",
  "brand": "WAKEMAKE",
  "category": {"main": "lip", "sub": "립밤"},
  "attributes": {"shade": null, "type": null, "volume": null, "unit": null}
}

입력: 롬앤 쥬시 라스팅 틴트 피그 로즈
출력:
{
  "product_name": "쥬시 라스팅 틴트 피그 로즈",
  "brand": "ROMAND",
  "category": {"main": "lip", "sub": "틴트"},
  "attributes": {"shade": "피그 로즈", "type": null, "volume": null, "unit": null}
}

입력: 달바 화이트 트러플 퍼스트 스프레이 세럼 100mL
출력:
{
  "product_name": "화이트 트러플 퍼스트 스프레이 세럼",
  "brand": "DALBA",
  "category": {"main": "skincare", "sub": "세럼"},
  "attributes": {"shade": null, "type": null, "volume": 100, "unit": "ml"}
}

입력: LANEIGE 립 슬리핑 마스크 베리
출력:
{
  "product_name": "립 슬리핑 마스크",
  "brand": "LANEIGE",
  "category": {"main": "lip", "sub": "립밤"},
  "attributes": {"shade": "베리", "type": null, "volume": null, "unit": null}
}"""

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

    result = ExtractedProduct(**json.loads(raw))

    first_word = text.strip().split()[0] if text.strip() else ""
    if first_word in BRAND_MAP:
        result.brand = BRAND_MAP[first_word]

    return result
