from typing import TypedDict, Optional, Annotated
from langgraph.graph.message import add_messages


class GraphState(TypedDict):
    # ReAct 메시지 히스토리
    messages: Annotated[list, add_messages]

    # 입력 — agent_router가 채움
    job_id: str
    user_id: str
    base_product_id: Optional[str]
    search_purpose: Optional[str]
    price_tolerance_percent: int
    user_profile: dict          # UserProfile 직렬화 dict

    # discovery_agent 출력
    candidates: list[dict]
    intent_vector: list[float]

    # score_agent 출력
    scores: list[dict]

    # alternative_agent 출력
    alternatives: list[dict]

    # collaborative_agent 출력
    collaborative_results: list[dict]

    # 최종 결과 — DB write 전 assembled dict
    final_result: Optional[dict]
