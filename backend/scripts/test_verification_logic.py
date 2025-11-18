#!/usr/bin/env python3
"""
제품 지식 검증 로직 테스트 스크립트
- 임베딩 기반 Semantic 유사도
- 숫자 정확도 비교
- LLM reasoning
"""
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from app.services.product_knowledge_service import ProductKnowledgeService


def test_verification_logic():
    """제품 지식 검증 로직 종합 테스트 (실제 대화 기반)"""
    print("=" * 80)
    print("🧪 제품 지식 검증 로직 테스트 (실제 대화 기반)")
    print("=" * 80)
    
    # 서비스 초기화 (LLM 활성화)
    print("\n📦 서비스 초기화 중...")
    service = ProductKnowledgeService(use_llm=True)
    
    print(f"✅ 임베딩 사용: {service.use_embedding}")
    print(f"✅ LLM 사용: {service.use_llm}")
    
    # 실제 대화 기반 테스트 케이스
    test_conversations = [
        {
            "name": "테스트 1: 정확한 정보 제공",
            "conversation": [
                {"role": "customer", "text": "정기예금 12개월 금리가 어떻게 되나요?"},
                {"role": "employee", "text": "정기예금 12개월 기본금리는 연 2.15%입니다. 최소 50만원부터 가입 가능합니다."},
            ],
            "expected_accuracy_rate": 1.0,  # 100% 정확
            "description": "실제 데이터와 일치하는 정확한 정보"
        },
        {
            "name": "테스트 2: 잘못된 정보 제공",
            "conversation": [
                {"role": "customer", "text": "정기예금 12개월 금리가 어떻게 되나요?"},
                {"role": "employee", "text": "정기예금 12개월 기본금리는 연 3.5%입니다. 최소 10만원부터 가입 가능합니다."},
            ],
            "expected_accuracy_rate": 0.0,  # 0% 정확 (모두 오류)
            "description": "실제 데이터와 다른 잘못된 정보"
        },
        {
            "name": "테스트 3: 부분적으로 정확한 정보",
            "conversation": [
                {"role": "customer", "text": "정기예금에 대해 알려주세요."},
                {"role": "employee", "text": "정기예금 12개월 기본금리는 연 2.15%입니다. 최소 10만원부터 가입 가능합니다."},
            ],
            "expected_accuracy_rate": 0.5,  # 50% 정확 (금리는 맞지만 가입금액은 틀림)
            "description": "일부는 정확하고 일부는 부정확"
        },
        {
            "name": "테스트 4: 우대금리 정보 포함",
            "conversation": [
                {"role": "customer", "text": "우대금리는 어떻게 되나요?"},
                {"role": "employee", "text": "우대금리는 최대 0.5%p 추가됩니다. 따라서 12개월 최고금리는 2.65%입니다."},
            ],
            "expected_accuracy_rate": 1.0,  # 100% 정확
            "description": "우대금리 및 최고금리 정보"
        },
    ]
    
    # 각 테스트 케이스 실행
    results = []
    for i, test_case in enumerate(test_conversations, 1):
        print(f"\n{'='*80}")
        print(f"📋 {test_case['name']}")
        print(f"   설명: {test_case['description']}")
        print(f"{'='*80}")
        
        try:
            # 대화 전체 검증 실행
            verification_result = service.batch_verify_conversation(
                test_case['conversation'],
                use_llm=service.use_llm
            )
            
            # 결과 출력
            print(f"\n📝 테스트 대화:")
            for msg in test_case['conversation']:
                role = "고객" if msg['role'] == 'customer' else "직원"
                print(f"   {role}: {msg['text']}")
            
            print(f"\n📊 검증 결과:")
            print(f"   총 주장 수: {verification_result['total_claims']}")
            print(f"   정확한 주장: {verification_result['accurate_claims']}")
            print(f"   부정확한 주장: {verification_result['inaccurate_claims']}")
            print(f"   정확도: {verification_result['accuracy_rate']:.1%}")
            print(f"   검증 방법: {verification_result.get('verification_methods', {})}")
            
            # 추출된 사실 확인
            if verification_result.get('facts'):
                print(f"\n📋 추출된 사실:")
                for j, fact in enumerate(verification_result['facts'][:3], 1):
                    print(f"   {j}. '{fact['claim']}'")
                    print(f"      제품: {fact.get('product_codes', [])}")
                    print(f"      카테고리: {fact.get('category', '')}")
            
            # 상세 검증 결과
            if verification_result.get('verifications'):
                print(f"\n📋 상세 검증 결과:")
                for j, v in enumerate(verification_result['verifications'][:3], 1):
                    status = "✅" if v.is_accurate else "❌"
                    print(f"   {j}. {status} '{v.claim}'")
                    print(f"      검증 방법: {v.verification_method}")
                    print(f"      유사도: {v.similarity_score:.3f}")
                    if v.ground_truth:
                        print(f"      찾은 정답: {v.ground_truth[:80]}...")
                    if v.llm_reasoning:
                        print(f"      LLM reasoning: {v.llm_reasoning[:100]}...")
            
            # 예상 결과와 비교 (정확도가 예상 범위 내인지 확인)
            actual_rate = verification_result['accuracy_rate']
            expected_rate = test_case['expected_accuracy_rate']
            tolerance = 0.1  # 10% 허용 오차
            
            is_correct = abs(actual_rate - expected_rate) <= tolerance
            status = "✅ 통과" if is_correct else "❌ 실패"
            print(f"\n{status} (예상 정확도: {expected_rate:.0%}, 실제: {actual_rate:.1%})")
            
            results.append({
                "test": test_case['name'],
                "passed": is_correct,
                "result": verification_result
            })
            
        except Exception as e:
            print(f"❌ 오류 발생: {e}")
            import traceback
            traceback.print_exc()
            results.append({
                "test": test_case['name'],
                "passed": False,
                "error": str(e)
            })
    
    # 전체 결과 요약
    print(f"\n{'='*80}")
    print("📊 테스트 결과 요약")
    print(f"{'='*80}")
    
    passed = sum(1 for r in results if r.get('passed', False))
    total = len(results)
    
    for r in results:
        status = "✅" if r.get('passed', False) else "❌"
        print(f"{status} {r['test']}")
        if 'error' in r:
            print(f"   오류: {r['error']}")
        elif 'result' in r:
            result = r['result']
            print(f"   정확도: {result['accuracy_rate']:.1%} ({result['accurate_claims']}/{result['total_claims']})")
    
    print(f"\n총 {total}개 테스트 중 {passed}개 통과 ({passed/total*100:.1f}%)")
    
    return results


