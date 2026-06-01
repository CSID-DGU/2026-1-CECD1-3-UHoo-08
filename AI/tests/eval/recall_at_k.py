"""
alternative_agent 추천 품질 평가 — Recall@K, MRR.

eval_dataset.json의 사람 라벨(기준 상품 → 정답 대체 상품)을 기준으로
match_alternatives 결과가 정답을 얼마나 잘 맞추는지 측정.

사용법:
    cd AI
    python -m tests.eval.recall_at_k            # K=10 기본
    python -m tests.eval.recall_at_k --k 5

전제: product_embeddings에 임베딩이 적재돼 있어야 의미 있는 수치가 나옴.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from db.vector_search import match_alternatives

_DATASET_PATH = Path(__file__).parent / "eval_dataset.json"


def load_dataset() -> List[Dict[str, Any]]:
    """eval_dataset.json 로드. 메모용 필드(_comment 등)와 미치환 placeholder 제외."""
    raw = json.loads(_DATASET_PATH.read_text(encoding="utf-8"))
    cases = []
    for case in raw:
        base_id = case.get("base_product_id", "")
        truth = case.get("ground_truth_alternative_ids", [])
        # placeholder 미치환 케이스는 평가에서 제외
        if base_id.startswith("REPLACE_WITH") or not truth:
            continue
        cases.append({"base_product_id": base_id, "ground_truth": set(truth)})
    return cases


def evaluate(k: int = 10) -> Dict[str, Any]:
    """Recall@K, MRR 계산."""
    cases = load_dataset()
    if not cases:
        return {
            "recall@k": 0.0,
            "mrr": 0.0,
            "n_cases": 0,
            "note": "유효한 평가 케이스 없음. eval_dataset.json의 placeholder를 실제 uuid로 채우세요.",
        }

    recall_total = 0.0
    rr_total = 0.0

    for case in cases:
        result = match_alternatives(case["base_product_id"], match_count=k)
        result_ids = [r["product_id"] for r in result]
        truth = case["ground_truth"]

        # Recall@K = 정답 중 상위 K에 포함된 비율
        hits = sum(1 for rid in result_ids if rid in truth)
        recall_total += hits / len(truth)

        # MRR = 첫 정답의 역순위
        for rank, rid in enumerate(result_ids, start=1):
            if rid in truth:
                rr_total += 1.0 / rank
                break

    n = len(cases)
    return {
        "recall@k": round(recall_total / n, 4),
        "mrr": round(rr_total / n, 4),
        "n_cases": n,
        "k": k,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="alternative_agent Recall@K 평가")
    parser.add_argument("--k", type=int, default=10)
    args = parser.parse_args()
    metrics = evaluate(k=args.k)
    print(json.dumps(metrics, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()