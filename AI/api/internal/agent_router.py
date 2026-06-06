from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel
from langchain_core.messages import HumanMessage

from config import settings
from graph.action_model import agent_graph
from services import job_updater

router = APIRouter()


class UserProfileInput(BaseModel):
    skinType: str | None = None
    skinConcerns: list[str] = []
    personalColor: str | None = None


class AgentRunRequest(BaseModel):
    jobId: str
    userId: str
    baseProductId: str | None = None
    searchPurpose: str | None = None   # DAILY | OFFICE | DATE
    priceTolerancePercent: int = 10
    userProfile: UserProfileInput = UserProfileInput()


def _build_context_message(req: AgentRunRequest) -> str:
    profile_json = json.dumps(
        {
            "skinType": req.userProfile.skinType,
            "skinConcerns": req.userProfile.skinConcerns,
            "personalColor": req.userProfile.personalColor,
        },
        ensure_ascii=False,
    )
    return (
        f"작업 ID: {req.jobId}\n"
        f"사용자 ID: {req.userId}\n"
        f"기준 상품 ID: {req.baseProductId or ''}\n"
        f"구매 목적: {req.searchPurpose or ''}\n"
        f"가격 허용 범위: {req.priceTolerancePercent}\n"
        f"사용자 프로필: {profile_json}\n\n"
        "화장품 추천을 시작하세요."
    )


