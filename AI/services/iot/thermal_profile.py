"""
제품 열민감도 · 개봉 후 사용기간 · 광학 적합성 결정 규칙.

product_thermal_profile 한 행을 만들기 위한 순수 함수 모음이다.
DB에 접근하지 않으므로 단독으로 실행해 규칙 자체를 검증할 수 있다.

    python -m services.iot.thermal_profile

── 전성분 데이터가 없다 ────────────────────────────────────────────
민감도 표는 성분군을 기준으로 한다. 레티놀이 들어 있는지
아닌지는 전성분을 봐야 알 수 있지만, 지금 products 테이블에는 전성분
컬럼이 없다.

그래서 제품명 키워드 매칭을 대용 수단으로 쓴다. "레티놀 나이트 세럼"
처럼 핵심 성분이 제품명에 드러나는 경우가 많다는 관찰에 기댄 것이며,
전성분 DB가 확보되면 `resolve_profile()`의 입력만 바꿔 끼우면 된다
(`ingredients` 인자가 이미 열려 있다).

한계는 분명하다.
    · 성분이 이름에 없으면 못 잡는다 → 카테고리 기본값으로 떨어진다
    · 마케팅 문구를 성분으로 오인할 수 있다 ("비타민 워터 토너")
    · 함량을 모른다 (레티놀 0.01%도 2%도 똑같이 k=1.5)
따라서 이 값은 "정확한 성분 분석"이 아니라 점검 순서를 정하기 위한
보수적 추정이다.

── 카테고리는 네 개뿐이다 ──────────────────────────────────────────
    base     쿠션, 파운데이션, 프라이머, 컨실러
    sun      선크림, 선스틱, 선쿠션, 선스프레이
    lip      틴트, 립스틱, 립글로스, 립밤
    skincare 토너, 에센스, 세럼, 크림, 오일, 로션 등 기타

── 광학 등급은 사용자에게 묻지 않는다 ────────────────
    suitable     색이 있는 제형. delta_pct를 정상 반영 (w4 = 1.0)
    conditional  흰색 크림·로션·반투명. 측정하되 가중치 하향 (w4 = 0.4)
    unsuitable   투명 토너·에센스. 측정 생략 (w4 = 0)

카테고리에서 자동으로 정해지고, skincare 안에서만 이름 키워드로
투명 계열(unsuitable)과 유백·반투명 계열(conditional)을 가른다.
"""
from __future__ import annotations

import logging
import re

from dataclasses import dataclass, field
from typing import Any, Iterable, Optional, Sequence

logger = logging.getLogger(__name__)

# ── 어휘 ──────────────────────────────────────────────────────────
CATEGORIES = ("base", "sun", "lip", "skincare")
FALLBACK_CATEGORY = "skincare"

K_HIGH = 1.5    # 레티놀, 순수 비타민C
K_MEDIUM = 1.3  # 식물성 오일, 유기 자외선차단제
K_NORMAL = 1.0  # 일반 에멀전
K_LOW = 0.7     # 무기 자외선차단제, 파우더

GRADE_SUITABLE = "suitable"
GRADE_CONDITIONAL = "conditional"
GRADE_UNSUITABLE = "unsuitable"


@dataclass(frozen=True)
class Rule:
    """
    키워드 규칙 하나.

    keywords 중 하나라도 걸리고 excludes 중 어느 것도 걸리지 않으면 채택한다.
    excludes가 필요한 이유: "오일프리 로션"에는 '오일'이 들어 있지만
    오히려 오일이 없다는 뜻이다. 부분 문자열 매칭의 대표적 함정이다.
    """

    value: Any
    label: str
    keywords: tuple = ()
    excludes: tuple = ()
    categories: tuple = ()   # 비어 있으면 전 카테고리

    def match(self, text: str, category: str) -> bool:
        if self.categories and category not in self.categories:
            return False
        if any(x in text for x in self.excludes):
            return False
        return any(k in text for k in self.keywords)


@dataclass(frozen=True)
class ThermalProfile:
    """product_thermal_profile 한 행에 해당하는 결정 결과."""

    sensitivity_k: float
    pao_months: int
    optical_grade: str
    driver_note: str
    category: str
    matched: dict = field(default_factory=dict)   # 어떤 규칙이 걸렸는지

    def as_row(self, product_id: str) -> dict:
        """upsert에 그대로 넣을 수 있는 dict."""
        return {
            "product_id": product_id,
            "sensitivity_k": self.sensitivity_k,
            "pao_months": self.pao_months,
            "optical_grade": self.optical_grade,
            "driver_note": self.driver_note,
        }


