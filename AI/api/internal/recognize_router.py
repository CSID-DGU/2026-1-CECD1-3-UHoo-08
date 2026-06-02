from __future__ import annotations

import base64

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import agents.input_agent as input_agent
import agents.product_agent as product_agent
from db.supabase_client import get_supabase
from models.product_response import ProductResponse

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
    try:
        extracted = input_agent.run(req.type, req.data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    response = product_agent.run(extracted)

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
                _save_image(response.productId, image_bytes)
        except Exception as e:
            import traceback
            print(f"[recognize] 이미지 저장 실패: {traceback.format_exc()}")

    return response
