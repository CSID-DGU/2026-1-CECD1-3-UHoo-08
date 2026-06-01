import json
import hashlib
import base64
import redis

from config import settings
from models.extracted_product import ExtractedProduct
from agents.input_agent.image_parser import parse_image
from agents.input_agent.nfc_parser import parse_nfc_url
from agents.input_agent.text_parser import parse_text

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
    # r = _get_redis()

    # # L1: 동일 raw 입력 → 파서 호출 생략
    # l1_key = _raw_key(input_type, data)
    # cached = r.get(l1_key)
    # if cached:
    #     return ExtractedProduct(**json.loads(cached))

    if input_type == "IMAGE":
        result = parse_image(base64.b64decode(data))
    elif input_type == "NFC":
        result = parse_nfc_url(data)
    elif input_type == "TEXT":
        result = parse_text(data)
    else:
        raise ValueError(f"알 수 없는 input_type: {input_type}")

    # # L2: 같은 상품이 이미 캐싱돼 있으면 기존 정규화 결과 반환
    # l2_key = _product_key(result)
    # cached_l2 = r.get(l2_key)
    # if cached_l2:
    #     r.setex(l1_key, _TTL, cached_l2)
    #     return ExtractedProduct(**json.loads(cached_l2))

    # result_json = result.model_dump_json()
    # r.setex(l1_key, _TTL, result_json)
    # r.setex(l2_key, _TTL, result_json)
    return result
