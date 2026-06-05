from __future__ import annotations

import base64
import logging
import time

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import agents.input_agent as input_agent
import agents.product_agent as product_agent
from db.supabase_client import get_supabase
from models.product_response import ProductResponse

logger = logging.getLogger(__name__)
router = APIRouter()

_BUCKET = "product_image"


class RecognizeRequest(BaseModel):
    type: str                   # IMAGE | NFC | TEXT
    data: str                   # base64 이미지 / 올리브영 URL / 평문 텍스트
    userId: str | None = None


def _save_image(product_id: str, image_bytes: bytes) -> None:
    """Supabase Storage에 이미지 업로드 후 products.image_url 업데이트."""
    sb = get_supabase()
    path = f"{product_id}.jpg"
    sb.storage.from_(_BUCKET).upload(
        path, image_bytes, {"upsert": "true", "content-type": "image/jpeg"}
    )
    public_url = sb.storage.from_(_BUCKET).get_public_url(path)
    sb.table("products").update({"image_url": public_url}).eq("product_id", product_id).execute()


@router.post("/recognize", response_model=ProductResponse)
def recognize(req: RecognizeRequest) -> ProductResponse:
    total_start = time.perf_counter()
    data_preview = req.data[:40] + "..." if len(req.data) > 40 else req.data
    logger.info("[recognize] 요청 수신 | type=%s | userId=%s | data=%s", req.type, req.userId, data_preview)

    # ── 1. 입력 파싱 ──────────────────────────────────────────────────
    t0 = time.perf_counter()
    try:
        extracted = input_agent.run(req.type, req.data)
    except ValueError as e:
        logger.warning("[recognize] 입력 파싱 실패 | type=%s | error=%s", req.type, e)
        raise HTTPException(status_code=400, detail=str(e))

    logger.info(
        "[recognize] 입력 파싱 완료 | %.2fs | 상품명=%s | 브랜드=%s | 카테고리=%s",
        time.perf_counter() - t0,
        extracted.product_name,
        extracted.brand,
        extracted.category,
    )

    # ── 2. 상품 보강 ──────────────────────────────────────────────────
    t0 = time.perf_counter()
    response = product_agent.run(extracted)
    logger.info(
        "[recognize] 상품 보강 완료 | %.2fs | productId=%s | name=%s | brand=%s",
        time.perf_counter() - t0,
        response.productId,
        response.name,
        response.brand,
    )

    # ── 3. 이미지 저장 ────────────────────────────────────────────────
    if response.productId:
        try:
            if req.type == "IMAGE":
                image_bytes = base64.b64decode(req.data)
            elif req.type == "NFC" and extracted.image_url:
                import httpx
                image_bytes = httpx.get(extracted.image_url, timeout=10).content
            else:
                image_bytes = None

            if image_bytes:
                t0 = time.perf_counter()
                _save_image(response.productId, image_bytes)
                logger.info("[recognize] 이미지 저장 완료 | %.2fs | productId=%s", time.perf_counter() - t0, response.productId)
        except Exception as e:
            import traceback
            logger.error("[recognize] 이미지 저장 실패 | productId=%s | %s", response.productId, traceback.format_exc())

    logger.info("[recognize] 전체 완료 | 총 %.2fs", time.perf_counter() - total_start)
    return response
