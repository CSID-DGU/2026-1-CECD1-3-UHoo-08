"""
자연어 상품 검색 API.

Qwen으로 쿼리에서 카테고리 + feature 추출 → bge-m3 임베딩 → pgvector 유사도 검색.
"""
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.search_service import search as search_service

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
    category: str
    products: list[ProductResult]


@router.post(
    "",
    response_model=SearchResponse,
    summary="자연어 상품 검색",
    description="자연어 쿼리를 Qwen으로 분석해 bge-m3 임베딩 후 pgvector 유사도 검색.",
)
async def search_products(body: SearchRequest) -> SearchResponse:
    if not body.query.strip():
        raise HTTPException(status_code=400, detail="검색어를 입력해주세요")

    try:
        result = await search_service(body.query)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"검색 실패: {e}")

    return SearchResponse(
        query=result["query"],
        category=result["category"],
        products=[ProductResult(**p) for p in result["products"]],
    )
