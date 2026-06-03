"""
개발자용 리뷰 시딩 API.

운영 환경에서는 노출하지 않는다.
Gemini Google Search로 올리브영 실제 리뷰를 수집해 reviews 테이블에 적재하고,
auto_embed=True면 이어서 review_embeddings까지 임베딩한다.
seed-products와 동일한 admin 네임스페이스 사용.
"""
from typing import Any, Dict, List, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from services.review_collector import collect_reviews

router = APIRouter(prefix="/internal/admin", tags=["admin"])

CATEGORIES = Literal["base", "sun", "lip", "skincare"]


class SeedReviewRequest(BaseModel):
    category: CATEGORIES = Field(..., description="base | sun | lip | skincare")
    limit: int = Field(10, ge=1, le=30, description="리뷰 수집 대상 상품 수")
    per_product: int = Field(8, ge=1, le=20, description="상품당 목표 리뷰 수")
    auto_embed: bool = Field(
        False,
        description="True면 수집 직후 review_embeddings까지 임베딩 (느려짐)",
    )

class SeedReviewResponse(BaseModel):
    category: str
    saved: int                      # 적재된 리뷰 총 건수
    skipped: int                    # 리뷰 못 찾은 상품 수
    errors: List[Dict[str, Any]]
    results: List[Dict[str, Any]]
    embedded: int = 0               # auto_embed 시 review_embeddings 적재 건수

@router.post(
    "/seed-reviews",
    response_model=SeedReviewResponse,
    summary="올리브영 실제 리뷰 시딩 (개발 전용)",
    description=(
        "Gemini Google Search로 카테고리별 상품의 실제 올리브영 리뷰를 수집해 "
        "reviews 테이블에 저장한다. seed-products와 동일한 검색 방식. "
        "auto_embed=True면 이어서 review_embeddings까지 임베딩한다 "
    ),
)
def seed_reviews(body: SeedReviewRequest) -> SeedReviewResponse:
    try:
        result = collect_reviews(body.category, body.limit, body.per_product)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"리뷰 수집 실패: {e}")

    embedded = 0
    if body.auto_embed and result["saved"] > 0:
        # 수집된 리뷰가 있을 때만 임베딩 (불필요한 모델 로딩 방지)
        try:
            from scripts.reembed_reviews import reembed_reviews
            embedded = reembed_reviews()
        except Exception as e:
            # 임베딩 실패해도 수집 결과는 살림. 에러만 기록
            result["errors"].append({"stage": "reembed", "error": str(e)})

    return SeedReviewResponse(embedded=embedded, **result)