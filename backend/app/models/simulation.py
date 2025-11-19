"""
시뮬레이션 관련 데이터 모델
"""
from sqlmodel import SQLModel, Field, Relationship, Column
import sqlalchemy as sa
from typing import Optional, List, Dict, Any
from datetime import datetime
import json


class SimulationScenario(SQLModel, table=True):
    """시뮬레이션 시나리오"""
    __tablename__ = "simulation_scenarios"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = Field(max_length=200)
    description: str = Field(sa_column=Column("description", sa.Text))
    category: str = Field(max_length=50)  # 고객상담, 업무처리, 응급상황 등
    difficulty: str = Field(max_length=20)  # 초급, 중급, 고급
    estimated_duration: int = Field(default=0)  # 예상 소요 시간(분)
    
    # 시나리오 데이터 (JSON 형태로 저장)
    scenario_data: str = Field(sa_column=Column("scenario_data", sa.Text))  # 시나리오 상세 내용
    evaluation_criteria: str = Field(sa_column=Column("evaluation_criteria", sa.Text))  # 평가 기준
    
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # 관계
    attempts: List["SimulationAttempt"] = Relationship(back_populates="scenario")


class SimulationAttempt(SQLModel, table=True):
    """시뮬레이션 시도 기록"""
    __tablename__ = "simulation_attempts"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id")
    scenario_id: int = Field(foreign_key="simulation_scenarios.id")
    
    # 시도 정보
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = Field(default=None)
    duration_minutes: Optional[int] = Field(default=None)
    
    # 결과 정보
    total_score: float = Field(default=0.0)
    max_score: float = Field(default=100.0)
    grade: str = Field(max_length=10)
    
    # 상세 결과 (JSON 형태)
    detailed_results: str = Field(sa_column=Column("detailed_results", sa.Text))
    feedback: Optional[str] = Field(sa_column=Column("feedback", sa.Text))
    
    # 상태
    status: str = Field(default="in_progress", max_length=20)  # in_progress, completed, abandoned
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # 관계
    scenario: Optional[SimulationScenario] = Relationship(back_populates="attempts")
    user: Optional["User"] = Relationship()


class SimulationStep(SQLModel, table=True):
    """시뮬레이션 단계별 기록"""
    __tablename__ = "simulation_steps"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    attempt_id: int = Field(foreign_key="simulation_attempts.id")
    
    step_number: int
    step_type: str = Field(max_length=50)  # question, action, decision, feedback
    step_content: str = Field(sa_column=Column("step_content", sa.Text))
    
    # 사용자 응답/행동
    user_response: Optional[str] = Field(sa_column=Column("user_response", sa.Text))
    user_action: Optional[str] = Field(max_length=100)
    
    # 평가 결과
    is_correct: Optional[bool] = Field(default=None)
    score: float = Field(default=0.0)
    max_score: float = Field(default=0.0)
    
    # 피드백
    feedback: Optional[str] = Field(sa_column=Column("feedback", sa.Text))
    tips: Optional[str] = Field(sa_column=Column("tips", sa.Text))
    
    created_at: datetime = Field(default_factory=datetime.utcnow)


class SimulationProgress(SQLModel, table=True):
    """사용자별 시뮬레이션 진행 상황"""
    __tablename__ = "simulation_progress"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id")
    
    # 진행 상황
    completed_scenarios: str = Field(default="[]")  # JSON 배열
    total_attempts: int = Field(default=0)
    total_score: float = Field(default=0.0)
    average_score: float = Field(default=0.0)
    
    # 카테고리별 성과
    category_scores: str = Field(default="{}")  # JSON 객체
    
    # 학습 추천
    recommended_scenarios: str = Field(default="[]")  # JSON 배열
    weak_areas: str = Field(default="[]")  # JSON 배열
    strong_areas: str = Field(default="[]")  # JSON 배열
    
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # 관계
    user: Optional["User"] = Relationship()
