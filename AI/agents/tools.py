import json

from langchain_core.tools import tool

# job_id별 사이드채널 저장소 (LLM 컨텍스트 오염 방지)
_intent_store: dict[str, list] = {}
_collaborative_store: dict[str, list] = {}
_alternative_store: dict[str, list] = {}
_score_store: dict[str, list] = {}

try:
    from agents.discovery_agent import run_discovery
    from models.agent_context import UserProfile
    _DISCOVERY = True
except ImportError:
    _DISCOVERY = False

try:
    from agents.alternative_agent import run_alternative
    _ALTERNATIVE = True
except ImportError:
    _ALTERNATIVE = False

try:
    from agents.score_agent import run_score
    _SCORE = True
except ImportError:
    _SCORE = False

try:
    from agents.collaborative_agent import run_collaborative
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
    반환: {"candidates": [...]} JSON 문자열
    """
    if not _DISCOVERY:
        return json.dumps({"candidates": []})

    if not base_product_id:
        return json.dumps({"candidates": [], "error": "base_product_id 필요"})

    if isinstance(user_profile, str):
        profile_dict = json.loads(user_profile) if user_profile.strip() else {}
    else:
        profile_dict = user_profile or {}
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

    if job_id:
        _intent_store[job_id] = result["intent_vector"]
        from services import job_updater
        await job_updater.update(job_id, step="후보 탐색", progress=25, status="IN_PROGRESS")

    return json.dumps({"candidates": result["candidates"]})


@tool
async def run_score_agent(
    candidates: str,
    user_profile: str,
    price_tolerance_percent: int,
    base_product_price: float,
    search_purpose: str = "",
    job_id: str = "",
) -> str:
    """
    후보 상품 각각에 대해 예산·가격·리뷰·개인화 점수를 계산합니다.
    candidates는 run_discovery_agent가 반환한 candidates 배열 JSON 문자열.
    반환: 총점 기준 내림차순 정렬된 scored_candidates JSON 문자열
    """
    if not _SCORE:
        return json.dumps([])

    # intent_vector를 사이드채널에서 읽고 삭제 (메모리 누수 방지)
    resolved_intent_vector = (_intent_store.pop(job_id, None) if job_id else None) or []

    # candidates JSON → candidate_ids 추출
    parsed = json.loads(candidates) if isinstance(candidates, str) else candidates
    if isinstance(parsed, dict) and "candidates" in parsed:
        candidate_list = parsed["candidates"]
    else:
        candidate_list = parsed if isinstance(parsed, list) else []
    candidate_ids = [c["product_id"] for c in candidate_list if "product_id" in c]

    # user_profile camelCase → snake_case (personalization_scorer 요구사항)
    if isinstance(user_profile, str):
        profile_dict = json.loads(user_profile) if user_profile.strip() else {}
    else:
        profile_dict = user_profile or {}
    profile_snake = {
        "skin_type": profile_dict.get("skinType"),
        "personal_color": profile_dict.get("personalColor"),
        "skin_concerns": profile_dict.get("skinConcerns", []),
    }

    result = await run_score(
        intent_vector=resolved_intent_vector,
        candidate_ids=candidate_ids,
        user_profile=profile_snake,
        search_purpose=search_purpose or None,
        price_tolerance_percent=price_tolerance_percent,
        target_price=int(base_product_price) if base_product_price else None,
    )

    if job_id:
        _score_store[job_id] = result
        from services import job_updater
        await job_updater.update(job_id, step="AI 분석", progress=60, status="IN_PROGRESS")

    return json.dumps(result)


@tool
async def run_alternative_agent(
    base_product_id: str,
    exclude_product_ids: str = "[]",
    top_k: int = 5,
    job_id: str = "",
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

    serialized = [r.model_dump(by_alias=True) for r in result]
    if job_id:
        _alternative_store[job_id] = serialized

    return json.dumps(serialized)


@tool
async def run_collaborative_agent(
    user_id: str,
    skin_type: str = "",
    personal_color: str = "",
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

    result = await run_collaborative(
        user_id=user_id,
        skin_type=skin_type or None,
        personal_color=personal_color or None,
        exclude_ids=json.loads(exclude_product_ids),
        top_k=top_k,
    )
    serialized = [r.model_dump(by_alias=True) for r in result]
    if job_id:
        _collaborative_store[job_id] = serialized
    return json.dumps(serialized)


ALL_TOOLS = [
    run_discovery_agent,
    run_score_agent,
    run_alternative_agent,
    run_collaborative_agent,
]
