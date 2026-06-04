"""
올리브영 카테고리별 제품 시딩.

Gemini (Google Search grounding)로 올리브영 실제 판매 제품을 조회하고,
feature_json 스키마에 맞게 추출한 뒤 Supabase에 저장한다.
제품 이미지는 Gemini에게 직접 요청하여 inline_data로 받아 Storage에 업로드한다.
"""
from __future__ import annotations

import json
import re
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any, Dict, List, Optional

import cloudscraper
from google import genai
from google.genai import types

from config import settings
from db.supabase_client import get_supabase

_scraper = cloudscraper.create_scraper()

# ── 카테고리 메타 ──────────────────────────────────────────────────────────

_CATEGORY_LABEL = {
    "base": "베이스 메이크업 (쿠션, 파운데이션, 프라이머, 컨실러)",
    "sun": "선케어 (선크림, 선스틱, 선쿠션, 선스프레이)",
    "lip": "립 메이크업 (틴트, 립스틱, 립글로스, 립밤)",
    "skincare": "스킨케어 (토너, 에센스, 세럼, 크림, 오일, 로션)",
}

_FEATURE_SCHEMA = {
    "base": """{
  "product_type": "쿠션 | 파운데이션 | 프라이머 | 컨실러",
  "coverage": "가벼운 | 중간 | 높음",
  "finish": "매트 | 세미매트 | 글로우 | 촉촉",
  "skin_type": "건성 | 지성 | 복합 | 민감",
  "skin_concern": ["모공", "잡티", "칙칙함", "트러블"] 또는 null,
  "personal_color": "웜톤 | 쿨톤 | 뉴트럴 | null",
  "lasting_power": "낮음 | 중간 | 높음",
  "spf": "예: SPF50+/PA++++ 또는 null"
}""",
    "sun": """{
  "product_type": "선크림 | 선스틱 | 선쿠션 | 선스프레이",
  "spf": "예: SPF50+",
  "pa": "예: PA++++",
  "finish": "매트 | 세미매트 | 촉촉",
  "skin_type": "건성 | 지성 | 복합 | 민감",
  "skin_concern": ["진정", "보습", "미백"] 또는 null,
  "lasting_power": "낮음 | 중간 | 높음",
  "white_cast": true | false
}""",
    "lip": """{
  "product_type": "틴트 | 립스틱 | 립글로스 | 립밤",
  "finish": "매트 | 세미매트 | 글로우 | 촉촉",
  "personal_color": "웜톤 | 쿨톤 | 뉴트럴 | null",
  "lasting_power": "낮음 | 중간 | 높음",
  "moisturizing": true | false,
  "skin_concern": ["보습", "각질"] 또는 null
}""",
    "skincare": """{
  "product_type": "토너 | 에센스 | 세럼 | 크림 | 오일 | 로션",
  "skin_type": "건성 | 지성 | 복합 | 민감",
  "skin_concern": ["보습", "미백", "주름", "진정", "모공"] 또는 null,
  "key_ingredient": ["히알루론산", "나이아신아마이드"] 또는 null,
  "texture": "가벼운 | 중간 | 진한",
  "lasting_power": null,
  "fragrance_free": true | false
}""",
}

_STORAGE_BUCKET = "product_image"


# ── 프롬프트 (제품 정보만 — 이미지는 별도 호출) ──────────────────────────────

def _make_prompt(category: str, limit: int) -> str:
    label = _CATEGORY_LABEL[category]
    schema = _FEATURE_SCHEMA[category]
    return f"""올리브영에서 현재 실제 판매 중인 인기 {label} 제품을 {limit}개 검색하라.

각 제품의 실제 정보를 아래 JSON 형식으로 반환하라.
반드시 유효한 JSON만 출력하라. 설명 문장·마크다운·코드블록 출력 금지.

[출력 형식]
{{
  "products": [
    {{
      "name": "실제 제품명",
      "brand": "브랜드명 (영문 대문자, 예: LANEIGE)",
      "original_price": 정가(숫자, 원 단위),
      "average_score": 평점(소수점 1자리, 모르면 null),
      "review_count": 리뷰 수(숫자, 모르면 null),
      "review_summary": "한 줄 리뷰 요약 (없으면 null)",
      "skin_type_satisfaction": {{"skinType": "건성|지성|복합|민감 중 하나", "satisfactionPercent": 0~100 정수}},
      "price_options": [
        {{"platform": "올리브영", "price": 숫자, "shipping_fee": 0, "discount": 0, "coupon": 0, "final_price": 숫자}},
        {{"platform": "쿠팡", "price": 숫자, "shipping_fee": 0, "discount": 0, "coupon": 0, "final_price": 숫자}},
        {{"platform": "네이버쇼핑", "price": 숫자, "shipping_fee": 숫자, "discount": 0, "coupon": 0, "final_price": 숫자}}
      ],
      "image_url": "올리브영 CDN 이미지 직접 URL (예: https://image.oliveyoung.co.kr/...)",
      "oliveyoung_url": "https://www.oliveyoung.co.kr/store/goods/getGoodsDetail.do?goodsNo=...",
      "feature_json": {schema}
    }}
  ]
}}

[규칙]
- 올리브영에서 실제 판매 중인 제품만 포함
- image_url은 올리브영 상품 이미지 CDN 직접 URL (image.oliveyoung.co.kr 도메인, 조회 불가 시 null)
- oliveyoung_url은 해당 제품의 실제 올리브영 상품 상세 페이지 URL (조회 불가 시 null)
- price_options는 올리브영·쿠팡·네이버쇼핑 3개 플랫폼 기준, 모르면 해당 항목 제외
- skin_type_satisfaction: 리뷰에서 가장 많이 언급된 피부타입과 만족도 (모르면 null)
- feature_json의 해당 없는 필드는 반드시 null (생략 금지)
- 허용값 목록 외 값 사용 금지
- skin_concern, key_ingredient는 해당 항목만 배열로, 없으면 null
- brand는 영문 대문자 공식 브랜드명
- 모든 가격은 숫자만 (원 기호 제외)
"""


