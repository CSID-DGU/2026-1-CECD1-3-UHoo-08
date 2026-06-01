"""
LLM 가중치 출력 검증·정규화.

Qwen-Plus가 반환한 4요소 가중치 dict가 다음 조건을 만족하는지 확인:
- 4개 키(budget_fit, price_value, review_score, personalization) 모두 존재
- 값이 0~1 사이 float
- 합이 0이 아님

검증 통과 시 합을 1.0으로 정규화해 반환. 실패 시 기본 가중치(균등 0.25) 반환.
"""
from typing import Any, Dict

DEFAULT_WEIGHTS: Dict[str, float] = {
    "budget_fit": 0.25,
    "price_value": 0.25,
    "review_score": 0.25,
    "personalization": 0.25,
}

REQUIRED_KEYS = set(DEFAULT_WEIGHTS.keys())


def validate_and_normalize(raw: Any) -> Dict[str, float]:
    """
    LLM 출력 검증·정규화.

    잘못된 출력이면 DEFAULT_WEIGHTS 반환 (점수 계산 중단되지 않도록).
    """
    if not isinstance(raw, dict):
        return dict(DEFAULT_WEIGHTS)

    # 키 누락 체크
    if not REQUIRED_KEYS.issubset(raw.keys()):
        return dict(DEFAULT_WEIGHTS)

    # 값 타입·범위 체크
    parsed: Dict[str, float] = {}
    for k in REQUIRED_KEYS:
        v = raw[k]
        if not isinstance(v, (int, float)):
            return dict(DEFAULT_WEIGHTS)
        if v < 0 or v > 1:
            return dict(DEFAULT_WEIGHTS)
        parsed[k] = float(v)

    total = sum(parsed.values())
    if total <= 0:
        return dict(DEFAULT_WEIGHTS)

    # 합 1.0으로 정규화
    return {k: v / total for k, v in parsed.items()}