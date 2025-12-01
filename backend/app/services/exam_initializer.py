"""
시험 점수 초기화 유틸리티
연수원 연동/관리자 기능 등 사용자 계정 생성 시 공통으로 사용한다.
"""
from __future__ import annotations

import json
import random
from datetime import datetime
from typing import Dict, Optional

from sqlmodel import Session, select

from app.models.mentor import ExamScore, ExamType
from app.models.training_center import TrainingCenterRecord
from app.models.user import User, UserRole


def generate_random_performance_scores() -> Dict[str, int]:
    """멘티에게 보여줄 랜덤 성과 지표 생성"""
    return {
        "은행업무": random.randint(60, 95),
        "상품지식": random.randint(60, 95),
        "고객응대": random.randint(60, 95),
        "법규준수": random.randint(60, 95),
        "IT활용": random.randint(60, 95),
        "영업실적": random.randint(60, 95),
    }


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
            performance_scores = generate_random_performance_scores()
            total_score = sum(performance_scores.values()) / len(performance_scores)
            grade = _grade_from_total(total_score)

            exam_score = ExamScore(
                mentee_id=user_id,
                exam_name=exam_name,
                exam_type=exam_type,
                exam_date=exam_date,
                score_data=json.dumps(performance_scores, ensure_ascii=False),
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

