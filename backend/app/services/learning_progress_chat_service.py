"""
학습현황 분석 챗봇 서비스
사용자의 학습 데이터를 분석하고 개인화된 피드백과 추천을 제공
"""
from typing import Dict, List, Optional, Tuple
from sqlmodel import Session, select, func
from datetime import datetime, timedelta
import json
import re

from app.models.user import User
from app.models.mentor import ExamScore, ChatHistory
from app.models.simulation import SimulationAttempt, SimulationProgress
from app.models.simulation_feedback import SimulationFeedback
from app.models.rag_simulation import RAGSimulationSession


class LearningProgressChatService:
    """학습현황 분석 및 챗봇 응답 서비스"""
    
    def __init__(self, session: Session):
        self.session = session
        
        # 학습현황 관련 키워드
        self._learning_keywords = {
            "general": ["학습", "공부", "진도", "진행", "현황", "상황", "성과"],
            "score": ["성적", "점수", "시험", "평가", "결과"],
            "weak": ["약점", "부족", "취약", "못하는", "어려운", "보완", "약한", "낮은"],
            "strong": ["강점", "잘하는", "우수", "뛰어난", "높은", "좋은", "강한"],
            "relative": ["제일", "가장", "상대적", "그래도", "그중", "비교적"],
            "recommendation": ["추천", "해야", "공부해야", "학습해야", "보완해야"],
            "simulation": ["시뮬레이션", "실습", "연습"],
            "score": ["점수", "성적", "평가", "결과"],
            "improvement": ["개선률", "개선", "향상", "향상률", "주간", "주간개선률", "주간 향상", "개선률은", "개선률이"],
            "overall": ["전체", "종합", "요약", "정리"]
        }
    
    def is_learning_progress_query(self, message: str) -> bool:
        """학습현황 관련 쿼리인지 확인"""
        original_message = message
        message = message.lower().strip()
        
        # 학습현황 관련 키워드 확인
        for category, keywords in self._learning_keywords.items():
            for keyword in keywords:
                if keyword in message:
                    print(f"✅ [학습현황 쿼리 인식] 키워드 '{keyword}' 발견 (카테고리: {category})")
                    return True
        
        # 특정 패턴 확인
        patterns = [
            r"내\s*(학습|공부|성적|점수)",
            r"(어떻게|얼마나)\s*(공부|학습)",
            r"(무엇을|뭘)\s*(공부|학습)",
            r"(약점|강점).*뭐",
            r"추천.*해",
            r"학습현황",
            r"시뮬레이션\s*현황",
            r"시뮬레이션\s*상황",
            r"시뮬레이션\s*어떻게",
            r"시뮬레이션\s*어떤",
            r"시뮬레이션\s*어떠",
            r"시뮬레이션\s*점수",
            r"시뮬레이션\s*성적",
            r"시뮬레이션\s*평가",
            r"시뮬레이션\s*결과",
            r"내\s*시뮬레이션",
            r"시뮬레이션\s*주간",
            r"시뮬레이션\s*개선률",
            r"시뮬레이션\s*주간개선률",
            r"주간개선률",
            r"시뮬레이션.*개선률",
            r"개선률.*시뮬레이션",
        ]
        
        for pattern in patterns:
            if re.search(pattern, message):
                print(f"✅ [학습현황 쿼리 인식] 패턴 '{pattern}' 매칭")
                return True
        
        print(f"❌ [학습현황 쿼리 인식 실패] 메시지: '{original_message}'")
        return False
    
    def _resolve_context_references(self, message: str, context_history: Optional[List[Dict]] = None) -> str:
        """컨텍스트 히스토리를 활용하여 대명사/연결어 해석"""
        if not context_history or len(context_history) == 0:
            return message
        
        # 대명사 및 연결어 패턴
        pronouns = {
            "그거": None,
            "이거": None,
            "그것": None,
            "이것": None,
            "그럼": None,
            "그러면": None,
            "그래서": None,
            "그리고": None,
        }
        
        # 최근 대화에서 주제 추출
        recent_topics = []
        for hist in context_history[:3]:  # 최근 3개만 확인
            user_msg = hist.get("user_message", "").lower()
            bot_resp = hist.get("bot_response", "").lower()
            
            # 이전 질문에서 주요 키워드 추출
            for keyword_type, keywords in self._learning_keywords.items():
                for kw in keywords:
                    if kw in user_msg:
                        recent_topics.append({
                            "keyword": kw,
                            "type": keyword_type,
                            "message": user_msg
                        })
                        break
        
        # 대명사 해석
        message_lower = message.lower()
        resolved_message = message
        
        # "그거", "이거" 해석
        if any(pronoun in message_lower for pronoun in ["그거", "이거", "그것", "이것"]):
            if recent_topics:
                last_topic = recent_topics[0]
                # 마지막 주제를 참조로 사용
                if "시뮬레이션" in last_topic.get("message", ""):
                    resolved_message = message.replace("그거", "시뮬레이션").replace("이거", "시뮬레이션")
                    resolved_message = resolved_message.replace("그것", "시뮬레이션").replace("이것", "시뮬레이션")
                elif "점수" in last_topic.get("message", "") or "성적" in last_topic.get("message", ""):
                    resolved_message = message.replace("그거", "점수").replace("이거", "점수")
                    resolved_message = resolved_message.replace("그것", "점수").replace("이것", "점수")
                elif "약점" in last_topic.get("message", "") or "부족" in last_topic.get("message", ""):
                    resolved_message = message.replace("그거", "약점").replace("이거", "약점")
                    resolved_message = resolved_message.replace("그것", "약점").replace("이것", "약점")
                elif "강점" in last_topic.get("message", "") or "잘하는" in last_topic.get("message", ""):
                    resolved_message = message.replace("그거", "강점").replace("이거", "강점")
                    resolved_message = resolved_message.replace("그것", "강점").replace("이것", "강점")
        
        # "그럼", "그러면" 해석 - 이전 질문의 반대/연속 질문
        if "그럼" in message_lower or "그러면" in message_lower:
            if recent_topics:
                last_topic = recent_topics[0]
                topic_type = last_topic.get("type", "")
                # 반대 개념으로 해석
                if topic_type == "weak":
                    resolved_message = message.replace("그럼", "강점").replace("그러면", "강점")
                elif topic_type == "strong":
                    resolved_message = message.replace("그럼", "약점").replace("그러면", "약점")
        
        if resolved_message != message:
            print(f"🔄 [컨텍스트 해석] '{message}' → '{resolved_message}'")
        
        return resolved_message
    
    def _enhance_message_with_context(self, message: str, context_history: Optional[List[Dict]] = None) -> str:
        """컨텍스트를 활용하여 메시지 보강"""
        if not context_history or len(context_history) == 0:
            return message
        
        # 대명사 해석
        enhanced_message = self._resolve_context_references(message, context_history)
        
        # 메시지가 너무 짧고 컨텍스트가 있으면 보강
        if len(enhanced_message.strip()) < 3:
            # 최근 대화에서 주제 추출
            for hist in context_history[:1]:  # 가장 최근 대화만
                bot_resp = hist.get("bot_response", "")
                # 이전 응답에서 언급된 주제 확인
                if "시뮬레이션" in bot_resp and "시뮬레이션" not in enhanced_message:
                    enhanced_message = f"시뮬레이션 {enhanced_message}"
                elif "점수" in bot_resp and "점수" not in enhanced_message:
                    enhanced_message = f"점수 {enhanced_message}"
        
        return enhanced_message
    
    def get_query_type(self, message: str, context_history: Optional[List[Dict]] = None) -> str:
        """쿼리 유형 분석 (컨텍스트 히스토리 활용)"""
        # 컨텍스트를 활용하여 메시지 보강
        enhanced_message = self._enhance_message_with_context(message, context_history)
        message = enhanced_message.lower().strip()
        
        # 시뮬레이션 키워드 체크 (우선순위 높음 - 점수보다 먼저)
        has_simulation = any(kw in message for kw in self._learning_keywords["simulation"])
        
        # 주간개선률 체크 (약점/강점 체크보다 먼저 - "개선"이 약점 키워드에 포함되어 있어서)
        # "개선률", "향상률" 키워드가 있으면 주간개선률로 처리 (주간 키워드 없어도 됨)
        # "개선률은", "개선률이" 같은 변형도 인식 (조사 포함)
        improvement_rate_keywords = ["개선률", "향상률", "주간개선률", "개선률은", "개선률이", "개선률을", "개선률", "개선률이", "개선률을"]
        has_improvement_rate = any(kw in message for kw in improvement_rate_keywords)
        
        # "개선률"이 포함되어 있는지 직접 확인 (조사가 붙어도 인식)
        if "개선률" in message:
            has_improvement_rate = True
        
        if has_simulation and has_improvement_rate:
            print(f"✅ [주간개선률 인식] 시뮬레이션 + 개선률 키워드 발견")
            return "weekly_improvement"
        
        # improvement 키워드 중 "개선률" 관련이 아닌 것들도 체크 (예: "주간", "향상")
        if has_simulation:
            improvement_keywords_in_message = [kw for kw in self._learning_keywords["improvement"] if kw in message]
            # "개선" 단독은 제외 (약점 키워드와 혼동 방지), "개선률" 관련만 처리
            if any(kw in message for kw in ["개선률", "향상률", "주간"]):
                print(f"✅ [주간개선률 인식] 시뮬레이션 + improvement 키워드 발견: {improvement_keywords_in_message}")
                return "weekly_improvement"
        
        # 상대적 약점/강점 질문 체크 (우선순위 높음)
        has_relative = any(kw in message for kw in self._learning_keywords["relative"])
        has_weak = any(kw in message for kw in self._learning_keywords["weak"])
        has_strong = any(kw in message for kw in self._learning_keywords["strong"])
        
        # "어때"는 약점 키워드로 인식하지 않도록 (주간개선률 질문에서 사용됨)
        # "개선률", "주간개선률"이 있으면 약점으로 인식하지 않음
        has_improvement_keyword = any(kw in message for kw in ["개선률", "주간개선률", "향상률", "주간"])
        
        if has_relative and has_weak and not has_improvement_keyword:
            return "relative_weak_areas"
        elif has_relative and has_strong:
            return "relative_strong_areas"
        elif has_weak and not has_improvement_keyword:
            return "weak_areas"
        elif has_strong:
            return "strong_areas"
        elif has_simulation:
            # 시뮬레이션 키워드가 있으면 시뮬레이션으로 인식 (점수 키워드보다 우선)
            return "simulation"
        elif any(kw in message for kw in self._learning_keywords["recommendation"]):
            return "recommendation"
        elif any(kw in message for kw in self._learning_keywords["score"]):
            return "scores"
        else:
            return "overall"
    
    def analyze_learning_progress(self, user: User) -> Dict:
        """사용자의 학습현황 종합 분석"""
        try:
            # 1. 시험 성적 분석
            exam_analysis = self._analyze_exam_scores(user.id)
            
            # 2. 시뮬레이션 성과 분석
            simulation_analysis = self._analyze_simulation_progress(user.id)
            
            # 3. 채팅 활동 분석
            chat_analysis = self._analyze_chat_activity(user.id)
            
            # 4. 종합 분석
            overall_analysis = self._generate_overall_analysis(
                exam_analysis,
                simulation_analysis,
                chat_analysis
            )
            
            return {
                "exam": exam_analysis,
                "simulation": simulation_analysis,
                "chat": chat_analysis,
                "overall": overall_analysis,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            print(f"❌ [학습현황 분석 오류] {str(e)}")
            import traceback
            traceback.print_exc()
            # 기본값 반환
            return {
                "exam": {"has_data": False, "message": "분석 중 오류가 발생했습니다."},
                "simulation": {"has_data": False, "message": "분석 중 오류가 발생했습니다."},
                "chat": {"total_chats": 0, "recent_chats_30days": 0, "recent_topics": [], "engagement_level": "낮음"},
                "overall": {"level": "알 수 없음", "level_score": 0, "overall_weak_areas": [], "overall_strong_areas": [], "engagement": "낮음"},
                "timestamp": datetime.now().isoformat()
            }
    
    def _analyze_exam_scores(self, user_id: int) -> Dict:
        """시험 성적 분석"""
        statement = (
            select(ExamScore)
            .where(ExamScore.mentee_id == user_id)
            .order_by(ExamScore.exam_date.desc())
        )
        exams = list(self.session.exec(statement).all())
        
        if not exams:
            return {
                "has_data": False,
                "message": "아직 시험 기록이 없습니다."
            }
        
        latest_exam = exams[0]
        score_data = json.loads(latest_exam.score_data) if latest_exam.score_data else {}
        
        # 카테고리별 점수 분석
        categories = {
            "은행업무": score_data.get("은행업무", 0),
            "상품지식": score_data.get("상품지식", 0),
            "고객응대": score_data.get("고객응대", 0),
            "법규준수": score_data.get("법규준수", 0),
            "IT활용": score_data.get("IT활용", 0),
            "영업실적": score_data.get("영업실적", 0)
        }
        
        # 약점과 강점 파악 (절대적 기준)
        sorted_categories = sorted(categories.items(), key=lambda x: x[1])
        weak_areas = [cat for cat, score in sorted_categories[:2] if score < 70]
        strong_areas = [cat for cat, score in sorted_categories[-2:] if score >= 80]
        
        # 상대적 약점과 강점 (모든 점수가 우수해도 비교)
        relative_weak_areas = [cat for cat, score in sorted_categories[:3]]  # 하위 3개
        relative_strong_areas = [cat for cat, score in sorted_categories[-3:]]  # 상위 3개
        
        # 평균 점수 계산
        avg_score = sum(categories.values()) / len(categories) if categories else 0
        
        # 진척도 분석 (최근 3개 시험)
        trend = "stable"
        if len(exams) >= 2:
            recent_avg = sum(json.loads(e.score_data).values() if e.score_data else [0] 
                           for e in exams[:3]) / min(len(exams), 3)
            old_avg = sum(json.loads(e.score_data).values() if e.score_data else [0] 
                         for e in exams[-3:]) / min(len(exams), 3)
            
            if recent_avg > old_avg + 5:
                trend = "improving"
            elif recent_avg < old_avg - 5:
                trend = "declining"
        
        return {
            "has_data": True,
            "total_exams": len(exams),
            "latest_exam": {
                "name": latest_exam.exam_name,
                "date": latest_exam.exam_date.isoformat(),
                "score": latest_exam.total_score,
                "grade": latest_exam.grade
            },
            "categories": categories,
            "average_score": round(avg_score, 1),
            "weak_areas": weak_areas,
            "strong_areas": strong_areas,
            "relative_weak_areas": relative_weak_areas,
            "relative_strong_areas": relative_strong_areas,
            "trend": trend
        }
    
    def _analyze_simulation_progress(self, user_id: int) -> Dict:
        """시뮬레이션 진행 상황 분석"""
        
        # 시뮬레이션 진행 상황
        progress_statement = select(SimulationProgress).where(
            SimulationProgress.user_id == user_id
        )
        progress = self.session.exec(progress_statement).first()
        
        # 최근 시뮬레이션 시도
        attempts_statement = (
            select(SimulationAttempt)
            .where(SimulationAttempt.user_id == user_id)
            .order_by(SimulationAttempt.started_at.desc())
            .limit(10)
        )
        attempts = list(self.session.exec(attempts_statement).all())
        
        # RAG 시뮬레이션
        rag_sim_statement = (
            select(RAGSimulationSession)
            .where(RAGSimulationSession.user_id == user_id)
            .order_by(RAGSimulationSession.started_at.desc())
            .limit(10)
        )
        rag_sims = list(self.session.exec(rag_sim_statement).all())
        
        # 시뮬레이션 평가 결과 (대시보드에서 사용하는 데이터)
        feedback_statement = (
            select(SimulationFeedback)
            .where(SimulationFeedback.user_id == user_id)
            .order_by(SimulationFeedback.created_at.desc())
            .limit(10)
        )
        feedbacks = list(self.session.exec(feedback_statement).all())
        
        if not progress and not attempts and not rag_sims and not feedbacks:
            return {
                "has_data": False,
                "message": "아직 시뮬레이션 기록이 없습니다."
            }
        
        # 통계 계산
        total_attempts = len(attempts) + len(rag_sims) + len(feedbacks)
        
        # 점수 계산 (여러 소스에서)
        all_scores = []
        if attempts:
            scores = [a.final_score for a in attempts if a.final_score is not None]
            all_scores.extend(scores)
        
        # SimulationFeedback에서 점수 추출
        if feedbacks:
            feedback_scores = [f.overall_score for f in feedbacks if f.overall_score is not None]
            all_scores.extend(feedback_scores)
        
        avg_score = 0
        if all_scores:
            avg_score = sum(all_scores) / len(all_scores)
        
        # 최근 성과 (SimulationFeedback 포함)
        recent_performance = []
        
        # SimulationAttempt에서
        for attempt in attempts[:3]:
            recent_performance.append({
                "scenario": attempt.scenario_type or "일반",
                "score": attempt.final_score or 0,
                "date": attempt.started_at.isoformat() if attempt.started_at else "",
                "type": "attempt"
            })
        
        # SimulationFeedback에서
        for feedback in feedbacks[:5]:
            # persona_info나 situation_info에서 시나리오 정보 추출
            scenario_name = "일반"
            try:
                if feedback.persona_info:
                    import json
                    persona_data = json.loads(feedback.persona_info) if isinstance(feedback.persona_info, str) else feedback.persona_info
                    if isinstance(persona_data, dict):
                        scenario_name = persona_data.get("name", persona_data.get("persona_name", "일반"))
            except:
                pass
            
            recent_performance.append({
                "scenario": scenario_name,
                "score": feedback.overall_score or 0,
                "date": feedback.created_at.isoformat() if feedback.created_at else "",
                "grade": feedback.grade,
                "performance_level": feedback.performance_level,
                "type": "feedback",
                "knowledge_score": feedback.knowledge_score,
                "skill_score": feedback.skill_score,
                "empathy_score": feedback.empathy_score,
                "clarity_score": feedback.clarity_score,
                "kindness_score": feedback.kindness_score,
                "confidence_score": feedback.confidence_score
            })
        
        # 날짜순으로 정렬
        recent_performance.sort(key=lambda x: x.get("date", ""), reverse=True)
        recent_performance = recent_performance[:5]
        
        # progress가 None일 수 있으므로 안전하게 처리
        completed_scenarios = []
        weak_areas = []
        strong_areas = []
        
        if progress:
            try:
                if progress.completed_scenarios:
                    completed_scenarios = json.loads(progress.completed_scenarios)
            except (json.JSONDecodeError, TypeError):
                completed_scenarios = []
            
            try:
                if progress.weak_areas:
                    weak_areas = json.loads(progress.weak_areas)
            except (json.JSONDecodeError, TypeError):
                weak_areas = []
            
            try:
                if progress.strong_areas:
                    strong_areas = json.loads(progress.strong_areas)
            except (json.JSONDecodeError, TypeError):
                strong_areas = []
        
        return {
            "has_data": True,
            "total_attempts": total_attempts,
            "average_score": round(avg_score, 1) if avg_score else 0,
            "recent_performance": recent_performance,
            "completed_scenarios": completed_scenarios,
            "weak_areas": weak_areas,
            "strong_areas": strong_areas
        }
    
    def _analyze_chat_activity(self, user_id: int) -> Dict:
        """채팅 활동 분석"""
        
        # 전체 채팅 수
        total_statement = select(func.count(ChatHistory.id)).where(
            ChatHistory.user_id == user_id
        )
        total_chats = self.session.exec(total_statement).first() or 0
        
        # 최근 30일 채팅 수
        thirty_days_ago = datetime.now() - timedelta(days=30)
        recent_statement = select(func.count(ChatHistory.id)).where(
            ChatHistory.user_id == user_id,
            ChatHistory.created_at >= thirty_days_ago
        )
        recent_chats = self.session.exec(recent_statement).first() or 0
        
        # 최근 대화 주제
        recent_chats_statement = (
            select(ChatHistory)
            .where(ChatHistory.user_id == user_id)
            .order_by(ChatHistory.created_at.desc())
            .limit(10)
        )
        recent_chat_data = list(self.session.exec(recent_chats_statement).all())
        
        recent_topics = [
            chat.user_message[:50] + "..." if len(chat.user_message) > 50 else chat.user_message
            for chat in recent_chat_data
        ]
        
        return {
            "total_chats": total_chats,
            "recent_chats_30days": recent_chats,
            "recent_topics": recent_topics[:5],
            "engagement_level": self._calculate_engagement_level(total_chats, recent_chats)
        }
    
    def _calculate_engagement_level(self, total: int, recent: int) -> str:
        """학습 참여도 레벨 계산"""
        if recent >= 50:
            return "매우 활발"
        elif recent >= 20:
            return "활발"
        elif recent >= 10:
            return "보통"
        elif recent >= 5:
            return "낮음"
        else:
            return "매우 낮음"
    
    def _generate_overall_analysis(
        self,
        exam: Dict,
        simulation: Dict,
        chat: Dict
    ) -> Dict:
        """종합 분석 생성"""
        
        # 전체 학습 레벨 계산
        level_score = 0
        
        if exam.get("has_data"):
            level_score += min(exam["average_score"] / 100 * 40, 40)
        
        if simulation.get("has_data"):
            level_score += min(simulation["average_score"] / 100 * 30, 30)
        
        level_score += min(chat["total_chats"] / 100 * 30, 30)
        
        # 레벨 판정
        if level_score >= 80:
            level = "우수"
        elif level_score >= 60:
            level = "양호"
        elif level_score >= 40:
            level = "보통"
        else:
            level = "노력 필요"
        
        # 종합 약점과 강점
        all_weak_areas = []
        all_strong_areas = []
        
        if exam.get("has_data"):
            all_weak_areas.extend(exam["weak_areas"])
            all_strong_areas.extend(exam["strong_areas"])
        
        if simulation.get("has_data"):
            all_weak_areas.extend(simulation["weak_areas"])
            all_strong_areas.extend(simulation["strong_areas"])
        
        return {
            "level": level,
            "level_score": round(level_score, 1),
            "overall_weak_areas": list(set(all_weak_areas)),
            "overall_strong_areas": list(set(all_strong_areas)),
            "engagement": chat["engagement_level"]
        }
    
    def _check_recent_duplicate(self, message: str, context_history: Optional[List[Dict]] = None) -> Optional[str]:
        """최근 대화에서 중복 질문 확인 및 간단한 응답 제공"""
        if not context_history or len(context_history) == 0:
            return None
        
        message_lower = message.lower().strip()
        
        # 최근 대화와 유사한 질문인지 확인
        for hist in context_history[:1]:  # 가장 최근 대화만 확인
            prev_message = hist.get("user_message", "").lower().strip()
            prev_response = hist.get("bot_response", "")
            
            # 같은 주제의 질문인지 확인 (키워드 기반)
            common_keywords = ["점수", "성적", "약점", "강점", "시뮬레이션", "개선률", "학습현황"]
            message_has_keyword = any(kw in message_lower for kw in common_keywords)
            prev_has_keyword = any(kw in prev_message for kw in common_keywords)
            
            # 같은 키워드가 있고 메시지가 매우 유사하면 중복으로 간주
            if message_has_keyword and prev_has_keyword:
                # 메시지가 거의 동일한지 확인 (단어 단위로)
                message_words = set(message_lower.split())
                prev_words = set(prev_message.split())
                similarity = len(message_words & prev_words) / max(len(message_words | prev_words), 1)
                
                if similarity > 0.7:  # 70% 이상 유사하면 중복
                    # 시간 체크 (ISO 형식 파싱)
                    created_at_str = hist.get("created_at", "")
                    if created_at_str:
                        try:
                            # ISO 형식 파싱
                            if 'T' in created_at_str:
                                created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                            else:
                                created_at = datetime.fromisoformat(created_at_str)
                            
                            # timezone 제거 후 비교
                            if created_at.tzinfo:
                                created_at = created_at.replace(tzinfo=None)
                            
                            time_diff = (datetime.now() - created_at).total_seconds()
                            if time_diff < 300:  # 5분 이내
                                return f"💬 방금 말씀드린 내용입니다:\n\n{prev_response[:300]}..."
                        except Exception as e:
                            print(f"⚠️ [중복 체크] 시간 파싱 오류: {e}")
        
        return None
    
    def generate_response(self, user: User, message: str, context_history: Optional[List[Dict]] = None) -> str:
        """학습현황 관련 응답 생성 (컨텍스트 히스토리 활용)"""
        try:
            # 최근 중복 질문 확인
            duplicate_response = self._check_recent_duplicate(message, context_history)
            if duplicate_response:
                return duplicate_response
            
            # 컨텍스트 히스토리를 활용하여 쿼리 타입 분석
            query_type = self.get_query_type(message, context_history)
            analysis = self.analyze_learning_progress(user)
            
            # 컨텍스트 히스토리 로깅
            if context_history:
                print(f"📚 [컨텍스트 히스토리] {len(context_history)}개의 이전 대화 참조")
                for i, hist in enumerate(context_history[:2]):
                    print(f"  {i+1}. 사용자: {hist.get('user_message', '')[:50]}...")
            
            if query_type == "relative_weak_areas":
                return self._generate_relative_weak_areas_response(user, analysis)
            elif query_type == "relative_strong_areas":
                return self._generate_relative_strong_areas_response(user, analysis)
            elif query_type == "weak_areas":
                return self._generate_weak_areas_response(user, analysis)
            elif query_type == "strong_areas":
                return self._generate_strong_areas_response(user, analysis)
            elif query_type == "recommendation":
                return self._generate_recommendation_response(user, analysis)
            elif query_type == "scores":
                return self._generate_scores_response(user, analysis)
            elif query_type == "weekly_improvement":
                return self._generate_weekly_improvement_response(user, analysis)
            elif query_type == "simulation":
                return self._generate_simulation_response(user, analysis)
            else:
                return self._generate_overall_response(user, analysis)
        except Exception as e:
            print(f"❌ [학습현황 응답 생성 오류] {str(e)}")
            import traceback
            traceback.print_exc()
            return f"죄송합니다. 학습현황을 분석하는 중 오류가 발생했습니다. 다시 시도해주세요.\n\n오류: {str(e)}"
    
    def _generate_overall_response(self, user: User, analysis: Dict) -> str:
        """전체 학습현황 응답"""
        exam = analysis["exam"]
        simulation = analysis["simulation"]
        chat = analysis["chat"]
        overall = analysis["overall"]
        
        response = f"""📊 **{user.name}님의 학습현황 분석**

🎯 **종합 평가**: {overall['level']} (점수: {overall['level_score']}/100)
📈 **학습 참여도**: {overall['engagement']}

"""
        
        # 시험 성적
        if exam.get("has_data"):
            response += f"""📝 **시험 성적**
- 최근 시험: {exam['latest_exam']['name']} ({exam['latest_exam']['grade']})
- 평균 점수: {exam['average_score']}점
- 추세: {self._get_trend_emoji(exam['trend'])} {exam['trend']}

"""
        
        # 시뮬레이션
        if simulation.get("has_data"):
            response += f"""🎭 **시뮬레이션**
- 총 {simulation['total_attempts']}회 실습
- 평균 점수: {simulation['average_score']}점

"""
        
        # 채팅 활동
        response += f"""💬 **학습 활동**
- 전체 질문: {chat['total_chats']}회
- 최근 30일: {chat['recent_chats_30days']}회

"""
        
        # 약점과 강점
        if overall['overall_weak_areas']:
            response += f"""⚠️ **보완이 필요한 영역**
"""
            for area in overall['overall_weak_areas'][:3]:
                response += f"- {area}\n"
            response += "\n"
        
        if overall['overall_strong_areas']:
            response += f"""✨ **강점 영역**
"""
            for area in overall['overall_strong_areas'][:3]:
                response += f"- {area}\n"
            response += "\n"
        
        # 추천 사항
        response += self._generate_recommendations(analysis)
        
        return response
    
    def _generate_weak_areas_response(self, user: User, analysis: Dict) -> str:
        """약점 분석 응답"""
        exam = analysis["exam"]
        overall = analysis["overall"]
        
        response = f"""⚠️ **{user.name}님의 보완이 필요한 영역**

"""
        
        if not overall['overall_weak_areas'] and not exam.get('weak_areas'):
            hint = "\n\n💡 Tip: '그 와중에 제일 약한거' 또는 '상대적으로 약한 부분' 같이 물어보시면 상대적인 약점을 알려드릴 수 있어요!"
            return f"🎉 {user.name}님은 모든 영역에서 우수한 성과를 보이고 있습니다!\n계속 이 흐름을 유지하세요.{hint}"
        
        # 시험 기반 약점
        if exam.get("has_data") and exam['weak_areas']:
            response += f"""📝 **시험 성적 기반 약점**
"""
            for area in exam['weak_areas']:
                score = exam['categories'].get(area, 0)
                response += f"- **{area}**: {score}점\n"
                response += f"  💡 {self._get_study_tip(area)}\n\n"
        
        # 추천 학습 방법
        response += f"""🎯 **개선 방법**
"""
        for area in overall['overall_weak_areas'][:2]:
            response += f"- {self._get_improvement_suggestion(area)}\n"
        
        return response
    
    def _generate_relative_weak_areas_response(self, user: User, analysis: Dict) -> str:
        """상대적 약점 분석 응답 (모든 영역이 우수해도 비교)"""
        exam = analysis["exam"]
        
        if not exam.get("has_data"):
            return "아직 시험 기록이 없어서 비교할 수 없습니다. 첫 시험을 응시해보세요! 📝"
        
        response = f"""📊 **{user.name}님의 상대적 약점 분석**

모든 영역에서 우수한 성과를 보이고 계시네요! 👏
그래도 상대적으로 보완하면 좋을 영역을 알려드릴게요.

"""
        
        # 상대적 약점 (하위 3개)
        if exam.get('relative_weak_areas'):
            response += "📉 **상대적으로 낮은 점수 영역**\n"
            for i, area in enumerate(exam['relative_weak_areas'][:3], 1):
                score = exam['categories'].get(area, 0)
                emoji = "🥉" if i == 1 else "🥈" if i == 2 else "🥇"
                response += f"{i}. **{area}**: {score}점 {emoji}\n"
                response += f"   💡 {self._get_study_tip(area)}\n\n"
        
        # 평균과 비교
        avg_score = exam['average_score']
        response += f"""📈 **전체 평균**: {avg_score}점

💪 **추천 학습 전략**
위 영역들은 이미 우수하지만, 더 완벽해지기 위해:
"""
        
        for area in exam['relative_weak_areas'][:2]:
            response += f"- {self._get_improvement_suggestion(area)}\n"
        
        response += f"""
✨ 이미 훌륭한 성적이지만, 완벽을 향해 한 걸음 더 나아가세요!
"""
        
        return response
    
    def _generate_strong_areas_response(self, user: User, analysis: Dict) -> str:
        """강점 분석 응답"""
        exam = analysis["exam"]
        overall = analysis["overall"]
        
        response = f"""✨ **{user.name}님의 강점 영역**

"""
        
        if not overall['overall_strong_areas'] and not exam.get('strong_areas'):
            # 상대적 강점이라도 있으면 힌트 제공
            if exam.get("has_data") and exam.get('relative_strong_areas'):
                hint = "\n\n💡 Tip: '제일 강한 부분' 또는 '가장 높은 점수' 같이 물어보시면 상대적인 강점을 알려드릴 수 있어요!"
                return f"아직 두드러진 강점이 나타나지 않았지만, 꾸준히 학습하시면 곧 강점 영역이 생길 거예요! 💪{hint}"
            return f"아직 두드러진 강점이 나타나지 않았지만, 꾸준히 학습하시면 곧 강점 영역이 생길 거예요! 💪"
        
        # 시험 기반 강점
        if exam.get("has_data") and exam['strong_areas']:
            response += f"""📝 **시험 성적 기반 강점**
"""
            for area in exam['strong_areas']:
                score = exam['categories'].get(area, 0)
                response += f"- **{area}**: {score}점 🌟\n"
        
        response += f"""
👍 정말 훌륭합니다! 이 강점을 활용해서 다른 영역도 발전시켜보세요.
"""
        
        return response
    
    def _generate_relative_strong_areas_response(self, user: User, analysis: Dict) -> str:
        """상대적 강점 분석 응답 (상위 영역 순위 표시)"""
        exam = analysis["exam"]
        
        if not exam.get("has_data"):
            return "아직 시험 기록이 없어서 비교할 수 없습니다. 첫 시험을 응시해보세요! 📝"
        
        response = f"""🌟 **{user.name}님의 상대적 강점 분석**

{user.name}님이 특히 뛰어난 영역을 알려드릴게요! 👏

"""
        
        # 상대적 강점 (상위 3개)
        if exam.get('relative_strong_areas'):
            response += "📈 **가장 높은 점수 영역**\n"
            # 상위부터 표시하기 위해 역순
            top_areas = list(reversed(exam['relative_strong_areas'][-3:]))
            for i, area in enumerate(top_areas, 1):
                score = exam['categories'].get(area, 0)
                if i == 1:
                    emoji = "🥇"
                    praise = "최고입니다!"
                elif i == 2:
                    emoji = "🥈"
                    praise = "아주 훌륭해요!"
                else:
                    emoji = "🥉"
                    praise = "잘하고 계세요!"
                
                response += f"{i}. **{area}**: {score}점 {emoji} - {praise}\n"
        
        # 평균과 비교
        avg_score = exam['average_score']
        response += f"""
📊 **전체 평균**: {avg_score}점

✨ **{user.name}님의 강점 활용 전략**
"""
        
        # 강점 활용 제안
        if exam.get('relative_strong_areas'):
            top_area = exam['relative_strong_areas'][-1]
            response += f"""
💡 **{top_area}** 분야에서 특히 뛰어나시네요!
   - 이 강점을 살려 다른 분야 학습에도 적용해보세요
   - 동료들에게 {top_area} 관련 노하우를 공유하는 것도 좋습니다
   - 멘토링 활동에서 이 영역을 특화해보세요

"""
        
        # 격려 메시지
        if avg_score >= 90:
            response += "🎉 정말 탁월한 성과입니다! 계속 이 수준을 유지하세요!"
        elif avg_score >= 80:
            response += "👏 훌륭한 성과입니다! 이 강점을 더욱 발전시켜보세요!"
        else:
            response += "💪 좋은 출발입니다! 이 강점을 발판 삼아 더 성장해보세요!"
        
        return response
    
    def _generate_recommendation_response(self, user: User, analysis: Dict) -> str:
        """학습 추천 응답"""
        overall = analysis["overall"]
        exam = analysis["exam"]
        
        response = f"""🎯 **{user.name}님을 위한 맞춤 학습 추천**

"""
        
        response += self._generate_recommendations(analysis)
        
        return response
    
    def _generate_scores_response(self, user: User, analysis: Dict) -> str:
        """성적 상세 응답"""
        exam = analysis["exam"]
        
        if not exam.get("has_data"):
            return "아직 시험 기록이 없습니다. 첫 시험을 응시해보세요! 📝"
        
        response = f"""📊 **{user.name}님의 성적 분석**

📝 **최근 시험**
- 시험명: {exam['latest_exam']['name']}
- 날짜: {exam['latest_exam']['date'][:10]}
- 총점: {exam['latest_exam']['score']}점
- 등급: {exam['latest_exam']['grade']}

📈 **영역별 점수**
"""
        
        categories_sorted = sorted(
            exam['categories'].items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        for category, score in categories_sorted:
            emoji = "🌟" if score >= 80 else "⚠️" if score < 60 else "📌"
            response += f"{emoji} {category}: {score}점\n"
        
        response += f"""
**평균 점수**: {exam['average_score']}점
**추세**: {self._get_trend_emoji(exam['trend'])} {exam['trend']}
"""
        
        return response
    
    def _generate_simulation_response(self, user: User, analysis: Dict) -> str:
        """시뮬레이션 성과 응답"""
        try:
            simulation = analysis.get("simulation", {})
            
            if not simulation.get("has_data"):
                return "아직 시뮬레이션 기록이 없습니다. 실전 연습을 시작해보세요! 🎭"
            
            response = f"""🎭 **{user.name}님의 시뮬레이션 성과**

📊 **전체 통계**
- 총 실습 횟수: {simulation.get('total_attempts', 0)}회
- 평균 점수: {simulation.get('average_score', 0)}점

"""
            
            recent_performance = simulation.get('recent_performance', [])
            if recent_performance:
                response += "📈 **최근 시뮬레이션 결과**\n"
                for i, perf in enumerate(recent_performance[:5], 1):
                    scenario = perf.get('scenario', '일반')
                    score = perf.get('score', 0)
                    date = perf.get('date', '')[:10] if perf.get('date') else '날짜 없음'
                    grade = perf.get('grade', '')
                    perf_type = perf.get('type', '')
                    
                    # SimulationFeedback 데이터인 경우 상세 정보 표시
                    if perf_type == 'feedback':
                        performance_level = perf.get('performance_level', '')
                        response += f"{i}. **{scenario}** ({date})\n"
                        response += f"   - 종합 점수: {score}점"
                        if grade:
                            response += f" ({grade})"
                        if performance_level:
                            response += f" - {performance_level}"
                        response += "\n"
                        
                        # 세부 점수 표시
                        knowledge = perf.get('knowledge_score')
                        skill = perf.get('skill_score')
                        empathy = perf.get('empathy_score')
                        clarity = perf.get('clarity_score')
                        kindness = perf.get('kindness_score')
                        confidence = perf.get('confidence_score')
                        
                        if any([knowledge, skill, empathy, clarity, kindness, confidence]):
                            response += "   - 세부 평가:\n"
                            if knowledge is not None:
                                response += f"     • 지식: {knowledge}점\n"
                            if skill is not None:
                                response += f"     • 기술: {skill}점\n"
                            if empathy is not None:
                                response += f"     • 공감: {empathy}점\n"
                            if clarity is not None:
                                response += f"     • 명확성: {clarity}점\n"
                            if kindness is not None:
                                response += f"     • 친절함: {kindness}점\n"
                            if confidence is not None:
                                response += f"     • 자신감: {confidence}점\n"
                    else:
                        response += f"{i}. {scenario}: {score}점 ({date})\n"
                response += "\n"
            
            weak_areas = simulation.get('weak_areas', [])
            if weak_areas:
                response += "⚠️ **보완 필요 영역**\n"
                for area in weak_areas[:3]:
                    response += f"- {area}\n"
                response += "\n"
            
            strong_areas = simulation.get('strong_areas', [])
            if strong_areas:
                response += "✨ **강점 영역**\n"
                for area in strong_areas[:3]:
                    response += f"- {area}\n"
                response += "\n"
            
            completed_scenarios = simulation.get('completed_scenarios', [])
            if completed_scenarios:
                response += f"✅ **완료한 시나리오**: {len(completed_scenarios)}개\n\n"
            
            # 최근 시뮬레이션의 평균 점수 계산
            if recent_performance:
                recent_scores = [p.get('score', 0) for p in recent_performance if p.get('score', 0) > 0]
                if recent_scores:
                    recent_avg = sum(recent_scores) / len(recent_scores)
                    response += f"📊 **최근 평균 점수**: {recent_avg:.1f}점\n\n"
            
            response += "💡 실전 연습을 통해 실력이 향상되고 있습니다. 계속해서 도전하세요!"
            
            return response
        except Exception as e:
            print(f"❌ [시뮬레이션 응답 생성 오류] {str(e)}")
            import traceback
            traceback.print_exc()
            return f"시뮬레이션 현황을 불러오는 중 오류가 발생했습니다. 다시 시도해주세요."
    
    def _generate_weekly_improvement_response(self, user: User, analysis: Dict) -> str:
        """시뮬레이션 주간개선률 응답"""
        try:
            simulation = analysis.get("simulation", {})
            
            if not simulation.get("has_data"):
                return "아직 시뮬레이션 기록이 없습니다. 실전 연습을 시작해보세요! 🎭"
            
            # 최근 성과 데이터 가져오기
            recent_performance = simulation.get('recent_performance', [])
            
            if not recent_performance or len(recent_performance) < 2:
                return "주간개선률을 계산하기 위해서는 최소 2회 이상의 시뮬레이션 기록이 필요합니다. 더 많은 연습을 해보세요! 💪"
            
            # 날짜별로 점수 정리
            from datetime import datetime, timedelta
            now = datetime.now()
            week_ago = now - timedelta(days=7)
            two_weeks_ago = now - timedelta(days=14)
            
            # 최근 1주일 점수
            recent_week_scores = []
            # 1주일 전 ~ 2주일 전 점수
            previous_week_scores = []
            
            for perf in recent_performance:
                if not perf.get('date'):
                    continue
                try:
                    perf_date = datetime.fromisoformat(perf['date'].replace('Z', '+00:00'))
                    if perf_date.tzinfo:
                        perf_date = perf_date.replace(tzinfo=None)
                    
                    score = perf.get('score', 0)
                    if score > 0:
                        if perf_date >= week_ago:
                            recent_week_scores.append(score)
                        elif perf_date >= two_weeks_ago:
                            previous_week_scores.append(score)
                except:
                    continue
            
            # 개선률 계산
            if not recent_week_scores:
                return "최근 1주일 동안 시뮬레이션 기록이 없습니다. 더 많은 연습을 해보세요! 💪"
            
            recent_avg = sum(recent_week_scores) / len(recent_week_scores) if recent_week_scores else 0
            
            if previous_week_scores:
                previous_avg = sum(previous_week_scores) / len(previous_week_scores)
                if previous_avg > 0:
                    improvement_rate = ((recent_avg - previous_avg) / previous_avg) * 100
                else:
                    improvement_rate = 100 if recent_avg > 0 else 0
            else:
                # 이전 주 데이터가 없으면 전체 평균과 비교
                all_scores = [p.get('score', 0) for p in recent_performance if p.get('score', 0) > 0]
                if len(all_scores) > len(recent_week_scores):
                    previous_avg = sum(all_scores[:-len(recent_week_scores)]) / (len(all_scores) - len(recent_week_scores))
                    if previous_avg > 0:
                        improvement_rate = ((recent_avg - previous_avg) / previous_avg) * 100
                    else:
                        improvement_rate = 100 if recent_avg > 0 else 0
                else:
                    improvement_rate = 0
            
            response = f"""📈 **{user.name}님의 시뮬레이션 주간개선률**

📊 **최근 1주일 성과**
- 평균 점수: {recent_avg:.1f}점
- 시뮬레이션 횟수: {len(recent_week_scores)}회

"""
            
            if previous_week_scores:
                response += f"""📉 **이전 주 성과**
- 평균 점수: {previous_avg:.1f}점
- 시뮬레이션 횟수: {len(previous_week_scores)}회

"""
            
            # 개선률 표시
            if improvement_rate > 0:
                emoji = "📈"
                status = "향상"
                color = "양호"
            elif improvement_rate < 0:
                emoji = "📉"
                status = "하락"
                color = "주의"
                improvement_rate = abs(improvement_rate)
            else:
                emoji = "➡️"
                status = "유지"
                color = "보통"
            
            response += f"""{emoji} **주간개선률**: {improvement_rate:.1f}% ({status})

"""
            
            # 개선률에 따른 피드백
            if improvement_rate > 10:
                response += "🎉 정말 훌륭합니다! 꾸준한 향상을 보이고 계시네요. 이 기세를 유지하세요!\n\n"
            elif improvement_rate > 5:
                response += "👍 좋은 성장세입니다! 계속해서 연습하시면 더욱 발전할 수 있어요.\n\n"
            elif improvement_rate > 0:
                response += "💪 조금씩 향상되고 있습니다. 조금 더 집중하면 더 큰 발전이 있을 거예요.\n\n"
            elif improvement_rate == 0:
                response += "📌 현재 수준을 유지하고 있습니다. 새로운 시나리오에 도전해보세요!\n\n"
            else:
                response += "⚠️ 점수가 하락하고 있습니다. 복습과 추가 연습을 권장드립니다.\n\n"
            
            response += "💡 꾸준한 연습이 실력 향상의 핵심입니다. 매일 조금씩이라도 시뮬레이션을 해보세요!"
            
            return response
        except Exception as e:
            print(f"❌ [주간개선률 응답 생성 오류] {str(e)}")
            import traceback
            traceback.print_exc()
            return f"주간개선률을 계산하는 중 오류가 발생했습니다. 다시 시도해주세요."
    
    def _generate_recommendations(self, analysis: Dict) -> str:
        """학습 추천 생성"""
        overall = analysis["overall"]
        exam = analysis["exam"]
        
        recommendations = "💡 **추천 학습 계획**\n\n"
        
        # 약점 기반 추천
        if overall['overall_weak_areas']:
            recommendations += "**우선 학습 영역**\n"
            for i, area in enumerate(overall['overall_weak_areas'][:3], 1):
                recommendations += f"{i}. {area}\n"
                recommendations += f"   - {self._get_study_resource(area)}\n"
            recommendations += "\n"
        
        # 참여도 기반 추천
        engagement = overall['engagement']
        if engagement in ["낮음", "매우 낮음"]:
            recommendations += "**학습 활동 증대**\n"
            recommendations += "- 매일 10분씩 챗봇으로 질문하기\n"
            recommendations += "- 주 2회 이상 시뮬레이션 연습\n\n"
        
        # 추세 기반 추천
        if exam.get("has_data") and exam.get("trend") == "declining":
            recommendations += "**⚠️ 성적이 하락세입니다**\n"
            recommendations += "- 멘토님과 1:1 상담 권장\n"
            recommendations += "- 학습 방법 재검토 필요\n\n"
        
        recommendations += "📚 언제든지 질문이 있으면 챗봇에게 물어보세요!"
        
        return recommendations
    
    def _get_trend_emoji(self, trend: str) -> str:
        """추세 이모지 반환"""
        if trend == "improving":
            return "📈"
        elif trend == "declining":
            return "📉"
        else:
            return "➡️"
    
    def _get_study_tip(self, area: str) -> str:
        """영역별 학습 팁"""
        tips = {
            "은행업무": "기본 은행 업무 프로세스를 반복 학습하세요",
            "상품지식": "주요 금융상품의 특징과 차이점을 정리해보세요",
            "고객응대": "고객 응대 시뮬레이션을 반복 연습하세요",
            "법규준수": "금융 관련 법규를 사례 중심으로 학습하세요",
            "IT활용": "은행 시스템 활용법을 실습해보세요",
            "영업실적": "영업 스킬과 상품 추천 방법을 연습하세요"
        }
        return tips.get(area, "해당 영역의 기초부터 차근차근 학습하세요")
    
    def _get_improvement_suggestion(self, area: str) -> str:
        """개선 제안"""
        suggestions = {
            "은행업무": "은행 업무 매뉴얼을 읽고 챗봇에 질문하기",
            "상품지식": "매일 1개씩 금융상품 공부하고 정리하기",
            "고객응대": "고객 응대 시나리오 시뮬레이션 연습",
            "법규준수": "주요 금융법규 요약본 학습",
            "IT활용": "은행 시스템 튜토리얼 완료",
            "영업실적": "영업 화법 및 상품 추천 스킬 학습"
        }
        return suggestions.get(area, f"{area} 관련 학습 자료 복습하기")
    
    def _get_study_resource(self, area: str) -> str:
        """학습 자료 추천"""
        resources = {
            "은행업무": "RAG 챗봇에서 '은행업무 기초' 질문하기",
            "상품지식": "문서실에서 '금융상품 가이드' 읽기",
            "고객응대": "고객 응대 시뮬레이션 실습",
            "법규준수": "RAG 챗봇에서 '금융법규' 학습",
            "IT활용": "시스템 활용 가이드 문서 참고",
            "영업실적": "영업 시나리오 시뮬레이션 연습"
        }
        return resources.get(area, f"RAG 챗봇에서 '{area}' 질문하기")

