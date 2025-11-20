"""
연수원(Training Center) 데이터 모델
"""
from datetime import date, datetime
from typing import Dict, List, Optional

from sqlalchemy import Column, JSON, String, UniqueConstraint
from sqlmodel import Field, SQLModel


class TrainingCohort(SQLModel, table=True):
    """연수원 기수 메타데이터"""

    __tablename__ = "training_cohorts"
    __table_args__ = (UniqueConstraint("cohort_date", name="uq_training_cohort_date"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    label: str = Field(index=True)
    cohort_date: date = Field(index=True)
    cohort_index: int = Field(index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class TrainingCenterRecord(SQLModel, table=True):
    """연수원에서 전달된 연수생 점수/인적 정보"""

    __tablename__ = "training_center_records"
    __table_args__ = (
        UniqueConstraint("cohort_id", "cohort_slot", name="uq_training_cohort_slot"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    cohort_id: int = Field(foreign_key="training_cohorts.id")
    cohort_slot: int
    cohort_date: date = Field(index=True)
    cohort_label: str = Field(index=True)
    employee_type: str = Field(index=True, description="mentee | mentor")

    name: str = Field(index=True)
    employee_number: str = Field(sa_column=Column(String(20), unique=True, index=True))
    join_year: int
    mbti: str
    position: str
    department: str
    team: str
    city: str = Field(index=True)
    hobbies: List[str] = Field(default_factory=list, sa_column=Column(JSON))

    birth: date
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None

    section_scores: Dict[str, int] = Field(sa_column=Column(JSON))
    question_scores: Dict[str, List[int]] = Field(sa_column=Column(JSON))
    total_score: int

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


