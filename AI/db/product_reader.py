"""
상품 메타데이터 read-only 조회. 추천 결과 조립용.

products 테이블에서 추천 결과·후보 필터링에 필요한 메타 정보를 읽는다.
쓰기(insert/update)는 product_agent 담당의 product_repository.py가 수행하며,
본 모듈은 읽기만 담당해 역할이 겹치지 않는다.
"""
import json

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
    return {row["product_id"]: _row_to_meta(row) for row in (res.data or [])}


def get_product_features(product_ids: List[str]) -> Dict[str, Dict]:
    """
    product_id → feature_json(파싱된 dict).

    제품을 왜 추천했는지 설명할 때 쓴다. "같은 용도 제품입니다"로는 고를
    근거가 되지 않는다. 제형·용도·고민을 그대로 말해 줘야 한다.

    feature_json은 컬럼 타입이 text라 문자열로 오는 경우가 있어 둘 다 받는다.
    """
    if not product_ids:
        return {}

    sb = get_supabase()
    rows = (
        sb.table("products")
        .select("product_id, feature_json")
        .in_("product_id", product_ids)
        .execute()
    ).data or []

    out: Dict[str, Dict] = {}
    for r in rows:
        f = r.get("feature_json")
        if isinstance(f, str):
            try:
                f = json.loads(f)
            except (ValueError, TypeError):
                f = None
        if isinstance(f, dict):
            out[r["product_id"]] = f
    return out


def search_products_by_category(
    category: str,
    limit: int = 20,
    *,
    exclude_product_id: Optional[str] = None,
) -> List[ProductMeta]:
    """
    같은 카테고리의 제품. 벡터 연산 없음.

    확인 결과 이상이 발견된 제품을 대신할 후보를 찾을 때 쓴다. 이름 검색으로는
    "선크림"처럼 카테고리 단어가 상품명에 안 들어간 제품을 놓친다.

    자기 자신은 제외한다. 바꾸라고 권해 놓고 같은 제품을 다시 보여줄 수 없다.
    """
    cat = (category or "").strip()
    if not cat:
        return []

    sb = get_supabase()
    q = (
        sb.table("products")
        .select(_COLUMNS)
        .eq("category", cat)
        .limit(limit)
    )
    if exclude_product_id:
        q = q.neq("product_id", exclude_product_id)

    rows = q.execute().data or []
    return [_row_to_meta(r) for r in rows]


def search_products_by_name(keyword: str, limit: int = 20) -> List[ProductMeta]:
    """
    상품명·브랜드 ILIKE 직접 조회. 벡터 연산 없음.

    검색 의도가 PRODUCT_NAME일 때 사용. "라네즈 네오쿠션" 같은
    특정 상품 검색을 이름 부분일치로 빠르게 찾는다.

    name 또는 brand에 keyword가 포함되면 매칭.
    PostgREST or 필터에서 쉼표·괄호는 구분 문자이므로 공백으로 치환해 깨짐 방지.
    """
    kw = keyword.strip().replace(",", " ").replace("(", " ").replace(")", " ")
    if not kw:
        return []
    sb = get_supabase()
    pattern = f"%{kw}%"
    res = (
        sb.table("products")
        .select(_COLUMNS)
        # name 또는 brand 부분일치 (Supabase or 필터)
        .or_(f"name.ilike.{pattern},brand.ilike.{pattern}")
        .limit(limit)
        .execute()
    )
    return [_row_to_meta(row) for row in (res.data or [])]


def search_products_by_traits(
    *,
    categories: Optional[List[str]] = None,
    product_types: Optional[List[str]] = None,
    concerns: Optional[List[str]] = None,
    limit: int = 20,
) -> List[ProductMeta]:
    """
    카테고리·제품종류·피부고민으로 제품을 찾는다.

    상품명 부분일치(search_products_by_name)로는 "자외선차단"·"진정"·"쿨링"처럼
    사람이 쓰는 조건어가 상품명에 그대로 들어있지 않아 한 건도 못 찾는다.
    실제로 sun 카테고리에 20건이 있는데도 "선크림"으로는 3건만 잡혔다.
    분류와 feature_json은 그 조건을 그대로 담고 있으므로 이쪽을 본다.

    feature_json은 행마다 dict이거나 JSON 문자열이라 파싱해서 파이썬에서 거른다.
    조건을 많이 만족하는 제품이 앞에 오도록 정렬한다.
    """
    sb = get_supabase()
    q = sb.table("products").select(f"{_COLUMNS}, feature_json")
    if categories:
        q = q.in_("category", [c for c in categories if c])
    rows = q.limit(500).execute().data or []

    wanted_types = {t for t in (product_types or []) if t}
    wanted_concerns = {c for c in (concerns or []) if c}

    scored: List[tuple] = []
    for row in rows:
        feat = row.get("feature_json")
        if isinstance(feat, str):
            try:
                feat = json.loads(feat)
            except (ValueError, TypeError):
                feat = None
        feat = feat if isinstance(feat, dict) else {}

        score = 0
        if wanted_types:
            ptype = (feat.get("product_type") or "").strip()
            if ptype in wanted_types:
                score += 2
        if wanted_concerns:
            have = {str(c).strip() for c in (feat.get("skin_concern") or []) if c}
            score += len(have & wanted_concerns)

        # 조건을 하나도 안 걸었으면 카테고리만으로 고른 것이라 전부 후보다.
        if score or not (wanted_types or wanted_concerns):
            scored.append((score, row))

    scored.sort(key=lambda sr: sr[0], reverse=True)
    return [_row_to_meta(r) for _, r in scored[:limit]]
