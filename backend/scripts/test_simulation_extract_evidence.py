#!/usr/bin/env python3
"""
시뮬레이션의 _extract_product_evidence 메서드 테스트
벡터 검색 우선 + 키워드 fallback이 잘 동작하는지 확인
"""
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from sqlmodel import Session
from app.database import engine
from app.services.rag_simulation_service import RAGSimulationService


def test_extract_product_evidence():
    """시뮬레이션의 _extract_product_evidence 메서드 테스트"""
    print("🔍 시뮬레이션 _extract_product_evidence 테스트 시작...\n")
    print("📋 테스트 방식: 벡터 검색 우선, 실패 시 키워드 fallback\n")
    
    with Session(engine) as session:
        try:
            # RAGSimulationService 초기화
            simulation_service = RAGSimulationService(session=session)
            
            if not simulation_service.product_knowledge_service:
                print("❌ ProductKnowledgeService가 초기화되지 않았습니다.")
                return False
            
            if not simulation_service.product_knowledge_service.use_vector_search:
                print("⚠️ 벡터 검색이 비활성화되어 있습니다. 키워드 fallback만 사용됩니다.")
            else:
                print("✅ 벡터 검색 활성화됨\n")
            
            # 테스트 케이스: 상품별 다양한 발화
            test_cases = [
                {
                    "name": "정확한 상품 정보 발화 (벡터 검색 성공 예상)",
                    "product_code": "CRD-CRE",
                    "text": "프리미엄 신용카드 연회비는 국내전용 10,000원, 해외겸용 15,000원입니다. 일시불은 무이자이고 할부는 연 5.9%부터 시작합니다.",
                    "expected_method": "vector"
                },
                {
                    "name": "정기예금 금리 정보 (벡터 검색 성공 예상)",
                    "product_code": "DEP-TIM",
                    "text": "정기예금 금리는 가입 당시 은행이 고시한 금리를 연 단위로 계산합니다. 중도해지 시에는 예치기간에 따라 다른 금리가 적용됩니다.",
                    "expected_method": "vector"
                },
                {
                    "name": "대출 한도 정보 (벡터 검색 성공 예상)",
                    "product_code": "LON-MTG",
                    "text": "주택담보대출 한도는 최소 3,000만원부터 최대 10억원까지 가능하며, LTV 기준으로 일반지역은 60%까지 가능합니다.",
                    "expected_method": "vector"
                },
                {
                    "name": "존재하지 않는 상품 코드 (키워드 fallback 예상)",
                    "product_code": "INVALID-PRODUCT",
                    "text": "이 상품의 금리는 연 5%입니다.",
                    "expected_method": "keyword_fallback"
                },
                {
                    "name": "매우 짧은 발화 (벡터 검색 실패 시 키워드 fallback 예상)",
                    "product_code": "CRD-CRE",
                    "text": "연회비",
                    "expected_method": "vector_or_keyword"
                }
            ]
            
            # 🆕 두 상품을 비교하거나 동시에 언급하는 케이스
            multi_product_cases = [
                {
                    "name": "정기예금 vs 자유적금 비교",
                    "text": "정기예금과 자유적금의 차이를 설명해드리면, 정기예금은 일정 기간 동안 예치하여 높은 금리를 받는 상품이고, 자유적금은 매월 일정 금액을 납입하여 목돈을 만드는 상품입니다. 정기예금은 만기까지 출금이 어렵지만 자유적금은 자유롭게 입출금이 가능합니다.",
                    "primary_product": "DEP-TIM",
                    "secondary_product": "SAV-FRE"
                },
                {
                    "name": "신용카드와 체크카드 비교",
                    "text": "신용카드와 체크카드를 비교해드리면, 신용카드는 한도 내에서 선 결제 후 나중에 상환하는 방식이고, 체크카드는 계좌 잔액 내에서 즉시 결제되는 방식입니다. 신용카드는 연회비가 있지만 체크카드는 연회비가 없습니다.",
                    "primary_product": "CRD-CRE",
                    "secondary_product": "CRD-DEB"
                },
                {
                    "name": "여러 상품 동시 설명 (정기예금 + 주택담보대출)",
                    "text": "정기예금 금리는 가입 당시 은행이 고시한 금리를 연 단위로 계산하며, 중도해지 시에는 예치기간에 따라 다른 금리가 적용됩니다. 주택담보대출은 한도가 최소 3,000만원부터 최대 10억원까지 가능하고 LTV 기준으로 일반지역은 60%까지 가능합니다.",
                    "primary_product": "DEP-TIM",
                    "secondary_product": "LON-MTG"
                }
            ]
            
            for test_case in test_cases:
                print(f"📝 테스트 케이스: {test_case['name']}")
                print(f"   상품 코드: {test_case['product_code']}")
                print(f"   발화: {test_case['text'][:80]}...")
                
                # 상품 데이터 로드
                product_data = simulation_service._load_product_data(test_case['product_code'])
                
                # _extract_product_evidence 실행
                evidence = simulation_service._extract_product_evidence(
                    product_code=test_case['product_code'],
                    text=test_case['text'],
                    product_data=product_data
                )
                
                # 결과 분석
                print(f"\n   📊 검색 결과:")
                print(f"      - 매칭된 청크: {len(evidence.get('matched_chunks', []))}개")
                
                if evidence.get('similarity_scores'):
                    avg_similarity = sum(evidence['similarity_scores']) / len(evidence['similarity_scores'])
                    print(f"      - 평균 유사도: {avg_similarity:.3f}")
                    print(f"      - 사용 방법: ✅ 벡터 검색")
                    
                    # Top 3 결과 출력
                    for i, chunk in enumerate(evidence['matched_chunks'][:3], 1):
                        similarity = chunk.get('similarity', 0)
                        subsection = chunk.get('subsection_title', 'N/A')
                        print(f"        {i}. [{similarity:.3f}] {subsection}")
                        print(f"           {chunk.get('text', '')[:60]}...")
                else:
                    # 벡터 검색 실패 시 키워드 fallback 결과
                    if evidence.get('matched_chunks'):
                        print(f"      - 사용 방법: ⚠️ 키워드 매칭 (fallback)")
                        for i, chunk in enumerate(evidence['matched_chunks'][:3], 1):
                            subsection = chunk.get('subsection_title', 'N/A')
                            print(f"        {i}. {subsection}")
                            print(f"           {chunk.get('text', '')[:60]}...")
                    else:
                        print(f"      - 사용 방법: ❌ 검색 실패 (벡터 검색 + 키워드 fallback 모두 실패)")
                
                # 키워드 정보
                if evidence.get('key_information'):
                    print(f"      - 발견된 키워드: {', '.join(evidence['key_information'][:5])}")
                if evidence.get('missing_information'):
                    print(f"      - 누락된 키워드: {', '.join(evidence['missing_information'][:5])}")
                
                print()
            
            # 🆕 두 상품 비교 테스트
            print("\n" + "="*80)
            print("🔄 두 상품을 비교하거나 동시에 언급하는 케이스 테스트")
            print("="*80 + "\n")
            
            for multi_case in multi_product_cases:
                print(f"📝 테스트 케이스: {multi_case['name']}")
                print(f"   발화: {multi_case['text'][:100]}...")
                print(f"   주요 상품: {multi_case['primary_product']} / 비교 상품: {multi_case['secondary_product']}\n")
                
                # 1. 자동으로 여러 상품 추출 테스트
                print("   🔍 1단계: 자동 상품 추출 (extract_product_facts_from_conversation)")
                conversation = [{"role": "employee", "text": multi_case['text']}]
                facts = simulation_service.product_knowledge_service.extract_product_facts_from_conversation(conversation)
                
                extracted_product_codes = set()
                for fact in facts:
                    product_codes = fact.get("product_codes", [])
                    extracted_product_codes.update(product_codes)
                    print(f"      - 추출된 주장: {fact.get('claim', '')[:60]}...")
                    print(f"      - 상품 코드: {product_codes}")
                
                print(f"\n   📊 추출된 상품 코드: {list(extracted_product_codes)}")
                
                # 2. 각 상품에 대해 개별적으로 evidence 추출
                print(f"\n   🔍 2단계: 각 상품별 벡터 검색 수행")
                for product_code in [multi_case['primary_product'], multi_case['secondary_product']]:
                    print(f"\n      📦 상품: {product_code}")
                    product_data = simulation_service._load_product_data(product_code)
                    
                    evidence = simulation_service._extract_product_evidence(
                        product_code=product_code,
                        text=multi_case['text'],
                        product_data=product_data
                    )
                    
                    if evidence.get('similarity_scores'):
                        avg_similarity = sum(evidence['similarity_scores']) / len(evidence['similarity_scores'])
                        print(f"         ✅ 벡터 검색: {len(evidence['matched_chunks'])}개 청크 (평균 유사도: {avg_similarity:.3f})")
                        
                        # Top 3 결과 상세 출력
                        print(f"         📋 매칭된 청크 상세:")
                        for i, chunk in enumerate(evidence['matched_chunks'][:3], 1):
                            similarity = chunk.get('similarity', 0)
                            subsection = chunk.get('subsection_title', 'N/A')
                            chunk_text = chunk.get('text', '')[:80]
                            print(f"            {i}. [{similarity:.3f}] {subsection}")
                            print(f"               내용: {chunk_text}...")
                    elif evidence.get('matched_chunks'):
                        print(f"         ⚠️ 키워드 매칭 (fallback): {len(evidence['matched_chunks'])}개 청크")
                        for i, chunk in enumerate(evidence['matched_chunks'][:3], 1):
                            subsection = chunk.get('subsection_title', 'N/A')
                            chunk_text = chunk.get('text', '')[:60]
                            print(f"            {i}. {subsection}: {chunk_text}...")
                    else:
                        print(f"         ❌ 검색 실패")
                
                print()
            
            print("✅ 시뮬레이션 _extract_product_evidence 테스트 완료!\n")
            print("💡 참고:")
            print("   - 벡터 검색을 우선적으로 시도합니다")
            print("   - 벡터 검색 결과가 없거나 실패하면 키워드 매칭으로 자동 fallback됩니다")
            print("   - 두 상품을 비교하는 발화는 각 상품별로 개별적으로 검색이 수행됩니다")
            print("   - 실제 시뮬레이션 평가에서도 동일한 방식으로 작동합니다")
            
            return True
            
        except Exception as e:
            print(f"❌ 오류 발생: {e}")
            import traceback
            traceback.print_exc()
            return False


if __name__ == "__main__":
    success = test_extract_product_evidence()
    sys.exit(0 if success else 1)

