#!/usr/bin/env python3
"""
카테고리 필터 없이 전체 상품에서 벡터 검색 테스트
정확도 비교 테스트
"""
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from sqlmodel import Session
from app.database import engine
from app.services.product_knowledge_service import ProductKnowledgeService


def test_without_category_filter():
    """카테고리 필터 없이 벡터 검색 테스트"""
    print("🔍 카테고리 필터 없이 벡터 검색 테스트\n")
    
    with Session(engine) as session:
        try:
            product_service = ProductKnowledgeService(
                use_llm=True,
                session=session
            )
            
            if not product_service.use_vector_search:
                print("❌ 벡터 검색이 비활성화되어 있습니다.")
                return False
            
            print("✅ 벡터 검색 활성화됨\n")
            
            # 테스트 쿼리들
            test_cases = [
                {
                    "claim": "연회비는 국내전용 10,000원입니다",
                    "product_code": "CRD-CRE",
                    "category": "수수료",  # 카테고리 필터 있음
                    "category_none": None  # 카테고리 필터 없음
                },
                {
                    "claim": "일시불은 무이자입니다",
                    "product_code": "CRD-CRE",
                    "category": "이자율",  # 카테고리 필터 있음
                    "category_none": None  # 카테고리 필터 없음
                },
                {
                    "claim": "정기예금 금리는 연 2.5%입니다",
                    "product_code": "DEP-TIM",
                    "category": "금리",  # 카테고리 필터 있음
                    "category_none": None  # 카테고리 필터 없음
                },
            ]
            
            for test_case in test_cases:
                claim = test_case["claim"]
                product_code = test_case["product_code"]
                category = test_case["category"]
                
                print(f"📝 테스트 쿼리: {claim}")
                print(f"   상품 코드: {product_code}\n")
                
                # 1. 카테고리 필터 있음
                print("   [1] 카테고리 필터 있음:")
                results_with_category = product_service.search_by_vector_similarity(
                    query=claim,
                    category=category,
                    product_codes=[product_code],
                    top_k=3,
                    similarity_threshold=0.5
                )
                
                if results_with_category:
                    print(f"      ✅ 검색 결과: {len(results_with_category)}개")
                    for i, r in enumerate(results_with_category[:2], 1):
                        print(f"         {i}. [{r.get('product_code')}] {r.get('subsection_title', 'N/A')[:40]}")
                        print(f"            유사도: {r.get('similarity', 0):.3f}")
                else:
                    print(f"      ❌ 검색 결과 없음")
                
                # 2. 카테고리 필터 없음 (전체 상품)
                print("\n   [2] 카테고리 필터 없음 (전체 상품):")
                results_without_category = product_service.search_by_vector_similarity(
                    query=claim,
                    category=None,  # 카테고리 필터 제거
                    product_codes=[product_code],
                    top_k=3,
                    similarity_threshold=0.5
                )
                
                if results_without_category:
                    print(f"      ✅ 검색 결과: {len(results_without_category)}개")
                    for i, r in enumerate(results_without_category[:2], 1):
                        print(f"         {i}. [{r.get('product_code')}] {r.get('subsection_title', 'N/A')[:40]}")
                        print(f"            유사도: {r.get('similarity', 0):.3f}")
                else:
                    print(f"      ❌ 검색 결과 없음")
                
                # 비교
                print("\n   📊 비교:")
                if results_with_category and results_without_category:
                    top_with = results_with_category[0]
                    top_without = results_without_category[0]
                    same_result = (top_with.get('subsection_title') == top_without.get('subsection_title'))
                    print(f"      - 카테고리 필터: {len(results_with_category)}개 결과")
                    print(f"      - 필터 없음: {len(results_without_category)}개 결과")
                    print(f"      - 최상위 결과 동일: {'✅ 예' if same_result else '❌ 아니오'}")
                    if not same_result:
                        print(f"        필터 있음: {top_with.get('subsection_title', 'N/A')}")
                        print(f"        필터 없음: {top_without.get('subsection_title', 'N/A')}")
                elif not results_with_category and results_without_category:
                    print(f"      ✅ 필터 없음이 더 많은 결과 발견: {len(results_without_category)}개")
                elif results_with_category and not results_without_category:
                    print(f"      ⚠️ 필터 있음만 결과 발견: {len(results_with_category)}개")
                else:
                    print(f"      ❌ 둘 다 결과 없음")
                
                print("\n" + "="*60 + "\n")
            
            print("✅ 테스트 완료!")
            return True
            
        except Exception as e:
            print(f"❌ 오류 발생: {e}")
            import traceback
            traceback.print_exc()
            return False


if __name__ == "__main__":
    success = test_without_category_filter()
    sys.exit(0 if success else 1)

