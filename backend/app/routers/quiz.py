from __future__ import annotations

import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlmodel import Session, select

from app.config import settings
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


class QuizSubmissionRequest(BaseModel):
    generation_id: int
    answers: Dict[int, str]


class QuizSubmissionResponse(BaseModel):
    score: float
    correct_count: int
    total_questions: int
    details: List[Dict[str, Literal[True, False]]]


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
                detail="맞춤 세트를 생성하려면 사용자 프로필 정보가 필요합니다.",
            )

        used_attempts = _get_custom_attempt_count(current_user.id, session)
        if used_attempts >= MAX_CUSTOM_ATTEMPTS:
            raise HTTPException(
                status_code=403,
                detail="맞춤 세트 생성 가능 횟수를 모두 사용했습니다.",
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
        questions=payload["questions"],
        extra={
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


@router.post("/submit", response_model=QuizSubmissionResponse)
def submit_quiz(
    request: QuizSubmissionRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    log = session.get(QuizGenerationLog, request.generation_id)
    if not log or log.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="생성된 퀴즈를 찾을 수 없습니다.")
    if not log.questions:
        raise HTTPException(status_code=400, detail="퀴즈 정보가 유효하지 않습니다.")

    question_map = {int(item["q_id"]): item for item in log.questions}
    correct = 0
    details: List[Dict[str, Literal[True, False]]] = []
    for q_id, question in question_map.items():
        user_answer = request.answers.get(q_id)
        is_correct = bool(user_answer) and user_answer == question.get("answer")
        if is_correct:
            correct += 1
        details.append({"q_id": q_id, "correct": is_correct})

    total = len(question_map)
    score = round((correct / total) * 100, 2) if total else 0.0

    log.answers = {str(k): v for k, v in request.answers.items()}
    log.score = score
    log.submitted_at = log.submitted_at or datetime.utcnow()
    session.add(log)
    session.commit()

    return QuizSubmissionResponse(
        score=score,
        correct_count=correct,
        total_questions=total,
        details=details,
    )


def _get_custom_attempt_count(user_id: int, session: Session) -> int:
    statement = select(func.count(QuizGenerationLog.id)).where(
        QuizGenerationLog.user_id == user_id,
        QuizGenerationLog.mode == "custom",
    )
    result = session.exec(statement).one_or_none()
    return int(result or 0)


def _content_disposition(name: str) -> str:
    ascii_fallback = name.encode("ascii", "ignore").decode("ascii") or "file"
    utf8_name = urllib.parse.quote(name)
    return f"inline; filename=\"{ascii_fallback}\"; filename*=UTF-8''{utf8_name}"


@router.get("/source-file")
def get_source_file(
    file_name: str,
):
    """
    Locate a source file by name under allowed roots and stream it inline.
    Falls back to 404 instead of surfacing a 500.
    """
    safe_name = Path(file_name).name

    search_roots = [
        Path(settings.UPLOAD_DIR),
        Path("/app/data/rag_sources/uploads"),
    ]

    target: Optional[Path] = None
    for root in search_roots:
        if not root.exists():
            continue
        for candidate in root.rglob("*"):
            if candidate.is_file() and candidate.name == safe_name:
                target = candidate
                break
        if target:
            break

    if not target:
        raise HTTPException(status_code=404, detail="본문 파일을 찾을 수 없습니다.")

    ext = target.suffix.lower()
    if ext == ".pdf":
        media_type = "application/pdf"
    elif ext == ".jsonl":
        media_type = "text/plain"
    else:
        media_type = "application/octet-stream"

    try:
        return FileResponse(
            path=target,
            filename=target.name,
            media_type=media_type,
            headers={"Content-Disposition": _content_disposition(target.name)},
        )
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"파일 제공 중 오류: {exc}") from exc
