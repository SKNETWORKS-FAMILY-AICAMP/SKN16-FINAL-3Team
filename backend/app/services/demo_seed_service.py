"""
데모 시드 데이터 로드 및 4기 생성 서비스

1~3기 시드 JSON 로드 + 4기 동적 생성 + 매칭 실행
"""

import json
import random
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from collections import defaultdict

from sqlalchemy import delete
from sqlmodel import Session, select

from app.models.matching import MatchingReport, MatchingResult
from app.models.mentor import (
    ChatHistory,
    ExamScore,
    ExamResult,
    ExamType,
    Feedback,
    LearningTopic,
    MentorMenteeRelation,
    SimulationRecording,
)
from app.models.post import Comment, Post
from app.models.quiz import QuizGenerationLog
from app.models.training_center import TrainingCenterRecord
from app.models.user import User
from app.models.rag_simulation import (
    RAGSimulationEvaluation,
    RAGSimulationSession,
    RAGSimulationTurn,
)
from app.models.schedule import Schedule
from app.models.simulation import SimulationAttempt, SimulationProgress, SimulationStep
from app.models.simulation_feedback import SimulationFeedback

# 페르소나 정보 옵션
PERSONA_AGE_GROUPS = ["20대", "30대", "40대", "50대", "60대 이상"]
PERSONA_GENDERS = ["남성", "여성"]
PERSONA_OCCUPATIONS = ["학생", "직장인", "자영업자", "은퇴자", "무직"]
PERSONA_CUSTOMER_STYLES = ["실용형", "보수형", "불만형", "긍정형", "급함형"]
SITUATION_CATEGORIES = ["수신", "여신", "카드", "외환", "인터넷뱅킹", "민원처리"]
from app.models.advanced_simulation import (
    SimulationAnalytics,
    VoiceInteraction,
    VoiceSimulationSession,
)
from app.models.training_center import TrainingCenterRecord, TrainingCohort
from app.models.user import User, UserRole
from app.utils.auth import get_password_hash


# 시드 데이터 디렉토리
SEED_DATA_DIR = Path(__file__).parent.parent.parent / "data" / "seed"

# 4기 설정
COHORT_4_DATE = date(2025, 12, 1)
COHORT_4_MENTEES = 30
COHORT_4_MENTORS = 15

# 연수원 섹션 점수 카테고리 (TrainingCenterService.CATEGORY_KEYS와 동일하게 유지)
TRAINING_SECTION_KEYS = [
    "금융영업",
    "상품개발 및 운용",
    "신용분석 및 리스크관리",
    "외환",
    "은행지식 및 관련법률",
    "하경은행",
]

# 이름 생성용 데이터
LAST_NAMES = ["김", "이", "박", "정", "최", "조", "윤", "장", "임", "한", "오", "서", "신", "권", "황", "안", "송", "유", "홍", "양"]
MALE_FIRST_LEADING = ["민", "서", "도", "하", "지", "유", "준", "시", "태", "수", "건", "현", "연", "재", "가", "동", "성", "영", "호", "우"]
MALE_FIRST_TRAILING = ["현", "우", "윤", "진", "환", "혁", "훈", "열", "형", "람", "석", "준", "호", "성", "민", "재", "영", "수", "태", "원"]
FEMALE_FIRST_LEADING = ["민", "서", "하", "지", "아", "유", "예", "다", "채", "주", "현", "연", "수", "가", "은", "혜", "지", "서", "예", "나"]
FEMALE_FIRST_TRAILING = ["림", "은", "율", "빈", "영", "정", "미", "솔", "나", "람", "아", "연", "희", "진", "수", "영", "미", "은", "혜", "지"]

MBTI_OPTIONS = ["INTJ", "INTP", "ENTJ", "ENTP", "INFJ", "INFP", "ENFJ", "ENFP", "ISTJ", "ISFJ", "ESTJ", "ESFJ", "ISTP", "ISFP", "ESTP", "ESFP"]
MBTI_WEIGHTS = [0.04, 0.04, 0.05, 0.04, 0.05, 0.05, 0.06, 0.06, 0.09, 0.13, 0.08, 0.10, 0.04, 0.05, 0.05, 0.05]

CITY_OPTIONS = ["서울특별시", "부산광역시", "인천광역시", "대구광역시", "대전광역시", "광주광역시", "울산광역시", "세종특별자치시", "고양시", "성남시", "용인시", "수원시", "청주시", "전주시", "창원시", "천안시"]
CITY_WEIGHTS = [0.25, 0.10, 0.08, 0.05, 0.05, 0.05, 0.05, 0.03, 0.06, 0.06, 0.06, 0.05, 0.04, 0.03, 0.03, 0.03]

HOBBY_OPTIONS = ["스포츠", "영화감상", "독서", "요리", "러닝", "사진", "게임", "음악", "여행", "원예"]

MAJOR_OPTIONS = ["경제학", "경영학", "회계학", "금융학", "통계학", "수학", "컴퓨터공학", "산업공학", "법학", "행정학", "국제통상", "영어영문학", "중어중문학", "심리학", "사회학"]
MAJOR_WEIGHTS = [0.18, 0.20, 0.12, 0.10, 0.05, 0.04, 0.08, 0.04, 0.05, 0.04, 0.03, 0.03, 0.02, 0.02, 0.02]

CAREER_GOALS = ["VIP자산관리전문가", "기업금융전문가", "여신심사전문가", "디지털금융전문가", "외환딜러", "PB(프라이빗뱅커)", "지점장", "본부전문직", "리스크관리전문가", "금융상품개발자"]

BRANCH_TEAMS = ["창구영업1팀", "창구영업2팀", "VIP창구팀", "외환창구팀", "디지털창구팀", "기업창구팀"]
TEAM_WEIGHTS = [0.3, 0.3, 0.1, 0.1, 0.1, 0.1]

EXAM_CATEGORIES = ["은행업무", "상품개발 및 운용", "신용분석 및 리스크관리", "외환", "은행지식 및 관련법률", "하경은행"]

PERSONA_IDS = ["persona_001", "persona_002", "persona_003", "persona_004", "persona_005"]
SCENARIO_IDS = ["scenario_001", "scenario_002", "scenario_003", "scenario_004", "scenario_005"]


