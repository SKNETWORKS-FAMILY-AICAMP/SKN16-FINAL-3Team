#!/usr/bin/env python3
"""
제품 키워드 자동 추출 스크립트

사용법:
    python scripts/extract_product_keywords.py all          # 모든 제품
    python scripts/extract_product_keywords.py LON-MTG     # 특정 제품
    python scripts/extract_product_keywords.py --no-llm all # LLM 검증 없이
"""
import sys
import os
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.services.product_keyword_extractor import ProductKeywordExtractor


def main():
    use_llm = "--no-llm" not in sys.argv
    
    if "--no-llm" in sys.argv:
        sys.argv.remove("--no-llm")
    
    extractor = ProductKeywordExtractor(use_llm=use_llm)
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "all":
            # 모든 제품 추출
            print("🚀 모든 제품 키워드 추출 시작...")
            extractor.extract_all_products(use_llm=use_llm)
            print("✅ 완료!")
        else:
            # 특정 제품 추출
            product_code = sys.argv[1]
            print(f"🚀 {product_code} 키워드 추출 시작...")
            result = extractor.extract_keywords_for_product(product_code, use_llm=use_llm)
            import json
            print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("사용법:")
        print("  python scripts/extract_product_keywords.py <product_code>  # 특정 제품")
        print("  python scripts/extract_product_keywords.py all            # 모든 제품")
        print("  python scripts/extract_product_keywords.py --no-llm all   # LLM 검증 없이")


if __name__ == "__main__":
    main()

