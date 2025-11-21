#!/usr/bin/env python3
"""
두 상품을 비교하는 발화에서 실제로 정확한 내용이 매칭되는지 확인
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from sqlmodel import Session
from app.database import engine
from app.services.rag_simulation_service import RAGSimulationService


def test_multi_product_accuracy():
    """두 상품 비교 발화의 정확한 매칭 확인"""
    print("🔍 두 상품 비교 발화의 정확도 테스트\n")
    
    with Session(engine) as session:
        simulation_service = RAGSimulationService(session=session)
        
        # 테스트 케이스: 정기예금 + 주택담보대출 동시 설명
        test_text = """정기예금 금리는 가입 당시 은행이 고시한 금리를 연 단위로 계산하며, 중도해지 시에는 예치기간에 따라 다른 금리가 적용됩니다. 
        주택담보대출은 한도가 최소 3,000만원부터 최대 10억원까지 가능하며, LTV 기준으로 일반지역은 60%까지 가능합니다."""
        
        print(f"📝 테스트 발화:")
        print(f"   {test_text}\n")
        print("="*80)
        
        # DEP-TIM (정기예금) 검색
        print("\n📦 1. DEP-TIM (정기예금) 검색 결과:")
        print("-"*80)
        product_data_dep = simulation_service._load_product_data("DEP-TIM")
        evidence_dep = simulation_service._extract_product_evidence(
            product_code="DEP-TIM",
            text=test_text,
            product_data=product_data_dep
        )
        
        print(f"\n✅ 매칭된 청크: {len(evidence_dep.get('matched_chunks', []))}개")
        if evidence_dep.get('matched_chunks'):
            print("\n📋 Top 3 결과:")
            for i, chunk in enumerate(evidence_dep['matched_chunks'][:3], 1):
                similarity = chunk.get('similarity', 0)
                subsection = chunk.get('subsection_title', 'N/A')
                chunk_text = chunk.get('text', '')
                print(f"\n   {i}. [{similarity:.3f}] {subsection}")
                print(f"      발화 내용: '정기예금 금리는 가입 당시 은행이 고시한 금리를 연 단위로 계산'")
                print(f"      매칭된 청크 내용: {chunk_text[:150]}...")
                
                # 정확도 확인
                relevant_keywords = ["금리", "고시", "연 단위", "중도해지", "예치기간"]
                found_in_chunk = [kw for kw in relevant_keywords if kw in chunk_text]
                print(f"      ✅ 관련 키워드 매칭: {', '.join(found_in_chunk)}")
        
        # LON-MTG (주택담보대출) 검색
        print("\n\n📦 2. LON-MTG (주택담보대출) 검색 결과:")
        print("-"*80)
        product_data_loan = simulation_service._load_product_data("LON-MTG")
        evidence_loan = simulation_service._extract_product_evidence(
            product_code="LON-MTG",
            text=test_text,
            product_data=product_data_loan
        )
        
        print(f"\n✅ 매칭된 청크: {len(evidence_loan.get('matched_chunks', []))}개")
        if evidence_loan.get('matched_chunks'):
            print("\n📋 Top 3 결과:")
            for i, chunk in enumerate(evidence_loan['matched_chunks'][:3], 1):
                similarity = chunk.get('similarity', 0)
                subsection = chunk.get('subsection_title', 'N/A')
                chunk_text = chunk.get('text', '')
                print(f"\n   {i}. [{similarity:.3f}] {subsection}")
                print(f"      발화 내용: '주택담보대출은 한도가 최소 3,000만원부터 최대 10억원까지 가능하며, LTV 기준으로 일반지역은 60%까지 가능'")
                print(f"      매칭된 청크 내용: {chunk_text[:150]}...")
                
                # 정확도 확인
                relevant_keywords = ["한도", "3,000만원", "10억원", "LTV", "60%", "일반지역"]
                found_in_chunk = [kw for kw in relevant_keywords if kw in chunk_text]
                print(f"      ✅ 관련 키워드 매칭: {', '.join(found_in_chunk)}")
        
        print("\n" + "="*80)
        print("💡 결론:")
        print("   - 각 상품별로 해당 상품과 관련된 내용만 높은 유사도로 매칭되는지 확인")
        print("   - 정기예금 검색 시: 금리, 중도해지 관련 내용이 나와야 함")
        print("   - 주택담보대출 검색 시: 한도, LTV 관련 내용이 나와야 함")
        print("   - 벡터 검색은 전체 발화를 query로 사용하지만, 각 상품의 청크만 검색하므로")
        print("     해당 상품과 관련된 내용만 매칭됩니다.")


if __name__ == "__main__":
    test_multi_product_accuracy()

