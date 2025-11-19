"""
고도화된 시뮬레이션 시스템 모델
STT/LLM/TTS 기반 음성 시뮬레이션 및 고객 페르소나 시스템
"""
from sqlmodel import SQLModel, Field, Relationship, Column
import sqlalchemy as sa
from typing import Optional, List, Dict, Any
from datetime import datetime
import json


class CustomerPersona(SQLModel, table=True):
    """고객 페르소나 설정"""
    __tablename__ = "customer_personas"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=100)
    
    # 기본 정보
    age_group: str = Field(max_length=20)  # 20대, 30대, 40대, 50대, 60대 이상
    occupation: str = Field(max_length=50)  # 학생, 직장인, 자영업자, 은퇴자, 외국인
    financial_literacy: str = Field(max_length=20)  # 낮음, 중간, 높음
    
    # 고객 타입
    customer_type: str = Field(max_length=30)  # 실용형, 보수형, 불만형, 긍정형, 급함형
    
    # 페르소나 특성 (JSON)
    personality_traits: str = Field(sa_column=Column("personality_traits", sa.Text))
    communication_style: str = Field(sa_column=Column("communication_style", sa.Text))
    typical_concerns: str = Field(sa_column=Column("typical_concerns", sa.Text))
    response_patterns: str = Field(sa_column=Column("response_patterns", sa.Text))
    
    # 음성 설정
    voice_characteristics: str = Field(sa_column=Column("voice_characteristics", sa.Text))
    
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class SimulationSituation(SQLModel, table=True):
    """시뮬레이션 상황 설정"""
    __tablename__ = "simulation_situations"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = Field(max_length=200)
    
    # 업무 카테고리
    business_category: str = Field(max_length=50)  # 수신, 여신, 카드, 외환/송금, 인터넷/모바일 뱅킹, 민원/불만 처리
    
    # 상황 설정
    situation_type: str = Field(max_length=50)  # 상담, 문제해결, 민원처리, 상품추천 등
    difficulty_level: str = Field(max_length=20)  # 쉬움, 보통, 어려움
    
    # 상황 상세 정보 (JSON)
    situation_context: str = Field(sa_column=Column("situation_context", sa.Text))
    expected_outcomes: str = Field(sa_column=Column("expected_outcomes", sa.Text))
    evaluation_criteria: str = Field(sa_column=Column("evaluation_criteria", sa.Text))
    
    # 대화 플로우
    conversation_flow: str = Field(sa_column=Column("conversation_flow", sa.Text))
    
    # 예상 고객 반응
    customer_reactions: str = Field(sa_column=Column("customer_reactions", sa.Text))
    
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class VoiceSimulationSession(SQLModel, table=True):
    """음성 시뮬레이션 세션"""
    __tablename__ = "voice_simulation_sessions"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id")
    persona_id: int = Field(foreign_key="customer_personas.id")
    situation_id: int = Field(foreign_key="simulation_situations.id")
    
    # 세션 정보
    session_name: str = Field(max_length=200)
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = Field(default=None)
    duration_seconds: Optional[int] = Field(default=None)
    
    # 음성 설정
    voice_enabled: bool = Field(default=True)
    stt_enabled: bool = Field(default=True)
    tts_enabled: bool = Field(default=True)
    
    # 세션 상태
    status: str = Field(default="in_progress", max_length=20)  # in_progress, completed, abandoned
    
    # 결과
    total_score: float = Field(default=0.0)
    max_score: float = Field(default=100.0)
    grade: str = Field(max_length=10)
    
    # 상세 결과 (JSON)
    detailed_results: str = Field(sa_column=Column("detailed_results", sa.Text))
    feedback: Optional[str] = Field(sa_column=Column("feedback", sa.Text))
    
    # 대화 기록
    conversation_log: str = Field(sa_column=Column("conversation_log", sa.Text))
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # 관계
    persona: Optional[CustomerPersona] = Relationship()
    situation: Optional[SimulationSituation] = Relationship()


class VoiceInteraction(SQLModel, table=True):
    """음성 상호작용 기록"""
    __tablename__ = "voice_interactions"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: int = Field(foreign_key="voice_simulation_sessions.id")
    
    # 상호작용 정보
    interaction_type: str = Field(max_length=20)  # user_speech, customer_speech, system_response
    sequence_number: int
    
    # 음성 데이터
    audio_file_path: Optional[str] = Field(max_length=500)
    audio_duration: Optional[float] = Field(default=None)
    
    # 텍스트 변환
    transcribed_text: Optional[str] = Field(sa_column=Column("transcribed_text", sa.Text))
    
    # AI 응답
    ai_response_text: Optional[str] = Field(sa_column=Column("ai_response_text", sa.Text))
    ai_response_audio: Optional[str] = Field(max_length=500)
    
    # 평가 결과
    is_correct: Optional[bool] = Field(default=None)
    score: float = Field(default=0.0)
    max_score: float = Field(default=0.0)
    
    # 피드백
    feedback: Optional[str] = Field(sa_column=Column("feedback", sa.Text))
    improvement_suggestions: Optional[str] = Field(sa_column=Column("improvement_suggestions", sa.Text))
    
    created_at: datetime = Field(default_factory=datetime.utcnow)


class SimulationAnalytics(SQLModel, table=True):
    """시뮬레이션 분석 데이터"""
    __tablename__ = "simulation_analytics"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id")
    
    # 분석 기간
    analysis_period: str = Field(max_length=20)  # daily, weekly, monthly
    analysis_date: datetime = Field(default_factory=datetime.utcnow)
    
    # 성과 지표
    total_sessions: int = Field(default=0)
    completed_sessions: int = Field(default=0)
    average_score: float = Field(default=0.0)
    improvement_rate: float = Field(default=0.0)
    
    # 카테고리별 성과
    category_performance: str = Field(sa_column=Column("category_performance", sa.Text))
    
    # 약점 분석
    weak_areas: str = Field(sa_column=Column("weak_areas", sa.Text))
    strong_areas: str = Field(sa_column=Column("strong_areas", sa.Text))
    
    # 학습 추천
    recommended_learning: str = Field(sa_column=Column("recommended_learning", sa.Text))
    
    # 음성 분석
    voice_analysis: str = Field(sa_column=Column("voice_analysis", sa.Text))
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # 관계
    user: Optional["User"] = Relationship()
