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
    
    # 페르소나 및 상황 정보 (JSON 형식)
    persona_info: Optional[str] = Field(default=None, sa_column=Column(Text))  # 페르소나 전체 정보 (JSON)
    situation_info: Optional[str] = Field(default=None, sa_column=Column(Text))  # 상황 전체 정보 (JSON - goals 포함)
    
    # 목표 및 달성 정보
    goal_achievement_data: Optional[str] = Field(default=None, sa_column=Column(Text))  # 목표 달성 데이터 (JSON - achieved_indices, achievement_times 포함)
    achieved_goals: Optional[str] = Field(default=None, sa_column=Column(Text))  # 달성된 목표 (deprecated - goal_achievement_data 사용)
    
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
    speaker_role: str  # "employee" (직원) 또는 "customer" (고객)
    speaker_text: str = Field(sa_column=Column(Text))  # 발화 내용
    
    # 하위 호환성을 위한 별칭 (deprecated)
    @property
    def role(self) -> str:
        return self.speaker_role
    
    @property
    def text(self) -> str:
        return self.speaker_text
    
    # 음성 특성 (employee 발화만 수집)
    voice_speed: Optional[float] = None  # 말하기 속도 (0.0 ~ 2.0)
    tone_score: Optional[float] = None  # 톤 점수 (0.0 ~ 1.0)
    
    # 타임스탬프
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        indexes = [
            ("session_id", "turn_index"),  # 복합 인덱스
        ]


class RAGSimulationEvaluation(SQLModel, table=True):
    """RAG 시뮬레이션 평가 결과 - 6가지 지표 기반"""
    __tablename__ = "rag_simulation_evaluations"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: int = Field(foreign_key="rag_simulation_sessions.id", index=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    
    # 6가지 세부 지표 점수 (각 0-100점)
    knowledge_point: int = Field(default=0, ge=0, le=100)  # 지식 (상품 설명 정확성) - 가중치 20%
    skill_point: int = Field(default=0, ge=0, le=100)  # 기술 (응대 절차 및 목표 달성) - 가중치 20%
    empathy_point: int = Field(default=0, ge=0, le=100)  # 공감도 - 가중치 15%
    clarity_point: int = Field(default=0, ge=0, le=100)  # 명확성 - 가중치 15%
    kindness_point: int = Field(default=0, ge=0, le=100)  # 친절도 - 가중치 15%
    confidence_point: int = Field(default=0, ge=0, le=100)  # 자신감 - 가중치 15%
    
    # 총점 및 등급
    total_point: int = Field(default=0, ge=0, le=100)  # 총점 (가중 평균)
    grade: Optional[str] = None  # 등급 (A+, A, B+, B, C+, C, D)
    
    # 각 지표별 상세 이유
    knowledge_reason: Optional[str] = Field(default=None, sa_column=Column(Text))
    skill_reason: Optional[str] = Field(default=None, sa_column=Column(Text))
    empathy_reason: Optional[str] = Field(default=None, sa_column=Column(Text))
    clarity_reason: Optional[str] = Field(default=None, sa_column=Column(Text))
    kindness_reason: Optional[str] = Field(default=None, sa_column=Column(Text))
    confidence_reason: Optional[str] = Field(default=None, sa_column=Column(Text))
    
    # 종합 피드백
    feedback_summary: Optional[str] = Field(default=None, sa_column=Column(Text))  # 피드백 요약
    
    # 세부 정보 JSON (각 지표별 details)
    detail_json: Optional[str] = Field(default=None, sa_column=Column(Text))
    
    # 타임스탬프
    created_at: datetime = Field(default_factory=datetime.utcnow)

