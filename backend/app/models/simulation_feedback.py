"""
시뮬레이션 피드백 데이터 모델
6가지 역량 평가 기반
"""
from sqlmodel import SQLModel, Field, Column
from sqlalchemy import Text
from typing import Optional
from datetime import datetime


class SimulationFeedback(SQLModel, table=True):
    """시뮬레이션 피드백 (6가지 역량 평가)"""
    __tablename__ = "simulation_feedbacks"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    
    # 시뮬레이션 정보
    session_key: Optional[str] = Field(default=None, index=True)
    persona_id: Optional[str] = None
    situation_id: Optional[str] = None
    persona_info: Optional[str] = Field(default=None, max_length=200)  # "나이대 성별 직업" 형식으로 저장
    situation_info: Optional[str] = Field(default=None, max_length=100)  # "여신", "수신", "카드" 등 카테고리만 저장
    
    # 종합 점수
    overall_score: float = Field(default=0.0, ge=0.0, le=100.0)
    grade: str = Field(default="C")  # A, B, C, D, F
    performance_level: str = Field(default="양호한 성과")
    
    # 6가지 역량 점수 (각 0-100)
    knowledge_score: int = Field(default=0, ge=0, le=100)
    skill_score: int = Field(default=0, ge=0, le=100)
    empathy_score: int = Field(default=0, ge=0, le=100)
    clarity_score: int = Field(default=0, ge=0, le=100)
    kindness_score: int = Field(default=0, ge=0, le=100)
    confidence_score: int = Field(default=0, ge=0, le=100)
    
    # 상세 피드백
    knowledge_feedback: Optional[str] = Field(default=None, sa_column=Column(Text))
    skill_feedback: Optional[str] = Field(default=None, sa_column=Column(Text))
    empathy_feedback: Optional[str] = Field(default=None, sa_column=Column(Text))
    clarity_feedback: Optional[str] = Field(default=None, sa_column=Column(Text))
    kindness_feedback: Optional[str] = Field(default=None, sa_column=Column(Text))
    confidence_feedback: Optional[str] = Field(default=None, sa_column=Column(Text))
    
    # 종합 평가
    summary: Optional[str] = Field(default=None, sa_column=Column(Text))
    improvements: Optional[str] = Field(default=None, sa_column=Column(Text))
    
    # 메타 정보
    total_turns: Optional[int] = None  # 총 대화 턴 수
    duration_seconds: Optional[int] = None  # 세션 지속 시간 (초)
    conversation_log: Optional[str] = Field(default=None, sa_column=Column(Text))  # 대화 로그 (JSON)
    goal_achievement_data: Optional[str] = Field(default=None, sa_column=Column(Text))  # 목표 달성 정보 (JSON)
    is_test_mode: bool = Field(default=False, index=True)  # 테스트 모드 여부
    
    # 🧪 테스트 모드: RAG 평가 결과 (JSON)
    rag_evaluations: Optional[str] = Field(default=None, sa_column=Column(Text))  # RAG 평가 결과 배열 (JSON)
    rag_summary: Optional[str] = Field(default=None, sa_column=Column(Text))  # RAG 평가 종합 결과 (JSON)
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        indexes = [
            ("user_id", "created_at"),  # 사용자별 최신순 조회
        ]