# ── 이미지 URL 조회 및 다운로드 ───────────────────────────────────────────

def _find_image_url_via_gemini(brand: str, name: str) -> Optional[str]:
    """Gemini Google Search로 올리브영 상품 이미지 CDN URL 조회."""
    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    try:
        response = client.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=(
                f"올리브영에서 판매하는 {brand} {name} 상품의 대표 이미지 URL을 찾아라. "
                f"image.oliveyoung.co.kr 도메인의 실제 이미지 URL만 반환하라. "
                f"URL 외에 아무것도 출력하지 마라."
            ),
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
                temperature=0,
            ),
        )
        url = (response.text or "").strip()
        if url.startswith("http") and "oliveyoung" in url:
            print(f"[이미지] Gemini 조회 성공: {url}")
            return url
        print(f"[이미지] Gemini 조회 실패 (유효하지 않은 URL): {url!r}")
    except Exception as e:
        print(f"[이미지] Gemini 조회 오류 {brand} {name}: {e}")
    return None


def _fetch_image_from_url(image_url: str) -> tuple[Optional[bytes], str]:
    """CDN 이미지 URL에서 직접 bytes 다운로드."""
    try:
        r = _scraper.get(image_url, timeout=15)
        print(f"[이미지] 다운로드 status={r.status_code} url={image_url}")
        if r.status_code != 200:
            return None, ""
        content_type = r.headers.get("Content-Type", "image/jpeg").split(";")[0].strip()
        print(f"[이미지] 성공 size={len(r.content)} type={content_type}")
        return r.content, content_type
    except Exception as e:
        print(f"[이미지 다운로드 실패] {image_url}: {e}")
    return None, ""


# ── Supabase Storage 업로드 ────────────────────────────────────────────────

def _ext_from_content_type(ct: str) -> str:
    return {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}.get(ct, "jpg")


def _upload_image(product_id: str, image_bytes: bytes, content_type: str) -> Optional[str]:
    """Supabase Storage에 업로드 후 public URL 반환."""
    sb = get_supabase()
    path = f"{product_id}.{_ext_from_content_type(content_type)}"
    try:
        sb.storage.from_(_STORAGE_BUCKET).upload(
            path=path,
            file=image_bytes,
            file_options={"content-type": content_type, "upsert": "true"},
        )
        return sb.storage.from_(_STORAGE_BUCKET).get_public_url(path)
    except Exception as e:
        print(f"[Storage 업로드 실패] {product_id}: {e}")
        return None


# ── DB 저장 ────────────────────────────────────────────────────────────────

