"""
올리브영 카테고리별 제품 시딩.

Gemini (Google Search grounding)로 올리브영 실제 판매 제품을 조회하고,
feature_json 스키마에 맞게 추출한 뒤 Supabase에 저장한다.
제품 이미지는 Gemini에게 직접 요청하여 inline_data로 받아 Storage에 업로드한다.
"""
from __future__ import annotations

import base64
import json
import re
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any, Dict, List, Optional

from google import genai
from google.genai import types

from config import settings
from db.supabase_client import get_supabase

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
_IMAGE_MODEL = "gemini-2.0-flash"   # 이미지 출력 지원 모델


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
      "feature_json": {schema}
    }}
  ]
}}

[규칙]
- 올리브영에서 실제 판매 중인 제품만 포함
- feature_json의 해당 없는 필드는 반드시 null (생략 금지)
- 허용값 목록 외 값 사용 금지
- skin_concern, key_ingredient는 해당 항목만 배열로, 없으면 null
- brand는 영문 대문자 공식 브랜드명
- original_price는 올리브영 정가 기준 (숫자만, 원 기호 제외)
"""


# ── Gemini 이미지 직접 요청 ────────────────────────────────────────────────

def _fetch_image_inline(brand: str, name: str) -> tuple[Optional[bytes], str]:
    """Gemini에게 제품 이미지를 inline_data로 직접 요청."""
    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    try:
        response = client.models.generate_content(
            model=_IMAGE_MODEL,
            contents=f"{brand} {name} 화장품 제품 대표 이미지",
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"],
                tools=[types.Tool(google_search=types.GoogleSearch())],
            ),
        )
        for candidate in (response.candidates or []):
            for part in candidate.content.parts:
                if hasattr(part, "inline_data") and part.inline_data and part.inline_data.data:
                    img_bytes = base64.b64decode(part.inline_data.data)
                    if len(img_bytes) > 1024:
                        return img_bytes, part.inline_data.mime_type or "image/jpeg"
    except Exception as e:
        print(f"[이미지 요청 실패] {brand} {name}: {e}")
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
        # 이미지 없으면 재시도
        if not existing.data[0].get("image_url"):
            _set_product_image(product_id, brand, name)
        return product_id

    product_id = str(uuid.uuid4())
    image_url = _resolve_image(product_id, brand, name)

    res = sb.table("products").insert({
        "product_id": product_id,
        "name": name,
        "brand": brand,
        "category": category,
        "image_url": image_url,
        "original_price": product.get("original_price"),
    }).execute()
    return res.data[0]["product_id"] if res.data else None


def _resolve_image(product_id: str, brand: str, name: str) -> Optional[str]:
    img_bytes, ct = _fetch_image_inline(brand, name)
    if img_bytes:
        return _upload_image(product_id, img_bytes, ct)
    return None


def _set_product_image(product_id: str, brand: str, name: str) -> None:
    image_url = _resolve_image(product_id, brand, name)
    if image_url:
        get_supabase().table("products").update(
            {"image_url": image_url}
        ).eq("product_id", product_id).execute()


def _upsert_feature(product_id: str, feature_json: Dict[str, Any]) -> None:
    sb = get_supabase()
    existing = (
        sb.table("product_features")
        .select("id")
        .eq("product_id", product_id)
        .limit(1)
        .execute()
    )
    if existing.data:
        sb.table("product_features").update({
            "feature_json": json.dumps(feature_json, ensure_ascii=False),
            "updated_at": datetime.utcnow().isoformat(),
        }).eq("product_id", product_id).execute()
    else:
        now = datetime.utcnow().isoformat()
        sb.table("product_features").insert({
            "id": str(uuid.uuid4()),
            "product_id": product_id,
            "feature_json": json.dumps(feature_json, ensure_ascii=False),
            "created_at": now,
            "updated_at": now,
        }).execute()


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

    def _process(p: Dict[str, Any]) -> str:
        feature_json = p.get("feature_json")
        if not feature_json:
            return "skipped"
        product_id = _upsert_product(p, category)
        if not product_id:
            return "skipped"
        _upsert_feature(product_id, feature_json)
        return "saved"

    saved, skipped, errors = 0, 0, []
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(_process, p): p for p in products}
        for future in as_completed(futures):
            p = futures[future]
            try:
                if future.result() == "saved":
                    saved += 1
                else:
                    skipped += 1
            except Exception as e:
                errors.append({"product": p.get("name"), "error": str(e)})

    return {"saved": saved, "skipped": skipped, "errors": errors}
