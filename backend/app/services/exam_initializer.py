"""
시험 점수 초기화 유틸리티
연수원 연동/관리자 기능 등 사용자 계정 생성 시 공통으로 사용한다.
"""
from __future__ import annotations

import json
import random
import hashlib
from datetime import datetime
from typing import Dict, Optional

from sqlmodel import Session, select

from app.models.mentor import ExamScore, ExamType
from app.models.training_center import TrainingCenterRecord
from app.models.user import User, UserRole


def generate_random_performance_scores() -> Dict[str, int]:
    """멘티에게 보여줄 랜덤 성과 지표 생성 (구버전 호환용)"""
    return {
        "은행업무": random.randint(60, 95),
        "상품지식": random.randint(60, 95),
        "고객응대": random.randint(60, 95),
        "법규준수": random.randint(60, 95),
        "IT활용": random.randint(60, 95),
        "영업실적": random.randint(60, 95),
    }


def generate_progressive_exam_score(exam_type: ExamType, previous_total: Optional[float] = None, user_seed: Optional[int] = None) -> Dict[str, int]:
    """
    점진적 상승 패턴의 시험 점수 생성
    - 초기: 30~40% (18~24점)
    - 중간: 50~70% (30~42점)
    - 최종: 80~90% (48~54점)
    - 일부(10~20%)는 성적이 거의 오르지 않음
    """
    EXAM_SECTION_KEYS = [
        "은행업무",
        "상품개발 및 운용",
        "신용분석 및 리스크관리",
        "외환",
        "은행지식 및 관련법률",
        "하경은행",
    ]
    
    # 사용자별 일관성을 위한 시드 설정
    if user_seed is not None:
        random.seed(user_seed)
        # 성적이 오르지 않는 사람인지 결정 (15% 확률, 사용자별로 일관성 있게)
        is_low_performer = (user_seed % 100) < 15  # 0~99 중 0~14는 저성과자
    else:
        # 시드가 없으면 랜덤으로 결정
        is_low_performer = random.random() < 0.15
    
    if exam_type == ExamType.BEGINNING:
        # 초기: 30~40% (18~24점)
        if is_low_performer:
            total = random.randint(15, 20)  # 더 낮은 점수
        else:
            total = random.randint(18, 24)
    elif exam_type == ExamType.MIDTERM:
        # 중간: 50~70% (30~42점)
        if previous_total is not None:
            if is_low_performer:
                # 성적이 안 오르는 경우: 최대 +3점
                total = random.randint(int(previous_total), int(previous_total) + 3)
                total = min(42, total)  # 최대 42점
            else:
                # 정상 상승: 초기보다 최소 +6점 이상
                min_score = max(30, int(previous_total) + 6)
                total = random.randint(min_score, 42)
        else:
            if is_low_performer:
                total = random.randint(20, 28)
            else:
                total = random.randint(30, 42)
    elif exam_type == ExamType.FINAL:
        # 최종: 80~90% (48~54점)
        if previous_total is not None:
            if is_low_performer:
                # 성적이 안 오르는 경우: 최대 +3점
                total = random.randint(int(previous_total), int(previous_total) + 3)
                total = min(54, total)  # 최대 54점
            else:
                # 정상 상승: 중간보다 최소 +6점 이상
                min_score = max(48, int(previous_total) + 6)
                total = random.randint(min_score, 54)
        else:
            if is_low_performer:
                total = random.randint(25, 35)
            else:
                total = random.randint(48, 54)
    else:
        # 기본값
        total = random.randint(18, 54)
    
    # 총점을 6개 섹션으로 균등 분배
    total = max(0, min(60, total))
    base = total // len(EXAM_SECTION_KEYS)
    remainder = total % len(EXAM_SECTION_KEYS)
    scores: Dict[str, int] = {}
    
    # 초기 분배
    for idx, key in enumerate(EXAM_SECTION_KEYS):
        scores[key] = min(10, base + (1 if idx < remainder else 0))
    
    # 다양성 부여
    for _ in range(10):
        donor, receiver = random.sample(EXAM_SECTION_KEYS, 2)
        if scores[donor] > 2 and scores[receiver] < 10:
            transfer = min(2, scores[donor] - 2, 10 - scores[receiver])
            if transfer > 0:
                scores[donor] -= transfer
                scores[receiver] += transfer
    
    # 최종 검증
    for key in EXAM_SECTION_KEYS:
        scores[key] = max(0, min(10, scores[key]))
    
    # 총점 조정
    current_total = sum(scores.values())
    if current_total != total:
        diff = total - current_total
        if diff > 0:
            min_key = min(EXAM_SECTION_KEYS, key=lambda k: scores[k])
            scores[min_key] = min(10, scores[min_key] + diff)
        elif diff < 0:
            max_key = max(EXAM_SECTION_KEYS, key=lambda k: scores[k])
            scores[max_key] = max(0, scores[max_key] + diff)
    
    return scores


