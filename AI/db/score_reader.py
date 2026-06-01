"""
score·collaborative 에이전트가 사용하는 read-only DB 헬퍼.

- product_insights: lowestPrice, originalPrice (score_agent의 budget/price)
- product_features: feature_json (score_agent의 personalization)
- user_products: 협업 필터링 집계 (collaborative_agent)
- user_skin_profiles: 유사 사용자 필터 (collaborative_agent)
"""
from typing import Any, Dict, List, Optional, TypedDict

from db.supabase_client import get_supabase


class InsightRow(TypedDict):
    product_id: str
    lowest_price: Optional[int]
    original_price: Optional[int]


class UserProductRow(TypedDict):
    user_id: str
    product_id: str
    usage_type: str
    rating: Optional[int]


def get_insights(product_ids: List[str]) -> Dict[str, InsightRow]:
    """product_insights + products.original_price 조인."""
    if not product_ids:
        return {}
    sb = get_supabase()
    res = (
        sb.table("product_insights")
        .select("product_id, lowest_price, products(original_price)")
        .in_("product_id", product_ids)
        .execute()
    )
    out: Dict[str, InsightRow] = {}
    for row in res.data or []:
        products_obj = row.get("products") or {}
        out[row["product_id"]] = InsightRow(
            product_id=row["product_id"],
            lowest_price=row.get("lowest_price"),
            original_price=products_obj.get("original_price"),
        )
    return out


def get_features(product_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    """{product_id: feature_json}."""
    if not product_ids:
        return {}
    sb = get_supabase()
    res = (
        sb.table("product_features")
        .select("product_id, feature_json")
        .in_("product_id", product_ids)
        .execute()
    )
    return {row["product_id"]: row["feature_json"] for row in (res.data or [])}


def get_similar_user_ids(
    skin_type: Optional[str],
    personal_color: Optional[str],
    exclude_user_id: str,
) -> List[str]:
    """user_skin_profiles에서 피부타입·퍼스널컬러 일치하는 사용자 ID 목록 (본인 제외)."""
    sb = get_supabase()
    query = sb.table("user_skin_profiles").select("user_id")
    if skin_type:
        query = query.eq("skin_type", skin_type)
    if personal_color:
        query = query.eq("personal_color", personal_color)
    query = query.neq("user_id", exclude_user_id)
    res = query.execute()
    return [row["user_id"] for row in (res.data or [])]


def get_user_products_by_users(user_ids: List[str]) -> List[UserProductRow]:
    """주어진 사용자들의 user_products 전체."""
    if not user_ids:
        return []
    sb = get_supabase()
    res = (
        sb.table("user_products")
        .select("user_id, product_id, usage_type, rating")
        .in_("user_id", user_ids)
        .execute()
    )
    return [
        UserProductRow(
            user_id=row["user_id"],
            product_id=row["product_id"],
            usage_type=row["usage_type"],
            rating=row.get("rating"),
        )
        for row in (res.data or [])
    ]


def get_popular_products_by_skin_type(
    skin_type: Optional[str],
    limit: int = 5,
    min_rating: float = 3.5,
) -> List[str]:
    """
    콜드스타트 폴백용. 같은 skinType 사용자 전체의 user_products에서
    rating 평균이 min_rating 이상인 상품의 ID를 인기순으로 limit개 반환.

    Supabase 단순 쿼리로는 GROUP BY + AVG가 어려워 Python에서 집계.
    """
    if not skin_type:
        # skin_type 없으면 product_insights.average_score 기반 폴백
        sb = get_supabase()
        res = (
            sb.table("product_insights")
            .select("product_id, average_score")
            .gte("average_score", min_rating)
            .order("average_score", desc=True)
            .limit(limit)
            .execute()
        )
        return [row["product_id"] for row in (res.data or [])]

    sb = get_supabase()
    res = (
        sb.table("user_skin_profiles")
        .select("user_id")
        .eq("skin_type", skin_type)
        .execute()
    )
    user_ids = [r["user_id"] for r in (res.data or [])]
    if not user_ids:
        return []

    rows = get_user_products_by_users(user_ids)
    # 상품별 rating 평균 + 카운트 집계
    agg: Dict[str, Dict[str, float]] = {}
    for r in rows:
        if r["rating"] is None:
            continue
        pid = r["product_id"]
        a = agg.setdefault(pid, {"sum": 0.0, "n": 0.0})
        a["sum"] += r["rating"]
        a["n"] += 1

    scored = [
        (pid, v["sum"] / v["n"], v["n"])
        for pid, v in agg.items()
        if v["n"] > 0 and (v["sum"] / v["n"]) >= min_rating
    ]
    # 평균 내림차순, 동률이면 카운트 내림차순
    scored.sort(key=lambda x: (x[1], x[2]), reverse=True)
    return [pid for pid, _, _ in scored[:limit]]