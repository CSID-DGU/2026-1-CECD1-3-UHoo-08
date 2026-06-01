from __future__ import annotations

from pydantic import BaseModel


class ExtractedProduct(BaseModel):
    product_name: str | None = None
    brand: str | None = None
    category: dict | None = None       # {"main": base|sun|lip|skincare, "sub": ...}
    attributes: dict | None = None     # {"shade", "type", "volume", "unit"}
    package_claims: list[str] = []
    detected_objects: list[str] = []


class UserQuery(BaseModel):
    budget: int | None = None          # 예산 (원)
    category: str | None = None        # 예: "스킨케어", "립"
    conditions: list[str] = []         # 기타 조건: ["보습", "저자극"]
    raw_text: str = ""                 # 원문 보존 (RAG 입력용)
