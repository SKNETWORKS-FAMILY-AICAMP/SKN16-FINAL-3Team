#!/usr/bin/env python3
"""
테스트 시나리오로 평가서 생성 및 분석
고정된 테스트 시나리오를 사용하여 평가서를 생성하고 결과를 분석합니다.
"""
import sys
import json
from pathlib import Path
from datetime import datetime

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from app.services.rag_simulation_service import RAGSimulationService
from app.database import get_session

# ✅ 기본 테스트 시나리오 (MMDA 및 대출 상품 상담)
DEFAULT_TEST_SCENARIO = {
    "name": "테스트 시나리오: MMDA 및 대출 상담",
    "conversation": [
        {"role": "employee", "text": "안녕하세요, 무엇을 도와드릴까요?"},
        {"role": "customer", "text": "안녕하세요, MMDA 상품에 대해 문의하고 싶어요."},
        {
            "role": "employee",
            "text": "MMDA는 입출금이 자유로우면서도 높은 금리를 받을 수 있는 예금상품입니다. 최소 100만원부터 가입 가능하며, 잔액에 따라 차등 금리가 적용됩니다."
        },
        {"role": "customer", "text": "주택담보대출을 받으려고 하는데 LTV와 DTI 규제가 어떻게 되나요?"},
        {
            "role": "employee",
            "text": "주택담보대출은 주택을 담보로 제공하여 대출받는 상품입니다. LTV 즉 담보인정비율은 일반지역 70%, DTI 즉 총부채상환비율은 60%까지 가능합니다."
        },
        {"role": "customer", "text": "예금담보대출도 가능한가요? 수취은행이 다른 경우에도 되나요?"},
        {
            "role": "employee",
            "text": "예금담보대출은 예금을 담보로 제공하여 초저금리로 대출받는 상품입니다. 예금잔액의 95%까지 대출 가능하며, 수취은행과 무관하게 본행 예금만 가능합니다."
        },
        {"role": "customer", "text": "중개인을 통해서도 대출 신청이 가능한가요?"},
        {
            "role": "employee",
            "text": "중개인을 통한 대출 신청도 가능합니다. 다만 직접 방문하시거나 온라인으로 신청하시는 것이 더 빠르고 정확합니다."
        }
    ],
    "persona": {
        "id": "test_persona_001",
        "name": "테스트 고객",
        "gender": "female",
        "age_group": "40대",
        "occupation": "직장인",
        "type": "긍정형",
        "customer_style": "긍정형",
        "tone": "neutral",
        "speech": {"tone": "neutral", "speed": 1.0},
        "utterance_hints": [],
        "financial_literacy": "보통"
    },
    "situation": {
        "id": "test_situation_001",
        "title": "STT 성능 및 RAG 연동 테스트",
        "category": "test",
        "goals": [
            "금융 용어 STT 인식 정확도 평가",
            "RAG 상품 데이터 연동 확인",
            "지식 평가 로직 검증"
        ],
        "has_product_data": True
    }
}