def test_batch_verification():
    """대화 전체 검증 테스트"""
    print("\n" + "=" * 80)
    print("🧪 대화 전체 검증 테스트")
    print("=" * 80)
    
    service = ProductKnowledgeService(use_llm=True)
    
    # 테스트 대화 (직원 발화에 제품 정보 포함 - 실제 데이터 기반)
    test_conversation = [
        {"role": "customer", "text": "정기예금 상품에 대해 알려주세요."},
        {
            "role": "employee", 
            "text": "정기예금 12개월 기본금리는 연 2.15%입니다. 최소 50만원부터 가입 가능하며, 만기 12개월입니다."
        },
        {"role": "customer", "text": "우대금리는 어떻게 되나요?"},
        {
            "role": "employee",
            "text": "우대금리는 최대 0.5%p 추가됩니다. 따라서 12개월 최고금리는 2.65%입니다."
        },
        {"role": "customer", "text": "감사합니다."},
    ]
    
    print("\n📝 테스트 대화:")
    for msg in test_conversation:
        role = "고객" if msg['role'] == 'customer' else "직원"
        print(f"   {role}: {msg['text']}")
    
    print("\n🔍 검증 시작...")
    result = service.batch_verify_conversation(test_conversation, use_llm=True)
    
    print(f"\n📊 검증 결과:")
    print(f"   총 주장 수: {result['total_claims']}")
    print(f"   정확한 주장: {result['accurate_claims']}")
    print(f"   부정확한 주장: {result['inaccurate_claims']}")
    print(f"   정확도: {result['accuracy_rate']:.1%}")
    print(f"   검증 방법: {result.get('verification_methods', {})}")
    
    print(f"\n📋 상세 검증 결과:")
    for i, v in enumerate(result.get('verifications', [])[:5], 1):
        status = "✅" if v.is_accurate else "❌"
        print(f"\n   {i}. {status} '{v.claim}'")
        print(f"      검증 방법: {v.verification_method}")
        print(f"      유사도: {v.similarity_score:.3f}")
        if v.llm_reasoning:
            print(f"      LLM reasoning: {v.llm_reasoning[:100]}...")
    
    return result


if __name__ == "__main__":
    try:
        # 개별 검증 테스트
        test_verification_logic()
        
        # 대화 전체 검증 테스트
        test_batch_verification()
        
        print("\n" + "=" * 80)
        print("✅ 모든 테스트 완료!")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ 테스트 실행 중 오류: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

