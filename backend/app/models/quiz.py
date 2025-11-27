from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Literal

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


QuizModeLiteral = Literal["random", "custom", "midterm", "final", "pre"]


class QuizGenerationLog(SQLModel, table=True):
    """사용자별 퀴즈 생성 기록."""

    __tablename__ = "quiz_generation_logs"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id")
    mode: QuizModeLiteral = Field(index=True)
    total_questions: int
    questions: List[Dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    extra: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    answers: Optional[Dict[str, str]] = Field(default=None, sa_column=Column(JSON))
    score: Optional[float] = None
    submitted_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    def record_submission(self, *, answers: Dict[str, str], score: float, submitted_at: Optional[datetime] = None) -> None:
        """Update answers/score/submission timestamp in a single call."""
        self.answers = answers
        self.score = score
        self.submitted_at = submitted_at or datetime.utcnow()


class QuizAttemptLimit(SQLModel, table=True):
    """
    퀴즈 모드별 시도 가능 횟수 설정.

    단일 레코드(id=1)로 관리하며 관리자가 값을 수정할 수 있다.
    user_id가 설정되면 해당 사용자에 대한 override를 의미한다.
    """

    __tablename__ = "quiz_attempt_limits"

    # 글로벌 기본 레코드는 id=1을 사용하고, 사용자별 override는 autoincrement 사용
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(default=None, foreign_key="users.id", index=True)
    max_random_attempts: int = Field(default=6, description="랜덤 세트 허용 횟수")
    max_custom_attempts: int = Field(default=6, description="맞춤형 세트 허용 횟수")
    max_midterm_attempts: int = Field(default=6, description="중간 평가 허용 횟수")
    max_final_attempts: int = Field(default=6, description="최종 평가 허용 횟수")
    last_reset_at: Optional[datetime] = Field(default=None, description="사용자별 시도 횟수 초기화 기준 시각")
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def touch(self) -> None:
        """설정 갱신 시점을 업데이트한다."""
        self.updated_at = datetime.utcnow()

    @property
    def is_user_override(self) -> bool:
        """Return True if this row is a per-user override record."""
        return self.user_id is not None
