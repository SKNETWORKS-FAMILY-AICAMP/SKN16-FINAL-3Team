"""
피드백 구체성 개선 테스트 스크립트
실제 대화 로그 인용이 제대로 작동하는지 확인
"""
import json
from app.database import engine
from sqlmodel import Session
from app.services.rag_simulation_service import RAGSimulationService

# 테스트용 대화 로그 예시
test_conversation_history = [
    {
        "role": "customer",
        "text": "정기예금 상품이 궁금한데요"
    },
    {
        "role": "employee",
        "text": "네, 정기예금 상품에 대해 안내해드리겠습니다. 금리 3.5% 상품이 있습니다."
    },
    {
        "role": "customer",
        "text": "그럼 이 상품은 안 되네요"
    },
    {
        "role": "employee",
        "text": "아, 죄송합니다. 그럼 다른 상품을 찾아드리겠습니다."
    },
    {
        "role": "customer",
        "text": "좋아요, 추천해주세요"
    },
    {
        "role": "employee",
        "text": "좋은 선택입니다! 더 빠르고 정확한 상품을 추천드리겠습니다."
    }
]

def test_feedback_prompt():
    """평가 프롬프트에 구체성 요구사항이 포함되어 있는지 확인"""
    print("="*80)
    print("🔍 피드백 구체성 개선 테스트")
    print("="*80)
    
    with Session(engine) as session:
        service = RAGSimulationService(session)
        
        # 간단한 테스트 데이터
        persona = {
            "id": "test_persona",
            "type": "긍정형",
            "financial_literacy": "보통"
        }
        situation = {
            "id": "test_situation",
            "title": "정기예금 상담",
            "category": "수신",
            "goals": ["정기예금 상품 설명"]
        }
        
        # 평가 프롬프트 생성 부분 확인
        # 실제로는 _evaluate_complete_session 내부에서 생성되므로
        # 프롬프트의 주요 부분만 확인
        
        print("\n✅ 테스트 1: 피드백 가이드에 구체성 요구사항 확인")
        print("-" * 80)
        
        # 피드백 가이드 키워드 확인
        required_keywords = [
            "실제 대화 로그",
            "구체적인 표현을 찾아서 인용",
            "모호한 표현 금지",
            "Before → After",
            "절대 금지"
        ]
        
        # 파일에서 직접 확인
        try:
            import os
            file_path = os.path.join(os.path.dirname(__file__), "app", "services", "rag_simulation_service.py")
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                
                print("\n📝 피드백 가이드 섹션 확인:")
                for keyword in required_keywords:
                    if keyword in content:
                        print(f"  ✓ '{keyword}' 키워드 발견")
                    else:
                        print(f"  ✗ '{keyword}' 키워드 없음")
                
                # 실제 대화 로그 인용 관련 부분 확인
                if "실제 대화 로그에서 사용된" in content:
                    print("\n  ✅ 실제 대화 로그 인용 요구사항 확인됨")
                else:
                    print("\n  ⚠️ 실제 대화 로그 인용 요구사항 확인 실패")
                
                # 모호한 표현 금지 관련
                if "부정 표현을 회피할 수 있도록" in content:
                    print("  ✅ 모호한 표현 금지 예시 확인됨")
                else:
                    print("  ⚠️ 모호한 표현 금지 예시 확인 실패")
                
        except Exception as e:
            print(f"  ❌ 파일 읽기 오류: {e}")
        
        print("\n" + "="*80)
        print("✅ 테스트 완료")
        print("="*80)
        print("\n💡 실제 평가 결과를 확인하려면:")
        print("  1. 실제 시뮬레이션을 실행하거나")
        print("  2. run_test_mode_batch.py를 실행하여 평가 결과를 확인하세요")
        print("\n📌 예상 결과:")
        print("  - '부정 표현을 회피할 수 있도록' 같은 모호한 피드백 ❌")
        print("  - '**안 됩니다**라는 부정 표현이 사용되었습니다' 같은 구체적 피드백 ✅")

if __name__ == "__main__":
    test_feedback_prompt()

