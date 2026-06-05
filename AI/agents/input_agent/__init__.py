import json
import hashlib
import base64
import logging
import time
import redis

from config import settings
from models.extracted_product import ExtractedProduct
from agents.input_agent.image_parser import parse_image
from agents.input_agent.nfc_parser import parse_nfc_url
from agents.input_agent.text_parser import parse_text

logger = logging.getLogger(__name__)

_TTL = 6 * 60 * 60  # 6시간
_redis_client = None


def _get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis_client


def _raw_key(input_type: str, data: str) -> str:
    """L1 캐시 키: 동일 raw 입력 재호출 방지."""
    hashed = hashlib.sha256(data.encode()).hexdigest()[:16]
    return f"input_agent:{input_type}:{hashed}"


def _product_key(result: ExtractedProduct) -> str:
    """L2 캐시 키: 상품명+브랜드+카테고리+옵션 기반. 다른 이미지로 같은 상품 조회 시 히트."""
    name  = (result.product_name or "").lower().strip()
    brand = (result.brand or "").lower().strip()
    main  = (result.category or {}).get("main", "") if isinstance(result.category, dict) else ""
    shade = ((result.attributes or {}).get("shade") or "") if result.attributes else ""
    combined = f"{name}:{brand}:{main}:{shade}"
    hashed = hashlib.sha256(combined.encode()).hexdigest()[:16]
    return f"input_agent:product:{hashed}"


def run(input_type: str, data: str) -> ExtractedProduct:
    """
    input_type: IMAGE | NFC | TEXT
    data: base64 이미지 / 올리브영 URL / 평문 텍스트
    """
    logger.info("[input_agent] 파싱 시작 | type=%s", input_type)
    t0 = time.perf_counter()

    if input_type == "IMAGE":
        result = parse_image(base64.b64decode(data))
    elif input_type == "NFC":
        result = parse_nfc_url(data)
    elif input_type == "TEXT":
        result = parse_text(data)
    else:
        raise ValueError(f"알 수 없는 input_type: {input_type}")

    logger.info(
        "[input_agent] 파싱 완료 | %.2fs | name=%s | brand=%s | category=%s | attributes=%s",
        time.perf_counter() - t0,
        result.product_name,
        result.brand,
        result.category,
        result.attributes,
    )
    return result
