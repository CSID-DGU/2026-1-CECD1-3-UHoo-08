"""
상품 대표 이미지 확보 파이프라인.

Gemini에게 이미지 URL을 직접 물어보면 존재하지 않는 CDN 경로를 지어낸다
(image.oliveyoung.co.kr/uploads/... 형태로 그럴듯하게 만들어내지만 전부 403).
그래서 그라운딩 메타데이터가 돌려준 실제 판매 페이지를 따라가 og:image를 읽고,
바이트를 실제로 받아본 뒤에만 Supabase Storage에 올려 public URL을 반환한다.

products.image_url에는 검증되지 않은 외부 URL을 절대 넣지 않는다.
올리브영 CDN은 핫링크를 막고 상품이 바뀌면 경로가 죽으므로, 항상 우리 Storage 사본을 쓴다.
"""
from __future__ import annotations

from typing import List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import cloudscraper
from bs4 import BeautifulSoup
from google import genai
from google.genai import types

from config import settings
from db.supabase_client import get_supabase

STORAGE_BUCKET = "product_image"

_MIN_IMAGE_BYTES = 5_000
_MAX_IMAGE_BYTES = 8_000_000
_ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
_EXT_BY_TYPE = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}

# 로고·배너·플레이스홀더가 og:image로 걸리는 경우를 걸러낸다
_REJECT_HINTS = ("logo", "sprite", "placeholder", "noimage", "no_image", "default_")

# 블로그·커뮤니티의 og:image는 제품컷이 아니라 본문 첫 사진인 경우가 많아 뒤로 미룬다
_LOW_PRIORITY_HOSTS = (
    "tistory", "daumcdn", "blog.naver", "blogspot", "brunch",
    "youtube", "instagram", "facebook", "pinterest", "namu.wiki",
)

_scraper = cloudscraper.create_scraper()
_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


# ── 후보 판매 페이지 조회 ──────────────────────────────────────────────────

def _candidate_pages(brand: str, name: str, limit: int = 8) -> List[str]:
    """Gemini 검색 그라운딩이 실제로 인용한 페이지 URL 목록."""
    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    try:
        response = client.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=f"{brand} {name} 화장품 제품 상세 판매 페이지",
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
                temperature=0,
            ),
        )
    except Exception as e:
        print(f"[이미지] 검색 실패 {brand} {name}: {e}")
        return []

    if not response.candidates:
        return []
    metadata = response.candidates[0].grounding_metadata
    if metadata is None:
        return []

    preferred: List[str] = []
    deferred: List[str] = []
    for chunk in (metadata.grounding_chunks or []):
        web = getattr(chunk, "web", None)
        uri = getattr(web, "uri", None) if web else None
        if not uri or not uri.startswith("http"):
            continue
        # 그라운딩 uri는 리다이렉터라 도메인이 title에만 드러난다
        source = f"{getattr(web, 'title', '') or ''} {uri}".lower()
        bucket = deferred if any(h in source for h in _LOW_PRIORITY_HOSTS) else preferred
        if uri not in bucket:
            bucket.append(uri)
    return (preferred + deferred)[:limit]


# ── 페이지에서 대표 이미지 URL 추출 ────────────────────────────────────────

def _meta_image(soup: BeautifulSoup, page_url: str) -> Optional[str]:
    for attrs in (
        {"property": "og:image"},
        {"property": "og:image:url"},
        {"name": "twitter:image"},
    ):
        tag = soup.find("meta", attrs=attrs)
        content = (tag.get("content") or "").strip() if tag else ""
        if content:
            return urljoin(page_url, content)
    return None


def _looks_rejected(url: str) -> bool:
    lowered = url.lower()
    return any(hint in lowered for hint in _REJECT_HINTS)