class DemoSeedService:
    """데모 시드 데이터 로드 및 초기화 서비스"""

    def __init__(self, session: Session):
        self.session = session

    def initialize_demo_data(self) -> Dict[str, Any]:
        """
        데모 데이터 초기화
        1. 1~3기 시드 데이터 확인 및 로드 (이미 있으면 스킵)
        2. 4기 데이터만 삭제 및 재생성
        3. 매칭 실행 (각 기수별 독립적인 멘토 할당)
        """
        result = {
            "message": "",
            "cohorts_loaded": [],
            "cohort_4_generated": False,
            "matching_completed": False,
            "stats": {},
        }

        try:
            # 전역 중복 체크용 집합 초기화
            self._seen_employee_numbers = set()
            self._seen_user_emails = set()
            
            # 1. 1~3기 시드 데이터 확인 및 로드 (보완 로직 포함)
            for cohort_num in range(1, 4):
                existing_cohort = self.session.exec(
                    select(TrainingCohort).where(TrainingCohort.cohort_index == cohort_num)
                ).first()
                existing_records = []
                if existing_cohort:
                    existing_records = self.session.exec(
                        select(TrainingCenterRecord).where(
                            TrainingCenterRecord.cohort_id == existing_cohort.id
                        )
                    ).all()
                
                if existing_cohort:
                    # 이미 존재하는 경우, 멘토 수 확인
                    mentor_records = [r for r in existing_records if r.employee_type == "mentor"]
                    mentor_count = len(mentor_records)
                    total_records = len(existing_records)

                    # 만약 기존 기수는 있으나 데이터가 거의 없는 경우(예: 전체 삭제 후 남은 cohort 레코드만 존재),
                    # 시드를 다시 로드해서 1~3기 완주 데이터를 재생성한다.
                    if total_records == 0:
                        stats = self._load_cohort_seed(cohort_num)
                        result["cohorts_loaded"].append({
                            "cohort": cohort_num,
                            "stats": stats,
                        })
                        # 새로 로드했으므로 다음 기수로 진행
                        self.session.commit()
                        continue
                    
                    # 멘토 수가 15명 미만이면 부족한 멘토만 추가 생성
                    if mentor_count < 15:
                        needed_mentors = 15 - mentor_count
                        result["cohorts_loaded"].append({
                            "cohort": cohort_num,
                            "stats": {
                                "users": 0,
                                "training_records": 0,
                                "skipped": False,
                                "message": f"{cohort_num}기 멘토 수가 부족합니다 ({mentor_count}명/15명). {needed_mentors}명 추가 생성합니다.",
                            },
                        })
                        # 부족한 멘토만 추가 생성
                        self._add_missing_mentors_to_cohort(existing_cohort, needed_mentors)
                        stats = {
                            "users": needed_mentors,
                            "training_records": needed_mentors,
                            "skipped": False,
                        }
                        result["cohorts_loaded"][-1]["stats"] = stats
                    else:
                        # 멘토 수가 충분하면 스킵
                        existing_records = self.session.exec(
                            select(TrainingCenterRecord).where(
                                TrainingCenterRecord.cohort_id == existing_cohort.id
                            )
                        ).all()
                        result["cohorts_loaded"].append({
                            "cohort": cohort_num,
                            "stats": {
                                "users": 0,
                                "training_records": len(existing_records),
                                "skipped": True,
                                "message": f"{cohort_num}기 데이터가 이미 존재하며 멘토 수가 충분합니다 ({mentor_count}명). 스킵했습니다.",
                            },
                        })
                        # 기존 데이터의 employee_number와 email을 집합에 추가
                        for record in existing_records:
                            if record.employee_number:
                                self._seen_employee_numbers.add(record.employee_number)
                            if record.email:
                                self._seen_user_emails.add(record.email)
                else:
                    # 존재하지 않는 경우, 시드 데이터 로드
                    stats = self._load_cohort_seed(cohort_num)
                    result["cohorts_loaded"].append({
                        "cohort": cohort_num,
                        "stats": stats,
                    })
                
                # 각 cohort 로드 후 commit하여 확실히 저장
                self.session.commit()
            
            # 2. 4기 데이터만 삭제 및 재생성
            self._delete_cohort_4_data()
            
            # 3. 4기 데이터 동적 생성
            cohort_4_stats = self._generate_cohort_4()
            result["cohort_4_generated"] = True
            result["stats"]["cohort_4"] = cohort_4_stats
            
            # 4. 매칭 실행 (각 기수별 독립적인 멘토 할당)
            matching_stats = self._run_matching_all_cohorts()
            result["matching_completed"] = True
            result["stats"]["matching"] = matching_stats
            
            self.session.commit()
            
            result["message"] = "데모 데이터 초기화 완료 (1-3기는 멘토 수 확인 후 유지/재생성, 4기는 재생성)"
            return result
            
        except Exception as exc:
            self.session.rollback()
            raise exc

    def _delete_all_data(self) -> None:
        """모든 관련 데이터 삭제 (사용하지 않음 - 1-3기 유지를 위해)"""
        # 이 메서드는 더 이상 사용하지 않지만 호환성을 위해 유지
        pass
    
    def _delete_cohort_data(self, cohort_num: int) -> None:
        """특정 기수(cohort_num)의 데이터만 삭제"""
        cohort = self.session.exec(
            select(TrainingCohort).where(TrainingCohort.cohort_index == cohort_num)
        ).first()
        
        if not cohort:
            return
        
        # 멘티들의 User ID 수집
        mentee_records = self.session.exec(
            select(TrainingCenterRecord).where(
                TrainingCenterRecord.cohort_id == cohort.id,
                TrainingCenterRecord.employee_type == "mentee"
            )
        ).all()
        mentee_user_ids = set()
        for record in mentee_records:
            user = self.session.exec(
                select(User).where(User.employee_number == record.employee_number)
            ).first()
            if user:
                mentee_user_ids.add(user.id)
        
        # 멘토들의 User ID 수집
        mentor_records = self.session.exec(
            select(TrainingCenterRecord).where(
                TrainingCenterRecord.cohort_id == cohort.id,
                TrainingCenterRecord.employee_type == "mentor"
            )
        ).all()
        mentor_user_ids = set()
        for record in mentor_records:
            user = self.session.exec(
                select(User).where(User.employee_number == record.employee_number)
            ).first()
            if user:
                mentor_user_ids.add(user.id)
        
        all_cohort_user_ids = mentee_user_ids | mentor_user_ids
        
        # FK 순서 고려하여 삭제
        if all_cohort_user_ids:
            # 시뮬레이션 관련
            self.session.exec(
                delete(RAGSimulationEvaluation).where(
                    RAGSimulationEvaluation.user_id.in_(all_cohort_user_ids)
                )
            )
            sim_sessions = self.session.exec(
                select(RAGSimulationSession).where(
                    RAGSimulationSession.user_id.in_(all_cohort_user_ids)
                )
            ).all()
            sim_session_ids = [s.id for s in sim_sessions]
            if sim_session_ids:
                self.session.exec(
                    delete(RAGSimulationTurn).where(
                        RAGSimulationTurn.session_id.in_(sim_session_ids)
                    )
                )
            self.session.exec(
                delete(RAGSimulationSession).where(
                    RAGSimulationSession.user_id.in_(all_cohort_user_ids)
                )
            )
            
            # 기타 시뮬레이션 관련
            # VoiceSimulationSession 먼저 조회
            voice_sessions = self.session.exec(
                select(VoiceSimulationSession).where(
                    VoiceSimulationSession.user_id.in_(all_cohort_user_ids)
                )
            ).all()
            voice_session_ids = [s.id for s in voice_sessions]
            
            # VoiceInteraction은 session_id를 통해 삭제
            if voice_session_ids:
                self.session.exec(
                    delete(VoiceInteraction).where(
                        VoiceInteraction.session_id.in_(voice_session_ids)
                    )
                )
            
            # VoiceSimulationSession 삭제
            if all_cohort_user_ids:
                self.session.exec(
                    delete(VoiceSimulationSession).where(
                        VoiceSimulationSession.user_id.in_(all_cohort_user_ids)
                    )
                )
            self.session.exec(
                delete(SimulationAnalytics).where(
                    SimulationAnalytics.user_id.in_(all_cohort_user_ids)
                )
            )
            # SimulationAttempt 먼저 조회
            attempts = self.session.exec(
                select(SimulationAttempt).where(
                    SimulationAttempt.user_id.in_(all_cohort_user_ids)
                )
            ).all()
            attempt_ids = [a.id for a in attempts]
            
            # SimulationStep은 attempt_id를 통해 삭제
            if attempt_ids:
                self.session.exec(
                    delete(SimulationStep).where(
                        SimulationStep.attempt_id.in_(attempt_ids)
                    )
                )
            
            # SimulationAttempt 삭제
            if all_cohort_user_ids:
                self.session.exec(
                    delete(SimulationAttempt).where(
                        SimulationAttempt.user_id.in_(all_cohort_user_ids)
                    )
                )
            self.session.exec(
                delete(SimulationProgress).where(
                    SimulationProgress.user_id.in_(all_cohort_user_ids)
                )
            )
            self.session.exec(
                delete(SimulationFeedback).where(
                    SimulationFeedback.user_id.in_(all_cohort_user_ids)
                )
            )
            # SimulationRecording은 mentee_id만 있음
            self.session.exec(
                delete(SimulationRecording).where(
                    SimulationRecording.mentee_id.in_(mentee_user_ids)
                )
            )
            
            # 퀴즈 관련
            self.session.exec(
                delete(QuizGenerationLog).where(
                    QuizGenerationLog.user_id.in_(all_cohort_user_ids)
                )
            )
            
            # 멘토/멘티 관련
            self.session.exec(
                delete(Feedback).where(
                    Feedback.mentee_id.in_(mentee_user_ids) | 
                    Feedback.mentor_id.in_(mentor_user_ids)
                )
            )
            self.session.exec(
                delete(ExamResult).where(
                    ExamResult.mentee_id.in_(all_cohort_4_user_ids)
                )
            )
            # 일부 멘토 계정에도 시험 점수가 있을 수 있으므로 mentor/mentee 구분 없이 일괄 삭제
            self.session.exec(
                delete(ExamScore).where(
                    ExamScore.mentee_id.in_(all_cohort_4_user_ids)
                )
            )
            self.session.exec(
                delete(LearningTopic).where(
                    LearningTopic.mentee_id.in_(mentee_user_ids)
                )
            )
            # ChatHistory는 user_id만 있음
            self.session.exec(
                delete(ChatHistory).where(
                    ChatHistory.user_id.in_(all_cohort_user_ids)
                )
            )
            
            # FK 제약 조건을 피하기 위해 중간 flush
            self.session.flush()
        
        # MentorMenteeRelation 삭제 (해당 기수의 멘토/멘티와 관련된 모든 관계)
        if all_cohort_user_ids:
            self.session.exec(
                delete(MentorMenteeRelation).where(
                    MentorMenteeRelation.mentor_id.in_(all_cohort_user_ids) |
                    MentorMenteeRelation.mentee_id.in_(all_cohort_user_ids)
                )
            )
            self.session.flush()
        
        # MatchingResult 삭제 (TrainingCenterRecord를 참조하므로 먼저 삭제)
        # 해당 기수의 모든 TrainingCenterRecord ID 수집
        all_record_ids = []
        all_records = self.session.exec(
            select(TrainingCenterRecord).where(
                TrainingCenterRecord.cohort_id == cohort.id
            )
        ).all()
        all_record_ids = [r.id for r in all_records]
        
        if all_record_ids:
            # mentee_id나 mentor_id가 해당 기수의 record ID인 모든 MatchingResult 삭제
            self.session.exec(
                delete(MatchingResult).where(
                    MatchingResult.mentee_id.in_(all_record_ids) |
                    MatchingResult.mentor_id.in_(all_record_ids)
                )
            )
        
        # TrainingCenterRecord 삭제
        self.session.exec(
            delete(TrainingCenterRecord).where(
                TrainingCenterRecord.cohort_id == cohort.id
            )
        )
        self.session.flush()
        
        # User 삭제
        if all_cohort_user_ids:
            self.session.exec(
                delete(User).where(User.id.in_(all_cohort_user_ids))
            )
        
        # TrainingCohort 삭제
        self.session.exec(delete(TrainingCohort).where(TrainingCohort.id == cohort.id))
        
        self.session.commit()
    
    def _delete_cohort_4_data(self) -> None:
        """4기 관련 데이터만 삭제"""
        # 4기 cohort 조회
        cohort_4 = self.session.exec(
            select(TrainingCohort).where(TrainingCohort.cohort_index == 4)
        ).first()
        
        if not cohort_4:
            return
        
        # 4기 멘티들의 User ID 수집
        mentee_records = self.session.exec(
            select(TrainingCenterRecord).where(
                TrainingCenterRecord.cohort_id == cohort_4.id,
                TrainingCenterRecord.employee_type == "mentee"
            )
        ).all()
        mentee_user_ids = set()
        for record in mentee_records:
            user = self.session.exec(
                select(User).where(User.employee_number == record.employee_number)
            ).first()
            if user:
                mentee_user_ids.add(user.id)
        
        # 4기 멘토들의 User ID 수집
        mentor_records = self.session.exec(
            select(TrainingCenterRecord).where(
                TrainingCenterRecord.cohort_id == cohort_4.id,
                TrainingCenterRecord.employee_type == "mentor"
            )
        ).all()
        mentor_user_ids = set()
        for record in mentor_records:
            user = self.session.exec(
                select(User).where(User.employee_number == record.employee_number)
            ).first()
            if user:
                mentor_user_ids.add(user.id)
        
        # TrainingCenterRecord가 삭제된 경우를 대비하여 cohort_label로도 사용자 수집
        orphan_users = self.session.exec(
            select(User).where(
                User.role != UserRole.ADMIN,
                User.cohort_label.contains("4기")
            )
        ).all()
        orphan_user_ids = {user.id for user in orphan_users}

        all_cohort_4_user_ids = mentee_user_ids | mentor_user_ids | orphan_user_ids
        
        # FK 순서 고려하여 삭제 (4기 관련만)
        if all_cohort_4_user_ids:
            # 시뮬레이션 관련 (4기 사용자만)
            self.session.exec(
                delete(RAGSimulationEvaluation).where(
                    RAGSimulationEvaluation.user_id.in_(all_cohort_4_user_ids)
                )
            )
            sim_sessions = self.session.exec(
                select(RAGSimulationSession).where(
                    RAGSimulationSession.user_id.in_(all_cohort_4_user_ids)
                )
            ).all()
            sim_session_ids = [s.id for s in sim_sessions]
            if sim_session_ids:
                self.session.exec(
                    delete(RAGSimulationTurn).where(
                        RAGSimulationTurn.session_id.in_(sim_session_ids)
                    )
                )
            self.session.exec(
                delete(RAGSimulationSession).where(
                    RAGSimulationSession.user_id.in_(all_cohort_4_user_ids)
                )
            )
            
            # 기타 시뮬레이션 관련
            # VoiceSimulationSession 먼저 조회
            voice_sessions = self.session.exec(
                select(VoiceSimulationSession).where(
                    VoiceSimulationSession.user_id.in_(all_cohort_4_user_ids)
                )
            ).all()
            voice_session_ids = [s.id for s in voice_sessions]
            
            # VoiceInteraction은 session_id를 통해 삭제
            if voice_session_ids:
                self.session.exec(
                    delete(VoiceInteraction).where(
                        VoiceInteraction.session_id.in_(voice_session_ids)
                    )
                )
            
            # VoiceSimulationSession 삭제
            if all_cohort_4_user_ids:
                self.session.exec(
                    delete(VoiceSimulationSession).where(
                        VoiceSimulationSession.user_id.in_(all_cohort_4_user_ids)
                    )
                )
            self.session.exec(
                delete(SimulationAnalytics).where(
                    SimulationAnalytics.user_id.in_(all_cohort_4_user_ids)
                )
            )
            # SimulationAttempt 먼저 조회
            attempts = self.session.exec(
                select(SimulationAttempt).where(
                    SimulationAttempt.user_id.in_(all_cohort_4_user_ids)
                )
            ).all()
            attempt_ids = [a.id for a in attempts]
            
            # SimulationStep은 attempt_id를 통해 삭제
            if attempt_ids:
                self.session.exec(
                    delete(SimulationStep).where(
                        SimulationStep.attempt_id.in_(attempt_ids)
                    )
                )
            
            # SimulationAttempt 삭제
            if all_cohort_4_user_ids:
                self.session.exec(
                    delete(SimulationAttempt).where(
                        SimulationAttempt.user_id.in_(all_cohort_4_user_ids)
                    )
                )
            self.session.exec(
                delete(SimulationProgress).where(
                    SimulationProgress.user_id.in_(all_cohort_4_user_ids)
                )
            )
            self.session.exec(
                delete(SimulationFeedback).where(
                    SimulationFeedback.user_id.in_(all_cohort_4_user_ids)
                )
            )
            # SimulationRecording은 mentee_id만 있음
            self.session.exec(
                delete(SimulationRecording).where(
                    SimulationRecording.mentee_id.in_(mentee_user_ids)
                )
            )
            
            # 퀴즈 관련
            self.session.exec(
                delete(QuizGenerationLog).where(
                    QuizGenerationLog.user_id.in_(all_cohort_4_user_ids)
                )
            )
            
            # 멘토/멘티 관련 (4기 관계만)
            self.session.exec(
                delete(Feedback).where(
                    Feedback.mentee_id.in_(mentee_user_ids) | 
                    Feedback.mentor_id.in_(mentor_user_ids)
                )
            )
            self.session.exec(
                delete(ExamResult).where(
                    ExamResult.mentee_id.in_(mentee_user_ids)
                )
            )
            self.session.exec(
                delete(ExamScore).where(
                    ExamScore.mentee_id.in_(mentee_user_ids)
                )
            )
            self.session.exec(
                delete(LearningTopic).where(
                    LearningTopic.mentee_id.in_(mentee_user_ids)
                )
            )
            # ChatHistory는 user_id만 있음
            self.session.exec(
                delete(ChatHistory).where(
                    ChatHistory.user_id.in_(all_cohort_4_user_ids)
                )
            )
            
            # FK 제약 조건을 피하기 위해 중간 commit
            self.session.flush()
        
        # 4기 MentorMenteeRelation 삭제 (4기의 멘토/멘티와 관련된 모든 관계)
        if all_cohort_4_user_ids:
            self.session.exec(
                delete(MentorMenteeRelation).where(
                    MentorMenteeRelation.mentor_id.in_(all_cohort_4_user_ids) |
                    MentorMenteeRelation.mentee_id.in_(all_cohort_4_user_ids)
                )
            )
            self.session.flush()
        
        # 4기 MatchingResult 삭제 (TrainingCenterRecord를 참조하므로 먼저 삭제)
        # 해당 기수의 모든 TrainingCenterRecord ID 수집
        all_cohort_4_record_ids = []
        all_cohort_4_records = self.session.exec(
            select(TrainingCenterRecord).where(
                TrainingCenterRecord.cohort_id == cohort_4.id
            )
        ).all()
        all_cohort_4_record_ids = [r.id for r in all_cohort_4_records]
        
        if all_cohort_4_record_ids:
            # mentee_id나 mentor_id가 해당 기수의 record ID인 모든 MatchingResult 삭제
            self.session.exec(
                delete(MatchingResult).where(
                    MatchingResult.mentee_id.in_(all_cohort_4_record_ids) |
                    MatchingResult.mentor_id.in_(all_cohort_4_record_ids)
                )
            )
        
        # 4기 TrainingCenterRecord 삭제
        self.session.exec(
            delete(TrainingCenterRecord).where(
                TrainingCenterRecord.cohort_id == cohort_4.id
            )
        )
        self.session.flush()
        
        # 4기 User 삭제
        if all_cohort_4_user_ids:
            self.session.exec(
                delete(User).where(User.id.in_(all_cohort_4_user_ids))
            )
        
        # 4기 TrainingCohort 삭제
        self.session.exec(delete(TrainingCohort).where(TrainingCohort.id == cohort_4.id))
        
        self.session.commit()

    def _load_cohort_seed(self, cohort_num: int) -> Dict[str, int]:
        """시드 JSON에서 기수 데이터 로드"""
        seed_file = SEED_DATA_DIR / f"cohort_{cohort_num}_2025.json"
        
        if not seed_file.exists():
            raise FileNotFoundError(f"시드 파일을 찾을 수 없습니다: {seed_file}")
        
        with open(seed_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        stats = {
            "users": 0,
            "training_records": 0,
            "exam_scores": 0,
            "quiz_logs": 0,
            "simulation_sessions": 0,
            "simulation_evaluations": 0,
            "simulation_feedbacks": 0,
            "matching_results": 0,
            "feedbacks": 0,
        }
        
        # User ID 매핑 초기화
        user_id_map = {}
        # Cohort ID 매핑 초기화 (시드 ID -> 실제 DB ID)
        cohort_id_map = {}
        
        # TrainingCohort 로드 (기존 것이 있으면 스킵)
        for cohort_data in data.get("training_cohorts", []):
            existing_cohort = self.session.exec(
                select(TrainingCohort).where(TrainingCohort.cohort_index == cohort_data["cohort_index"])
            ).first()
            
            seed_cohort_id = cohort_data.get("id", cohort_data["cohort_index"])
            
            if existing_cohort:
                cohort_id_map[seed_cohort_id] = existing_cohort.id
            else:
                cohort = TrainingCohort(
                    cohort_date=date.fromisoformat(cohort_data["cohort_date"]),
                    cohort_index=cohort_data["cohort_index"],
                    label=cohort_data["label"],
                )
                self.session.add(cohort)
                self.session.flush()
                cohort_id_map[seed_cohort_id] = cohort.id
        
        self.session.flush()

        # ------------------------------------------------------------------
        # 1, 2, 3기 멘티 사번/이메일 규칙 통일
        # - 기존 시드 JSON의 사번/이메일 대신
        #   1기: 202501001~, 2기: 202502001~, 3기: 202503001~ 으로 재부여
        # - 이름 가나다 순으로 정렬 후 순번 부여
        # ------------------------------------------------------------------
        email_to_birth = {}
        if cohort_num in (1, 2, 3):
            # 1) 멘티 user 목록 수집 및 정렬
            mentee_users: List[Dict[str, Any]] = [
                u for u in data.get("users", []) if u.get("role") == "mentee"
            ]
            mentee_users.sort(key=lambda u: u.get("name", ""))

            old_email_to_new: Dict[str, Tuple[str, str]] = {}
            for idx, u in enumerate(mentee_users, start=1):
                new_emp = f"2025{cohort_num:02d}{idx:03d}"
                new_email = f"{new_emp}@bank.com"
                old_email = u["email"]

                u["employee_number"] = new_emp
                u["email"] = new_email
                old_email_to_new[old_email] = (new_email, new_emp)

            # 2) training_records의 멘티 레코드도 동일하게 사번/이메일 재설정
            for record_data in data.get("training_records", []):
                if record_data.get("employee_type") != "mentee":
                    continue
                old_email = record_data.get("email")
                if not old_email:
                    continue
                mapping = old_email_to_new.get(old_email)
                if not mapping:
                    continue
                new_email, new_emp = mapping
                record_data["email"] = new_email
                record_data["employee_number"] = new_emp

        # training_records에서 email -> birth 매핑 생성 (비밀번호용)
        email_to_birth = {}
        for record_data in data.get("training_records", []):
            record_email = record_data.get("email")
            record_birth = record_data.get("birth")
            if record_email and record_birth:
                email_to_birth[record_email] = record_birth
        
        # User 로드 (중복 이메일 체크 - 메모리 집합 우선)
        users_to_add = []  # 새로 추가할 user들
        for user_data in data.get("users", []):
            email = user_data["email"]
            
            # 메모리 기반 중복 체크 (이전 cohort에서 이미 추가됨) - 가장 먼저 체크!
            if email in self._seen_user_emails:
                # 이미 추가된 경우, DB에서 찾아서 ID 매핑
                existing_user = self.session.exec(
                    select(User).where(User.email == email)
                ).first()
                if existing_user:
                    user_id_map[user_data["id"]] = existing_user.id
                continue
            
            # DB 기반 중복 체크 (혹시 모를 기존 데이터)
            existing_user = self.session.exec(
                select(User).where(User.email == email)
            ).first()
            
            if existing_user:
                # 이미 존재하면 ID 매핑만 하고 스킵
                user_id_map[user_data["id"]] = existing_user.id
                self._seen_user_emails.add(email)  # 집합에 추가하여 다음 cohort에서 스킵
                continue
            
            # birth 찾기 (training_records에서)
            birth_str = email_to_birth.get(email, "19900101")
            if isinstance(birth_str, str) and len(birth_str) >= 10:
                # "1993-06-19" 형식 -> "19930619"로 변환
                birth_str = birth_str.replace("-", "")[:8]
            elif isinstance(birth_str, str) and len(birth_str) == 8:
                # 이미 "19930619" 형식
                pass
            else:
                birth_str = "19900101"  # 기본값
            
            # 새로 추가할 user 준비 (기수 라벨은 나중에 업데이트)
            employee_number = user_data.get("employee_number")
            user = User(
                email=email,
                hashed_password=get_password_hash(birth_str),
                name=user_data["name"],
                role=UserRole.MENTEE if user_data["role"] == "mentee" else UserRole.MENTOR,
                employee_number=employee_number,
                join_year=user_data.get("join_year"),
                position=user_data.get("position"),
                team=user_data.get("team"),
                phone=user_data.get("phone"),
                mbti=user_data.get("mbti"),
                hobbies=user_data.get("hobbies", ""),
                interests=user_data.get("interests"),
                is_active=user_data.get("is_active", True),
            )
            self.session.add(user)
            # 집합에 먼저 추가 (flush 전에!) - 같은 cohort 내 중복 방지
            self._seen_user_emails.add(email)
            users_to_add.append((user_data["id"], email))
            stats["users"] += 1
        
        # 모든 user를 한 번에 flush
        self.session.flush()
        
        # flush 후 실제 ID로 매핑
        for seed_user_id, email in users_to_add:
            user = self.session.exec(
                select(User).where(User.email == email)
            ).first()
            if user:
                user_id_map[seed_user_id] = user.id
        
        # TrainingCenterRecord 로드 (employee_number 중복 체크 - DB + 메모리)
        for record_data in data.get("training_records", []):
            emp_number = record_data["employee_number"]
            
            # 메모리 기반 중복 체크 (이전 cohort에서 이미 추가됨)
            if emp_number in self._seen_employee_numbers:
                continue
            
            # DB 기반 중복 체크 (혹시 모를 기존 데이터)
            existing_record = self.session.exec(
                select(TrainingCenterRecord).where(
                    TrainingCenterRecord.employee_number == emp_number
                )
            ).first()
            
            if existing_record:
                self._seen_employee_numbers.add(emp_number)
                continue
            
            # 시드 cohort_id를 실제 DB의 cohort_id로 매핑
            seed_cohort_id = record_data["cohort_id"]
            actual_cohort_id = cohort_id_map.get(seed_cohort_id, seed_cohort_id)
            
            record = TrainingCenterRecord(
                cohort_id=actual_cohort_id,
                cohort_slot=record_data["cohort_slot"],
                cohort_date=date.fromisoformat(record_data["cohort_date"]),
                cohort_label=record_data["cohort_label"],
                employee_type=record_data["employee_type"],
                name=record_data["name"],
                employee_number=emp_number,
                gender=record_data["gender"],
                join_year=record_data["join_year"],
                mbti=record_data["mbti"],
                position=record_data["position"],
                department=record_data["department"],
                team=record_data["team"],
                city=record_data["city"],
                hobby1=record_data["hobby1"],
                hobby2=record_data["hobby2"],
                major=record_data["major"],
                career_goal=record_data["career_goal"],
                birth=date.fromisoformat(record_data["birth"]),
                phone=record_data["phone"],
                address=record_data["address"],
                email=record_data["email"],
                section_scores=record_data.get("section_scores", {}),
                question_scores=record_data.get("question_scores", {}),
                total_score=record_data.get("total_score", 0.0),
            )
            self.session.add(record)
            self._seen_employee_numbers.add(emp_number)  # 중복 방지용 집합에 추가
            stats["training_records"] += 1
        
        self.session.flush()
        
        # User들의 기수 라벨 업데이트 (TrainingCenterRecord 생성 후)
        for user_data in data.get("users", []):
            employee_number = user_data.get("employee_number")
            if not employee_number:
                continue
            
            user = self.session.exec(
                select(User).where(User.employee_number == employee_number)
            ).first()
            
            if not user:
                continue
            
            # TrainingCenterRecord에서 기수 정보 찾기
            record = self.session.exec(
                select(TrainingCenterRecord).where(
                    TrainingCenterRecord.employee_number == employee_number
                )
            ).first()
            
            if record and record.cohort_label:
                role_label = "멘티" if user.role == UserRole.MENTEE else "멘토"
                user.cohort_label = f"{record.cohort_label} {role_label}"
                self.session.add(user)
        
        self.session.flush()
        
        # ExamScore 로드
        for exam_data in data.get("exam_scores", []):
            old_user_id = exam_data["mentee_id"]
            new_user_id = user_id_map.get(old_user_id)
            if not new_user_id:
                continue
            
            exam = ExamScore(
                mentee_id=new_user_id,
                exam_name=exam_data["exam_name"],
                exam_type=ExamType(exam_data["exam_type"]),
                exam_date=datetime.fromisoformat(exam_data["exam_date"]),
                score_data=exam_data["score_data"],
                total_score=exam_data["total_score"],
                grade=exam_data.get("grade"),
                feedback=exam_data.get("feedback"),
            )
            self.session.add(exam)
            stats["exam_scores"] += 1
        
        # QuizGenerationLog 로드
        for quiz_data in data.get("quiz_logs", []):
            old_user_id = quiz_data["user_id"]
            new_user_id = user_id_map.get(old_user_id)
            if not new_user_id:
                continue
            
            quiz = QuizGenerationLog(
                user_id=new_user_id,
                mode=quiz_data["mode"],
                total_questions=quiz_data["total_questions"],
                questions=quiz_data.get("questions", []),
                extra=quiz_data.get("extra", {}),
                answers=quiz_data.get("answers"),
                score=quiz_data.get("score"),
                submitted_at=datetime.fromisoformat(quiz_data["submitted_at"]) if quiz_data.get("submitted_at") else None,
                created_at=datetime.fromisoformat(quiz_data["created_at"]),
            )
            self.session.add(quiz)
            stats["quiz_logs"] += 1
        
        # RAGSimulationSession 로드
        session_id_map = {}
        for session_data in data.get("simulation_sessions", []):
            old_user_id = session_data["user_id"]
            new_user_id = user_id_map.get(old_user_id)
            if not new_user_id:
                continue
            
            sim_session = RAGSimulationSession(
                session_key=session_data["session_key"],
                user_id=new_user_id,
                persona_id=session_data["persona_id"],
                scenario_id=session_data["scenario_id"],
                persona_name=session_data.get("persona_name"),
                scenario_title=session_data.get("scenario_title"),
                started_at=datetime.fromisoformat(session_data["started_at"]),
                ended_at=datetime.fromisoformat(session_data["ended_at"]) if session_data.get("ended_at") else None,
                is_completed=session_data.get("is_completed", False),
                total_turns=session_data.get("total_turns", 0),
                duration_seconds=session_data.get("duration_seconds"),
            )
            self.session.add(sim_session)
            self.session.flush()
            session_id_map[session_data["id"]] = sim_session.id
            stats["simulation_sessions"] += 1
        
        # RAGSimulationEvaluation 로드
        for eval_data in data.get("simulation_evaluations", []):
            old_session_id = eval_data["session_id"]
            old_user_id = eval_data["user_id"]
            new_session_id = session_id_map.get(old_session_id)
            new_user_id = user_id_map.get(old_user_id)
            
            if not new_session_id or not new_user_id:
                continue
            
            evaluation = RAGSimulationEvaluation(
                session_id=new_session_id,
                user_id=new_user_id,
                knowledge_point=eval_data.get("knowledge_point", 0),
                skill_point=eval_data.get("skill_point", 0),
                empathy_point=eval_data.get("empathy_point", 0),
                clarity_point=eval_data.get("clarity_point", 0),
                kindness_point=eval_data.get("kindness_point", 0),
                confidence_point=eval_data.get("confidence_point", 0),
                total_point=eval_data.get("total_point", 0),
                grade=eval_data.get("grade"),
                knowledge_reason=eval_data.get("knowledge_reason"),
                skill_reason=eval_data.get("skill_reason"),
                empathy_reason=eval_data.get("empathy_reason"),
                clarity_reason=eval_data.get("clarity_reason"),
                kindness_reason=eval_data.get("kindness_reason"),
                confidence_reason=eval_data.get("confidence_reason"),
                feedback_summary=eval_data.get("feedback_summary"),
                created_at=datetime.fromisoformat(eval_data["created_at"]),
            )
            self.session.add(evaluation)
            stats["simulation_evaluations"] += 1
        
        # MentorMenteeRelation 로드
        for relation_data in data.get("mentor_mentee_relations", []):
            old_mentor_id = relation_data["mentor_id"]
            old_mentee_id = relation_data["mentee_id"]
            new_mentor_id = user_id_map.get(old_mentor_id)
            new_mentee_id = user_id_map.get(old_mentee_id)
            
            if not new_mentor_id or not new_mentee_id:
                continue
            
            # 멘티의 기수 정보 찾기
            mentee_user = self.session.exec(
                select(User).where(User.id == new_mentee_id)
            ).first()
            cohort_id = None
            if mentee_user and mentee_user.employee_number:
                record = self.session.exec(
                    select(TrainingCenterRecord).where(
                        TrainingCenterRecord.employee_number == mentee_user.employee_number,
                        TrainingCenterRecord.employee_type == "mentee"
                    )
                ).first()
                cohort_id = record.cohort_id if record else None
            
            relation = MentorMenteeRelation(
                mentor_id=new_mentor_id,
                mentee_id=new_mentee_id,
                cohort_id=cohort_id,
                matched_at=datetime.fromisoformat(relation_data["matched_at"]),
                is_active=relation_data.get("is_active", True),
                notes=relation_data.get("notes"),
            )
            self.session.add(relation)
        
        # Feedback 로드
        for feedback_data in data.get("feedbacks", []):
            old_mentor_id = feedback_data["mentor_id"]
            old_mentee_id = feedback_data["mentee_id"]
            new_mentor_id = user_id_map.get(old_mentor_id)
            new_mentee_id = user_id_map.get(old_mentee_id)
            
            if not new_mentor_id or not new_mentee_id:
                continue
            
            feedback = Feedback(
                mentor_id=new_mentor_id,
                mentee_id=new_mentee_id,
                feedback_text=feedback_data["feedback_text"],
                feedback_type=feedback_data.get("feedback_type", "general"),
                color_section=feedback_data.get("color_section", "gray"),
                is_read=feedback_data.get("is_read", False),
                created_at=datetime.fromisoformat(feedback_data["created_at"]),
                read_at=datetime.fromisoformat(feedback_data["read_at"]) if feedback_data.get("read_at") else None,
            )
            self.session.add(feedback)
            stats["feedbacks"] += 1
        
        # SimulationFeedback 로드 (시뮬레이션 분석용)
        for sf_data in data.get("simulation_feedbacks", []):
            old_user_id = sf_data["user_id"]
            new_user_id = user_id_map.get(old_user_id)
            
            if not new_user_id:
                continue
            
            sim_feedback = SimulationFeedback(
                user_id=new_user_id,
                session_key=sf_data.get("session_key"),
                persona_id=sf_data.get("persona_id"),
                situation_id=sf_data.get("situation_id"),
                persona_info=sf_data.get("persona_info"),
                persona_age_group=sf_data.get("persona_age_group"),
                persona_gender=sf_data.get("persona_gender"),
                persona_occupation=sf_data.get("persona_occupation"),
                persona_customer_style=sf_data.get("persona_customer_style"),
                situation_info=sf_data.get("situation_info"),
                overall_score=sf_data.get("overall_score", 0.0),
                grade=sf_data.get("grade", "C"),
                performance_level=sf_data.get("performance_level", "양호한 성과"),
                knowledge_score=sf_data.get("knowledge_score", 0),
                skill_score=sf_data.get("skill_score", 0),
                empathy_score=sf_data.get("empathy_score", 0),
                clarity_score=sf_data.get("clarity_score", 0),
                kindness_score=sf_data.get("kindness_score", 0),
                confidence_score=sf_data.get("confidence_score", 0),
                persona_fit_score=sf_data.get("persona_fit_score", 0),
                knowledge_feedback=sf_data.get("knowledge_feedback"),
                skill_feedback=sf_data.get("skill_feedback"),
                empathy_feedback=sf_data.get("empathy_feedback"),
                clarity_feedback=sf_data.get("clarity_feedback"),
                kindness_feedback=sf_data.get("kindness_feedback"),
                confidence_feedback=sf_data.get("confidence_feedback"),
                persona_fit_feedback=sf_data.get("persona_fit_feedback"),
                summary=sf_data.get("summary"),
                improvements=sf_data.get("improvements"),
                total_turns=sf_data.get("total_turns"),
                duration_seconds=sf_data.get("duration_seconds"),
                is_test_mode=sf_data.get("is_test_mode", False),
                created_at=datetime.fromisoformat(sf_data["created_at"]),
            )
            self.session.add(sim_feedback)
            stats["simulation_feedbacks"] += 1
        
        self.session.flush()
        return stats

    def _generate_cohort_4(self) -> Dict[str, int]:
        """4기 데이터 동적 생성 (0~4회 시뮬레이션 진행 상태)"""
        stats = {
            "mentors": 0,
            "mentees": 0,
            "simulation_sessions": 0,
            "quiz_logs": 0,
        }

        cohort_date = COHORT_4_DATE
        cohort_label = "2025년 4기"

        # 기수 생성 (이미 있으면 재사용)
        cohort = self.session.exec(
            select(TrainingCohort).where(TrainingCohort.cohort_index == 4)
        ).first()
        if not cohort:
            cohort = TrainingCohort(
                cohort_date=cohort_date,
                cohort_index=4,
                label=cohort_label,
            )
            self.session.add(cohort)
            self.session.flush()
        
        # 멘토 데이터 먼저 생성 (사번 없이 고정 개수 생성)
        mentor_data_list: List[Dict[str, Any]] = []
        for _ in range(COHORT_4_MENTORS):
            gender = random.choice(["남성", "여성"])
            name = self._generate_name(gender)
            current_year = 2025
            join_year = random.randint(current_year - 10, current_year - 4)
            birth = self._generate_birth(join_year, gender)
            team = self._weighted_choice(BRANCH_TEAMS, TEAM_WEIGHTS)
            mbti = self._weighted_choice(MBTI_OPTIONS, MBTI_WEIGHTS)
            city = self._weighted_choice(CITY_OPTIONS, CITY_WEIGHTS)
            hobbies = random.sample(HOBBY_OPTIONS, 2)
            major = self._weighted_choice(MAJOR_OPTIONS, MAJOR_WEIGHTS)
            career_goal = random.choice(CAREER_GOALS)
            
            mentor_data_list.append({
                "name": name,
                "gender": gender,
                "join_year": join_year,
                "birth": birth,
                "team": team,
                "mbti": mbti,
                "city": city,
                "hobbies": hobbies,
                "major": major,
                "career_goal": career_goal,
                "position": random.choice(["선임", "사원", "책임"]),
            })
        
        # 멘토를 이름 가나다 순으로 정렬
        mentor_data_list.sort(key=lambda x: x["name"])
        
        # 멘토 생성 및 사번 부여 (입사년도 기반: join_year + 01 + 연번)
        # 기존 멘토들의 사번을 참고하여 join_year 별 최대 순번 이후부터 부여
        mentors = []
        # 기존 멘토들의 최대 인덱스 계산
        existing_mentor_records = self.session.exec(
            select(TrainingCenterRecord.join_year, TrainingCenterRecord.employee_number).where(
                TrainingCenterRecord.employee_type == "mentor"
            )
        ).all()
        max_index_by_year: Dict[int, int] = defaultdict(int)
        for jy, emp_no in existing_mentor_records:
            if not jy or not emp_no:
                continue
            year_str = str(jy)
            if not emp_no.startswith(year_str):
                continue
            # 형식: YYYY01XXX 인 경우만 인덱스 추출
            try:
                idx_part = int(emp_no[6:])
            except (ValueError, IndexError):
                continue
            if idx_part > max_index_by_year[jy]:
                max_index_by_year[jy] = idx_part

        for mentor_idx, mentor_data in enumerate(mentor_data_list):
            jy = mentor_data["join_year"]
            current_idx = max_index_by_year.get(jy, 0) + 1
            max_index_by_year[jy] = current_idx

            employee_number = f"{jy}01{current_idx:03d}"
            email = f"{employee_number}@bank.com"
            
            user = User(
                email=email,
                hashed_password=get_password_hash(mentor_data["birth"].strftime("%Y%m%d")),
                name=mentor_data["name"],
                role=UserRole.MENTOR,
                employee_number=employee_number,
                join_year=mentor_data["join_year"],
                position=mentor_data["position"],
                team=mentor_data["team"],
                phone=self._generate_phone(),
                mbti=mentor_data["mbti"],
                hobbies=mentor_data["hobbies"][0],
                interests=json.dumps(mentor_data["hobbies"], ensure_ascii=False),
                cohort_label=f"{cohort_label} 멘토",
                is_active=True,
            )
            self.session.add(user)
            self.session.flush()
            self._seen_user_emails.add(email)
            
            # TrainingCenterRecord 생성 (4기 규칙에 맞게 cohort 정보 통일)
            # - 섹션/문항/총점은 초기 상태이므로 0점/빈 배열로 세팅
            # - 멘토의 cohort_date는 사번의 년-월을 기준으로 설정 (사번: YYYYMMXXX)
            mentor_cohort_date = date(mentor_data["join_year"], 1, 1)  # 사번의 년도, 1월 1일
            record = TrainingCenterRecord(
                cohort_id=cohort.id,
                cohort_slot=mentor_idx,
                cohort_date=mentor_cohort_date,    # 사번의 년-월 기준 (예: 2017-01-01)
                cohort_label=f"{cohort_label} 멘토",  # "2025년 4기 멘토"
                employee_type="mentor",
                name=mentor_data["name"],
                employee_number=employee_number,  # 202504XXX (가나다 순)
                gender=mentor_data["gender"],
                join_year=mentor_data["join_year"],
                mbti=mentor_data["mbti"],
                position=mentor_data["position"],
                department="영업지원본부",
                team=mentor_data["team"],
                city=mentor_data["city"],
                hobby1=mentor_data["hobbies"][0],
                hobby2=mentor_data["hobbies"][1],
                major=mentor_data["major"],
                career_goal=mentor_data["career_goal"],
                birth=mentor_data["birth"],
                phone=user.phone,
                address=f"{mentor_data['city']} 중앙로 {random.randint(1, 100)}",
                email=user.email,
                section_scores={k: 0 for k in TRAINING_SECTION_KEYS},
                question_scores={k: [] for k in TRAINING_SECTION_KEYS},
                total_score=0,
            )
            self.session.add(record)
            self.session.flush()
            
            mentors.append({"user": user, "record": record})
            stats["mentors"] += 1
        
        # 멘티 데이터 먼저 생성 (사번 없이 고정 개수 생성)
        mentee_data_list: List[Dict[str, Any]] = []
        for _ in range(COHORT_4_MENTEES):
            gender = random.choice(["남성", "여성"])
            name = self._generate_name(gender)
            join_year = cohort_date.year
            birth = self._generate_birth(join_year, gender)
            team = self._weighted_choice(BRANCH_TEAMS, TEAM_WEIGHTS)
            mbti = self._weighted_choice(MBTI_OPTIONS, MBTI_WEIGHTS)
            city = self._weighted_choice(CITY_OPTIONS, CITY_WEIGHTS)
            hobbies = random.sample(HOBBY_OPTIONS, 2)
            major = self._weighted_choice(MAJOR_OPTIONS, MAJOR_WEIGHTS)
            career_goal = random.choice(CAREER_GOALS)
            
            mentee_data_list.append({
                "name": name,
                "gender": gender,
                "join_year": join_year,
                "birth": birth,
                "team": team,
                "mbti": mbti,
                "city": city,
                "hobbies": hobbies,
                "major": major,
                "career_goal": career_goal,
            })
        
        # 멘티를 이름 가나다 순으로 정렬
        mentee_data_list.sort(key=lambda x: x["name"])
        
        # 멘티 생성 및 사번 부여 (4기: 202504001~202504030, 이름 가나다 순)
        mentees = []
        for idx, mentee_data in enumerate(mentee_data_list):
            employee_number = f"202504{(idx + 1):03d}"
            email = f"{employee_number}@bank.com"
            
            user = User(
                email=email,
                hashed_password=get_password_hash(mentee_data["birth"].strftime("%Y%m%d")),
                name=mentee_data["name"],
                role=UserRole.MENTEE,
                employee_number=employee_number,
                join_year=mentee_data["join_year"],
                position="사원",
                team=mentee_data["team"],
                phone=self._generate_phone(),
                mbti=mentee_data["mbti"],
                hobbies=mentee_data["hobbies"][0],
                interests=json.dumps(mentee_data["hobbies"], ensure_ascii=False),
                cohort_label=f"{cohort_label} 멘티",
                is_active=True,
            )
            self.session.add(user)
            self.session.flush()
            self._seen_user_emails.add(email)
            
            # TrainingCenterRecord 생성
            # - 섹션/문항/총점은 초기 상태이므로 0점/빈 배열로 세팅
            record = TrainingCenterRecord(
                cohort_id=cohort.id,
                cohort_slot=COHORT_4_MENTORS + idx,
                cohort_date=cohort_date,
                cohort_label=cohort_label,
                employee_type="mentee",
                name=mentee_data["name"],
                employee_number=employee_number,
                gender=mentee_data["gender"],
                join_year=mentee_data["join_year"],
                mbti=mentee_data["mbti"],
                position="사원",
                department="영업지원본부",
                team=mentee_data["team"],
                city=mentee_data["city"],
                hobby1=mentee_data["hobbies"][0],
                hobby2=mentee_data["hobbies"][1],
                major=mentee_data["major"],
                career_goal=mentee_data["career_goal"],
                birth=mentee_data["birth"],
                phone=user.phone,
                address=f"{mentee_data['city']} 중앙로 {random.randint(1, 100)}",
                email=user.email,
                section_scores={k: 0 for k in TRAINING_SECTION_KEYS},
                question_scores={k: [] for k in TRAINING_SECTION_KEYS},
                total_score=0,
            )
            self.session.add(record)
            self.session.flush()
            
            mentees.append({"user": user, "record": record})
            stats["mentees"] += 1
            
            # 초기 ExamScore 생성
            initial_score = random.randint(25, 40)
            score_data = self._distribute_score_to_categories(initial_score)
            exam = ExamScore(
                mentee_id=user.id,
                exam_name="초기 평가",
                exam_type=ExamType.BEGINNING,
                exam_date=datetime.combine(cohort_date + timedelta(days=7), datetime.min.time()),
                score_data=json.dumps(score_data, ensure_ascii=False),
                total_score=float(sum(score_data.values())),
                grade=self._calculate_grade(sum(score_data.values())),
                feedback="초기 평가 결과가 기록되었습니다.",
            )
            self.session.add(exam)
            
            # 0~4회 시뮬레이션 진행 (사람마다 편차)
            num_simulations = random.randint(0, 4)
            for s in range(num_simulations):
                sim_date = datetime.combine(
                    cohort_date + timedelta(days=random.randint(7, 14)),
                    datetime.min.time()
                ) + timedelta(hours=random.randint(9, 17))
                
                # 초기 점수 (25~40점)
                total_score = random.randint(25, 40)
                metrics = self._generate_simulation_metrics(total_score)
                
                sim_session = RAGSimulationSession(
                    session_key=f"session_{user.id}_{int(sim_date.timestamp())}",
                    user_id=user.id,
                    persona_id=random.choice(PERSONA_IDS),
                    scenario_id=random.choice(SCENARIO_IDS),
                    persona_name=f"고객_{random.randint(1, 100)}",
                    scenario_title=f"시나리오_{random.randint(1, 50)}",
                    started_at=sim_date,
                    ended_at=sim_date + timedelta(minutes=random.randint(3, 10)),
                    is_completed=True,
                    total_turns=random.randint(6, 12),
                    duration_seconds=random.randint(180, 600),
                )
                self.session.add(sim_session)
                self.session.flush()
                
                evaluation = RAGSimulationEvaluation(
                    session_id=sim_session.id,
                    user_id=user.id,
                    **metrics,
                    total_point=self._calculate_weighted_total(metrics),
                    grade=self._calculate_simulation_grade(self._calculate_weighted_total(metrics)),
                    feedback_summary="초기 단계입니다. 꾸준히 연습하세요.",
                    created_at=sim_date + timedelta(minutes=random.randint(3, 10)),
                )
                self.session.add(evaluation)
                
                # SimulationFeedback 생성 (시뮬레이션 분석용)
                sim_feedback = SimulationFeedback(
                    user_id=user.id,
                    session_key=sim_session.session_key,
                    persona_id=sim_session.persona_id,
                    situation_id=sim_session.scenario_id,
                    persona_info=f"{random.choice(PERSONA_AGE_GROUPS)} {random.choice(PERSONA_GENDERS)} {random.choice(PERSONA_OCCUPATIONS)}",
                    persona_age_group=random.choice(PERSONA_AGE_GROUPS),
                    persona_gender=random.choice(PERSONA_GENDERS),
                    persona_occupation=random.choice(PERSONA_OCCUPATIONS),
                    persona_customer_style=random.choice(PERSONA_CUSTOMER_STYLES),
                    situation_info=random.choice(SITUATION_CATEGORIES),
                    overall_score=float(total_score),
                    grade=self._calculate_simulation_grade(total_score),
                    performance_level="초기 단계" if total_score < 50 else "양호한 성과",
                    knowledge_score=metrics["knowledge_point"],
                    skill_score=metrics["skill_point"],
                    clarity_score=metrics["clarity_point"],
                    kindness_score=metrics["kindness_point"],
                    confidence_score=metrics["confidence_point"],
                    persona_fit_score=random.randint(25, 45),
                    summary="초기 단계입니다. 꾸준히 연습하세요.",
                    is_test_mode=False,
                    created_at=sim_date + timedelta(minutes=random.randint(3, 10)),
                )
                self.session.add(sim_feedback)
                
                stats["simulation_sessions"] += 1
            
            # 0~4회 퀴즈 진행
            num_quizzes = random.randint(0, 4)
            for q in range(num_quizzes):
                quiz_date = datetime.combine(
                    cohort_date + timedelta(days=random.randint(7, 14)),
                    datetime.min.time()
                ) + timedelta(hours=random.randint(9, 17))
                
                quiz = QuizGenerationLog(
                    user_id=user.id,
                    mode=random.choice(["random", "custom"]),
                    total_questions=10,
                    questions=[],
                    extra={"category": random.choice(EXAM_CATEGORIES)},
                    score=random.randint(40, 70),
                    submitted_at=quiz_date,
                    created_at=quiz_date,
                )
                self.session.add(quiz)
                stats["quiz_logs"] += 1
        
        # 전체 멘토/멘티 생성 후 최종 flush 및 개수 확인
        self.session.flush()
        
        created_mentors = self.session.exec(
            select(TrainingCenterRecord).where(
                TrainingCenterRecord.cohort_id == cohort.id,
                TrainingCenterRecord.employee_type == "mentor"
            )
        ).all()
        created_mentees = self.session.exec(
            select(TrainingCenterRecord).where(
                TrainingCenterRecord.cohort_id == cohort.id,
                TrainingCenterRecord.employee_type == "mentee"
            )
        ).all()
        
        print(f"✅ 4기 생성 완료: 멘토 {len(created_mentors)}명, 멘티 {len(created_mentees)}명")

        return stats

    def _run_matching_for_cohort_4(self) -> Dict[str, int]:
        """4기 멘토-멘티 매칭 실행"""
        stats = {
            "matched_count": 0,
            "relations_created": 0,
        }
        
        # 4기 멘티/멘토 조회
        cohort_4 = self.session.exec(
            select(TrainingCohort).where(TrainingCohort.cohort_index == 4)
        ).first()
        
        if not cohort_4:
            return stats
        
        mentees = self.session.exec(
            select(TrainingCenterRecord).where(
                TrainingCenterRecord.cohort_id == cohort_4.id,
                TrainingCenterRecord.employee_type == "mentee"
            )
        ).all()
        
        mentors = self.session.exec(
            select(TrainingCenterRecord).where(
                TrainingCenterRecord.employee_type == "mentor"
            )
        ).all()
        
        if not mentees or not mentors:
            return stats
        
        # 간단한 매칭 (멘토당 2명 멘티)
        matched_at = datetime.now()
        mentor_idx = 0
        
        for mentee in mentees:
            mentor = mentors[mentor_idx % len(mentors)]
            
            # MatchingResult 생성
            matching = MatchingResult(
                mentee_id=mentee.id,
                mentor_id=mentor.id,
                total_score=random.uniform(0.6, 0.9),
                team_score=random.uniform(0.7, 1.0),
                city_score=random.uniform(0.5, 1.0),
                hobby_score=random.uniform(0.3, 1.0),
                weakness_strength_score=random.uniform(0.5, 1.0),
                career_score=random.uniform(0.4, 1.0),
                major_score=random.uniform(0.3, 1.0),
                matching_details={},
                is_active=True,
                matched_at=matched_at,
            )
            self.session.add(matching)
            stats["matched_count"] += 1
            
            # MentorMenteeRelation 생성
            mentee_user = self.session.exec(
                select(User).where(User.employee_number == mentee.employee_number)
            ).first()
            mentor_user = self.session.exec(
                select(User).where(User.employee_number == mentor.employee_number)
            ).first()
            
            if mentee_user and mentor_user:
                relation = MentorMenteeRelation(
                    mentor_id=mentor_user.id,
                    mentee_id=mentee_user.id,
                    cohort_id=cohort_4.id,  # 4기 cohort ID
                    matched_at=matched_at,
                    is_active=True,
                    notes="매칭 시스템 자동 생성 (4기)",
                )
                self.session.add(relation)
                stats["relations_created"] += 1
            
            mentor_idx += 1
            if mentor_idx % 2 == 0:
                mentor_idx += 1
        
        # 매칭 리포트 생성
        report = MatchingReport(
            report_name=f"2025년 4기 매칭 리포트 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            total_mentees=len(mentees),
            total_mentors=len(mentors),
            total_matched=stats["matched_count"],
            overall_score=0.75,
            team_statistics={},
            report_data={},
        )
        self.session.add(report)
        
        self.session.flush()
        return stats

    def _run_matching_all_cohorts(self) -> Dict[str, Any]:
        """각 기수별로 독립적인 멘토 할당하여 매칭 실행 (완전 재구현)"""
        stats = {
            "matched_count": 0,
            "relations_created": 0,
            "cohorts": {},
        }
        
        # 1. 모든 기존 관계 비활성화
        existing_relations = self.session.exec(
            select(MentorMenteeRelation).where(
                MentorMenteeRelation.is_active == True
            )
        ).all()
        for relation in existing_relations:
            relation.is_active = False
            self.session.add(relation)
        self.session.flush()
        
        # 2. 모든 기수 조회 (1, 2, 3, 4기)
        cohorts = self.session.exec(
            select(TrainingCohort).where(
                TrainingCohort.cohort_index.in_([1, 2, 3, 4])
            ).order_by(TrainingCohort.cohort_index)
        ).all()
        
        # 3. 전체 멘토 풀 조회 (User와 TrainingCenterRecord 조인)
        all_mentor_users = self.session.exec(
            select(User).where(User.role == UserRole.MENTOR)
        ).all()
        
        # 멘토 User를 employee_number로 매핑
        mentor_user_map = {}
        for mentor_user in all_mentor_users:
            if mentor_user.employee_number:
                mentor_user_map[mentor_user.employee_number] = mentor_user
        
        # 전체 멘토 TrainingCenterRecord 조회
        all_mentor_records = self.session.exec(
            select(TrainingCenterRecord).where(
                TrainingCenterRecord.employee_type == "mentor"
            )
        ).all()
        
        # 사용된 멘토 추적 (전체 기수에 걸쳐)
        used_mentor_employee_numbers = set()
        
        matched_at = datetime.now()
        
        # 4. 각 기수별로 처리
        for cohort in cohorts:
            cohort_stats = {
                "matched_count": 0,
                "relations_created": 0,
                "mentors_assigned": 0,
            }
            
            # 해당 기수의 멘티 조회
            mentees = self.session.exec(
                select(TrainingCenterRecord).where(
                    TrainingCenterRecord.cohort_id == cohort.id,
                    TrainingCenterRecord.employee_type == "mentee"
                ).order_by(TrainingCenterRecord.cohort_slot)
            ).all()
            
            if not mentees:
                stats["cohorts"][cohort.label] = cohort_stats
                continue
            
            # 해당 기수에 할당할 멘토 선택 (아직 다른 기수에 할당되지 않은 멘토만)
            available_mentors = [
                m for m in all_mentor_records 
                if m.employee_number and 
                m.employee_number not in used_mentor_employee_numbers and
                mentor_user_map.get(m.employee_number) is not None
            ]
            
            # 필요한 멘토 수 (멘티 수 / 2, 최대 15명)
            required_mentors = min(len(mentees) // 2, 15)
            
            if len(available_mentors) < required_mentors:
                # 사용 가능한 멘토가 부족하면 경고
                print(f"⚠️ {cohort.label}: 사용 가능한 멘토가 부족합니다 (필요: {required_mentors}명, 사용 가능: {len(available_mentors)}명)")
                required_mentors = len(available_mentors)
            
            if required_mentors == 0:
                stats["cohorts"][cohort.label] = cohort_stats
                continue
            
            # 랜덤하게 또는 순서대로 멘토 선택
            selected_mentor_records = random.sample(available_mentors, required_mentors)
            
            # 선택된 멘토들을 사용된 멘토 집합에 추가
            for m in selected_mentor_records:
                if m.employee_number:
                    used_mentor_employee_numbers.add(m.employee_number)
            
            # 5. 멘토당 2명의 멘티 할당
            mentor_idx = 0
            for mentee in mentees:
                # 멘토 인덱스 계산 (멘토당 2명씩, 순환)
                mentor_index = (mentor_idx // 2) % len(selected_mentor_records)
                mentor_record = selected_mentor_records[mentor_index]
                mentor_user = mentor_user_map.get(mentor_record.employee_number)
                
                if not mentor_user:
                    continue
                
                # MatchingResult 생성
                matching = MatchingResult(
                    mentee_id=mentee.id,
                    mentor_id=mentor_record.id,
                    total_score=random.uniform(0.6, 0.9),
                    team_score=random.uniform(0.7, 1.0),
                    city_score=random.uniform(0.5, 1.0),
                    hobby_score=random.uniform(0.3, 1.0),
                    weakness_strength_score=random.uniform(0.5, 1.0),
                    career_score=random.uniform(0.4, 1.0),
                    major_score=random.uniform(0.3, 1.0),
                    matching_details={},
                    is_active=True,
                    matched_at=matched_at,
                )
                self.session.add(matching)
                stats["matched_count"] += 1
                cohort_stats["matched_count"] += 1
                
                # MentorMenteeRelation 생성
                mentee_user = self.session.exec(
                    select(User).where(User.employee_number == mentee.employee_number)
                ).first()
                
                if mentee_user:
                    relation = MentorMenteeRelation(
                        mentor_id=mentor_user.id,
                        mentee_id=mentee_user.id,
                        cohort_id=cohort.id,
                        matched_at=matched_at,
                        is_active=True,
                        notes=f"매칭 시스템 자동 생성 ({cohort.label})",
                    )
                    self.session.add(relation)
                    stats["relations_created"] += 1
                    cohort_stats["relations_created"] += 1
                    
                    # 멘토의 cohort_label 업데이트 (해당 기수 기준)
                    mentor_user.cohort_label = f"{cohort.label} 멘토"
                    mentor_record.cohort_label = f"{cohort.label} 멘토"
                    self.session.add(mentor_user)
                    self.session.add(mentor_record)
                
                mentor_idx += 1
            
            cohort_stats["mentors_assigned"] = len(selected_mentor_records)
            stats["cohorts"][cohort.label] = cohort_stats
            self.session.flush()
        
        # 6. 매칭되지 않은 멘토들의 cohort_label 초기화
        for mentor_user in all_mentor_users:
            if mentor_user.employee_number and mentor_user.employee_number not in used_mentor_employee_numbers:
                mentor_user.cohort_label = f"{mentor_user.join_year}년 입사 멘토" if mentor_user.join_year else None
                self.session.add(mentor_user)
                
                mentor_record = self.session.exec(
                    select(TrainingCenterRecord).where(
                        TrainingCenterRecord.employee_number == mentor_user.employee_number,
                        TrainingCenterRecord.employee_type == "mentor"
                    )
                ).first()
                if mentor_record:
                    mentor_record.cohort_label = f"{mentor_user.join_year}년 입사 멘토" if mentor_user.join_year else None
                    self.session.add(mentor_record)
        
        self.session.flush()
        
        # 7. 매칭 리포트 생성
        total_mentees = sum(
            len(self.session.exec(
                select(TrainingCenterRecord).where(
                    TrainingCenterRecord.cohort_id == c.id,
                    TrainingCenterRecord.employee_type == "mentee"
                )
            ).all()) for c in cohorts
        )
        
        report = MatchingReport(
            report_name=f"전체 기수 매칭 리포트 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            total_mentees=total_mentees,
            total_mentors=len(used_mentor_employee_numbers),
            total_matched=stats["matched_count"],
            overall_score=random.uniform(0.7, 0.9),
            team_statistics={},
            report_data=stats["cohorts"],
        )
        self.session.add(report)
        
        self.session.flush()
        return stats

    def _add_missing_mentors_to_cohort(self, cohort: TrainingCohort, count: int) -> None:
        """특정 기수에 부족한 멘토만 추가 생성"""
        # 해당 기수의 현재 멘토 수 확인
        existing_mentors = self.session.exec(
            select(TrainingCenterRecord).where(
                TrainingCenterRecord.cohort_id == cohort.id,
                TrainingCenterRecord.employee_type == "mentor"
            )
        ).all()
        
        # 사번 생성용 데이터 미리 계산
        existing_mentor_records = self.session.exec(
            select(TrainingCenterRecord.join_year, TrainingCenterRecord.employee_number).where(
                TrainingCenterRecord.employee_type == "mentor"
            )
        ).all()
        max_index_by_year: Dict[int, int] = defaultdict(int)
        for jy, emp_no in existing_mentor_records:
            if not jy or not emp_no:
                continue
            year_str = str(jy)
            if not emp_no.startswith(year_str):
                continue
            try:
                idx_part = int(emp_no[6:])
            except (ValueError, IndexError):
                continue
            if idx_part > max_index_by_year[jy]:
                max_index_by_year[jy] = idx_part
        
        # 멘토 데이터 생성
        for i in range(count):
            # 슬롯 번호 동적 계산 (각 반복마다 현재 DB 상태 확인)
            all_cohort_records = self.session.exec(
                select(TrainingCenterRecord).where(
                    TrainingCenterRecord.cohort_id == cohort.id
                )
            ).all()
            existing_slots = {r.cohort_slot for r in all_cohort_records}
            next_slot = max(existing_slots) + 1 if existing_slots else 0
            
            gender = random.choice(["남성", "여성"])
            name = self._generate_name(gender)
            current_year = 2025
            join_year = random.randint(current_year - 10, current_year - 4)
            birth = self._generate_birth(join_year, gender)
            team = self._weighted_choice(BRANCH_TEAMS, TEAM_WEIGHTS)
            mbti = self._weighted_choice(MBTI_OPTIONS, MBTI_WEIGHTS)
            city = self._weighted_choice(CITY_OPTIONS, CITY_WEIGHTS)
            hobbies = random.sample(HOBBY_OPTIONS, 2)
            major = self._weighted_choice(MAJOR_OPTIONS, MAJOR_WEIGHTS)
            career_goal = random.choice(CAREER_GOALS)
            
            # 사번 생성
            jy = join_year
            current_idx = max_index_by_year.get(jy, 0) + 1
            max_index_by_year[jy] = current_idx
            employee_number = f"{jy}01{current_idx:03d}"
            
            # 중복 체크
            while employee_number in self._seen_employee_numbers:
                current_idx += 1
                max_index_by_year[jy] = current_idx
                employee_number = f"{jy}01{current_idx:03d}"
            
            email = f"{employee_number}@bank.com"
            while email in self._seen_user_emails:
                current_idx += 1
                employee_number = f"{jy}01{current_idx:03d}"
                email = f"{employee_number}@bank.com"
            
            # User 생성
            user = User(
                email=email,
                hashed_password=get_password_hash(birth.strftime("%Y%m%d")),
                name=name,
                role=UserRole.MENTOR,
                employee_number=employee_number,
                join_year=join_year,
                position=random.choice(["선임", "사원", "책임"]),
                team=team,
                phone=self._generate_phone(),
                mbti=mbti,
                hobbies=hobbies[0],
                interests=json.dumps(hobbies, ensure_ascii=False),
                cohort_label=f"{cohort.label} 멘토",
                is_active=True,
            )
            self.session.add(user)
            self.session.flush()
            self._seen_user_emails.add(email)
            self._seen_employee_numbers.add(employee_number)
            
            # TrainingCenterRecord 생성
            mentor_cohort_date = date(join_year, 1, 1)
            record = TrainingCenterRecord(
                cohort_id=cohort.id,
                cohort_slot=next_slot,
                cohort_date=mentor_cohort_date,
                cohort_label=f"{cohort.label} 멘토",
                employee_type="mentor",
                name=name,
                employee_number=employee_number,
                gender=gender,
                join_year=join_year,
                mbti=mbti,
                position=random.choice(["선임", "사원", "책임"]),
                department="영업지원본부",
                team=team,
                city=city,
                hobby1=hobbies[0],
                hobby2=hobbies[1],
                major=major,
                career_goal=career_goal,
                birth=birth,
                phone=user.phone,
                address=f"{city} 중앙로 {random.randint(1, 100)}",
                email=email,
                section_scores={k: 0 for k in TRAINING_SECTION_KEYS},
                question_scores={k: [] for k in TRAINING_SECTION_KEYS},
                total_score=0,
            )
            self.session.add(record)
            self.session.flush()

    # 유틸리티 메서드들
    def _generate_name(self, gender: str) -> str:
        last = random.choice(LAST_NAMES)
        if gender == "남성":
            first = random.choice(MALE_FIRST_LEADING) + random.choice(MALE_FIRST_TRAILING)
        else:
            first = random.choice(FEMALE_FIRST_LEADING) + random.choice(FEMALE_FIRST_TRAILING)
        return f"{last}{first}"

    def _generate_birth(self, join_year: int, gender: str) -> date:
        if gender == "남성":
            birth_year = random.randint(join_year - 27, join_year - 25)
        else:
            birth_year = random.randint(join_year - 25, join_year - 23)
        return date(birth_year, random.randint(1, 12), random.randint(1, 28))

    def _generate_phone(self) -> str:
        mid = random.randint(2000, 9999)
        last = random.randint(1000, 9999)
        return f"010-{mid:04d}-{last:04d}"

    def _weighted_choice(self, options: List[str], weights: List[float]) -> str:
        return random.choices(options, weights=weights, k=1)[0]

    def _distribute_score_to_categories(self, total_score: int) -> Dict[str, int]:
        max_per_category = 10
        target_total = (total_score * 60) // 100
        base = target_total // len(EXAM_CATEGORIES)
        remainder = target_total % len(EXAM_CATEGORIES)
        
        scores = {}
        for i, category in enumerate(EXAM_CATEGORIES):
            scores[category] = min(max_per_category, base + (1 if i < remainder else 0))
        
        return scores

    def _generate_simulation_metrics(self, total_score: int) -> Dict[str, int]:
        metrics = {}
        for metric in ["knowledge_point", "skill_point", "empathy_point", "clarity_point", "kindness_point", "confidence_point"]:
            variation = random.randint(-10, 10)
            metrics[metric] = max(0, min(100, total_score + variation))
        return metrics

    def _calculate_weighted_total(self, metrics: Dict[str, int]) -> int:
        weights = {
            "knowledge_point": 0.20,
            "skill_point": 0.20,
            "empathy_point": 0.15,
            "clarity_point": 0.15,
            "kindness_point": 0.15,
            "confidence_point": 0.15,
        }
        return int(round(sum(metrics.get(k, 0) * w for k, w in weights.items())))

    def _calculate_grade(self, total: int) -> str:
        if total >= 54:
            return "A"
        elif total >= 48:
            return "B"
        elif total >= 42:
            return "C"
        elif total >= 36:
            return "D"
        return "F"

    def _calculate_simulation_grade(self, total: int) -> str:
        if total >= 90:
            return "A+"
        elif total >= 85:
            return "A"
        elif total >= 80:
            return "B+"
        elif total >= 75:
            return "B"
        elif total >= 70:
            return "C+"
        elif total >= 65:
            return "C"
        return "D"

