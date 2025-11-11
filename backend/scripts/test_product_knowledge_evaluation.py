#!/usr/bin/env python3
"""
제품 지식 기반 평가 시스템 테스트 스크립트
"""
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from app.services.product_knowledge_service import ProductKnowledgeService
from app.services.score_metrics import ScoreMetrics


def test_product_knowledge_service():
    """제품 지식 서비스 테스트 (LLM 비활성화)"""
    print("=" * 80)
    print("🧪 제품 지식 베이스 서비스 테스트")
    print("=" * 80)
    
    # LLM 없이 테스트 (키워드 + 의미 검증만)
    service = ProductKnowledgeService(use_llm=False)
    
    # 1. 제품 로드 확인
    print("\n1️⃣ 로드된 제품 목록:")
    for product_code in service.product_knowledge.keys():
        chunk_count = len(service.product_knowledge[product_code])
        print(f"   - {product_code}: {chunk_count}개 청크")
    
    # 2. 키워드 검색 테스트
    print("\n2️⃣ 키워드 검색 테스트:")
    test_queries = [
        ("정기예금 금리", ["DEP-TIM"]),
        ("신용카드 혜택", ["CRD-CRE"]),
        ("주택담보대출 한도", ["LON-MTG"]),
    ]
    
    for query, expected_products in test_queries:
        print(f"\n   쿼리: '{query}'")
        results = service.search_by_keyword(query, top_k=3)
        print(f"   결과: {len(results)}개 찾음")
        for chunk in results[:1]:  # 상위 1개만 출력
            print(f"      - [{chunk.get('product_code')}] {chunk.get('subsection_title')}")
            print(f"        {chunk.get('text', '')[:80]}...")
    
    # 3. 대화에서 사실 추출 테스트
    print("\n3️⃣ 대화에서 사실 추출 테스트:")
    test_conversation = [
        {"role": "customer", "text": "정기예금 상품에 대해 알려주세요."},
        {"role": "employee", "text": "안녕하세요! 하경은행 정기예금은 금리가 연 2.5%이며, 최소 50만원부터 가입 가능합니다."},
        {"role": "customer", "text": "기간은 어떻게 되나요?"},
        {"role": "employee", "text": "가입 기간은 1개월부터 36개월까지 선택하실 수 있습니다. 12개월이 가장 인기가 많습니다."},
    ]
    
    facts = service.extract_product_facts_from_conversation(test_conversation)
    print(f"   추출된 사실: {len(facts)}개")
    for i, fact in enumerate(facts, 1):
        print(f"\n   [{i}] {fact['claim']}")
        print(f"       - 제품: {', '.join(fact['product_codes'])}")
        print(f"       - 카테고리: {fact['category']}")
        if fact['matched_value']:
            print(f"       - 값: {fact['matched_value']}")
    
    # 4. 사실 검증 테스트
    print("\n4️⃣ 사실 검증 테스트:")
    test_claims = [
        ("금리는 연 2.5%입니다", "DEP-TIM", "금리"),
        ("최소 50만원부터 가입 가능합니다", "DEP-TIM", "한도"),
        ("주택담보대출 한도는 최대 10억원입니다", "LON-MTG", "한도"),
    ]
    
    for claim, product_code, category in test_claims:
        print(f"\n   검증: '{claim}'")
        result = service.verify_fact_accuracy(claim, product_code, category)
        print(f"   - 정확도: {'✅ 정확' if result.is_accurate else '❌ 부정확'}")
        print(f"   - 유사도: {result.similarity_score:.2f}")
        if result.ground_truth:
            print(f"   - 근거: {result.ground_truth[:100]}...")
    
    # 5. 대화 전체 검증 테스트 (Semantic)
    print("\n5️⃣ 대화 전체 검증 테스트 (Semantic):")
    verification = service.batch_verify_conversation(test_conversation, use_llm=False)
    print(f"   - 총 주장: {verification['total_claims']}개")
    print(f"   - 정확한 주장: {verification['accurate_claims']}개")
    print(f"   - 부정확한 주장: {verification['inaccurate_claims']}개")
    print(f"   - 정확도: {verification['accuracy_rate']:.1%}")
    print(f"   - 검증 방법: {verification.get('verification_methods', {})}")
    
    print("\n   카테고리별 정확도:")
    for category, stats in verification['details']['by_category'].items():
        print(f"      - {category}: {stats['accurate']}/{stats['total']} ({stats['accuracy_rate']:.1%})")


