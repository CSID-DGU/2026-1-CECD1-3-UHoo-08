"""
product_features 기반 상품 유사도 검색.

1차: category로 필터
2차: feature_json 필드별 유사도 점수화 → 내림차순 정렬
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

from db.supabase_client import get_supabase

# 순서형 필드 → 점수 매핑 (거리가 멀수록 페널티)
_ORDINAL: Dict[str, Dict[str, int]] = {
    "coverage":      {"가벼운": 1, "중간": 2, "높음": 3},
    "lasting_power": {"낮음": 1, "중간": 2, "높음": 3},
    "texture":       {"가벼운": 1, "중간": 2, "진한": 3},
}


def _score(query_feat: Dict[str, Any], product_feat: Dict[str, Any]) -> float:
    """feature_json 유사도 0~1 반환."""
    total = matched = 0.0

    for key, qval in query_feat.items():
        if qval is None:
            continue
        pval = product_feat.get(key)
        if pval is None:
            continue
        total += 1

        if key in _ORDINAL:
            q = _ORDINAL[key].get(str(qval), 0)
            p = _ORDINAL[key].get(str(pval), 0)
            if q and p:
                matched += max(0.0, 1.0 - abs(q - p) * 0.4)
        elif isinstance(qval, list) and isinstance(pval, list):
            overlap = len(set(qval) & set(pval))
            matched += overlap / max(len(qval), 1)
        elif isinstance(qval, bool) or isinstance(pval, bool):
            matched += 1.0 if qval == pval else 0.0
        else:
            matched += 1.0 if str(qval) == str(pval) else 0.0

    return matched / total if total > 0 else 0.0


def _parse_feature_json(raw: Any) -> Dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except Exception:
            return {}
    return {}


def search_by_features(
    category: str,
    query_features: Dict[str, Any],
    top_k: int = 20,
) -> List[Dict[str, Any]]:
    """category 1차 필터 → feature 유사도 2차 정렬."""
    sb = get_supabase()

    products_res = (
        sb.table("products")
        .select("product_id, name, brand, category, image_url, original_price")
        .eq("category", category)
        .execute()
    )
    products = products_res.data or []
    if not products:
        return []

    product_ids = [p["product_id"] for p in products]
    features_res = (
        sb.table("product_features")
        .select("product_id, feature_json")
        .in_("product_id", product_ids)
        .execute()
    )
    features_map: Dict[str, Dict[str, Any]] = {
        r["product_id"]: _parse_feature_json(r["feature_json"])
        for r in (features_res.data or [])
    }

    results = []
    for p in products:
        pid = p["product_id"]
        feat = features_map.get(pid, {})
        score = _score(query_features, feat) if query_features else 0.0
        results.append({
            "productId": pid,
            "name": p["name"],
            "brand": p["brand"],
            "category": p["category"],
            "imageUrl": p.get("image_url"),
            "originalPrice": p.get("original_price"),
            "matchScore": round(score * 100),
        })

    results.sort(key=lambda x: x["matchScore"], reverse=True)
    return results[:top_k]
