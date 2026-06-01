"""
product_features.feature_json을 카테고리별 자연어 문장으로 변환.

product_embeddings.feature_vec을 생성하기 위해 사용된다.
리뷰 어휘와 정합성을 맞추기 위해 한국어 자연 표현을 사용한다.
null 필드는 문장에서 자동 제외.

허용값 (스키마 기준):
  coverage : 가벼운 | 중간 | 높음
  finish   : 매트 | 세미매트 | 글로우 | 촉촉
  skin_type: 건성 | 지성 | 복합 | 민감
  texture  : 가벼운 | 중간 | 진한
  personal_color: 웜톤 | 쿨톤 | 뉴트럴
  lasting_power : 낮음 | 중간 | 높음
"""
from typing import Any, Dict


def build_product_text(category: str, feature_json: Dict[str, Any]) -> str:
    """카테고리별 자연어 변환 분기."""
    if category == "base":
        return _build_base(feature_json)
    elif category == "sun":
        return _build_sun(feature_json)
    elif category == "lip":
        return _build_lip(feature_json)
    elif category == "skincare":
        return _build_skincare(feature_json)
    raise ValueError(f"알 수 없는 카테고리: {category}")


def _build_base(f: Dict[str, Any]) -> str:
    parts = []
    if f.get("product_type"):
        parts.append(f"{f['product_type']} 제품")
    if f.get("coverage"):
        parts.append(f"커버력이 {f['coverage']}")
    if f.get("finish"):
        parts.append(f"{f['finish']} 마무리감")
    if f.get("skin_type"):
        parts.append(f"{f['skin_type']} 피부에 적합")
    if f.get("skin_concern"):
        concerns = "·".join(f["skin_concern"])
        parts.append(f"{concerns} 고민에 효과적")
    if f.get("personal_color"):
        parts.append(f"{f['personal_color']}에 어울림")
    if f.get("lasting_power"):
        parts.append(f"지속력 {f['lasting_power']}")
    if f.get("spf"):
        parts.append(f"자외선 차단 {f['spf']}")
    return ". ".join(parts) + "." if parts else ""


def _build_sun(f: Dict[str, Any]) -> str:
    parts = []
    if f.get("product_type"):
        parts.append(f"{f['product_type']} 제품")
    if f.get("spf"):
        parts.append(f"{f['spf']}")
    if f.get("pa"):
        parts.append(f"{f['pa']}")
    if f.get("finish"):
        parts.append(f"{f['finish']} 마무리감")
    if f.get("skin_type"):
        parts.append(f"{f['skin_type']} 피부에 적합")
    if f.get("skin_concern"):
        concerns = "·".join(f["skin_concern"])
        parts.append(f"{concerns}에 도움")
    if f.get("lasting_power"):
        parts.append(f"지속력 {f['lasting_power']}")
    if f.get("white_cast") is not None:
        parts.append(f"백탁 {'있음' if f['white_cast'] else '없음'}")
    return ". ".join(parts) + "." if parts else ""


def _build_lip(f: Dict[str, Any]) -> str:
    parts = []
    if f.get("product_type"):
        parts.append(f"{f['product_type']} 제품")
    if f.get("finish"):
        parts.append(f"{f['finish']} 마무리감")
    if f.get("personal_color"):
        parts.append(f"{f['personal_color']}에 어울림")
    if f.get("lasting_power"):
        parts.append(f"지속력 {f['lasting_power']}")
    if f.get("moisturizing") is not None:
        parts.append(f"보습력 {'높음' if f['moisturizing'] else '낮음'}")
    if f.get("skin_concern"):
        concerns = "·".join(f["skin_concern"])
        parts.append(f"{concerns}에 도움")
    return ". ".join(parts) + "." if parts else ""


def _build_skincare(f: Dict[str, Any]) -> str:
    parts = []
    if f.get("product_type"):
        parts.append(f"{f['product_type']} 제품")
    if f.get("texture"):
        parts.append(f"{f['texture']} 제형")
    if f.get("skin_type"):
        parts.append(f"{f['skin_type']} 피부에 적합")
    if f.get("skin_concern"):
        concerns = "·".join(f["skin_concern"])
        parts.append(f"{concerns}에 효과적")
    if f.get("key_ingredient"):
        ings = "·".join(f["key_ingredient"])
        parts.append(f"주요 성분 {ings}")
    if f.get("fragrance_free") is not None:
        parts.append(f"{'무향 제품' if f['fragrance_free'] else '향 있음'}")
    return ". ".join(parts) + "." if parts else ""
