from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import agents.input_agent as input_agent
import agents.product_agent as product_agent
from models.product_response import ProductResponse

router = APIRouter()


class RecognizeRequest(BaseModel):
    type: str         # IMAGE | NFC | TEXT
    data: str         # base64 이미지 / 올리브영 URL / 평문 텍스트
    userId: str


@router.post("/recognize", response_model=ProductResponse)
def recognize(req: RecognizeRequest) -> ProductResponse:
    try:
        extracted = input_agent.run(req.type, req.data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return product_agent.run(extracted)
