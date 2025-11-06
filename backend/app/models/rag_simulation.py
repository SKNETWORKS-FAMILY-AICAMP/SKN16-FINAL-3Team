"""
RAG 시뮬레이션 관련 데이터 모델
대화 기록 및 평가 결과 저장용
"""
from sqlmodel import SQLModel, Field, Column
from sqlalchemy import Text, UniqueConstraint
from typing import Optional
from datetime import datetime


class RAGSimulationSession(SQLModel, table=True):
    """RAG 시뮬레이션 세션 정보"""
    __tablename__ = "rag_simulation_sessions"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    session_key: str = Field(index=True)  # "session_{userId}_{timestamp}"
    user_id: int = Field(foreign_key="users.id", index=True)
    
    # 시뮬레이션 정보
    persona_id: str  # 선택된 페르소나 ID
    scenario_id: str  # 선택된 시나리오 ID
    persona_name: Optional[str] = None  # 페르소나 이름 (캐시용)
    scenario_title: Optional[str] = None  # 시나리오 제목 (캐시용)
    
    # 세션 상태
    started_at: datetime = Field(default_factory=datetime.utcnow)
    ended_at: Optional[datetime] = None
    is_completed: bool = Field(default=False)
    
    # 통계
    total_turns: int = Field(default=0)  # 총 대화 턴 수
    duration_seconds: Optional[int] = None  # 세션 지속 시간(초)
    
    class Config:
        table_args = (
            UniqueConstraint("session_key", name="uq_rag_sim_session_key"),
        )


class RAGSimulationTurn(SQLModel, table=True):
    """RAG 시뮬레이션 대화 턴"""
    __tablename__ = "rag_simulation_turns"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: int = Field(foreign_key="rag_simulation_sessions.id", index=True)
    
    # 턴 정보
    turn_index: int  # 0, 1, 2, ...
    role: str  # "teller" (직원) 또는 "customer" (고객)
    text: str = Field(sa_column=Column(Text))  # 발화 내용
    
    # 음성 특성 (teller 발화만 수집)
    voice_speed: Optional[float] = None  # 말하기 속도 (0.0 ~ 2.0)
    tone_score: Optional[float] = None  # 톤 점수 (0.0 ~ 1.0)
    
    # 타임스탬프
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        indexes = [
            ("session_id", "turn_index"),  # 복합 인덱스
        ]


class RAGSimulationEvaluation(SQLModel, table=True):
    """RAG 시뮬레이션 평가 결과"""
    __tablename__ = "rag_simulation_evaluations"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: int = Field(foreign_key="rag_simulation_sessions.id", index=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    
    # 점 points
    knowledge_point: int = Field(default=0, ge=0, le=40)  # 지식 점수
    skill_point: int = Field(default=0, ge=0, le=30)  # 기술 점수
    attitude_point: int = Field(default=0, ge=0, le=30)  # 태도 점수
    total_point: int = Field(default=0, ge=0, le=100)  # 총점
    
    # 상세 피드백 (JSON 문자열로 저장)
    strengths: Optional[str] = Field(default=None, sa_column=Column(Text))  # 강점 리스트
    improvements: Optional[str] = Field(default=None, sa_column=Column(Text))  # 개선점 리스트
    recommended_training: Optional[str] = Field(default=None, sa_column=Column(Text))  # 추천 학습
    
    # 원본 JSON 결과 (디버깅용)
    raw_json: Optional[str] = Field(default=None, sa_column=Column(Text))
    
    created_at: datetime = Field(default_factory=datetime.utcnow)

