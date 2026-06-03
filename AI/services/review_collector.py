"""
올리브영 실제 리뷰 수집.

Gemini (Google Search grounding)로 상품별 실제 리뷰를 조회해 reviews 테이블에 저장한다.
seed-products(product_crawler)와 동일한 google_search 방식을 사용하되,
결합도를 낮추기 위해 product_crawler를 import하지 않고 호출 패턴만 재사용한다.

reviews → (reembed_reviews) → review_embeddings 흐름의 시작점.
"""
from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

from google import genai
from google.genai import types

from config import settings
from db.supabase_client import get_supabase

_CATEGORY_LABEL = {
    "base": "베이스 메이크업",
    "sun": "선케어",
    "lip": "립 메이크업",
    "skincare": "스킨케어",
}


def _make_review_prompt(brand: str, name: str, n: int) -> str:
    return f"""올리브영에서 판매하는 "{brand} {name}" 제품의 실제 사용자 리뷰를 {n}개 검색하라.

각 리뷰를 아래 JSON 형식으로 반환하라.
반드시 유효한 JSON만 출력하라. 설명·마크다운·코드블록 출력 금지.

[출력 형식]
{{
  "reviews": [
    {{"content": "실제 리뷰 내용 (1~3문장)", "rating": 평점(1~5 정수, 모르면 null)}}
  ]
}}

[규칙]
- 올리브영에 실제로 올라온 리뷰만 포함 (지어내지 말 것)
- 긍정·중립·부정 리뷰를 골고루 포함
- 광고성·도배성 리뷰 제외
- 실제 리뷰를 찾을 수 없으면 빈 배열 반환"""


def _parse_reviews(text: str) -> List[Dict[str, Any]]:
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-z]*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```$", "", cleaned)
    try:
        return json.loads(cleaned).get("reviews", [])
    except json.JSONDecodeError:
        return []


def _fetch_products(category: str, limit: int) -> List[Dict[str, Any]]:
    """해당 카테고리 상품 조회. 리뷰 수집 대상."""
    sb = get_supabase()
    res = (
        sb.table("products")
        .select("product_id, name, brand")
        .eq("category", category)
        .limit(limit)
        .execute()
    )
    return res.data or []


def _collect_for_product(
    client, product: Dict[str, Any], per_product: int
) -> Dict[str, Any]:
    """단일 상품의 실제 리뷰 수집 후 reviews 테이블에 저장."""
    brand = product["brand"]
    name = product["name"]
    product_id = product["product_id"]

    try:
        response = client.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=_make_review_prompt(brand, name, per_product),
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
                temperature=0,
            ),
        )
    except Exception as e:
        return {"status": "error", "name": name, "brand": brand, "error": str(e)}

    reviews = _parse_reviews(response.text or "")
    payload = [
        {
            "product_id": product_id,
            "content": r["content"],
            "rating": r.get("rating"),
            "source": "OLIVEYOUNG",
        }
        for r in reviews
        if isinstance(r, dict) and r.get("content")
    ]
    if not payload:
        return {"status": "skipped", "name": name, "brand": brand, "saved": 0}

    get_supabase().table("reviews").insert(payload).execute()
    return {"status": "saved", "name": name, "brand": brand, "saved": len(payload)}


def collect_reviews(category: str, limit: int = 10, per_product: int = 8) -> Dict[str, Any]:
    """
    카테고리별 상품에 대해 Gemini Google Search로 실제 리뷰를 수집·적재.

    Args:
        category: base | sun | lip | skincare
        limit: 리뷰를 수집할 상품 수
        per_product: 상품당 목표 리뷰 수
    """
    if category not in _CATEGORY_LABEL:
        raise ValueError(f"지원하지 않는 카테고리: {category}. 허용: {list(_CATEGORY_LABEL)}")

    products = _fetch_products(category, limit)
    if not products:
        return {"category": category, "saved": 0, "skipped": 0, "errors": [], "results": []}

    client = genai.Client(api_key=settings.GEMINI_API_KEY)

    saved_reviews, skipped, errors = 0, 0, []
    results: List[Dict[str, Any]] = []

    # 병렬 처리 (동시에 상품 5개 처리)
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(_collect_for_product, client, p, per_product): p
            for p in products
        }
        for future in as_completed(futures):
            p = futures[future]
            try:
                r = future.result()
                results.append(r)
                if r["status"] == "saved":
                    saved_reviews += r["saved"]
                elif r["status"] == "skipped":
                    skipped += 1
                else:
                    errors.append({"name": r.get("name"), "error": r.get("error")})
            except Exception as e:
                errors.append({"name": p.get("name"), "error": str(e)})

    return {
        "category": category,
        "saved": saved_reviews,
        "skipped": skipped,
        "errors": errors,
        "results": results,
    }