#!/usr/bin/env python3
"""
벡터 검색 테스트 스크립트
상품 데이터 벡터 검색이 제대로 작동하는지 확인
"""
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from sqlmodel import Session
from app.database import engine
from app.services.product_knowledge_service import ProductKnowledgeService


def test_vector_search(save_to_file: bool = True):
    """벡터 검색 테스트"""
    print("🔍 벡터 검색 테스트 시작...\n")
    
    # 결과 저장용
    results_summary = []
    
    with Session(engine) as session:
        try:
            # ProductKnowledgeService 초기화
            product_service = ProductKnowledgeService(
                use_llm=True,
                session=session
            )
            
            if not product_service.use_vector_search:
                print("❌ 벡터 검색이 비활성화되어 있습니다.")
                return False
            
            print("✅ 벡터 검색 활성화됨\n")
            
            # 테스트 쿼리들
            test_queries = [
                ("연회비는 얼마인가요?", ["CRD-CRE"]),
                ("정기예금 금리는?", ["DEP-TIM"]),
                ("대출 한도는 얼마까지 가능한가요?", ["LON-MTG"]),
                ("적금 만기 기간은?", ["SAV-FIX"]),
            ]
            
            for query, product_codes in test_queries:
                print(f"📝 테스트 쿼리: {query}")
                print(f"   상품 코드: {product_codes}")
                
                # 벡터 검색 실행
                results = product_service.search_by_vector_similarity(
                    query=query,
                    product_codes=product_codes,
                    top_k=3,
                    similarity_threshold=0.5
                )
                
                query_result = {
                    "query": query,
                    "product_codes": product_codes,
                    "result_count": len(results),
                    "results": []
                }
                
                if results:
                    print(f"   ✅ 검색 결과: {len(results)}개")
                    for i, result in enumerate(results[:3], 1):
                        similarity = result.get('similarity', 0)
                        product_code = result.get('product_code', 'N/A')
                        subsection = result.get('subsection_title', 'N/A')
                        # search_by_vector_similarity는 'text' 키를 반환함
                        content_text = result.get('text', '') or result.get('content', '')
                        content_preview = content_text[:100] if content_text else ''
                        print(f"      {i}. [{product_code}] {subsection}")
                        print(f"         유사도: {similarity:.3f}")
                        print(f"         내용: {content_preview}...")
                        
                        query_result["results"].append({
                            "rank": i,
                            "product_code": product_code,
                            "subsection_title": subsection,
                            "similarity": round(similarity, 3),
                            "content_preview": content_preview,
                            "content_full": content_text  # 전체 내용도 저장
                        })
                else:
                    print(f"   ⚠️ 검색 결과 없음 (임계값 조정 필요할 수 있음)")
                
                results_summary.append(query_result)
                print()
            
            print("✅ 벡터 검색 테스트 완료!")
            
            # 결과를 파일로 저장
            if save_to_file:
                import json
                from datetime import datetime
                output_file = project_root / "scripts" / f"vector_search_test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump({
                        "test_date": datetime.now().isoformat(),
                        "total_queries": len(test_queries),
                        "results": results_summary
                    }, f, ensure_ascii=False, indent=2)
                print(f"\n📄 결과 파일 저장: {output_file}")
            
            return True
            
        except Exception as e:
            print(f"❌ 오류 발생: {e}")
            import traceback
            traceback.print_exc()
            return False


if __name__ == "__main__":
    success = test_vector_search()
    sys.exit(0 if success else 1)

