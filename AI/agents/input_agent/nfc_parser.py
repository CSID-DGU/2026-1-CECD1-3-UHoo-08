import json
import re
from urllib.parse import urlparse, parse_qs
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

import cloudscraper
from bs4 import BeautifulSoup

from config import settings
from models.extracted_product import ExtractedProduct

_scraper = cloudscraper.create_scraper()

_client = ChatOpenAI(
    model=settings.QWEN_TEXT_MODEL,
    api_key=settings.DASHSCOPE_API_KEY,
    base_url=settings.QWEN_TEXT_BASE_URL,
    temperature=0,
    max_tokens=1024,
)

PROMPT = """너는 화장품 상품 정보 추출 전문가이다.

아래 상품 정보에서 구조화된 데이터를 추출하라.
주어진 정보에 없는 값은 null로 출력하라.

반드시 유효한 JSON만 출력하라. 설명, 마크다운, 코드블록 없이 순수 JSON만.

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

[규칙]
- brand: 영문 대문자로 표기 (예: HERA, LANEIGE, BRING GREEN)
- volume: 숫자만 추출 (예: "500ml" → 500), unit: g 또는 ml
- 모르는 값은 null, 배열 정보 없으면 빈 배열 []"""


def _scrape_oliveyoung(url: str) -> dict:
    r = _scraper.get(url, timeout=15)
    soup = BeautifulSoup(r.content, "html.parser", from_encoding="utf-8")

    title_tag = soup.find("meta", property="og:title")
    image_tag = soup.find("meta", property="og:image")

    title = title_tag["content"] if title_tag else ""
    # "| 올리브영" 제거
    title = re.sub(r"\s*\|\s*올리브영.*$", "", title).strip()
    # 대괄호 태그 제거 (예: [수부지토너])
    label = re.search(r"^\[([^\]]+)\]", title)
    label_text = label.group(1) if label else ""
    title = re.sub(r"^\[[^\]]+\]\s*", "", title).strip()

    image_url = image_tag["content"] if image_tag else ""

    return {
        "title": title,
        "label": label_text,
        "image_url": image_url,
    }


def parse_nfc_url(url: str) -> ExtractedProduct:
    scraped = _scrape_oliveyoung(url)
    title = scraped["title"]
    label = scraped["label"]

    info_text = f"상품명: {title}"
    if label:
        info_text += f"\n태그: {label}"

    message = HumanMessage(content=f"{PROMPT}\n\n[상품 정보]\n{info_text}")
    response = _client.invoke([message])

    raw = response.content.strip()
    if raw.startswith("```"):
        raw = raw.strip("`").removeprefix("json").strip()

    return ExtractedProduct(**json.loads(raw))
