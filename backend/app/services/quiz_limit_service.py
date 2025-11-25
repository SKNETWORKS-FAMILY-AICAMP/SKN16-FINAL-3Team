"""
퀴즈 시도 제한 관리 서비스.
"""
from __future__ import annotations

from datetime import datetime
from typing import Dict, Optional

from sqlalchemy import func, text
from sqlmodel import Session, select

from app.models import QuizAttemptLimit, QuizGenerationLog

QuizMode = str

DEFAULT_ATTEMPT_LIMITS: Dict[str, int] = {
    "random": 200,
    "custom": 10,
    "midterm": 1,
    "final": 1,
}


class QuizLimitService:
    """DB 기반 퀴즈 시도 제한을 관리한다."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        """user_id 컬럼 및 유니크 제약을 보장한다."""
        statements = [
            "ALTER TABLE quiz_attempt_limits ADD COLUMN IF NOT EXISTS user_id INTEGER",
            "ALTER TABLE quiz_attempt_limits ADD COLUMN IF NOT EXISTS last_reset_at TIMESTAMP",
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_quiz_attempt_limits_user_id ON quiz_attempt_limits(user_id)",
            "CREATE SEQUENCE IF NOT EXISTS quiz_attempt_limits_id_seq",
            "SELECT setval('quiz_attempt_limits_id_seq', GREATEST((SELECT COALESCE(MAX(id), 1) FROM quiz_attempt_limits), 1))",
            "ALTER TABLE quiz_attempt_limits ALTER COLUMN id SET DEFAULT nextval('quiz_attempt_limits_id_seq')",
        ]
        for stmt in statements:
            try:
                self.session.execute(text(stmt))
            except Exception:
                # 실패해도 테이블이 없거나 이미 생성된 경우라면 무시
                self.session.rollback()
        self.session.commit()

    def _load_global(self) -> QuizAttemptLimit:
        limits = self.session.get(QuizAttemptLimit, 1)
        if limits:
            return limits
        limits = QuizAttemptLimit(
            id=1,
            user_id=None,
            max_random_attempts=DEFAULT_ATTEMPT_LIMITS["random"],
            max_custom_attempts=DEFAULT_ATTEMPT_LIMITS["custom"],
            max_midterm_attempts=DEFAULT_ATTEMPT_LIMITS["midterm"],
            max_final_attempts=DEFAULT_ATTEMPT_LIMITS["final"],
        )
        self.session.add(limits)
        self.session.commit()
        self.session.refresh(limits)
        return limits

    def _load_for_user(self, user_id: Optional[int]) -> Optional[QuizAttemptLimit]:
        if not user_id:
            return None
        return self.session.exec(
            select(QuizAttemptLimit).where(QuizAttemptLimit.user_id == user_id)
        ).first()

    def _load(self, user_id: Optional[int] = None) -> QuizAttemptLimit:
        if user_id:
            override = self._load_for_user(user_id)
            if override:
                return override
        return self._load_global()

    def get_limits(self, user_id: Optional[int] = None) -> Dict[str, int]:
        limits = self._load(user_id)
        return {
            "random": limits.max_random_attempts,
            "custom": limits.max_custom_attempts,
            "midterm": limits.max_midterm_attempts,
            "final": limits.max_final_attempts,
        }

    def get_limit_record(self, user_id: Optional[int] = None) -> QuizAttemptLimit:
        """Full model 액세스가 필요할 때 사용."""
        return self._load(user_id)

    def get_limit_for_mode(self, mode: QuizMode, user_id: Optional[int] = None) -> int:
        limits = self.get_limits(user_id)
        if mode not in limits:
            raise ValueError(f"Unsupported quiz mode: {mode}")
        return limits[mode]

    def update_limits(
        self,
        payload: Dict[str, Optional[int]],
        user_id: Optional[int] = None,
    ) -> QuizAttemptLimit:
        limits = self._load(user_id)

        # 새 override가 필요하면 생성
        if user_id and limits.user_id is None:
            limits = QuizAttemptLimit(
                user_id=user_id,
                max_random_attempts=limits.max_random_attempts,
                max_custom_attempts=limits.max_custom_attempts,
                max_midterm_attempts=limits.max_midterm_attempts,
                max_final_attempts=limits.max_final_attempts,
            )
            self.session.add(limits)
            self.session.commit()
            self.session.refresh(limits)

        for key, value in payload.items():
            if value is None:
                continue
            if value < 0:
                raise ValueError("시도 가능 횟수는 0 이상이어야 합니다.")
            if hasattr(limits, key):
                setattr(limits, key, value)
        limits.touch()
        self.session.add(limits)
        self.session.commit()
        self.session.refresh(limits)
        return limits

    def reset_user_limits(self, user_id: int) -> None:
        """사용자 override 제거"""
        record = self._load_for_user(user_id)
        if record:
            self.session.delete(record)
            self.session.commit()

    def reset_usage(self, user_id: int) -> QuizAttemptLimit:
        """사용자 시도 횟수를 초기화하고 기본값으로 설정"""
        limits = self._load_for_user(user_id)
        if not limits:
            limits = QuizAttemptLimit(
                user_id=user_id,
                max_random_attempts=DEFAULT_ATTEMPT_LIMITS["random"],
                max_custom_attempts=DEFAULT_ATTEMPT_LIMITS["custom"],
                max_midterm_attempts=DEFAULT_ATTEMPT_LIMITS["midterm"],
                max_final_attempts=DEFAULT_ATTEMPT_LIMITS["final"],
            )
        else:
            limits.max_random_attempts = DEFAULT_ATTEMPT_LIMITS["random"]
            limits.max_custom_attempts = DEFAULT_ATTEMPT_LIMITS["custom"]
            limits.max_midterm_attempts = DEFAULT_ATTEMPT_LIMITS["midterm"]
            limits.max_final_attempts = DEFAULT_ATTEMPT_LIMITS["final"]
        limits.last_reset_at = datetime.utcnow()
        limits.touch()
        self.session.add(limits)
        self.session.commit()
        self.session.refresh(limits)
        return limits

    def get_usage(self, user_id: int) -> Dict[str, int]:
        """모드별 생성/응시 횟수 (reset 시점 이후만 계산)"""
        reset_at = None
        override = self._load_for_user(user_id)
        if override and override.last_reset_at:
            reset_at = override.last_reset_at

        statement = select(QuizGenerationLog.mode, func.count(QuizGenerationLog.id)).where(
            QuizGenerationLog.user_id == user_id
        )
        if reset_at:
            statement = statement.where(QuizGenerationLog.created_at >= reset_at)
        statement = statement.group_by(QuizGenerationLog.mode)

        rows = self.session.exec(statement).all()
        usage: Dict[str, int] = {mode: int(count) for mode, count in rows}
        for mode in DEFAULT_ATTEMPT_LIMITS:
            usage.setdefault(mode, 0)
        return usage

    def get_remaining(self, user_id: int) -> Dict[str, int]:
        limits = self.get_limits(user_id)
        usage = self.get_usage(user_id)
        remaining: Dict[str, int] = {}
        for mode, max_attempts in limits.items():
            remaining[mode] = max(0, max_attempts - usage.get(mode, 0))
        return remaining