def _parse_response(text: str) -> List[Dict[str, Any]]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-z]*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```$", "", cleaned)
    return json.loads(cleaned).get("products", [])


def _upsert_product(product: Dict[str, Any], category: str) -> Optional[str]:
    """products 테이블 upsert. 이미 존재하면 product_id 반환."""
    sb = get_supabase()
    name = product.get("name", "").strip()
    brand = product.get("brand", "").strip()
    if not name or not brand:
        return None

    cdn_image_url = product.get("image_url") or None
    print(f"[시딩] {name} / {brand} → image_url={cdn_image_url}")

    existing = (
        sb.table("products")
        .select("product_id, image_url")
        .eq("name", name)
        .eq("brand", brand)
        .limit(1)
        .execute()
    )
    if existing.data:
        product_id = existing.data[0]["product_id"]
        if not existing.data[0].get("image_url"):
            _set_product_image(product_id, brand, name, cdn_image_url)
        return product_id

    product_id = str(uuid.uuid4())
    image_url = _resolve_image(product_id, brand, name, cdn_image_url)

    res = sb.table("products").insert({
        "product_id": product_id,
        "name": name,
        "brand": brand,
        "category": category,
        "image_url": image_url,
        "original_price": product.get("original_price"),
    }).execute()
    return res.data[0]["product_id"] if res.data else None


def _resolve_image(product_id: str, brand: str, name: str, cdn_image_url: Optional[str]) -> Optional[str]:
    url = cdn_image_url or _find_image_url_via_gemini(brand, name)
    if not url:
        return None
    img_bytes, ct = _fetch_image_from_url(url)
    if img_bytes:
        return _upload_image(product_id, img_bytes, ct)
    return None


def _set_product_image(product_id: str, brand: str, name: str, cdn_image_url: Optional[str]) -> None:
    public_url = _resolve_image(product_id, brand, name, cdn_image_url)
    if public_url:
        get_supabase().table("products").update(
            {"image_url": public_url}
        ).eq("product_id", product_id).execute()


def _build_stores(price_options: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """price_options → stores 형식 변환 (product_repository.save_enriched 동일 패턴)."""
    if not price_options:
        return []
    best_price = min((o.get("final_price") or o.get("price") or 0) for o in price_options)
    stores = []
    for opt in price_options:
        final_price = opt.get("final_price") or opt.get("price")
        shipping_fee = opt.get("shipping_fee") or 0
        stores.append({
            "storeName": opt.get("platform", ""),
            "price": final_price,
            "shippingInfo": "무료배송" if not shipping_fee else f"배송비 {shipping_fee}원",
            "isLowest": final_price == best_price,
        })
    return stores


def _upsert_product_data(product_id: str, product: Dict[str, Any], feature_json: Dict[str, Any]) -> None:
    """가격·리뷰·feature 데이터를 products 테이블에 단일 upsert."""
    sb = get_supabase()
    original_price = product.get("original_price")
    price_options = product.get("price_options") or []
    stores = _build_stores(price_options)
    lowest_price = min((s["price"] for s in stores if s["price"]), default=None)
    savings = (original_price - lowest_price) if (original_price and lowest_price) else None
    payload: Dict[str, Any] = {
        "product_id": product_id,
        "lowest_price": lowest_price,
        "savings": savings,
        "stores": stores,
        "review_summary": product.get("review_summary"),
        "average_score": product.get("average_score"),
        "review_count": product.get("review_count"),
        "skin_type_satisfaction": product.get("skin_type_satisfaction"),
        "feature_json": json.dumps(feature_json, ensure_ascii=False),
        "last_updated_at": datetime.utcnow().isoformat(),
    }
    if original_price:
        payload["original_price"] = original_price
    sb.table("products").upsert(payload, on_conflict="product_id").execute()


# ── 공개 함수 ──────────────────────────────────────────────────────────────

def crawl_and_seed(category: str, limit: int = 10) -> Dict[str, Any]:
    """
    Gemini로 올리브영 제품 조회 → 이미지 병렬 요청 → DB 저장.
    """
    if category not in _CATEGORY_LABEL:
        raise ValueError(f"지원하지 않는 카테고리: {category}. 허용: {list(_CATEGORY_LABEL)}")

    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    response = client.models.generate_content(
        model=settings.GEMINI_MODEL,
        contents=_make_prompt(category, limit),
        config=types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
            temperature=0,
        ),
    )

    products = _parse_response(response.text or "")

    def _process(p: Dict[str, Any]) -> Dict[str, Any]:
        feature_json = p.get("feature_json")
        if not feature_json:
            return {"status": "skipped", "name": p.get("name"), "brand": p.get("brand"), "reason": "feature_json 없음"}
        product_id = _upsert_product(p, category)
        if not product_id:
            return {"status": "skipped", "name": p.get("name"), "brand": p.get("brand"), "reason": "upsert 실패"}
        _upsert_product_data(product_id, p, feature_json)
        price_options = p.get("price_options") or []
        lowest = min((o.get("final_price") or o.get("price") or 0 for o in price_options), default=None)
        return {
            "status": "saved",
            "name": p.get("name"),
            "brand": p.get("brand"),
            "original_price": p.get("original_price"),
            "lowest_price": lowest if lowest else None,
            "average_score": p.get("average_score"),
            "review_count": p.get("review_count"),
        }

    saved, skipped, errors = 0, 0, []
    product_results: List[Dict[str, Any]] = []

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(_process, p): p for p in products}
        for future in as_completed(futures):
            p = futures[future]
            try:
                result = future.result()
                product_results.append(result)
                if result["status"] == "saved":
                    saved += 1
                else:
                    skipped += 1
            except Exception as e:
                errors.append({"name": p.get("name"), "error": str(e)})

    return {"saved": saved, "skipped": skipped, "errors": errors, "products": product_results}
