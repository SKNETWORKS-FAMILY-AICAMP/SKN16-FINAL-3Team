"""
시뮬레이션 초기 데이터 생성 스크립트
"""
import json
from sqlmodel import Session, select
from app.database import engine
from app.models.simulation import SimulationScenario


def create_simulation_scenarios():
    """시뮬레이션 시나리오 초기 데이터 생성"""
    with Session(engine) as session:
        # 기존 시나리오 확인
        existing_scenarios = session.exec(select(SimulationScenario)).first()
        if existing_scenarios:
            print("✅ 시뮬레이션 시나리오가 이미 존재합니다. 스킵합니다.")
            return
        
        scenarios_data = [
            {
                "title": "신규 고객 예금 상담",
                "description": "처음 은행을 방문한 고객에게 적합한 예금 상품을 추천하는 시뮬레이션입니다.",
                "category": "고객상담",
                "difficulty": "초급",
                "estimated_duration": 15,
                "scenario_data": {
                    "situation": "30대 직장인 김고객이 첫 방문하여 예금 상품에 대해 문의했습니다.",
                    "customer_profile": {
                        "age": "30대",
                        "occupation": "직장인",
                        "income": "월 300-400만원",
                        "savings_goal": "안전한 자산 증식",
                        "risk_tolerance": "보수적"
                    },
                    "steps": [
                        {
                            "step_number": 1,
                            "type": "question",
                            "question": "고객의 예금 목적과 투자 성향을 파악하기 위해 어떤 질문을 하시겠습니까?",
                            "expected_response": "예금 목적, 투자 성향, 금리 선호도",
                            "max_score": 10.0,
                            "tips": "고객의 재정 상황과 목표를 파악하는 것이 중요합니다."
                        },
                        {
                            "step_number": 2,
                            "type": "action",
                            "question": "고객이 보수적인 성향이라고 답했습니다. 어떤 상품을 추천하시겠습니까?",
                            "expected_action": "정기예금",
                            "max_score": 15.0,
                            "tips": "보수적인 고객에게는 안전한 상품을 추천하는 것이 좋습니다."
                        },
                        {
                            "step_number": 3,
                            "type": "question",
                            "question": "정기예금의 장점과 특징을 어떻게 설명하시겠습니까?",
                            "expected_response": "안전성, 확정금리, 만기일정",
                            "max_score": 10.0,
                            "tips": "고객이 이해하기 쉽게 간단명료하게 설명하세요."
                        }
                    ]
                },
                "evaluation_criteria": {
                    "communication": "고객과의 소통 능력",
                    "product_knowledge": "상품 지식",
                    "customer_service": "고객 서비스 마인드"
                }
            },
            {
                "title": "대출 상담 시뮬레이션",
                "description": "주택 구입을 위한 대출 상담을 진행하는 시뮬레이션입니다.",
                "category": "은행업무",
                "difficulty": "중급",
                "estimated_duration": 20,
                "scenario_data": {
                    "situation": "40대 직장인 박고객이 주택 구입을 위한 대출을 문의했습니다.",
                    "customer_profile": {
                        "age": "40대",
                        "occupation": "직장인",
                        "income": "월 500-600만원",
                        "loan_amount": "2억원",
                        "property_value": "3억원"
                    },
                    "steps": [
                        {
                            "step_number": 1,
                            "type": "question",
                            "question": "대출 심사에 필요한 서류와 정보를 어떻게 안내하시겠습니까?",
                            "expected_response": "소득증명, 재직증명서, 부동산 관련 서류",
                            "max_score": 15.0,
                            "tips": "필요한 서류를 체계적으로 안내하는 것이 중요합니다."
                        },
                        {
                            "step_number": 2,
                            "type": "question",
                            "question": "고객의 대출 조건(금리, 상환방법)을 어떻게 설명하시겠습니까?",
                            "expected_response": "금리, 상환방법, 중도상환 조건",
                            "max_score": 15.0,
                            "tips": "고객이 이해하기 쉽게 구체적인 예시와 함께 설명하세요."
                        }
                    ]
                },
                "evaluation_criteria": {
                    "documentation": "서류 안내 능력",
                    "explanation": "상품 설명 능력",
                    "compliance": "법규 준수"
                }
            },
            {
                "title": "민원 처리 시뮬레이션",
                "description": "고객의 민원을 처리하는 시뮬레이션입니다.",
                "category": "응급상황",
                "difficulty": "고급",
                "estimated_duration": 25,
                "scenario_data": {
                    "situation": "고객이 카드 사용에 대해 불만을 제기하며 화를 내고 있습니다.",
                    "customer_profile": {
                        "age": "50대",
                        "issue": "카드 승인 거절",
                        "emotional_state": "화가 나 있음",
                        "demand": "즉시 해결 요구"
                    },
                    "steps": [
                        {
                            "step_number": 1,
                            "type": "action",
                            "question": "화가 난 고객을 어떻게 응대하시겠습니까?",
                            "expected_action": "공감하고 차분하게 대응",
                            "max_score": 20.0,
                            "tips": "고객의 감정을 먼저 이해하고 공감하는 것이 중요합니다."
                        },
                        {
                            "step_number": 2,
                            "type": "question",
                            "question": "카드 승인 거절 사유를 어떻게 조사하고 설명하시겠습니까?",
                            "expected_response": "시스템 확인, 원인 파악, 해결방안 제시",
                            "max_score": 15.0,
                            "tips": "체계적으로 문제를 파악하고 해결방안을 제시하세요."
                        }
                    ]
                },
                "evaluation_criteria": {
                    "emotional_intelligence": "감정 관리 능력",
                    "problem_solving": "문제 해결 능력",
                    "customer_satisfaction": "고객 만족도"
                }
            }
        ]
        
        for scenario_data in scenarios_data:
            scenario = SimulationScenario(
                title=scenario_data["title"],
                description=scenario_data["description"],
                category=scenario_data["category"],
                difficulty=scenario_data["difficulty"],
                estimated_duration=scenario_data["estimated_duration"],
                scenario_data=json.dumps(scenario_data["scenario_data"], ensure_ascii=False),
                evaluation_criteria=json.dumps(scenario_data["evaluation_criteria"], ensure_ascii=False)
            )
            
            session.add(scenario)
        
        session.commit()
        print(f"✅ {len(scenarios_data)}개의 시뮬레이션 시나리오 생성 완료")


if __name__ == "__main__":
    create_simulation_scenarios()