# ── 성분 민감도 규칙 (위에서부터 검사, 처음 걸린 것 채택) ──────────
#
# 순서가 곧 우선순위다. 고민감을 맨 위에 두는 이유는, 한 제품에 여러
# 키워드가 걸릴 때 더 빨리 늙는 쪽으로 판정해야 점검 순서에서 뒤로
# 밀리지 않기 때문이다. 틀리더라도 "일찍 확인하게 하는" 쪽으로 틀린다.
_SENSITIVITY_RULES: tuple = (
    Rule(K_HIGH, "고민감(레티노이드)",
         keywords=("레티놀", "레티날", "레티노이드", "레티닐",
                   "retinol", "retinal", "바쿠치올")),
    Rule(K_HIGH, "고민감(순수 비타민C)",
         keywords=("비타민c", "비타민씨", "vitaminc", "vitc",
                   "아스코르빅", "아스코르브", "ascorbic", "퓨어비타민"),
         # 유도체(에틸아스코빌 등)는 훨씬 안정하지만 이름만으로는
         # 구분이 어렵다. 보수적으로 고민감으로 둔다.
         excludes=("비타민워터",)),

    Rule(K_LOW, "저민감(무기 자외선차단제)",
         keywords=("무기자차", "미네랄자차", "물리자차", "논케미컬",
                   "논-케미컬", "미네랄선", "mineral", "징크옥사이드",
                   "티타늄디옥사이드")),
    Rule(K_LOW, "저민감(파우더 제형)",
         keywords=("파우더", "팩트", "프레스드", "쉐딩", "섀도", "블러셔")),

    Rule(K_MEDIUM, "중민감(식물성 오일)",
         keywords=("오일", "로즈힙", "아르간", "호호바", "마룰라",
                   "동백", "올리브", "시어버터", "아보카도"),
         excludes=("오일프리", "오일-프리", "oilfree", "오일컨트롤")),
    Rule(K_MEDIUM, "중민감(유기 자외선차단제)",
         keywords=("선크림", "선스틱", "선쿠션", "선스프레이", "선젤",
                   "선세럼", "톤업선", "sunscreen", "uv"),
         categories=("sun",)),
)

# 카테고리 기본값. 키워드가 하나도 안 걸렸을 때 쓴다.
# sun만 1.3인 이유: 국내 유통 제품 다수가 유기 자외선차단제 또는
# 혼합제이며, 무기 전용은 보통 이름에 그 사실을 명시한다.
_SENSITIVITY_DEFAULT = {
    "base": (K_NORMAL, "기본(일반 에멀전)"),
    "sun": (K_MEDIUM, "기본(자외선차단제 — 유기 필터 가정)"),
    "lip": (K_NORMAL, "기본(일반 제형)"),
    "skincare": (K_NORMAL, "기본(일반 에멀전)"),
}


# ── 개봉 후 사용기간(PAO) 규칙 ─────────────────────────────────────
#
# 실제 PAO는 용기에 인쇄된 값이 정답이고, 
# 이 표는 그것을 모를 때 쓰는 관용적 추정이다.
_PAO_RULES: tuple = (
    Rule(6, "고농도 활성 성분",
         keywords=("레티놀", "레티날", "레티노이드", "비타민c", "비타민씨",
                   "아스코르빅", "ascorbic", "퓨어비타민")),
    Rule(6, "고농축 제형(세럼·앰플·에센스)",
         keywords=("세럼", "앰플", "에센스", "serum", "ampoule"),
         categories=("skincare",)),
    Rule(24, "파우더 제형(수분 없음)",
         keywords=("파우더", "팩트", "프레스드", "섀도", "블러셔")),
    Rule(6, "눈가 사용",
         keywords=("아이크림", "아이세럼", "마스카라", "아이라이너")),
)
_PAO_DEFAULT = 12   # 대부분의 스킨케어·베이스·립 제품의 관용값


