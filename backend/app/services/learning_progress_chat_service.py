"""
학습현황 분석 챗봇 서비스
사용자의 학습 데이터를 분석하고 개인화된 피드백과 추천을 제공
"""
from typing import Dict, List, Optional, Tuple
from sqlmodel import Session, select, func
from datetime import datetime, timedelta, date, timezone
import json
import re

from app.models.user import User

# 한국 시간대 (KST = UTC+9) - 상수로 정의
KST = timezone(timedelta(hours=9))
from app.models.mentor import ExamScore, ChatHistory
from app.models.simulation import SimulationAttempt, SimulationProgress
from app.models.simulation_feedback import SimulationFeedback
from app.models.rag_simulation import RAGSimulationSession


class LearningProgressChatService:
    """학습현황 분석 및 챗봇 응답 서비스"""
    
    @staticmethod
    def _to_kst(utc_datetime: datetime) -> datetime:
        """UTC datetime을 한국 시간(KST)으로 변환
        
        주의: PostgreSQL의 timezone이 'Asia/Seoul'로 설정되어 있으면,
        naive datetime이 저장될 때 KST로 해석될 수 있습니다.
        
        따라서 두 가지 경우를 모두 처리:
        1. UTC로 저장된 경우: +9시간 추가
        2. KST로 저장된 경우: 그대로 사용
        """
        if utc_datetime is None:
            return None
        
        # naive datetime인 경우 (타임존 정보 없음)
        if utc_datetime.tzinfo is None:
            # PostgreSQL의 timezone이 'Asia/Seoul'로 설정되어 있으므로,
            # naive datetime은 이미 KST로 저장되었습니다.
            # 따라서 KST로 간주하고 타임존 정보만 추가합니다.
            kst_time = utc_datetime.replace(tzinfo=KST)
            print(f"🔍 [타임존 변환] naive datetime: {utc_datetime} (KST로 간주) → {kst_time}")
            return kst_time
        else:
            # 이미 타임존 정보가 있으면 그대로 변환
            kst_time = utc_datetime.astimezone(KST)
            print(f"🔍 [타임존 변환] aware datetime: {utc_datetime} → {kst_time} (KST)")
            return kst_time
    
    @staticmethod
    def _get_kst_date(utc_datetime: datetime) -> date:
        """UTC datetime을 한국 시간 기준 날짜로 변환"""
        if utc_datetime is None:
            return None
        kst_time = LearningProgressChatService._to_kst(utc_datetime)
        return kst_time.date()
    
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
            "exam_trend": ["시험 추이", "시험 점수 추이", "시험 성적 추이", "시험 성과 추이", "성적 추이", "시험 변화", "시험 트렌드"],
            "date_based": ["월", "일", "짜", "날짜", "일자"]
        }
    
    def _parse_date_from_message(self, message: str, user: Optional[User] = None) -> Optional[date]:
        """메시지에서 날짜 추출 (예: 12월 2일, 11월 25일, 2025-12-02 등)"""
        if not message:
            return None
        message = str(message).strip()
        current_year = datetime.now().year
        
        # 디버깅: 날짜 파싱 시도
        print(f"🔍 [날짜 파싱 시도] 메시지: '{message}'")
        
        # 패턴 1: YYYY-MM-DD 형식 (예: 2025-12-02)
        pattern1 = r'(\d{4})-(\d{1,2})-(\d{1,2})'
        match = re.search(pattern1, message)
        if match:
            try:
                year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
                return date(year, month, day)
            except (ValueError, IndexError):
                pass
        
        # 패턴 2: M월 D일 형식 (예: 12월 2일, 11월 25일)
        pattern2 = r'(\d{1,2})\s*월\s*(\d{1,2})\s*일'
        match = re.search(pattern2, message)
        if match:
            try:
                month, day = int(match.group(1)), int(match.group(2))
                if 1 <= month <= 12 and 1 <= day <= 31:
                    # 연도가 명시되지 않은 경우, 사용자의 기록에서 실제 연도 찾기
                    if user:
                        # 시험 점수 질문인지 확인
                        is_exam_query = any(keyword in message.lower() for keyword in ['시험', '점수', '성적', '시험점수', '시험 점수'])
                        if is_exam_query:
                            # 시험 점수에서 연도 찾기
                            actual_year = self._find_year_from_exam_scores(user, month, day)
                            if actual_year:
                                print(f"🔍 [날짜 파싱] 시험 점수에서 찾은 연도: {actual_year}년 {month}월 {day}일")
                                return date(actual_year, month, day)
                        # 퀴즈 기록에서 연도 찾기
                        actual_year = self._find_year_from_quiz_logs(user, month, day)
                        if actual_year:
                            print(f"🔍 [날짜 파싱] 사용자 기록에서 찾은 연도: {actual_year}년 {month}월 {day}일")
                            return date(actual_year, month, day)
                    # 사용자 정보가 없거나 기록이 없으면 현재 연도 사용
                    print(f"🔍 [날짜 파싱] 현재 연도 사용: {current_year}년 {month}월 {day}일")
                    return date(current_year, month, day)
            except (ValueError, IndexError):
                pass
        
        # 패턴 3: M/D 형식 (예: 12/2, 11/25)
        pattern3 = r'(\d{1,2})/(\d{1,2})'
        match = re.search(pattern3, message)
        if match:
            try:
                month, day = int(match.group(1)), int(match.group(2))
                if 1 <= month <= 12 and 1 <= day <= 31:
                    # 연도가 명시되지 않은 경우, 사용자의 기록에서 실제 연도 찾기
                    if user:
                        # 시험 점수 질문인지 확인
                        is_exam_query = any(keyword in message.lower() for keyword in ['시험', '점수', '성적', '시험점수', '시험 점수'])
                        if is_exam_query:
                            # 시험 점수에서 연도 찾기
                            actual_year = self._find_year_from_exam_scores(user, month, day)
                            if actual_year:
                                print(f"🔍 [날짜 파싱] 시험 점수에서 찾은 연도: {actual_year}년 {month}월 {day}일")
                                return date(actual_year, month, day)
                        # 퀴즈 기록에서 연도 찾기
                        actual_year = self._find_year_from_quiz_logs(user, month, day)
                        if actual_year:
                            print(f"🔍 [날짜 파싱] 사용자 기록에서 찾은 연도: {actual_year}년 {month}월 {day}일")
                            return date(actual_year, month, day)
                    # 사용자 정보가 없거나 기록이 없으면 현재 연도 사용
                    print(f"🔍 [날짜 파싱] 현재 연도 사용: {current_year}년 {month}월 {day}일")
                    return date(current_year, month, day)
            except (ValueError, IndexError):
                pass
        
        return None
    
    def _extract_relative_date(self, message: str) -> Optional[Tuple[date, Optional[date]]]:
        """상대적 날짜 표현 파싱 (예: 지난주, 2주전, 3일전 등)
        
        Returns:
            (시작일, 종료일) 튜플. 단일 날짜인 경우 (날짜, None)
        """
        if not message:
            return None
        message_lower = message.lower().strip()
        today = datetime.now(KST).date()
        print(f"🔍 [상대적 날짜 파싱] 메시지: '{message}', 오늘 날짜: {today}")
        
        # 패턴 1: 지난주, 지난 주 (기간: 월요일 ~ 일요일)
        if "지난주" in message_lower or "지난 주" in message_lower:
            # 지난주 월요일 계산 (오늘 기준으로 지난주 월요일)
            days_since_monday = today.weekday()  # 0=월요일, 6=일요일
            last_monday = today - timedelta(days=days_since_monday + 7)
            last_sunday = last_monday + timedelta(days=6)
            print(f"🔍 [지난주 계산] 오늘: {today}, 지난주 월요일: {last_monday}, 지난주 일요일: {last_sunday}")
            return (last_monday, last_sunday)
        
        # 패턴 2: N주전, N주 전 (예: 2주전, 3주 전) - 해당 주의 월요일~일요일
        pattern_weeks = r'(\d+)\s*주\s*전'
        match = re.search(pattern_weeks, message_lower)
        if match:
            try:
                weeks_ago = int(match.group(1))
                # 해당 주의 월요일 계산
                target_week_monday = today - timedelta(weeks=weeks_ago, days=today.weekday())
                target_week_sunday = target_week_monday + timedelta(days=6)
                print(f"🔍 [N주전 계산] 오늘: {today}, {weeks_ago}주전 월요일: {target_week_monday}, 일요일: {target_week_sunday}")
                return (target_week_monday, target_week_sunday)
            except (ValueError, IndexError) as e:
                print(f"❌ [N주전 파싱 오류] {e}")
                pass
        
        # 패턴 3: N일전, N일 전 (예: 3일전, 5일 전) - 단일 날짜
        pattern_days = r'(\d+)\s*일\s*전'
        match = re.search(pattern_days, message_lower)
        if match:
            try:
                days_ago = int(match.group(1))
                target_date = today - timedelta(days=days_ago)
                print(f"🔍 [N일전 계산] 오늘: {today}, {days_ago}일전: {target_date}")
                return (target_date, None)
            except (ValueError, IndexError) as e:
                print(f"❌ [N일전 파싱 오류] {e}")
                pass
        
        print(f"❌ [상대적 날짜 파싱 실패] 패턴을 찾을 수 없습니다: '{message}'")
        return None
    
    def _get_simulation_results_by_date(self, user: User, start_date: date, end_date: Optional[date] = None) -> List[Dict]:
        """특정 날짜 또는 기간의 시뮬레이션 결과 조회
        
        Args:
            user: 사용자
            start_date: 시작 날짜
            end_date: 종료 날짜 (None이면 start_date만 조회)
        """
        from app.models.simulation_feedback import SimulationFeedback
        
        try:
            # 종료일이 없으면 시작일만 조회
            if end_date is None:
                end_date = start_date
            
            print(f"🔍 [시뮬레이션 조회] 사용자: {user.id}, 기간: {start_date} ~ {end_date}")
            
            # 모든 시뮬레이션 결과 조회 (날짜 필터링은 나중에 KST로 변환하여 수행)
            simulation_statement = (
                select(SimulationFeedback)
                .where(SimulationFeedback.user_id == user.id)
                .order_by(SimulationFeedback.created_at.desc())
            )
            all_simulations = list(self.session.exec(simulation_statement).all())
            
            print(f"🔍 [시뮬레이션 조회] 전체 결과 수: {len(all_simulations)}")
            
            result = []
            for sim in all_simulations:
                try:
                    # created_at의 실제 값과 타입 확인
                    created_at_value = sim.created_at
                    tzinfo = getattr(created_at_value, 'tzinfo', None)
                    print(f"🔍 [시뮬레이션 원본] sim.id={sim.id}, created_at={created_at_value}, 타입={type(created_at_value)}, tzinfo={tzinfo}")
                    
                    # KST로 변환하여 날짜 확인
                    kst_datetime = self._to_kst(created_at_value)
                    sim_date_kst = kst_datetime.date()
                    print(f"🔍 [시뮬레이션 날짜 확인] sim.id={sim.id}, 원본={created_at_value}, KST={kst_datetime}, 날짜={sim_date_kst}, 범위: {start_date} ~ {end_date}")
                    
                    # 날짜 범위 확인
                    if start_date <= sim_date_kst <= end_date:
                        print(f"✅ [시뮬레이션 포함] sim.id={sim.id}, 날짜: {sim_date_kst}")
                        result.append({
                            "id": sim.id,
                            "scenario_title": sim.scenario_title or "일반",
                            "created_at": created_at_value.isoformat() if hasattr(created_at_value, 'isoformat') else str(created_at_value),
                            "overall_score": sim.overall_score,
                            "knowledge_score": sim.knowledge_score,
                            "skill_score": sim.skill_score,
                            "clarity_score": sim.clarity_score,
                            "kindness_score": sim.kindness_score,
                            "confidence_score": sim.confidence_score,
                            "feedback_summary": sim.feedback_summary
                        })
                    else:
                        print(f"❌ [시뮬레이션 제외] sim.id={sim.id}, 날짜: {sim_date_kst} (범위 밖: {start_date} <= {sim_date_kst} <= {end_date})")
                except Exception as e:
                    print(f"⚠️ [시뮬레이션 결과 처리 오류] {e}, sim.id: {sim.id}")
                    import traceback
                    print(traceback.format_exc())
                    continue
            
            print(f"🔍 [시뮬레이션 조회] 최종 결과 수: {len(result)}")
            return result
        except Exception as e:
            import traceback
            print(f"❌ [시뮬레이션 조회 오류] {e}")
            print(traceback.format_exc())
            return []
    
    def _generate_date_based_simulation_response(self, user: User, date_range: Optional[Tuple[date, Optional[date]]]) -> str:
        """특정 날짜 또는 기간의 시뮬레이션 결과 응답 생성"""
        if date_range is None:
            return "날짜를 찾을 수 없습니다. 예: '지난주 시뮬레이션', '2주전 시뮬레이션 결과'"
        
        try:
            start_date, end_date = date_range
        except (ValueError, TypeError) as e:
            print(f"❌ [날짜 범위 파싱 오류] {e}, date_range: {date_range}")
            return "날짜를 찾을 수 없습니다. 예: '지난주 시뮬레이션', '2주전 시뮬레이션 결과'"
        
        # 날짜 문자열 생성
        if end_date:
            date_str = f"{start_date.strftime('%Y년 %m월 %d일')} ~ {end_date.strftime('%m월 %d일')}"
        else:
            date_str = start_date.strftime("%Y년 %m월 %d일")
        
        simulations = self._get_simulation_results_by_date(user, start_date, end_date)
        
        if not simulations:
            return f"📅 {date_str}에는 시뮬레이션 기록이 없습니다."
        
        response = f"📅 **{date_str} 시뮬레이션 결과**\n\n"
        
        # 평균 점수 계산
        if simulations:
            overall_scores = [s.get('overall_score', 0) for s in simulations if s.get('overall_score')]
            avg_score = sum(overall_scores) / len(overall_scores) if overall_scores else 0
            response += f"**총 {len(simulations)}회 실습, 평균 점수: {round(avg_score, 1)}점**\n\n"
        
        for i, sim in enumerate(simulations, 1):
            # created_at을 datetime으로 변환
            try:
                if isinstance(sim['created_at'], str):
                    # ISO 형식 문자열인 경우
                    if 'Z' in sim['created_at']:
                        sim_datetime = datetime.fromisoformat(sim['created_at'].replace('Z', '+00:00'))
                    else:
                        sim_datetime = datetime.fromisoformat(sim['created_at'])
                else:
                    sim_datetime = sim['created_at']
                sim_date = self._get_kst_date(sim_datetime)
                date_str = sim_date.strftime('%m월 %d일')
            except Exception as e:
                print(f"⚠️ [날짜 파싱 오류] {e}")
                date_str = ""
            response += f"**{i}. {sim.get('scenario_title', '일반')}**" + (f" ({date_str})" if date_str else "") + "\n"
            if sim.get('overall_score'):
                response += f"- 총점: {sim['overall_score']}점\n"
            if sim.get('knowledge_score'):
                response += f"- 지식: {sim['knowledge_score']}점\n"
            if sim.get('skill_score'):
                response += f"- 기술: {sim['skill_score']}점\n"
            if sim.get('clarity_score'):
                response += f"- 명확성: {sim['clarity_score']}점\n"
            if sim.get('kindness_score'):
                response += f"- 친절도: {sim['kindness_score']}점\n"
            if sim.get('confidence_score'):
                response += f"- 자신감: {sim['confidence_score']}점\n"
            if sim.get('feedback_summary'):
                feedback = sim['feedback_summary']
                if len(feedback) > 100:
                    response += f"- 피드백: {feedback[:100]}...\n"
                else:
                    response += f"- 피드백: {feedback}\n"
            response += "\n"
        
        return response
    
    def _find_year_from_exam_scores(self, user: User, month: int, day: int) -> Optional[int]:
        """사용자의 시험 점수 기록에서 해당 월/일이 있는 연도 찾기"""
        from app.models.mentor import ExamScore
        
        try:
            print(f"🔍 [시험 점수 연도 찾기 시작] 사용자 {user.id}, 찾을 날짜: {month}월 {day}일")
            
            # 사용자의 모든 시험 점수 기록 조회
            exam_scores_statement = (
                select(ExamScore)
                .where(ExamScore.mentee_id == user.id)
                .order_by(ExamScore.exam_date.desc())
            )
            exam_scores = list(self.session.exec(exam_scores_statement).all())
            
            print(f"🔍 [시험 점수 연도 찾기] 사용자 {user.id}의 시험 점수 기록 {len(exam_scores)}개 확인 중...")
            
            # 한국 시간대 고려
            # 처음 10개 기록의 날짜 출력 (디버깅용, 한국 시간 기준)
            print(f"🔍 [시험 점수 연도 찾기] 최근 기록 샘플 (최대 10개, KST 기준):")
            for i, exam in enumerate(exam_scores[:10], 1):
                kst_date = self._get_kst_date(exam.exam_date)
                print(f"🔍 [시험 점수 연도 찾기] 기록 {i}: {kst_date} (KST) / UTC: {exam.exam_date}")
            
            # 해당 월/일이 있는 연도 찾기 (최근 것 우선, 한국 시간 기준)
            for exam in exam_scores:
                exam_date = self._get_kst_date(exam.exam_date)
                if exam_date.month == month and exam_date.day == day:
                    found_year = exam_date.year
                    kst_time = self._to_kst(exam.exam_date)
                    print(f"🔍 [시험 점수 연도 찾기] ✅ 시험 점수에서 발견: {found_year}년 {month}월 {day}일 (KST: {kst_time}, UTC: {exam.exam_date})")
                    return found_year
            
            print(f"🔍 [시험 점수 연도 찾기] ❌ {month}월 {day}일과 일치하는 시험 점수 기록을 찾지 못했습니다.")
            kst_dates = [self._get_kst_date(exam.exam_date) for exam in exam_scores[:20]]
            print(f"🔍 [시험 점수 연도 찾기] 확인한 모든 기록의 날짜(KST): {kst_dates}")
            return None
        except Exception as e:
            print(f"❌ [시험 점수 연도 찾기 오류] {str(e)}")
            import traceback
            print(traceback.format_exc())
            return None
    
    def _find_year_from_quiz_logs(self, user: User, month: int, day: int) -> Optional[int]:
        """사용자의 퀴즈 기록에서 해당 월/일이 있는 연도 찾기"""
        from app.models import QuizGenerationLog
        
        try:
            print(f"🔍 [연도 찾기 시작] 사용자 {user.id}, 찾을 날짜: {month}월 {day}일")
            
            # 사용자의 모든 퀴즈 기록 조회
            quiz_logs_statement = (
                select(QuizGenerationLog)
                .where(
                    QuizGenerationLog.user_id == user.id,
                    QuizGenerationLog.answers.is_not(None)
                )
                .order_by(QuizGenerationLog.created_at.desc())
            )
            quiz_logs = list(self.session.exec(quiz_logs_statement).all())
            
            print(f"🔍 [연도 찾기] 사용자 {user.id}의 퀴즈 기록 {len(quiz_logs)}개 확인 중...")
            
            # 한국 시간대 고려
            # 처음 10개 기록의 날짜 출력 (디버깅용, 한국 시간 기준)
            print(f"🔍 [연도 찾기] 최근 기록 샘플 (최대 10개, KST 기준):")
            for i, log in enumerate(quiz_logs[:10], 1):
                kst_date = self._get_kst_date(log.created_at)
                print(f"🔍 [연도 찾기] 기록 {i}: {kst_date} (KST) / UTC: {log.created_at}")
            
            # 해당 월/일이 있는 연도 찾기 (최근 것 우선, 한국 시간 기준)
            for log in quiz_logs:
                log_date = self._get_kst_date(log.created_at)
                if log_date.month == month and log_date.day == day:
                    found_year = log_date.year
                    kst_time = self._to_kst(log.created_at)
                    print(f"🔍 [연도 찾기] ✅ 퀴즈 기록에서 발견: {found_year}년 {month}월 {day}일 (KST: {kst_time}, UTC: {log.created_at})")
                    return found_year
            
            print(f"🔍 [연도 찾기] ❌ {month}월 {day}일과 일치하는 퀴즈 기록을 찾지 못했습니다.")
            kst_dates = [self._get_kst_date(log.created_at) for log in quiz_logs[:20]]
            print(f"🔍 [연도 찾기] 확인한 모든 기록의 날짜(KST): {kst_dates}")
            return None
        except Exception as e:
            print(f"❌ [연도 찾기 오류] {str(e)}")
            import traceback
            print(traceback.format_exc())
            return None
    
    def is_learning_progress_query(self, message: str) -> bool:
        """학습현황 관련 쿼리인지 확인"""
        message = message.lower().strip()
        
        # 학습현황 관련 키워드 확인 (더 엄격한 매칭)
        # 학습 관련 키워드와 함께 나타나는 경우만 True 반환
        learning_context_keywords = ["학습", "공부", "성적", "점수", "시험", "평가", "약점", "강점", "추천"]
        has_learning_context = any(keyword in message for keyword in learning_context_keywords)
        
        if not has_learning_context:
            # 학습 맥락이 없으면 False 반환 (일반 질문으로 처리)
            return False
        
        # 학습 맥락이 있는 경우에만 키워드 확인
        for category, keywords in self._learning_keywords.items():
            for keyword in keywords:
                if keyword in message:
                    return True
        
        # 특정 패턴 확인 (학습 관련 패턴만)
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
    
    def get_query_type(self, message: str, context_history: Optional[List[Dict]] = None, user: Optional[User] = None) -> str:
        """쿼리 유형 분석 (맥락 고려)"""
        # 원본 메시지 저장 (날짜 파싱용)
        original_message = str(message).strip()
        message_lower = original_message.lower()
        
        # 날짜 기반 쿼리 체크 (가장 우선순위 높음 - 소문자 변환 전에 체크)
        # 사용자 정보가 있으면 실제 연도 찾기에 사용
        parsed_date = self._parse_date_from_message(original_message, user)
        has_date_keywords = any(kw in original_message for kw in ["월", "일", "짜", "날짜", "일자"]) or parsed_date is not None
        
        if has_date_keywords and parsed_date is not None:
            # 날짜가 파싱되면 날짜 기반 쿼리로 처리
            # 시험 관련 키워드가 있으면 날짜 기반 시험 점수
            if any(kw in original_message for kw in ["시험", "시험 점수", "시험성적", "시험 결과"]):
                return "date_based_exam_score"
            # 학습현황 관련 키워드가 있으면 날짜 기반 학습현황 (퀴즈 기록)
            elif any(kw in original_message for kw in ["학습", "학습현황", "학습 기록", "퀴즈", "퀴즈 기록"]):
                return "date_based_quiz"
            # 기본적으로 학습현황으로 처리 (퀴즈 기록)
            else:
                return "date_based_quiz"
        
        # 나머지 로직은 소문자 변환된 메시지 사용
        message = message_lower
        
        # 맥락 분석: 이전 대화에서 시뮬레이션/시험 관련 키워드 확인
        context_simulation = False
        context_exam = False
        
        # 최근 맥락의 인덱스 추적 (더 최근 맥락 우선)
        context_simulation_index = -1
        context_exam_index = -1
        
        if context_history:
            # 최근 대화 히스토리에서 맥락 파악 (최신 대화 우선)
            for idx, ctx in enumerate(reversed(context_history[:5])):  # 최근 5개 대화를 역순으로 확인 (최신이 우선)
                ctx_text = (ctx.get("user_message", "") + " " + ctx.get("bot_response", "")).lower()
                # 시뮬레이션 관련 키워드 (더 구체적인 키워드 우선)
                if any(kw in ctx_text for kw in ["시뮬레이션", "실습", "연습", "시뮬레이션 점수", "시뮬레이션 성과", "시뮬레이션 결과"]):
                    context_simulation = True
                    if context_simulation_index == -1:  # 첫 번째 발견만 기록
                        context_simulation_index = idx
                    # 시뮬레이션이 명확하면 시험 맥락은 덜 중요
                    if "시뮬레이션" in ctx_text:
                        break
                # 시험 관련 키워드 (더 구체적인 키워드 우선, "평가", "성적"은 너무 일반적이므로 제외)
                if any(kw in ctx_text for kw in ["시험", "시험 성적", "시험 점수", "시험 결과", "시험 평가"]):
                    context_exam = True
                    if context_exam_index == -1:  # 첫 번째 발견만 기록
                        context_exam_index = idx
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
                # 최근 3개 대화 확인 (더 넓은 범위로 최신 맥락 파악)
                for ctx in reversed(context_history[:3]):
                    ctx_text = (ctx.get("user_message", "") + " " + ctx.get("bot_response", "")).lower()
                    print(f"🔍 [맥락 체크] 대화: {ctx_text[:100]}...")
                    # 시뮬레이션 관련 키워드 체크 (더 구체적인 키워드 우선)
                    sim_keywords = ["시뮬레이션", "실습", "연습", "시뮬레이션 점수", "시뮬레이션 성과", "시뮬레이션 결과"]
                    if any(kw in ctx_text for kw in sim_keywords):
                        recent_context_simulation = True
                        # "시뮬레이션" 키워드가 명시적으로 있으면 가중치 높게
                        if "시뮬레이션" in ctx_text:
                            recent_simulation_keywords_count += 3
                            print(f"✅ [맥락 체크] 시뮬레이션 맥락 발견 (가중치 3): {ctx_text[:50]}")
                        else:
                            recent_simulation_keywords_count += sum(1 for kw in sim_keywords if kw in ctx_text)
                            print(f"✅ [맥락 체크] 시뮬레이션 맥락 발견 (가중치 {sum(1 for kw in sim_keywords if kw in ctx_text)}): {ctx_text[:50]}")
                    # 시험 관련 키워드 체크 (더 구체적인 키워드 우선)
                    # "성적", "평가"는 너무 일반적이므로 제외하고 명시적인 시험 키워드만 사용
                    exam_keywords = ["시험성적", "시험 성적", "시험 점수", "시험 결과", "시험 평가", "시험"]
                    if any(kw in ctx_text for kw in exam_keywords):
                        recent_context_exam = True
                        # 명시적인 시험 키워드가 있으면 더 높은 우선순위
                        if any(kw in ctx_text for kw in ["시험성적", "시험 성적", "시험 점수", "시험 결과", "시험 평가"]):
                            recent_exam_keywords_count += 3  # 명시적 키워드는 가중치 높게
                            print(f"✅ [맥락 체크] 시험 맥락 발견 (가중치 3): {ctx_text[:50]}")
                        elif "시험" in ctx_text:
                            recent_exam_keywords_count += 2  # "시험" 키워드도 가중치 적용
                            print(f"✅ [맥락 체크] 시험 맥락 발견 (가중치 2): {ctx_text[:50]}")
                        else:
                            recent_exam_keywords_count += 1
                            print(f"✅ [맥락 체크] 시험 맥락 발견 (가중치 1): {ctx_text[:50]}")
            
            print(f"🔍 [맥락 체크 결과] recent_context_simulation={recent_context_simulation} (가중치={recent_simulation_keywords_count}), recent_context_exam={recent_context_exam} (가중치={recent_exam_keywords_count})")
            
            # 최근 맥락에서 시험과 시뮬레이션이 모두 있으면, 더 명확한 쪽 우선
            # 시뮬레이션 키워드가 더 많거나 명시적이면 시뮬레이션 우선 (더 구체적)
            if recent_context_exam and recent_context_simulation:
                print(f"🔍 [맥락 충돌] 시험과 시뮬레이션 모두 발견. 시험 가중치={recent_exam_keywords_count}, 시뮬레이션 가중치={recent_simulation_keywords_count}")
                # 시뮬레이션 키워드가 더 많거나 같으면 시뮬레이션 우선 (더 구체적)
                if recent_simulation_keywords_count >= recent_exam_keywords_count:
                    print(f"✅ [맥락 충돌 해결] 시뮬레이션 우선 (가중치 {recent_simulation_keywords_count} >= {recent_exam_keywords_count}) → 시뮬레이션 강점/약점 반환")
                    # 시뮬레이션 맥락 우선
                    if has_relative and has_weak:
                        return "simulation_relative_weak_areas"
                    elif has_relative and has_strong:
                        return "simulation_relative_strong_areas"
                    elif has_weak:
                        return "simulation_weak_areas"
                    elif has_strong:
                        return "simulation_strong_areas"
                else:
                    print(f"✅ [맥락 충돌 해결] 시험 우선 (가중치 {recent_exam_keywords_count} > {recent_simulation_keywords_count}) → 시험 강점/약점 반환")
                    # 시험 맥락 우선
                    if has_relative and has_weak:
                        return "relative_weak_areas"
                    elif has_relative and has_strong:
                        return "relative_strong_areas"
                    elif has_weak:
                        return "weak_areas"
                    elif has_strong:
                        return "strong_areas"
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
                print(f"✅ [맥락 기반 결정] 시뮬레이션 맥락만 있음 → 시뮬레이션 강점/약점 반환")
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
                print(f"🔍 [전체 맥락 체크] context_simulation={context_simulation} (인덱스={context_simulation_index}), context_exam={context_exam} (인덱스={context_exam_index})")
                # 전체 맥락에서도 시험과 시뮬레이션 우선순위 판단
                # 더 최근 맥락을 우선시 (인덱스가 작을수록 더 최근)
                if context_exam and context_simulation:
                    # 더 최근 맥락 우선 (인덱스가 작을수록 더 최근)
                    if context_simulation_index != -1 and context_exam_index != -1:
                        # 시뮬레이션이 더 최근이면 시뮬레이션 우선
                        if context_simulation_index < context_exam_index:
                            print(f"✅ [전체 맥락 결정] 시뮬레이션이 더 최근 (인덱스 {context_simulation_index} < {context_exam_index}) → 시뮬레이션 강점/약점 반환")
                            if has_relative and has_weak:
                                return "simulation_relative_weak_areas"
                            elif has_relative and has_strong:
                                return "simulation_relative_strong_areas"
                            elif has_weak:
                                return "simulation_weak_areas"
                            elif has_strong:
                                return "simulation_strong_areas"
                        # 시험이 더 최근이면 시험 우선
                        else:
                            print(f"✅ [전체 맥락 결정] 시험이 더 최근 (인덱스 {context_exam_index} < {context_simulation_index}) → 시험 강점/약점 반환")
                            if has_relative and has_weak:
                                return "relative_weak_areas"
                            elif has_relative and has_strong:
                                return "relative_strong_areas"
                            elif has_weak:
                                return "weak_areas"
                            elif has_strong:
                                return "strong_areas"
                    # 인덱스 정보가 없으면 최근 맥락 체크 결과 사용
                    # 최근 맥락이 없으면 기본값으로 시험 우선 (학습현황이 더 일반적)
                    else:
                        # 최근 맥락 체크 결과가 있으면 그것을 사용
                        if recent_context_simulation and not recent_context_exam:
                            print(f"✅ [전체 맥락 결정] 최근 맥락 체크 결과: 시뮬레이션만 있음 → 시뮬레이션 강점/약점 반환")
                            if has_relative and has_weak:
                                return "simulation_relative_weak_areas"
                            elif has_relative and has_strong:
                                return "simulation_relative_strong_areas"
                            elif has_weak:
                                return "simulation_weak_areas"
                            elif has_strong:
                                return "simulation_strong_areas"
                        # 시뮬레이션이 전체 맥락에 있으면 시뮬레이션 우선 (더 구체적)
                        elif context_simulation:
                            print(f"✅ [전체 맥락 결정] 시뮬레이션 맥락이 있음 → 시뮬레이션 강점/약점 반환")
                            if has_relative and has_weak:
                                return "simulation_relative_weak_areas"
                            elif has_relative and has_strong:
                                return "simulation_relative_strong_areas"
                            elif has_weak:
                                return "simulation_weak_areas"
                            elif has_strong:
                                return "simulation_strong_areas"
                        # 기본값: 시험 우선 (학습현황)
                        else:
                            print(f"✅ [전체 맥락 결정] 기본값: 시험 강점/약점 반환")
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
        
        if has_date_keywords and parsed_date is not None:
            # 날짜가 파싱되면 날짜 기반 쿼리로 처리
            # 시험 관련 키워드가 있으면 날짜 기반 시험 점수
            if any(kw in message for kw in ["시험", "시험 점수", "시험성적", "시험 결과"]):
                return "date_based_exam_score"
            # 학습현황 관련 키워드가 있으면 날짜 기반 학습현황 (퀴즈 기록)
            elif any(kw in message for kw in ["학습", "학습현황", "학습 기록", "퀴즈", "퀴즈 기록"]):
                return "date_based_quiz"
            # 기본적으로 학습현황으로 처리 (퀴즈 기록)
            else:
                return "date_based_quiz"
        
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
            # 날짜 표현이 있으면 날짜 기반 시뮬레이션 조회
            date_range = self._extract_relative_date(message)
            if date_range:
                return "date_based_simulation"
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
            # 날짜 표현이 있으면 날짜 기반 시뮬레이션 조회
            date_range = self._extract_relative_date(message)
            if date_range:
                return "date_based_simulation"
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
        try:
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
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            print(f"❌ [학습현황 분석 오류] {str(e)}")
            print(f"상세 오류:\n{error_trace}")
            raise  # 상위로 전파하여 generate_response에서 처리
    
    def _get_dashboard_data(self, user: User) -> Dict:
        """대시보드 데이터 가져오기 (대시보드 API 직접 호출)"""
        from app.routers.dashboard import get_mentee_dashboard_data
        
        # 대시보드 API의 공통 함수를 직접 호출하여 데이터 가져오기
        dashboard_data = get_mentee_dashboard_data(user, self.session)
        return dashboard_data
    
    def _analyze_exam_scores_from_dashboard(self, dashboard_data: Dict) -> Dict:
        """대시보드 데이터에서 시험 성적 분석 (대시보드 레이더 차트와 동일한 데이터 사용)"""
        exam_scores = dashboard_data.get("exam_scores", [])
        quiz_aggregate_stats = dashboard_data.get("quiz_aggregate_stats", {})
        
        # 퀴즈 집계 통계가 있으면 우선 사용 (대시보드와 동일한 데이터)
        if quiz_aggregate_stats:
            # 퀴즈 집계 통계를 카테고리별 점수로 변환
            # 대시보드 레이더 차트와 동일하게 정확도 % 사용 (0-100 점수)
            categories = {}
            for cat, stats in quiz_aggregate_stats.items():
                # score 필드는 정확도 % (0-100)
                score_value = stats.get("score", 0)
                categories[cat] = score_value
            
            # 시험 점수가 있으면 함께 사용
            if exam_scores:
                latest_exam = exam_scores[0]
                score_data = latest_exam.get("score_data", {})
                if isinstance(score_data, dict):
                    # 시험 점수와 퀴즈 점수를 병합 (시험 점수가 있으면 우선)
                    for key in score_data:
                        if key in categories:
                            # 시험 점수가 더 높은 우선순위
                            exam_score = float(score_data.get(key, 0)) if score_data.get(key) is not None else 0
                            if exam_score > 0:
                                categories[key] = exam_score
        elif exam_scores:
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
            
            # 대시보드 카테고리 매핑 (금융영업, 상품개발 및 운용 등)
            if "금융영업" in score_data:
                categories["금융영업"] = float(score_data.get("금융영업", 0)) if score_data.get("금융영업") is not None else 0
            if "상품개발 및 운용" in score_data:
                categories["상품개발 및 운용"] = float(score_data.get("상품개발 및 운용", 0)) if score_data.get("상품개발 및 운용") is not None else 0
            if "신용분석 및 리스크관리" in score_data:
                categories["신용분석 및 리스크관리"] = float(score_data.get("신용분석 및 리스크관리", 0)) if score_data.get("신용분석 및 리스크관리") is not None else 0
            if "외환" in score_data:
                categories["외환"] = float(score_data.get("외환", 0)) if score_data.get("외환") is not None else 0
            if "은행지식 및 관련법률" in score_data:
                categories["은행지식 및 관련법률"] = float(score_data.get("은행지식 및 관련법률", 0)) if score_data.get("은행지식 및 관련법률") is not None else 0
            if "하경은행" in score_data:
                categories["하경은행"] = float(score_data.get("하경은행", 0)) if score_data.get("하경은행") is not None else 0
        else:
            return {
                "has_data": False,
                "message": "아직 시험 기록이 없습니다."
            }
        
        # 최근 퀴즈 기록 가져오기 (학습 기록과 동일한 데이터)
        quiz_logs = dashboard_data.get("quiz_logs", [])
        latest_quiz = None
        if quiz_logs:
            latest_quiz = quiz_logs[0]  # 가장 최근 퀴즈 기록
        
        # 평균 점수 계산 - 대시보드 레이더 차트와 동일하게 퀴즈 집계 통계 기반으로 계산
        latest_exam = None
        if quiz_aggregate_stats:
            # 대시보드와 동일하게 퀴즈 집계 통계의 평균 점수 사용
            valid_scores = [stats.get("score", 0) for stats in quiz_aggregate_stats.values() if stats.get("total", 0) > 0]
            if valid_scores:
                avg_score = sum(valid_scores) / len(valid_scores)
            else:
                avg_score = 0
        elif exam_scores:
            latest_exam = exam_scores[0]
            total_score = latest_exam.get("total_score", 0)
            if total_score and total_score > 0:
                avg_score = float(total_score)
            else:
                # 카테고리별 점수의 평균 계산
                valid_scores = [v for v in categories.values() if v > 0]
                avg_score = sum(valid_scores) / len(valid_scores) if valid_scores else 0
        else:
            avg_score = 0
        
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
        
        # 최근 시험 정보 생성 - 퀴즈 기록이 있으면 우선 사용 (학습 기록과 일치)
        if latest_quiz:
            # QuizGenerationLog에서 최근 퀴즈 정보 추출
            quiz_date_str = latest_quiz.get("created_at", "") or latest_quiz.get("submitted_at", "")
            quiz_score = latest_quiz.get("score", 0)
            quiz_mode = latest_quiz.get("mode", "")
            
            # 날짜 파싱 및 한국 시간으로 변환
            quiz_date_formatted = ""
            if quiz_date_str:
                try:
                    from datetime import timezone, timedelta
                    # ISO 형식 날짜 파싱
                    if 'T' in quiz_date_str:
                        quiz_date = datetime.fromisoformat(quiz_date_str.replace('Z', '+00:00'))
                    else:
                        quiz_date = datetime.strptime(quiz_date_str[:10], '%Y-%m-%d')
                    
                    # UTC를 한국 시간(KST, UTC+9)으로 변환
                    if quiz_date.tzinfo:
                        kst = timezone(timedelta(hours=9))
                        quiz_date_kst = quiz_date.astimezone(kst)
                    else:
                        # 타임존 정보가 없으면 그대로 사용 (이미 로컬 시간일 수 있음)
                        quiz_date_kst = quiz_date
                    
                    quiz_date_formatted = quiz_date_kst.strftime('%Y-%m-%d')
                except Exception as e:
                    print(f"⚠️ [날짜 파싱 오류] {str(e)}, 원본: {quiz_date_str}")
                    # 파싱 실패 시 원본에서 날짜 부분만 추출
                    quiz_date_formatted = quiz_date_str[:10] if len(quiz_date_str) >= 10 else ""
            
            # 모드명을 한글로 변환
            mode_map = {
                "random": "랜덤 세트",
                "custom": "맞춤형 세트",
                "pre": "초기 평가",
                "midterm": "중간 평가",
                "final": "최종 평가"
            }
            quiz_name = mode_map.get(quiz_mode, quiz_mode)
            
            # 점수가 없으면 카테고리 평균 사용
            if not quiz_score or quiz_score == 0:
                quiz_score = round(avg_score, 1)
            
            latest_exam_info = {
                "name": quiz_name,
                "date": quiz_date_formatted,
                "score": round(quiz_score, 1),
                "grade": ""  # 퀴즈는 등급 없음
            }
            
            # 평균 점수는 집계된 점수를 유지 (대시보드와 일치)
            # 최근 시험 점수는 참고용으로만 표시
        elif exam_scores and latest_exam:
            latest_exam_info = {
                "name": latest_exam.get("exam_name", ""),
                "date": latest_exam.get("exam_date", ""),
                "score": latest_exam.get("total_score", 0),
                "grade": latest_exam.get("grade", "")
            }
        else:
            # 데이터가 없는 경우
            latest_exam_info = {
                "name": "퀴즈 학습",
                "date": "",
                "score": round(avg_score, 1),
                "grade": ""
            }
        
        return {
            "has_data": True,
            "total_exams": len(exam_scores),
            "latest_exam": latest_exam_info,
            "categories": categories,
            "average_score": round(avg_score, 1),
            "weak_areas": weak_areas,
            "strong_areas": strong_areas,
            "relative_weak_areas": relative_weak_areas,
            "relative_strong_areas": relative_strong_areas,
            "trend": trend,
            "quiz_aggregate_stats": quiz_aggregate_stats  # 퀴즈 집계 통계 추가
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
        # exam_type enum 필드 접근을 피하기 위해 필요한 필드만 직접 조회
        statement = (
            select(
                ExamScore.id,
                ExamScore.exam_name,
                ExamScore.exam_date,
                ExamScore.score_data,
                ExamScore.total_score,
                ExamScore.grade
            )
            .where(ExamScore.mentee_id == user_id)
            .order_by(ExamScore.exam_date.desc())
        )
        exam_rows = list(self.session.exec(statement).all())
        
        if not exam_rows:
            return {
                "has_data": False,
                "message": "아직 시험 기록이 없습니다."
            }
        
        latest_exam = exam_rows[0]
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
        if len(exam_rows) >= 2:
            recent_avg = sum(json.loads(e.score_data).values() if e.score_data else [0] 
                           for e in exam_rows[:3]) / min(len(exam_rows), 3)
            old_avg = sum(json.loads(e.score_data).values() if e.score_data else [0] 
                         for e in exam_rows[-3:]) / min(len(exam_rows), 3)
            
            if recent_avg > old_avg + 5:
                trend = "improving"
            elif recent_avg < old_avg - 5:
                trend = "declining"
        
        return {
            "has_data": True,
            "total_exams": len(exam_rows),
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
        try:
            # 사용자 정보를 전달하여 날짜 파싱 시 실제 연도 찾기
            query_type = self.get_query_type(message, context_history, user)
            analysis = self.analyze_learning_progress(user)
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            print(f"❌ [학습현황 분석 오류] {str(e)}")
            print(f"상세 오류:\n{error_trace}")
            return f"죄송합니다. 학습현황을 불러오는 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.\n(오류: {str(e)})"
        
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
        elif query_type == "date_based_quiz":
            # 메시지에서 날짜 파싱 (원본 메시지 사용, 사용자 정보 전달하여 실제 연도 찾기)
            print(f"🔍 [날짜 기반 퀴즈 쿼리] 원본 메시지: '{message}', 사용자 ID: {user.id}")
            parsed_date = self._parse_date_from_message(message, user)
            print(f"🔍 [날짜 파싱 결과] 파싱된 날짜: {parsed_date} (타입: {type(parsed_date)})")
            if parsed_date is None:
                print(f"❌ [날짜 파싱 실패] 메시지에서 날짜를 추출할 수 없습니다: '{message}'")
            return self._generate_date_based_quiz_response(user, parsed_date)
        elif query_type == "date_based_exam_score":
            # 메시지에서 날짜 파싱 (원본 메시지 사용, 사용자 정보 전달하여 실제 연도 찾기)
            print(f"🔍 [날짜 기반 시험 쿼리] 원본 메시지: '{message}', 사용자 ID: {user.id}")
            parsed_date = self._parse_date_from_message(message, user)
            print(f"🔍 [날짜 파싱 결과] 파싱된 날짜: {parsed_date} (타입: {type(parsed_date)})")
            if parsed_date is None:
                print(f"❌ [날짜 파싱 실패] 메시지에서 날짜를 추출할 수 없습니다: '{message}'")
            return self._generate_date_based_exam_response(user, parsed_date)
        elif query_type == "date_based_simulation":
            # 메시지에서 상대적 날짜 파싱 (지난주, 2주전 등)
            try:
                print(f"🔍 [날짜 기반 시뮬레이션 쿼리] 원본 메시지: '{message}', 사용자 ID: {user.id}")
                date_range = self._extract_relative_date(message)
                print(f"🔍 [상대적 날짜 파싱 결과] 파싱된 날짜 범위: {date_range} (타입: {type(date_range)})")
                if date_range is None:
                    print(f"❌ [날짜 파싱 실패] 메시지에서 날짜를 추출할 수 없습니다: '{message}'")
                    return "날짜를 찾을 수 없습니다. 예: '지난주 시뮬레이션', '2주전 시뮬레이션 결과'"
                return self._generate_date_based_simulation_response(user, date_range)
            except Exception as e:
                import traceback
                error_trace = traceback.format_exc()
                print(f"❌ [날짜 기반 시뮬레이션 응답 생성 오류] {str(e)}")
                print(f"상세 오류:\n{error_trace}")
                return f"죄송합니다. 시뮬레이션 결과를 불러오는 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.\n(오류: {str(e)})"
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
        """성적 상세 응답 (대시보드 퀴즈 점수 연동)"""
        exam = analysis["exam"]
        
        if not exam.get("has_data"):
            return "아직 시험 기록이 없습니다. 첫 시험을 응시해보세요! 📝"
        
        # 퀴즈 집계 통계가 있으면 함께 표시
        quiz_aggregate_stats = exam.get("quiz_aggregate_stats", {})
        
        response = f"""📊 **{user.name}님의 성적 분석**

📝 **최근 시험**
- 시험명: {exam['latest_exam']['name']}
"""
        
        if exam['latest_exam']['date']:
            response += f"- 날짜: {exam['latest_exam']['date'][:10]}\n"
        
        response += f"- 총점: {exam['latest_exam']['score']}점\n"
        
        if exam['latest_exam']['grade']:
            response += f"- 등급: {exam['latest_exam']['grade']}\n"
        
        response += "\n📈 **영역별 점수**\n\n"
        
        # 대시보드와 동일한 카테고리 순서 유지
        category_order = [
            '금융영업',
            '상품개발 및 운용',
            '신용분석 및 리스크관리',
            '외환',
            '은행지식 및 관련법률',
            '하경은행',
        ]
        
        # 마크다운 표 형식으로 영역별 점수 표시 (대시보드 형식)
        response += "| 영역 | 점수 | 정확도 | 상태 |\n"
        response += "|------|------|--------|------|\n"
        
        for category in category_order:
            score = exam['categories'].get(category, 0)
            stats = quiz_aggregate_stats.get(category, {}) if quiz_aggregate_stats else {}
            correct = stats.get("correct", 0)
            total = stats.get("total", 0)
            
            # 상태 이모지
            if score >= 80:
                status = "🌟 우수"
            elif score < 60:
                status = "⚠️ 개선 필요"
            else:
                status = "📌 양호"
            
            if total > 0:
                accuracy = round((correct / total) * 100, 1)
                # 대시보드와 동일한 형식: 정답/전체 문제 수를 강조
                response += f"| {category} | **{correct}/{total}** | {accuracy}% | {status} |\n"
            else:
                # 시험 점수만 있는 경우
                if score > 0:
                    response += f"| {category} | {score}점 | - | {status} |\n"
                else:
                    response += f"| {category} | - | - | - |\n"
        
        response += "\n"
        
        response += f"""
**평균 점수**: {exam['average_score']}점
**추세**: {self._get_trend_emoji(exam['trend'])} {exam['trend']}
"""
        
        # 퀴즈 통계 요약 정보 추가
        if quiz_aggregate_stats:
            total_questions = sum(stats.get("total", 0) for stats in quiz_aggregate_stats.values())
            total_correct = sum(stats.get("correct", 0) for stats in quiz_aggregate_stats.values())
            if total_questions > 0:
                overall_accuracy = (total_correct / total_questions) * 100
                response += f"\n📚 **퀴즈 학습 통계**\n"
                response += f"- 총 문제 수: {total_questions}문제\n"
                response += f"- 정답 수: {total_correct}문제\n"
                response += f"- 전체 정답률: {overall_accuracy:.1f}%\n"
        
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
    
    def _get_quiz_logs_by_date(self, user: User, target_date: date) -> List[Dict]:
        """특정 날짜의 퀴즈 기록 조회 (한국 시간 기준)"""
        from app.models import QuizGenerationLog
        
        # 디버깅: 조회할 날짜 확인
        print(f"🔍 [퀴즈 기록 조회] 사용자 ID: {user.id}, 조회 날짜: {target_date} (KST 기준)")
        
        # 한국 시간 기준 시작/끝 시간
        kst_start = datetime.combine(target_date, datetime.min.time()).replace(tzinfo=KST)
        kst_end = datetime.combine(target_date, datetime.max.time()).replace(tzinfo=KST)
        
        # 한국 시간을 UTC로 변환 (데이터베이스는 UTC로 저장됨)
        utc_start = kst_start.astimezone(timezone.utc).replace(tzinfo=None)
        utc_end = kst_end.astimezone(timezone.utc).replace(tzinfo=None)
        
        # 하루 전후 범위도 포함 (타임존 경계 문제 방지)
        utc_start = utc_start - timedelta(hours=9)  # 하루 전 15:00 (UTC)
        utc_end = utc_end + timedelta(hours=15)  # 하루 후 15:00 (UTC)
        
        print(f"🔍 [퀴즈 기록 조회] 한국 시간 범위: {kst_start} ~ {kst_end} (KST)")
        print(f"🔍 [퀴즈 기록 조회] UTC 범위: {utc_start} ~ {utc_end} (UTC)")
        
        # 날짜 범위로 조회 (UTC 기준)
        quiz_logs_statement = (
            select(QuizGenerationLog)
            .where(
                QuizGenerationLog.user_id == user.id,
                QuizGenerationLog.answers.is_not(None),
                QuizGenerationLog.created_at >= utc_start,
                QuizGenerationLog.created_at <= utc_end
            )
            .order_by(QuizGenerationLog.created_at.desc())
        )
        quiz_logs = list(self.session.exec(quiz_logs_statement).all())
        
        # 한국 시간으로 변환하여 날짜 필터링 (정확한 날짜 매칭)
        filtered_logs = []
        for log in quiz_logs:
            kst_date = self._get_kst_date(log.created_at)
            if kst_date == target_date:
                filtered_logs.append(log)
        
        quiz_logs = filtered_logs
        
        # 디버깅: 조회된 모든 퀴즈 기록의 날짜 확인
        print(f"🔍 [퀴즈 기록 조회] 조회된 퀴즈 기록 수: {len(quiz_logs)}")
        if quiz_logs:
            for i, log in enumerate(quiz_logs[:5], 1):  # 최대 5개만 출력
                log_date = log.created_at.date()
                print(f"🔍 [퀴즈 기록 {i}] ID: {log.id}, 날짜: {log_date}, created_at: {log.created_at}")
        else:
            # 조회 결과가 없을 때, 사용자의 최근 퀴즈 기록 몇 개 확인
            all_logs_statement = (
                select(QuizGenerationLog)
                .where(
                    QuizGenerationLog.user_id == user.id,
                    QuizGenerationLog.answers.is_not(None)
                )
                .order_by(QuizGenerationLog.created_at.desc())
                .limit(5)
            )
            recent_logs = list(self.session.exec(all_logs_statement).all())
            print(f"🔍 [퀴즈 기록 조회] 최근 퀴즈 기록 {len(recent_logs)}개 확인:")
            for i, log in enumerate(recent_logs, 1):
                log_date = log.created_at.date()
                print(f"🔍 [최근 기록 {i}] 날짜: {log_date}, created_at: {log.created_at}")
        
        result = []
        for log in quiz_logs:
            answers = log.answers or {}
            questions = log.questions or []
            total_questions = len(questions)
            correct_count = 0
            
            for q in questions:
                qid = q.get("q_id") or q.get("qid") or q.get("question_id")
                if qid is None:
                    continue
                
                key = str(qid)
                user_answer = answers.get(key) or answers.get(int(key)) if isinstance(answers, dict) else None
                correct_answer = q.get("answer") or q.get("correct_answer")
                
                def normalize_answer(ans):
                    if ans is None:
                        return ""
                    return str(ans).strip().upper()
                
                if normalize_answer(user_answer) == normalize_answer(correct_answer):
                    correct_count += 1
            
            score = (correct_count / total_questions * 100) if total_questions > 0 else 0
            
            result.append({
                "id": log.id,
                "created_at": log.created_at.isoformat(),
                "mode": log.mode,
                "total_questions": total_questions,
                "correct_count": correct_count,
                "score": round(score, 1)
            })
        
        return result
    
    def _get_exam_scores_by_date(self, user: User, target_date: date) -> List[Dict]:
        """특정 날짜의 시험 점수 조회"""
        # 날짜 범위로 조회 (더 안전한 방법)
        start_datetime = datetime.combine(target_date, datetime.min.time())
        end_datetime = datetime.combine(target_date, datetime.max.time())
        
        exam_statement = (
            select(
                ExamScore.id,
                ExamScore.exam_name,
                ExamScore.exam_date,
                ExamScore.score_data,
                ExamScore.total_score,
                ExamScore.grade,
                ExamScore.feedback
            )
            .where(
                ExamScore.mentee_id == user.id,
                ExamScore.exam_date >= start_datetime,
                ExamScore.exam_date <= end_datetime
            )
            .order_by(ExamScore.exam_date.desc())
        )
        exam_rows = self.session.exec(exam_statement).all()
        
        result = []
        for exam_row in exam_rows:
            result.append({
                "id": exam_row.id,
                "exam_name": exam_row.exam_name,
                "exam_date": exam_row.exam_date.isoformat(),
                "score_data": json.loads(exam_row.score_data) if exam_row.score_data else {},
                "total_score": exam_row.total_score,
                "grade": exam_row.grade,
                "feedback": exam_row.feedback
            })
        
        return result
    
    def _generate_date_based_quiz_response(self, user: User, target_date: Optional[date]) -> str:
        """특정 날짜의 퀴즈 기록 응답 생성"""
        if target_date is None:
            return "날짜를 찾을 수 없습니다. 예: '12월 2일 학습현황', '11월 25일 퀴즈 기록'"
        
        # 디버깅: 날짜 확인
        print(f"🔍 [날짜 기반 조회] 사용자: {user.id}, 조회 날짜: {target_date}")
        
        quiz_logs = self._get_quiz_logs_by_date(user, target_date)
        
        # 디버깅: 조회 결과 확인
        print(f"🔍 [날짜 기반 조회] 조회된 퀴즈 기록 수: {len(quiz_logs)}")
        
        if not quiz_logs:
            date_str = target_date.strftime("%Y년 %m월 %d일")
            return f"📅 {date_str}에는 퀴즈 기록이 없습니다."
        
        date_str = target_date.strftime("%Y년 %m월 %d일")
        response = f"📅 **{date_str} 학습 기록**\n\n"
        
        for i, log in enumerate(quiz_logs, 1):
            mode_label = {
                "random": "랜덤 세트",
                "custom": "맞춤형 세트",
                "pre": "초기 평가",
                "midterm": "중간 평가",
                "final": "최종 평가"
            }.get(log["mode"], log["mode"])
            
            created_at = datetime.fromisoformat(log["created_at"])
            time_str = created_at.strftime("%Y-%m-%d %H:%M")
            
            response += f"**{i}. {mode_label}** ({time_str})\n"
            response += f"- 점수: {log['score']}점\n"
            response += f"- 정답률: {log['correct_count']}/{log['total_questions']}\n\n"
        
        return response
    
    def _generate_date_based_exam_response(self, user: User, target_date: Optional[date]) -> str:
        """특정 날짜의 시험 점수 응답 생성"""
        if target_date is None:
            return "날짜를 찾을 수 없습니다. 예: '12월 2일 시험 점수', '11월 25일 시험성적'"
        
        exam_scores = self._get_exam_scores_by_date(user, target_date)
        
        if not exam_scores:
            date_str = target_date.strftime("%Y년 %m월 %d일")
            return f"📅 {date_str}에는 시험 기록이 없습니다."
        
        date_str = target_date.strftime("%Y년 %m월 %d일")
        response = f"📅 **{date_str} 시험 점수**\n\n"
        
        for i, exam in enumerate(exam_scores, 1):
            response += f"**{i}. {exam['exam_name']}**\n"
            response += f"- 총점: {exam['total_score']}점\n"
            if exam.get('grade'):
                response += f"- 등급: {exam['grade']}\n"
            response += "\n"
            
            # 영역별 점수 표시
            score_data = exam.get('score_data', {})
            if score_data:
                response += "**영역별 점수**\n"
                for category, score in score_data.items():
                    response += f"- {category}: {score}점\n"
                response += "\n"
        
        return response

