from __future__ import annotations

import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlmodel import Session, select

from app.config import settings
from app.database import get_session
from app.models import QuizGenerationLog, User
from app.services.quiz_limit_service import QuizLimitService
from app.utils.auth import get_current_user
from create_quiz import QuizBuilder, QuizDataSource, UserQuizProfile

router = APIRouter(prefix="/quiz", tags=["Quiz"])

QuizMode = Literal["random", "custom", "midterm", "final", "pre"]
_quiz_data_source: Optional[QuizDataSource] = None
_quiz_builder: Optional[QuizBuilder] = None


def get_quiz_builder() -> QuizBuilder:
    global _quiz_builder, _quiz_data_source
    if _quiz_builder is None:
        _quiz_data_source = QuizDataSource()
        _quiz_builder = QuizBuilder(_quiz_data_source)
    return _quiz_builder


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


class AggregateCategoryStat(BaseModel):
  category: str
  correct: int
  total: int
  accuracy: float


class AggregateStatsResponse(BaseModel):
  total_logs: int
  categories: List[AggregateCategoryStat]

class QuestionStat(BaseModel):
    question_id: int
    category: str
    correct: int
    total: int
    accuracy: float


class StaticQuizSubmissionRequest(BaseModel):
    mode: Literal["midterm", "final"]
    total_questions: int
    score: float
    answers: Dict[int, str]
    questions: List[Dict[str, Any]]
    generation_id: Optional[int] = None


_LIMIT_ERROR_MESSAGES: Dict[QuizMode, str] = {
    "random": "랜덤 세트 생성 가능 횟수를 모두 사용했습니다.",
    "custom": "맞춤 세트 생성 가능 횟수를 모두 사용했습니다.",
    "midterm": "중간 평가 응시 가능 횟수를 모두 사용했습니다.",
    "final": "최종 평가 응시 가능 횟수를 모두 사용했습니다.",
}


class RemainingAttemptsResponse(BaseModel):
    remaining: Dict[str, int]
    generation_id: Optional[int] = None


class QuizHistoryItem(BaseModel):
    id: int
    mode: QuizMode
    score: float
    total_questions: int
    created_at: datetime
    questions: Optional[List[Dict[str, Any]]] = None
    answers: Optional[Dict[str, str]] = None
    category_stats: Optional[Dict[str, Dict[str, int]]] = None


