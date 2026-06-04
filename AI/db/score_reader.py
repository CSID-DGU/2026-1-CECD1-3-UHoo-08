"""
score·collaborative 에이전트가 사용하는 read-only DB 헬퍼.

- products: lowestPrice, originalPrice, feature_json, average_score (통합)
- user_products: 협업 필터링 집계 (collaborative_agent)
- users: 유사 사용자 필터 (collaborative_agent) — skin_type, personal_color
"""
from typing import Any, Dict, List, Optional, TypedDict
import json

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
    """products 테이블에서 lowest_price, original_price 조회."""
    if not product_ids:
        return {}
    sb = get_supabase()
    res = (
        sb.table("products")
        .select("product_id, lowest_price, original_price")
        .in_("product_id", product_ids)
        .execute()
    )
    return {
        row["product_id"]: InsightRow(
            product_id=row["product_id"],
            lowest_price=row.get("lowest_price"),
            original_price=row.get("original_price"),
        )
        for row in (res.data or [])
    }


def get_features(product_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    """{product_id: feature_json}. products 테이블에서 직접 조회."""
    if not product_ids:
        return {}
    sb = get_supabase()
    res = (
        sb.table("products")
        .select("product_id, feature_json")
        .in_("product_id", product_ids)
        .execute()
    )

    out: Dict[str, Dict[str, Any]] = {}
    for row in res.data or []:
        fj = row.get("feature_json")
        if isinstance(fj, str):
            try:
                fj = json.loads(fj)
            except (json.JSONDecodeError, TypeError):
                fj = {}
        out[row["product_id"]] = fj or {}
    return out


def get_similar_user_ids(
    skin_type: Optional[str],
    personal_color: Optional[str],
    exclude_user_id: str,
) -> List[str]:
    """users에서 피부타입·퍼스널컬러 일치하는 사용자 ID 목록 (본인 제외)."""
    sb = get_supabase()
    query = sb.table("users").select("id")
    if skin_type:
        query = query.eq("skin_type", skin_type)
    if personal_color:
        query = query.eq("personal_color", personal_color)
    query = query.neq("id", exclude_user_id)
    res = query.execute()
    return [row["id"] for row in (res.data or [])]


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
    """
    if not skin_type:
        # skin_type 없으면 products.average_score 기반 폴백
        sb = get_supabase()
        res = (
            sb.table("products")
            .select("product_id, average_score")
            .gte("average_score", min_rating)
            .order("average_score", desc=True)
            .limit(limit)
            .execute()
        )
        return [row["product_id"] for row in (res.data or [])]

    sb = get_supabase()
    res = (
        sb.table("users")
        .select("id")
        .eq("skin_type", skin_type)
        .execute()
    )
    user_ids = [r["id"] for r in (res.data or [])]
    if not user_ids:
        return []

    rows = get_user_products_by_users(user_ids)
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
    scored.sort(key=lambda x: (x[1], x[2]), reverse=True)
    return [pid for pid, _, _ in scored[:limit]]