def test_feedback_generation():
    """기본 테스트 시나리오로 평가서 생성 및 분석"""
    scenario = DEFAULT_TEST_SCENARIO.copy()
    
    print("=" * 80)
    print(f"🧪 테스트 시나리오 평가서 생성 및 분석: {scenario['name']}")
    print("=" * 80)
    
    test_conversation = scenario['conversation']
    test_persona = scenario['persona']
    test_situation = scenario['situation']
    
    print("\n📝 테스트 대화 내용:")
    for i, msg in enumerate(test_conversation, 1):
        role = "직원" if msg['role'] == 'employee' else "고객"
        print(f"   {i}. {role}: {msg['text']}")
    
    print("\n🔍 평가서 생성 중...")
    
    try:
        # 세션 생성
        session = next(get_session())
        
        # RAG 시뮬레이션 서비스 초기화
        rag_service = RAGSimulationService(session)
        
        # 평가서 생성
        feedback_result = rag_service.generate_comprehensive_feedback(
            conversation_history=test_conversation,
            persona=test_persona,
            situation=test_situation
        )
        
        print("\n" + "=" * 80)
        print("📊 평가서 생성 결과")
        print("=" * 80)
        
        # 전체 점수
        print(f"\n🎯 종합 점수: {feedback_result.get('overall_score', 0):.1f}점")
        
        # 역량별 점수
        detailed_feedback = feedback_result.get('detailedFeedback', {})
        print("\n📈 역량별 점수:")
        print(f"   - 지식 (Knowledge): {detailed_feedback.get('knowledge', {}).get('score', 0)}점")
        print(f"   - 기술 (Skill): {detailed_feedback.get('skill', {}).get('score', 0)}점")
        print(f"   - 친절도 (Kindness): {detailed_feedback.get('kindness', {}).get('score', 0)}점")
        print(f"   - 전달력 (Delivery): {detailed_feedback.get('clarity_confidence', {}).get('score', 0)}점")
        
        # 지식 피드백 상세 분석
        knowledge_feedback = detailed_feedback.get('knowledge', {}).get('feedback', '')
        print("\n📚 지식 피드백:")
        print("   " + "\n   ".join(knowledge_feedback.split('\n')[:10]))  # 처음 10줄만
        
        # 기술 피드백
        skill_feedback = detailed_feedback.get('skill', {}).get('feedback', '')
        print("\n🔧 기술 피드백:")
        print("   " + "\n   ".join(skill_feedback.split('\n')[:10]))  # 처음 10줄만
        
        # 친절도 피드백
        kindness_feedback = detailed_feedback.get('kindness', {}).get('feedback', '')
        print("\n😊 친절도 피드백:")
        print("   " + "\n   ".join(kindness_feedback.split('\n')[:10]))  # 처음 10줄만
        
        # 전달력 피드백
        delivery_feedback = detailed_feedback.get('clarity_confidence', {}).get('feedback', '')
        print("\n💬 전달력 피드백:")
        print("   " + "\n   ".join(delivery_feedback.split('\n')[:10]))  # 처음 10줄만
        
        # 요약
        summary = feedback_result.get('summary', '')
        print("\n📝 요약:")
        print(f"   {summary}")
        
        # 개선 제안
        improvements = feedback_result.get('improvements', '')
        print("\n💡 개선 제안:")
        print(f"   {improvements}")
        
        # 결과를 JSON 파일로 저장
        output_file = project_root / "test_feedback_result.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(feedback_result, f, ensure_ascii=False, indent=2)
        
        print(f"\n💾 결과가 {output_file}에 저장되었습니다.")
        
        # 분석
        print("\n" + "=" * 80)
        print("🔍 분석 결과")
        print("=" * 80)
        
        # 지식 점수 분석
        knowledge_score = detailed_feedback.get('knowledge', {}).get('score', 0)
        print(f"\n1. 지식 점수: {knowledge_score}점")
        if "100만원" in knowledge_feedback.lower() or "최소 100" in knowledge_feedback.lower():
            if "100만원" in knowledge_feedback and "최소 100" in knowledge_feedback:
                print("   ⚠️ 문제 발견: '100만원'과 '최소 100'이 혼재되어 있습니다.")
                print("   → '최소 100만원'으로 정확히 말했는데 '최소 100'으로 잘못 인식되었을 가능성")
            elif "100만원" in knowledge_feedback:
                print("   ✅ 정상: '100만원'으로 정확히 인식되었습니다.")
            elif "최소 100" in knowledge_feedback:
                print("   ❌ 문제: '최소 100만원'을 '최소 100'으로 잘못 인식했습니다.")
        else:
            print("   ℹ️ '100만원' 관련 언급이 없습니다.")
        
        # 개선점 섹션 확인
        if "개선점" in knowledge_feedback:
            print("\n2. 개선점 섹션:")
            improvement_section = knowledge_feedback.split("개선점")[1] if "개선점" in knowledge_feedback else ""
            if "최소 100" in improvement_section and "100만원" not in improvement_section:
                print("   ❌ 문제: 개선점에서 '최소 100'으로 잘못 표시되었습니다.")
                print("   → 실제 대화에서는 '최소 100만원'으로 정확히 말했습니다.")
            elif "100만원" in improvement_section:
                print("   ✅ 정상: 개선점에서 '100만원'으로 정확히 표시되었습니다.")
        
        print("\n✅ 분석 완료!")
        return feedback_result
        
    except Exception as e:
        print(f"\n❌ 평가서 생성 실패: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    try:
        result = test_feedback_generation()
        
        if result:
            print("\n" + "=" * 80)
            print("✅ 테스트 완료!")
            print("=" * 80)
        else:
            print("\n❌ 테스트 실패!")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n❌ 테스트 실행 중 오류: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

