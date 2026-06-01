"""
에이전트 도구 호출 흐름 테스트.
DB팀 파일 없이 Qwen-Plus가 올바른 순서로 도구를 호출하는지 확인.
"""
from langchain_core.messages import HumanMessage
from graph.action_model import agent_graph

INITIAL_STATE = {
    "messages": [
        HumanMessage(content=(
            "다음 사용자의 화장품 추천을 시작하세요.\n"
            "- job_id: test_001\n"
            "- user_id: user_abc\n"
            "- base_product_id: prod_001\n"
            "- user_profile: {\"skinType\": \"OILY\", \"skinConcerns\": [\"ACNE\", \"PORE\"], \"personalColor\": \"SPRING_WARM\"}\n"
            "- search_purpose: DAILY\n"
            "- price_tolerance_percent: 10"
        ))
    ],
}


def main():
    print("=" * 60)
    print("에이전트 도구 호출 테스트 시작")
    print("=" * 60)

    result = agent_graph.invoke(INITIAL_STATE)

    print("\n[메시지 흐름]")
    for msg in result["messages"]:
        msg_type = getattr(msg, "type", "unknown")

        if msg_type == "human":
            print(f"\n[Human] {str(msg.content)[:100]}")

        elif msg_type == "ai":
            content = str(msg.content)[:100] if msg.content else "(tool call 생성)"
            print(f"\n[AI] {content}")
            tool_calls = getattr(msg, "tool_calls", [])
            for tc in tool_calls:
                print(f"   -> 도구 호출: {tc['name']}")
                print(f"      args: {list(tc['args'].keys())}")

        elif msg_type == "tool":
            name = getattr(msg, "name", "")
            content_preview = str(msg.content)[:80]
            print(f"\n[Tool:{name}] {content_preview}")

    print("\n" + "=" * 60)
    print("테스트 완료")


if __name__ == "__main__":
    main()