def _write_result(job_id: str, result: dict) -> None:
    from db.supabase_client import get_supabase
    get_supabase().table("recommendation_jobs").update({
        "result": result,
        "status": "COMPLETED",
        "step": "루틴 생성",
        "progress": 100,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", job_id).execute()


async def _save_user_context(req: AgentRunRequest) -> None:
    """추천 완료 후 검색 맥락을 user_context_rags에 저장. 실패해도 무시."""
    try:
        from services.embedding_service import EmbeddingService
        from db.supabase_client import get_supabase
        from db.product_reader import get_product_meta

        sb = get_supabase()

        user_check = await asyncio.to_thread(
            lambda: sb.table("users").select("id").eq("id", req.userId).limit(1).execute()
        )
        if not user_check.data:
            print(f"[user_context_rags] userId {req.userId} not found in users, skipping")
            return

        profile = req.userProfile
        concerns = "·".join(profile.skinConcerns) if profile.skinConcerns else ""
        context_text = (
            f"{profile.skinType or ''} 피부, {profile.personalColor or ''} 톤"
            + (f", {concerns} 고민" if concerns else "")
            + f". {req.searchPurpose or ''} 용도로 추천 요청."
            + f" 가격 허용 폭 ±{req.priceTolerancePercent}%."
        ).strip()

        emb = EmbeddingService.get()
        vec = await asyncio.to_thread(emb.embed, context_text)

        meta = await asyncio.to_thread(get_product_meta, req.baseProductId or "")
        category = meta["category"] if meta else None

        await asyncio.to_thread(
            lambda: sb.table("user_context_rags").insert({
                "user_id": req.userId,
                "context_text": context_text,
                "embedding": vec,
                "category": category,
            }).execute()
        )
    except Exception as e:
        print(f"[user_context_rags] 저장 실패: {e}")


async def _generate_ai_reason(
    req: AgentRunRequest,
    base_product_name: str,
    category: str,
    match_score: int,
    breakdown: dict,
) -> str:
    """baseProduct 채점 결과 기반으로 aiReason 생성."""
    profile = req.userProfile
    concerns = ", ".join(profile.skinConcerns) if profile.skinConcerns else "없음"
    purpose_map = {"DAILY": "데일리", "OFFICE": "직장", "DATE": "데이트"}
    purpose = purpose_map.get(req.searchPurpose or "", req.searchPurpose or "데일리")

    score_context = ""
    if breakdown:
        parts = []
        if breakdown.get("personalization", 0) >= 70:
            parts.append("피부 조건 적합도 높음")
        elif breakdown.get("personalization", 0) < 40:
            parts.append("피부 조건 적합도 낮음")
        if breakdown.get("reviewScore", 0) >= 70:
            parts.append("사용 목적에 맞는 리뷰 다수")
        if breakdown.get("budgetFit", 0) >= 70:
            parts.append("예산 범위 적합")
        if parts:
            score_context = f"점수 근거: {', '.join(parts)}\n"

    category_guide = {
        "sun": "자외선차단·수분·피부자극 최소화",
        "base": "커버력·지속력·피부톤",
        "skincare": "성분·피부고민 해결",
        "lip": "발색·제형·퍼스널컬러",
    }.get(category, "성분·피부 조건")

    prompt = (
        f"[상품 정보]\n"
        f"상품명: {base_product_name}, 카테고리: {category}, 적합도: {match_score}/100\n"
        f"{score_context}"
        f"\n[사용자 정보]\n"
        f"피부타입: {profile.skinType}, 퍼스널컬러: {profile.personalColor}, 피부고민: {concerns}\n"
        f"사용 목적: {purpose}\n"
        f"\n[작성 규칙]\n"
        f"- 이 상품이 위 사용자에게 {match_score}점인 이유를 1~2문장 한국어로 작성하세요.\n"
        f"- 브랜드명·상품명·ID는 절대 언급하지 마세요.\n"
        f"- {category} 카테고리 기준: {category_guide}을 근거로 작성하세요.\n"
        f"- 점수 수치는 언급하지 마세요."
    )
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{settings.QWEN_LLM_BASE_URL.rstrip('/v1')}/api/chat",
                json={"model": settings.QWEN_LLM_MODEL, "messages": [{"role": "user", "content": prompt}], "stream": False},
            )
            data = resp.json()
            return data.get("message", {}).get("content", "").strip()
    except Exception as e:
        print(f"[agent_router] aiReason 생성 실패: {e}")
        return ""


async def _score_base_product(req: AgentRunRequest, intent_vector: list) -> tuple[int, dict]:
    """baseProduct를 score_agent로 채점 → (matchScore, breakdown)."""
    if not req.baseProductId or not intent_vector:
        return 0, {}
    try:
        from agents.score_agent import run_score
        results = await run_score(
            intent_vector=intent_vector,
            candidate_ids=[req.baseProductId],
            user_profile={
                "skin_type": req.userProfile.skinType,
                "personal_color": req.userProfile.personalColor,
                "skin_concerns": req.userProfile.skinConcerns,
            },
            search_purpose=req.searchPurpose,
            price_tolerance_percent=req.priceTolerancePercent,
        )
        if results:
            return min(100, int(results[0]["totalScore"])), dict(results[0].get("breakdown", {}))
    except Exception as e:
        print(f"[agent_router] baseProduct 채점 실패: {e}")
    return 0, {}


async def _build_main_recommendations(scores: list) -> list:
    """score_agent candidates 결과 + 상품 메타 조인 → mainRecommendations."""
    if not scores:
        return []
    try:
        from db.product_reader import get_products_meta
        product_ids = [s["productId"] for s in scores]
        metas = await asyncio.to_thread(get_products_meta, product_ids)
        result = []
        for s in scores:
            meta = metas.get(s["productId"])
            if not meta:
                continue
            result.append({
                "id": meta["id"],
                "name": meta["name"],
                "brand": meta["brand"],
                "imageUrl": meta["image_url"],
                "price": meta["price"],
                "totalScore": s["totalScore"],
                "breakdown": s.get("breakdown", {}),
            })
        return result
    except Exception as e:
        print(f"[agent_router] mainRecommendations 조립 실패: {e}")
        return []


async def _run_agent(req: AgentRunRequest) -> None:
    try:
        await job_updater.update(req.jobId, status="IN_PROGRESS", progress=0)

        initial_state = {
            "messages": [HumanMessage(content=_build_context_message(req))],
            "job_id": req.jobId,
            "user_id": req.userId,
            "base_product_id": req.baseProductId,
            "search_purpose": req.searchPurpose,
            "price_tolerance_percent": req.priceTolerancePercent,
            "user_profile": {
                "skinType": req.userProfile.skinType,
                "skinConcerns": req.userProfile.skinConcerns,
                "personalColor": req.userProfile.personalColor,
            },
            "candidates": [],
            "intent_vector": [],
            "scores": [],
            "alternatives": [],
            "collaborative_results": [],
            "final_result": None,
        }

        final_state = await agent_graph.ainvoke(initial_state)

        from agents.tools import (
            _collaborative_store, _alternative_store,
            _score_store, _intent_backup_store,
        )
        job_id = req.jobId

        # store에서 실제 tool 결과 수집
        collaborative = _collaborative_store.pop(job_id, [])
        alternative = _alternative_store.pop(job_id, [])
        candidate_scores = _score_store.pop(job_id, [])
        intent_vector = _intent_backup_store.pop(job_id, [])

        # baseProduct 자체 채점 → matchScore
        match_score, breakdown = await _score_base_product(req, intent_vector)

        # mainRecommendations 조립 (candidates 채점 결과)
        main_recommendations = await _build_main_recommendations(candidate_scores)

        # base product 메타 조회
        from db.product_reader import get_product_meta
        base_meta = await asyncio.to_thread(get_product_meta, req.baseProductId or "")
        base_name = base_meta["name"] if base_meta else ""
        category = base_meta["category"] if base_meta else "skincare"

        # aiReason 생성
        ai_reason = await _generate_ai_reason(req, base_name, category, match_score, breakdown)
        if not ai_reason:
            ai_reason = "사용자 피부 타입과 퍼스널컬러를 기반으로 선별된 추천 상품입니다."

        match_label = (
            "인생템 확률 매칭" if match_score >= 90
            else "높은 적합도" if match_score >= 70
            else "괜찮은 선택" if match_score >= 50
            else "추천 상품"
        )

        result = {
            "matchScore": match_score,
            "matchLabel": match_label,
            "aiReason": ai_reason,
            "mainRecommendations": main_recommendations,
            "similarUserProducts": collaborative,
            "alternativeProducts": alternative,
        }

        # Qwen이 호출 안 한 에이전트는 직접 실행
        if not result["alternativeProducts"] and req.baseProductId:
            try:
                from agents.alternative_agent import run_alternative
                alt_results = await run_alternative(
                    base_product_id=req.baseProductId,
                    exclude_ids=[req.baseProductId],
                    top_k=5,
                )
                result["alternativeProducts"] = [r.model_dump(by_alias=True) for r in alt_results]
                print(f"[agent_router] alternative fallback: {len(result['alternativeProducts'])}개")
            except Exception as e:
                print(f"[agent_router] alternative fallback 실패: {e}")

        if not result["similarUserProducts"]:
            try:
                from agents.collaborative_agent import run_collaborative
                collab_results = await run_collaborative(
                    user_id=req.userId,
                    skin_type=req.userProfile.skinType,
                    personal_color=req.userProfile.personalColor,
                    exclude_ids=[req.baseProductId] if req.baseProductId else [],
                    top_k=5,
                )
                result["similarUserProducts"] = [r.model_dump(by_alias=True) for r in collab_results]
                print(f"[agent_router] collaborative fallback: {len(result['similarUserProducts'])}개")
            except Exception as e:
                print(f"[agent_router] collaborative fallback 실패: {e}")

        await asyncio.to_thread(_write_result, req.jobId, result)
        await _save_user_context(req)

    except Exception as e:
        await job_updater.update(req.jobId, status="FAILED", error_msg=str(e))


@router.post("/agent/run", status_code=202)
async def agent_run(req: AgentRunRequest, background_tasks: BackgroundTasks) -> dict:
    background_tasks.add_task(_run_agent, req)
    return {"jobId": req.jobId, "status": "accepted"}
