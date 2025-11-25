"""
2025년 분기별 고정 기수 데이터를 생성하는 스크립트
- 각 기수: 멘티 120명, 멘토 60명
- 1~3기는 수료, 4기는 중간 평가까지 완료
- TrainingCenterRecord 에만 데이터를 기록하여 계정 없이도 EDA가 가능하도록 함
"""
from __future__ import annotations

from datetime import date
from typing import List

from sqlalchemy import delete
from sqlmodel import Session

from app.database import engine
from app.models.training_center import TrainingCenterRecord, TrainingCohort
from app.services.training_center_service import TrainingCenterService

COHORT_SPECS = [
    {
        "label": "2025년 1기 (1분기 수료)",
        "cohort_date": date(2025, 1, 1),
        "cohort_index": 1,
        "status": "completed",
    },
    {
        "label": "2025년 2기 (2분기 수료)",
        "cohort_date": date(2025, 4, 1),
        "cohort_index": 2,
        "status": "completed",
    },
    {
        "label": "2025년 3기 (3분기 수료)",
        "cohort_date": date(2025, 7, 1),
        "cohort_index": 3,
        "status": "completed",
    },
    {
        "label": "2025년 4기 (중간 평가 완료)",
        "cohort_date": date(2025, 10, 1),
        "cohort_index": 4,
        "status": "mid_exam",
    },
]


def create_large_cohort_data(session: Session):
    """2025년 분기별 TrainingCenterRecord 데이터를 생성"""
    service = TrainingCenterService(session)
    total_mentees = 0
    total_mentors = 0

    print("🔧 2025년 1~4기 고정 DB 초기화 시작...")

    for spec in COHORT_SPECS:
        _reset_cohort(session, spec["cohort_date"])

        cohort = service._create_cohort(
            spec["label"], spec["cohort_date"], spec["cohort_index"]
        )

        mentee_records = service._generate_records_for_cohort(
            cohort, 120, "mentee"
        )
        service._assign_employee_numbers_by_name(
            mentee_records, spec["cohort_date"]
        )
        _apply_status_adjustments(
            mentee_records, spec["status"], service, is_mentor=False
        )

        mentor_records = service._generate_records_for_cohort(
            cohort, 60, "mentor"
        )
        service._assign_employee_numbers_by_join_year(mentor_records)
        _apply_status_adjustments(
            mentor_records, spec["status"], service, is_mentor=True
        )

        total_mentees += len(mentee_records)
        total_mentors += len(mentor_records)

        print(
            f"  ✅ {spec['label']} 생성 완료 "
            f"(멘티 {len(mentee_records)}명 / 멘토 {len(mentor_records)}명)"
        )

    session.commit()
    print(
        f"\n✅ 2025년 1~4기 데이터 생성 완료 (멘티 {total_mentees}명, 멘토 {total_mentors}명)"
    )


def _reset_cohort(session: Session, cohort_date: date):
    """해당 기수의 기존 TrainingCenter 데이터 삭제"""
    session.exec(
        delete(TrainingCenterRecord).where(
            TrainingCenterRecord.cohort_date == cohort_date
        )
    )
    session.exec(
        delete(TrainingCohort).where(TrainingCohort.cohort_date == cohort_date)
    )
    session.commit()


def _apply_status_adjustments(
    records: List[TrainingCenterRecord],
    status: str,
    service: TrainingCenterService,
    is_mentor: bool = False,
):
    """기수 상태에 맞춰 점수 스케일 조정"""
    if status == "completed":
        min_score, max_score = (84, 97) if is_mentor else (78, 94)
    elif status == "mid_exam":
        min_score, max_score = (76, 92) if is_mentor else (68, 86)
    else:
        min_score, max_score = (72, 90) if is_mentor else (62, 82)

    for record in records:
        adjusted = {}
        for category in service.CATEGORY_KEYS:
            score = service.random.randint(min_score, max_score)
            adjusted[category] = score
            record.question_scores[category] = [
                1 if service.random.random() < score / 100 else 0
                for _ in range(10)
            ]
        record.section_scores = adjusted
        record.total_score = round(
            sum(adjusted.values()) / len(adjusted), 1
        )


if __name__ == "__main__":
    with Session(engine) as session:
        create_large_cohort_data(session)

