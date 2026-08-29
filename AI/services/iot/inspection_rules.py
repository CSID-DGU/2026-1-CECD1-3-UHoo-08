"""
제품 카테고리별 확인 항목

── "확인해 보세요"만으로는 아무것도 알려주지 않는다 ────────────────
무엇을 어떻게 볼지 함께 줘야 한다. 색을 봐야 하는 제품과 냄새를 맡아야
하는 제품이 다르고, 순서도 다르다.

── 항목은 임의로 만든 것이 아니다 ──────────────────────────────────
식약처 「화장품 안정성시험 가이드라인」의 시험항목을 소비자가 확인
가능한 형태로 옮긴 것이다.

    성상·색    "손등에 발라 다른 부위와 색을 비교하세요"
    냄새       "시큼하거나 기름 냄새가 나나요?"
    유화상태   "층이 분리되었나요?"
    점도       "평소보다 묽거나 되직한가요?"
    미생물     측정 불가 — 눈가 제품은 보수적으로 안내

미생물은 소비자가 확인할 방법이 없다. 그래서 눈가 제품만은 다른 항목과
달리 "확인해 보라"가 아니라 "사용을 멈추고 판단하시라"에 가깝게 쓴다.
감염 위험이 있는 부위라 그렇다.

── 규칙 테이블로 구현한다 ──────────────────────────────────────────
설계서가 명시한 이유 그대로다. 환각 위험이 없고, 판단 근거를 질의응답에서
그대로 설명할 수 있다. "이 문구는 어디서 나왔나요"에 답할 수 있어야 한다.

── 여전히 판정하지 않는다 ──────────────────────────────────────────
항목을 제시하는 것과 상했다고 말하는 것은 다르다. 여기서 하는 일은
사용자가 스스로 확인할 수 있도록 순서를 알려주는 것뿐이다. 결과 판단은
사용자가 한다. 그래서 마지막에 답을 받는다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from services.iot.thermal_profile import normalize_category


@dataclass
class CheckStep:
    """확인 항목 한 줄."""
    order: int
    # 가이드라인의 어느 시험항목에서 왔는지. 발표에서 근거를 대는 데 쓴다.
    basis: str
    text: str
    # AS7341로 도울 수 있는 항목인지. 색은 기계가 사람보다 잘 본다.
    optical: bool = False


@dataclass
class Protocol:
    category: str
    label: str
    steps: List[CheckStep]
    answers: List[str]
    # 눈가 제품처럼 따로 덧붙일 말이 있는 경우
    caution: Optional[str] = None
    note: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "label": self.label,
            "steps": [
                {"order": s.order, "basis": s.basis, "text": s.text, "optical": s.optical}
                for s in self.steps
            ],
            "answers": self.answers,
            "caution": self.caution,
            "note": self.note,
        }


# 사용자가 고를 수 있는 답. 설계서 §5-7의 피드백 루프 입력이다.
ANSWER_OK = "이상 없음"
ANSWER_COLOR = "색이 다름"
ANSWER_SMELL = "냄새가 남"
ANSWER_SEPARATED = "분리됨"
ANSWER_TURBID = "혼탁함"
ANSWER_TEXTURE = "질감 변화"
ANSWER_CLUMP = "덩어리짐"


# ── 세부 유형 판별 ───────────────────────────────────────────────
#
# thermal_profile의 카테고리는 base / sun / lip / skincare 넷뿐이라
# 확인 항목을 가르기에는 거칠다. 크림과 토너가 둘 다 skincare인데
# 봐야 할 것이 정반대다(표면 변색 vs 부유물).
#
# 그래서 제품명으로 한 번 더 나눈다. thermal_profile과 같은 한계를
# 가진다 — 전성분이 없어 이름에 기대는 것이다.
_EYE_WORDS = ("아이크림", "아이 크림", "아이세럼", "마스카라", "아이라이너",
              "아이섀도", "속눈썹", "아이 에센스")
_OIL_WORDS = ("오일", "세럼", "앰플", "에센스", "serum", "ampoule")
_CLEAR_WORDS = ("토너", "스킨", "미스트", "부스터", "워터", "퍼스트")


def _subtype(name: Optional[str], category: str, optical_grade: Optional[str]) -> str:
    """
    확인 항목을 고르기 위한 세부 유형.

    optical_grade가 unsuitable이면 투명 제형이라는 뜻이므로 그것을 먼저 믿는다.
    이름 매칭보다 앞선 단계에서 이미 판정된 값이다.
    """
    text = (name or "").replace(" ", "").lower()

    if any(w.replace(" ", "") in text for w in _EYE_WORDS):
        return "eye"
    if category == "base":
        return "base"
    if category == "lip":
        return "lip"
    if category == "sun":
        # 자외선차단제는 백탁 크림이 대부분이라 크림과 같은 항목을 본다.
        return "cream"
    if (optical_grade or "").lower() == "unsuitable":
        return "clear"
    if any(w in text for w in _CLEAR_WORDS):
        return "clear"
    if any(w in text for w in _OIL_WORDS):
        return "oil"
    return "cream"


# ── 카테고리별 항목 (설계서 §5-6 표) ─────────────────────────────
#
#   파운데이션·쿠션   색 비교 → 펌프 주변 굳음 → 층 분리
#   오일·세럼         냄새(산패) → 층 분리 → 점도
#   크림·로션         표면 변색 → 물기 분리 → 냄새
#   립 제품           표면 블루밍 → 냄새 → 질감
#   아이 제품         덩어리짐 → 냄새 → 감염 위험 병기
#   투명 토너·에센스   냄새 → 부유물·혼탁 → 점도
_PROTOCOLS: Dict[str, Protocol] = {
    "base": Protocol(
        category="base", label="파운데이션·쿠션",
        steps=[
            CheckStep(1, "성상·색",
                      "손등에 소량 발라 다른 부위와 색을 비교하세요. "
                      "평소보다 누렇게 뜨나요?", optical=True),
            CheckStep(2, "성상",
                      "펌프나 뚜껑 주변에 굳은 자국이나 덩어리가 있나요?"),
            CheckStep(3, "유화상태",
                      "용기를 기울였을 때 층이 분리돼 있나요?"),
        ],
        answers=[ANSWER_OK, ANSWER_COLOR, ANSWER_CLUMP, ANSWER_SEPARATED],
        note="색 변화는 기계가 눈보다 먼저 잡습니다. 측정하기로 함께 확인해 보세요.",
    ),
    "oil": Protocol(
        category="oil", label="오일·세럼",
        steps=[
            CheckStep(1, "냄새",
                      "향이 평소와 다른가요? 시큼하거나 기름 전 냄새가 나나요?"),
            CheckStep(2, "유화상태",
                      "용기를 세워 두었을 때 층이 분리돼 있나요?"),
            CheckStep(3, "점도",
                      "한 방울 떨어뜨렸을 때 평소보다 묽거나 되직한가요?"),
        ],
        answers=[ANSWER_OK, ANSWER_SMELL, ANSWER_SEPARATED, ANSWER_TEXTURE],
        note="식물성 오일은 산패하면 냄새가 먼저 바뀝니다. 색보다 코가 빠릅니다.",
    ),
    "cream": Protocol(
        category="cream", label="크림·로션",
        steps=[
            CheckStep(1, "성상·색",
                      "뚜껑을 열고 표면 색이 평소와 다른지 보세요. "
                      "가장자리가 누렇게 변했나요?", optical=True),
            CheckStep(2, "유화상태",
                      "표면에 물기가 배어 나오거나 층이 분리돼 있나요?"),
            CheckStep(3, "냄새",
                      "향이 평소와 다른가요?"),
        ],
        answers=[ANSWER_OK, ANSWER_COLOR, ANSWER_SEPARATED, ANSWER_SMELL],
    ),
    "lip": Protocol(
        category="lip", label="립 제품",
        steps=[
            CheckStep(1, "성상",
                      "표면에 하얀 가루막(블루밍)이 생겼나요?", optical=True),
            CheckStep(2, "냄새",
                      "향이 평소와 다른가요? 기름 전 냄새가 나나요?"),
            CheckStep(3, "점도",
                      "발랐을 때 평소보다 거칠거나 잘 발리지 않나요?"),
        ],
        answers=[ANSWER_OK, ANSWER_COLOR, ANSWER_SMELL, ANSWER_TEXTURE],
        note="블루밍은 온도 변화로도 생깁니다. 그 자체가 변질을 뜻하지는 않습니다.",
    ),
    "eye": Protocol(
        category="eye", label="아이 제품",
        steps=[
            CheckStep(1, "성상",
                      "브러시나 팁 끝에 덩어리가 굳어 있나요?"),
            CheckStep(2, "냄새",
                      "향이 평소와 다른가요?"),
            CheckStep(3, "점도",
                      "평소보다 되직하거나 잘 발리지 않나요?"),
        ],
        answers=[ANSWER_OK, ANSWER_CLUMP, ANSWER_SMELL, ANSWER_TEXTURE],
        # 미생물은 소비자가 확인할 방법이 없다. 눈은 감염되면 위험한 부위라
        # 다른 카테고리보다 보수적으로 안내한다.
        caution="눈가 제품은 오염 여부를 눈으로 확인할 수 없습니다. "
                "개봉 후 6개월이 지났다면 이상이 없어 보여도 교체를 권합니다.",
    ),
    "clear": Protocol(
        category="clear", label="투명 토너·에센스",
        steps=[
            CheckStep(1, "냄새",
                      "향이 평소와 다른가요? 시큼하거나 알코올 냄새가 강해졌나요?"),
            CheckStep(2, "성상",
                      "밝은 빛에 비춰 부유물이나 혼탁이 있는지 보세요."),
            CheckStep(3, "점도",
                      "평소보다 묽거나 끈적한가요?"),
        ],
        answers=[ANSWER_OK, ANSWER_SMELL, ANSWER_TURBID, ANSWER_TEXTURE],
        note="투명 제형은 광학 측정 대상이 아닙니다. 감각으로 확인해 주세요.",
    ),
}


def build_protocol(
    name: Optional[str],
    category: Optional[str] = None,
    optical_grade: Optional[str] = None,
    *,
    pao_months: Optional[int] = None,
    opened_months: Optional[float] = None,
) -> Dict[str, Any]:
    """
    제품 하나에 대한 확인 절차.

    pao_months와 opened_months를 주면 마지막에 사용기간 확인을 덧붙인다.
    설계서 예시의 "용기에 표시된 개봉 후 사용기간(PAO)을 확인하세요"가
    그것이며, 이미 지났다면 그 사실을 알려준다.
    """
    cat = normalize_category(category)
    sub = _subtype(name, cat, optical_grade)
    proto = _PROTOCOLS[sub]

    steps = [
        {"order": s.order, "basis": s.basis, "text": s.text, "optical": s.optical}
        for s in proto.steps
    ]

    # PAO 안내는 감각 점검 뒤에 붙인다. 앞에 두면 "기간이 지났으니 버려라"로
    # 읽혀서, 확인해 보라는 취지가 묻힌다.
    if pao_months:
        last = len(steps) + 1
        if opened_months is not None and opened_months > pao_months:
            steps.append({
                "order": last, "basis": "사용기간",
                "text": (f"용기에 표시된 개봉 후 사용기간을 확인하세요. "
                         f"등록된 정보로는 {pao_months}개월 기준을 "
                         f"{opened_months - pao_months:.0f}개월 지났습니다."),
                "optical": False,
            })
        else:
            steps.append({
                "order": last, "basis": "사용기간",
                "text": "용기에 표시된 개봉 후 사용기간(PAO)을 확인하세요.",
                "optical": False,
            })

    out = proto.as_dict()
    out["steps"] = steps
    return out


# 화면의 답변 → user_feedback.answer 코드.
#
# DB CHECK 제약이 다섯 값만 허용한다(none/color/odor/separation/texture).
# 화면에는 더 세분화된 항목이 있어 가까운 것으로 접는다. 덩어리짐과
# 혼탁은 성상 변화라 texture로 묶는다.
FEEDBACK_CODE = {
    ANSWER_OK: "none",
    ANSWER_COLOR: "color",
    ANSWER_SMELL: "odor",
    ANSWER_SEPARATED: "separation",
    ANSWER_TEXTURE: "texture",
    ANSWER_TURBID: "texture",
    ANSWER_CLUMP: "texture",
}

# 점검 목록에 붙일 짧은 표시. 카드에 한 줄로 들어가야 해서 길면 안 된다.
SHORT_LABEL = {
    ANSWER_COLOR: "색 변화",
    ANSWER_SMELL: "냄새 변화",
    ANSWER_SEPARATED: "층 분리",
    ANSWER_TURBID: "부유물",
    ANSWER_TEXTURE: "질감 변화",
    ANSWER_CLUMP: "덩어리",
}

# 항목별 안내. 사용자가 고른 것마다 하나씩 보여준다.
#
# 기록했다는 말은 쓰지 않는다. 저장은 우리 일이고 사용자에게 알릴 이유가
# 없다. 사용자가 알아야 할 것은 "그래서 어떻게 해야 하는가"뿐이다.
_ADVICE = {
    ANSWER_COLOR: [
        "색 변화만으로 사용 여부를 정하기는 어렵습니다.",
        "냄새와 질감도 함께 확인해 보세요.",
    ],
    ANSWER_SMELL: [
        "냄새 변화는 되돌아오지 않습니다.",
        "얼굴에 쓰기 전에 팔 안쪽에 발라 보시고, 붉어지면 사용을 멈추세요.",
    ],
    ANSWER_SEPARATED: [
        "흔들었을 때 다시 섞인다면 일시적인 분리일 수 있습니다.",
        "섞이지 않는다면 사용을 멈추시는 편이 좋습니다.",
    ],
    ANSWER_TURBID: [
        "부유물이 보이면 눈가나 상처가 있는 부위에는 쓰지 마세요.",
    ],
    ANSWER_CLUMP: [
        "굳은 덩어리는 세균이 자라기 쉬운 자리입니다.",
        "눈가나 상처가 있는 부위에는 쓰지 마세요.",
    ],
    ANSWER_TEXTURE: [
        "질감이 달라졌다면 성분이 변했을 수 있습니다.",
        "팔 안쪽에 먼저 발라 보시고 자극이 없는지 확인하세요.",
    ],
}

# 이 중 하나라도 고르면 교체를 권한다. 되돌릴 수 없는 변화들이다.
_REPLACE_TRIGGERS = (ANSWER_SMELL, ANSWER_TURBID, ANSWER_CLUMP)


def answer_guidance(
    answers: List[str],
    protocol_category: str,
) -> Dict[str, Any]:
    """
    사용자가 고른 항목들에 대한 안내.

    여러 개를 고를 수 있다. 냄새도 나고 층도 분리됐다면 둘 다 말해야 한다.
    하나만 보여주면 나머지는 못 본 것이 된다.

    여기서도 "상했습니다"라고 말하지 않는다. 관측된 사실에 대해 무엇을
    하면 되는지 알려줄 뿐이며, 최종 판단은 사용자 몫이다.
    """
    picked = [a for a in answers if a in ANSWERS]

    if not picked or picked == [ANSWER_OK]:
        return {
            "headline": "이상이 없다고 확인하셨습니다",
            "sections": [],
            "lines": ["다음 점검 때 이 확인을 기준으로 변화를 봅니다."],
            "recommend_replace": False,
            "findings": [],
        }

    issues = [a for a in picked if a != ANSWER_OK]

    sections = []
    for a in issues:
        sections.append({
            "label": SHORT_LABEL.get(a, a),
            "lines": _ADVICE.get(a, []),
        })

    lines: List[str] = []
    if protocol_category == "eye":
        lines.append("눈가 제품은 오염이 눈에 보이지 않습니다. "
                     "이상이 하나라도 있으면 교체를 권합니다.")

    return {
        "headline": ("확인해 주셔서 감사합니다"
                     if len(issues) == 1 else "확인하신 내용입니다"),
        "sections": sections,
        "lines": lines,
        "recommend_replace": any(a in _REPLACE_TRIGGERS for a in issues)
                             or protocol_category == "eye",
        "findings": [SHORT_LABEL.get(a, a) for a in issues],
    }


def summary_label(findings: List[str]) -> Optional[str]:
    """
    점검 목록에 붙일 한 줄.

    "상했습니다"가 아니라 사용자가 확인한 사실을 그대로 옮긴다.
    판단한 것은 시스템이 아니라 사용자다.
    """
    if not findings:
        return None
    if len(findings) == 1:
        return f"{findings[0]} 확인됨 · 주의가 필요합니다"
    return f"{' · '.join(findings)} 확인됨 · 주의가 필요합니다"


ANSWERS = [ANSWER_OK, ANSWER_COLOR, ANSWER_SMELL, ANSWER_SEPARATED,
           ANSWER_TURBID, ANSWER_TEXTURE, ANSWER_CLUMP]