# ── 광학 적합성 규칙 ────────────────────────────────
#
# base·lip은 색이 있으므로 무조건 suitable, sun은 흰 크림이 많아
# conditional. skincare만 이름으로 투명/유백을 가른다.
_OPTICAL_BY_CATEGORY = {
    "base": (GRADE_SUITABLE, "색조 제형"),
    "lip": (GRADE_SUITABLE, "색조 제형"),
    "sun": (GRADE_CONDITIONAL, "백탁 크림 제형"),
    "skincare": (GRADE_CONDITIONAL, "유백·반투명 제형 가정"),
}

_OPTICAL_RULES: tuple = (
    Rule(GRADE_UNSUITABLE, "투명 제형",
         keywords=("토너", "스킨로션", "미스트", "부스터", "워터",
                   "에센스", "퍼스트", "클렌징워터", "toner", "mist"),
         # 유백색 토너·에센스도 있지만 이름만으로는 갈리지 않는다.
         # 측정 생략 쪽으로 틀리는 편이 안전하다. 광학을 제외해도
         # risk_score가 나머지 가중치로 재정규화하므로 불이익이 없다.
         excludes=("크림", "밤", "오일", "선"),
         categories=("skincare",)),
    Rule(GRADE_SUITABLE, "색이 있는 제형",
         keywords=("오일", "쿠션", "틴트", "밤"),
         excludes=("오일프리", "oilfree"),
         categories=("skincare",)),
)


# ── 텍스트 정규화 ─────────────────────────────────────────────────
_NON_WORD = re.compile(r"[\s\-_/·,\.\(\)\[\]]+")


def normalize(*parts: Any) -> str:
    """
    비교용 텍스트를 만든다.

    공백·하이픈·괄호를 전부 제거하고 소문자로 만든다.
    '비타민 C 세럼'과 '비타민C세럼'과 'Vitamin-C Serum'을 같은 방식으로
    다루기 위해서다. 키워드 표도 같은 형태로 적어야 한다.
    """
    joined = " ".join(str(p) for p in parts if p)
    return _NON_WORD.sub("", joined).lower()


def _first_match(rules: Sequence[Rule], text: str, category: str):
    for r in rules:
        if r.match(text, category):
            return r
    return None


def normalize_category(category: Optional[str]) -> str:
    """
    카테고리를 네 값 중 하나로 강제한다.

    products.category에 예상 밖의 값이 들어 있어도 조용히 통과시키지 않고
    경고를 남긴 뒤 skincare로 떨어뜨린다. 카테고리가 틀리면 광학 등급이
    통째로 틀리므로 눈에 보여야 한다.
    """
    key = (category or "").strip().lower()
    if key in CATEGORIES:
        return key
    if key:
        logger.warning("알 수 없는 카테고리 %r → %s로 처리", category, FALLBACK_CATEGORY)
    return FALLBACK_CATEGORY


def resolve_profile(
    name: Optional[str],
    *,
    category: Optional[str] = None,
    brand: Optional[str] = None,
    ingredients: Optional[Iterable[str]] = None,
) -> ThermalProfile:
    """
    제품 하나의 열민감도·PAO·광학 등급을 결정한다.

    ingredients는 전성분 리스트가 생겼을 때를 위한 자리다. 지금은 None으로
    호출되며, 값이 들어오면 제품명과 함께 같은 키워드 표로 검사한다.
    (전성분이 있으면 '레티닐팔미테이트'처럼 이름에 안 나오는 것도 잡힌다)
    """
    cat = normalize_category(category)
    text = normalize(name, brand, *(ingredients or ()))

    k_rule = _first_match(_SENSITIVITY_RULES, text, cat)
    if k_rule is not None:
        k, k_label = float(k_rule.value), k_rule.label
    else:
        k, k_label = _SENSITIVITY_DEFAULT[cat]

    pao_rule = _first_match(_PAO_RULES, text, cat)
    if pao_rule is not None:
        pao, pao_label = int(pao_rule.value), pao_rule.label
    else:
        pao, pao_label = _PAO_DEFAULT, "기본값"

    opt_rule = _first_match(_OPTICAL_RULES, text, cat)
    if opt_rule is not None:
        grade, grade_label = opt_rule.value, opt_rule.label
    else:
        grade, grade_label = _OPTICAL_BY_CATEGORY[cat]

    note = (f"[{cat}] k={k} {k_label} / PAO {pao}개월 {pao_label} / "
            f"광학 {grade} {grade_label} "
            f"— 전성분 미확보, 제품명 키워드 대용 판정")

    return ThermalProfile(
        sensitivity_k=k,
        pao_months=pao,
        optical_grade=grade,
        driver_note=note,
        category=cat,
        matched={
            "sensitivity": k_label,
            "pao": pao_label,
            "optical": grade_label,
        },
    )


