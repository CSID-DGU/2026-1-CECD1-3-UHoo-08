"""
lip 카테고리 상품 시딩 스크립트
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.product_crawler import crawl_and_seed

print("lip 상품 시딩 시작...")
result = crawl_and_seed("lip", limit=20)

print(f"\n완료: 저장 {result['saved']}개, 스킵 {result['skipped']}개, 오류 {len(result['errors'])}개")
for p in result["products"]:
    status = "✓" if p["status"] == "saved" else "~"
    print(f"  {status} {p.get('brand', '')} {p.get('name', '')} ({p.get('lowest_price', '')}원)")
if result["errors"]:
    print("\n오류 목록:")
    for e in result["errors"]:
        print(f"  - {e}")