def _image_url_from_page(page_url: str) -> Optional[str]:
    try:
        res = _scraper.get(page_url, timeout=20, headers={"User-Agent": _UA})
    except Exception as e:
        print(f"[이미지] 페이지 조회 실패 {page_url[:80]}: {type(e).__name__}")
        return None
    if res.status_code != 200:
        return None

    image_url = _meta_image(BeautifulSoup(res.content, "html.parser"), res.url)
    if not image_url or _looks_rejected(image_url):
        return None
    if any(host in image_url.lower() for host in _LOW_PRIORITY_HOSTS):
        return None
    return image_url


# ── 다운로드 검증 ──────────────────────────────────────────────────────────

def _download(image_url: str, referer: Optional[str] = None) -> Optional[Tuple[bytes, str]]:
    """실제 바이트를 받아 이미지가 맞는지 확인한다. 아니면 None."""
    headers = {"User-Agent": _UA}
    if referer:
        parsed = urlparse(referer)
        headers["Referer"] = f"{parsed.scheme}://{parsed.netloc}/"
    try:
        res = _scraper.get(image_url, timeout=20, headers=headers)
    except Exception as e:
        print(f"[이미지] 다운로드 실패 {image_url[:80]}: {type(e).__name__}")
        return None

    if res.status_code != 200:
        print(f"[이미지] 다운로드 status={res.status_code} {image_url[:80]}")
        return None

    content_type = res.headers.get("Content-Type", "").split(";")[0].strip().lower()
    if content_type not in _ALLOWED_TYPES:
        print(f"[이미지] 이미지가 아님 type={content_type!r} {image_url[:80]}")
        return None
    if not (_MIN_IMAGE_BYTES <= len(res.content) <= _MAX_IMAGE_BYTES):
        print(f"[이미지] 크기 부적합 size={len(res.content)} {image_url[:80]}")
        return None

    return res.content, content_type


# ── Storage 업로드 ─────────────────────────────────────────────────────────

def store_image(product_id: str, image_bytes: bytes, content_type: str) -> Optional[str]:
    """Supabase Storage에 업로드 후 public URL 반환."""
    sb = get_supabase()
    path = f"{product_id}.{_EXT_BY_TYPE.get(content_type, 'jpg')}"
    try:
        sb.storage.from_(STORAGE_BUCKET).upload(
            path=path,
            file=image_bytes,
            file_options={"content-type": content_type, "upsert": "true"},
        )
        return sb.storage.from_(STORAGE_BUCKET).get_public_url(path)
    except Exception as e:
        print(f"[이미지] Storage 업로드 실패 {product_id}: {e}")
        return None


# ── 공개 함수 ──────────────────────────────────────────────────────────────

def fetch_image(brand: str, name: str, hint_url: Optional[str] = None) -> Optional[Tuple[bytes, str]]:
    """
    상품 이미지 바이트 확보. hint_url(NFC 스크래핑 등으로 이미 알아낸 URL)을 먼저 시도하고,
    실패하면 검색 그라운딩이 인용한 판매 페이지들의 og:image를 차례로 시도한다.
    """
    if hint_url:
        downloaded = _download(hint_url)
        if downloaded:
            return downloaded

    for page_url in _candidate_pages(brand, name):
        image_url = _image_url_from_page(page_url)
        if not image_url:
            continue
        downloaded = _download(image_url, referer=page_url)
        if downloaded:
            print(f"[이미지] 확보 {brand} {name} ← {image_url[:90]}")
            return downloaded

    print(f"[이미지] 후보 없음 {brand} {name}")
    return None


def ensure_product_image(
    product_id: str,
    brand: str,
    name: str,
    hint_url: Optional[str] = None,
) -> Optional[str]:
    """이미지를 확보해 Storage에 올리고 products.image_url까지 갱신한다."""
    fetched = fetch_image(brand, name, hint_url)
    if not fetched:
        return None

    public_url = store_image(product_id, *fetched)
    if not public_url:
        return None

    get_supabase().table("products").update(
        {"image_url": public_url}
    ).eq("product_id", product_id).execute()
    return public_url
