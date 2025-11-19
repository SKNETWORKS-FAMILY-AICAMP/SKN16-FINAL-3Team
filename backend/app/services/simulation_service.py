"""
시뮬레이션 서비스
시뮬레이션 시나리오 관리, 실행, 평가 기능
"""
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
from sqlmodel import Session, select

from app.models.simulation import (
    SimulationScenario, SimulationAttempt, SimulationStep, SimulationProgress
)
from app.models.user import User


class SimulationService:
    """시뮬레이션 서비스"""
    
    def __init__(self, session: Session):
        self.session = session
    
    def get_scenarios(self, category: Optional[str] = None, difficulty: Optional[str] = None) -> List[Dict]:
        """시뮬레이션 시나리오 목록 조회"""
        query = select(SimulationScenario).where(SimulationScenario.is_active == True)
        
        if category:
            query = query.where(SimulationScenario.category == category)
        if difficulty:
            query = query.where(SimulationScenario.difficulty == difficulty)
        
        scenarios = self.session.exec(query.order_by(SimulationScenario.created_at.desc())).all()
        
        result = []
        for scenario in scenarios:
            result.append({
                "id": scenario.id,
                "title": scenario.title,
                "description": scenario.description,
                "category": scenario.category,
                "difficulty": scenario.difficulty,
                "estimated_duration": scenario.estimated_duration,
                "created_at": scenario.created_at.isoformat()
            })
        
        return result
    
    def get_scenario_detail(self, scenario_id: int) -> Optional[Dict]:
        """시뮬레이션 시나리오 상세 정보 조회"""
        scenario = self.session.get(SimulationScenario, scenario_id)
        if not scenario or not scenario.is_active:
            return None
        
        return {
            "id": scenario.id,
            "title": scenario.title,
            "description": scenario.description,
            "category": scenario.category,
            "difficulty": scenario.difficulty,
            "estimated_duration": scenario.estimated_duration,
            "scenario_data": json.loads(scenario.scenario_data),
            "evaluation_criteria": json.loads(scenario.evaluation_criteria)
        }
    
    def start_simulation(self, user_id: int, scenario_id: int) -> Dict:
        """시뮬레이션 시작"""
        scenario = self.session.get(SimulationScenario, scenario_id)
        if not scenario or not scenario.is_active:
            raise ValueError("시나리오를 찾을 수 없습니다.")
        
        # 진행 중인 시뮬레이션이 있는지 확인
        existing_attempt = self.session.exec(
            select(SimulationAttempt).where(
                SimulationAttempt.user_id == user_id,
                SimulationAttempt.scenario_id == scenario_id,
                SimulationAttempt.status == "in_progress"
            )
        ).first()
        
        if existing_attempt:
            raise ValueError("이미 진행 중인 시뮬레이션이 있습니다.")
        
        # 새로운 시도 생성
        attempt = SimulationAttempt(
            user_id=user_id,
            scenario_id=scenario_id,
            status="in_progress",
            detailed_results="{}"
        )
        
        self.session.add(attempt)
        self.session.commit()
        self.session.refresh(attempt)
        
        # 시나리오 데이터 파싱
        scenario_data = json.loads(scenario.scenario_data)
        
        return {
            "attempt_id": attempt.id,
            "scenario": {
                "id": scenario.id,
                "title": scenario.title,
                "description": scenario.description,
                "category": scenario.category,
                "difficulty": scenario.difficulty
            },
            "current_step": scenario_data.get("steps", [{}])[0] if scenario_data.get("steps") else {},
            "total_steps": len(scenario_data.get("steps", []))
        }
    
    def submit_step_response(self, attempt_id: int, step_number: int, 
                           user_response: str, user_action: Optional[str] = None) -> Dict:
        """시뮬레이션 단계 응답 제출"""
        attempt = self.session.get(SimulationAttempt, attempt_id)
        if not attempt or attempt.status != "in_progress":
            raise ValueError("진행 중인 시뮬레이션을 찾을 수 없습니다.")
        
        scenario = self.session.get(SimulationScenario, attempt.scenario_id)
        scenario_data = json.loads(scenario.scenario_data)
        evaluation_criteria = json.loads(scenario.evaluation_criteria)
        
        # 현재 단계 정보
        steps = scenario_data.get("steps", [])
        if step_number >= len(steps):
            raise ValueError("잘못된 단계 번호입니다.")
        
        current_step = steps[step_number]
        
        # 응답 평가
        step_result = self._evaluate_step_response(
            current_step, user_response, user_action, evaluation_criteria
        )
        
        # 단계 기록 저장
        simulation_step = SimulationStep(
            attempt_id=attempt_id,
            step_number=step_number,
            step_type=current_step.get("type", "question"),
            step_content=json.dumps(current_step),
            user_response=user_response,
            user_action=user_action,
            is_correct=step_result["is_correct"],
            score=step_result["score"],
            max_score=step_result["max_score"],
            feedback=step_result["feedback"],
            tips=step_result["tips"]
        )
        
        self.session.add(simulation_step)
        
        # 다음 단계 확인
        next_step = steps[step_number + 1] if step_number + 1 < len(steps) else None
        
        result = {
            "step_result": step_result,
            "current_score": self._calculate_current_score(attempt_id),
            "next_step": next_step,
            "is_completed": next_step is None
        }
        
        # 시뮬레이션 완료 처리
        if result["is_completed"]:
            result["final_result"] = self._complete_simulation(attempt_id)
        
        self.session.commit()
        return result
    
    def _evaluate_step_response(self, step: Dict, user_response: str, 
                              user_action: Optional[str], criteria: Dict) -> Dict:
        """단계 응답 평가"""
        # 간단한 평가 로직 (실제로는 더 복잡한 AI 평가 가능)
        step_type = step.get("type", "question")
        expected_response = step.get("expected_response", "")
        expected_action = step.get("expected_action", "")
        
        score = 0.0
        max_score = step.get("max_score", 10.0)
        is_correct = False
        
        if step_type == "question":
            # 답변 유사도 기반 평가 (간단한 키워드 매칭)
            if any(keyword in user_response.lower() for keyword in expected_response.lower().split()):
                score = max_score * 0.8
                is_correct = True
            elif len(user_response.strip()) > 10:  # 최소한의 답변 길이
                score = max_score * 0.5
                is_correct = False
        elif step_type == "action":
            if user_action == expected_action:
                score = max_score
                is_correct = True
        
        # 피드백 생성
        feedback = self._generate_step_feedback(step, user_response, score, max_score)
        tips = step.get("tips", "")
        
        return {
            "is_correct": is_correct,
            "score": score,
            "max_score": max_score,
            "feedback": feedback,
            "tips": tips
        }
    
    def _generate_step_feedback(self, step: Dict, user_response: str, score: float, max_score: float) -> str:
        """단계별 피드백 생성"""
        if score >= max_score * 0.8:
            return "훌륭한 답변입니다! 실무에서도 이런 식으로 응답하시면 좋겠습니다."
        elif score >= max_score * 0.5:
            return "좋은 시도입니다. 조금 더 구체적으로 답변하면 더 좋겠습니다."
        else:
            return "다시 한번 생각해보세요. 고객의 상황을 더 자세히 파악해보시기 바랍니다."
    
    def _calculate_current_score(self, attempt_id: int) -> float:
        """현재까지의 점수 계산"""
        steps = self.session.exec(
            select(SimulationStep).where(SimulationStep.attempt_id == attempt_id)
        ).all()
        
        if not steps:
            return 0.0
        
        total_score = sum(step.score for step in steps)
        max_score = sum(step.max_score for step in steps)
        
        return (total_score / max_score * 100) if max_score > 0 else 0.0
    
    def _complete_simulation(self, attempt_id: int) -> Dict:
        """시뮬레이션 완료 처리"""
        attempt = self.session.get(SimulationAttempt, attempt_id)
        
        # 최종 점수 계산
        final_score = self._calculate_current_score(attempt_id)
        grade = self._calculate_grade(final_score)
        
        # 시도 정보 업데이트
        attempt.completed_at = datetime.utcnow()
        attempt.duration_minutes = int((attempt.completed_at - attempt.started_at).total_seconds() / 60)
        attempt.total_score = final_score
        attempt.grade = grade
        attempt.status = "completed"
        
        # 상세 결과 저장
        steps = self.session.exec(
            select(SimulationStep).where(SimulationStep.attempt_id == attempt_id)
        ).all()
        
        detailed_results = {
            "total_score": final_score,
            "grade": grade,
            "steps": [
                {
                    "step_number": step.step_number,
                    "step_type": step.step_type,
                    "score": step.score,
                    "max_score": step.max_score,
                    "is_correct": step.is_correct,
                    "feedback": step.feedback
                }
                for step in steps
            ]
        }
        
        attempt.detailed_results = json.dumps(detailed_results, ensure_ascii=False)
        attempt.feedback = self._generate_final_feedback(final_score, grade)
        
        # 진행 상황 업데이트
        self._update_user_progress(attempt.user_id, attempt.scenario_id, final_score)
        
        self.session.add(attempt)
        
        return {
            "total_score": final_score,
            "grade": grade,
            "duration_minutes": attempt.duration_minutes,
            "feedback": attempt.feedback,
            "detailed_results": detailed_results
        }
    
    def _calculate_grade(self, score: float) -> str:
        """등급 계산"""
        if score >= 90:
            return "A+"
        elif score >= 85:
            return "A"
        elif score >= 80:
            return "B+"
        elif score >= 75:
            return "B"
        elif score >= 70:
            return "C+"
        elif score >= 65:
            return "C"
        else:
            return "D"
    
    def _generate_final_feedback(self, score: float, grade: str) -> str:
        """최종 피드백 생성"""
        if grade in ["A+", "A"]:
            return "🎉 훌륭한 성과입니다! 실무에서도 이런 수준으로 고객을 응대하실 수 있을 것입니다."
        elif grade in ["B+", "B"]:
            return "👍 좋은 성과입니다. 몇 가지 부분만 더 보완하면 완벽할 것 같습니다."
        elif grade in ["C+", "C"]:
            return "📚 더 많은 연습이 필요합니다. 관련 자료를 다시 학습해보시기 바랍니다."
        else:
            return "🔄 기초부터 다시 학습하시는 것을 권장합니다. 멘토와 상담해보세요."
    
    def _update_user_progress(self, user_id: int, scenario_id: int, score: float):
        """사용자 진행 상황 업데이트"""
        progress = self.session.exec(
            select(SimulationProgress).where(SimulationProgress.user_id == user_id)
        ).first()
        
        if not progress:
            progress = SimulationProgress(user_id=user_id)
            self.session.add(progress)
        
        # 완료된 시나리오 목록 업데이트
        completed_scenarios = json.loads(progress.completed_scenarios)
        if scenario_id not in completed_scenarios:
            completed_scenarios.append(scenario_id)
        
        # 통계 업데이트
        progress.completed_scenarios = json.dumps(completed_scenarios)
        progress.total_attempts += 1
        progress.total_score += score
        progress.average_score = progress.total_score / progress.total_attempts
        progress.last_updated = datetime.utcnow()
        
        self.session.add(progress)
    
    def get_user_progress(self, user_id: int) -> Dict:
        """사용자 진행 상황 조회"""
        progress = self.session.exec(
            select(SimulationProgress).where(SimulationProgress.user_id == user_id)
        ).first()
        
        if not progress:
            return {
                "completed_scenarios": [],
                "total_attempts": 0,
                "total_score": 0.0,
                "average_score": 0.0,
                "category_scores": {},
                "recommended_scenarios": [],
                "weak_areas": [],
                "strong_areas": []
            }
        
        return {
            "completed_scenarios": json.loads(progress.completed_scenarios),
            "total_attempts": progress.total_attempts,
            "total_score": progress.total_score,
            "average_score": progress.average_score,
            "category_scores": json.loads(progress.category_scores),
            "recommended_scenarios": json.loads(progress.recommended_scenarios),
            "weak_areas": json.loads(progress.weak_areas),
            "strong_areas": json.loads(progress.strong_areas),
            "last_updated": progress.last_updated.isoformat()
        }
    
    def get_attempt_history(self, user_id: int, limit: int = 10) -> List[Dict]:
        """시뮬레이션 시도 기록 조회"""
        attempts = self.session.exec(
            select(SimulationAttempt)
            .where(SimulationAttempt.user_id == user_id)
            .order_by(SimulationAttempt.created_at.desc())
            .limit(limit)
        ).all()
        
        result = []
        for attempt in attempts:
            scenario = self.session.get(SimulationScenario, attempt.scenario_id)
            result.append({
                "id": attempt.id,
                "scenario_title": scenario.title if scenario else "알 수 없음",
                "category": scenario.category if scenario else "알 수 없음",
                "difficulty": scenario.difficulty if scenario else "알 수 없음",
                "total_score": attempt.total_score,
                "grade": attempt.grade,
                "duration_minutes": attempt.duration_minutes,
                "status": attempt.status,
                "completed_at": attempt.completed_at.isoformat() if attempt.completed_at else None
            })
        
        return result
