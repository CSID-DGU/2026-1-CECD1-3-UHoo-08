"""
score_agent — discovery 후보를 0~100점으로 채점.

흐름:
  1. 각 candidate의 budget_fit/price_value/review_score/personalization 독립 계산
  2. Qwen-Plus로 가중치 보정 (searchPurpose·priceTolerancePercent 반영)
  3. weighted_validator로 가중치 합 1.0 정규화
  4. totalScore = Σ(score_i X weight_i)
  5. 정렬 결과를 메인 추천 목록으로 반환
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional, TypedDict

from agents.score_agent import (
    budget_scorer,
    personalization_scorer,
    price_scorer,
    review_scorer,
)
from db.score_reader import get_features, get_insights
from prompts.weight_adjustment import (
    WEIGHT_ADJUSTMENT_SYSTEM,
    build_weight_adjustment_user_prompt,
)
from services.qwen_client import get_qwen_llm
from services.weight_validator import validate_and_normalize


class ScoreBreakdown(TypedDict):
    budgetFit: int
    priceValue: int
    reviewScore: int
    personalization: int


class ScoredProduct(TypedDict):
    productId: str
    totalScore: int
    breakdown: ScoreBreakdown


async def run_score(
    intent_vector: List[float],
    candidate_ids: List[str],
    user_profile: Dict[str, Any],
    search_purpose: Optional[str] = None,
    price_tolerance_percent: Optional[int] = None,
    target_price: Optional[int] = None,
) -> List[ScoredProduct]:
    """
    score_agent 핵심 로직.

    target_price 없으면 후보 평균 lowest_price로 추정.
    candidate_ids 비어있으면 빈 리스트 반환.
    """
    if not candidate_ids:
        return []

    # 1. 부가 데이터 일괄 조회
    insights = await asyncio.to_thread(get_insights, candidate_ids)
    features = await asyncio.to_thread(get_features, candidate_ids)

    # target_price 추정 (사용자 입력 없으면 후보 lowest_price 중앙값)
    if target_price is None:
        prices = [
            r["lowest_price"]
            for r in insights.values()
            if r["lowest_price"] is not None
        ]
        if prices:
            prices.sort()
            target_price = prices[len(prices) // 2]

    # 2. 가중치 보정 (Qwen-Plus 호출)
    llm = get_qwen_llm()
    raw_weights = await llm.chat_json(
        system=WEIGHT_ADJUSTMENT_SYSTEM,
        user=build_weight_adjustment_user_prompt(
            search_purpose, price_tolerance_percent
        ),
    )
    weights = validate_and_normalize(raw_weights)

    # 3. candidate별 4요소 계산 → totalScore
    results: List[ScoredProduct] = []
    for pid in candidate_ids:
        ins = insights.get(pid)
        feat = features.get(pid)
        lowest = ins["lowest_price"] if ins else None
        original = ins["original_price"] if ins else None

        budget = budget_scorer.compute(lowest, target_price, price_tolerance_percent)
        price = price_scorer.compute(lowest, original)
        review = await asyncio.to_thread(
            review_scorer.compute, intent_vector, pid, 10
        )
        person = personalization_scorer.compute(user_profile, feat)

        total = round(
            budget * weights["budget_fit"]
            + price * weights["price_value"]
            + review * weights["review_score"]
            + person * weights["personalization"]
        )

        results.append(
            ScoredProduct(
                productId=pid,
                totalScore=max(0, min(100, total)),
                breakdown=ScoreBreakdown(
                    budgetFit=budget,
                    priceValue=price,
                    reviewScore=review,
                    personalization=person,
                ),
            )
        )

    # 4. totalScore 내림차순
    results.sort(key=lambda r: r["totalScore"], reverse=True)
    return results


# ── @tool 래퍼 ───────────────────────────────────────────────────────────

try:
    from langchain_core.tools import tool

    @tool
    async def call_score_agent(
        intent_vector: List[float],
        candidate_product_ids: List[str],
        skin_type: Optional[str] = None,
        personal_color: Optional[str] = None,
        skin_concerns: Optional[List[str]] = None,
        search_purpose: Optional[str] = None,
        price_tolerance_percent: Optional[int] = None,
        target_price: Optional[int] = None,
    ) -> list:
        """discovery_agent의 candidates를 0~100점으로 채점한다.
        4요소(예산·가성비·리뷰적합도·개인화)를 Qwen-Plus 가중치로 합성한다."""
        profile = {
            "skin_type": skin_type,
            "personal_color": personal_color,
            "skin_concerns": skin_concerns or [],
        }
        results = await run_score(
            intent_vector=intent_vector,
            candidate_ids=candidate_product_ids,
            user_profile=profile,
            search_purpose=search_purpose,
            price_tolerance_percent=price_tolerance_percent,
            target_price=target_price,
        )
        return results  # type: ignore[return-value]

except ImportError:
    call_score_agent = None  # type: ignore