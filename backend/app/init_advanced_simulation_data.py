"""
고도화된 시뮬레이션 초기 데이터 생성 스크립트
STT/LLM/TTS 기반 음성 시뮬레이션 및 고객 페르소나 시스템
"""
import json
from sqlmodel import Session, select
from app.database import engine
from app.models.advanced_simulation import CustomerPersona, SimulationSituation


def create_customer_personas():
    """고객 페르소나 초기 데이터 생성"""
    with Session(engine) as session:
        # 기존 페르소나 확인
        existing_personas = session.exec(select(CustomerPersona)).first()
        if existing_personas:
            print("✅ 고객 페르소나가 이미 존재합니다. 스킵합니다.")
            return
        
        personas_data = [
            {
                "name": "김실용",
                "age_group": "30대",
                "occupation": "직장인",
                "financial_literacy": "중간",
                "customer_type": "실용형",
                "personality_traits": {
                    "traits": ["빠른 의사결정", "효율성 중시", "직설적 소통"],
                    "preferences": ["간결한 설명", "빠른 처리", "명확한 정보"]
                },
                "communication_style": {
                    "tone": "직설적이고 간결함",
                    "language_level": "중급",
                    "response_speed": "빠름"
                },
                "typical_concerns": [
                    "수수료 절약",
                    "처리 시간 단축",
                    "명확한 조건 설명"
                ],
                "response_patterns": {
                    "positive": "빠른 이해와 결정",
                    "negative": "불만 표현이 직접적",
                    "neutral": "정보 요구가 구체적"
                },
                "voice_characteristics": {
                    "voice": "alloy",
                    "speed": 1.1,
                    "pitch": "normal",
                    "tone": "business-like"
                }
            },
            {
                "name": "박보수",
                "age_group": "50대",
                "occupation": "은퇴자",
                "financial_literacy": "낮음",
                "customer_type": "보수형",
                "personality_traits": {
                    "traits": ["안정성 중시", "신중한 결정", "전통적 가치"],
                    "preferences": ["안전한 상품", "자세한 설명", "검증된 정보"]
                },
                "communication_style": {
                    "tone": "정중하고 신중함",
                    "language_level": "기본",
                    "response_speed": "느림"
                },
                "typical_concerns": [
                    "자금 안전성",
                    "손실 위험",
                    "복잡한 조건"
                ],
                "response_patterns": {
                    "positive": "신중한 검토 후 결정",
                    "negative": "걱정과 우려 표현",
                    "neutral": "반복적인 확인 요청"
                },
                "voice_characteristics": {
                    "voice": "nova",
                    "speed": 0.9,
                    "pitch": "low",
                    "tone": "calm"
                }
            },
            {
                "name": "이불만",
                "age_group": "40대",
                "occupation": "자영업자",
                "financial_literacy": "높음",
                "customer_type": "불만형",
                "personality_traits": {
                    "traits": ["의심이 많음", "비판적 사고", "감정적 반응"],
                    "preferences": ["투명한 정보", "공정한 처리", "빠른 해결"]
                },
                "communication_style": {
                    "tone": "의심스럽고 비판적",
                    "language_level": "고급",
                    "response_speed": "빠름"
                },
                "typical_concerns": [
                    "은행의 수수료 정책",
                    "고객 서비스 품질",
                    "정보 투명성"
                ],
                "response_patterns": {
                    "positive": "조건부 수용",
                    "negative": "강한 불만 표현",
                    "neutral": "세부사항 추궁"
                },
                "voice_characteristics": {
                    "voice": "shimmer",
                    "speed": 1.2,
                    "pitch": "high",
                    "tone": "skeptical"
                }
            },
            {
                "name": "최긍정",
                "age_group": "20대",
                "occupation": "학생",
                "financial_literacy": "낮음",
                "customer_type": "긍정형",
                "personality_traits": {
                    "traits": ["낙천적", "협조적", "학습 의지"],
                    "preferences": ["친근한 설명", "단계별 안내", "긍정적 피드백"]
                },
                "communication_style": {
                    "tone": "친근하고 활발함",
                    "language_level": "기본",
                    "response_speed": "보통"
                },
                "typical_concerns": [
                    "이해하기 쉬운 설명",
                    "학습 기회",
                    "긍정적 경험"
                ],
                "response_patterns": {
                    "positive": "적극적 참여",
                    "negative": "도움 요청",
                    "neutral": "호기심 많은 질문"
                },
                "voice_characteristics": {
                    "voice": "echo",
                    "speed": 1.0,
                    "pitch": "normal",
                    "tone": "cheerful"
                }
            },
            {
                "name": "정급함",
                "age_group": "30대",
                "occupation": "직장인",
                "financial_literacy": "중간",
                "customer_type": "급함형",
                "personality_traits": {
                    "traits": ["시간 압박", "효율성 중시", "결과 지향"],
                    "preferences": ["빠른 처리", "핵심 정보", "즉시 해결"]
                },
                "communication_style": {
                    "tone": "급하고 간결함",
                    "language_level": "중급",
                    "response_speed": "매우 빠름"
                },
                "typical_concerns": [
                    "처리 시간",
                    "지연 요인",
                    "빠른 결과"
                ],
                "response_patterns": {
                    "positive": "빠른 승인",
                    "negative": "급한 불만 표현",
                    "neutral": "시간 확인 요청"
                },
                "voice_characteristics": {
                    "voice": "fable",
                    "speed": 1.3,
                    "pitch": "high",
                    "tone": "urgent"
                }
            }
        ]
        
        for persona_data in personas_data:
            persona = CustomerPersona(
                name=persona_data["name"],
                age_group=persona_data["age_group"],
                occupation=persona_data["occupation"],
                financial_literacy=persona_data["financial_literacy"],
                customer_type=persona_data["customer_type"],
                personality_traits=json.dumps(persona_data["personality_traits"], ensure_ascii=False),
                communication_style=json.dumps(persona_data["communication_style"], ensure_ascii=False),
                typical_concerns=json.dumps(persona_data["typical_concerns"], ensure_ascii=False),
                response_patterns=json.dumps(persona_data["response_patterns"], ensure_ascii=False),
                voice_characteristics=json.dumps(persona_data["voice_characteristics"], ensure_ascii=False)
            )
            
            session.add(persona)
        
        session.commit()
        print(f"✅ {len(personas_data)}개의 고객 페르소나 생성 완료")


