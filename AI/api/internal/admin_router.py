"""
개발자용 관리 API.

운영 환경에서는 노출하지 않는다.
product_features 테이블 초기 시딩 등 일회성 작업에 사용.
"""
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from services.product_crawler import crawl_and_seed

router = APIRouter(prefix="/internal/admin", tags=["admin"])

CATEGORIES = Literal["base", "sun", "lip", "skincare"]


class SeedRequest(BaseModel):
    category: CATEGORIES = Field(..., description="base | sun | lip | skincare")
    limit: int = Field(10, ge=1, le=30, description="조회할 제품 수 (최대 30)")


class SeedResponse(BaseModel):
    category: str
    saved: int
    skipped: int
    errors: list


@router.post(
    "/seed-products",
    response_model=SeedResponse,
    summary="올리브영 제품 시딩 (개발 전용)",
    description=(
        "Gemini Google Search로 올리브영 카테고리별 제품을 조회하고 "
        "products + product_features 테이블에 저장한다. "
        "이미 존재하는 제품(name+brand 기준)은 feature만 업데이트."
    ),
)
def seed_products(body: SeedRequest) -> SeedResponse:
    try:
        result = crawl_and_seed(body.category, body.limit)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"크롤링 실패: {e}")

    return SeedResponse(
        category=body.category,
        saved=result["saved"],
        skipped=result["skipped"],
        errors=result["errors"],
    )
