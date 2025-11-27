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
            "score": ["성적", "점수", "시험", "평가", "결과"],  # 단, "점수 추이"는 제외
            "weak": ["약점", "부족", "취약", "못하는", "어려운", "개선", "보완", "약한", "낮은"],
            "strong": ["강점", "잘하는", "우수", "뛰어난", "높은", "좋은", "강한"],
            "relative": ["제일", "가장", "상대적", "그래도", "그중", "비교적"],
            "recommendation": ["추천", "해야", "공부해야", "학습해야", "보완해야"],
            "simulation": ["시뮬레이션", "실습", "연습"],
            "overall": ["전체", "종합", "요약", "정리"],
            "weekly_improvement": ["주간", "주간개선", "주간개선률", "주간 개선", "주간 개선률", "이번주", "지난주", "주간 추이"],
            "simulation_history": ["시뮬레이션 기록", "시뮬레이션 히스토리", "전체 기록", "시뮬레이션 목록", "실습 기록", "시뮬레이션 내역"],
            "simulation_detail": ["시뮬레이션 상세", "피드백 상세", "상세보기", "시뮬레이션 결과", "평가 결과"],
            "simulation_recording": ["녹화", "시뮬레이션 녹화", "녹화본", "영상", "비디오"],
            "simulation_trend": ["시뮬레이션 추이", "시뮬레이션 점수 추이", "시뮬레이션 성과 추이", "시뮬레이션 변화", "시뮬레이션 트렌드", "실습 추이"],
            "exam_trend": ["시험 추이", "시험 점수 추이", "시험 성적 추이", "시험 성과 추이", "성적 추이", "시험 변화", "시험 트렌드"]
        }
    
    def is_learning_progress_query(self, message: str) -> bool:
        """학습현황 관련 쿼리인지 확인"""
        message = message.lower().strip()
        
        # 학습현황 관련 키워드 확인
        for category, keywords in self._learning_keywords.items():
            for keyword in keywords:
                if keyword in message:
                    return True
        
        # 특정 패턴 확인
        patterns = [
            r"내\s*(학습|공부|성적|점수)",
            r"(어떻게|얼마나)\s*(공부|학습)",
            r"(무엇을|뭘)\s*(공부|학습)",
            r"(약점|강점).*뭐",
            r"추천.*해",
        ]
        
        for pattern in patterns:
            if re.search(pattern, message):
                return True
        
        return False
    
    def get_query_type(self, message: str, context_history: Optional[List[Dict]] = None) -> str:
        """쿼리 유형 분석 (맥락 고려)"""
        message = message.lower().strip()
        
        # 맥락 분석: 이전 대화에서 시뮬레이션/시험 관련 키워드 확인
        context_simulation = False
        context_exam = False
        
        if context_history:
            # 최근 대화 히스토리에서 맥락 파악 (최신 대화 우선)
            for ctx in reversed(context_history[:5]):  # 최근 5개 대화를 역순으로 확인 (최신이 우선)
                ctx_text = (ctx.get("user_message", "") + " " + ctx.get("bot_response", "")).lower()
                # 시뮬레이션 관련 키워드 (더 구체적인 키워드 우선)
                if any(kw in ctx_text for kw in ["시뮬레이션", "실습", "연습", "시뮬레이션 점수", "시뮬레이션 성과", "시뮬레이션 결과"]):
                    context_simulation = True
                    # 시뮬레이션이 명확하면 시험 맥락은 덜 중요
                    if "시뮬레이션" in ctx_text:
                        break
                # 시험 관련 키워드
                if any(kw in ctx_text for kw in ["시험", "시험 성적", "시험 점수", "시험 결과", "평가", "성적"]):
                    context_exam = True
                    # 시험이 명확하면 시뮬레이션 맥락은 덜 중요
                    if "시험" in ctx_text:
                        break
        
        # 시뮬레이션 관련 질문 우선 체크 (강점/약점보다 먼저)
        has_simulation = any(kw in message for kw in self._learning_keywords["simulation"])
        
        # 상대적 약점/강점 질문 체크
        has_relative = any(kw in message for kw in self._learning_keywords["relative"])
        has_weak = any(kw in message for kw in self._learning_keywords["weak"])
        has_strong = any(kw in message for kw in self._learning_keywords["strong"])
        
        # 맥락 기반 강점/약점 처리
        # "강점은?", "약점은?" 같은 짧은 질문도 맥락으로 구분
        if (has_strong or has_weak) and not any(kw in message for kw in ["시뮬레이션", "시험", "실습", "성적", "점수"]):
            # 최근 대화에서 더 최신 맥락 확인 (최신 대화 우선)
            recent_context_simulation = False
            recent_context_exam = False
            recent_exam_keywords_count = 0
            recent_simulation_keywords_count = 0
            
            if context_history:
                # 최근 2개 대화만 확인 (더 최신 맥락)
                for ctx in reversed(context_history[:2]):
                    ctx_text = (ctx.get("user_message", "") + " " + ctx.get("bot_response", "")).lower()
                    # 시뮬레이션 관련 키워드 체크
                    sim_keywords = ["시뮬레이션", "실습", "연습"]
                    if any(kw in ctx_text for kw in sim_keywords):
                        recent_context_simulation = True
                        recent_simulation_keywords_count += sum(1 for kw in sim_keywords if kw in ctx_text)
                    # 시험 관련 키워드 체크 (더 구체적인 키워드 우선)
                    exam_keywords = ["시험성적", "시험 성적", "시험 점수", "시험 결과", "시험 평가", "시험", "성적", "평가"]
                    if any(kw in ctx_text for kw in exam_keywords):
                        recent_context_exam = True
                        # 명시적인 시험 키워드가 있으면 더 높은 우선순위
                        if any(kw in ctx_text for kw in ["시험성적", "시험 성적", "시험 점수", "시험 결과", "시험 평가"]):
                            recent_exam_keywords_count += 3  # 명시적 키워드는 가중치 높게
                        else:
                            recent_exam_keywords_count += 1
            
            # 최근 맥락에서 시험과 시뮬레이션이 모두 있으면, 더 명확한 쪽 우선
            # 시험 키워드가 더 많거나 명시적이면 시험 우선
            if recent_context_exam and recent_context_simulation:
                if recent_exam_keywords_count >= recent_simulation_keywords_count:
                    # 시험 맥락 우선
                    if has_relative and has_weak:
                        return "relative_weak_areas"
                    elif has_relative and has_strong:
                        return "relative_strong_areas"
                    elif has_weak:
                        return "weak_areas"
                    elif has_strong:
                        return "strong_areas"
                else:
                    # 시뮬레이션 맥락 우선
                    if has_relative and has_weak:
                        return "simulation_relative_weak_areas"
                    elif has_relative and has_strong:
                        return "simulation_relative_strong_areas"
                    elif has_weak:
                        return "simulation_weak_areas"
                    elif has_strong:
                        return "simulation_strong_areas"
            # 최근 맥락에서 시험만 있으면 시험 강점/약점
            elif recent_context_exam:
                if has_relative and has_weak:
                    return "relative_weak_areas"
                elif has_relative and has_strong:
                    return "relative_strong_areas"
                elif has_weak:
                    return "weak_areas"
                elif has_strong:
                    return "strong_areas"
            # 최근 맥락에서 시뮬레이션만 있으면 시뮬레이션 강점/약점
            elif recent_context_simulation:
                if has_relative and has_weak:
                    return "simulation_relative_weak_areas"
                elif has_relative and has_strong:
                    return "simulation_relative_strong_areas"
                elif has_weak:
                    return "simulation_weak_areas"
                elif has_strong:
                    return "simulation_strong_areas"
            # 최근 맥락이 없으면 전체 맥락 사용
            else:
                # 전체 맥락에서도 시험과 시뮬레이션 우선순위 판단
                if context_exam and context_simulation:
                    # 시험 맥락이 더 명확하면 시험 우선 (기본값)
                    if has_relative and has_weak:
                        return "relative_weak_areas"
                    elif has_relative and has_strong:
                        return "relative_strong_areas"
                    elif has_weak:
                        return "weak_areas"
                    elif has_strong:
                        return "strong_areas"
                elif context_exam:
                    if has_relative and has_weak:
                        return "relative_weak_areas"
                    elif has_relative and has_strong:
                        return "relative_strong_areas"
                    elif has_weak:
                        return "weak_areas"
                    elif has_strong:
                        return "strong_areas"
                elif context_simulation:
                    if has_relative and has_weak:
                        return "simulation_relative_weak_areas"
                    elif has_relative and has_strong:
                        return "simulation_relative_strong_areas"
                    elif has_weak:
                        return "simulation_weak_areas"
                    elif has_strong:
                        return "simulation_strong_areas"
        
        # 시뮬레이션과 강점/약점이 함께 있으면 시뮬레이션 강점/약점으로 처리
        if has_simulation:
            if has_weak:
                return "simulation_weak_areas"
            elif has_strong:
                return "simulation_strong_areas"
            elif has_relative and has_weak:
                return "simulation_relative_weak_areas"
            elif has_relative and has_strong:
                return "simulation_relative_strong_areas"
        
        # 시뮬레이션이 없으면 일반 강점/약점 처리
        if has_relative and has_weak:
            return "relative_weak_areas"
        elif has_relative and has_strong:
            return "relative_strong_areas"
        elif has_weak:
            return "weak_areas"
        elif has_strong:
            return "strong_areas"
        elif any(kw in message for kw in self._learning_keywords["recommendation"]):
            return "recommendation"
        
        # 명시적인 시험/학습현황 키워드 우선 체크 (시뮬레이션보다 먼저)
        # "학습현황", "시험성적", "시험 점수" 등 명시적 키워드가 있으면 시험 성적으로 처리
        has_explicit_exam = any(kw in message for kw in ["학습현황", "시험성적", "시험 점수", "시험 결과", "시험 평가"])
        has_explicit_simulation = any(kw in message for kw in ["시뮬레이션 점수", "시뮬레이션 성적", "시뮬레이션 결과", "시뮬레이션 평가"])
        
        # 시험 추이와 시뮬레이션 추이 구분 (score 체크보다 우선순위 높음)
        has_exam_trend = any(kw in message for kw in self._learning_keywords["exam_trend"])
        has_simulation_trend = any(kw in message for kw in self._learning_keywords["simulation_trend"])
        
        if has_exam_trend:
            return "exam_trend"
        elif has_simulation_trend:
            return "simulation_trend"
        # "점수 추이", "성과 추이" 등 추이 관련 키워드 체크 (score보다 우선)
        elif "점수 추이" in message or "성과 추이" in message or ("변화" in message and ("점수" in message or "성적" in message)) or ("트렌드" in message and ("점수" in message or "성적" in message)):
            # 시뮬레이션 관련 키워드가 명확히 있으면 시뮬레이션 추이 (우선)
            if any(kw in message for kw in ["시뮬레이션", "실습", "연습"]):
                return "simulation_trend"
            # 시험 관련 키워드가 있으면 시험 추이
            elif any(kw in message for kw in ["시험", "성적", "평가"]):
                return "exam_trend"
            # 둘 다 없으면 종합 추이 (시험과 시뮬레이션 모두)
            else:
                return "overall_trend"
        # 명시적인 시험 키워드가 있으면 시험 성적으로 우선 처리
        elif has_explicit_exam and not has_explicit_simulation:
            return "scores"
        # 명시적인 시뮬레이션 키워드가 있으면 시뮬레이션으로 처리
        elif has_explicit_simulation:
            if any(kw in message for kw in self._learning_keywords["simulation_recording"]):
                return "simulation_recording"
            elif any(kw in message for kw in self._learning_keywords["simulation_detail"]):
                return "simulation_detail"
            elif any(kw in message for kw in self._learning_keywords["simulation_history"]):
                return "simulation_history"
            elif any(kw in message for kw in self._learning_keywords["simulation_trend"]):
                return "simulation_trend"
            elif any(kw in message for kw in self._learning_keywords["weekly_improvement"]):
                return "weekly_improvement"
            return "simulation"
        # 시험 관련 키워드가 있으면 시험 성적으로 처리 (맥락보다 우선)
        elif any(kw in message for kw in self._learning_keywords["score"]):
            return "scores"
        # 시뮬레이션 관련 질문 체크 (명시적 키워드가 없을 때만 맥락 사용)
        elif any(kw in message for kw in self._learning_keywords["simulation"]):
            # 시뮬레이션 관련 세부 질문 우선 처리
            if any(kw in message for kw in self._learning_keywords["simulation_recording"]):
                return "simulation_recording"
            elif any(kw in message for kw in self._learning_keywords["simulation_detail"]):
                return "simulation_detail"
            elif any(kw in message for kw in self._learning_keywords["simulation_history"]):
                return "simulation_history"
            elif any(kw in message for kw in self._learning_keywords["simulation_trend"]):
                return "simulation_trend"
            elif any(kw in message for kw in self._learning_keywords["weekly_improvement"]):
                return "weekly_improvement"
            # "시뮬레이션 점수" 같은 질문도 시뮬레이션으로 처리
            return "simulation"
        # 맥락 기반 처리 (명시적 키워드가 없을 때만)
        elif context_exam and not context_simulation:
            # 맥락에서 시험이 있었고, 시뮬레이션이 없으면 시험 성적으로 처리
            return "scores"
        elif context_simulation and not context_exam:
            # 맥락에서 시뮬레이션이 있었고, 시험이 없으면 시뮬레이션으로 처리
            if any(kw in message for kw in self._learning_keywords["simulation_recording"]):
                return "simulation_recording"
            elif any(kw in message for kw in self._learning_keywords["simulation_detail"]):
                return "simulation_detail"
            elif any(kw in message for kw in self._learning_keywords["simulation_history"]):
                return "simulation_history"
            elif any(kw in message for kw in self._learning_keywords["simulation_trend"]):
                return "simulation_trend"
            elif any(kw in message for kw in self._learning_keywords["weekly_improvement"]):
                return "weekly_improvement"
            return "simulation"
        elif any(kw in message for kw in self._learning_keywords["weekly_improvement"]):
            return "weekly_improvement"
        elif any(kw in message for kw in self._learning_keywords["simulation_history"]):
            return "simulation_history"
        elif any(kw in message for kw in self._learning_keywords["simulation_detail"]):
            return "simulation_detail"
        elif any(kw in message for kw in self._learning_keywords["simulation_recording"]):
            return "simulation_recording"
        else:
            return "overall"
    
    def analyze_learning_progress(self, user: User) -> Dict:
        """사용자의 학습현황 종합 분석 (대시보드 데이터 기반)"""
        
        # 대시보드 데이터 가져오기
        dashboard_data = self._get_dashboard_data(user)
        
        # 대시보드 데이터를 기반으로 분석
        # 1. 시험 성적 분석 (대시보드의 exam_scores 사용)
        exam_analysis = self._analyze_exam_scores_from_dashboard(dashboard_data)
        
        # 2. 시뮬레이션 성과 분석 (대시보드의 simulation_results 사용)
        simulation_analysis = self._analyze_simulation_from_dashboard(dashboard_data)
        
        # 3. 채팅 활동 분석 (대시보드의 learning_progress 사용)
        chat_analysis = self._analyze_chat_from_dashboard(dashboard_data)
        
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
    
    def _get_dashboard_data(self, user: User) -> Dict:
        """대시보드 데이터 가져오기 (대시보드 라우터 로직 재사용)"""
        from app.routers.dashboard import get_mentee_dashboard
        from app.database import get_session
        
        # 대시보드 라우터 함수를 직접 호출하여 데이터 가져오기
        # 하지만 순환 참조를 피하기 위해 직접 DB 조회 로직을 재사용
        from app.models.mentor import ExamScore, ChatHistory, Feedback
        from sqlmodel import select, func
        import json
        
        # 시험 점수 조회 (대시보드와 동일한 로직) - 최신 데이터만 가져오기
        exam_statement = (
            select(ExamScore)
            .where(ExamScore.mentee_id == user.id)
            .order_by(ExamScore.exam_date.desc(), ExamScore.id.desc())  # 날짜와 ID 모두 내림차순으로 최신 데이터 보장
        )
        exams = list(self.session.exec(exam_statement).all())
        
        # 디버깅: 최신 시험 점수 확인
        if exams:
            latest_exam = exams[0]
            print(f"🔍 [챗봇] 최신 시험 점수 조회: exam_id={latest_exam.id}, exam_date={latest_exam.exam_date}, total_score={latest_exam.total_score}")
        
        exam_scores = []
        for exam in exams:
            exam_scores.append({
                "id": exam.id,
                "exam_name": exam.exam_name,
                "exam_date": exam.exam_date.isoformat(),
                "score_data": json.loads(exam.score_data) if exam.score_data else {},
                "total_score": exam.total_score,
                "grade": exam.grade,
                "feedback": exam.feedback
            })
        
        # 학습 진행도 (대시보드와 동일한 로직)
        chat_count_statement = select(func.count(ChatHistory.id)).where(
            ChatHistory.user_id == user.id
        )
        total_chats = self.session.exec(chat_count_statement).first() or 0
        
        # 최근 대화 주제 추출
        recent_chats_statement = (
            select(ChatHistory)
            .where(ChatHistory.user_id == user.id)
            .order_by(ChatHistory.created_at.desc())
            .limit(20)
        )
        recent_chats_data = list(self.session.exec(recent_chats_statement).all())
        
        recent_topics = []
        for chat in recent_chats_data:
            if chat.user_message:
                topic = chat.user_message[:50]
                recent_topics.append(topic)
        
        # 시뮬레이션 평가 결과 조회 (대시보드와 동일한 로직) - 최신 데이터만 가져오기
        simulation_feedbacks_statement = (
            select(SimulationFeedback)
            .where(SimulationFeedback.user_id == user.id)
            .order_by(SimulationFeedback.created_at.desc(), SimulationFeedback.id.desc())  # 날짜와 ID 모두 내림차순으로 최신 데이터 보장
            .limit(10)
        )
        simulation_feedbacks = list(self.session.exec(simulation_feedbacks_statement).all())
        
        # 디버깅: 최신 시뮬레이션 피드백 확인
        if simulation_feedbacks:
            latest_feedback = simulation_feedbacks[0]
            print(f"🔍 [챗봇] 최신 시뮬레이션 피드백 조회: feedback_id={latest_feedback.id}, created_at={latest_feedback.created_at}, overall_score={latest_feedback.overall_score}")
        
        simulation_results = []
        for sf in simulation_feedbacks:
            simulation_results.append({
                "id": sf.id,
                "overall_score": sf.overall_score,
                "grade": sf.grade,
                "performance_level": sf.performance_level,
                "knowledge_score": sf.knowledge_score,
                "skill_score": sf.skill_score,
                "clarity_score": sf.clarity_score,
                "kindness_score": sf.kindness_score,
                "confidence_score": sf.confidence_score,
                "delivery_score": (sf.clarity_score + sf.confidence_score) / 2.0,
                "summary": sf.summary,
                "improvements": sf.improvements,
                "persona_id": sf.persona_id,
                "situation_id": sf.situation_id,
                "persona_info": sf.persona_info,
                "situation_info": sf.situation_info,
                "total_turns": sf.total_turns,
                "duration_seconds": sf.duration_seconds,
                "created_at": sf.created_at.isoformat()
            })
        
        # 성과 지표 (대시보드와 동일한 로직)
        performance_scores = {
            "banking": 0,
            "product_knowledge": 0,
            "customer_service": 0,
            "compliance": 0,
            "it_usage": 0,
            "sales_performance": 0
        }
        
        if exams:
            latest_exam = exams[0]
            if latest_exam.score_data:
                score_data = json.loads(latest_exam.score_data)
                
                # 대시보드에 표시되는 카테고리 매핑 (금융영업, 상품개발 및 운용 등)
                # 기존 카테고리도 지원하되, 새로운 카테고리도 매핑
                performance_scores = {
                    "banking": score_data.get("은행업무", score_data.get("은행지식 및 관련법률", 0)),
                    "product_knowledge": score_data.get("상품지식", score_data.get("상품개발 및 운용", 0)),
                    "customer_service": score_data.get("고객응대", 0),
                    "compliance": score_data.get("법규준수", score_data.get("신용분석 및 리스크관리", 0)),
                    "it_usage": score_data.get("IT활용", 0),
                    "sales_performance": score_data.get("영업실적", score_data.get("금융영업", 0))
                }
                
                # 새로운 카테고리도 직접 매핑
                if "금융영업" in score_data:
                    performance_scores["sales_performance"] = score_data.get("금융영업", 0)
                if "상품개발 및 운용" in score_data:
                    performance_scores["product_knowledge"] = score_data.get("상품개발 및 운용", 0)
                if "신용분석 및 리스크관리" in score_data:
                    performance_scores["compliance"] = score_data.get("신용분석 및 리스크관리", 0)
                if "외환" in score_data:
                    performance_scores["banking"] = max(performance_scores.get("banking", 0), score_data.get("외환", 0))
                if "은행지식 및 관련법률" in score_data:
                    performance_scores["banking"] = max(performance_scores.get("banking", 0), score_data.get("은행지식 및 관련법률", 0))
                if "하경은행" in score_data:
                    performance_scores["banking"] = max(performance_scores.get("banking", 0), score_data.get("하경은행", 0))
                
                print(f"🔍 [챗봇] 성과 지표 계산: {performance_scores}, 원본 score_data: {score_data}")
        
        return {
            "user_id": user.id,
            "exam_scores": exam_scores,
            "total_chats": total_chats,
            "recent_topics": recent_topics,
            "simulation_results": simulation_results,
            "performance_scores": performance_scores
        }
    
    def _analyze_exam_scores_from_dashboard(self, dashboard_data: Dict) -> Dict:
        """대시보드 데이터에서 시험 성적 분석"""
        exam_scores = dashboard_data.get("exam_scores", [])
        
        if not exam_scores:
            return {
                "has_data": False,
                "message": "아직 시험 기록이 없습니다."
            }
        
        latest_exam = exam_scores[0]
        score_data = latest_exam.get("score_data", {})
        
        # score_data가 딕셔너리가 아닌 경우 처리
        if not isinstance(score_data, dict):
            score_data = {}
        
        # 카테고리별 점수 분석 (명시적으로 숫자로 변환)
        categories = {
            "은행업무": float(score_data.get("은행업무", 0)) if score_data.get("은행업무") is not None else 0,
            "상품지식": float(score_data.get("상품지식", 0)) if score_data.get("상품지식") is not None else 0,
            "고객응대": float(score_data.get("고객응대", 0)) if score_data.get("고객응대") is not None else 0,
            "법규준수": float(score_data.get("법규준수", 0)) if score_data.get("법규준수") is not None else 0,
            "IT활용": float(score_data.get("IT활용", 0)) if score_data.get("IT활용") is not None else 0,
            "영업실적": float(score_data.get("영업실적", 0)) if score_data.get("영업실적") is not None else 0
        }
        
        # total_score가 있으면 그것을 우선 사용, 없으면 카테고리 평균 사용
        total_score = latest_exam.get("total_score", 0)
        if total_score and total_score > 0:
            avg_score = float(total_score)
        else:
            # 카테고리별 점수의 평균 계산
            valid_scores = [v for v in categories.values() if v > 0]
            avg_score = sum(valid_scores) / len(valid_scores) if valid_scores else 0
        
        # 약점과 강점 파악
        sorted_categories = sorted(categories.items(), key=lambda x: x[1])
        weak_areas = [cat for cat, score in sorted_categories[:2] if score < 70]
        strong_areas = [cat for cat, score in sorted_categories[-2:] if score >= 80]
        
        relative_weak_areas = [cat for cat, score in sorted_categories[:3]]
        relative_strong_areas = [cat for cat, score in sorted_categories[-3:]]
        
        # 추세 분석
        trend = "stable"
        if len(exam_scores) >= 2:
            recent_score_data = exam_scores[0].get("score_data", {})
            old_score_data = exam_scores[-1].get("score_data", {})
            
            if recent_score_data and old_score_data:
                recent_values = [v for v in recent_score_data.values() if isinstance(v, (int, float))]
                old_values = [v for v in old_score_data.values() if isinstance(v, (int, float))]
                
                if recent_values and old_values:
                    recent_avg = sum(recent_values) / len(recent_values)
                    old_avg = sum(old_values) / len(old_values)
                    
                    if recent_avg > old_avg + 5:
                        trend = "improving"
                    elif recent_avg < old_avg - 5:
                        trend = "declining"
        
        return {
            "has_data": True,
            "total_exams": len(exam_scores),
            "latest_exam": {
                "name": latest_exam.get("exam_name", ""),
                "date": latest_exam.get("exam_date", ""),
                "score": latest_exam.get("total_score", 0),
                "grade": latest_exam.get("grade", "")
            },
            "categories": categories,
            "average_score": round(avg_score, 1),
            "weak_areas": weak_areas,
            "strong_areas": strong_areas,
            "relative_weak_areas": relative_weak_areas,
            "relative_strong_areas": relative_strong_areas,
            "trend": trend
        }
    
    def _analyze_simulation_from_dashboard(self, dashboard_data: Dict) -> Dict:
        """대시보드 데이터에서 시뮬레이션 분석"""
        simulation_results = dashboard_data.get("simulation_results", [])
        
        if not simulation_results:
            return {
                "has_data": False,
                "message": "아직 시뮬레이션 기록이 없습니다."
            }
        
        # 통계 계산
        total_attempts = len(simulation_results)
        overall_scores = [s.get("overall_score", 0) for s in simulation_results if s.get("overall_score") is not None and s.get("overall_score") > 0]
        avg_score = sum(overall_scores) / len(overall_scores) if overall_scores else 0
        
        # 최근 성과
        recent_performance = []
        for sf in simulation_results[:3]:
            recent_performance.append({
                "scenario": sf.get("situation_info", "일반"),
                "score": sf.get("overall_score", 0),
                "date": sf.get("created_at", "")[:10] if sf.get("created_at") else ""
            })
        
        # 약점/강점 동적 계산 (SimulationFeedback 점수 기반)
        avg_scores = {}
        knowledge_scores = [s.get("knowledge_score", 0) for s in simulation_results if s.get("knowledge_score") is not None]
        skill_scores = [s.get("skill_score", 0) for s in simulation_results if s.get("skill_score") is not None]
        clarity_scores = [s.get("clarity_score", 0) for s in simulation_results if s.get("clarity_score") is not None]
        kindness_scores = [s.get("kindness_score", 0) for s in simulation_results if s.get("kindness_score") is not None]
        confidence_scores = [s.get("confidence_score", 0) for s in simulation_results if s.get("confidence_score") is not None]
        
        if knowledge_scores:
            avg_scores["지식"] = sum(knowledge_scores) / len(knowledge_scores)
        if skill_scores:
            avg_scores["기술"] = sum(skill_scores) / len(skill_scores)
        if clarity_scores:
            avg_scores["명확성"] = sum(clarity_scores) / len(clarity_scores)
        if kindness_scores:
            avg_scores["친절도"] = sum(kindness_scores) / len(kindness_scores)
        if confidence_scores:
            avg_scores["자신감"] = sum(confidence_scores) / len(confidence_scores)
        
        # 약점/강점 계산
        weak_areas = []
        strong_areas = []
        
        if avg_scores:
            sorted_areas = sorted(avg_scores.items(), key=lambda x: x[1])
            weak_areas = [area for area, score in sorted_areas[:3] if score < 70]
            
            sorted_areas_desc = sorted(avg_scores.items(), key=lambda x: x[1], reverse=True)
            strong_areas = [area for area, score in sorted_areas_desc[:3] if score >= 80]
        
        # 주간개선률 계산
        weekly_improvement = self._calculate_weekly_improvement(simulation_results)
        
        return {
            "has_data": True,
            "total_attempts": total_attempts,
            "average_score": round(avg_score, 1) if avg_score else 0,
            "recent_performance": recent_performance,
            "completed_scenarios": [],
            "weak_areas": weak_areas,
            "strong_areas": strong_areas,
            "feedback_count": len(simulation_results),
            "avg_scores": avg_scores,
            "weekly_improvement": weekly_improvement  # 주간개선률 추가
        }
    
    def _calculate_weekly_improvement(self, simulation_results: List[Dict]) -> Dict:
        """시뮬레이션 주간개선률 계산"""
        if not simulation_results or len(simulation_results) < 2:
            return {
                "has_data": False,
                "message": "주간개선률을 계산하기에는 데이터가 부족합니다."
            }
        
        # 현재 날짜 기준으로 주간 구분
        now = datetime.now()
        one_week_ago = now - timedelta(days=7)
        two_weeks_ago = now - timedelta(days=14)
        
        # 최근 1주일간 점수
        recent_week_scores = []
        # 그 이전 1주일간 점수
        previous_week_scores = []
        
        for result in simulation_results:
            created_at_str = result.get("created_at", "")
            if not created_at_str:
                continue
            
            try:
                # ISO 형식 날짜 파싱
                if isinstance(created_at_str, str):
                    if 'T' in created_at_str:
                        created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                    else:
                        created_at = datetime.strptime(created_at_str[:10], '%Y-%m-%d')
                else:
                    created_at = created_at_str
                
                # UTC를 로컬 시간으로 변환 (필요시)
                if created_at.tzinfo:
                    from datetime import timezone
                    created_at = created_at.replace(tzinfo=None)
                
                score = result.get("overall_score", 0)
                if score and score > 0:
                    if created_at >= one_week_ago:
                        recent_week_scores.append(score)
                    elif created_at >= two_weeks_ago:
                        previous_week_scores.append(score)
            except Exception as e:
                print(f"⚠️ 날짜 파싱 오류: {e}, created_at: {created_at_str}")
                continue
        
        if not recent_week_scores or not previous_week_scores:
            return {
                "has_data": False,
                "message": "주간개선률을 계산하기에는 데이터가 부족합니다."
            }
        
        # 주간 평균 점수 계산
        recent_avg = sum(recent_week_scores) / len(recent_week_scores)
        previous_avg = sum(previous_week_scores) / len(previous_week_scores)
        
        # 개선률 계산 (백분율)
        if previous_avg > 0:
            improvement_rate = ((recent_avg - previous_avg) / previous_avg) * 100
        else:
            improvement_rate = 0.0
        
        # 개선 방향
        if improvement_rate > 5:
            trend = "크게 개선"
        elif improvement_rate > 0:
            trend = "개선"
        elif improvement_rate > -5:
            trend = "유지"
        else:
            trend = "하락"
        
        return {
            "has_data": True,
            "recent_week_avg": round(recent_avg, 1),
            "previous_week_avg": round(previous_avg, 1),
            "improvement_rate": round(improvement_rate, 1),
            "trend": trend,
            "recent_count": len(recent_week_scores),
            "previous_count": len(previous_week_scores)
        }
    
    def _analyze_chat_from_dashboard(self, dashboard_data: Dict) -> Dict:
        """대시보드 데이터에서 채팅 활동 분석"""
        total_chats = dashboard_data.get("total_chats", 0)
        recent_topics = dashboard_data.get("recent_topics", [])
        user_id = dashboard_data.get("user_id")
        
        # 최근 30일 채팅 수 계산
        recent_chats_30days = 0
        if user_id:
            thirty_days_ago = datetime.now() - timedelta(days=30)
            recent_statement = select(func.count(ChatHistory.id)).where(
                ChatHistory.user_id == user_id,
                ChatHistory.created_at >= thirty_days_ago
            )
            recent_chats_30days = self.session.exec(recent_statement).first() or 0
        
        return {
            "total_chats": total_chats,
            "recent_chats_30days": recent_chats_30days,
            "recent_topics": recent_topics[:5],
            "engagement_level": self._calculate_engagement_level(total_chats, recent_chats_30days)
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
        """시뮬레이션 진행 상황 분석 (실시간 SimulationFeedback 데이터 포함)"""
        
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
        
        # 실시간 SimulationFeedback 데이터 가져오기
        feedbacks_statement = (
            select(SimulationFeedback)
            .where(SimulationFeedback.user_id == user_id)
            .order_by(SimulationFeedback.created_at.desc())
            .limit(50)  # 최근 50개 피드백 분석
        )
        feedbacks = list(self.session.exec(feedbacks_statement).all())
        
        if not progress and not attempts and not rag_sims and not feedbacks:
            return {
                "has_data": False,
                "message": "아직 시뮬레이션 기록이 없습니다."
            }
        
        # 통계 계산
        total_attempts = len(attempts) + len(rag_sims)
        
        avg_score = 0
        if attempts:
            avg_score = sum(a.final_score for a in attempts if a.final_score) / len(attempts)
        
        # 최근 성과
        recent_performance = []
        for attempt in attempts[:3]:
            recent_performance.append({
                "scenario": attempt.scenario_type or "일반",
                "score": attempt.final_score or 0,
                "date": attempt.started_at.isoformat() if attempt.started_at else ""
            })
        
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
        
        # SimulationFeedback의 점수를 평균에 반영하여 weak_areas와 strong_areas 동적 계산
        avg_scores = {}
        if feedbacks:
            # 각 지표별로 모든 피드백의 점수를 모아서 평균 계산
            knowledge_scores = [f.knowledge_score for f in feedbacks if f.knowledge_score is not None]
            skill_scores = [f.skill_score for f in feedbacks if f.skill_score is not None]
            clarity_scores = [f.clarity_score for f in feedbacks if f.clarity_score is not None]
            kindness_scores = [f.kindness_score for f in feedbacks if f.kindness_score is not None]
            confidence_scores = [f.confidence_score for f in feedbacks if f.confidence_score is not None]
            
            if knowledge_scores:
                avg_scores["지식"] = sum(knowledge_scores) / len(knowledge_scores)
            if skill_scores:
                avg_scores["기술"] = sum(skill_scores) / len(skill_scores)
            # empathy_score는 더 이상 사용하지 않음 (5가지 지표로 변경)
            if clarity_scores:
                avg_scores["명확성"] = sum(clarity_scores) / len(clarity_scores)
            if kindness_scores:
                avg_scores["친절도"] = sum(kindness_scores) / len(kindness_scores)
            if confidence_scores:
                avg_scores["자신감"] = sum(confidence_scores) / len(confidence_scores)
        
        # progress에 저장된 값이 없거나 비어있으면 동적으로 계산한 값 사용
        if not weak_areas and avg_scores:
            sorted_areas = sorted(avg_scores.items(), key=lambda x: x[1])
            weak_areas = [area for area, score in sorted_areas[:3] if score < 70]
        
        # 강점 분석
        if not strong_areas and avg_scores:
            sorted_areas = sorted(avg_scores.items(), key=lambda x: x[1], reverse=True)
            strong_areas = [area for area, score in sorted_areas[:3] if score >= 80]
        
        return {
            "has_data": True,
            "total_attempts": total_attempts,
            "average_score": round(avg_score, 1) if avg_score else 0,
            "recent_performance": recent_performance,
            "completed_scenarios": completed_scenarios,
            "weak_areas": weak_areas,
            "strong_areas": strong_areas,
            "feedback_count": len(feedbacks),
            "avg_scores": avg_scores  # 실시간 계산된 평균 점수
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
    
    def generate_response(self, user: User, message: str, context_history: Optional[List[Dict]] = None) -> str:
        """학습현황 관련 응답 생성"""
        
        query_type = self.get_query_type(message, context_history)
        analysis = self.analyze_learning_progress(user)
        
        if query_type == "relative_weak_areas":
            return self._generate_relative_weak_areas_response(user, analysis)
        elif query_type == "relative_strong_areas":
            return self._generate_relative_strong_areas_response(user, analysis)
        elif query_type == "weak_areas":
            return self._generate_weak_areas_response(user, analysis)
        elif query_type == "strong_areas":
            return self._generate_strong_areas_response(user, analysis)
        elif query_type == "simulation_weak_areas":
            return self._generate_simulation_weak_areas_response(user, analysis)
        elif query_type == "simulation_strong_areas":
            return self._generate_simulation_strong_areas_response(user, analysis)
        elif query_type == "simulation_relative_weak_areas":
            return self._generate_simulation_relative_weak_areas_response(user, analysis)
        elif query_type == "simulation_relative_strong_areas":
            return self._generate_simulation_relative_strong_areas_response(user, analysis)
        elif query_type == "recommendation":
            return self._generate_recommendation_response(user, analysis)
        elif query_type == "scores":
            return self._generate_scores_response(user, analysis)
        elif query_type == "simulation":
            return self._generate_simulation_response(user, analysis)
        elif query_type == "weekly_improvement":
            return self._generate_weekly_improvement_response(user, analysis)
        elif query_type == "simulation_history":
            return self._generate_simulation_history_response(user, analysis)
        elif query_type == "simulation_detail":
            return self._generate_simulation_detail_response(user, analysis, message)
        elif query_type == "simulation_recording":
            return self._generate_simulation_recording_response(user, analysis)
        elif query_type == "simulation_trend":
            return self._generate_simulation_trend_response(user, analysis)
        elif query_type == "exam_trend":
            return self._generate_exam_trend_response(user, analysis)
        elif query_type == "overall_trend":
            return self._generate_overall_trend_response(user, analysis)
        else:
            return self._generate_overall_response(user, analysis)
    
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
        simulation = analysis["simulation"]
        
        if not simulation.get("has_data"):
            return "아직 시뮬레이션 기록이 없습니다. 실전 연습을 시작해보세요! 🎭"
        
        response = f"""🎭 **{user.name}님의 시뮬레이션 성과**

📊 **전체 통계**
- 총 실습 횟수: {simulation['total_attempts']}회
- 평균 점수: {simulation['average_score']}점

"""
        
        # 최근 시뮬레이션 정보
        if simulation.get('recent_performance'):
            latest = simulation['recent_performance'][0]
            response += f"""📝 **최근 시뮬레이션**
- 시나리오: {latest.get('scenario', '일반')}
- 날짜: {latest.get('date', '')[:10]}
- 점수: {latest.get('score', 0)}점

"""
        
        # 역량별 점수 (avg_scores가 있으면 표시)
        avg_scores = simulation.get('avg_scores', {})
        if avg_scores:
            response += "📈 **역량별 평균 점수**\n"
            for area, score in sorted(avg_scores.items(), key=lambda x: x[1], reverse=True):
                emoji = "🌟" if score >= 80 else "⚠️" if score < 70 else "📌"
                response += f"{emoji} {area}: {round(score, 1)}점\n"
            response += "\n"
        
        if simulation.get('recent_performance'):
            response += "📈 **최근 성과**\n"
            for perf in simulation['recent_performance'][:3]:
                response += f"- {perf['scenario']}: {perf['score']}점 ({perf['date'][:10]})\n"
            response += "\n"
        
        if simulation.get('weak_areas'):
            response += "⚠️ **보완 필요**\n"
            for area in simulation['weak_areas'][:3]:
                score = avg_scores.get(area, 0) if avg_scores else 0
                response += f"- {area}: {round(score, 1)}점\n" if score > 0 else f"- {area}\n"
            response += "\n"
        
        if simulation.get('strong_areas'):
            response += "✅ **강점 영역**\n"
            for area in simulation['strong_areas'][:3]:
                score = avg_scores.get(area, 0) if avg_scores else 0
                response += f"- {area}: {round(score, 1)}점 🌟\n" if score > 0 else f"- {area} 🌟\n"
            response += "\n"
        
        response += "💡 실전 연습을 통해 실력이 향상되고 있습니다. 계속해서 도전하세요!"
        
        return response
    
    def _generate_simulation_strong_areas_response(self, user: User, analysis: Dict) -> str:
        """시뮬레이션 강점 분석 응답"""
        simulation = analysis.get("simulation", {})
        
        if not simulation.get("has_data"):
            return "아직 시뮬레이션 기록이 없습니다. 실전 연습을 시작해보세요! 🎭"
        
        strong_areas = simulation.get("strong_areas", [])
        avg_scores = simulation.get("avg_scores", {})
        
        if not strong_areas:
            return f"""🌟 **{user.name}님의 시뮬레이션 강점**

아직 강점으로 분류된 영역이 없습니다. 더 많은 연습을 통해 강점을 만들어보세요! 💪"""
        
        response = f"""🌟 **{user.name}님의 시뮬레이션 강점**

시뮬레이션에서 특히 뛰어난 영역을 알려드릴게요! 👏

"""
        
        response += "📈 **시뮬레이션 기반 강점**\n"
        for area in strong_areas:
            score = avg_scores.get(area, 0)
            response += f"- **{area}**: {round(score, 1)}점 🌟\n"
        
        response += f"""
👍 정말 훌륭합니다! 이 강점을 활용해서 다른 영역도 발전시켜보세요.
"""
        
        return response
    
    def _generate_simulation_weak_areas_response(self, user: User, analysis: Dict) -> str:
        """시뮬레이션 약점 분석 응답"""
        simulation = analysis.get("simulation", {})
        
        if not simulation.get("has_data"):
            return "아직 시뮬레이션 기록이 없습니다. 실전 연습을 시작해보세요! 🎭"
        
        weak_areas = simulation.get("weak_areas", [])
        avg_scores = simulation.get("avg_scores", {})
        
        if not weak_areas:
            return f"""⚠️ **{user.name}님의 시뮬레이션 약점**

모든 영역에서 양호한 성과를 보이고 있습니다! 계속 유지하세요! 💪"""
        
        response = f"""⚠️ **{user.name}님의 시뮬레이션 약점**

시뮬레이션에서 개선이 필요한 영역을 알려드릴게요.

"""
        
        response += "📉 **시뮬레이션 기반 약점**\n"
        for area in weak_areas:
            score = avg_scores.get(area, 0)
            response += f"- **{area}**: {round(score, 1)}점\n"
        
        response += f"""
🎯 **개선 방법**
"""
        for area in weak_areas[:3]:
            response += f"- {self._get_simulation_improvement_suggestion(area)}\n"
        
        return response
    
    def _generate_simulation_relative_weak_areas_response(self, user: User, analysis: Dict) -> str:
        """시뮬레이션 상대적 약점 분석 응답"""
        simulation = analysis.get("simulation", {})
        
        if not simulation.get("has_data"):
            return "아직 시뮬레이션 기록이 없습니다. 실전 연습을 시작해보세요! 🎭"
        
        avg_scores = simulation.get("avg_scores", {})
        
        if not avg_scores:
            return "시뮬레이션 데이터가 부족하여 비교할 수 없습니다."
        
        # 상대적으로 낮은 영역 (하위 3개)
        sorted_areas = sorted(avg_scores.items(), key=lambda x: x[1])
        relative_weak_areas = [area for area, score in sorted_areas[:3]]
        
        response = f"""📊 **{user.name}님의 시뮬레이션 상대적 약점**

다른 영역에 비해 상대적으로 낮은 영역입니다.

"""
        
        response += "📉 **상대적으로 낮은 영역**\n"
        for i, area in enumerate(relative_weak_areas, 1):
            score = avg_scores.get(area, 0)
            if i == 1:
                emoji = "🔴"
            elif i == 2:
                emoji = "🟠"
            else:
                emoji = "🟡"
            response += f"{i}. **{area}**: {round(score, 1)}점 {emoji}\n"
        
        response += "\n💡 이 영역들을 집중적으로 연습하면 전체 성과가 향상될 것입니다!"
        
        return response
    
    def _generate_simulation_relative_strong_areas_response(self, user: User, analysis: Dict) -> str:
        """시뮬레이션 상대적 강점 분석 응답"""
        simulation = analysis.get("simulation", {})
        
        if not simulation.get("has_data"):
            return "아직 시뮬레이션 기록이 없습니다. 실전 연습을 시작해보세요! 🎭"
        
        avg_scores = simulation.get("avg_scores", {})
        
        if not avg_scores:
            return "시뮬레이션 데이터가 부족하여 비교할 수 없습니다."
        
        # 상대적으로 높은 영역 (상위 3개)
        sorted_areas = sorted(avg_scores.items(), key=lambda x: x[1], reverse=True)
        relative_strong_areas = [area for area, score in sorted_areas[:3]]
        
        response = f"""🌟 **{user.name}님의 시뮬레이션 상대적 강점**

다른 영역에 비해 특히 뛰어난 영역입니다! 👏

"""
        
        response += "📈 **상대적으로 높은 영역**\n"
        for i, area in enumerate(relative_strong_areas, 1):
            score = avg_scores.get(area, 0)
            if i == 1:
                emoji = "🥇"
                praise = "최고입니다!"
            elif i == 2:
                emoji = "🥈"
                praise = "아주 훌륭해요!"
            else:
                emoji = "🥉"
                praise = "잘하고 계세요!"
            response += f"{i}. **{area}**: {round(score, 1)}점 {emoji} - {praise}\n"
        
        response += "\n✨ 이 강점을 살려 다른 영역 학습에도 적용해보세요!"
        
        return response
    
    def _get_simulation_improvement_suggestion(self, area: str) -> str:
        """시뮬레이션 영역별 개선 제안"""
        suggestions = {
            "지식": "금융상품과 은행 업무 지식을 더 학습하고, 챗봇에 질문하여 지식을 보강하세요",
            "기술": "시뮬레이션을 더 자주 연습하여 실무 기술을 향상시키세요",
            "명확성": "고객에게 설명할 때 더 명확하고 이해하기 쉽게 전달하는 연습을 하세요",
            "친절도": "고객 응대 시 더 친절하고 배려심 있는 태도를 보이도록 연습하세요",
            "자신감": "더 많은 시뮬레이션 연습을 통해 자신감을 키우세요"
        }
        return suggestions.get(area, f"{area} 영역을 집중적으로 연습하세요")
    
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
    
    def _generate_weekly_improvement_response(self, user: User, analysis: Dict) -> str:
        """시뮬레이션 주간개선률 응답 생성"""
        simulation = analysis.get("simulation", {})
        weekly_improvement = simulation.get("weekly_improvement", {})
        
        if not weekly_improvement.get("has_data"):
            return f"""📊 **시뮬레이션 주간개선률**

{weekly_improvement.get("message", "주간개선률을 계산하기에는 데이터가 부족합니다.")}

최소 2주 이상의 시뮬레이션 기록이 필요합니다."""
        
        recent_avg = weekly_improvement.get("recent_week_avg", 0)
        previous_avg = weekly_improvement.get("previous_week_avg", 0)
        improvement_rate = weekly_improvement.get("improvement_rate", 0)
        trend = weekly_improvement.get("trend", "유지")
        recent_count = weekly_improvement.get("recent_count", 0)
        previous_count = weekly_improvement.get("previous_count", 0)
        
        # 이모지 선택
        if improvement_rate > 5:
            emoji = "📈"
        elif improvement_rate > 0:
            emoji = "📊"
        elif improvement_rate > -5:
            emoji = "➡️"
        else:
            emoji = "📉"
        
        response = f"""📊 **시뮬레이션 주간개선률**

{emoji} **최근 1주일 평균**: {recent_avg}점 ({recent_count}회)
📅 **이전 1주일 평균**: {previous_avg}점 ({previous_count}회)

🎯 **개선률**: {improvement_rate:+.1f}%
📈 **추세**: {trend}

"""
        
        if improvement_rate > 0:
            response += f"""✅ 최근 1주일간 평균 점수가 {previous_avg}점에서 {recent_avg}점으로 {improvement_rate:.1f}% 개선되었습니다!
계속해서 좋은 성과를 보이고 계시네요. 💪"""
        elif improvement_rate < 0:
            response += f"""⚠️ 최근 1주일간 평균 점수가 {previous_avg}점에서 {recent_avg}점으로 {abs(improvement_rate):.1f}% 하락했습니다.
더 많은 연습과 피드백 확인을 통해 개선해보세요. 화이팅! 💪"""
        else:
            response += f"""➡️ 최근 1주일간 평균 점수가 이전 주와 비슷하게 유지되고 있습니다.
지속적인 연습을 통해 더 높은 점수를 목표로 해보세요! 💪"""
        
        return response
    
    def _generate_simulation_history_response(self, user: User, analysis: Dict) -> str:
        """시뮬레이션 기록/히스토리 응답 생성"""
        simulation = analysis.get("simulation", {})
        
        if not simulation.get("has_data"):
            return "아직 시뮬레이션 기록이 없습니다. 실전 연습을 시작해보세요! 🎭"
        
        total_attempts = simulation.get("total_attempts", 0)
        avg_score = simulation.get("average_score", 0)
        recent_performance = simulation.get("recent_performance", [])
        
        response = f"""📋 **{user.name}님의 시뮬레이션 기록**

📊 **전체 통계**
- 총 실습 횟수: {total_attempts}회
- 평균 점수: {avg_score}점

"""
        
        if recent_performance:
            response += "📈 **최근 실습 기록**\n"
            for i, perf in enumerate(recent_performance[:5], 1):
                scenario = perf.get("scenario", "일반")
                score = perf.get("score", 0)
                date = perf.get("date", "")
                response += f"{i}. {scenario}: {score}점 ({date})\n"
            response += "\n"
        
        # 등급 분포 계산
        if recent_performance:
            grades = {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0}
            for perf in recent_performance:
                score = perf.get("score", 0)
                if score >= 90:
                    grades["A"] += 1
                elif score >= 80:
                    grades["B"] += 1
                elif score >= 70:
                    grades["C"] += 1
                elif score >= 60:
                    grades["D"] += 1
                else:
                    grades["F"] += 1
            
            response += "📊 **등급 분포**\n"
            for grade, count in grades.items():
                if count > 0:
                    response += f"- {grade}등급: {count}회\n"
            response += "\n"
        
        response += "💡 더 자세한 정보는 대시보드의 시뮬레이션 탭에서 확인하실 수 있습니다."
        
        return response
    
    def _generate_simulation_detail_response(self, user: User, analysis: Dict, message: str) -> str:
        """시뮬레이션 상세 정보 응답 생성"""
        simulation = analysis.get("simulation", {})
        
        if not simulation.get("has_data"):
            return "아직 시뮬레이션 기록이 없습니다. 실전 연습을 시작해보세요! 🎭"
        
        recent_performance = simulation.get("recent_performance", [])
        avg_scores = simulation.get("avg_scores", {})
        weak_areas = simulation.get("weak_areas", [])
        strong_areas = simulation.get("strong_areas", [])
        
        if not recent_performance:
            return "최근 시뮬레이션 기록이 없습니다."
        
        # 가장 최근 기록 사용
        latest = recent_performance[0]
        
        response = f"""📊 **최근 시뮬레이션 상세 결과**

🎭 **시나리오**: {latest.get("scenario", "일반")}
📅 **날짜**: {latest.get("date", "")}
⭐ **종합 점수**: {latest.get("score", 0)}점

"""
        
        if avg_scores:
            response += "📈 **역량별 평균 점수**\n"
            for area, score in sorted(avg_scores.items(), key=lambda x: x[1], reverse=True):
                emoji = "🌟" if score >= 80 else "⚠️" if score < 70 else "📌"
                response += f"{emoji} {area}: {round(score, 1)}점\n"
            response += "\n"
        
        if strong_areas:
            response += "✅ **강점 영역**\n"
            for area in strong_areas:
                score = avg_scores.get(area, 0)
                response += f"- {area}: {round(score, 1)}점 🌟\n"
            response += "\n"
        
        if weak_areas:
            response += "⚠️ **개선 필요 영역**\n"
            for area in weak_areas:
                score = avg_scores.get(area, 0)
                response += f"- {area}: {round(score, 1)}점\n"
            response += "\n"
        
        response += "💡 더 자세한 피드백은 대시보드의 시뮬레이션 탭에서 '상세보기'를 클릭하시면 확인하실 수 있습니다."
        
        return response
    
    def _generate_simulation_recording_response(self, user: User, analysis: Dict) -> str:
        """시뮬레이션 녹화 관련 응답 생성"""
        simulation = analysis.get("simulation", {})
        
        if not simulation.get("has_data"):
            return "아직 시뮬레이션 기록이 없습니다. 실전 연습을 시작해보세요! 🎭"
        
        recent_performance = simulation.get("recent_performance", [])
        
        response = f"""🎥 **시뮬레이션 녹화 정보**

"""
        
        if recent_performance:
            response += "📹 **녹화 가능한 시뮬레이션**\n"
            response += "대시보드의 시뮬레이션 탭에서 각 시뮬레이션 기록의 '녹화' 버튼을 클릭하시면 녹화본을 확인하실 수 있습니다.\n\n"
            
            response += "📋 **최근 시뮬레이션 기록**\n"
            for i, perf in enumerate(recent_performance[:3], 1):
                scenario = perf.get("scenario", "일반")
                date = perf.get("date", "")
                response += f"{i}. {scenario} ({date})\n"
            response += "\n"
        else:
            response += "아직 시뮬레이션 기록이 없어 녹화본을 확인할 수 없습니다.\n\n"
        
        response += "💡 시뮬레이션을 완료하면 자동으로 녹화가 저장되며, 대시보드에서 언제든지 다시 확인하실 수 있습니다."
        
        return response
    
    def _generate_simulation_trend_response(self, user: User, analysis: Dict) -> str:
        """시뮬레이션 추이/트렌드 응답 생성"""
        simulation = analysis.get("simulation", {})
        weekly_improvement = simulation.get("weekly_improvement", {})
        
        if not simulation.get("has_data"):
            return "아직 시뮬레이션 기록이 없습니다. 실전 연습을 시작해보세요! 🎭"
        
        recent_performance = simulation.get("recent_performance", [])
        avg_score = simulation.get("average_score", 0)
        
        response = f"""📈 **시뮬레이션 성과 추이**

📊 **전체 평균 점수**: {avg_score}점

"""
        
        # 주간개선률 정보 포함
        if weekly_improvement.get("has_data"):
            improvement_rate = weekly_improvement.get("improvement_rate", 0)
            trend = weekly_improvement.get("trend", "유지")
            recent_avg = weekly_improvement.get("recent_week_avg", 0)
            previous_avg = weekly_improvement.get("previous_week_avg", 0)
            
            response += f"""📅 **주간 개선률**
- 최근 1주일 평균: {recent_avg}점
- 이전 1주일 평균: {previous_avg}점
- 개선률: {improvement_rate:+.1f}%
- 추세: {trend}

"""
        
        if recent_performance:
            response += "📉 **최근 점수 추이**\n"
            scores = [p.get("score", 0) for p in recent_performance[:5]]
            for i, (perf, score) in enumerate(zip(recent_performance[:5], scores), 1):
                date = perf.get("date", "")
                scenario = perf.get("scenario", "일반")
                
                # 이전 점수와 비교
                if i > 1:
                    prev_score = scores[i-2]
                    if score > prev_score:
                        arrow = "📈"
                        change = f"(+{score - prev_score:.1f}점)"
                    elif score < prev_score:
                        arrow = "📉"
                        change = f"({score - prev_score:.1f}점)"
                    else:
                        arrow = "➡️"
                        change = "(변화 없음)"
                else:
                    arrow = "📊"
                    change = ""
                
                response += f"{arrow} {date} - {scenario}: {score}점 {change}\n"
            response += "\n"
        
        # 추세 분석
        if len(recent_performance) >= 3:
            recent_scores = [p.get("score", 0) for p in recent_performance[:3]]
            if all(recent_scores[i] <= recent_scores[i+1] for i in range(len(recent_scores)-1)):
                trend_msg = "📈 최근 점수가 지속적으로 상승하고 있습니다! 훌륭합니다! 💪"
            elif all(recent_scores[i] >= recent_scores[i+1] for i in range(len(recent_scores)-1)):
                trend_msg = "📉 최근 점수가 하락하고 있습니다. 더 많은 연습을 권장합니다."
            else:
                trend_msg = "➡️ 점수가 일정하게 유지되고 있습니다. 꾸준한 연습을 계속하세요!"
            
            response += f"{trend_msg}\n\n"
        
        response += "💡 더 자세한 추이 분석은 대시보드의 시뮬레이션 탭에서 '주간 시뮬레이션 점수 추이' 차트를 확인하세요."
        
        return response
    
    def _generate_exam_trend_response(self, user: User, analysis: Dict) -> str:
        """시험 성적 추이/트렌드 응답 생성"""
        exam = analysis.get("exam", {})
        
        if not exam.get("has_data"):
            return "아직 시험 기록이 없습니다. 첫 시험을 응시해보세요! 📝"
        
        exam_scores = exam.get("total_exams", 0)
        avg_score = exam.get("average_score", 0)
        trend = exam.get("trend", "stable")
        latest_exam = exam.get("latest_exam", {})
        
        response = f"""📈 **시험 성적 추이**

📊 **전체 통계**
- 총 시험 횟수: {exam_scores}회
- 평균 점수: {avg_score}점
- 최근 시험: {latest_exam.get("name", "")} ({latest_exam.get("date", "")[:10]})
- 최근 점수: {latest_exam.get("score", 0)}점
- 등급: {latest_exam.get("grade", "")}

"""
        
        # 추세 분석
        trend_emoji = self._get_trend_emoji(trend)
        if trend == "improving":
            trend_msg = "📈 시험 점수가 지속적으로 상승하고 있습니다! 훌륭합니다! 💪"
        elif trend == "declining":
            trend_msg = "📉 시험 점수가 하락하고 있습니다. 더 많은 학습을 권장합니다."
        else:
            trend_msg = "➡️ 시험 점수가 일정하게 유지되고 있습니다. 꾸준한 학습을 계속하세요!"
        
        response += f"""📊 **추세 분석**
{trend_emoji} **현재 추세**: {trend}
{trend_msg}

"""
        
        # 카테고리별 추이 (최근 2개 시험 비교)
        categories = exam.get("categories", {})
        if categories:
            response += "📋 **영역별 점수**\n"
            categories_sorted = sorted(categories.items(), key=lambda x: x[1], reverse=True)
            for category, score in categories_sorted:
                emoji = "🌟" if score >= 80 else "⚠️" if score < 70 else "📌"
                response += f"{emoji} {category}: {score}점\n"
            response += "\n"
        
        # 약점과 강점
        weak_areas = exam.get("weak_areas", [])
        strong_areas = exam.get("strong_areas", [])
        
        if weak_areas:
            response += "⚠️ **개선 필요 영역**\n"
            for area in weak_areas[:3]:
                score = categories.get(area, 0)
                response += f"- {area}: {score}점\n"
            response += "\n"
        
        if strong_areas:
            response += "✅ **강점 영역**\n"
            for area in strong_areas[:3]:
                score = categories.get(area, 0)
                response += f"- {area}: {score}점 🌟\n"
            response += "\n"
        
        response += "💡 더 자세한 성적 분석은 대시보드에서 확인하실 수 있습니다."
        
        return response
    
    def _generate_overall_trend_response(self, user: User, analysis: Dict) -> str:
        """시험과 시뮬레이션 종합 추이 응답 생성"""
        exam = analysis.get("exam", {})
        simulation = analysis.get("simulation", {})
        
        response = f"""📊 **{user.name}님의 학습 성과 추이 (종합)**

"""
        
        # 시험 추이
        if exam.get("has_data"):
            exam_avg = exam.get("average_score", 0)
            exam_trend = exam.get("trend", "stable")
            exam_trend_emoji = self._get_trend_emoji(exam_trend)
            
            response += f"""📝 **시험 성적**
- 평균 점수: {exam_avg}점
- 추세: {exam_trend_emoji} {exam_trend}

"""
        else:
            response += "📝 **시험 성적**: 아직 기록이 없습니다.\n\n"
        
        # 시뮬레이션 추이
        if simulation.get("has_data"):
            sim_avg = simulation.get("average_score", 0)
            weekly_improvement = simulation.get("weekly_improvement", {})
            
            response += f"""🎭 **시뮬레이션 성과**
- 평균 점수: {sim_avg}점
"""
            
            if weekly_improvement.get("has_data"):
                improvement_rate = weekly_improvement.get("improvement_rate", 0)
                trend = weekly_improvement.get("trend", "유지")
                response += f"- 주간 개선률: {improvement_rate:+.1f}% ({trend})\n"
            
            response += "\n"
        else:
            response += "🎭 **시뮬레이션 성과**: 아직 기록이 없습니다.\n\n"
        
        # 종합 평가
        if exam.get("has_data") and simulation.get("has_data"):
            exam_trend = exam.get("trend", "stable")
            sim_weekly = simulation.get("weekly_improvement", {})
            sim_trend = sim_weekly.get("trend", "유지") if sim_weekly.get("has_data") else "유지"
            
            if exam_trend == "improving" and sim_trend in ["개선", "크게 개선"]:
                overall_msg = "🎉 시험과 시뮬레이션 모두 개선되고 있습니다! 정말 훌륭합니다! 💪"
            elif exam_trend == "improving" or sim_trend in ["개선", "크게 개선"]:
                overall_msg = "📈 한 영역에서 개선이 보이고 있습니다. 계속 노력하세요! 💪"
            elif exam_trend == "declining" or sim_trend == "하락":
                overall_msg = "📉 일부 영역에서 하락이 있습니다. 더 많은 학습과 연습을 권장합니다."
            else:
                overall_msg = "➡️ 전반적으로 안정적인 성과를 보이고 있습니다. 꾸준히 유지하세요!"
            
            response += f"""🎯 **종합 평가**
{overall_msg}

"""
        
        response += "💡 더 자세한 정보는 대시보드에서 확인하실 수 있습니다."
        
        return response
    
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