def create_simulation_situations():
    """시뮬레이션 상황 초기 데이터 생성"""
    with Session(engine) as session:
        # 기존 상황 확인
        existing_situations = session.exec(select(SimulationSituation)).first()
        if existing_situations:
            print("✅ 시뮬레이션 상황이 이미 존재합니다. 스킵합니다.")
            return
        
        situations_data = [
            {
                "title": "신규 예금 상품 상담",
                "business_category": "수신",
                "situation_type": "상품상담",
                "difficulty_level": "쉬움",
                "situation_context": {
                    "description": "고객이 은행을 방문하여 새로운 예금 상품에 대해 문의하고 있습니다.",
                    "customer_goal": "적절한 예금 상품 선택",
                    "bank_goal": "고객에게 맞는 상품 추천 및 가입 유도",
                    "key_points": ["고객 재정 상황 파악", "상품 특징 설명", "가입 절차 안내"]
                },
                "expected_outcomes": {
                    "success_criteria": [
                        "고객 재정 상황 정확히 파악",
                        "적절한 상품 추천",
                        "고객 만족도 향상"
                    ],
                    "failure_criteria": [
                        "고객 상황 파악 실패",
                        "부적절한 상품 추천",
                        "고객 불만 발생"
                    ]
                },
                "evaluation_criteria": {
                    "communication": "고객과의 소통 능력 (30%)",
                    "product_knowledge": "상품 지식 및 설명 능력 (40%)",
                    "customer_service": "고객 서비스 마인드 (30%)"
                },
                "conversation_flow": {
                    "phases": [
                        {"phase": "greeting", "description": "인사 및 목적 확인"},
                        {"phase": "information_gathering", "description": "고객 정보 수집"},
                        {"phase": "product_recommendation", "description": "상품 추천 및 설명"},
                        {"phase": "closing", "description": "결론 및 다음 단계 안내"}
                    ]
                },
                "customer_reactions": {
                    "positive": ["적극적 관심", "질문 증가", "승인 의사 표현"],
                    "negative": ["의심 표현", "불만 표시", "거부 의사"],
                    "neutral": ["정보 확인", "추가 질문", "신중한 검토"]
                }
            },
            {
                "title": "대출 상담 및 신청",
                "business_category": "여신",
                "situation_type": "상담",
                "difficulty_level": "보통",
                "situation_context": {
                    "description": "고객이 주택 구입을 위한 대출을 신청하고 있습니다.",
                    "customer_goal": "적절한 대출 조건으로 승인받기",
                    "bank_goal": "신용도 평가 및 적절한 대출 조건 제시",
                    "key_points": ["신용도 평가", "대출 조건 설명", "서류 안내"]
                },
                "expected_outcomes": {
                    "success_criteria": [
                        "정확한 신용도 평가",
                        "명확한 대출 조건 설명",
                        "필요 서류 완벽 안내"
                    ],
                    "failure_criteria": [
                        "신용도 평가 오류",
                        "조건 설명 불명확",
                        "서류 누락 안내"
                    ]
                },
                "evaluation_criteria": {
                    "assessment_accuracy": "신용도 평가 정확성 (35%)",
                    "explanation_quality": "조건 설명 품질 (35%)",
                    "documentation": "서류 안내 완성도 (30%)"
                },
                "conversation_flow": {
                    "phases": [
                        {"phase": "loan_purpose", "description": "대출 목적 확인"},
                        {"phase": "credit_assessment", "description": "신용도 평가"},
                        {"phase": "condition_explanation", "description": "대출 조건 설명"},
                        {"phase": "documentation", "description": "필요 서류 안내"},
                        {"phase": "application_process", "description": "신청 절차 안내"}
                    ]
                },
                "customer_reactions": {
                    "positive": ["조건 수용", "신청 진행", "추가 상담 요청"],
                    "negative": ["조건 불만", "신청 거부", "다른 은행 고려"],
                    "neutral": ["조건 검토", "서류 준비", "추가 질문"]
                }
            },
            {
                "title": "카드 민원 처리",
                "business_category": "민원/불만 처리",
                "situation_type": "민원처리",
                "difficulty_level": "어려움",
                "situation_context": {
                    "description": "고객이 카드 사용 관련 문제로 불만을 제기하고 있습니다.",
                    "customer_goal": "문제 해결 및 보상 요구",
                    "bank_goal": "민원 해결 및 고객 만족도 회복",
                    "key_points": ["문제 상황 파악", "원인 분석", "해결방안 제시"]
                },
                "expected_outcomes": {
                    "success_criteria": [
                        "문제 원인 정확히 파악",
                        "적절한 해결방안 제시",
                        "고객 만족도 회복"
                    ],
                    "failure_criteria": [
                        "문제 파악 실패",
                        "부적절한 해결방안",
                        "고객 불만 지속"
                    ]
                },
                "evaluation_criteria": {
                    "problem_solving": "문제 해결 능력 (40%)",
                    "emotional_intelligence": "감정 관리 능력 (30%)",
                    "customer_satisfaction": "고객 만족도 (30%)"
                },
                "conversation_flow": {
                    "phases": [
                        {"phase": "complaint_reception", "description": "민원 접수 및 공감"},
                        {"phase": "situation_analysis", "description": "상황 분석 및 원인 파악"},
                        {"phase": "solution_proposal", "description": "해결방안 제시"},
                        {"phase": "resolution", "description": "문제 해결 및 보상"},
                        {"phase": "follow_up", "description": "후속 조치 안내"}
                    ]
                },
                "customer_reactions": {
                    "positive": ["해결 만족", "감사 표현", "서비스 개선 제안"],
                    "negative": ["해결 불만", "상급자 요청", "법적 대응 언급"],
                    "neutral": ["해결책 검토", "추가 확인 요청", "시간 요청"]
                }
            }
        ]
        
        for situation_data in situations_data:
            situation = SimulationSituation(
                title=situation_data["title"],
                business_category=situation_data["business_category"],
                situation_type=situation_data["situation_type"],
                difficulty_level=situation_data["difficulty_level"],
                situation_context=json.dumps(situation_data["situation_context"], ensure_ascii=False),
                expected_outcomes=json.dumps(situation_data["expected_outcomes"], ensure_ascii=False),
                evaluation_criteria=json.dumps(situation_data["evaluation_criteria"], ensure_ascii=False),
                conversation_flow=json.dumps(situation_data["conversation_flow"], ensure_ascii=False),
                customer_reactions=json.dumps(situation_data["customer_reactions"], ensure_ascii=False)
            )
            
            session.add(situation)
        
        session.commit()
        print(f"✅ {len(situations_data)}개의 시뮬레이션 상황 생성 완료")


if __name__ == "__main__":
    create_customer_personas()
    create_simulation_situations()
