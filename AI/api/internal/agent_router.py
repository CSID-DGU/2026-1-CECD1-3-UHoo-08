from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel
from langchain_core.messages import HumanMessage

from graph.action_model import agent_graph

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


def _save_result(job_id: str, result: dict) -> None:
    try:
        from db.supabase_client import get_supabase
        sb = get_supabase()
        sb.table("recommendation_jobs").update({
            "result": result,
            "status": "COMPLETED",
            "step": "루틴 생성",
            "progress": 100,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", job_id).execute()
    except Exception:
        pass


def _save_failed(job_id: str, error_msg: str) -> None:
    try:
        from db.supabase_client import get_supabase
        sb = get_supabase()
        sb.table("recommendation_jobs").update({
            "status": "FAILED",
            "error_msg": error_msg,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", job_id).execute()
    except Exception:
        pass


async def _run_agent(req: AgentRunRequest) -> None:
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
    try:
        final_state = await agent_graph.ainvoke(initial_state)

        # 마지막 메시지에서 JSON 파싱
        last_content = final_state["messages"][-1].content.strip()
        if last_content.startswith("```"):
            last_content = last_content.strip("`").removeprefix("json").strip()
        result = json.loads(last_content)
        _save_result(req.jobId, result)

    except Exception as e:
        _save_failed(req.jobId, str(e))


@router.post("/agent/run", status_code=202)
async def agent_run(req: AgentRunRequest, background_tasks: BackgroundTasks) -> dict:
    background_tasks.add_task(_run_agent, req)
    return {"jobId": req.jobId, "status": "accepted"}
