"""
멘토-멘티 매칭 모델
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import Column, JSON, Text
from sqlmodel import Field, SQLModel


class MatchingResult(SQLModel, table=True):
    """매칭 결과 저장"""

    __tablename__ = "matching_results"

    id: Optional[int] = Field(default=None, primary_key=True)
    mentee_id: int = Field(foreign_key="training_center_records.id", index=True)
    mentor_id: int = Field(foreign_key="training_center_records.id", index=True)
    
    # 매칭 점수
    total_score: float = Field(description="전체 매칭 점수")
    team_score: float = Field(description="팀 매칭 점수")
    city_score: float = Field(description="거주지 매칭 점수")
    hobby_score: float = Field(description="취미 매칭 점수")
    weakness_strength_score: float = Field(default=0.0, description="약점-강점 매칭 점수")
    career_score: float = Field(default=0.0, description="커리어 경로 매칭 점수")
    major_score: float = Field(default=0.0, description="전공 매칭 점수")
    
    # 매칭 상세 정보
    matching_details: Dict[str, Any] = Field(
        default_factory=dict, sa_column=Column(JSON), description="매칭 상세 정보"
    )
    
    # 매칭 메타데이터
    matched_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    is_active: bool = Field(default=True, index=True)
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class MatchingReport(SQLModel, table=True):
    """매칭 리포트"""

    __tablename__ = "matching_reports"

    id: Optional[int] = Field(default=None, primary_key=True)
    report_name: str = Field(index=True)
    report_date: datetime = Field(default_factory=datetime.utcnow, index=True)
    
    # 전체 통계
    total_mentees: int
    total_mentors: int
    total_matched: int
    
    # 전체 매칭 점수
    overall_score: float = Field(description="전체 평균 매칭 점수")
    
    # 팀별 통계
    team_statistics: Dict[str, Any] = Field(
        default_factory=dict, sa_column=Column(JSON), description="팀별 매칭 통계"
    )
    
    # 리포트 상세 정보
    report_data: Dict[str, Any] = Field(
        default_factory=dict, sa_column=Column(JSON), description="리포트 상세 데이터"
    )
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

