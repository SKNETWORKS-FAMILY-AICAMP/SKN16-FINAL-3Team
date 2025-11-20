#!/usr/bin/env python3
"""
실제 시뮬레이션에서 벡터 검색이 작동하는지 테스트
RAGSimulationService가 사용하는 방식과 동일하게 테스트
"""
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from sqlmodel import Session
from app.database import engine
from app.services.product_knowledge_service import ProductKnowledgeService


def test_simulation_vector_search():
    """시뮬레이션에서 사용하는 방식으로 벡터 검색 테스트"""
    print("🔍 시뮬레이션 벡터 검색 테스트 시작...\n")
    print("📋 테스트 방식: RAGSimulationService가 사용하는 search_by_keyword() 방식\n")
    
    with Session(engine) as session:
        try:
            # ProductKnowledgeService 초기화 (시뮬레이션과 동일)
            product_service = ProductKnowledgeService(
                use_llm=True,
                session=session  # 벡터 검색 활성화
            )
            
            if not product_service.use_vector_search:
                print("❌ 벡터 검색이 비활성화되어 있습니다.")
                return False
            
            print("✅ 벡터 검색 활성화됨\n")
            
            # 시뮬레이션에서 실제로 사용될 수 있는 쿼리들
            test_queries = [
                {
                    "query": "연회비는 얼마인가요?",
                    "product_code": "CRD-CRE",
                    "category": None
                },
                {
                    "query": "정기예금 금리는 어떻게 되나요?",
                    "product_code": "DEP-TIM",
                    "category": "금리"
                },
                {
                    "query": "대출 한도는 얼마까지 가능한가요?",
                    "product_code": "LON-MTG",
                    "category": "한도"
                },
                {
                    "query": "적금 만기 기간은?",
                    "product_code": "SAV-FIX",
                    "category": "기간"
                },
            ]
            
            for test_case in test_queries:
                query = test_case["query"]
                product_code = test_case["product_code"]
                category = test_case["category"]
                
                print(f"📝 테스트 쿼리: {query}")
                print(f"   상품 코드: {product_code}")
                if category:
                    print(f"   카테고리: {category}")
                
                # 시뮬레이션에서 사용하는 방식: search_by_keyword()
                # 이 함수는 내부적으로 벡터 검색을 먼저 시도함
                results = product_service.search_by_keyword(
                    query=query,
                    category=category,
                    product_codes=[product_code],
                    top_k=3
                )
                
                if results:
                    print(f"   ✅ 검색 결과: {len(results)}개")
                    for i, result in enumerate(results[:3], 1):
                        similarity = result.get('similarity', 0)
                        product_code_result = result.get('product_code', 'N/A')
                        subsection = result.get('subsection_title', 'N/A')
                        content_text = result.get('text', '') or result.get('content', '')
                        content_preview = content_text[:80] if content_text else ''
                        
                        print(f"      {i}. [{product_code_result}] {subsection}")
                        print(f"         유사도: {similarity:.3f}")
                        print(f"         내용: {content_preview}...")
                else:
                    print(f"   ⚠️ 검색 결과 없음")
                
                print()
            
            print("✅ 시뮬레이션 벡터 검색 테스트 완료!")
            print("\n💡 참고:")
            print("   - search_by_keyword()는 내부적으로 벡터 검색을 먼저 시도합니다")
            print("   - 벡터 검색 실패 시 키워드 검색으로 자동 fallback됩니다")
            print("   - 실제 시뮬레이션에서도 동일한 방식으로 작동합니다")
            
            return True
            
        except Exception as e:
            print(f"❌ 오류 발생: {e}")
            import traceback
            traceback.print_exc()
            return False


if __name__ == "__main__":
    success = test_simulation_vector_search()
    sys.exit(0 if success else 1)

