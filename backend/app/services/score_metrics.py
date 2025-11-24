"""
시뮬레이션 평가 지표 계산 모듈
6가지 세부 지표별 점수 산출 로직 구현
"""
import re
import json
from typing import Dict, List, Tuple, Optional
from collections import Counter
from pathlib import Path

from app.services.product_knowledge_service import ProductKnowledgeService


class ScoreMetrics:
    """시뮬레이션 평가 지표 계산 클래스"""
    
    def __init__(self, config: Optional[Dict] = None):
        """
        초기화
        
        Args:
            config: 평가 가중치 및 파라미터 설정
        """
        # 기본 가중치 설정 (파라미터화)
        self.weights = config.get("weights", {}) if config else {}
        self.weights.setdefault("knowledge", 0.20)
        self.weights.setdefault("skill", 0.20)
        self.weights.setdefault("empathy", 0.15)
        self.weights.setdefault("clarity", 0.15)
        self.weights.setdefault("kindness", 0.15)
        self.weights.setdefault("confidence", 0.15)
        
        # KB 권장용어 사전 로드
        self.recommended_terms = self._load_recommended_terms()
        
        # 제품 지식 서비스 초기화
        try:
            self.product_knowledge_service = ProductKnowledgeService()
            print("✅ 제품 지식 서비스 초기화 완료")
        except Exception as e:
            print(f"⚠️ 제품 지식 서비스 초기화 실패: {e}")
            self.product_knowledge_service = None
        
        # 각 지표별 세부 가중치 (파라미터화)
        self.clarity_weights = config.get("clarity_weights", {}) if config else {}
        self.clarity_weights.setdefault("structure", 0.4)
        self.clarity_weights.setdefault("logic", 0.3)
        self.clarity_weights.setdefault("terminology", 0.3)
        
        self.empathy_weights = config.get("empathy_weights", {}) if config else {}
        self.empathy_weights.setdefault("frequency", 0.4)
        self.empathy_weights.setdefault("context", 0.6)
        
        self.skill_weights = config.get("skill_weights", {}) if config else {}
        self.skill_weights.setdefault("flow", 0.4)
        self.skill_weights.setdefault("goal", 0.4)
        self.skill_weights.setdefault("feedback", 0.2)
    
    def _load_recommended_terms(self) -> Dict:
        """KB 권장용어 사전 로드"""
        try:
            terms_path = Path(__file__).parent.parent.parent / "data" / "kb_recommended_terms.json"
            with open(terms_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ KB 권장용어 사전 로드 실패: {e}")
            return {"recommended_terms": {}, "positive_expressions": {}, "negative_patterns": []}
    
    def calculate_knowledge_score(
        self,
        conversation: List[Dict],
        product_data: Optional[List[Dict]] = None,
        rag_context: Optional[str] = None
    ) -> Dict:
        """
        1️⃣ 지식 점수 계산 (상품 설명 정확성) - RAG 기반 강화 버전
        
        Args:
            conversation: 대화 로그 [{"role": "employee"|"customer", "text": "..."}]
            product_data: 상품 정보 데이터 (선택)
            rag_context: RAG 검색 컨텍스트 (선택)
        
        Returns:
            {
                "score": 85,
                "details": {
                    "rag_verified": True,
                    "total_claims": 10,
                    "accurate_claims": 8,
                    "inaccurate_claims": 2,
                    "accuracy_rate": 0.8,
                    "by_category": {...},
                    "errors": [...]
                },
                "reason": "설명"
            }
        """
        employee_utterances = [msg["text"] for msg in conversation if msg.get("role") == "employee"]
        
        if not employee_utterances:
            return {"score": 0, "details": {}, "reason": "직원 발화가 없습니다."}
        
        # RAG 기반 검증 (제품 지식 서비스 사용)
        if self.product_knowledge_service:
            return self._calculate_knowledge_score_with_rag(conversation)
        else:
            # Fallback: 기존 휴리스틱 방식
            return self._calculate_knowledge_score_heuristic(conversation)
    
    def _calculate_knowledge_score_with_rag(self, conversation: List[Dict]) -> Dict:
        """RAG 기반 지식 점수 계산 (제품 데이터와 실제 비교)"""
        print("🔍 RAG 기반 제품 지식 정확도 검증 시작...")
        
        # 대화 전체 검증
        # 🆕 LLM 기반 상품 코드 추출 사용 여부 (설정 파일에서 제어)
        from app.config import settings
        use_llm_extraction = settings.USE_LLM_EXTRACTION if hasattr(settings, 'USE_LLM_EXTRACTION') else False
        verification_result = self.product_knowledge_service.batch_verify_conversation(
            conversation,
            use_llm_extraction=use_llm_extraction  # 🆕 LLM 기반 상품 코드 추출
        )
        
        total_claims = verification_result["total_claims"]
        accurate_claims = verification_result["accurate_claims"]
        inaccurate_claims = verification_result["inaccurate_claims"]
        accuracy_rate = verification_result["accuracy_rate"]
        
        # 점수 계산 (정확도 기반)
        base_score = int(accuracy_rate * 100)
        
        # 정보 제공이 있었는지 확인
        employee_utterances = [msg["text"] for msg in conversation if msg.get("role") == "employee"]
        info_keywords = ["금리", "이자", "한도", "기간", "조건", "수수료", "혜택", "우대", "만기"]
        has_info = any(
            any(keyword in utterance for keyword in info_keywords)
            for utterance in employee_utterances
        )
        
        # 정보 제공이 없으면 기본 점수
        if total_claims == 0:
            if has_info:
                # 정보 언급은 있지만 구체적 수치가 없는 경우
                score = 60
                reason = "상품 정보를 언급했으나 구체적인 수치 제공이 부족합니다."
            else:
                score = 50
                reason = "구체적인 상품 정보 제공이 부족합니다."
        else:
            # 정확도가 이미 오류를 반영하고 있으므로, 오류 개수로 추가 감점하지 않음
            # 불확실한 표현은 전달력(자신감) 평가에서 다루므로 지식 점수에는 반영하지 않음
            score = base_score
            
            # 이유 생성
            if score >= 90:
                reason = f"상품 정보를 매우 정확하게 설명했습니다. ({accurate_claims}/{total_claims} 정확)"
            elif score >= 70:
                reason = f"상품 정보 설명이 대체로 정확합니다. ({accurate_claims}/{total_claims} 정확)"
            else:
                reason = f"정보 정확성 개선이 필요합니다. {inaccurate_claims}개 오류 발견 ({accurate_claims}/{total_claims} 정확)"
        
        # 오류 세부 정보 추출
        errors = []
        for verification in verification_result.get("verifications", []):
            if not verification.is_accurate:
                errors.append({
                    "claim": verification.claim,
                    "ground_truth": verification.ground_truth[:100] + "..." if len(verification.ground_truth) > 100 else verification.ground_truth,
                    "product": verification.product_code,
                    "category": verification.category,
                    "similarity_score": round(verification.similarity_score, 2)
                })
        
        print(f"  ✓ RAG 검증 완료: {accurate_claims}/{total_claims} 정확 (정확도: {accuracy_rate:.1%})")
        
        return {
            "score": score,
            "details": {
                "rag_verified": True,
                "total_claims": total_claims,
                "accurate_claims": accurate_claims,
                "inaccurate_claims": inaccurate_claims,
                "accuracy_rate": accuracy_rate,
                "by_category": verification_result["details"]["by_category"],
                "by_product": verification_result["details"]["by_product"],
                "errors": errors[:5]  # 상위 5개 오류만 표시
            },
            "reason": reason
        }
    
    def _calculate_knowledge_score_heuristic(self, conversation: List[Dict]) -> Dict:
        """휴리스틱 기반 지식 점수 계산 (Fallback)"""
        print("⚠️ RAG 서비스 없음 - 휴리스틱 방식으로 평가")
        
        employee_utterances = [msg["text"] for msg in conversation if msg.get("role") == "employee"]
        
        # 핵심 정보 항목 추출
        info_keywords = ["금리", "이자", "한도", "기간", "조건", "수수료", "혜택", "우대", "만기", "중도해지"]
        total_info_count = 0
        accurate_info_count = 0
        errors = []
        
        for utterance in employee_utterances:
            # 정보 제공 발화 확인
            info_mentions = sum(1 for keyword in info_keywords if keyword in utterance)
            total_info_count += info_mentions
            
            # 불확실한 표현 체크
            if info_mentions > 0:
                uncertain_patterns = ["같아요", "보이는데", "아닐까", "모르겠", "확실하진"]
                if not any(pattern in utterance for pattern in uncertain_patterns):
                    accurate_info_count += info_mentions
                else:
                    errors.append({
                        "utterance": utterance[:50] + "...",
                        "issue": "불확실한 표현 사용"
                    })
        
        # 점수 계산
        if total_info_count == 0:
            score = 50
            reason = "구체적인 상품 정보 제공이 부족합니다."
        else:
            accuracy_rate = accurate_info_count / total_info_count
            score = int(accuracy_rate * 100) - len(errors) * 10
            score = max(0, min(100, score))
            
            if score >= 90:
                reason = "상품 정보를 매우 정확하게 설명했습니다."
            elif score >= 70:
                reason = "상품 정보 설명이 대체로 정확합니다."
            else:
                reason = f"정보 정확성 개선이 필요합니다. ({len(errors)}개 문제)"
        
        return {
            "score": score,
            "details": {
                "rag_verified": False,
                "accurate_info_count": accurate_info_count,
                "total_info_count": total_info_count,
                "errors": errors,
                "accuracy_rate": accurate_info_count / total_info_count if total_info_count > 0 else 0
            },
            "reason": reason
        }
    
    def calculate_skill_score(
        self,
        conversation: List[Dict],
        goal_list: List[str],
        achieved_goals: List[int]
    ) -> Dict:
        """
        2️⃣ 기술 점수 계산 (응대 절차 및 목표 달성)
        
        Args:
            conversation: 대화 로그
            goal_list: 시뮬레이션 목표 리스트
            achieved_goals: 달성된 목표 인덱스 리스트
        
        Returns:
            {
                "score": 88,
                "details": {
                    "flow_score": 85,
                    "goal_achievement_rate": 0.8,
                    "feedback_loop_score": 90
                },
                "reason": "설명"
            }
        """
        # ① 대화 절차 구조 적합성 (Flow)
        flow_score = self._evaluate_conversation_flow(conversation)
        
        # ② 목표 달성도 (Goal Achievement)
        total_goals = len(goal_list)
        achieved_count = len(achieved_goals)
        goal_achievement_rate = achieved_count / total_goals if total_goals > 0 else 0
        goal_score = int(goal_achievement_rate * 100)
        
        # ③ 피드백 루프 (Feedback Loop)
        feedback_score = self._evaluate_feedback_loop(conversation)
        
        # 최종 점수 계산
        final_score = int(
            self.skill_weights["flow"] * flow_score +
            self.skill_weights["goal"] * goal_score +
            self.skill_weights["feedback"] * feedback_score
        )
        
        # 이유 생성
        if final_score >= 90:
            reason = f"응대 절차가 우수하며 목표 달성률이 높습니다. ({achieved_count}/{total_goals} 달성)"
        elif final_score >= 70:
            reason = f"응대 절차는 양호하나 일부 목표 미달성. ({achieved_count}/{total_goals} 달성)"
        else:
            reason = f"응대 절차와 목표 달성도 개선 필요. ({achieved_count}/{total_goals} 달성)"
        
        return {
            "score": final_score,
            "details": {
                "flow_score": flow_score,
                "goal_achievement_rate": goal_achievement_rate,
                "feedback_loop_score": feedback_score,
                "achieved_goals": achieved_count,
                "total_goals": total_goals
            },
            "reason": reason
        }
    
    def _evaluate_conversation_flow(self, conversation: List[Dict]) -> int:
        """대화 흐름 평가"""
        score = 100
        
        if len(conversation) < 3:
            return 50  # 대화가 너무 짧음
        
        # 인사 → 요구파악 → 정보제공 → 마무리 흐름 확인
        employee_utterances = [msg["text"] for msg in conversation if msg.get("role") == "employee"]
        
        # 인사 확인
        first_utterance = employee_utterances[0] if employee_utterances else ""
        greetings = ["안녕하세요", "반갑습니다", "환영합니다", "찾아주셔서"]
        has_greeting = any(greet in first_utterance for greet in greetings)
        if not has_greeting:
            score -= 10
        
        # 질문 확인 (요구 파악)
        question_patterns = ["무엇을", "어떤", "언제", "얼마", "어떻게", "?"]
        has_questions = any(
            any(pattern in utterance for pattern in question_patterns)
            for utterance in employee_utterances[:len(employee_utterances)//2]
        )
        if not has_questions:
            score -= 15
        
        # 마무리 확인
        last_utterance = employee_utterances[-1] if employee_utterances else ""
        closings = ["감사합니다", "도움이 되셨", "추가로 궁금", "또 방문", "좋은 하루"]
        has_closing = any(closing in last_utterance for closing in closings)
        if not has_closing:
            score -= 10
        
        return max(0, score)
    
    def _evaluate_feedback_loop(self, conversation: List[Dict]) -> int:
        """피드백 루프 평가 (요약 및 추가 확인)"""
        employee_utterances = [msg["text"] for msg in conversation if msg.get("role") == "employee"]
        
        if not employee_utterances:
            return 0
        
        # 마지막 몇 개 발화에서 요약/확인 표현 찾기
        last_utterances = employee_utterances[-3:]
        
        feedback_patterns = [
            "정리하면", "요약하면", "다시 말씀드리면",
            "추가로 궁금", "더 필요하신", "다른 도움",
            "확인해 드릴", "문의하실"
        ]
        
        has_feedback = any(
            any(pattern in utterance for pattern in feedback_patterns)
            for utterance in last_utterances
        )
        
        return 100 if has_feedback else 60
    
    def calculate_empathy_score(self, conversation: List[Dict]) -> Dict:
        """
        3️⃣ 공감도 점수 계산
        
        Args:
            conversation: 대화 로그
        
        Returns:
            {
                "score": 82,
                "details": {
                    "frequency_score": 80,
                    "context_score": 85,
                    "empathy_count": 3,
                    "total_utterances": 15
                },
                "reason": "설명"
            }
        """
        employee_utterances = [msg["text"] for msg in conversation if msg.get("role") == "employee"]
        
        if not employee_utterances:
            return {"score": 0, "details": {}, "reason": "직원 발화가 없습니다."}
        
        # 공감 표현 패턴
        empathy_patterns = self.recommended_terms.get("positive_expressions", {}).get("empathy", [])
        additional_empathy = [
            "이해합니다", "그러셨군요", "힘드셨겠어요", "불편하셨겠어요",
            "걱정되시", "고민이시", "어려우시", "답답하시"
        ]
        empathy_patterns.extend(additional_empathy)
        
        # 공감 표현 빈도 계산
        empathy_count = 0
        empathy_positions = []
        
        for idx, utterance in enumerate(employee_utterances):
            if any(pattern in utterance for pattern in empathy_patterns):
                empathy_count += 1
                empathy_positions.append(idx)
        
        total_utterances = len(employee_utterances)
        empathy_ratio = empathy_count / total_utterances if total_utterances > 0 else 0
        
        # ① 빈도 적정성 (3~10% 범위가 이상적)
        if 0.03 <= empathy_ratio <= 0.10:
            frequency_score = 100
        elif 0.01 <= empathy_ratio < 0.03:
            frequency_score = 70
        elif empathy_ratio > 0.10:
            frequency_score = 80  # 너무 많아도 감점
        else:
            frequency_score = 40
        
        # ② 맥락 적합성 (감정형 발화 직후 공감 표현)
        # 고객의 감정 표현 탐지
        customer_utterances = [
            (idx, msg["text"]) 
            for idx, msg in enumerate(conversation) 
            if msg.get("role") == "customer"
        ]
        
        emotion_patterns = [
            "왜 이렇게", "답답", "화나", "짜증", "불편", "걱정", 
            "어려워", "힘들", "복잡", "이상한데", "오래 걸려"
        ]
        
        emotional_moments = []
        for idx, text in customer_utterances:
            if any(pattern in text for pattern in emotion_patterns):
                emotional_moments.append(idx)
        
        # 감정 표현 직후 공감 확인
        contextual_empathy = 0
        for emotion_idx in emotional_moments:
            # 다음 직원 발화 확인
            next_employee_idx = next(
                (i for i, msg in enumerate(conversation[emotion_idx+1:], emotion_idx+1) 
                 if msg.get("role") == "employee"), 
                None
            )
            if next_employee_idx:
                employee_text = conversation[next_employee_idx].get("text", "")
                if any(pattern in employee_text for pattern in empathy_patterns):
                    contextual_empathy += 1
        
        context_score = int(
            (contextual_empathy / len(emotional_moments) * 100) 
            if emotional_moments else 70
        )
        
        # 최종 점수
        final_score = int(
            self.empathy_weights["frequency"] * frequency_score +
            self.empathy_weights["context"] * context_score
        )
        
        # 이유 생성
        if final_score >= 85:
            reason = "고객 감정에 적절히 공감하며 응대했습니다."
        elif final_score >= 70:
            reason = "공감 표현이 있으나 타이밍 개선이 필요합니다."
        else:
            reason = "고객 감정에 대한 공감 표현이 부족합니다."
        
        return {
            "score": final_score,
            "details": {
                "frequency_score": frequency_score,
                "context_score": context_score,
                "empathy_count": empathy_count,
                "total_utterances": total_utterances,
                "empathy_ratio": empathy_ratio,
                "contextual_empathy": contextual_empathy,
                "emotional_moments": len(emotional_moments)
            },
            "reason": reason
        }
    
    def calculate_clarity_score(self, conversation: List[Dict]) -> Dict:
        """
        4️⃣ 명확성 점수 계산
        
        Args:
            conversation: 대화 로그
        
        Returns:
            {
                "score": 86,
                "details": {
                    "structure_score": 85,
                    "logic_score": 90,
                    "terminology_score": 83,
                    "recommended_term_usage": 0.8
                },
                "reason": "설명"
            }
        """
        employee_utterances = [msg["text"] for msg in conversation if msg.get("role") == "employee"]
        
        if not employee_utterances:
            return {"score": 0, "details": {}, "reason": "직원 발화가 없습니다."}
        
        # ① 문장 구조의 명료성 (40%)
        structure_score = self._evaluate_sentence_structure(employee_utterances)
        
        # ② 정보 전달의 논리성 (30%)
        logic_score = self._evaluate_information_logic(employee_utterances)
        
        # ③ 용어의 평이성 (30%) - KB 권장용어 준수
        terminology_score, term_details = self._evaluate_terminology(employee_utterances)
        
        # 최종 점수
        final_score = int(
            self.clarity_weights["structure"] * structure_score +
            self.clarity_weights["logic"] * logic_score +
            self.clarity_weights["terminology"] * terminology_score
        )
        
        # 이유 생성
        if final_score >= 85:
            reason = "명확하고 이해하기 쉬운 언어로 설명했습니다."
        elif final_score >= 70:
            reason = "대체로 명확하나 일부 전문용어 사용이 있습니다."
        else:
            reason = "문장 구조와 용어 사용 개선이 필요합니다."
        
        return {
            "score": final_score,
            "details": {
                "structure_score": structure_score,
                "logic_score": logic_score,
                "terminology_score": terminology_score,
                "recommended_term_usage": term_details["usage_rate"],
                "jargon_count": term_details["jargon_count"],
                "recommended_terms_used": term_details["recommended_count"]
            },
            "reason": reason
        }
    
    def _evaluate_sentence_structure(self, utterances: List[str]) -> int:
        """문장 구조 명료성 평가"""
        score = 100
        
        for utterance in utterances:
            # 문장 길이 체크 (너무 길면 감점)
            sentence_count = len([s for s in utterance.split('.') if s.strip()])
            avg_length = len(utterance) / sentence_count if sentence_count > 0 else len(utterance)
            
            if avg_length > 100:  # 한 문장이 100자 초과
                score -= 5
            
            # 복합문 과다 사용 체크
            complex_markers = ["그리고", "또한", "하지만", "그러나", "따라서"]
            complex_count = sum(utterance.count(marker) for marker in complex_markers)
            if complex_count > 3:
                score -= 3
        
        return max(0, score)
    
    def _evaluate_information_logic(self, utterances: List[str]) -> int:
        """정보 전달 논리성 평가"""
        score = 100
        
        # 논리적 연결어 사용 확인
        logical_connectors = ["먼저", "다음으로", "그래서", "따라서", "예를 들어", "즉", "정리하면"]
        connector_count = sum(
            1 for utterance in utterances 
            if any(conn in utterance for conn in logical_connectors)
        )
        
        if connector_count < len(utterances) * 0.2:  # 20% 미만 사용
            score -= 15
        
        # 숫자나 구체적 정보 제공 확인
        has_numbers = any(re.search(r'\d+', utterance) for utterance in utterances)
        if not has_numbers:
            score -= 10
        
        return max(0, score)
    
    def _evaluate_terminology(self, utterances: List[str]) -> Tuple[int, Dict]:
        """용어 평이성 평가 (KB 권장용어 매칭)"""
        recommended_terms = self.recommended_terms.get("recommended_terms", {})
        forbidden_jargon = self.recommended_terms.get("forbidden_jargon", [])
        
        jargon_count = 0
        recommended_count = 0
        total_term_opportunities = 0
        
        full_text = " ".join(utterances)
        
        # 전문용어 사용 체크
        for jargon in forbidden_jargon:
            if jargon in full_text:
                jargon_count += 1
        
        # 권장용어 사용 체크
        for technical_term, term_info in recommended_terms.items():
            preferred = term_info.get("preferred", "")
            
            # 전문용어 사용 여부
            if technical_term in full_text:
                total_term_opportunities += 1
                # 권장용어로 설명했는지 확인
                if preferred and preferred in full_text:
                    recommended_count += 1
        
        # 사용률 계산
        usage_rate = recommended_count / total_term_opportunities if total_term_opportunities > 0 else 1.0
        
        # 점수 계산
        score = int(usage_rate * 100) - (jargon_count * 10)
        score = max(0, min(100, score))
        
        return score, {
            "usage_rate": usage_rate,
            "jargon_count": jargon_count,
            "recommended_count": recommended_count,
            "total_opportunities": total_term_opportunities
        }
    
    def calculate_kindness_score(self, conversation: List[Dict]) -> Dict:
        """
        5️⃣ 친절도 점수 계산
        
        Args:
            conversation: 대화 로그
        
        Returns:
            {
                "score": 92,
                "details": {
                    "positive_expression_count": 8,
                    "negative_expression_count": 1,
                    "positive_ratio": 0.15
                },
                "reason": "설명"
            }
        """
        employee_utterances = [msg["text"] for msg in conversation if msg.get("role") == "employee"]
        
        if not employee_utterances:
            return {"score": 0, "details": {}, "reason": "직원 발화가 없습니다."}
        
        # 긍정적/배려 표현
        positive_expressions = []
        for category, expressions in self.recommended_terms.get("positive_expressions", {}).items():
            positive_expressions.extend(expressions)
        
        # 부정적/명령형 표현
        negative_patterns = self.recommended_terms.get("negative_patterns", [])
        
        # 표현 카운트
        positive_count = 0
        negative_count = 0
        
        for utterance in employee_utterances:
            positive_count += sum(1 for expr in positive_expressions if expr in utterance)
            negative_count += sum(1 for pattern in negative_patterns if pattern in utterance)
        
        total_utterances = len(employee_utterances)
        positive_ratio = positive_count / total_utterances if total_utterances > 0 else 0
        
        # 점수 계산
        score = int(positive_ratio * 100) - (negative_count * 50)
        score = max(0, min(100, score))
        
        # 최소 점수 보정 (긍정 표현이 적어도 있으면)
        if positive_count > 0 and score < 50:
            score = 50
        
        # 이유 생성
        if score >= 85:
            reason = "매우 친절하고 배려 있는 응대입니다."
        elif score >= 70:
            reason = "친절한 응대이나 배려 표현을 더 추가하면 좋습니다."
        else:
            reason = f"친절도 개선 필요. 부정 표현 {negative_count}회 발견."
        
        return {
            "score": score,
            "details": {
                "positive_expression_count": positive_count,
                "negative_expression_count": negative_count,
                "positive_ratio": positive_ratio,
                "total_utterances": total_utterances
            },
            "reason": reason
        }
    
    def calculate_confidence_score(self, conversation: List[Dict]) -> Dict:
        """
        6️⃣ 자신감 점수 계산
        
        Args:
            conversation: 대화 로그
        
        Returns:
            {
                "score": 80,
                "details": {
                    "uncertain_count": 2,
                    "assertive_count": 12,
                    "uncertain_ratio": 0.14
                },
                "reason": "설명"
            }
        """
        employee_utterances = [msg["text"] for msg in conversation if msg.get("role") == "employee"]
        
        if not employee_utterances:
            return {"score": 0, "details": {}, "reason": "직원 발화가 없습니다."}
        
        # 모호한 표현 패턴
        uncertain_patterns = [
            "같아요", "같습니다", "일 수도 있어요", "일 수도 있습니다",
            "보입니다", "보이는데요", "아닐까요", "아닐까 합니다",
            "인 것 같은데요", "인 것 같습니다", "모르겠어요", "모르겠습니다",
            "확실하진 않지만", "확실하진 않은데", "아마도", "아마"
        ]
        
        # 단정형 어미
        assertive_patterns = [
            "합니다", "됩니다", "입니다", "있습니다", "없습니다",
            "가능합니다", "불가능합니다", "맞습니다", "그렇습니다"
        ]
        
        # 카운트
        uncertain_count = 0
        assertive_count = 0
        
        for utterance in employee_utterances:
            uncertain_count += sum(1 for pattern in uncertain_patterns if pattern in utterance)
            assertive_count += sum(1 for pattern in assertive_patterns if pattern in utterance)
        
        total_utterances = len(employee_utterances)
        uncertain_ratio = uncertain_count / total_utterances if total_utterances > 0 else 0
        
        # 점수 계산
        score = 100 - int(uncertain_ratio * 150)
        score += assertive_count * 2  # 단정형 어미 사용 가산점
        score = max(0, min(100, score))
        
        # 이유 생성
        if score >= 85:
            reason = "확신 있고 책임감 있게 안내했습니다."
        elif score >= 70:
            reason = "대체로 자신 있게 응대했으나 일부 모호한 표현이 있습니다."
        else:
            reason = f"불확실한 표현이 많습니다. ({uncertain_count}회) 자신감 있는 응대가 필요합니다."
        
        return {
            "score": score,
            "details": {
                "uncertain_count": uncertain_count,
                "assertive_count": assertive_count,
                "uncertain_ratio": uncertain_ratio,
                "total_utterances": total_utterances
            },
            "reason": reason
        }
    
    def calculate_total_score(self, scores: Dict[str, Dict]) -> Dict:
        """
        종합 점수 계산
        
        Args:
            scores: {
                "knowledge": {"score": 85, ...},
                "skill": {"score": 88, ...},
                ...
            }
        
        Returns:
            {
                "scores": {
                    "knowledge": 85,
                    "skill": 88,
                    "empathy": 82,
                    "clarity": 86,
                    "kindness": 92,
                    "confidence": 80
                },
                "total": 86,
                "weighted_total": 86.0,
                "grade": "A",
                "feedback_summary": "..."
            }
        """
        # 각 지표 점수 추출
        score_values = {
            key: scores[key]["score"]
            for key in ["knowledge", "skill", "empathy", "clarity", "kindness", "confidence"]
            if key in scores
        }
        
        # 가중 평균 계산
        weighted_total = sum(
            score_values.get(key, 0) * self.weights[key]
            for key in score_values
        )
        
        total_score = int(weighted_total)
        
        # 등급 산정
        if total_score >= 90:
            grade = "A+"
        elif total_score >= 85:
            grade = "A"
        elif total_score >= 80:
            grade = "B+"
        elif total_score >= 75:
            grade = "B"
        elif total_score >= 70:
            grade = "C+"
        elif total_score >= 65:
            grade = "C"
        else:
            grade = "D"
        
        # 피드백 요약 생성
        feedback_summary = self._generate_feedback_summary(scores, score_values)
        
        return {
            "scores": score_values,
            "total": total_score,
            "weighted_total": round(weighted_total, 2),
            "grade": grade,
            "feedback_summary": feedback_summary
        }
    
    def _generate_feedback_summary(self, scores: Dict[str, Dict], score_values: Dict[str, int]) -> str:
        """피드백 요약 생성"""
        strengths = []
        improvements = []
        
        metric_names = {
            "knowledge": "지식(상품 설명)",
            "skill": "기술(응대 절차)",
            "empathy": "공감도",
            "clarity": "명확성",
            "kindness": "친절도",
            "confidence": "자신감"
        }
        
        for key, score in score_values.items():
            name = metric_names.get(key, key)
            if score >= 85:
                strengths.append(name)
            elif score < 70:
                improvements.append(name)
        
        summary_parts = []
        
        if strengths:
            summary_parts.append(f"{', '.join(strengths)}은(는) 우수합니다")
        
        if improvements:
            summary_parts.append(f"{', '.join(improvements)} 개선이 필요합니다")
        
        if not improvements:
            summary_parts.append("전반적으로 우수한 응대입니다")
        
        return ". ".join(summary_parts) + "."

