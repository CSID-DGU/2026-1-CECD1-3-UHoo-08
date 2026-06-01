from __future__ import annotations

from typing import List
from pydantic import BaseModel


class ProductResponse(BaseModel):
    productId: str | None = None
    name: str | None = None
    brand: str | None = None
    category: str | None = None          # "base" | "sun" | "lip" | "skincare"
    geminiPrice: dict = {}
    reviewSummary: dict = {}
    ingredients: List[str] = []