@router.post("/generate")
def generate_quiz_set(
    request: QuizGenerationRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    limit_service = QuizLimitService(session)
    usage = limit_service.get_usage(current_user.id)
    max_attempts = limit_service.get_limit_for_mode(request.mode, user_id=current_user.id)
    used_attempts = usage.get(request.mode, 0)
    if used_attempts >= max_attempts:
        raise HTTPException(
            status_code=403,
            detail=_get_limit_error_message(request.mode),
        )

    if request.mode == "custom":
        if not request.profile:
            raise HTTPException(
                status_code=400,
                detail="맞춤 세트를 생성하려면 사용자 프로필 정보가 필요합니다.",
            )

        profile = UserQuizProfile(
            wrong_question_ids=request.profile.wrong_question_ids,
            recent_category_scores=request.profile.recent_category_scores,
            cumulative_category_scores=request.profile.cumulative_category_scores,
        )
        builder = get_quiz_builder()
        payload = builder.generate_custom_quiz(
            request.total_questions,
            profile,
            seed=request.seed,
        )
    else:
        builder = get_quiz_builder()
        payload = builder.generate_random_quiz(
            request.total_questions,
            seed=request.seed,
        )

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
    remaining = limit_service.get_remaining(current_user.id)
    payload["remaining_attempts"] = remaining
    payload["remaining_custom_attempts"] = remaining.get("custom", 0)
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


@router.post("/submit-static", response_model=QuizSubmissionResponse)
def submit_static_quiz(
    request: StaticQuizSubmissionRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    limit_service = QuizLimitService(session)
    usage = limit_service.get_usage(current_user.id)
    max_attempts = limit_service.get_limit_for_mode(request.mode, user_id=current_user.id)
    used_attempts = usage.get(request.mode, 0)
    log: Optional[QuizGenerationLog] = None
    if request.generation_id:
        log = session.get(QuizGenerationLog, request.generation_id)
        if not log or log.user_id != current_user.id or log.mode != request.mode:
            raise HTTPException(status_code=404, detail="생성된 퀴즈를 찾을 수 없습니다.")
    else:
        if used_attempts >= max_attempts:
            raise HTTPException(status_code=403, detail=_get_limit_error_message(request.mode))

    correct = 0
    details: List[Dict[str, Literal[True, False]]] = []
    question_map = {int(q.get("q_id") or q.get("question_id") or q.get("qid", idx + 1)): q for idx, q in enumerate(request.questions)}

    for qid, question in question_map.items():
        user_answer = request.answers.get(qid) or request.answers.get(str(qid))
        is_correct = bool(user_answer) and _normalize_answer(user_answer) == _normalize_answer(
            question.get("answer")
        )
        if is_correct:
            correct += 1
        details.append({"q_id": qid, "correct": is_correct})

    score = round((correct / request.total_questions) * 100, 2) if request.total_questions else 0.0

    if log:
        log.questions = request.questions
        log.answers = {str(k): v for k, v in request.answers.items()}
        log.score = score
        log.submitted_at = datetime.utcnow()
        log.extra = (log.extra or {}) | {"source": "static"}
        session.add(log)
    else:
        log = QuizGenerationLog(
            user_id=current_user.id,
            mode=request.mode,
            total_questions=request.total_questions,
            questions=request.questions,
            answers={str(k): v for k, v in request.answers.items()},
            score=score,
            submitted_at=datetime.utcnow(),
            extra={"source": "static"},
        )
        session.add(log)
    session.commit()

    return QuizSubmissionResponse(
        score=score,
        correct_count=correct,
        total_questions=request.total_questions,
        details=details,
    )


def _normalize_answer(value: Optional[str]) -> str:
    if not value:
        return ""
    digits = "".join(ch for ch in value if ch.isdigit())
    if digits:
        return digits
    return str(value).strip().lower().replace(" ", "")


@router.get("/my-history", response_model=List[QuizHistoryItem])
def get_my_quiz_history(
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """
    현재 사용자 퀴즈 제출 이력 (score가 있는 로그만)
    """
    logs = session.exec(
        select(QuizGenerationLog)
        .where(
            QuizGenerationLog.user_id == current_user.id,
            QuizGenerationLog.score.is_not(None),
        )
        .order_by(func.coalesce(QuizGenerationLog.submitted_at, QuizGenerationLog.created_at).desc())
        .limit(limit)
    ).all()

    CATEGORY_KEYS = [
        "금융영업",
        "상품개발 및 운용",
        "신용분석 및 리스크관리",
        "외환",
        "은행지식 및 관련법률",
        "하경은행",
    ]

    def _norm(val: Optional[str]) -> str:
        if not val:
            return ""
        digits = "".join(ch for ch in str(val) if ch.isdigit())
        return digits or str(val).replace(" ", "").lower()

    items: List[QuizHistoryItem] = []
    for log in logs:
        category_stats: Dict[str, Dict[str, int]] = {k: {"correct": 0, "total": 0} for k in CATEGORY_KEYS}
        answers = log.answers or {}
        questions = log.questions or []
        for q in questions:
            cat = q.get("category_name") or q.get("category") or "기타"
            qid = q.get("q_id") or q.get("question_id") or q.get("qid")
            if qid is None:
                continue
            key = str(qid)
            if cat not in category_stats:
                category_stats[cat] = {"correct": 0, "total": 0}
            category_stats[cat]["total"] += 1
            user_answer = answers.get(key) or answers.get(qid)
            if user_answer and _norm(user_answer) == _norm(q.get("answer")):
                category_stats[cat]["correct"] += 1

        items.append(
            QuizHistoryItem(
                id=log.id,
                mode=log.mode,  # type: ignore
                score=log.score or 0.0,
                total_questions=log.total_questions,
                created_at=log.submitted_at or log.created_at,
                questions=log.questions,
                answers=log.answers,
                category_stats=category_stats or None,
            )
        )

    return items


@router.get("/aggregate-stats", response_model=AggregateStatsResponse)
def aggregate_stats(session: Session = Depends(get_session)) -> AggregateStatsResponse:
    """
    Calculate aggregate category-level accuracy across all submitted quiz logs.
    """
    logs = session.exec(
        select(QuizGenerationLog).where(QuizGenerationLog.answers.is_not(None))
    ).all()

    category_totals: Dict[str, Dict[str, int]] = {}

    for log in logs:
        answers = log.answers or {}
        questions = log.questions or []
        for q in questions:
            cat = q.get("category_name") or "기타"
            qid = q.get("q_id") or q.get("qid") or q.get("question_id")
            if qid is None:
                continue
            key = str(qid)
            if cat not in category_totals:
                category_totals[cat] = {"correct": 0, "total": 0}
            category_totals[cat]["total"] += 1

            user_answer = answers.get(key) or answers.get(int(key)) if isinstance(answers, dict) else None
            is_correct = bool(user_answer) and _normalize_answer(user_answer) == _normalize_answer(
                q.get("answer")
            )
            if is_correct:
                category_totals[cat]["correct"] += 1

    categories: List[AggregateCategoryStat] = []
    for cat, stats in category_totals.items():
        total = stats["total"]
        correct = stats["correct"]
        accuracy = round((correct / total), 4) if total else 0.0
        categories.append(
            AggregateCategoryStat(category=cat, correct=correct, total=total, accuracy=accuracy)
        )

    return AggregateStatsResponse(total_logs=len(logs), categories=categories)


def _load_all_question_meta() -> Dict[int, Dict[str, Any]]:
    """
    Load full question metadata from the CSV to ensure all questions (e.g., 451) are present,
    even if not answered yet.
    """
    data: Dict[int, Dict[str, Any]] = {}
    csv_path = Path(__file__).resolve().parent.parent / "data" / "rag_sources" / "dbquiz_eval.csv"
    if not csv_path.exists():
        return data
    import pandas as pd  # local import to avoid hard dependency at module import

    df = pd.read_csv(csv_path, encoding="utf-8-sig")
    for _, row in df.iterrows():
        qid = int(row["id"])
        data[qid] = {
            "category_name": row.get("category") or "기타",
            "answer": str(row.get("answer") or "").strip(),
        }
    return data


@router.get("/question-stats", response_model=List[QuestionStat])
def question_stats(session: Session = Depends(get_session)) -> List[QuestionStat]:
    """
    Aggregate per-question accuracy across all submissions.
    Falls back to CSV metadata so unanswered 문항도 노출됩니다.
    """
    logs = session.exec(
        select(QuizGenerationLog).where(QuizGenerationLog.answers.is_not(None))
    ).all()

    meta = _load_all_question_meta()
    stats: Dict[int, Dict[str, Any]] = {
        qid: {"correct": 0, "total": 0, "category": info.get("category_name", "기타")}
        for qid, info in meta.items()
    }

    for log in logs:
        answers = log.answers or {}
        questions = log.questions or []
        for q in questions:
            qid = q.get("q_id") or q.get("question_id") or q.get("qid")
            if qid is None:
                continue
            try:
                qid_int = int(qid)
            except Exception:
                continue
            cat = q.get("category_name") or q.get("category") or meta.get(qid_int, {}).get("category_name", "기타")
            if qid_int not in stats:
                stats[qid_int] = {"correct": 0, "total": 0, "category": cat}
            else:
                if not stats[qid_int].get("category"):
                    stats[qid_int]["category"] = cat

            stats[qid_int]["total"] += 1
            user_answer = answers.get(str(qid_int)) or answers.get(qid_int)
            is_correct = bool(user_answer) and _normalize_answer(user_answer) == _normalize_answer(
                q.get("answer")
            )
            if is_correct:
                stats[qid_int]["correct"] += 1

    result: List[QuestionStat] = []
    for qid, s in stats.items():
        total = s["total"]
        correct = s["correct"]
        accuracy = round((correct / total), 4) if total else 0.0
        result.append(
            QuestionStat(
                question_id=qid,
                category=s.get("category") or "기타",
                correct=correct,
                total=total,
                accuracy=accuracy,
            )
        )

    # Sort by question id for stable output
    result.sort(key=lambda x: x.question_id)
    return result


def _get_limit_error_message(mode: QuizMode) -> str:
    return _LIMIT_ERROR_MESSAGES.get(mode, "퀴즈 시도 가능 횟수를 모두 사용했습니다.")


@router.get("/attempts/remaining", response_model=RemainingAttemptsResponse)
def get_remaining_attempts(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> RemainingAttemptsResponse:
    service = QuizLimitService(session)
    return RemainingAttemptsResponse(remaining=service.get_remaining(current_user.id))


class StaticQuizReserveRequest(BaseModel):
    mode: Literal["midterm", "final"]
    total_questions: int


@router.post("/reserve-static", response_model=RemainingAttemptsResponse)
def reserve_static_quiz(
    request: StaticQuizReserveRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> RemainingAttemptsResponse:
    service = QuizLimitService(session)
    usage = service.get_usage(current_user.id)
    max_attempts = service.get_limit_for_mode(request.mode, user_id=current_user.id)
    used_attempts = usage.get(request.mode, 0)
    if used_attempts >= max_attempts:
        raise HTTPException(status_code=403, detail=_get_limit_error_message(request.mode))

    log = QuizGenerationLog(
        user_id=current_user.id,
        mode=request.mode,
        total_questions=request.total_questions,
        questions=[],
        extra={"source": "static_reserve"},
    )
    session.add(log)
    session.commit()
    session.refresh(log)

    remaining = service.get_remaining(current_user.id)
    return RemainingAttemptsResponse(remaining=remaining, generation_id=log.id)


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
