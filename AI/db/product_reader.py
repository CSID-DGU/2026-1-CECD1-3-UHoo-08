"""
상품 메타데이터 read-only 조회. 추천 결과 조립용.

products 테이블에서 추천 결과·후보 필터링에 필요한 메타 정보를 읽는다.
쓰기(insert/update)는 product_agent 담당의 product_repository.py가 수행하며,
본 모듈은 읽기만 담당해 역할이 겹치지 않는다.
"""
from typing import Dict, List, Optional, TypedDict

from db.supabase_client import get_supabase


class ProductMeta(TypedDict):
    id: str
    name: str
    brand: str
    category: str
    image_url: Optional[str]
    price: Optional[int]


# feature_vec이 포함된 확장 타입 (discovery_agent 전용)
class ProductMetaWithVec(ProductMeta):
    feature_vec: List[float]


_COLUMNS = "product_id, name, brand, category, image_url, original_price"


def _row_to_meta(row: dict) -> ProductMeta:
    return ProductMeta(
        id=row["product_id"],
        name=row["name"],
        brand=row["brand"],
        category=row["category"],
        image_url=row.get("image_url"),
        price=row.get("original_price"),
    )


def get_product_meta(product_id: str) -> Optional[ProductMeta]:
    """단일 상품 메타 조회. 없으면 None."""
    sb = get_supabase()
    res = (
        sb.table("products")
        .select(_COLUMNS)
        .eq("product_id", product_id)
        .limit(1)
        .execute()
    )
    if not res.data:
        return None
    return _row_to_meta(res.data[0])


def get_product_meta_with_vec(product_id: str) -> Optional[ProductMetaWithVec]:
    """
    단일 상품 메타 + feature_vec 조회. discovery_agent 전용.

    product_embeddings.feature_vec은 feature_json을 자연어 변환 후
    bge-m3로 임베딩한 1024차원 벡터. RAG 검색(match_user_contexts)에 사용된다.

    feature_vec이 아직 생성되지 않은 상품이면 ValueError 발생
    (임베딩 파이프라인이 완료되지 않은 상품은 추천 불가).
    """
    sb = get_supabase()

    # products 기본 정보
    product_res = (
        sb.table("products")
        .select(_COLUMNS)
        .eq("product_id", product_id)
        .limit(1)
        .execute()
    )
    if not product_res.data:
        return None

    # feature_vec 조회
    emb_res = (
        sb.table("product_embeddings")
        .select("feature_vec")
        .eq("product_id", product_id)
        .limit(1)
        .execute()
    )
    if not emb_res.data:
        raise ValueError(
            f"feature_vec이 없는 상품입니다 (임베딩 파이프라인 미완료): {product_id}"
        )

    meta = _row_to_meta(product_res.data[0])
    return ProductMetaWithVec(**meta, feature_vec=emb_res.data[0]["feature_vec"])


def get_products_meta(product_ids: List[str]) -> Dict[str, ProductMeta]:
    """
    여러 상품 메타 배치 조회. {product_id: ProductMeta} 딕셔너리 반환.

    존재하지 않는 id는 결과에서 빠진다 (KeyError 방지를 위해 호출 측에서 확인).
    """
    if not product_ids:
        return {}
    sb = get_supabase()
    res = (
        sb.table("products")
        .select(_COLUMNS)
        .in_("product_id", product_ids)
        .execute()
    )
    return {row["id"]: _row_to_meta(row) for row in (res.data or [])}