def test_llm_verification():
    """LLM 기반 검증 테스트"""
    print("\n" + "=" * 80)
    print("🤖 LLM 기반 검증 테스트")
    print("=" * 80)
    
    service = ProductKnowledgeService(use_llm=True)
    
    if not service.use_llm:
        print("⚠️ LLM 검증 비활성화 상태 - 테스트 스킵")
        return
    
    # 테스트 케이스
    test_cases = [
        {
            "claim": "정기예금 금리는 연 2.15%입니다",
            "product": "DEP-TIM",
            "category": "금리",
            "expected": True,
            "note": "정확한 정보 (12개월 기준)"
        },
        {
            "claim": "최소 50만원부터 가입할 수 있습니다",
            "product": "DEP-TIM",
            "category": "한도",
            "expected": True,
            "note": "정확한 정보"
        },
        {
            "claim": "금리가 10% 정도 되는 것 같아요",
            "product": "DEP-TIM",
            "category": "금리",
            "expected": False,
            "note": "불확실한 표현 + 잘못된 수치"
        },
        {
            "claim": "포인트가 1% 적립됩니다",
            "product": "CRD-CRE",
            "category": "혜택",
            "expected": True,
            "note": "신용카드 포인트 적립"
        },
    ]
    
    print("\n검증 결과:")
    for i, case in enumerate(test_cases, 1):
        print(f"\n  [{i}] {case['note']}")
        print(f"      주장: \"{case['claim']}\"")
        print(f"      제품: {case['product']}, 카테고리: {case['category']}")
        
        # LLM 검증
        result = service.verify_fact_accuracy(
            claim=case['claim'],
            product_code=case['product'],
            category=case['category'],
            use_llm=True
        )
        
        expected_icon = "✅" if case['expected'] else "❌"
        actual_icon = "✅" if result.is_accurate else "❌"
        match_icon = "🎯" if (result.is_accurate == case['expected']) else "⚠️"
        
        print(f"      예상: {expected_icon} | 실제: {actual_icon} | 일치: {match_icon}")
        print(f"      검증 방법: {result.verification_method}")
        print(f"      신뢰도: {result.similarity_score:.2f}")
        
        if result.llm_reasoning:
            print(f"      LLM 이유: {result.llm_reasoning[:80]}...")


def test_hybrid_verification():
    """하이브리드 검증 비교 테스트 (Keyword+Semantic vs LLM)"""
    print("\n" + "=" * 80)
    print("⚖️  하이브리드 검증 비교 테스트")
    print("=" * 80)
    
    service = ProductKnowledgeService(use_llm=True)
    
    test_conversation = [
        {"role": "employee", "text": "정기예금 금리는 12개월 기준 연 2.15%이며, 최소 50만원부터 가입 가능합니다."},
        {"role": "employee", "text": "주택담보대출은 최대 10억원까지 가능하고, 금리는 3~4% 수준입니다."},
    ]
    
    # Semantic Only
    print("\n1️⃣ Semantic 검증만 사용:")
    result_semantic = service.batch_verify_conversation(test_conversation, use_llm=False)
    print(f"   정확도: {result_semantic['accuracy_rate']:.1%}")
    print(f"   검증 방법: {result_semantic.get('verification_methods', {})}")
    
    # LLM 검증 포함
    if service.use_llm:
        print("\n2️⃣ LLM 검증 포함:")
        result_llm = service.batch_verify_conversation(test_conversation, use_llm=True)
        print(f"   정확도: {result_llm['accuracy_rate']:.1%}")
        print(f"   검증 방법: {result_llm.get('verification_methods', {})}")
        
        # 차이 분석
        diff = result_llm['accuracy_rate'] - result_semantic['accuracy_rate']
        if abs(diff) > 0.01:
            print(f"\n   📊 정확도 차이: {diff:+.1%}")
            print(f"      → LLM 검증이 더 {'정확함' if diff > 0 else '엄격함'}")
    else:
        print("\n⚠️ LLM 검증 비활성화 상태")


