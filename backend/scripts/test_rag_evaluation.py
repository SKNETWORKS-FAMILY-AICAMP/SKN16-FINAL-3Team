#!/usr/bin/env python3
"""
RAG 기반 지식 역량 평가 테스트
벡터 검색을 사용한 상품 정확성 평가가 제대로 작동하는지 확인
"""
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from sqlmodel import Session
from app.database import engine
from app.services.product_knowledge_service import ProductKnowledgeService


def test_rag_evaluation():
    """RAG 기반 지식 역량 평가 테스트"""
    print("🔍 RAG 기반 지식 역량 평가 테스트 시작...\n")
    print("📋 테스트: 시뮬레이션에서 사용하는 batch_verify_conversation() 방식\n")
    
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
            
            # 시뮬레이션 대화 예시 (직원 발화에 상품 정보 포함)
            test_conversations = [
                {
                    "name": "정확한 정보 제공",
                    "conversation": [
                        {"role": "employee", "text": "안녕하세요 무엇을 도와드릴까요"},
                        {"role": "customer", "text": "신용카드 발급 받고 싶어요"},
                        {"role": "employee", "text": "프리미엄 신용카드 연회비는 국내전용 10,000원, 해외겸용 15,000원입니다"},
                        {"role": "customer", "text": "이자율은 어떻게 되나요?"},
                        {"role": "employee", "text": "일시불은 무이자이고, 할부는 연 5.9%부터 시작합니다"}
                    ]
                },
                {
                    "name": "부정확한 정보 제공",
                    "conversation": [
                        {"role": "employee", "text": "안녕하세요 무엇을 도와드릴까요"},
                        {"role": "customer", "text": "정기예금 금리가 궁금해요"},
                        {"role": "employee", "text": "정기예금 금리는 연 5.0%입니다"},  # 잘못된 정보
                        {"role": "customer", "text": "만기 기간은?"},
                        {"role": "employee", "text": "6개월, 12개월, 24개월, 36개월 중 선택 가능합니다"}
                    ]
                }
            ]
            
            for test_case in test_conversations:
                print(f"📝 테스트 케이스: {test_case['name']}")
                print(f"   대화 턴 수: {len(test_case['conversation'])}개\n")
                
                # batch_verify_conversation 실행 (시뮬레이션과 동일)
                result = product_service.batch_verify_conversation(
                    conversation=test_case['conversation'],
                    use_llm=True
                )
                
                # 결과 출력
                print(f"   📊 검증 결과:")
                print(f"      - 총 주장 수: {result['total_claims']}개")
                print(f"      - 정확한 주장: {result['accurate_claims']}개")
                print(f"      - 부정확한 주장: {result['inaccurate_claims']}개")
                print(f"      - 정확도: {result['accuracy_rate']:.1%}")
                print(f"      - 검증 방법: {result['verification_methods']}")
                
                # 검증 방법별 통계
                vector_count = sum(
                    count for method, count in result['verification_methods'].items() 
                    if 'vector' in method
                )
                if vector_count > 0:
                    print(f"      ✅ 벡터 검색 사용: {vector_count}개")
                else:
                    print(f"      ⚠️ 벡터 검색 미사용 (키워드 검색만 사용)")
                
                # 상세 검증 결과
                if result['verifications']:
                    print(f"\n   📋 상세 검증 결과:")
                    for i, v in enumerate(result['verifications'][:3], 1):
                        status = "✅" if v.is_accurate else "❌"
                        method = v.verification_method
                        print(f"      {i}. {status} [{method}] {v.claim[:50]}...")
                        print(f"         유사도: {v.similarity_score:.3f}")
                        if not v.is_accurate:
                            print(f"         정답: {v.ground_truth[:60]}...")
                
                print()
            
            print("✅ RAG 기반 지식 역량 평가 테스트 완료!")
            print("\n💡 변경 사항:")
            print("   - verify_fact_accuracy()가 이제 벡터 검색을 우선 사용합니다")
            print("   - 벡터 검색 실패 시에만 키워드 검색으로 fallback합니다")
            print("   - verification_method에 'vector_semantic' 또는 'vector_keyword'가 표시됩니다")
            
            return True
            
        except Exception as e:
            print(f"❌ 오류 발생: {e}")
            import traceback
            traceback.print_exc()
            return False


if __name__ == "__main__":
    success = test_rag_evaluation()
    sys.exit(0 if success else 1)

