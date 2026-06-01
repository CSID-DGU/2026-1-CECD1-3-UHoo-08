"""
자연어 쿼리에서 카테고리 + feature_json 추출.

Qwen (DashScope) 텍스트 모델을 사용해 사용자 입력을 구조화된 feature로 변환한다.
"""
from __future__ import annotations

import json
import re

from openai import OpenAI

from config import settings

_SCHEMA_HINT = """
base (쿠션,파운데이션,프라이머,컨실러):
  product_type: 쿠션|파운데이션|프라이머|컨실러
  coverage: 가벼운|중간|높음
  finish: 매트|세미매트|글로우|촉촉
  skin_type: 건성|지성|복합|민감
  skin_concern: [모공,잡티,칙칙함,트러블] 또는 null
  personal_color: 웜톤|쿨톤|뉴트럴 또는 null
  lasting_power: 낮음|중간|높음

sun (선크림,선스틱,선쿠션,선스프레이):
  product_type: 선크림|선스틱|선쿠션|선스프레이
  finish: 매트|세미매트|촉촉
  skin_type: 건성|지성|복합|민감
  skin_concern: [진정,보습,미백] 또는 null
  lasting_power: 낮음|중간|높음
  white_cast: true|false 또는 null

lip (틴트,립스틱,립글로스,립밤):
  product_type: 틴트|립스틱|립글로스|립밤
  finish: 매트|세미매트|글로우|촉촉
  personal_color: 웜톤|쿨톤|뉴트럴 또는 null
  lasting_power: 낮음|중간|높음
  moisturizing: true|false 또는 null
  skin_concern: [보습,각질] 또는 null

skincare (토너,에센스,세럼,크림,오일,로션):
  product_type: 토너|에센스|세럼|크림|오일|로션
  texture: 가벼운|중간|진한
  skin_type: 건성|지성|복합|민감
  skin_concern: [보습,미백,주름,진정,모공] 또는 null
  key_ingredient: 배열 또는 null
  fragrance_free: true|false 또는 null
"""


def parse_query(query: str) -> dict:
    """자연어 쿼리 → { category, features } 딕셔너리 반환."""
    client = OpenAI(
        api_key=settings.DASHSCOPE_API_KEY,
        base_url=settings.QWEN_VL_BASE_URL,
    )

    prompt = f"""사용자가 화장품을 검색하는 자연어 문장을 분석하여 JSON으로만 반환하라.
설명·마크다운·코드블록 출력 금지.

[카테고리]
- base: 쿠션, 파운데이션, 프라이머, 컨실러
- sun: 선크림, 선스틱, 선쿠션, 선스프레이, 자외선차단
- lip: 틴트, 립스틱, 립글로스, 립밤
- skincare: 토너, 에센스, 세럼, 크림, 오일, 로션, 스킨케어

[카테고리별 feature 허용값]
{_SCHEMA_HINT}

[출력 형식]
{{
  "category": "base|sun|lip|skincare",
  "features": {{
    ... 쿼리에서 파악 가능한 feature만 포함, 나머지는 null
  }}
}}

[사용자 입력] {query}"""

    response = client.chat.completions.create(
        model=settings.QWEN_TEXT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )

    text = (response.choices[0].message.content or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)

    return json.loads(text)