def test_knowledge_score_calculation():
    """지식 점수 계산 테스트"""
    print("\n" + "=" * 80)
    print("🧪 지식 점수 계산 테스트")
    print("=" * 80)
    
    score_metrics = ScoreMetrics()
    
    # 테스트 대화 1: 정확한 정보 제공
    print("\n1️⃣ 테스트 케이스 1: 정확한 정보 제공")
    accurate_conversation = [
        {"role": "customer", "text": "정기예금에 대해 알고 싶어요."},
        {"role": "employee", "text": "안녕하세요! 하경은행 정기예금은 최소 50만원부터 가입 가능하며, 기본 금리는 연 2.05%입니다."},
        {"role": "customer", "text": "기간은요?"},
        {"role": "employee", "text": "가입 기간은 1개월부터 36개월까지 선택하실 수 있습니다. 12개월의 경우 기본 금리 2.15%가 적용됩니다."},
    ]
    
    result1 = score_metrics.calculate_knowledge_score(accurate_conversation)
    print(f"   점수: {result1['score']}점")
    print(f"   이유: {result1['reason']}")
    print(f"   RAG 검증: {result1['details'].get('rag_verified', False)}")
    if result1['details'].get('rag_verified'):
        print(f"   - 총 주장: {result1['details']['total_claims']}")
        print(f"   - 정확한 주장: {result1['details']['accurate_claims']}")
        print(f"   - 정확도: {result1['details']['accuracy_rate']:.1%}")
    
    # 테스트 대화 2: 불확실한 표현 사용
    print("\n2️⃣ 테스트 케이스 2: 불확실한 표현 사용")
    uncertain_conversation = [
        {"role": "customer", "text": "신용카드 혜택이 뭔가요?"},
        {"role": "employee", "text": "음... 포인트 적립이 1% 정도 되는 것 같아요. 정확하진 않지만 아마 그럴 거예요."},
        {"role": "customer", "text": "연회비는요?"},
        {"role": "employee", "text": "연회비는... 확실하진 않은데 1만원에서 5만원 사이일 것 같습니다."},
    ]
    
    result2 = score_metrics.calculate_knowledge_score(uncertain_conversation)
    print(f"   점수: {result2['score']}점")
    print(f"   이유: {result2['reason']}")
    
    # 테스트 대화 3: 잘못된 정보 제공
    print("\n3️⃣ 테스트 케이스 3: 잘못된 정보 제공")
    incorrect_conversation = [
        {"role": "customer", "text": "정기예금 금리가 어떻게 되나요?"},
        {"role": "employee", "text": "정기예금 금리는 연 10%입니다."},  # 실제는 2~3%
        {"role": "customer", "text": "최소 가입 금액은?"},
        {"role": "employee", "text": "최소 10원부터 가입 가능합니다."},  # 실제는 50만원
    ]
    
    result3 = score_metrics.calculate_knowledge_score(incorrect_conversation)
    print(f"   점수: {result3['score']}점")
    print(f"   이유: {result3['reason']}")
    if result3['details'].get('errors'):
        print(f"   오류 목록:")
        for error in result3['details']['errors'][:3]:
            print(f"      - {error['claim']} ({error['category']})")
    
    # 테스트 대화 4: 정보 제공 없음
    print("\n4️⃣ 테스트 케이스 4: 정보 제공 없음")
    no_info_conversation = [
        {"role": "customer", "text": "대출 상담하고 싶어요."},
        {"role": "employee", "text": "네, 도와드리겠습니다."},
        {"role": "customer", "text": "어떤 상품이 있나요?"},
        {"role": "employee", "text": "여러 상품이 있습니다. 자세한 내용은 창구로 오시면 알려드리겠습니다."},
    ]
    
    result4 = score_metrics.calculate_knowledge_score(no_info_conversation)
    print(f"   점수: {result4['score']}점")
    print(f"   이유: {result4['reason']}")


def test_detailed_verification():
    """상세 검증 테스트"""
    print("\n" + "=" * 80)
    print("🧪 상세 검증 테스트")
    print("=" * 80)
    
    service = ProductKnowledgeService()
    
    # 다양한 제품 정보 테스트
    test_cases = [
        {
            "conversation": [
                {"role": "employee", "text": "하경 프리미엄 신용카드는 일반 가맹점에서 1.0% 포인트가 적립됩니다."},
                {"role": "employee", "text": "연회비는 Classic 등급의 경우 국내전용이 10,000원입니다."},
            ],
            "description": "신용카드 정보 (CRD-CRE)"
        },
        {
            "conversation": [
                {"role": "employee", "text": "주택담보대출은 최소 3,000만원부터 최대 10억원까지 가능합니다."},
                {"role": "employee", "text": "대출 기간은 최단 10년부터 최장 40년까지 선택하실 수 있습니다."},
            ],
            "description": "주택담보대출 정보 (LON-MTG)"
        },
        {
            "conversation": [
                {"role": "employee", "text": "자유적금은 매월 일정 금액을 납입하여 목돈을 만드는 상품입니다."},
                {"role": "employee", "text": "최소 10만원부터 최대 500만원까지 납입 가능합니다."},
            ],
            "description": "자유적금 정보 (DEP-FLX)"
        },
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{i}️⃣ {test_case['description']}")
        verification = service.batch_verify_conversation(test_case['conversation'])
        
        print(f"   - 정확도: {verification['accuracy_rate']:.1%}")
        print(f"   - 검증 항목: {verification['total_claims']}개")
        
        if verification['details']['by_product']:
            print(f"   - 제품별 정확도:")
            for product, stats in verification['details']['by_product'].items():
                print(f"      • {product}: {stats['accuracy_rate']:.1%}")
        
        if verification['verifications']:
            print(f"   - 검증 결과 샘플:")
            for v in verification['verifications'][:2]:
                status = "✅" if v.is_accurate else "❌"
                print(f"      {status} {v.claim} (유사도: {v.similarity_score:.2f})")


def main():
    """메인 함수"""
    try:
        test_product_knowledge_service()
        test_knowledge_score_calculation()
        test_detailed_verification()
        test_llm_verification()
        test_hybrid_verification()
        
        print("\n" + "=" * 80)
        print("✅ 모든 테스트 완료!")
        print("=" * 80)
        print("\n💡 Tip: OPENAI_API_KEY 설정 시 LLM 검증 테스트가 실행됩니다.")
        
    except Exception as e:
        print(f"\n❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

