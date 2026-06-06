from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel
from langchain_core.messages import HumanMessage

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

        from agents.tools import _collaborative_store, _alternative_store, _score_store
        job_id = req.jobId

        # store에서 실제 tool 결과 수집
        collaborative = _collaborative_store.pop(job_id, [])
        alternative = _alternative_store.pop(job_id, [])
        scores = _score_store.pop(job_id, [])
        match_score = 0
        if scores:
            top = max(scores, key=lambda x: x.get("totalScore", 0))
            match_score = min(100, int(top.get("totalScore", 0)))

        # Qwen 최종 응답 파싱 시도 — 실패하면 store 데이터로 직접 구성
        last_content = final_state["messages"][-1].content.strip()
        if last_content.startswith("```"):
            last_content = last_content.strip("`").removeprefix("json").strip()

        try:
            result = json.loads(last_content)
        except (json.JSONDecodeError, ValueError):
            print(f"[agent_router] Qwen 최종 응답 파싱 실패, store로 결과 구성. raw='{last_content[:200]}'")
            result = {
                "matchScore": match_score,
                "matchLabel": (
                    "인생템 확률 매칭" if match_score >= 90
                    else "높은 적합도" if match_score >= 70
                    else "괜찮은 선택" if match_score >= 50
                    else "추천 상품"
                ),
                "aiReason": "사용자 피부 타입과 퍼스널컬러를 기반으로 선별된 추천 상품입니다.",
                "similarUserProducts": collaborative,
                "alternativeProducts": alternative,
            }

        result["similarUserProducts"] = collaborative or result.get("similarUserProducts", [])
        result["alternativeProducts"] = alternative or result.get("alternativeProducts", [])
        if match_score:
            result["matchScore"] = match_score

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
