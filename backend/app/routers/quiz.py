from __future__ import annotations

from typing import Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlmodel import Session, select

from app.database import get_session
from app.models import QuizGenerationLog, User
from app.utils.auth import get_current_user
from create_quiz import QuizBuilder, QuizDataSource, UserQuizProfile

router = APIRouter(prefix="/quiz", tags=["Quiz"])

MAX_CUSTOM_ATTEMPTS = 5
_quiz_data_source = QuizDataSource()
_quiz_builder = QuizBuilder(_quiz_data_source)


class QuizProfilePayload(BaseModel):
    wrong_question_ids: List[int] = Field(default_factory=list)
    recent_category_scores: Dict[str, float] = Field(default_factory=dict)
    cumulative_category_scores: Dict[str, float] = Field(default_factory=dict)


class QuizGenerationRequest(BaseModel):
    mode: Literal["random", "custom"] = "random"
    total_questions: int = Field(gt=0, le=120)
    seed: Optional[int] = None
    profile: Optional[QuizProfilePayload] = None


@router.post("/generate")
def generate_quiz_set(
    request: QuizGenerationRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    if request.mode == "custom":
        if not request.profile:
            raise HTTPException(
                status_code=400,
                detail="맞춤형 세트를 생성하려면 사용자 프로필 정보가 필요합니다.",
            )

        used_attempts = _get_custom_attempt_count(current_user.id, session)
        if used_attempts >= MAX_CUSTOM_ATTEMPTS:
            raise HTTPException(
                status_code=403,
                detail="맞춤형 세트 생성 가능 횟수를 모두 사용했습니다.",
            )

        profile = UserQuizProfile(
            wrong_question_ids=request.profile.wrong_question_ids,
            recent_category_scores=request.profile.recent_category_scores,
            cumulative_category_scores=request.profile.cumulative_category_scores,
        )
        payload = _quiz_builder.generate_custom_quiz(
            request.total_questions,
            profile,
            seed=request.seed,
        )
        used_attempts += 1
    else:
        payload = _quiz_builder.generate_random_quiz(
            request.total_questions,
            seed=request.seed,
        )
        used_attempts = _get_custom_attempt_count(current_user.id, session)

    log = QuizGenerationLog(
        user_id=current_user.id,
        mode=request.mode,
        total_questions=payload["exam_info"]["total_questions"],
        metadata={
            "seed": request.seed,
            "category_summary": payload.get("category_summary", {}),
        },
    )
    session.add(log)
    session.commit()
    session.refresh(log)

    payload["generation_id"] = log.id
    payload["remaining_custom_attempts"] = max(0, MAX_CUSTOM_ATTEMPTS - used_attempts)
    return payload


def _get_custom_attempt_count(user_id: int, session: Session) -> int:
    statement = select(func.count(QuizGenerationLog.id)).where(
        QuizGenerationLog.user_id == user_id,
        QuizGenerationLog.mode == "custom",
    )
    result = session.exec(statement).one_or_none()
    return int(result or 0)
