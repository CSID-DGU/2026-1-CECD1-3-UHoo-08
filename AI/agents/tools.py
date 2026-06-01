import json
from langchain_core.tools import tool

# job_id별 intent_vector 사이드채널 저장소
# discovery → score 전달 시 LLM 컨텍스트 오염 방지
_intent_store: dict[str, list] = {}

# discovery_agent — 구현 완료
try:
    from agents.discovery_agent import run_discovery
    from models.agent_context import UserProfile
    _DISCOVERY = True
except ImportError:
    _DISCOVERY = False

# alternative_agent — 구현 완료
try:
    from agents.alternative_agent import run_alternative
    _ALTERNATIVE = True
except ImportError:
    _ALTERNATIVE = False

# score_agent — 미구현
try:
    from agents.score_agent import run as score_run
    _SCORE = True
except ImportError:
    _SCORE = False

# collaborative_agent — 미구현
try:
    from agents.collaborative_agent import run as collaborative_run
    _COLLABORATIVE = True
except ImportError:
    _COLLABORATIVE = False


@tool
async def run_discovery_agent(
    user_id: str,
    user_profile: str,
    base_product_id: str,
    search_purpose: str = "",
    price_tolerance_percent: int = 10,
    job_id: str = "",
) -> str:
    """
    사용자 프로필과 RAG 컨텍스트로 후보 상품을 탐색합니다.
    반환: {"candidates": [...], "intent_vector": [...]} JSON 문자열
    """
    if not _DISCOVERY:
        return json.dumps({"candidates": [], "intent_vector": []})

    if not base_product_id:
        return json.dumps({"candidates": [], "intent_vector": [], "error": "base_product_id 필요"})

    profile_dict = json.loads(user_profile) if isinstance(user_profile, str) else user_profile
    profile = UserProfile(
        user_id=user_id,
        skin_type=profile_dict.get("skinType"),
        personal_color=profile_dict.get("personalColor"),
        skin_concerns=profile_dict.get("skinConcerns", []),
    )
    result = await run_discovery(
        user_profile=profile,
        base_product_id=base_product_id,
        search_purpose=search_purpose or None,
        price_tolerance_percent=price_tolerance_percent,
    )

    # intent_vector는 사이드채널에 저장 — LLM 컨텍스트에 1024차원 벡터 노출 방지
    if job_id:
        _intent_store[job_id] = result["intent_vector"]

    return json.dumps({"candidates": result["candidates"]})


@tool
async def run_alternative_agent(
    base_product_id: str,
    exclude_product_ids: str = "[]",
    top_k: int = 5,
) -> str:
    """
    기준 상품의 feature 벡터와 유사한 대체 상품을 탐색합니다 (순수 벡터 검색).
    exclude_product_ids 는 JSON 배열 문자열.
    반환: 유사도 기준 대체 상품 목록 JSON 문자열
    """
    if not _ALTERNATIVE:
        return json.dumps([])

    result = await run_alternative(
        base_product_id=base_product_id,
        top_k=top_k,
        exclude_ids=json.loads(exclude_product_ids),
    )
    return json.dumps([r.model_dump(by_alias=True) for r in result])


@tool
def run_score_agent(
    candidates: str,
    intent_vector: str,
    user_profile: str,
    price_tolerance_percent: int,
    base_product_price: float,
    search_purpose: str,
    category: str,
    job_id: str,
) -> str:
    """
    후보 상품 각각에 대해 예산·가격·리뷰·개인화 점수를 계산합니다.
    반환: 총점 기준 내림차순 정렬된 scored_candidates JSON 문자열
    """
    if not _SCORE:
        return json.dumps([])

    # intent_vector를 사이드채널에서 읽고 삭제 (메모리 누수 방지)
    resolved_intent_vector = _intent_store.pop(job_id, None) or (
        json.loads(intent_vector) if intent_vector else []
    )

    result = score_run(
        candidates=json.loads(candidates),
        intent_vector=resolved_intent_vector,
        user_profile=json.loads(user_profile) if isinstance(user_profile, str) else user_profile,
        price_tolerance_percent=price_tolerance_percent,
        base_product_price=base_product_price,
        search_purpose=search_purpose or None,
        category=category,
        job_id=job_id or None,
    )
    return json.dumps(result)


@tool
def run_collaborative_agent(
    user_id: str,
    skin_type: str,
    personal_color: str,
    exclude_product_ids: str = "[]",
    top_k: int = 5,
    job_id: str = "",
) -> str:
    """
    유사 피부 조건의 사용자들이 높게 평가한 상품을 협업 필터링으로 추천합니다.
    반환: weighted_score 기준 상품 목록 JSON 문자열
    """
    if not _COLLABORATIVE:
        return json.dumps([])
    result = collaborative_run(
        user_id=user_id,
        skin_type=skin_type,
        personal_color=personal_color,
        top_k=top_k,
        exclude_product_ids=json.loads(exclude_product_ids),
        job_id=job_id or None,
    )
    return json.dumps(result)


ALL_TOOLS = [
    run_discovery_agent,
    run_score_agent,
    run_alternative_agent,
    run_collaborative_agent,
]
