"""
자연어 상품 검색 API.

검색창 입력을 Qwen으로 의도 분류 후 분기:
- PRODUCT_NAME   : products 이름 ILIKE 직접 조회 (벡터 X)
- RECOMMENDATION : 임베딩 + pgvector 추천 파이프라인

FE는 POST /search로 호출한다 (reverse proxy를 통해 /ai/search로 노출).
"""
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.search_service import run_search

router = APIRouter(prefix="/search", tags=["search"])


class SearchRequest(BaseModel):
    query: str


class ProductResult(BaseModel):
    productId: str
    name: str
    brand: str
    category: str
    imageUrl: Optional[str] = None
    originalPrice: Optional[int] = None
    matchScore: int


class SearchResponse(BaseModel):
    query: str
    intent: str
    category: str
    products: list[ProductResult]


@router.post(
    "",
    response_model=SearchResponse,
    summary="자연어 상품 검색",
    description="Qwen으로 검색 의도를 분류해 상품명 직접 조회 또는 추천 파이프라인으로 분기.",
)
async def search(body: SearchRequest) -> SearchResponse:
    if not body.query.strip():
        raise HTTPException(status_code=400, detail="검색어를 입력해주세요")

    result = await run_search(body.query)

    return SearchResponse(
        query=result["query"],
        intent=result["intent"],
        category=result.get("category") or "",
        products=[ProductResult(**p) for p in result["products"]],
    )