EXAM_TYPE_LABELS = {
    ExamType.BEGINNING: "연수원 초기 평가",
    ExamType.MIDTERM: "연수원 중간 평가",
    ExamType.FINAL: "연수원 최종 평가",
}


def _calculate_grade(total_score: float) -> str:
    """총점 기반 학점 계산"""
    if total_score >= 90:
        return "A+"
    if total_score >= 85:
        return "A"
    if total_score >= 80:
        return "B+"
    if total_score >= 75:
        return "B"
    if total_score >= 70:
        return "C+"
    if total_score >= 65:
        return "C"
    return "D"


def create_initial_exam_score(
    user_id: int,
    session: Session,
    exam_type: ExamType = ExamType.BEGINNING,
    section_scores_override: Optional[Dict[str, int]] = None,
    total_score_override: Optional[float] = None,
    feedback: Optional[str] = None,
    exam_date: Optional[datetime] = None,
    exam_name: Optional[str] = None,
    commit: bool = True,
):
    """
    멘티 시험 점수 생성 유틸리티
    연수원 계정 생성/관리자 스크립트에서 재사용된다.
    """
    try:
        user = session.get(User, user_id)
        if not user:
            return

        training_record = None
        if user.employee_number:
            training_record = session.exec(
                select(TrainingCenterRecord).where(
                    TrainingCenterRecord.employee_number == user.employee_number,
                    TrainingCenterRecord.employee_type == "mentee",
                )
            ).first()

        exam_name = exam_name or EXAM_TYPE_LABELS.get(exam_type, "연수원 평가")
        exam_date = exam_date or datetime.utcnow()

        def _grade_from_total(total: float) -> str:
            normalized = (total / 60) * 100 if total <= 60 else total
            return _calculate_grade(normalized)

        if section_scores_override is not None:
            section_scores = section_scores_override
            total_score = (
                total_score_override
                if total_score_override is not None
                else sum(section_scores.values()) / len(section_scores)
            )
            grade = _grade_from_total(total_score)
            
            exam_score = ExamScore(
                mentee_id=user_id,
                exam_name=exam_name,
                exam_type=exam_type,
                exam_date=exam_date,
                score_data=json.dumps(section_scores, ensure_ascii=False),
                total_score=total_score,
                grade=grade,
                feedback=feedback or "시험을 완료하셨습니다. 앞으로도 꾸준히 발전해 나가세요!",
            )
        elif (
            training_record
            and training_record.section_scores
            and exam_type == ExamType.BEGINNING
        ):
            section_scores = training_record.section_scores
            total_score = float(training_record.total_score)
            grade = _grade_from_total(total_score)

            exam_score = ExamScore(
                mentee_id=user_id,
                exam_name=exam_name,
                exam_type=exam_type,
                exam_date=exam_date,
                score_data=json.dumps(section_scores, ensure_ascii=False),
                total_score=total_score,
                grade=grade,
                feedback=feedback or "연수원 시험 점수가 반영되었습니다.",
            )
        else:
            # 점진적 상승 패턴 적용
            # 이전 점수 확인
            previous_total = None
            if exam_type != ExamType.BEGINNING:
                previous_exam = session.exec(
                    select(ExamScore).where(
                        ExamScore.mentee_id == user_id,
                        ExamScore.exam_type == (
                            ExamType.MIDTERM if exam_type == ExamType.FINAL 
                            else ExamType.BEGINNING
                        )
                    ).order_by(ExamScore.exam_date.desc())
                ).first()
                if previous_exam:
                    previous_total = previous_exam.total_score
            
            # 사용자별 일관성을 위한 시드 (user_id 기반)
            user_seed = user_id % 10000
            
            # 점진적 상승 패턴 점수 생성
            section_scores = generate_progressive_exam_score(
                exam_type=exam_type,
                previous_total=previous_total,
                user_seed=user_seed
            )
            total_score = float(sum(section_scores.values()))
            grade = _grade_from_total(total_score)

            exam_score = ExamScore(
                mentee_id=user_id,
                exam_name=exam_name,
                exam_type=exam_type,
                exam_date=exam_date,
                score_data=json.dumps(section_scores, ensure_ascii=False),
                total_score=round(total_score, 1),
                grade=grade,
                feedback=feedback
                or "시험을 완료하셨습니다. 앞으로도 꾸준히 발전해 나가세요!",
            )

        session.add(exam_score)
        if commit:
            session.commit()
        else:
            session.flush()
        return exam_score
    except Exception as exc:
        if commit:
            session.rollback()
        raise exc