def resolve_row(product: dict) -> dict:
    """
    products 행 하나를 받아 product_thermal_profile 행 dict를 만든다.

    product는 최소한 product_id, name, category를 가져야 한다.
    """
    prof = resolve_profile(
        product.get("name"),
        category=product.get("category"),
        brand=product.get("brand"),
    )
    return prof.as_row(product["product_id"])


if __name__ == "__main__":
    # DB 없이 규칙 자체를 검증한다.
    samples = [
        # (카테고리, 제품명, 기대 k, 기대 PAO, 기대 광학등급)
        ("skincare", "레티놀 0.1% 나이트 세럼", 1.5, 6, "conditional"),
        ("skincare", "비타민C 21.5 앰플", 1.5, 6, "conditional"),
        ("skincare", "히알루론산 수분 크림", 1.0, 12, "conditional"),
        ("skincare", "그린티 밸런싱 토너", 1.0, 12, "unsuitable"),
        ("skincare", "라이스 퍼스트 에센스", 1.0, 6, "unsuitable"),
        ("skincare", "로즈힙 페이셜 오일", 1.3, 12, "suitable"),
        ("skincare", "오일프리 수분 로션", 1.0, 12, "conditional"),
        ("sun", "에어리 선크림 SPF50+", 1.3, 12, "conditional"),
        ("sun", "무기자차 미네랄 선스틱", 0.7, 12, "conditional"),
        ("base", "글로우 쿠션 21호", 1.0, 12, "suitable"),
        ("base", "노세범 미네랄 파우더", 0.7, 24, "suitable"),
        ("lip", "벨벳 립 틴트", 1.0, 12, "suitable"),
        ("lip", "모이스처 립밤", 1.0, 12, "suitable"),
        (None, "정체불명 제품", 1.0, 12, "conditional"),
    ]

    print("=" * 96)
    print("규칙 테이블 검증 — 기대값과 실제값 비교")
    print("=" * 96)
    print(f"  {'카테고리':<10}{'제품명':<28}{'k':>5}{'PAO':>6}  {'광학':<13}판정")
    print("  " + "-" * 92)

    failures = 0
    for cat, name, exp_k, exp_pao, exp_grade in samples:
        p = resolve_profile(name, category=cat)
        ok = (p.sensitivity_k == exp_k
              and p.pao_months == exp_pao
              and p.optical_grade == exp_grade)
        if not ok:
            failures += 1
        mark = "OK" if ok else (f"불일치 (기대 k={exp_k} PAO={exp_pao} "
                                f"{exp_grade})")
        print(f"  {p.category:<10}{name:<28}{p.sensitivity_k:>5}"
              f"{p.pao_months:>6}  {p.optical_grade:<13}{mark}")

    print()
    print(f"  → {len(samples) - failures} / {len(samples)} 통과")

    print()
    print("=" * 96)
    print("판정 근거 (driver_note 예시)")
    print("=" * 96)
    for cat, name in [("skincare", "레티놀 0.1% 나이트 세럼"),
                      ("sun", "무기자차 미네랄 선스틱"),
                      ("skincare", "그린티 밸런싱 토너")]:
        print(f"  {name}")
        print(f"    {resolve_profile(name, category=cat).driver_note}")

    print()
    print("=" * 96)
    print("k값이 점검 순서를 어떻게 가르는가 (같은 열이력·같은 개봉일 가정)")
    print("=" * 96)
    for cat, name in [("skincare", "레티놀 나이트 세럼"),
                      ("sun", "에어리 선크림"),
                      ("skincare", "히알루론산 수분 크림"),
                      ("base", "노세범 미네랄 파우더")]:
        p = resolve_profile(name, category=cat)
        # 열이력 1개월(20℃ 상당)이 PAO를 얼마나 소모하는지
        ratio = (1.0 * p.sensitivity_k) / p.pao_months * 100
        print(f"  {name:<24}k={p.sensitivity_k}  PAO={p.pao_months:>2}개월  "
              f"→ 20℃ 1개월당 소모 {ratio:5.1f}%")