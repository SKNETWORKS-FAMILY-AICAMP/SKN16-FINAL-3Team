#!/usr/bin/env python3
"""
시뮬레이션 평가 로직 테스트
실제 시뮬레이션 완료 후 평가가 제대로 작동하는지 확인
"""
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from app.services.product_knowledge_service import ProductKnowledgeService


def test_evaluation_logic():
    """시뮬레이션 평가 로직 테스트 (제품 지식 검증 부분)"""
    print("=" * 80)
    print("🧪 시뮬레이션 평가 로직 테스트")
    print("=" * 80)
    
    # 제품 지식 서비스 초기화
    print("\n📦 서비스 초기화 중...")
    product_service = ProductKnowledgeService(use_llm=True)
    
    print(f"✅ 제품 지식 서비스: 활성화")
    print(f"   - 임베딩 사용: {product_service.use_embedding}")
    print(f"   - LLM 사용: {product_service.use_llm}")
    
    # 테스트 대화 (실제 시뮬레이션과 유사한 형태)
    test_conversation = [
        {"role": "customer", "text": "정기예금 상품에 대해 알려주세요."},
        {
            "role": "employee", 
            "text": "안녕하세요! 하경은행 정기예금은 최소 50만원부터 가입 가능하며, 12개월 기본금리는 연 2.15%입니다."
        },
        {"role": "customer", "text": "우대금리는 어떻게 되나요?"},
        {
            "role": "employee",
            "text": "우대금리는 최대 0.5%p 추가됩니다. 따라서 12개월 최고금리는 2.65%입니다."
        },
        {"role": "customer", "text": "감사합니다."},
    ]
    
    # 페르소나와 상황 (간단한 테스트용)
    test_persona = {
        "id": "test_persona",
        "type": "긍정형",
        "financial_literacy": "보통",
        "age_group": "30대",
        "occupation": "직장인"
    }
    
    test_situation = {
        "id": "test_situation",
        "title": "정기예금 상품 문의",
        "category": "수신",
        "goals": [
            "정기예금 금리 정보 제공",
            "가입 조건 안내"
        ]
    }
    
    print("\n📝 테스트 대화:")
    for msg in test_conversation:
        role = "고객" if msg['role'] == 'customer' else "직원"
        print(f"   {role}: {msg['text']}")
    
    print("\n🔍 제품 지식 검증 테스트...")
    try:
        # 제품 지식 검증 실행 (종합 평가에서 사용하는 부분)
        verification_result = product_service.batch_verify_conversation(
            test_conversation,
            use_llm=True
        )
        
        print("\n📊 제품 지식 검증 결과:")
        print(f"   총 주장 수: {verification_result['total_claims']}")
        print(f"   정확한 주장: {verification_result['accurate_claims']}")
        print(f"   부정확한 주장: {verification_result['inaccurate_claims']}")
        print(f"   정확도: {verification_result['accuracy_rate']:.1%}")
        print(f"   검증 방법: {verification_result.get('verification_methods', {})}")
        
        # 상세 검증 결과
        if verification_result.get('verifications'):
            print(f"\n📋 상세 검증 결과 (상위 3개):")
            for j, v in enumerate(verification_result['verifications'][:3], 1):
                status = "✅" if v.is_accurate else "❌"
                print(f"   {j}. {status} '{v.claim}'")
                print(f"      검증 방법: {v.verification_method}")
                print(f"      유사도: {v.similarity_score:.3f}")
                if v.ground_truth:
                    print(f"      찾은 정답: {v.ground_truth[:80]}...")
                if v.llm_reasoning:
                    print(f"      LLM reasoning: {v.llm_reasoning[:100]}...")
        
        # 지식 점수 계산 (정확도 기반)
        knowledge_score = int(verification_result['accuracy_rate'] * 100)
        print(f"\n💡 지식 점수 계산:")
        print(f"   정확도 {verification_result['accuracy_rate']:.1%} → {knowledge_score}점")
        
        print("\n✅ 검증 완료!")
        return verification_result
        
    except Exception as e:
        print(f"\n❌ 검증 실패: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    try:
        test_evaluation_logic()
        
        print("\n" + "=" * 80)
        print("✅ 테스트 완료!")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ 테스트 실행 중 오류: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

