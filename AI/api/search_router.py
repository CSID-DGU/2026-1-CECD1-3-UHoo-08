"""
자연어 상품 검색 API.

검색창 입력을 Qwen으로 분석해 카테고리·feature를 추출하고,
bge-m3 임베딩 + pgvector로 유사 상품을 검색한다.

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
    category: Optional[str] = None
    products: list[ProductResult]


@router.post(
    "",
    response_model=SearchResponse,
    summary="자연어 상품 검색",
    description="자연어 쿼리를 Qwen으로 분석해 카테고리 + feature 추출 후 DB 유사도 검색.",
)
async def search(body: SearchRequest) -> SearchResponse:
    if not body.query.strip():
        raise HTTPException(status_code=400, detail="검색어를 입력해주세요")
    
    result = await run_search(body.query)

    return SearchResponse(
        query=result["query"],
        category=result["category"],
        products=[ProductResult(**p) for p in result["products"]],
    )
