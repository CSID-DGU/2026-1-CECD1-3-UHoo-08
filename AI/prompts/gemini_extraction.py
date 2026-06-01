# 카테고리별 feature 스키마 — 노션 "화장품 카테고리별 Feature 정리 목록" 기준
FEATURE_SCHEMAS = {
    "base": """{
  "product_type": "쿠션 | 파운데이션 | 프라이머 | 컨실러",
  "coverage": "가벼운 | 중간 | 높음",
  "finish": "매트 | 세미매트 | 글로우 | 촉촉",
  "skin_type": "건성 | 지성 | 복합 | 민감",
  "skin_concern": ["모공", "잡티", "칙칙함", "트러블"] 또는 null,
  "personal_color": "웜톤 | 쿨톤 | 뉴트럴",
  "lasting_power": "낮음 | 중간 | 높음",
  "spf": "SPF50+/PA++++ 형식 또는 null"
}""",
    "sun": """{
  "product_type": "선크림 | 선스틱 | 선쿠션 | 선스프레이",
  "spf": "SPF50+ 형식",
  "pa": "PA++++ 형식",
  "finish": "매트 | 세미매트 | 촉촉",
  "skin_type": "건성 | 지성 | 복합 | 민감",
  "skin_concern": ["진정", "보습", "미백"] 또는 null,
  "lasting_power": "낮음 | 중간 | 높음",
  "white_cast": true 또는 false
}""",
    "lip": """{
  "product_type": "틴트 | 립스틱 | 립글로스 | 립밤",
  "finish": "매트 | 세미매트 | 글로우 | 촉촉",
  "personal_color": "웜톤 | 쿨톤 | 뉴트럴",
  "lasting_power": "낮음 | 중간 | 높음",
  "moisturizing": true 또는 false,
  "skin_concern": ["보습", "각질"] 또는 null
}""",
    "skincare": """{
  "product_type": "토너 | 에센스 | 세럼 | 크림 | 오일 | 로션 | 핸드크림 등",
  "skin_type": "건성 | 지성 | 복합 | 민감",
  "skin_concern": ["보습", "미백", "주름", "진정", "모공"] 또는 null,
  "key_ingredient": ["히알루론산", "나이아신아마이드", "레티놀"] 또는 null,
  "texture": "가벼운 | 중간 | 진한",
  "fragrance_free": true 또는 false
}""",
}


def build_prompt(product_name: str, brand: str, category_main: str,
                 category_sub: str, shade: str, volume: str, unit: str) -> str:
    feature_schema = FEATURE_SCHEMAS.get(category_main, FEATURE_SCHEMAS["skincare"])
    vol_str = f"{volume}{unit}" if volume else "null"

    return f"""너는 화장품 정보 통합 수집 및 분석 전문가이다.

다음 상품에 대해 가격, 리뷰, 성분 정보를 통합 수집하고,
카테고리에 맞는 feature를 적용하여 구조화된 데이터를 생성하라.

---

[상품 정보]
- 상품명: {product_name}
- 브랜드: {brand}
- 카테고리 (main): {category_main}
- 카테고리 (sub): {category_sub}
- 옵션:
  - shade: {shade or "null"}
  - volume: {vol_str}

---

[분석 목표]
1. 가격 정보를 수집하여 실제 결제 기준 최저가를 계산한다
2. 리뷰를 분석하여 사용감을 요약한다
3. 성분 정보를 정리한다
4. 카테고리에 맞는 feature를 생성한다

---

[데이터 수집 범위]
- 가격: 올리브영, 쿠팡, 네이버쇼핑
- 리뷰: 올리브영, 화해
- 성분: 화해
※ 핵심 사이트만 탐색하고 불필요한 확장은 하지 말 것

---

# 0. 상품 이미지
- image_url: 올리브영 공식 상품 페이지의 대표 이미지 URL. 없으면 빈 문자열.

# 1. 가격 정보 수집
- 판매가, 배송비, 할인(브랜드/세일), 쿠폰, 상품 구성(단품/세트/리필), ml당 가격
- final_price = price + shipping_fee - discount - coupon
- original_price: 할인·쿠폰 적용 전 공식 정가 (브랜드 공식 판매가 기준)

# 2. 리뷰 분석
- 반복되는 핵심 의견 추출
- 긍정 / 부정 구분
- 실제 사용감 중심 요약
- 올리브영·화해 평점 수집 (average_score: 소수점 1자리, review_count: 리뷰 수)
- 가장 많이 언급된 피부타입의 만족도 수집 (skin_type_satisfaction: skinType + satisfactionPercent)

# 3. 성분 분석
- 주요 성분, 주의 성분, 피부 적합성

# 4. Feature 생성
카테고리({category_main})에 맞는 아래 스키마를 사용하라.
허용값 외의 값은 절대 사용하지 마라. 해당 없는 필드는 null.

{feature_schema}

---

# 5. 출력 형식

반드시 유효한 JSON만 출력하라. 마크다운, 코드블록, 설명 없이 순수 JSON만 출력하라.

{{
  "image_url": "",
  "price_data": {{
    "original_price": 0,
    "best_option": {{
      "platform": "",
      "final_price": 0,
      "reason": ""
    }},
    "options": [
      {{
        "platform": "",
        "price": 0,
        "shipping_fee": 0,
        "discount": 0,
        "coupon": 0,
        "final_price": 0,
        "package": ""
      }}
    ]
  }},
  "review_data": {{
    "positive": [],
    "negative": [],
    "summary": "",
    "average_score": 0.0,
    "review_count": 0,
    "skin_type_satisfaction": {{
      "skinType": "",
      "satisfactionPercent": 0
    }}
  }},
  "product_features": {{}},
  "ingredient_data": {{
    "key_ingredients": [],
    "warnings": [],
    "skin_suitability": ""
  }},
  "analysis": {{
    "price_summary": "",
    "review_insight": "",
    "overall_summary": ""
  }}
}}

---

[주의사항]
- 반드시 카테고리에 맞는 feature만 사용하라
- 동일 상품 여부(색상, 용량, 구성) 확인
- 단순 최저가가 아닌 실제 결제 금액 기준으로 판단
- 리뷰는 실제 사용자 의견 기반으로 분석
- 불확실한 할인 정보는 제외"""
