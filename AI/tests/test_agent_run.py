import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import asyncio
import json
from langchain_core.messages import HumanMessage
from graph.action_model import agent_graph
from db.supabase_client import get_supabase

BASE_PRODUCT_ID = "cb4cc8ac-17a9-4a63-a5b6-f00164c91f3f"  # 릴리바이레드 쥬시 라이어 워터 틴트
TEST_USER_ID    = "00000000-0000-0000-0000-000000000001"
TEST_JOB_ID     = "00000000-0000-0000-0000-000000000099"


def setup_job():
    sb = get_supabase()
    sb.table("users").upsert({
        "id": TEST_USER_ID,
        "name": "테스트유저",
        "provider": "EMAIL",
    }).execute()
    sb.table("recommendation_jobs").upsert({
        "id": TEST_JOB_ID,
        "user_id": TEST_USER_ID,
        "base_product_id": BASE_PRODUCT_ID,
        "status": "PENDING",
        "progress": 0,
    }).execute()


def cleanup_job():
    sb = get_supabase()
    sb.table("recommendation_jobs").delete().eq("id", TEST_JOB_ID).execute()
    sb.table("users").delete().eq("id", TEST_USER_ID).execute()


initial_state = {
    "messages": [HumanMessage(content=(
        f"작업 ID: {TEST_JOB_ID}\n"
        f"사용자 ID: {TEST_USER_ID}\n"
        f"기준 상품 ID: {BASE_PRODUCT_ID}\n"
        "구매 목적: DAILY\n"
        "가격 허용 범위: 10\n"
        '사용자 프로필: {"skinType": "지성", "skinConcerns": ["모공"], "personalColor": "웜톤"}\n\n'
        "화장품 추천을 시작하세요."
    ))],
    "job_id": TEST_JOB_ID,
    "user_id": TEST_USER_ID,
    "base_product_id": BASE_PRODUCT_ID,
    "search_purpose": "DAILY",
    "price_tolerance_percent": 10,
    "user_profile": {"skinType": "지성", "skinConcerns": ["모공"], "personalColor": "웜톤"},
    "candidates": [],
    "intent_vector": [],
    "scores": [],
    "alternatives": [],
    "collaborative_results": [],
    "final_result": None,
}

setup_job()
try:
    result = asyncio.run(agent_graph.ainvoke(initial_state))
    last = result["messages"][-1].content.strip()
    if last.startswith("```"):
        last = last.strip("`").removeprefix("json").strip()
    print(json.dumps(json.loads(last), ensure_ascii=False, indent=2))
finally:
    cleanup_job()
