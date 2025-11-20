from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


class QuizGenerationLog(SQLModel, table=True):
    """사용자별 퀴즈 생성 기록."""

    __tablename__ = "quiz_generation_logs"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id")
    mode: str = Field(index=True)
    total_questions: int
    questions: List[Dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    extra: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    answers: Optional[Dict[str, str]] = Field(default=None, sa_column=Column(JSON))
    score: Optional[float] = None
    submitted_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
