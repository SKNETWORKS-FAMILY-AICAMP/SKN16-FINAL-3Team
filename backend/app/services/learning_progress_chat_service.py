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
from app.models.mentor import ExamScore, ChatHistory, LearningTopic
from app.models.simulation import SimulationAttempt, SimulationProgress
from app.models.simulation_feedback import SimulationFeedback
from app.models.rag_simulation import RAGSimulationSession, RAGSimulationEvaluation


class LearningProgressChatService:
    """학습현황 분석 및 챗봇 응답 서비스"""
    
    def __init__(self, session: Session):
        self.session = session
        
        # 학습현황 관련 키워드
        self._learning_keywords = {
            "general": ["학습현황", "학습 현황", "학습", "공부", "진도", "진행", "현황", "상황", "성과"],
            "score": ["성적", "점수", "시험", "평가", "결과"],
            "weak": ["약점", "부족", "취약", "못하는", "어려운", "개선", "보완", "약한", "낮은"],
            "strong": ["강점", "잘하는", "우수", "뛰어난", "높은", "좋은", "강한"],
            "relative": ["제일", "가장", "상대적", "그래도", "그중", "비교적"],
            "recommendation": ["추천", "해야", "공부해야", "학습해야", "보완해야"],
            "simulation": ["시뮬레이션", "simulation", "실습", "연습", "성과"],
            "overall": ["전체", "종합", "요약", "정리"]
        }
    
    def is_learning_progress_query(self, message: str) -> bool:
        """학습현황 관련 쿼리인지 확인"""
        message = message.lower().strip()
        
        # 학습현황 관련 키워드 확인
        for category, keywords in self._learning_keywords.items():
            for keyword in keywords:
                if keyword in message:
                    return True
        
        # 시뮬레이션 리포트 관련 키워드도 포함 (rag_service와 동일한 키워드)
        simulation_keywords = [
            "시뮬레이션", "simulation", "보고서", "리포트", "평가", "성적", "점수", 
            "약점", "weak point", "weakpoint", "개선점", "부족한",
            "내 성적", "나의 성적", "내 점수", "나의 점수",
            "평균", "수준", "등급", "성과", "어때"
        ]
        for keyword in simulation_keywords:
            if keyword in message:
                return True
        
        # 특정 패턴 확인
        patterns = [
            r"내\s*(학습|공부|성적|점수)",
            r"(어떻게|얼마나)\s*(공부|학습)",
            r"(무엇을|뭘)\s*(공부|학습)",
            r"(약점|강점).*뭐",
            r"추천.*해",
            r"학습현황.*어때",  # "학습현황 어때?" 패턴
            r"학습.*현황",  # "학습 현황" 패턴
        ]
        
        for pattern in patterns:
            if re.search(pattern, message):
                return True
        
        return False
    
    def _get_recent_chat_history(self, user_id: int, limit: int = 5) -> List[Dict]:
        """최근 대화 히스토리 조회"""
        try:
            from app.models.mentor import ChatHistory
            from sqlmodel import select
            
            statement = (
                select(ChatHistory)
                .where(ChatHistory.user_id == user_id)
                .order_by(ChatHistory.created_at.desc())
                .limit(limit)
            )
            histories = list(self.session.exec(statement).all())
            
            return [
                {
                    "user_message": h.user_message or "",
                    "bot_response": h.bot_response or "",
                    "created_at": h.created_at.isoformat() if h.created_at else ""
                }
                for h in histories
            ]
        except Exception as e:
            print(f"⚠️ 대화 히스토리 조회 실패: {e}")
            return []
    
    def _detect_context_from_history(self, context_history: List[Dict]) -> str:
        """대화 히스토리에서 맥락 파악 (시뮬레이션 vs 학습현황)"""
        if not context_history:
            return "general"
        
        # 최근 대화에서 시뮬레이션 관련 키워드 확인 (더 구체적인 키워드 사용)
        simulation_keywords = ["시뮬레이션", "simulation", "실습", "연습"]
        # 학습현황 관련 키워드 (점수는 제외 - 시뮬레이션 점수와 혼동 가능)
        learning_keywords = ["학습현황", "학습 현황", "공부", "시험", "성적", "학습"]
        
        simulation_score = 0
        learning_score = 0
        
        # 최근 대화부터 확인 (최근 것이 더 중요)
        for i, history in enumerate(context_history[:3]):  # 최근 3개만 확인
            user_msg = history.get("user_message", "").lower()
            bot_msg = history.get("bot_response", "").lower()
            
            # 가중치: 최근 대화일수록 높은 가중치
            weight = 3 - i  # 첫 번째: 3, 두 번째: 2, 세 번째: 1
            
            # 사용자 메시지 확인
            for keyword in simulation_keywords:
                if keyword in user_msg:
                    simulation_score += weight * 2  # 사용자 메시지가 더 중요
                    break
            
            for keyword in learning_keywords:
                if keyword in user_msg:
                    learning_score += weight * 2
                    break
            
            # 봇 응답 확인
            for keyword in simulation_keywords:
                if keyword in bot_msg:
                    simulation_score += weight
                    break
            
            for keyword in learning_keywords:
                if keyword in bot_msg:
                    learning_score += weight
                    break
            
            # 봇 응답에서 시뮬레이션 관련 특정 패턴 확인
            simulation_patterns = ["🎭", "시뮬레이션 성과", "시뮬레이션 점수", "실습", "RAG 시뮬레이션", "시뮬레이션 평가"]
            if any(pattern in bot_msg for pattern in simulation_patterns):
                simulation_score += weight * 3  # 패턴이 더 명확하므로 가중치 높임
            
            # 사용자 메시지에서도 "시뮬레이션 점수" 같은 조합 확인
            if "시뮬레이션" in user_msg and ("점수" in user_msg or "어때" in user_msg):
                simulation_score += weight * 3
            
            # 봇 응답에서 학습현황 관련 특정 패턴 확인
            learning_patterns = ["📊", "학습현황", "시험 성적", "시험 점수"]
            if any(pattern in bot_msg for pattern in learning_patterns):
                learning_score += weight * 3
        
        # 점수 비교
        if simulation_score > learning_score * 1.5:  # 시뮬레이션이 명확히 더 높으면
            return "simulation"
        elif learning_score > simulation_score * 1.5:  # 학습현황이 명확히 더 높으면
            return "learning"
        else:
            return "general"
    
    def get_query_type(self, message: str, context_history: Optional[List[Dict]] = None) -> str:
        """쿼리 유형 분석 (대화 맥락 고려)"""
        message = message.lower().strip()
        
        # 0) 명시적인 의도 우선 처리
        if "시뮬레이션 강점" in message or ("시뮬레이션" in message and "강점" in message):
            return "simulation_strong"
        if "시뮬레이션 약점" in message or ("시뮬레이션" in message and "약점" in message):
            return "simulation_weak"
        if "시험 강점" in message or "학습 강점" in message:
            return "strong_areas"  # 학습/시험 기준 강점
        if "시험 약점" in message or "학습 약점" in message:
            return "weak_areas"
        
        # 시뮬레이션 관련 키워드 확인 (우선순위 높음)
        has_simulation = any(kw in message for kw in self._learning_keywords["simulation"])
        
        # 학습현황 관련 키워드 확인
        has_learning = any(kw in message for kw in self._learning_keywords["general"])
        
        # 상대적 약점/강점 질문 체크
        has_relative = any(kw in message for kw in self._learning_keywords["relative"])
        has_weak = any(kw in message for kw in self._learning_keywords["weak"])
        has_strong = any(kw in message for kw in self._learning_keywords["strong"])
        
        # 학습현황과 시뮬레이션을 모두 물어본 경우 (예: "학습현황이랑 시뮬레이션 점수 어때?")
        if has_learning and has_simulation:
            # "학습현황"이 명시적으로 있으면 (예: "학습현황이랑", "학습현황과", "학습현황 어때")
            # 시뮬레이션도 함께 물어본 것으로 판단하여 둘 다 보여줌
            if any(phrase in message for phrase in ["학습현황", "학습 현황", "학습이랑", "학습과"]):
                return "both"
            # "시뮬레이션 현황"만 있는 경우 (학습현황이 명시되지 않은 경우)
            # 단순히 "시뮬레이션 현황" 또는 "시뮬레이션 상황"만 있으면 시뮬레이션으로 처리
            if "시뮬레이션" in message and ("현황" in message or "상황" in message):
                # 학습현황이 명시적으로 없고 시뮬레이션 현황만 있는 경우
                pass  # 시뮬레이션 처리 로직으로 넘어감
            else:
                # 그 외의 경우는 둘 다 처리
                return "both"
        
        # 시뮬레이션 관련 질문인 경우
        if has_simulation:
            if has_weak:
                return "simulation_weak"
            elif has_strong:
                return "simulation_strong"
            else:
                return "simulation"
        
        # 대화 맥락 파악 (강점/약점만 물어봤을 때)
        if (has_weak or has_strong) and not has_simulation:
            if context_history:
                # 직전 대화만 따로 꺼냄
                recent_user_msg = context_history[0].get("user_message", "").lower()
                recent_bot_msg = context_history[0].get("bot_response", "").lower()
                
                # 1) 직전이 시뮬레이션 문맥이면 무조건 시뮬레이션으로
                sim_triggers = ["시뮬레이션", "simulation", "실습", "연습", "RAG 시뮬레이션", "시뮬레이션 평가", "시뮬레이션 점수", "🎭"]
                if any(t in recent_user_msg for t in sim_triggers) or any(t in recent_bot_msg for t in sim_triggers):
                    print(f"🔍 직전 대화가 시뮬레이션 맥락 → 강점/약점은 시뮬레이션 기준으로 처리 (msg='{message}')")
                    if has_weak:
                        return "simulation_weak"
                    elif has_strong:
                        return "simulation_strong"
                    else:
                        return "simulation"
                
                # 2) 그 외의 경우에만 기존 맥락 감지 로직 사용
                context = self._detect_context_from_history(context_history)
                print(f"🔍 맥락 감지 결과: {context} (질문: {message})")
                
                if context == "simulation":
                    if has_weak:
                        return "simulation_weak"
                    elif has_strong:
                        return "simulation_strong"
                    else:
                        return "simulation"
                elif context == "learning":
                    # 학습현황 맥락이면 아래 일반 학습현황 분기로 떨어짐
                    pass
            # context_history 없으면 아래 일반 학습 분기로
        
        # 일반 학습현황 질문
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
        elif any(kw in message for kw in self._learning_keywords["score"]):
            return "scores"
        else:
            return "overall"
    
    def analyze_learning_progress(self, user: User) -> Dict:
        """사용자의 학습현황 종합 분석"""
        
        # 1. 시험 성적 분석
        exam_analysis = self._analyze_exam_scores(user.id)
        
        # 2. 시뮬레이션 성과 분석
        simulation_analysis = self._analyze_simulation_progress(user.id)
        
        # 3. 채팅 활동 분석
        chat_analysis = self._analyze_chat_activity(user.id)
        
        # 4. 학습 주제별 진도 분석
        learning_topics_analysis = self._analyze_learning_topics(user.id)
        
        # 5. 종합 분석
        overall_analysis = self._generate_overall_analysis(
            exam_analysis,
            simulation_analysis,
            chat_analysis,
            learning_topics_analysis
        )
        
        return {
            "exam": exam_analysis,
            "simulation": simulation_analysis,
            "chat": chat_analysis,
            "learning_topics": learning_topics_analysis,
            "overall": overall_analysis,
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
        """시뮬레이션 진행 상황 분석 (일반 시뮬레이션 + RAG 시뮬레이션 + SimulationFeedback 포함)"""
        
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
        
        # RAG 시뮬레이션 평가 결과
        rag_eval_statement = (
            select(RAGSimulationEvaluation)
            .where(RAGSimulationEvaluation.user_id == user_id)
            .order_by(RAGSimulationEvaluation.created_at.desc())
            .limit(10)
        )
        rag_evals = list(self.session.exec(rag_eval_statement).all())
        
        # SimulationFeedback 조회 (RAG 시뮬레이션 피드백)
        feedback_statement = (
            select(SimulationFeedback)
            .where(SimulationFeedback.user_id == user_id)
            .order_by(SimulationFeedback.created_at.desc())
            .limit(10)
        )
        feedbacks = list(self.session.exec(feedback_statement).all())
        
        # 디버깅 로그
        print(f"🔍 시뮬레이션 데이터 조회 결과 (user_id={user_id}):")
        print(f"  - SimulationProgress: {progress is not None}")
        print(f"  - SimulationAttempt: {len(attempts)}개")
        print(f"  - RAGSimulationEvaluation: {len(rag_evals)}개")
        print(f"  - SimulationFeedback: {len(feedbacks)}개")
        
        if not progress and not attempts and not rag_evals and not feedbacks:
            return {
                "has_data": False,
                "message": "아직 시뮬레이션 기록이 없습니다."
            }
        
        # 통계 계산
        total_attempts = len(attempts) + len(rag_evals) + len(feedbacks)
        
        # 평균 점수 계산 (일반 시뮬레이션 + RAG 시뮬레이션 + SimulationFeedback)
        all_scores = []
        if attempts:
            all_scores.extend([a.final_score for a in attempts if a.final_score])
        if rag_evals:
            all_scores.extend([e.total_point for e in rag_evals if e.total_point])
        if feedbacks:
            all_scores.extend([f.overall_score for f in feedbacks if f.overall_score])
        
        avg_score = sum(all_scores) / len(all_scores) if all_scores else 0
        
        # 최근 성과
        recent_performance = []
        for attempt in attempts[:3]:
            recent_performance.append({
                "scenario": attempt.scenario_type or "일반",
                "score": attempt.final_score or 0,
                "date": attempt.started_at.isoformat() if attempt.started_at else "",
                "type": "일반"
            })
        
        # RAG 시뮬레이션 성과 추가
        for eval_obj in rag_evals[:3]:
            session_info = self.session.get(RAGSimulationSession, eval_obj.session_id)
            recent_performance.append({
                "scenario": session_info.scenario_title if session_info else "RAG 시뮬레이션",
                "score": eval_obj.total_point,
                "date": eval_obj.created_at.isoformat() if eval_obj.created_at else "",
                "type": "RAG",
                "grade": eval_obj.grade
            })
        
        # SimulationFeedback 성과 추가
        for feedback in feedbacks[:3]:
            situation_info = {}
            if feedback.situation_info:
                try:
                    if isinstance(feedback.situation_info, str):
                        situation_info = json.loads(feedback.situation_info)
                    elif isinstance(feedback.situation_info, dict):
                        situation_info = feedback.situation_info
                except (json.JSONDecodeError, TypeError):
                    situation_info = {}
            
            scenario_title = "시뮬레이션"
            if situation_info:
                scenario_title = situation_info.get("title") or situation_info.get("name") or "시뮬레이션"
            
            recent_performance.append({
                "scenario": scenario_title,
                "score": feedback.overall_score or 0,
                "date": feedback.created_at.isoformat() if feedback.created_at else "",
                "type": "Feedback",
                "grade": feedback.grade
            })
        
        # 약점 분석 (RAG 시뮬레이션 평가 + SimulationFeedback 기준)
        weak_areas = []
        avg_scores = {}
        
        if rag_evals:
            # RAG 시뮬레이션 평가 점수
            avg_scores = {
                "지식": sum(e.knowledge_point for e in rag_evals) / len(rag_evals),
                "기술": sum(e.skill_point for e in rag_evals) / len(rag_evals),
                "공감도": sum(e.empathy_point for e in rag_evals) / len(rag_evals),
                "명확성": sum(e.clarity_point for e in rag_evals) / len(rag_evals),
                "친절도": sum(e.kindness_point for e in rag_evals) / len(rag_evals),
                "자신감": sum(e.confidence_point for e in rag_evals) / len(rag_evals),
            }
        
        if feedbacks:
            # SimulationFeedback 점수도 포함
            feedback_count = len(feedbacks)
            if not avg_scores:
                avg_scores = {
                    "지식": 0, "기술": 0, "공감도": 0,
                    "명확성": 0, "친절도": 0, "자신감": 0
                }
            
            # SimulationFeedback의 점수를 평균에 반영
            for feedback in feedbacks:
                if feedback.knowledge_score:
                    avg_scores["지식"] = (avg_scores.get("지식", 0) * (len(rag_evals) if rag_evals else 0) + feedback.knowledge_score) / ((len(rag_evals) if rag_evals else 0) + 1)
                if feedback.skill_score:
                    avg_scores["기술"] = (avg_scores.get("기술", 0) * (len(rag_evals) if rag_evals else 0) + feedback.skill_score) / ((len(rag_evals) if rag_evals else 0) + 1)
                if feedback.empathy_score:
                    avg_scores["공감도"] = (avg_scores.get("공감도", 0) * (len(rag_evals) if rag_evals else 0) + feedback.empathy_score) / ((len(rag_evals) if rag_evals else 0) + 1)
                if feedback.clarity_score:
                    avg_scores["명확성"] = (avg_scores.get("명확성", 0) * (len(rag_evals) if rag_evals else 0) + feedback.clarity_score) / ((len(rag_evals) if rag_evals else 0) + 1)
                if feedback.kindness_score:
                    avg_scores["친절도"] = (avg_scores.get("친절도", 0) * (len(rag_evals) if rag_evals else 0) + feedback.kindness_score) / ((len(rag_evals) if rag_evals else 0) + 1)
                if feedback.confidence_score:
                    avg_scores["자신감"] = (avg_scores.get("자신감", 0) * (len(rag_evals) if rag_evals else 0) + feedback.confidence_score) / ((len(rag_evals) if rag_evals else 0) + 1)
        
        if avg_scores:
            sorted_areas = sorted(avg_scores.items(), key=lambda x: x[1])
            weak_areas = [area for area, score in sorted_areas[:3] if score < 70]
        
        # 강점 분석
        strong_areas = []
        if avg_scores:
            sorted_areas = sorted(avg_scores.items(), key=lambda x: x[1], reverse=True)
            strong_areas = [area for area, score in sorted_areas[:3] if score >= 80]
        
        return {
            "has_data": True,
            "total_attempts": total_attempts,
            "average_score": round(avg_score, 1) if avg_score else 0,
            "recent_performance": recent_performance,
            "completed_scenarios": json.loads(progress.completed_scenarios) if progress and progress.completed_scenarios else [],
            "weak_areas": weak_areas,
            "strong_areas": strong_areas,
            "rag_evaluations": len(rag_evals),
            "feedbacks": len(feedbacks)
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
    
    def _analyze_learning_topics(self, user_id: int) -> Dict:
        """학습 주제별 진도 분석"""
        
        # 학습 주제 조회
        topics_statement = (
            select(LearningTopic)
            .where(LearningTopic.mentee_id == user_id)
        )
        topics = list(self.session.exec(topics_statement).all())
        
        if not topics:
            return {
                "has_data": False,
                "message": "아직 추천된 학습 주제가 없습니다."
            }
        
        # 통계 계산
        total_topics = len(topics)
        studied_topics = [t for t in topics if t.is_studied]
        not_studied_topics = [t for t in topics if not t.is_studied]
        
        studied_count = len(studied_topics)
        completion_rate = (studied_count / total_topics * 100) if total_topics > 0 else 0
        
        # 카테고리별 통계
        category_stats = {}
        for topic in topics:
            category = topic.topic_category or "기타"
            if category not in category_stats:
                category_stats[category] = {
                    "total": 0,
                    "studied": 0,
                    "topics": []
                }
            category_stats[category]["total"] += 1
            if topic.is_studied:
                category_stats[category]["studied"] += 1
            category_stats[category]["topics"].append({
                "name": topic.topic_name,
                "is_studied": topic.is_studied,
                "study_date": topic.study_date.isoformat() if topic.study_date else None
            })
        
        # 미학습 주제 (최근 생성된 순으로 상위 5개)
        priority_topics = not_studied_topics[:5]
        
        return {
            "has_data": True,
            "total_topics": total_topics,
            "studied_count": studied_count,
            "not_studied_count": len(not_studied_topics),
            "completion_rate": round(completion_rate, 1),
            "category_stats": category_stats,
            "priority_topics": [
                {
                    "name": t.topic_name,
                    "category": t.topic_category or "기타"
                }
                for t in priority_topics
            ],
            "recent_studied": [
                {
                    "name": t.topic_name,
                    "category": t.topic_category or "기타",
                    "study_date": t.study_date.isoformat() if t.study_date else None
                }
                for t in sorted(studied_topics, key=lambda t: t.study_date or datetime.min, reverse=True)[:5]
            ]
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
        chat: Dict,
        learning_topics: Optional[Dict] = None
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
        
        # 학습 주제 정보도 종합 분석에 포함
        learning_completion_rate = 0
        if learning_topics and learning_topics.get("has_data"):
            learning_completion_rate = learning_topics.get("completion_rate", 0)
            # 학습 레벨 점수 계산에 학습 주제 완료율도 반영
            level_score += min(learning_completion_rate / 100 * 10, 10)
        
        return {
            "level": level,
            "level_score": round(level_score, 1),
            "overall_weak_areas": list(set(all_weak_areas)),
            "overall_strong_areas": list(set(all_strong_areas)),
            "engagement": chat["engagement_level"],
            "learning_completion_rate": learning_completion_rate
        }
    
    def generate_response(self, user: User, message: str, context_history: Optional[List[Dict]] = None) -> str:
        """학습현황 관련 응답 생성"""
        
        # 대화 맥락 파악 (최근 대화 히스토리 확인)
        if context_history is None:
            context_history = self._get_recent_chat_history(user.id, limit=5)
        
        # 맥락에 따라 쿼리 타입 조정
        query_type = self.get_query_type(message, context_history)
        print(f"🔍 학습현황 쿼리 타입: {query_type} (질문: {message})")
        analysis = self.analyze_learning_progress(user)
        print(f"🔍 분석 결과 - 시뮬레이션 has_data: {analysis['simulation'].get('has_data', False)}")
        
        if query_type == "both":
            return self._generate_both_response(user, analysis)
        elif query_type == "simulation_weak":
            return self._generate_simulation_weak_response(user, analysis)
        elif query_type == "simulation_strong":
            return self._generate_simulation_strong_response(user, analysis)
        elif query_type == "relative_weak_areas":
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
        elif query_type == "simulation":
            return self._generate_simulation_response(user, analysis)
        else:
            return self._generate_overall_response(user, analysis)
    
    def _generate_both_response(self, user: User, analysis: Dict) -> str:
        """학습현황과 시뮬레이션 점수를 함께 보여주는 응답"""
        exam = analysis["exam"]
        simulation = analysis["simulation"]
        learning_topics = analysis.get("learning_topics", {})
        overall = analysis["overall"]
        
        response = f"""📊 **{user.name}님의 학습현황과 시뮬레이션 점수**

"""
        
        # 학습현황 부분
        response += """📚 **학습현황**
"""
        if exam.get("has_data"):
            response += f"- 최근 시험: {exam['latest_exam']['name']} ({exam['latest_exam']['grade']})\n"
            response += f"- 평균 점수: {exam['average_score']}점\n"
            response += f"- 추세: {self._get_trend_emoji(exam['trend'])} {exam['trend']}\n\n"
        else:
            response += """- 아직 시험 기록이 없습니다. 📝

"""
        
        # 학습 주제 진도 부분
        if learning_topics.get("has_data"):
            response += """📖 **학습 주제 진도**
"""
            response += f"- 총 학습 주제: {learning_topics['total_topics']}개\n"
            response += f"- 완료: {learning_topics['studied_count']}개 / 미완료: {learning_topics['not_studied_count']}개\n"
            response += f"- 완료율: {learning_topics['completion_rate']}%\n\n"
        
        # 시뮬레이션 점수 부분
        response += """🎭 **시뮬레이션 점수**
"""
        if simulation.get("has_data"):
            response += f"- 총 실습 횟수: {simulation['total_attempts']}회\n"
            response += f"- 평균 점수: {simulation['average_score']}점\n"
            if simulation.get('rag_evaluations', 0) > 0:
                response += f"- RAG 시뮬레이션 평가: {simulation['rag_evaluations']}회\n"
            
            # 최근 성과가 있으면 추가
            if simulation.get('recent_performance'):
                response += """\n- 최근 성과:
"""
                for perf in simulation['recent_performance'][:3]:
                    perf_type = perf.get('type', '')
                    grade_info = f" ({perf.get('grade', '')})" if perf.get('grade') else ""
                    type_info = f" [{perf_type}]" if perf_type else ""
                    response += f"  • {perf['scenario']}: {perf['score']}점{grade_info}{type_info} ({perf['date'][:10]})\n"
        else:
            response += """- 아직 시뮬레이션 기록이 없습니다. 실전 연습을 시작해보세요! 🎭

"""
        
        response += """
"""
        
        # 종합 평가
        response += f"""🎯 **종합 평가**
- 학습 레벨: {overall['level']} (점수: {overall['level_score']}/100)
- 학습 참여도: {overall['engagement']}

"""
        
        # 약점과 강점
        if overall['overall_weak_areas']:
            response += """⚠️ **보완이 필요한 영역**
"""
            for area in overall['overall_weak_areas'][:3]:
                response += f"- {area}\n"
            response += """
"""
        
        if overall['overall_strong_areas']:
            response += """✨ **강점 영역**
"""
            for area in overall['overall_strong_areas'][:3]:
                response += f"- {area}\n"
            response += """
"""
        
        response += "💡 꾸준한 학습과 실전 연습으로 더욱 발전해보세요!"
        
        return response
    
    def _generate_overall_response(self, user: User, analysis: Dict) -> str:
        """전체 학습현황 응답"""
        exam = analysis["exam"]
        simulation = analysis["simulation"]
        chat = analysis["chat"]
        learning_topics = analysis.get("learning_topics", {})
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
        
        # 학습 주제 진도
        if learning_topics.get("has_data"):
            response += f"""📖 **학습 주제 진도**
- 총 학습 주제: {learning_topics['total_topics']}개
- 완료: {learning_topics['studied_count']}개 / 미완료: {learning_topics['not_studied_count']}개
- 완료율: {learning_topics['completion_rate']}%

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
        """시뮬레이션 성과 응답 (일반 시뮬레이션 + RAG 시뮬레이션 포함)"""
        simulation = analysis["simulation"]
        
        if not simulation.get("has_data"):
            return "아직 시뮬레이션 기록이 없습니다. 실전 연습을 시작해보세요! 🎭"
        
        response = f"""🎭 **{user.name}님의 시뮬레이션 성과**

📊 **전체 통계**
- 총 실습 횟수: {simulation['total_attempts']}회
- 평균 점수: {simulation['average_score']}점
"""
        
        if simulation.get('rag_evaluations', 0) > 0:
            response += f"- RAG 시뮬레이션 평가: {simulation['rag_evaluations']}회\n"
        
        response += "\n"
        
        if simulation['recent_performance']:
            response += "📈 **최근 성과**\n"
            for perf in simulation['recent_performance']:
                perf_type = perf.get('type', '')
                grade_info = f" ({perf.get('grade', '')})" if perf.get('grade') else ""
                type_info = f" [{perf_type}]" if perf_type else ""
                response += f"- {perf['scenario']}: {perf['score']}점{grade_info}{type_info} ({perf['date'][:10]})\n"
            response += "\n"
        
        if simulation['weak_areas']:
            response += "⚠️ **보완이 필요한 영역**\n"
            for area in simulation['weak_areas'][:3]:
                response += f"- {area}\n"
            response += "\n"
        
        if simulation['strong_areas']:
            response += "✨ **강점 영역**\n"
            for area in simulation['strong_areas'][:3]:
                response += f"- {area}\n"
            response += "\n"
        
        response += "💡 실전 연습을 통해 실력이 향상되고 있습니다. 계속해서 도전하세요!"
        
        return response
    
    def _generate_simulation_strong_response(self, user: User, analysis: Dict) -> str:
        """시뮬레이션 강점 분석 응답"""
        simulation = analysis["simulation"]
        
        if not simulation.get("has_data"):
            return "아직 시뮬레이션 기록이 없습니다. 실전 연습을 시작해보세요! 🎭"
        
        response = f"""✨ **{user.name}님의 시뮬레이션 강점 영역**

"""
        
        if simulation.get('strong_areas'):
            response += "🌟 **특히 뛰어난 영역**\n"
            for area in simulation['strong_areas']:
                response += f"- {area} 🌟\n"
            response += "\n"
        else:
            response += "💡 아직 두드러진 강점이 나타나지 않았지만, 꾸준히 연습하시면 곧 강점 영역이 생길 거예요!\n\n"
        
        if simulation.get('recent_performance'):
            response += "📈 **최근 우수한 성과**\n"
            for perf in simulation['recent_performance'][:3]:
                if perf.get('score', 0) >= 80:
                    response += f"- {perf['scenario']}: {perf['score']}점 ({perf['date'][:10]})\n"
            response += "\n"
        
        response += "👍 정말 훌륭합니다! 이 강점을 활용해서 다른 영역도 발전시켜보세요."
        
        return response
    
    def _generate_simulation_weak_response(self, user: User, analysis: Dict) -> str:
        """시뮬레이션 약점 분석 응답"""
        simulation = analysis["simulation"]
        
        if not simulation.get("has_data"):
            return "아직 시뮬레이션 기록이 없습니다. 실전 연습을 시작해보세요! 🎭"
        
        response = f"""⚠️ **{user.name}님의 시뮬레이션 보완이 필요한 영역**

"""
        
        if simulation.get('weak_areas'):
            response += "📉 **개선이 필요한 영역**\n"
            for area in simulation['weak_areas']:
                response += f"- {area}\n"
                response += f"  💡 {self._get_simulation_improvement_tip(area)}\n\n"
        else:
            response += "🎉 모든 영역에서 우수한 성과를 보이고 있습니다!\n\n"
        
        response += "💪 꾸준한 연습을 통해 더욱 발전해보세요!"
        
        return response
    
    def _get_simulation_improvement_tip(self, area: str) -> str:
        """시뮬레이션 영역별 개선 팁"""
        tips = {
            "지식": "은행 상품과 업무 프로세스에 대한 지식을 더 학습하세요",
            "기술": "고객 응대 기술과 절차를 반복 연습하세요",
            "공감도": "고객의 감정을 이해하고 공감하는 연습을 하세요",
            "명확성": "설명을 명확하고 이해하기 쉽게 전달하는 연습을 하세요",
            "친절도": "고객에게 친절하고 배려하는 태도를 기르세요",
            "자신감": "은행 업무에 대한 자신감을 키우기 위해 지속적으로 학습하세요"
        }
        return tips.get(area, "해당 영역의 기초부터 차근차근 학습하세요")
    
    def _generate_recommendations(self, analysis: Dict) -> str:
        """학습 추천 생성"""
        overall = analysis["overall"]
        exam = analysis["exam"]
        learning_topics = analysis.get("learning_topics", {})
        
        recommendations = "💡 **추천 학습 계획**\n\n"
        
        # 학습 주제 기반 추천 (최우선)
        if learning_topics.get("has_data") and learning_topics.get("priority_topics"):
            recommendations += "**📖 우선 학습 주제**\n"
            for i, topic in enumerate(learning_topics["priority_topics"][:5], 1):
                category = topic.get("category", "기타")
                recommendations += f"{i}. {topic['name']} ({category})\n"
            recommendations += "\n"
        
        # 약점 기반 추천
        if overall['overall_weak_areas']:
            recommendations += "**우선 학습 영역**\n"
            for i, area in enumerate(overall['overall_weak_areas'][:3], 1):
                recommendations += f"{i}. {area}\n"
                recommendations += f"   - {self._get_study_resource(area)}\n"
            recommendations += "\n"
        
        # 학습 주제 완료율이 낮은 경우
        if learning_topics.get("has_data"):
            completion_rate = learning_topics.get("completion_rate", 0)
            if completion_rate < 50:
                recommendations += "**📚 학습 주제 완료율 개선 필요**\n"
                recommendations += f"- 현재 완료율: {completion_rate}%\n"
                recommendations += "- 추천된 학습 주제를 순서대로 학습하세요\n\n"
        
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

