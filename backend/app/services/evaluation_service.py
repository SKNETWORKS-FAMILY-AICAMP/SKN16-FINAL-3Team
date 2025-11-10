"""
시뮬레이션 평가 서비스
6가지 세부 지표(지식, 기술, 공감도, 명확성, 친절도, 자신감) 기반 종합 평가
"""
import json
from typing import Dict, List, Optional
from datetime import datetime
from sqlmodel import Session, select
from openai import OpenAI
import os

from app.services.score_metrics import ScoreMetrics
from app.models.rag_simulation import RAGSimulationSession, RAGSimulationTurn, RAGSimulationEvaluation
from app.models.user import User


class EvaluationService:
    """시뮬레이션 평가 서비스 - 6가지 지표 기반"""
    
    def __init__(self, session: Session, config: Optional[Dict] = None):
        """
        초기화
        
        Args:
            session: DB 세션
            config: 평가 설정 (가중치 등)
        """
        self.session = session
        self.config = config or {}
        self.score_metrics = ScoreMetrics(config)
        
        # OpenAI 클라이언트 초기화
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY 환경 변수가 설정되지 않았습니다.")
        self.openai_client = OpenAI(api_key=api_key)
    
    async def evaluate_session(
        self,
        session_key: str,
        use_llm: bool = True,
        llm_model: str = "gpt-4o"
    ) -> Dict:
        """
        시뮬레이션 세션 종합 평가
        
        Args:
            session_key: 세션 키
            use_llm: LLM 평가 사용 여부 (True면 LLM + Rule-based 병합, False면 Rule-based만)
            llm_model: 사용할 LLM 모델
        
        Returns:
            평가 결과 딕셔너리
        """
        # 세션 조회
        stmt = select(RAGSimulationSession).where(RAGSimulationSession.session_key == session_key)
        simulation_session = self.session.exec(stmt).first()
        
        if not simulation_session:
            raise ValueError(f"세션을 찾을 수 없습니다: {session_key}")
        
        # 대화 로그 조회
        turns = self.session.exec(
            select(RAGSimulationTurn)
            .where(RAGSimulationTurn.session_id == simulation_session.id)
            .order_by(RAGSimulationTurn.turn_index)
        ).all()
        
        if not turns:
            raise ValueError("대화 기록이 없습니다.")
        
        # 대화 로그를 표준 형식으로 변환
        conversation = self._convert_turns_to_conversation(turns)
        
        # 목표 정보 파싱 (situation_info에서 가져오기)
        situation_info = json.loads(simulation_session.situation_info) if simulation_session.situation_info else {}
        goal_list = situation_info.get("goals", [])
        
        # 달성된 목표 정보 파싱
        achieved_goals_data = json.loads(simulation_session.achieved_goals) if simulation_session.achieved_goals else {}
        achieved_goals = achieved_goals_data.get("achieved_indices", [])
        
        # Rule-based 평가 수행
        rule_based_scores = self._evaluate_rule_based(
            conversation=conversation,
            goal_list=goal_list,
            achieved_goals=achieved_goals
        )
        
        # LLM 평가 수행 (선택적)
        if use_llm:
            llm_scores = await self._evaluate_with_llm(
                conversation=conversation,
                goal_list=goal_list,
                achieved_goals=achieved_goals,
                model=llm_model
            )
            
            # Rule-based와 LLM 평가 병합 (가중 평균)
            final_scores = self._merge_scores(rule_based_scores, llm_scores)
        else:
            final_scores = rule_based_scores
        
        # 종합 점수 계산
        total_result = self.score_metrics.calculate_total_score(final_scores)
        
        # 평가 결과 저장
        evaluation = self._save_evaluation(
            simulation_session=simulation_session,
            scores=final_scores,
            total_result=total_result
        )
        
        # 결과 반환
        return {
            "session_id": session_key,
            "evaluation_id": evaluation.id,
            "score": {
                "knowledge": {"point": final_scores["knowledge"]["score"], "reason": final_scores["knowledge"]["reason"]},
                "skill": {"point": final_scores["skill"]["score"], "reason": final_scores["skill"]["reason"]},
                "empathy": {"point": final_scores["empathy"]["score"], "reason": final_scores["empathy"]["reason"]},
                "clarity": {"point": final_scores["clarity"]["score"], "reason": final_scores["clarity"]["reason"]},
                "kindness": {"point": final_scores["kindness"]["score"], "reason": final_scores["kindness"]["reason"]},
                "confidence": {"point": final_scores["confidence"]["score"], "reason": final_scores["confidence"]["reason"]},
                "total": total_result["total"]
            },
            "grade": total_result["grade"],
            "detail_feedback": {
                "feedback_summary": total_result["feedback_summary"],
                "knowledge_details": final_scores["knowledge"]["details"],
                "skill_details": final_scores["skill"]["details"],
                "empathy_details": final_scores["empathy"]["details"],
                "clarity_details": final_scores["clarity"]["details"],
                "kindness_details": final_scores["kindness"]["details"],
                "confidence_details": final_scores["confidence"]["details"]
            }
        }
    
    def _convert_turns_to_conversation(self, turns: List[RAGSimulationTurn]) -> List[Dict]:
        """대화 턴을 표준 형식으로 변환"""
        conversation = []
        for turn in turns:
            conversation.append({
                "role": turn.speaker_role,
                "text": turn.speaker_text
            })
        return conversation
    
    def _evaluate_rule_based(
        self,
        conversation: List[Dict],
        goal_list: List[str],
        achieved_goals: List[int]
    ) -> Dict:
        """Rule-based 평가 수행"""
        print("📊 Rule-based 평가 시작...")
        
        # 각 지표별 점수 계산
        knowledge_score = self.score_metrics.calculate_knowledge_score(
            conversation=conversation,
            product_data=None,  # 필요시 RAG 데이터 전달
            rag_context=None
        )
        print(f"  ✓ 지식: {knowledge_score['score']}점")
        
        skill_score = self.score_metrics.calculate_skill_score(
            conversation=conversation,
            goal_list=goal_list,
            achieved_goals=achieved_goals
        )
        print(f"  ✓ 기술: {skill_score['score']}점")
        
        empathy_score = self.score_metrics.calculate_empathy_score(
            conversation=conversation
        )
        print(f"  ✓ 공감도: {empathy_score['score']}점")
        
        clarity_score = self.score_metrics.calculate_clarity_score(
            conversation=conversation
        )
        print(f"  ✓ 명확성: {clarity_score['score']}점")
        
        kindness_score = self.score_metrics.calculate_kindness_score(
            conversation=conversation
        )
        print(f"  ✓ 친절도: {kindness_score['score']}점")
        
        confidence_score = self.score_metrics.calculate_confidence_score(
            conversation=conversation
        )
        print(f"  ✓ 자신감: {confidence_score['score']}점")
        
        return {
            "knowledge": knowledge_score,
            "skill": skill_score,
            "empathy": empathy_score,
            "clarity": clarity_score,
            "kindness": kindness_score,
            "confidence": confidence_score
        }
    
    async def _evaluate_with_llm(
        self,
        conversation: List[Dict],
        goal_list: List[str],
        achieved_goals: List[int],
        model: str = "gpt-4o"
    ) -> Dict:
        """LLM 기반 평가 수행"""
        print("🤖 LLM 평가 시작...")
        
        # LLM 평가 프롬프트 생성
        prompt = self._build_llm_evaluation_prompt(
            conversation=conversation,
            goal_list=goal_list,
            achieved_goals=achieved_goals
        )
        
        try:
            # OpenAI API 호출
            response = self.openai_client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "당신은 은행 신입행원 응대 시뮬레이션 평가 전문가입니다. 주어진 대화를 6가지 세부 지표로 평가하고 JSON 형식으로 결과를 반환합니다."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,
                max_tokens=2000,
                response_format={"type": "json_object"}
            )
            
            # 응답 파싱
            result_text = response.choices[0].message.content
            result = json.loads(result_text)
            
            print(f"  ✓ LLM 평가 완료")
            
            # 표준 형식으로 변환
            return self._convert_llm_result(result)
            
        except Exception as e:
            print(f"⚠️ LLM 평가 실패: {e}")
            # 실패 시 빈 결과 반환 (Rule-based만 사용)
            return {}
    
    def _build_llm_evaluation_prompt(
        self,
        conversation: List[Dict],
        goal_list: List[str],
        achieved_goals: List[int]
    ) -> str:
        """LLM 평가 프롬프트 생성"""
        # 대화 로그 포맷팅
        conversation_text = "\n".join([
            f"[{msg['role'].upper()}]: {msg['text']}"
            for msg in conversation
        ])
        
        # 목표 리스트 포맷팅
        goals_text = "\n".join([
            f"{i+1}. {goal} {'✓ (달성)' if i in achieved_goals else '✗ (미달성)'}"
            for i, goal in enumerate(goal_list)
        ])
        
        prompt = f"""다음은 은행 신입행원의 고객 응대 시뮬레이션 대화입니다. 아래 6가지 지표를 기준으로 평가하고 JSON 형식으로 결과를 반환해주세요.

📌 **평가 지표 및 기준**

**1️ 지식 (Knowledge, 0-100점)**
- 목적: 은행 상품(여신/수신 등)에 대한 설명이 정확한가
- 평가 기준:
  * 상품 정보(금리, 한도, 조건 등) 제공의 정확성
  * 잘못된 정보나 오류 발견 시 감점

**2️ 기술 (Skill, 0-100점)**
- 목적: 응대 절차가 체계적이며 목표를 달성했는가
- 평가 기준:
  * 대화 흐름: 인사 → 요구파악 → 정보제공 → 마무리
  * 목표 달성도: {len(achieved_goals)}/{len(goal_list)} 달성
  * 피드백 루프: 요약 및 추가 확인 여부

**3️ 공감도 (Empathy, 0-100점)**
- 목적: 고객 감정에 적절히 공감했는가
- 평가 기준:
  * 공감 표현 빈도: 전체 발화의 3-10%가 적정
  * 맥락 적합성: 고객의 감정 표현 직후 공감 응답
  * 예: "불편을 드려 죄송합니다", "이해합니다", "걱정되시겠어요"

**4️ 명확성 (Clarity, 0-100점)**
- 목적: 명확하고 이해하기 쉬운 언어 사용
- 평가 기준:
  * 문장 구조: 간결하고 명료한 문장 (100자 이내)
  * 논리성: 논리적 연결어 사용, 구체적 정보 제공
  * 용어 평이성: 전문용어보다 쉬운 말 사용 (예: "거치기간" → "이자만 내는 기간")

**5️ 친절도 (Kindness, 0-100점)**
- 목적: 고객 중심의 배려 있는 언어 사용
- 평가 기준:
  * 긍정 표현: "감사합니다", "도와드리겠습니다", "안내해 드리겠습니다"
  * 부정 표현 감점: "안 됩니다", "불가능합니다", "모르겠어요"

**6️ 자신감 (Confidence, 0-100점)**
- 목적: 확신 있고 책임감 있는 안내
- 평가 기준:
  * 단정형 어미: "합니다", "됩니다", "가능합니다"
  * 모호 표현 감점: "~같아요", "~일 수도", "확실하진 않지만"

───────────────────────────
📋 **대화 로그**
{conversation_text}

───────────────────────────
🎯 **시뮬레이션 목표**
{goals_text}

───────────────────────────
**출력 형식 (JSON)**
{{
  "knowledge": {{
    "score": 85,
    "reason": "상품 정보를 대체로 정확하게 설명했으나 일부 불확실한 표현 사용"
  }},
  "skill": {{
    "score": 88,
    "reason": "응대 절차가 체계적이며 대부분의 목표 달성"
  }},
  "empathy": {{
    "score": 82,
    "reason": "고객 감정에 적절히 공감했으나 타이밍 개선 여지"
  }},
  "clarity": {{
    "score": 86,
    "reason": "명확하고 이해하기 쉬운 설명"
  }},
  "kindness": {{
    "score": 92,
    "reason": "매우 친절하고 배려 있는 응대"
  }},
  "confidence": {{
    "score": 80,
    "reason": "대체로 자신 있으나 일부 모호한 표현 있음"
  }}
}}

위 형식으로 평가 결과를 JSON으로 반환해주세요."""
        
        return prompt
    
    def _convert_llm_result(self, llm_result: Dict) -> Dict:
        """LLM 결과를 표준 형식으로 변환"""
        standard_format = {}
        
        for metric in ["knowledge", "skill", "empathy", "clarity", "kindness", "confidence"]:
            if metric in llm_result:
                standard_format[metric] = {
                    "score": llm_result[metric].get("score", 0),
                    "reason": llm_result[metric].get("reason", ""),
                    "details": {}  # LLM은 세부 정보 없음
                }
        
        return standard_format
    
    def _merge_scores(self, rule_based: Dict, llm_based: Dict, rule_weight: float = 0.4, llm_weight: float = 0.6) -> Dict:
        """Rule-based와 LLM 평가 병합"""
        if not llm_based:
            return rule_based
        
        merged = {}
        
        for metric in ["knowledge", "skill", "empathy", "clarity", "kindness", "confidence"]:
            rule_score = rule_based.get(metric, {}).get("score", 0)
            llm_score = llm_based.get(metric, {}).get("score", 0)
            
            # 가중 평균
            final_score = int(rule_score * rule_weight + llm_score * llm_weight)
            
            # Rule-based의 세부 정보와 이유 유지, 점수만 병합
            merged[metric] = rule_based.get(metric, {}).copy()
            merged[metric]["score"] = final_score
            
            # 이유 병합 (Rule-based + LLM)
            rule_reason = rule_based.get(metric, {}).get("reason", "")
            llm_reason = llm_based.get(metric, {}).get("reason", "")
            merged[metric]["reason"] = f"{rule_reason} (LLM 평가: {llm_reason})"
        
        return merged
    
    def _save_evaluation(
        self,
        simulation_session: RAGSimulationSession,
        scores: Dict,
        total_result: Dict
    ) -> RAGSimulationEvaluation:
        """평가 결과 DB 저장"""
        evaluation = RAGSimulationEvaluation(
            session_id=simulation_session.id,
            user_id=simulation_session.user_id,
            knowledge_point=scores["knowledge"]["score"],
            skill_point=scores["skill"]["score"],
            empathy_point=scores["empathy"]["score"],
            clarity_point=scores["clarity"]["score"],
            kindness_point=scores["kindness"]["score"],
            confidence_point=scores["confidence"]["score"],
            total_point=total_result["total"],
            grade=total_result["grade"],
            feedback_summary=total_result["feedback_summary"],
            knowledge_reason=scores["knowledge"]["reason"],
            skill_reason=scores["skill"]["reason"],
            empathy_reason=scores["empathy"]["reason"],
            clarity_reason=scores["clarity"]["reason"],
            kindness_reason=scores["kindness"]["reason"],
            confidence_reason=scores["confidence"]["reason"],
            detail_json=json.dumps({
                "knowledge_details": scores["knowledge"]["details"],
                "skill_details": scores["skill"]["details"],
                "empathy_details": scores["empathy"]["details"],
                "clarity_details": scores["clarity"]["details"],
                "kindness_details": scores["kindness"]["details"],
                "confidence_details": scores["confidence"]["details"]
            }, ensure_ascii=False)
        )
        
        self.session.add(evaluation)
        self.session.commit()
        self.session.refresh(evaluation)
        
        print(f"✅ 평가 결과 저장 완료 (ID: {evaluation.id})")
        
        return evaluation
    
    def get_evaluation(self, session_key: str) -> Optional[Dict]:
        """저장된 평가 결과 조회"""
        # 세션 조회
        stmt = select(RAGSimulationSession).where(RAGSimulationSession.session_key == session_key)
        simulation_session = self.session.exec(stmt).first()
        
        if not simulation_session:
            return None
        
        # 평가 결과 조회
        eval_stmt = select(RAGSimulationEvaluation).where(
            RAGSimulationEvaluation.session_id == simulation_session.id
        ).order_by(RAGSimulationEvaluation.created_at.desc())
        evaluation = self.session.exec(eval_stmt).first()
        
        if not evaluation:
            return None
        
        # 세부 정보 파싱
        detail_json = json.loads(evaluation.detail_json) if evaluation.detail_json else {}
        
        return {
            "session_id": session_key,
            "evaluation_id": evaluation.id,
            "score": {
                "knowledge": {"point": evaluation.knowledge_point, "reason": evaluation.knowledge_reason},
                "skill": {"point": evaluation.skill_point, "reason": evaluation.skill_reason},
                "empathy": {"point": evaluation.empathy_point, "reason": evaluation.empathy_reason},
                "clarity": {"point": evaluation.clarity_point, "reason": evaluation.clarity_reason},
                "kindness": {"point": evaluation.kindness_point, "reason": evaluation.kindness_reason},
                "confidence": {"point": evaluation.confidence_point, "reason": evaluation.confidence_reason},
                "total": evaluation.total_point
            },
            "grade": evaluation.grade,
            "detail_feedback": {
                "feedback_summary": evaluation.feedback_summary,
                **detail_json
            },
            "created_at": evaluation.created_at.isoformat()
        }

