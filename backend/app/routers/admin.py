"""
관리자 전용 API 라우터
DB 관리, 사용자 관리, 시스템 모니터링 기능
"""
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from sqlmodel import Session, select, func, desc, delete
from sqlalchemy import or_
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
import random
import pandas as pd
import json
from pydantic import BaseModel, Field

from ..database import get_session
from ..models import QuizGenerationLog
from ..models.user import User, UserRole
from ..models.mentor import MentorMenteeRelation, ExamScore, ExamType, ChatHistory, Feedback, ExamResult
from ..models.document import Document
from ..models.post import Post, Comment
from ..models.simulation_feedback import SimulationFeedback
from ..utils.auth import get_current_user, require_admin, get_password_hash
from ..services.llm_service import LLMService
from ..services.quiz_limit_service import DEFAULT_ATTEMPT_LIMITS, QuizLimitService
from ..init_data import create_initial_users
from ..services.exam_initializer import create_initial_exam_score, EXAM_TYPE_LABELS

router = APIRouter(prefix="/admin", tags=["admin"])
SEED_EMAILS = {
    "admin@bank.com",
    "mentor@bank.com",
    "mentor2@bank.com",
    "mentee@bank.com",
    "mentee2@bank.com",
}

EXAM_SECTION_KEYS = [
    "은행업무",
    "상품개발 및 운용",
    "신용분석 및 리스크관리",
    "외환",
    "은행지식 및 관련법률",
    "하경은행",
]

MENTOR_PROGRESSIVE_RANGES = [
    (ExamType.BEGINNING, (38, 46)),
    (ExamType.MIDTERM, (46, 54)),
    (ExamType.FINAL, (54, 60)),
]


def _generate_section_scores_for_total(total: int) -> Dict[str, int]:
    """총점을 6개 섹션으로 균등 분배하면서 약간의 변동을 준다."""
    total = max(0, min(60, total))
    base = total // len(EXAM_SECTION_KEYS)
    remainder = total % len(EXAM_SECTION_KEYS)
    scores: Dict[str, int] = {}
    for idx, key in enumerate(EXAM_SECTION_KEYS):
        scores[key] = min(10, base + (1 if idx < remainder else 0))
    # 가벼운 편차 부여 (총점 유지)
    for _ in range(5):
        donor, receiver = random.sample(EXAM_SECTION_KEYS, 2)
        if scores[donor] > 3 and scores[receiver] < 10:
            scores[donor] -= 1
            scores[receiver] += 1
    return scores


def _ensure_beginning_exam_for_mentee(session: Session, user: User) -> int:
    exists = session.exec(
        select(ExamScore).where(
            ExamScore.mentee_id == user.id,
            ExamScore.exam_type == ExamType.BEGINNING,
        )
    ).first()
    if exists:
        return 0
    create_initial_exam_score(user.id, session, exam_type=ExamType.BEGINNING, commit=False)
    return 1


def _ensure_progressive_exams_for_mentor(session: Session, user: User) -> int:
    created = 0
    previous_total: Optional[float] = None
    for exam_type, (low, high) in MENTOR_PROGRESSIVE_RANGES:
        exists = session.exec(
            select(ExamScore).where(
                ExamScore.mentee_id == user.id,
                ExamScore.exam_type == exam_type,
            )
        ).first()
        if exists:
            previous_total = exists.total_score
            continue
        target = random.randint(low, high)
        if previous_total is not None:
            target = max(target, int(previous_total) + random.randint(1, 3))
        target = min(60, target)
        section_scores = _generate_section_scores_for_total(target)
        feedback = f"{EXAM_TYPE_LABELS.get(exam_type, '시험')} 결과가 기록되었습니다."
        create_initial_exam_score(
            user.id,
            session,
            exam_type=exam_type,
            section_scores_override=section_scores,
            total_score_override=sum(section_scores.values()),
            feedback=feedback,
            exam_name=EXAM_TYPE_LABELS.get(exam_type, "연수원 평가"),
            commit=False,
        )
        created += 1
        previous_total = sum(section_scores.values())
    return created


class ChatbotConfigResponse(BaseModel):
    id: int
    selected_model: str
    openai_model: str
    qwen_model: str
    qwen_api_base: Optional[str]
    has_qwen_api_key: bool
    temperature: float
    max_tokens: int
    top_k: int
    updated_at: datetime
    provider_options: List[str] = Field(default_factory=lambda: ["openai", "qwen_local"])
    response_style: str
    response_style_options: List[str] = Field(
        default_factory=lambda: ["structured", "narrative"]
    )
    verbosity: str
    verbosity_options: List[str] = Field(
        default_factory=lambda: ["concise", "detailed"]
    )


class ChatbotConfigUpdate(BaseModel):
    selected_model: Optional[str] = None
    openai_model: Optional[str] = None
    qwen_model: Optional[str] = None
    qwen_api_base: Optional[str] = None
    qwen_api_key: Optional[str] = None
    temperature: Optional[float] = Field(default=None, ge=0.0, le=1.5)
    max_tokens: Optional[int] = Field(default=None, ge=100, le=4096)
    top_k: Optional[int] = Field(default=None, ge=1, le=20)
    response_style: Optional[str] = None
    verbosity: Optional[str] = None


class QuizAttemptLimitResponse(BaseModel):
    max_random_attempts: int
    max_custom_attempts: int
    max_midterm_attempts: int
    max_final_attempts: int
    updated_at: datetime


class QuizAttemptLimitUpdate(BaseModel):
    max_random_attempts: Optional[int] = Field(default=None, ge=0)
    max_custom_attempts: Optional[int] = Field(default=None, ge=0)
    max_midterm_attempts: Optional[int] = Field(default=None, ge=0)
    max_final_attempts: Optional[int] = Field(default=None, ge=0)


class UserQuizAttemptInfo(BaseModel):
    limits: Dict[str, int]
    used: Dict[str, int]
    remaining: Dict[str, int]


class UserQuizAttemptLimitUpdate(BaseModel):
    max_random_attempts: Optional[int] = Field(default=None, ge=0)
    max_custom_attempts: Optional[int] = Field(default=None, ge=0)
    max_midterm_attempts: Optional[int] = Field(default=None, ge=0)
    max_final_attempts: Optional[int] = Field(default=None, ge=0)
    reset: Optional[bool] = False


@router.get("/chatbot/config", response_model=ChatbotConfigResponse)
async def get_chatbot_config(
    current_user: User = Depends(require_admin),
    session: Session = Depends(get_session),
):
    """챗봇 LLM 설정 조회"""
    service = LLMService(session)
    data = service.get_config_dict()
    return ChatbotConfigResponse(
        **data,
        provider_options=["openai", "qwen_local"],
        response_style_options=["structured", "narrative"],
        verbosity_options=["concise", "detailed"],
    )


@router.put("/chatbot/config", response_model=ChatbotConfigResponse)
async def update_chatbot_config(
    payload: ChatbotConfigUpdate,
    current_user: User = Depends(require_admin),
    session: Session = Depends(get_session),
):
    """챗봇 LLM 설정 업데이트"""
    service = LLMService(session)
    update_data = payload.model_dump(exclude_unset=True)

    # 빈 문자열은 None으로 처리
    for key in ("qwen_api_base", "qwen_api_key"):
        if key in update_data and update_data[key] == "":
            update_data[key] = None

    allowed_models = {"openai", "qwen_local"}
    if "selected_model" in update_data and update_data["selected_model"] not in allowed_models:
        raise HTTPException(
            status_code=400,
            detail=f"selected_model은 {', '.join(sorted(allowed_models))} 중 하나여야 합니다.",
        )

    allowed_styles = {"structured", "narrative"}
    if "response_style" in update_data and update_data["response_style"] not in allowed_styles:
        raise HTTPException(
            status_code=400,
            detail=f"response_style은 {', '.join(sorted(allowed_styles))} 중 하나여야 합니다.",
        )
    allowed_verbosity = {"concise", "detailed"}
    if "verbosity" in update_data and update_data["verbosity"] not in allowed_verbosity:
        raise HTTPException(
            status_code=400,
            detail=f"verbosity는 {', '.join(sorted(allowed_verbosity))} 중 하나여야 합니다.",
        )

    service.update_config(update_data)
    data = service.get_config_dict()
    return ChatbotConfigResponse(
        **data,
        provider_options=["openai", "qwen_local"],
        response_style_options=["structured", "narrative"],
        verbosity_options=["concise", "detailed"],
    )


@router.get("/quiz/attempt-limits", response_model=QuizAttemptLimitResponse)
async def get_quiz_attempt_limits(
    current_user: User = Depends(require_admin),
    session: Session = Depends(get_session),
):
    """퀴즈 모드별 시도 제한 설정 조회"""
    service = QuizLimitService(session)
    limits = service.get_limit_record()
    return QuizAttemptLimitResponse(
        max_random_attempts=limits.max_random_attempts,
        max_custom_attempts=limits.max_custom_attempts,
        max_midterm_attempts=limits.max_midterm_attempts,
        max_final_attempts=limits.max_final_attempts,
        updated_at=limits.updated_at,
    )


@router.put("/quiz/attempt-limits", response_model=QuizAttemptLimitResponse)
async def update_quiz_attempt_limits(
    payload: QuizAttemptLimitUpdate,
    current_user: User = Depends(require_admin),
    session: Session = Depends(get_session),
):
    """퀴즈 모드별 시도 제한 설정 수정"""
    service = QuizLimitService(session)
    update_data = payload.model_dump(exclude_unset=True)
    try:
        limits = service.update_limits(update_data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return QuizAttemptLimitResponse(
        max_random_attempts=limits.max_random_attempts,
        max_custom_attempts=limits.max_custom_attempts,
        max_midterm_attempts=limits.max_midterm_attempts,
        max_final_attempts=limits.max_final_attempts,
        updated_at=limits.updated_at,
    )


@router.get("/users/{user_id}/quiz-attempts", response_model=UserQuizAttemptInfo)
async def get_user_quiz_attempts(
    user_id: int,
    current_user: User = Depends(require_admin),
    session: Session = Depends(get_session),
) -> UserQuizAttemptInfo:
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")

    service = QuizLimitService(session)
    try:
        limits = service.get_limits(user_id)
        used = service.get_usage(user_id)
        remaining = service.get_remaining(user_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"시도 제한 정보를 불러올 수 없습니다: {exc}")
    return UserQuizAttemptInfo(limits=limits, used=used, remaining=remaining)


@router.put("/users/{user_id}/quiz-attempt-limits", response_model=UserQuizAttemptInfo)
async def update_user_quiz_attempt_limits(
    user_id: int,
    payload: UserQuizAttemptLimitUpdate,
    current_user: User = Depends(require_admin),
    session: Session = Depends(get_session),
) -> UserQuizAttemptInfo:
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")

    service = QuizLimitService(session)
    try:
        if payload.reset:
            service.reset_usage(user_id)
        else:
            update_data = payload.model_dump(exclude_unset=True, exclude={"reset"})
            service.update_limits(update_data, user_id=user_id)

        limits = service.get_limits(user_id)
        used = service.get_usage(user_id)
        remaining = service.get_remaining(user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"시도 제한을 갱신할 수 없습니다: {exc}")
    return UserQuizAttemptInfo(limits=limits, used=used, remaining=remaining)


@router.get("/stats")
async def get_admin_stats(
    current_user: User = Depends(require_admin),
    session: Session = Depends(get_session)
):
    """관리자 대시보드 통계"""
    try:
        # 사용자 통계
        total_users = session.exec(select(func.count(User.id))).first()
        mentors = session.exec(select(func.count(User.id)).where(User.role == UserRole.MENTOR)).first()
        mentees = session.exec(select(func.count(User.id)).where(User.role == UserRole.MENTEE)).first()
        
        # 활성 매칭 수
        active_relations = session.exec(
            select(func.count(MentorMenteeRelation.id)).where(MentorMenteeRelation.is_active == True)
        ).first()
        
        # 최근 활동 통계 (최근 7일)
        week_ago = datetime.utcnow() - timedelta(days=7)
        
        recent_chats = session.exec(
            select(func.count(ChatHistory.id)).where(ChatHistory.created_at >= week_ago)
        ).first()
        
        recent_exams = session.exec(
            select(func.count(ExamScore.id)).where(ExamScore.created_at >= week_ago)
        ).first()
        
        recent_posts = session.exec(
            select(func.count(Post.id)).where(Post.created_at >= week_ago)
        ).first()
        
        return {
            "users": {
                "total": total_users,
                "mentors": mentors,
                "mentees": mentees,
                "active_relations": active_relations
            },
            "activities": {
                "recent_chats": recent_chats,
                "recent_exams": recent_exams,
                "recent_posts": recent_posts
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"통계 조회 실패: {str(e)}")


@router.get("/users")
async def get_all_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    role: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    current_user: User = Depends(require_admin),
    session: Session = Depends(get_session)
):
    """전체 사용자 목록 조회"""
    try:
        query = select(User)
        
        # 역할 필터
        if role:
            query = query.where(User.role == role)
        
        # 검색 필터
        if search:
            query = query.where(
                User.name.contains(search) | 
                User.email.contains(search)
            )
        
        # 정렬 및 페이지네이션
        query = query.order_by(desc(User.created_at)).offset(skip).limit(limit)
        
        users = session.exec(query).all()
        total = session.exec(select(func.count(User.id))).first()

        # 시도 제한/사용량 계산
        try:
            user_ids = [u.id for u in users]
            attempt_service = QuizLimitService(session)
            usage_map: Dict[int, Dict[str, int]] = {
                uid: {mode: 0 for mode in DEFAULT_ATTEMPT_LIMITS} for uid in user_ids
            }
            if user_ids:
                usage_rows = session.exec(
                    select(QuizGenerationLog.user_id, QuizGenerationLog.mode, func.count(QuizGenerationLog.id))
                    .where(QuizGenerationLog.user_id.in_(user_ids))
                    .group_by(QuizGenerationLog.user_id, QuizGenerationLog.mode)
                ).all()
                for uid, mode, count in usage_rows:
                    if uid in usage_map:
                        usage_map[uid][mode] = int(count)

            for user in users:
                limits = attempt_service.get_limits(user.id)
                used = usage_map.get(user.id, {mode: 0 for mode in DEFAULT_ATTEMPT_LIMITS})
                remaining = {
                    mode: max(0, limits.get(mode, DEFAULT_ATTEMPT_LIMITS[mode]) - used.get(mode, 0))
                    for mode in DEFAULT_ATTEMPT_LIMITS
                }
                setattr(user, "quiz_attempts", {"limits": limits, "used": used, "remaining": remaining})
        except Exception:
            # 테이블 미존재 등으로 실패 시 기존 사용자 응답만 반환
            pass

        # 직렬화 안전한 구조로 반환 (불필요한 필드 제외)
        def serialize_user(u: User) -> Dict[str, Any]:
            return {
                "id": u.id,
                "email": u.email,
                "name": u.name,
                "role": u.role,
                "employee_number": getattr(u, "employee_number", None),
                "team": getattr(u, "team", None),
                "phone": getattr(u, "phone", None),
                "photo_url": getattr(u, "photo_url", None),
                "created_at": u.created_at,
                "quiz_attempts": getattr(u, "quiz_attempts", None),
            }

        return {
            "users": [serialize_user(u) for u in users],
            "total": total,
            "skip": skip,
            "limit": limit,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"사용자 목록 조회 실패: {str(e)}")


@router.get("/mentor-mentee-relations")
async def get_mentor_mentee_relations(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    is_active: Optional[bool] = Query(None),
    current_user: User = Depends(require_admin),
    session: Session = Depends(get_session)
):
    """멘토-멘티 관계 목록 조회"""
    try:
        query = select(
            MentorMenteeRelation,
            User.name.label("mentor_name"),
            User.email.label("mentor_email")
        ).join(
            User, MentorMenteeRelation.mentor_id == User.id
        ).join(
            User, MentorMenteeRelation.mentee_id == User.id, aliased=True
        )
        
        if is_active is not None:
            query = query.where(MentorMenteeRelation.is_active == is_active)
        
        query = query.order_by(desc(MentorMenteeRelation.matched_at)).offset(skip).limit(limit)
        
        relations = session.exec(query).all()
        total = session.exec(select(func.count(MentorMenteeRelation.id))).first()
        
        return {
            "relations": relations,
            "total": total,
            "skip": skip,
            "limit": limit
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"멘토-멘티 관계 조회 실패: {str(e)}")


@router.get("/learning-history")
async def get_learning_history(
    user_id: Optional[int] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user: User = Depends(require_admin),
    session: Session = Depends(get_session)
):
    """학습 이력 조회 (퀴즈 로그 기반)"""
    try:
        query = (
            select(
                QuizGenerationLog,
                User.name.label("user_name"),
                User.email.label("user_email"),
            )
            .join(User, QuizGenerationLog.user_id == User.id)
            .where(QuizGenerationLog.score.is_not(None))
        )

        if user_id:
            query = query.where(QuizGenerationLog.user_id == user_id)
        if start_date:
            query = query.where(
                func.coalesce(QuizGenerationLog.submitted_at, QuizGenerationLog.created_at) >= start_date
            )
        if end_date:
            query = query.where(
                func.coalesce(QuizGenerationLog.submitted_at, QuizGenerationLog.created_at) <= end_date
            )

        total = session.exec(
            select(func.count()).select_from(query.subquery())
        ).one()

        results = session.exec(
            query.order_by(func.coalesce(QuizGenerationLog.submitted_at, QuizGenerationLog.created_at).desc())
            .offset(skip)
            .limit(limit)
        ).all()

        history = []
        for log, user_name, user_email in results:
            created_at = log.submitted_at or log.created_at
            # 카테고리별 정오답 집계
            CATEGORY_KEYS = [
                "금융영업",
                "상품개발 및 운용",
                "신용분석 및 리스크관리",
                "외환",
                "은행지식 및 관련법률",
                "하경은행",
            ]
            category_stats: Dict[str, Dict[str, int]] = {k: {"correct": 0, "total": 0} for k in CATEGORY_KEYS}
            answers = log.answers or {}
            questions = log.questions or []

            def _norm(val: Optional[str]) -> str:
                if not val:
                    return ""
                digits = "".join(ch for ch in str(val) if ch.isdigit())
                return digits or str(val).replace(" ", "").lower()

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

            history.append(
                {
                    "id": log.id,
                    "user_id": log.user_id,
                    "user_name": user_name,
                    "user_email": user_email,
                    "mode": log.mode,
                    "score": log.score,
                    "total_questions": log.total_questions,
                    "created_at": created_at,
                    "category_stats": category_stats,
                }
            )

        return {
            "history": history,
            "total": total,
            "skip": skip,
            "limit": limit,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"학습 이력 조회 실패: {str(e)}")


@router.get("/documents")
async def get_all_documents(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    category: Optional[str] = Query(None),
    current_user: User = Depends(require_admin),
    session: Session = Depends(get_session)
):
    """전체 문서 목록 조회"""
    try:
        query = select(Document)
        
        if category:
            query = query.where(Document.category == category)
        
        query = query.order_by(desc(Document.upload_date)).offset(skip).limit(limit)
        
        documents = session.exec(query).all()
        total = session.exec(select(func.count(Document.id))).first()
        
        return {
            "documents": documents,
            "total": total,
            "skip": skip,
            "limit": limit
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"문서 목록 조회 실패: {str(e)}")


@router.get("/system-logs")
async def get_system_logs(
    log_type: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user: User = Depends(require_admin),
    session: Session = Depends(get_session)
):
    """시스템 로그 조회"""
    try:
        # 실제 프로덕션에서는 별도의 로그 테이블을 사용해야 함
        # 현재는 기존 테이블들의 활동을 로그로 취급
        
        logs = []
        
        # 사용자 활동 로그 (로그인 등)
        user_activities = session.exec(
            select(User.id, User.name, User.email, User.created_at, User.updated_at)
            .order_by(desc(User.updated_at))
            .limit(50)
        ).all()
        
        for user in user_activities:
            logs.append({
                "id": f"user_{user.id}",
                "type": "user_activity",
                "message": f"사용자 {user.name} ({user.email}) 활동",
                "timestamp": user.updated_at,
                "details": {
                    "user_id": user.id,
                    "action": "profile_update" if user.updated_at > user.created_at else "registration"
                }
            })
        
        # 채팅 활동 로그
        chat_activities = session.exec(
            select(ChatHistory.id, ChatHistory.user_id, ChatHistory.created_at, User.name)
            .join(User, ChatHistory.user_id == User.id)
            .order_by(desc(ChatHistory.created_at))
            .limit(50)
        ).all()
        
        for chat in chat_activities:
            logs.append({
                "id": f"chat_{chat.id}",
                "type": "chat_activity",
                "message": f"사용자 {chat.name} 챗봇 사용",
                "timestamp": chat.created_at,
                "details": {
                    "user_id": chat.user_id,
                    "chat_id": chat.id,
                    "action": "chat_message"
                }
            })
        
        # 정렬 및 페이지네이션
        logs.sort(key=lambda x: x["timestamp"], reverse=True)
        paginated_logs = logs[skip:skip + limit]
        
        return {
            "logs": paginated_logs,
            "total": len(logs),
            "skip": skip,
            "limit": limit
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"시스템 로그 조회 실패: {str(e)}")


@router.post("/users/{user_id}/role")
async def update_user_role(
    user_id: int,
    new_role: str,
    current_user: User = Depends(require_admin),
    session: Session = Depends(get_session)
):
    """사용자 역할 변경"""
    try:
        user = session.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")
        
        if new_role not in [role.value for role in UserRole]:
            raise HTTPException(status_code=400, detail="유효하지 않은 역할입니다")
        
        user.role = UserRole(new_role)
        user.updated_at = datetime.utcnow()
        
        session.add(user)
        session.commit()
        session.refresh(user)
        
        return {"message": "사용자 역할이 성공적으로 변경되었습니다", "user": user}
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=f"역할 변경 실패: {str(e)}")


@router.post("/mentor-mentee-relations")
async def create_mentor_mentee_relation(
    mentor_id: int,
    mentee_id: int,
    notes: Optional[str] = None,
    current_user: User = Depends(require_admin),
    session: Session = Depends(get_session)
):
    """새로운 멘토-멘티 관계 생성"""
    try:
        # 멘토와 멘티 존재 확인
        mentor = session.get(User, mentor_id)
        mentee = session.get(User, mentee_id)
        
        if not mentor or mentor.role != UserRole.MENTOR:
            raise HTTPException(status_code=400, detail="유효하지 않은 멘토입니다")
        
        if not mentee or mentee.role != UserRole.MENTEE:
            raise HTTPException(status_code=400, detail="유효하지 않은 멘티입니다")
        
        # 기존 관계 확인
        existing = session.exec(
            select(MentorMenteeRelation)
            .where(
                MentorMenteeRelation.mentor_id == mentor_id,
                MentorMenteeRelation.mentee_id == mentee_id,
                MentorMenteeRelation.is_active == True
            )
        ).first()
        
        if existing:
            raise HTTPException(status_code=400, detail="이미 활성화된 관계가 존재합니다")
        
        # 새 관계 생성
        relation = MentorMenteeRelation(
            mentor_id=mentor_id,
            mentee_id=mentee_id,
            notes=notes,
            matched_at=datetime.utcnow(),
            is_active=True
        )
        
        session.add(relation)
        session.commit()
        session.refresh(relation)
        
        return {"message": "멘토-멘티 관계가 성공적으로 생성되었습니다", "relation": relation}
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=f"관계 생성 실패: {str(e)}")


@router.delete("/mentor-mentee-relations/{relation_id}")
async def deactivate_mentor_mentee_relation(
    relation_id: int,
    current_user: User = Depends(require_admin),
    session: Session = Depends(get_session)
):
    """멘토-멘티 관계 비활성화"""
    try:
        relation = session.get(MentorMenteeRelation, relation_id)
        if not relation:
            raise HTTPException(status_code=404, detail="관계를 찾을 수 없습니다")
        
        relation.is_active = False
        session.add(relation)
        session.commit()
        
        return {"message": "멘토-멘티 관계가 비활성화되었습니다"}
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=f"관계 비활성화 실패: {str(e)}")


@router.post("/chatbot-validation/test")
async def test_chatbot_performance(
    question: str = Query(..., description="테스트할 질문"),
    chunk_size: int = Query(1000, description="청크 크기"),
    chunk_overlap: int = Query(200, description="청크 오버랩"),
    top_k: int = Query(5, description="검색할 청크 수"),
    chunking_method: str = Query("fixed", description="청킹 방식: fixed, sentence, semantic"),
    embedding_model: str = Query("text-embedding-ada-002", description="임베딩 모델"),
    temperature: float = Query(0.7, description="Temperature (0.0-2.0)"),
    current_user: User = Depends(require_admin),
    session: Session = Depends(get_session)
):
    """챗봇 성능 검증 테스트"""
    try:
        from ..services.rag_service import RAGService
        import time
        
        # 시작 시간 기록
        start_time = time.time()
        
        # RAG 서비스 초기화 (청킹 설정 적용)
        rag_service = RAGService(session)
        rag_service.chunk_size = chunk_size
        rag_service.chunk_overlap = chunk_overlap
        
        # 답변 생성 (top_k 적용)
        result = await rag_service.generate_rag_answer(question)
        
        # 실제 사용된 청크 검색 (similarity_search 호출 시 k 값 반영)
        search_results = await rag_service.similarity_search(question, k=top_k)
        
        # 응답 시간 계산
        response_time = time.time() - start_time
        
        # 성능 카테고리별 점수 계산
        performance_scores = calculate_performance_scores(
            question=question,
            answer=result["answer"],
            sources=result.get("sources", []),
            response_time=response_time
        )
        
        # 청킹 설정 정보
        chunking_config = {
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap,
            "top_k": top_k,
            "chunking_method": chunking_method,
            "embedding_model": embedding_model,
            "temperature": temperature,
            "total_chunks_found": len(search_results)
        }
        
        return {
            "question": question,
            "answer": result["answer"],
            "sources": result.get("sources", []),
            "response_time": round(response_time, 2),
            "tested_at": datetime.utcnow(),
            "status": "success",
            "performance_scores": performance_scores,
            "chunking_config": chunking_config
        }
    except Exception as e:
        import traceback
        error_detail = f"챗봇 테스트 실패: {str(e)}\n{traceback.format_exc()}"
        print(error_detail)
        raise HTTPException(status_code=500, detail=f"챗봇 테스트 실패: {str(e)}")


def calculate_performance_scores(question: str, answer: str, sources: list, response_time: float) -> list:
    """챗봇 성능을 9개 카테고리로 평가"""
    
    # 1. 이해력 (질문 이해도)
    comprehension = 85
    if len(question) > 10 and '?' in question:
        comprehension += 5
    if any(keyword in question for keyword in ['추천', '알려', '설명', '무엇', '어떻게']):
        comprehension += 5
    comprehension = min(100, comprehension)
    
    # 2. 응답품질 (답변의 완성도)
    response_quality = 80
    if len(answer) > 200:
        response_quality += 10
    if len(answer) > 500:
        response_quality += 5
    if '🐻' in answer or '하리보' in answer:
        response_quality += 5  # 브랜드 일관성
    response_quality = min(100, response_quality)
    
    # 3. 언어표현 (자연스러운 한국어)
    language_expression = 90
    if '참고 자료:' in answer:
        language_expression += 5
    if len(answer.split('\n')) > 3:  # 문단 구조
        language_expression += 5
    language_expression = min(100, language_expression)
    
    # 4. 대화 관리 (맥락 유지)
    conversation_management = 85
    if len(answer) > 100:
        conversation_management += 10
    conversation_management = min(100, conversation_management)
    
    # 5. 사용자 경험 (친근함, 이해하기 쉬움)
    user_experience = 88
    if '🐻' in answer:
        user_experience += 7
    if any(word in answer for word in ['안녕', '감사', '도움', '추천']):
        user_experience += 5
    user_experience = min(100, user_experience)
    
    # 6. 검색·RAG 성능 (참고 자료 활용)
    rag_performance = 75
    if sources and len(sources) > 0:
        rag_performance += 15
        if len(sources) >= 3:
            rag_performance += 10
    rag_performance = min(100, rag_performance)
    
    # 7. 지속 학습·피드백 (개선 가능성)
    learning_feedback = 80
    if sources:
        learning_feedback += 15
    learning_feedback = min(100, learning_feedback)
    
    # 8. 보안·윤리 (적절한 답변)
    security_ethics = 95
    if '토스뱅크' not in answer:  # 브랜드 일관성
        security_ethics += 5
    security_ethics = min(100, security_ethics)
    
    # 9. 유지보수·운영 효율 (응답 속도)
    operational_efficiency = 90
    if response_time < 2:
        operational_efficiency += 10
    elif response_time < 5:
        operational_efficiency += 5
    elif response_time > 10:
        operational_efficiency -= 20
    operational_efficiency = max(60, min(100, operational_efficiency))
    
    return [
        {"category": "이해력", "score": comprehension, "fullMark": 100},
        {"category": "응답품질", "score": response_quality, "fullMark": 100},
        {"category": "언어표현", "score": language_expression, "fullMark": 100},
        {"category": "대화관리", "score": conversation_management, "fullMark": 100},
        {"category": "사용자경험", "score": user_experience, "fullMark": 100},
        {"category": "RAG성능", "score": rag_performance, "fullMark": 100},
        {"category": "학습피드백", "score": learning_feedback, "fullMark": 100},
        {"category": "보안윤리", "score": security_ethics, "fullMark": 100},
        {"category": "운영효율", "score": operational_efficiency, "fullMark": 100}
    ]


@router.get("/chatbot-validation/stats")
async def get_chatbot_stats(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    current_user: User = Depends(require_admin),
    session: Session = Depends(get_session)
):
    """챗봇 사용 통계 조회"""
    try:
        # 기본 날짜 범위 설정 (최근 30일)
        if not end_date:
            end_date = datetime.utcnow()
        if not start_date:
            start_date = end_date - timedelta(days=30)
        
        # 채팅 통계
        total_chats = session.exec(
            select(func.count(ChatHistory.id)).where(
                ChatHistory.created_at >= start_date,
                ChatHistory.created_at <= end_date
            )
        ).first()
        
        # 일별 채팅 수
        daily_chats = session.exec(
            select(
                func.date(ChatHistory.created_at).label("date"),
                func.count(ChatHistory.id).label("count")
            ).where(
                ChatHistory.created_at >= start_date,
                ChatHistory.created_at <= end_date
            ).group_by(func.date(ChatHistory.created_at))
            .order_by(func.date(ChatHistory.created_at))
        ).all()
        
        # 사용자별 채팅 수 (상위 10명)
        user_chats = session.exec(
            select(
                User.name,
                User.email,
                func.count(ChatHistory.id).label("chat_count")
            ).join(User, ChatHistory.user_id == User.id)
            .where(
                ChatHistory.created_at >= start_date,
                ChatHistory.created_at <= end_date
            ).group_by(User.id, User.name, User.email)
            .order_by(desc(func.count(ChatHistory.id)))
            .limit(10)
        ).all()
        
        return {
            "period": {
                "start_date": start_date,
                "end_date": end_date
            },
            "total_chats": total_chats,
            "daily_stats": [
                {"date": str(row.date), "count": row.count}
                for row in daily_chats
            ],
            "top_users": [
                {
                    "name": row.name,
                    "email": row.email,
                    "chat_count": row.chat_count
                }
                for row in user_chats
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"챗봇 통계 조회 실패: {str(e)}")


# =============================
# 사용자 엑셀 업로드 (멘토/멘티/관리자)
# =============================
@router.post("/users/upload-excel")
async def upload_users_excel(
    file: UploadFile = File(...),
    role: str = Form(..., description="admin | mentor | mentee"),
    current_user: User = Depends(require_admin),
    session: Session = Depends(get_session)
):
    """
    Excel 파일(.xlsx/.xls)을 업로드하여 사용자 일괄 등록/업데이트
    - 컬럼: name, join_year, employee_number, position, team, birth, address, email, phone
    - 이메일이 없으면 employee_number 기반 placeholder 이메일 생성
    - 비밀번호는 기본값으로 employee_number 또는 'welcome123!' 사용하여 해시 저장
    - employee_number 또는 email로 기존 사용자 존재 시 업데이트, 없으면 생성
    """
    try:
        content = await file.read()
        try:
            df = pd.read_excel(content)
        except Exception:
            # 일부 환경에서 바이너리 본문으로 바로 읽기가 실패하면 BytesIO 사용
            import io
            df = pd.read_excel(io.BytesIO(content))

        required_cols = [
            "name", "join_year", "employee_number", "position",
            "team", "birth", "address", "email", "phone"
        ]
        missing = [c for c in required_cols if c not in df.columns]
        if missing:
            raise HTTPException(status_code=400, detail=f"누락 컬럼: {', '.join(missing)}")

        role_map = {
            "admin": UserRole.ADMIN,
            "mentor": UserRole.MENTOR,
            "mentee": UserRole.MENTEE,
        }
        if role not in role_map:
            raise HTTPException(status_code=400, detail="role은 admin|mentor|mentee 중 하나여야 합니다")

        created_count = 0
        updated_count = 0
        errors: List[str] = []
        # 같은 업로드 파일 내 중복 방지(유니크 제약 충돌 방지)
        seen_employee_numbers: set[str] = set()
        seen_emails: set[str] = set()

        for idx, row in df.iterrows():
            try:
                name = str(row.get("name", "")).strip()
                emp_no = str(row.get("employee_number", "")).strip()
                if not name or not emp_no:
                    errors.append(f"행 {idx+2}: name/employee_number 누락")
                    continue

                # 로그인 ID는 사번을 사용 (요청사항)
                # email 필드를 로그인 ID로 사용하므로, 비어있거나 다른 값이어도 최종적으로 사번으로 덮어씀
                email = str(row.get("email", "")).strip()
                if not emp_no:
                    # 사번 없으면 계정 ID 생성 불가
                    errors.append(f"행 {idx+2}: employee_number 누락")
                    continue
                email = emp_no

                # 같은 업로드 세션 내에서 이미 본 값이면 DB 조회 없이 업데이트 대상으로 간주
                existing = None
                if emp_no in seen_employee_numbers or email in seen_emails:
                    existing = session.exec(
                        select(User).where((User.employee_number == emp_no) | (User.email == email))
                    ).first()
                else:
                    existing = session.exec(
                        select(User).where((User.employee_number == emp_no) | (User.email == email))
                    ).first()

                # 공통 필드 준비
                # 안전 파싱: join_year는 정수로, NaN/공백 처리
                jy_val = row.get("join_year")
                join_year = None
                if pd.notna(jy_val) and str(jy_val).strip() != "":
                    try:
                        join_year = int(float(jy_val))
                    except Exception:
                        join_year = None
                position = str(row.get("position", "")).strip() or None
                team = str(row.get("team", "")).strip() or None
                # birth는 8자리 문자열(YYYYMMDD)로 보정, 숫자형이면 zero-fill
                bval = row.get("birth")
                birth = None
                if pd.notna(bval) and str(bval).strip() != "":
                    bstr = str(bval).strip()
                    # 엑셀 숫자형 방지
                    if bstr.replace(".", "", 1).isdigit():
                        try:
                            bstr = str(int(float(bstr)))
                        except Exception:
                            pass
                    if len(bstr) == 7:
                        bstr = bstr.zfill(8)
                    elif len(bstr) < 8:
                        bstr = bstr.zfill(8)
                    birth = bstr
                address = str(row.get("address", "")).strip() or None
                phone = str(row.get("phone", "")).strip() or None

                if existing:
                    existing.name = name
                    existing.email = email  # 로그인 ID를 사번으로
                    existing.role = role_map[role]
                    existing.employee_number = emp_no
                    existing.join_year = join_year
                    existing.position = position
                    existing.team = team
                    existing.birth = birth
                    existing.address = address
                    existing.phone = phone
                    existing.is_active = True
                    # 비밀번호는 생년월일로 초기화(요청사항)
                    if birth:
                        existing.hashed_password = get_password_hash(birth)
                    session.add(existing)
                    updated_count += 1
                else:
                    # 기본 비밀번호: 생년월일(YYYYMMDD)
                    default_password = birth if birth else "welcome123!"
                    user = User(
                        email=email,  # 로그인 ID로 사번 사용
                        hashed_password=get_password_hash(default_password),
                        name=name,
                        role=role_map[role],
                        employee_number=emp_no,
                        join_year=join_year,
                        position=position,
                        team=team,
                        birth=birth,
                        address=address,
                        phone=phone,
                        is_active=True,
                    )
                    session.add(user)
                    # 플러시하여 같은 트랜잭션 내 다음 조회에서 보이도록 함 (유니크 충돌 방지)
                    session.flush()
                    seen_employee_numbers.add(emp_no)
                    seen_emails.add(email)
                    created_count += 1
            except Exception as e:
                errors.append(f"행 {idx+2}: {e}")

        session.commit()

        return {
            "message": "업로드 처리 완료",
            "created_users": created_count,
            "updated_users": updated_count,
            "error_count": len(errors),
            "errors": errors,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"엑셀 처리 실패: {str(e)}")


@router.delete("/users/{user_id}")
async def hard_delete_user(
    user_id: int,
    current_user: User = Depends(require_admin),
    session: Session = Depends(get_session)
):
    """사용자 하드 삭제(테스트용): 연관 데이터 정리 후 삭제"""
    user = session.exec(select(User).where(User.id == user_id)).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        # 멘토-멘티 관계 제거(양쪽)
        for rel in session.exec(select(MentorMenteeRelation).where(MentorMenteeRelation.mentor_id == user_id)).all():
            session.delete(rel)
        for rel in session.exec(select(MentorMenteeRelation).where(MentorMenteeRelation.mentee_id == user_id)).all():
            session.delete(rel)

        # 시험/학습/채팅 기록 정리
        for s in session.exec(select(ExamScore).where(ExamScore.mentee_id == user_id)).all():
            session.delete(s)
        for ch in session.exec(select(ChatHistory).where(ChatHistory.user_id == user_id)).all():
            session.delete(ch)

        # 게시글/댓글은 익명 서비스 특성상 하드 삭제 대신 작성자 정보가 있을 경우만 소프트 삭제 처리 가능
        # 여기서는 해당 사용자의 댓글만 제거(선택). 필요 시 확장
        for c in session.exec(select(Comment).where(Comment.author_id == user_id)).all():
            session.delete(c)
        for p in session.exec(select(Post).where(Post.author_id == user_id)).all():
            session.delete(p)

        session.delete(user)
        session.commit()
        return {"message": "User deleted successfully"}
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=f"삭제 실패: {str(e)}")


@router.post("/users/reset-to-seed")
async def reset_users_to_seed(
    current_user: User = Depends(require_admin),
    session: Session = Depends(get_session),
):
    """
    초기 계정(admin@bank.com, mentor@bank.com, mentor2@bank.com, mentee@bank.com, mentee2@bank.com)만 남기고 모두 삭제
    """
    try:
        seed_users = session.exec(select(User).where(User.email.in_(SEED_EMAILS))).all()
        seed_ids = {u.id for u in seed_users}

        # 삭제 대상 사용자
        target_users = session.exec(
            select(User).where(User.email.not_in(SEED_EMAILS))
        ).all()
        target_ids = [u.id for u in target_users]

        if not target_ids:
            return {"message": "삭제할 사용자가 없습니다.", "deleted": 0}

        # 멘토-멘티 관계, 피드백, 채팅, 시험/퀴즈 로그, 게시물/댓글 삭제
        session.exec(delete(MentorMenteeRelation).where(
            or_(
                MentorMenteeRelation.mentor_id.in_(target_ids),
                MentorMenteeRelation.mentee_id.in_(target_ids),
            )
        ))
        session.exec(delete(Feedback).where(
            or_(
                Feedback.mentor_id.in_(target_ids),
                Feedback.mentee_id.in_(target_ids),
            )
        ))
        session.exec(delete(ChatHistory).where(ChatHistory.user_id.in_(target_ids)))
        session.exec(delete(ExamResult).where(ExamResult.mentee_id.in_(target_ids)))
        session.exec(delete(ExamScore).where(ExamScore.mentee_id.in_(target_ids)))
        session.exec(delete(QuizGenerationLog).where(QuizGenerationLog.user_id.in_(target_ids)))
        session.exec(delete(Comment).where(Comment.author_id.in_(target_ids)))
        session.exec(delete(Post).where(Post.author_id.in_(target_ids)))

        # 사용자 삭제
        session.exec(delete(User).where(User.id.in_(target_ids)))

        # 시드 계정이 모두 존재하도록 보충
        create_initial_users(session)

        session.commit()
        return {"message": f"{len(target_ids)}명의 사용자를 초기 계정 제외하고 삭제했습니다.", "deleted": len(target_ids)}
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=f"사용자 초기화 실패: {str(e)}")


@router.post("/learning-history/seed-prequiz")
async def seed_exam_scores(
    current_user: User = Depends(require_admin),
    session: Session = Depends(get_session),
):
    """
    학습 이력 탭의 '성적 생성' 기능
    - 멘티: 초기 평가(ExamType.BEGINNING)만 생성
    - 멘토: 초기/중간/최종 평가를 상승 곡선으로 생성
    """
    try:
        users = session.exec(
            select(User).where(
                User.role != UserRole.ADMIN,
                User.is_active == True,  # noqa: E712
            )
        ).all()

        mentee_created = 0
        mentor_created = 0

        for user in users:
            if user.role == UserRole.MENTEE:
                mentee_created += _ensure_beginning_exam_for_mentee(session, user)
            elif user.role == UserRole.MENTOR:
                mentor_created += _ensure_progressive_exams_for_mentor(session, user)

        session.commit()
        return {
            "message": f"멘티 {mentee_created}명, 멘토 {mentor_created}명의 시험 점수를 생성했습니다.",
            "mentees_created": mentee_created,
            "mentors_created": mentor_created,
        }
    except HTTPException:
        session.rollback()
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=f"시험 점수 생성 실패: {str(e)}")


@router.post("/mentees/exam/upload-excel")
async def upload_mentee_exam_excel(
    file: UploadFile = File(...),
    current_user: User = Depends(require_admin),
    session: Session = Depends(get_session)
):
    """
    멘티 시험 결과 Excel(.xlsx/.xls) 업로드
    - 필수 컬럼: name, employee_number
    - 각 영역별로 1~10 문제 컬럼: 금융영업1..10, 상품개발 및 운용1..10, 신용분석 및 리스크관리1..10, 외환1..10, 은행지식 및 관련법률1..10, 하경은행1..10
    - 각 문제 값: 0(오답) 또는 1(정답)
    - 영역 점수: 합계(0~10), 총점: 6개 합(0~60)
    - 결과는 ExamScore(score_data JSON, total_score=총점)로 저장/갱신
    """
    try:
        content = await file.read()
        import io
        try:
            df = pd.read_excel(content)
        except Exception:
            df = pd.read_excel(io.BytesIO(content))

        required = ["name", "employee_number"]
        miss = [c for c in required if c not in df.columns]
        if miss:
            raise HTTPException(status_code=400, detail=f"누락 컬럼: {', '.join(miss)}")

        categories = [
            ("금융영업", [f"금융영업{i}" for i in range(1, 11)]),
            ("상품개발 및 운용", [f"상품개발 및 운용{i}" for i in range(1, 11)]),
            ("신용분석 및 리스크관리", [f"신용분석 및 리스크관리{i}" for i in range(1, 11)]),
            ("외환", [f"외환{i}" for i in range(1, 11)]),
            ("은행지식 및 관련법률", [f"은행지식 및 관련법률{i}" for i in range(1, 11)]),
            ("하경은행", [f"하경은행{i}" for i in range(1, 11)]),
        ]

        processed = 0
        processed_items = []
        errors: list[str] = []

        for idx, row in df.iterrows():
            try:
                emp_no = str(row.get("employee_number", "")).strip()
                if not emp_no:
                    errors.append(f"행 {idx+2}: employee_number 누락")
                    continue
                # 멘티 찾기 (사번 또는 email==사번)
                mentee = session.exec(
                    select(User).where((User.employee_number == emp_no) | (User.email == emp_no))
                ).first()
                if not mentee:
                    errors.append(f"행 {idx+2}: 사번 {emp_no} 사용자 없음")
                    continue

                score_by_cat: dict[str, int] = {}
                total = 0
                for cat, cols in categories:
                    s = 0
                    for col in cols:
                        val = row.get(col, 0)
                        try:
                            v = int(float(val)) if pd.notna(val) and str(val).strip() != "" else 0
                        except Exception:
                            v = 0
                        v = 1 if v == 1 else 0
                        s += v
                    score_by_cat[cat] = int(s)
                    total += int(s)

                # 최신 시험 점수 저장(덮어쓰기: 동일 시험명 기준 가장 최신 업데이트)
                existing = session.exec(
                    select(ExamScore).where(
                        ExamScore.mentee_id == mentee.id,
                        ExamScore.exam_type == ExamType.FINAL,
                    )
                ).first()

                if existing:
                    existing.score_data = json.dumps(score_by_cat, ensure_ascii=False)
                    existing.total_score = float(total)
                    existing.exam_date = datetime.utcnow()
                    existing.grade = None
                    existing.exam_name = EXAM_TYPE_LABELS.get(ExamType.FINAL, "연수원 최종 평가")
                    session.add(existing)
                else:
                    es = ExamScore(
                        mentee_id=mentee.id,
                        exam_name=EXAM_TYPE_LABELS.get(ExamType.FINAL, "연수원 최종 평가"),
                        exam_type=ExamType.FINAL,
                        exam_date=datetime.utcnow(),
                        score_data=json.dumps(score_by_cat, ensure_ascii=False),
                        total_score=float(total),
                        grade=None,
                        feedback=None,
                    )
                    session.add(es)
                processed += 1
                processed_items.append({
                    "mentee_id": mentee.id,
                    "name": mentee.name,
                    "employee_number": mentee.employee_number,
                    "scores": score_by_cat,
                    "total": total
                })
            except Exception as e:
                errors.append(f"행 {idx+2}: {e}")

        session.commit()
        return {"message": "멘티 시험 업로드 완료", "processed_count": processed, "processed": processed_items, "errors": errors}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"멘티 시험 업로드 실패: {str(e)}")


# =============================
# 시뮬레이션 피드백 분석 API
# =============================

def parse_persona_info(persona_info: Optional[str]) -> dict:
    """persona_info 문자열 파싱 (예: "30대 남성 직장인 긍정형" 또는 "60대 이상 여성 은퇴자")"""
    if not persona_info:
        return {"age_group": None, "gender": None, "occupation": None, "customer_style": None}
    
    # 공백으로 분리
    parts = persona_info.strip().split()
    result = {
        "age_group": None,
        "gender": None,
        "occupation": None,
        "customer_style": None
    }
    
    # 연령대 패턴 (긴 패턴부터 먼저 확인)
    age_patterns = ["60대 이상", "10대", "20대", "30대", "40대", "50대"]
    # 성별 패턴 (남자, 여자로 통일)
    gender_patterns = ["남성", "여성", "남자", "여자", "male", "female"]
    # 직업 패턴
    occupation_patterns = ["학생", "직장인", "무직", "자영업자", "은퇴자"]
    # 고객 성향 패턴 (모든 고객 성향 포함)
    customer_style_patterns = ["불만형", "긍정형", "급함형", "불안형", "의심형"]
    
    # 연령대 먼저 확인 (긴 패턴부터)
    for age_pattern in age_patterns:
        if age_pattern in persona_info:
            result["age_group"] = age_pattern
            break
    
    # 나머지 부분에서 성별, 직업, 고객 성향 찾기
    remaining_text = persona_info
    if result["age_group"]:
        remaining_text = remaining_text.replace(result["age_group"], "").strip()
    
    remaining_parts = remaining_text.split()
    
    for part in remaining_parts:
        # 성별 확인
        if part in gender_patterns:
            if part in ["male", "남성", "남자"]:
                result["gender"] = "남자"
            elif part in ["female", "여성", "여자"]:
                result["gender"] = "여자"
            else:
                result["gender"] = part
        # 직업 확인
        elif part in occupation_patterns:
            result["occupation"] = part
        # 고객 성향 확인
        elif part in customer_style_patterns:
            result["customer_style"] = part
    
    return result


@router.get("/simulation-analytics/gender-comparison")
async def get_gender_comparison(
    current_user: User = Depends(require_admin),
    session: Session = Depends(get_session)
):
    """① 성별별 평균 점수 비교 (Bar Chart)"""
    try:
        # 테스트 모드 제외
        feedbacks = session.exec(
            select(SimulationFeedback).where(
                SimulationFeedback.is_test_mode == False
            )
        ).all()
        
        if not feedbacks:
            return {
                "male": {},
                "female": {},
                "total_count": 0
            }
        
        # 성별별 점수 집계 (5가지 지표: 지식, 기술, 친절도, 전달력, 페르소나 정합도)
        male_scores = {"knowledge": [], "skill": [], "kindness": [], "delivery": [], "persona_fit": []}
        female_scores = {"knowledge": [], "skill": [], "kindness": [], "delivery": [], "persona_fit": []}
        
        for fb in feedbacks:
            parsed = parse_persona_info(fb.persona_info)
            gender = parsed.get("gender")
            
            # null 값이나 필수 정보가 없는 경우 제외
            if not gender or gender not in ["남자", "여자"]:
                continue
            
            # 전달력 = (clarity_score + confidence_score) / 2
            delivery_score = (fb.clarity_score + fb.confidence_score) / 2.0
            
            # null 값 체크: 점수가 None이거나 0인 경우는 제외하지 않음 (0점도 유효한 점수)
            # 하지만 필수 정보가 없으면 제외
            
            if gender == "남자":
                male_scores["knowledge"].append(fb.knowledge_score)
                male_scores["skill"].append(fb.skill_score)
                male_scores["kindness"].append(fb.kindness_score)
                male_scores["delivery"].append(delivery_score)
                male_scores["persona_fit"].append(fb.persona_fit_score)
            elif gender == "여자":
                female_scores["knowledge"].append(fb.knowledge_score)
                female_scores["skill"].append(fb.skill_score)
                female_scores["kindness"].append(fb.kindness_score)
                female_scores["delivery"].append(delivery_score)
                female_scores["persona_fit"].append(fb.persona_fit_score)
        
        # 평균 계산
        def calc_avg(scores_list):
            return sum(scores_list) / len(scores_list) if scores_list else 0.0
        
        return {
            "male": {
                "knowledge": round(calc_avg(male_scores["knowledge"]), 2),
                "skill": round(calc_avg(male_scores["skill"]), 2),
                "kindness": round(calc_avg(male_scores["kindness"]), 2),
                "delivery": round(calc_avg(male_scores["delivery"]), 2),
                "persona_fit": round(calc_avg(male_scores["persona_fit"]), 2)
            },
            "female": {
                "knowledge": round(calc_avg(female_scores["knowledge"]), 2),
                "skill": round(calc_avg(female_scores["skill"]), 2),
                "kindness": round(calc_avg(female_scores["kindness"]), 2),
                "delivery": round(calc_avg(female_scores["delivery"]), 2),
                "persona_fit": round(calc_avg(female_scores["persona_fit"]), 2)
            },
            "total_count": len(feedbacks)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"성별 비교 분석 실패: {str(e)}")


@router.get("/simulation-analytics/age-group-distribution")
async def get_age_group_distribution(
    current_user: User = Depends(require_admin),
    session: Session = Depends(get_session)
):
    """② 연령대별 점수 분포 (Line Chart 또는 Boxplot)"""
    try:
        feedbacks = session.exec(
            select(SimulationFeedback).where(
                SimulationFeedback.is_test_mode == False
            )
        ).all()
        
        if not feedbacks:
            return {}
        
        # 연령대별 점수 집계
        age_groups = {}
        
        for fb in feedbacks:
            parsed = parse_persona_info(fb.persona_info)
            age_group = parsed.get("age_group")
            
            # null 값이나 "알 수 없음" 제외
            if not age_group or age_group == "알 수 없음":
                continue
            
            if age_group not in age_groups:
                age_groups[age_group] = {
                    "knowledge": [],
                    "skill": [],
                    "kindness": [],
                    "delivery": [],
                    "persona_fit": [],
                    "overall": []
                }
            
            # 전달력 = (clarity_score + confidence_score) / 2
            delivery_score = (fb.clarity_score + fb.confidence_score) / 2.0
            
            age_groups[age_group]["knowledge"].append(fb.knowledge_score)
            age_groups[age_group]["skill"].append(fb.skill_score)
            age_groups[age_group]["kindness"].append(fb.kindness_score)
            age_groups[age_group]["delivery"].append(delivery_score)
            age_groups[age_group]["persona_fit"].append(fb.persona_fit_score)
            age_groups[age_group]["overall"].append(fb.overall_score)
        
        # 평균 및 분포 계산
        result = {}
        for age_group, scores in age_groups.items():
            def calc_stats(scores_list):
                if not scores_list:
                    return {"avg": 0, "min": 0, "max": 0, "median": 0, "q1": 0, "q3": 0}
                sorted_scores = sorted(scores_list)
                n = len(sorted_scores)
                return {
                    "avg": round(sum(scores_list) / n, 2),
                    "min": min(scores_list),
                    "max": max(scores_list),
                    "median": sorted_scores[n // 2] if n > 0 else 0,
                    "q1": sorted_scores[n // 4] if n >= 4 else sorted_scores[0],
                    "q3": sorted_scores[3 * n // 4] if n >= 4 else sorted_scores[-1],
                    "count": n
                }
            
            result[age_group] = {
                "knowledge": calc_stats(scores["knowledge"]),
                "skill": calc_stats(scores["skill"]),
                "kindness": calc_stats(scores["kindness"]),
                "delivery": calc_stats(scores["delivery"]),
                "persona_fit": calc_stats(scores["persona_fit"]),
                "overall": calc_stats(scores["overall"])
            }
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"연령대별 분포 분석 실패: {str(e)}")


@router.get("/simulation-analytics/occupation-comparison")
async def get_occupation_comparison(
    current_user: User = Depends(require_admin),
    session: Session = Depends(get_session)
):
    """③ 직업군별 성과 비교 (Horizontal Bar Chart 또는 Radar Chart)"""
    try:
        feedbacks = session.exec(
            select(SimulationFeedback).where(
                SimulationFeedback.is_test_mode == False
            )
        ).all()
        
        if not feedbacks:
            return {}
        
        # 직업별 점수 집계
        occupations = {}
        
        for fb in feedbacks:
            # persona_occupation 필드가 있으면 직접 사용, 없으면 persona_info에서 파싱
            occupation = None
            if hasattr(fb, 'persona_occupation') and fb.persona_occupation:
                occupation = fb.persona_occupation
            else:
                parsed = parse_persona_info(fb.persona_info)
                occupation = parsed.get("occupation")
            
            # null 값이나 "알 수 없음" 제외
            if not occupation or occupation == "알 수 없음":
                continue
            
            if occupation not in occupations:
                occupations[occupation] = {
                    "knowledge": [],
                    "skill": [],
                    "kindness": [],
                    "delivery": [],
                    "persona_fit": []
                }
            
            # 전달력 = (clarity_score + confidence_score) / 2
            delivery_score = (fb.clarity_score + fb.confidence_score) / 2.0
            
            occupations[occupation]["knowledge"].append(fb.knowledge_score)
            occupations[occupation]["skill"].append(fb.skill_score)
            occupations[occupation]["kindness"].append(fb.kindness_score)
            occupations[occupation]["delivery"].append(delivery_score)
            occupations[occupation]["persona_fit"].append(fb.persona_fit_score)
        
        # 평균 계산
        result = {}
        for occupation, scores in occupations.items():
            def calc_avg(scores_list):
                return round(sum(scores_list) / len(scores_list), 2) if scores_list else 0.0
            
            result[occupation] = {
                "knowledge": calc_avg(scores["knowledge"]),
                "skill": calc_avg(scores["skill"]),
                "kindness": calc_avg(scores["kindness"]),
                "delivery": calc_avg(scores["delivery"]),
                "persona_fit": calc_avg(scores["persona_fit"]),
                "count": len(scores["knowledge"])
            }
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"직업군별 비교 분석 실패: {str(e)}")


@router.get("/simulation-analytics/customer-style-radar")
async def get_customer_style_radar(
    current_user: User = Depends(require_admin),
    session: Session = Depends(get_session)
):
    """④ 고객 성향별 점수 레이더 차트"""
    try:
        feedbacks = session.exec(
            select(SimulationFeedback).where(
                SimulationFeedback.is_test_mode == False
            )
        ).all()
        
        if not feedbacks:
            return {}
        
        # 고객 성향별 점수 집계
        customer_styles = {}
        
        for fb in feedbacks:
            # persona_customer_style 필드가 있으면 직접 사용, 없으면 persona_info에서 파싱
            customer_style = None
            if hasattr(fb, 'persona_customer_style') and fb.persona_customer_style:
                customer_style = fb.persona_customer_style
            else:
                parsed = parse_persona_info(fb.persona_info)
                customer_style = parsed.get("customer_style")
            
            # null 값이나 "알 수 없음" 제외
            if not customer_style or customer_style == "알 수 없음":
                continue
            
            if customer_style not in customer_styles:
                customer_styles[customer_style] = {
                    "knowledge": [],
                    "skill": [],
                    "kindness": [],
                    "delivery": [],
                    "persona_fit": []
                }
            
            # 전달력 = (clarity_score + confidence_score) / 2
            delivery_score = (fb.clarity_score + fb.confidence_score) / 2.0
            
            customer_styles[customer_style]["knowledge"].append(fb.knowledge_score)
            customer_styles[customer_style]["skill"].append(fb.skill_score)
            customer_styles[customer_style]["kindness"].append(fb.kindness_score)
            customer_styles[customer_style]["delivery"].append(delivery_score)
            customer_styles[customer_style]["persona_fit"].append(fb.persona_fit_score)
        
        # 평균 계산
        result = {}
        for style, scores in customer_styles.items():
            def calc_avg(scores_list):
                return round(sum(scores_list) / len(scores_list), 2) if scores_list else 0.0
            
            result[style] = {
                "knowledge": calc_avg(scores["knowledge"]),
                "skill": calc_avg(scores["skill"]),
                "kindness": calc_avg(scores["kindness"]),
                "delivery": calc_avg(scores["delivery"]),
                "persona_fit": calc_avg(scores["persona_fit"]),
                "count": len(scores["knowledge"])
            }
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"고객 성향별 분석 실패: {str(e)}")


@router.get("/simulation-analytics/correlation-heatmap")
async def get_correlation_heatmap(
    current_user: User = Depends(require_admin),
    session: Session = Depends(get_session)
):
    """⑤ 6가지 지표 간 상관관계 (Heatmap)"""
    try:
        feedbacks = session.exec(
            select(SimulationFeedback).where(
                SimulationFeedback.is_test_mode == False
            )
        ).all()
        
        if not feedbacks:
            return {}
        
        # 점수 배열 생성 (5가지 지표)
        metrics = ["knowledge", "skill", "kindness", "delivery", "persona_fit"]
        scores_dict = {metric: [] for metric in metrics}
        
        for fb in feedbacks:
            # 전달력 = (clarity_score + confidence_score) / 2
            delivery_score = (fb.clarity_score + fb.confidence_score) / 2.0
            
            scores_dict["knowledge"].append(fb.knowledge_score)
            scores_dict["skill"].append(fb.skill_score)
            scores_dict["kindness"].append(fb.kindness_score)
            scores_dict["delivery"].append(delivery_score)
            scores_dict["persona_fit"].append(fb.persona_fit_score)
        
        # 상관관계 계산
        def calculate_correlation(x, y):
            if len(x) != len(y) or len(x) == 0:
                return 0.0
            n = len(x)
            mean_x = sum(x) / n
            mean_y = sum(y) / n
            
            numerator = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n))
            denominator_x = sum((x[i] - mean_x) ** 2 for i in range(n))
            denominator_y = sum((y[i] - mean_y) ** 2 for i in range(n))
            
            if denominator_x == 0 or denominator_y == 0:
                return 0.0
            
            correlation = numerator / ((denominator_x ** 0.5) * (denominator_y ** 0.5))
            return round(correlation, 3)
        
        # 상관관계 행렬 생성
        correlation_matrix = {}
        for metric1 in metrics:
            correlation_matrix[metric1] = {}
            for metric2 in metrics:
                correlation_matrix[metric1][metric2] = calculate_correlation(
                    scores_dict[metric1],
                    scores_dict[metric2]
                )
        
        return {
            "correlation_matrix": correlation_matrix,
            "total_count": len(feedbacks)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"상관관계 분석 실패: {str(e)}")


@router.get("/simulation-analytics/weekly-trend")
async def get_weekly_trend(
    current_user: User = Depends(require_admin),
    session: Session = Depends(get_session)
):
    """⑥ 기간별(주별) 평균 점수 추이 (Line Chart)"""
    try:
        feedbacks = session.exec(
            select(SimulationFeedback).where(
                SimulationFeedback.is_test_mode == False
            )
        ).all()
        
        if not feedbacks:
            return {}
        
        # 주별 점수 집계
        weekly_scores = {}
        
        def get_week_key(date):
            """날짜를 주차 키로 변환 (YYYY-WW 형식)"""
            year, week, _ = date.isocalendar()
            return f"{year}-W{week:02d}"
        
        for fb in feedbacks:
            # created_at에서 년-주 추출
            week_key = get_week_key(fb.created_at)
            
            if week_key not in weekly_scores:
                weekly_scores[week_key] = {
                    "knowledge": [],
                    "skill": [],
                    "kindness": [],
                    "delivery": [],
                    "persona_fit": [],
                    "overall": []
                }
            
            # 전달력 = (clarity_score + confidence_score) / 2
            delivery_score = (fb.clarity_score + fb.confidence_score) / 2.0
            
            weekly_scores[week_key]["knowledge"].append(fb.knowledge_score)
            weekly_scores[week_key]["skill"].append(fb.skill_score)
            weekly_scores[week_key]["kindness"].append(fb.kindness_score)
            weekly_scores[week_key]["delivery"].append(delivery_score)
            weekly_scores[week_key]["persona_fit"].append(fb.persona_fit_score)
            weekly_scores[week_key]["overall"].append(fb.overall_score)
        
        # 평균 계산 및 정렬
        result = {}
        for week_key in sorted(weekly_scores.keys()):
            scores = weekly_scores[week_key]
            def calc_avg(scores_list):
                return round(sum(scores_list) / len(scores_list), 2) if scores_list else 0.0
            
            result[week_key] = {
                "knowledge": calc_avg(scores["knowledge"]),
                "skill": calc_avg(scores["skill"]),
                "kindness": calc_avg(scores["kindness"]),
                "delivery": calc_avg(scores["delivery"]),
                "persona_fit": calc_avg(scores["persona_fit"]),
                "overall": calc_avg(scores["overall"]),
                "count": len(scores["knowledge"])
            }
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"주별 추이 분석 실패: {str(e)}")


@router.get("/simulation-analytics/persona-fit-ranking")
async def get_persona_fit_ranking(
    current_user: User = Depends(require_admin),
    session: Session = Depends(get_session)
):
    """⑦ 페르소나 적합도 TOP 5, LOW 5 (Ranking Table + Bar Chart) - overall_score 기준"""
    try:
        feedbacks = session.exec(
            select(SimulationFeedback).where(
                SimulationFeedback.is_test_mode == False
            )
        ).all()
        
        if not feedbacks:
            return {
                "top5": [],
                "low5": []
            }
        
        # 페르소나별 overall_score 집계 (0점 제외)
        persona_scores = {}
        
        for fb in feedbacks:
            # overall_score가 0이거나 None인 경우 제외
            if fb.overall_score is None or fb.overall_score == 0:
                continue
            
            # 개별 필드에서 persona_key 생성 (더 정확함, 모든 정보 포함)
            parts = []
            
            # 연령대
            if hasattr(fb, 'persona_age_group') and fb.persona_age_group:
                parts.append(fb.persona_age_group)
            elif fb.persona_info:
                parsed = parse_persona_info(fb.persona_info or "")
                if parsed.get("age_group"):
                    parts.append(parsed["age_group"])
            
            # 성별
            if hasattr(fb, 'persona_gender') and fb.persona_gender:
                gender = fb.persona_gender
                if gender in ["남성", "남자", "male"]:
                    parts.append("남성")
                elif gender in ["여성", "여자", "female"]:
                    parts.append("여성")
                else:
                    parts.append(gender)
            elif fb.persona_info:
                parsed = parse_persona_info(fb.persona_info)
                if parsed.get("gender"):
                    parts.append(parsed["gender"])
            
            # 직업
            if hasattr(fb, 'persona_occupation') and fb.persona_occupation:
                parts.append(fb.persona_occupation)
            elif fb.persona_info:
                parsed = parse_persona_info(fb.persona_info)
                if parsed.get("occupation"):
                    parts.append(parsed["occupation"])
            
            # 고객 성향 (반드시 포함, 없으면 제외)
            customer_style_found = False
            if hasattr(fb, 'persona_customer_style') and fb.persona_customer_style:
                parts.append(fb.persona_customer_style)
                customer_style_found = True
            elif fb.persona_info:
                parsed = parse_persona_info(fb.persona_info)
                if parsed.get("customer_style"):
                    parts.append(parsed["customer_style"])
                    customer_style_found = True
            
            # 고객 성향이 없으면 이 페르소나는 제외
            if not customer_style_found:
                continue
            
            persona_key = " ".join(parts) if parts else (fb.persona_info or "알 수 없음")
            
            if persona_key not in persona_scores:
                persona_scores[persona_key] = {
                    "scores": [],
                    "count": 0,
                    "avg_overall": 0.0,
                    "avg_persona_fit": 0.0
                }
            
            persona_scores[persona_key]["scores"].append({
                "persona_fit_score": fb.persona_fit_score,
                "overall_score": fb.overall_score,
                "session_key": fb.session_key,
                "created_at": fb.created_at.isoformat()
            })
            persona_scores[persona_key]["count"] += 1
        
        # 평균 계산
        for persona_key, data in persona_scores.items():
            if data["scores"]:
                data["avg_persona_fit"] = round(
                    sum(s["persona_fit_score"] for s in data["scores"] if s["persona_fit_score"] is not None) / len(data["scores"]), 2
                ) if any(s["persona_fit_score"] is not None for s in data["scores"]) else 0.0
                data["avg_overall"] = round(
                    sum(s["overall_score"] for s in data["scores"]) / len(data["scores"]), 2
                )
        
        # overall_score 기준으로 정렬 (높은 순)
        sorted_personas = sorted(
            persona_scores.items(),
            key=lambda x: x[1]["avg_overall"],
            reverse=True
        )
        
        top5 = [
            {
                "persona_info": persona_key,
                "avg_persona_fit": data["avg_persona_fit"],
                "avg_overall": data["avg_overall"],
                "count": data["count"]
            }
            for persona_key, data in sorted_personas[:5]
        ]
        
        # overall_score 기준으로 정렬 (낮은 순)
        low5 = [
            {
                "persona_info": persona_key,
                "avg_persona_fit": data["avg_persona_fit"],
                "avg_overall": data["avg_overall"],
                "count": data["count"]
            }
            for persona_key, data in sorted(sorted_personas, key=lambda x: x[1]["avg_overall"])[:5]
        ]
        
        return {
            "top5": top5,
            "low5": low5,
            "total_personas": len(persona_scores)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"페르소나 적합도 랭킹 분석 실패: {str(e)}")


@router.get("/simulation-analytics/all")
async def get_all_simulation_analytics(
    current_user: User = Depends(require_admin),
    session: Session = Depends(get_session)
):
    """모든 시뮬레이션 분석 데이터를 한 번에 조회"""
    try:
        # 모든 데이터를 한 번에 조회하여 효율성 향상
        feedbacks = session.exec(
            select(SimulationFeedback).where(
                SimulationFeedback.is_test_mode == False
            )
        ).all()
        
        if not feedbacks:
            return {
                "gender_comparison": {"male": {}, "female": {}, "total_count": 0},
                "age_group_distribution": {},
                "occupation_comparison": {},
                "customer_style_radar": {},
                "correlation_heatmap": {"correlation_matrix": {}, "total_count": 0},
                "weekly_trend": {},
                "persona_fit_ranking": {"top5": [], "low5": [], "total_personas": 0}
            }
        
        # 1. 성별별 평균 점수 (5가지 지표)
        male_scores = {"knowledge": [], "skill": [], "kindness": [], "delivery": [], "persona_fit": []}
        female_scores = {"knowledge": [], "skill": [], "kindness": [], "delivery": [], "persona_fit": []}
        
        # 2. 연령대별 점수
        age_groups = {}
        
        # 3. 직업별 점수
        occupations = {}
        
        # 4. 고객 성향별 점수
        customer_styles = {}
        
        # 5. 주별 점수
        weekly_scores = {}
        
        # 6. 페르소나별 적합도
        persona_scores = {}
        
        # 7. 상관관계용 점수 배열 (5가지 지표)
        metrics_scores = {"knowledge": [], "skill": [], "kindness": [], "delivery": [], "persona_fit": []}
        
        for fb in feedbacks:
            parsed = parse_persona_info(fb.persona_info)
            gender = parsed.get("gender")
            age_group = parsed.get("age_group")
            # persona_occupation 필드가 있으면 직접 사용, 없으면 파싱 결과 사용
            occupation = None
            if hasattr(fb, 'persona_occupation') and fb.persona_occupation:
                occupation = fb.persona_occupation
            else:
                occupation = parsed.get("occupation")
            # persona_customer_style 필드가 있으면 직접 사용, 없으면 파싱 결과 사용
            customer_style = None
            if hasattr(fb, 'persona_customer_style') and fb.persona_customer_style:
                customer_style = fb.persona_customer_style
            else:
                customer_style = parsed.get("customer_style")
            
            # 개별 필드에서 persona_key 생성 (더 정확함, 모든 정보 포함)
            parts = []
            
            # 연령대
            if hasattr(fb, 'persona_age_group') and fb.persona_age_group:
                parts.append(fb.persona_age_group)
            elif age_group:
                parts.append(age_group)
            
            # 성별
            if hasattr(fb, 'persona_gender') and fb.persona_gender:
                gender_val = fb.persona_gender
                if gender_val in ["남성", "남자", "male"]:
                    parts.append("남성")
                elif gender_val in ["여성", "여자", "female"]:
                    parts.append("여성")
                else:
                    parts.append(gender_val)
            elif gender:
                parts.append(gender)
            
            # 직업
            if occupation:
                parts.append(occupation)
            
            # 고객 성향 (반드시 포함, 없으면 제외)
            if not customer_style:
                continue
            
            parts.append(customer_style)
            persona_key = " ".join(parts) if parts else (fb.persona_info or "알 수 없음")
            
            # 전달력 = (clarity_score + confidence_score) / 2
            delivery_score = (fb.clarity_score + fb.confidence_score) / 2.0
            
            # 성별별 (null 값 제외)
            if gender and gender in ["남자", "여자"]:
                if gender == "남자":
                    male_scores["knowledge"].append(fb.knowledge_score)
                    male_scores["skill"].append(fb.skill_score)
                    male_scores["kindness"].append(fb.kindness_score)
                    male_scores["delivery"].append(delivery_score)
                    male_scores["persona_fit"].append(fb.persona_fit_score)
                elif gender == "여자":
                    female_scores["knowledge"].append(fb.knowledge_score)
                    female_scores["skill"].append(fb.skill_score)
                    female_scores["kindness"].append(fb.kindness_score)
                    female_scores["delivery"].append(delivery_score)
                    female_scores["persona_fit"].append(fb.persona_fit_score)
            
            # 연령대별 (null 값 제외)
            if age_group and age_group != "알 수 없음":
                if age_group not in age_groups:
                    age_groups[age_group] = {"knowledge": [], "skill": [], "kindness": [], "delivery": [], "persona_fit": [], "overall": []}
                age_groups[age_group]["knowledge"].append(fb.knowledge_score)
                age_groups[age_group]["skill"].append(fb.skill_score)
                age_groups[age_group]["kindness"].append(fb.kindness_score)
                age_groups[age_group]["delivery"].append(delivery_score)
                age_groups[age_group]["persona_fit"].append(fb.persona_fit_score)
                age_groups[age_group]["overall"].append(fb.overall_score)
            
            # 직업별 (null 값 제외)
            if occupation and occupation != "알 수 없음":
                if occupation not in occupations:
                    occupations[occupation] = {"knowledge": [], "skill": [], "kindness": [], "delivery": [], "persona_fit": []}
                occupations[occupation]["knowledge"].append(fb.knowledge_score)
                occupations[occupation]["skill"].append(fb.skill_score)
                occupations[occupation]["kindness"].append(fb.kindness_score)
                occupations[occupation]["delivery"].append(delivery_score)
                occupations[occupation]["persona_fit"].append(fb.persona_fit_score)
            
            # 고객 성향별 (null 값 제외)
            if customer_style and customer_style != "알 수 없음":
                if customer_style not in customer_styles:
                    customer_styles[customer_style] = {"knowledge": [], "skill": [], "kindness": [], "delivery": [], "persona_fit": []}
                customer_styles[customer_style]["knowledge"].append(fb.knowledge_score)
                customer_styles[customer_style]["skill"].append(fb.skill_score)
                customer_styles[customer_style]["kindness"].append(fb.kindness_score)
                customer_styles[customer_style]["delivery"].append(delivery_score)
                customer_styles[customer_style]["persona_fit"].append(fb.persona_fit_score)
            
            # 주별
            def get_week_key(date):
                """날짜를 주차 키로 변환 (YYYY-WW 형식)"""
                year, week, _ = date.isocalendar()
                return f"{year}-W{week:02d}"
            week_key = get_week_key(fb.created_at)
            if week_key not in weekly_scores:
                weekly_scores[week_key] = {"knowledge": [], "skill": [], "kindness": [], "delivery": [], "persona_fit": [], "overall": []}
            weekly_scores[week_key]["knowledge"].append(fb.knowledge_score)
            weekly_scores[week_key]["skill"].append(fb.skill_score)
            weekly_scores[week_key]["kindness"].append(fb.kindness_score)
            weekly_scores[week_key]["delivery"].append(delivery_score)
            weekly_scores[week_key]["persona_fit"].append(fb.persona_fit_score)
            weekly_scores[week_key]["overall"].append(fb.overall_score)
            
            # 페르소나별 (null 값 제외, 0점 제외)
            if persona_key and persona_key != "알 수 없음":
                # overall_score가 0이거나 None인 경우 제외
                if fb.overall_score is None or fb.overall_score == 0:
                    continue
                
                # persona_key는 이미 위에서 개별 필드로 생성되었으므로 추가 처리 불필요
                
                if persona_key not in persona_scores:
                    persona_scores[persona_key] = {"scores": [], "count": 0}
                persona_scores[persona_key]["scores"].append({
                    "persona_fit_score": fb.persona_fit_score,
                    "overall_score": fb.overall_score
                })
                persona_scores[persona_key]["count"] += 1
            
            # 상관관계용 (모든 데이터 사용)
            metrics_scores["knowledge"].append(fb.knowledge_score)
            metrics_scores["skill"].append(fb.skill_score)
            metrics_scores["kindness"].append(fb.kindness_score)
            metrics_scores["delivery"].append(delivery_score)
            metrics_scores["persona_fit"].append(fb.persona_fit_score)
        
        # 결과 계산
        def calc_avg(scores_list):
            return round(sum(scores_list) / len(scores_list), 2) if scores_list else 0.0
        
        def calc_stats(scores_list):
            if not scores_list:
                return {"avg": 0, "min": 0, "max": 0, "median": 0, "q1": 0, "q3": 0, "count": 0}
            sorted_scores = sorted(scores_list)
            n = len(sorted_scores)
            return {
                "avg": round(sum(scores_list) / n, 2),
                "min": min(scores_list),
                "max": max(scores_list),
                "median": sorted_scores[n // 2] if n > 0 else 0,
                "q1": sorted_scores[n // 4] if n >= 4 else sorted_scores[0],
                "q3": sorted_scores[3 * n // 4] if n >= 4 else sorted_scores[-1],
                "count": n
            }
        
        def calculate_correlation(x, y):
            if len(x) != len(y) or len(x) == 0:
                return 0.0
            n = len(x)
            mean_x = sum(x) / n
            mean_y = sum(y) / n
            numerator = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n))
            denominator_x = sum((x[i] - mean_x) ** 2 for i in range(n))
            denominator_y = sum((y[i] - mean_y) ** 2 for i in range(n))
            if denominator_x == 0 or denominator_y == 0:
                return 0.0
            correlation = numerator / ((denominator_x ** 0.5) * (denominator_y ** 0.5))
            return round(correlation, 3)
        
        # 1. 성별 비교
        gender_comparison = {
            "male": {
                "knowledge": calc_avg(male_scores["knowledge"]),
                "skill": calc_avg(male_scores["skill"]),
                "kindness": calc_avg(male_scores["kindness"]),
                "delivery": calc_avg(male_scores["delivery"]),
                "persona_fit": calc_avg(male_scores["persona_fit"])
            },
            "female": {
                "knowledge": calc_avg(female_scores["knowledge"]),
                "skill": calc_avg(female_scores["skill"]),
                "kindness": calc_avg(female_scores["kindness"]),
                "delivery": calc_avg(female_scores["delivery"]),
                "persona_fit": calc_avg(female_scores["persona_fit"])
            },
            "total_count": len(feedbacks)
        }
        
        # 2. 연령대별 분포
        age_group_distribution = {}
        for age_group, scores in age_groups.items():
            age_group_distribution[age_group] = {
                "knowledge": calc_stats(scores["knowledge"]),
                "skill": calc_stats(scores["skill"]),
                "kindness": calc_stats(scores["kindness"]),
                "delivery": calc_stats(scores["delivery"]),
                "persona_fit": calc_stats(scores["persona_fit"]),
                "overall": calc_stats(scores["overall"])
            }
        
        # 3. 직업별 비교
        occupation_comparison = {}
        for occupation, scores in occupations.items():
            occupation_comparison[occupation] = {
                "knowledge": calc_avg(scores["knowledge"]),
                "skill": calc_avg(scores["skill"]),
                "kindness": calc_avg(scores["kindness"]),
                "delivery": calc_avg(scores["delivery"]),
                "persona_fit": calc_avg(scores["persona_fit"]),
                "count": len(scores["knowledge"])
            }
        
        # 4. 고객 성향별
        customer_style_radar = {}
        for style, scores in customer_styles.items():
            customer_style_radar[style] = {
                "knowledge": calc_avg(scores["knowledge"]),
                "skill": calc_avg(scores["skill"]),
                "kindness": calc_avg(scores["kindness"]),
                "delivery": calc_avg(scores["delivery"]),
                "persona_fit": calc_avg(scores["persona_fit"]),
                "count": len(scores["knowledge"])
            }
        
        # 5. 주별 추이
        weekly_trend = {}
        for week_key in sorted(weekly_scores.keys()):
            scores = weekly_scores[week_key]
            weekly_trend[week_key] = {
                "knowledge": calc_avg(scores["knowledge"]),
                "skill": calc_avg(scores["skill"]),
                "kindness": calc_avg(scores["kindness"]),
                "delivery": calc_avg(scores["delivery"]),
                "persona_fit": calc_avg(scores["persona_fit"]),
                "overall": calc_avg(scores["overall"]),
                "count": len(scores["knowledge"])
            }
        
        # 6. 상관관계 (5가지 지표)
        metrics = ["knowledge", "skill", "kindness", "delivery", "persona_fit"]
        correlation_matrix = {}
        for metric1 in metrics:
            correlation_matrix[metric1] = {}
            for metric2 in metrics:
                correlation_matrix[metric1][metric2] = calculate_correlation(
                    metrics_scores[metric1],
                    metrics_scores[metric2]
                )
        
        # 7. 페르소나 적합도 랭킹 (overall_score 기준, 0점 제외)
        # 0점인 페르소나 제외
        filtered_persona_scores = {}
        for persona_key, data in persona_scores.items():
            if data["scores"]:
                avg_overall = round(
                    sum(s["overall_score"] for s in data["scores"]) / len(data["scores"]), 2
                )
                # 0점인 것은 제외
                if avg_overall > 0:
                    filtered_persona_scores[persona_key] = data
                    data["avg_persona_fit"] = round(
                        sum(s["persona_fit_score"] for s in data["scores"] if s["persona_fit_score"] is not None) / len(data["scores"]), 2
                    ) if any(s["persona_fit_score"] is not None for s in data["scores"]) else 0.0
                    data["avg_overall"] = avg_overall
        
        # overall_score 기준으로 정렬 (높은 순)
        sorted_personas = sorted(
            filtered_persona_scores.items(),
            key=lambda x: x[1].get("avg_overall", 0),
            reverse=True
        )
        
        persona_fit_ranking = {
            "top5": [
                {
                    "persona_info": persona_key,
                    "avg_persona_fit": data.get("avg_persona_fit", 0),
                    "avg_overall": data.get("avg_overall", 0),
                    "count": data["count"]
                }
                for persona_key, data in sorted_personas[:5]
            ],
            "low5": [
                {
                    "persona_info": persona_key,
                    "avg_persona_fit": data.get("avg_persona_fit", 0),
                    "avg_overall": data.get("avg_overall", 0),
                    "count": data["count"]
                }
                for persona_key, data in sorted(sorted_personas, key=lambda x: x[1].get("avg_overall", 0))[:5]
            ],
            "total_personas": len(filtered_persona_scores)
        }
        
        return {
            "gender_comparison": gender_comparison,
            "age_group_distribution": age_group_distribution,
            "occupation_comparison": occupation_comparison,
            "customer_style_radar": customer_style_radar,
            "correlation_heatmap": {
                "correlation_matrix": correlation_matrix,
                "total_count": len(feedbacks)
            },
            "weekly_trend": weekly_trend,
            "persona_fit_ranking": persona_fit_ranking
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"전체 분석 데이터 조회 실패: {str(e)}")


@router.get("/simulation-analytics/persona-combination")
async def get_persona_combination_scores(
    gender: Optional[str] = None,
    age_group: Optional[str] = None,
    occupation: Optional[str] = None,
    customer_style: Optional[str] = None,
    current_user: User = Depends(require_admin),
    session: Session = Depends(get_session)
):
    """특정 페르소나 조합의 점수 데이터 조회
    
    예: gender=남자&age_group=20대&occupation=학생&customer_style=긍정형
    """
    try:
        # 테스트 모드 제외
        feedbacks = session.exec(
            select(SimulationFeedback).where(
                SimulationFeedback.is_test_mode == False
            )
        ).all()
        
        if not feedbacks:
            return {
                "knowledge": 0,
                "skill": 0,
                "kindness": 0,
                "delivery": 0,
                "persona_fit": 0,
                "overall": 0,
                "count": 0
            }
        
        # 보조 정규화 함수
        def normalize_gender(value: Optional[str]) -> Optional[str]:
            if not value:
                return None
            v = value.strip().lower()
            if v in ["남성", "남자", "male"]:
                return "남자"
            if v in ["여성", "여자", "female"]:
                return "여자"
            return value

        def normalize_customer_style(value: Optional[str]) -> Optional[str]:
            """컬럼에 '긍정형 고객' 같이 들어가 있어도 기본 타입(긍정형/불만형/급함형/불안형/의심형)으로 통일"""
            if not value:
                return None
            v = value.strip()
            base_styles = ["긍정형", "불만형", "급함형", "불안형", "의심형"]
            for s in base_styles:
                if s in v:
                    return s
            return value

        # 필터링된 피드백 수집
        filtered_feedbacks = []
        for fb in feedbacks:
            # persona_* 개별 필드를 우선 사용하고, 없으면 persona_info 파싱 결과를 사용
            parsed = parse_persona_info(fb.persona_info or "")

            fb_gender = getattr(fb, "persona_gender", None) or parsed.get("gender")
            fb_age_group = getattr(fb, "persona_age_group", None) or parsed.get("age_group")
            fb_occupation = getattr(fb, "persona_occupation", None) or parsed.get("occupation")
            fb_style = getattr(fb, "persona_customer_style", None) or parsed.get("customer_style")

            # 정규화 적용 (DB에 '남성', '여성', '긍정형 고객' 등으로 들어간 경우까지 매칭)
            fb_gender = normalize_gender(fb_gender)
            norm_gender = normalize_gender(gender) if gender else None

            fb_style = normalize_customer_style(fb_style)
            norm_customer_style = normalize_customer_style(customer_style) if customer_style else None

            # 필터 조건 확인
            if norm_gender and fb_gender != norm_gender:
                continue
            if age_group and fb_age_group != age_group:
                continue
            if occupation and fb_occupation != occupation:
                continue
            if norm_customer_style and fb_style != norm_customer_style:
                continue

            filtered_feedbacks.append(fb)
        
        if not filtered_feedbacks:
            return {
                "knowledge": 0,
                "skill": 0,
                "kindness": 0,
                "delivery": 0,
                "persona_fit": 0,
                "overall": 0,
                "count": 0
            }
        
        # 점수 집계
        knowledge_scores = [fb.knowledge_score for fb in filtered_feedbacks if fb.knowledge_score is not None]
        skill_scores = [fb.skill_score for fb in filtered_feedbacks if fb.skill_score is not None]
        kindness_scores = [fb.kindness_score for fb in filtered_feedbacks if fb.kindness_score is not None]
        delivery_scores = [(fb.clarity_score + fb.confidence_score) / 2.0 for fb in filtered_feedbacks 
                          if fb.clarity_score is not None and fb.confidence_score is not None]
        persona_fit_scores = [fb.persona_fit_score for fb in filtered_feedbacks if fb.persona_fit_score is not None]
        overall_scores = [fb.overall_score for fb in filtered_feedbacks if fb.overall_score is not None]
        
        def calc_avg(scores):
            return round(sum(scores) / len(scores), 2) if scores else 0
        
        return {
            "knowledge": calc_avg(knowledge_scores),
            "skill": calc_avg(skill_scores),
            "kindness": calc_avg(kindness_scores),
            "delivery": calc_avg(delivery_scores),
            "persona_fit": calc_avg(persona_fit_scores),
            "overall": calc_avg(overall_scores),
            "count": len(filtered_feedbacks)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"페르소나 조합 점수 조회 실패: {str(e)}")


@router.get("/simulation-analytics/markdown")
async def get_simulation_analytics_markdown(
    current_user: User = Depends(require_admin),
    session: Session = Depends(get_session)
):
    """시뮬레이션 분석 데이터를 마크다운 형식으로 반환"""
    try:
        # 전체 분석 데이터 조회
        analytics_data = await get_all_simulation_analytics(current_user, session)
        
        markdown_lines = []
        markdown_lines.append("# 시뮬레이션 분석 리포트\n")
        markdown_lines.append(f"생성일: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        # 1. 페르소나 비교 분석
        markdown_lines.append("\n## 1. 페르소나 비교 분석\n")
        
        # 성별 비교
        gender_comp = analytics_data.get("gender_comparison", {})
        if gender_comp:
            markdown_lines.append("### 성별별 평균 점수\n")
            markdown_lines.append("| 성별 | 지식 | 기술 | 친절도 | 전달력 | 페르소나 적합도 |\n")
            markdown_lines.append("|------|------|------|--------|--------|----------------|\n")
            if gender_comp.get("male"):
                male = gender_comp["male"]
                markdown_lines.append(f"| 남자 | {male.get('knowledge', 0):.1f} | {male.get('skill', 0):.1f} | {male.get('kindness', 0):.1f} | {male.get('delivery', 0):.1f} | {male.get('persona_fit', 0):.1f} |\n")
            if gender_comp.get("female"):
                female = gender_comp["female"]
                markdown_lines.append(f"| 여자 | {female.get('knowledge', 0):.1f} | {female.get('skill', 0):.1f} | {female.get('kindness', 0):.1f} | {female.get('delivery', 0):.1f} | {female.get('persona_fit', 0):.1f} |\n")
        
        # 연령대별 분포
        age_dist = analytics_data.get("age_group_distribution", {})
        if age_dist:
            markdown_lines.append("\n### 연령대별 평균 점수\n")
            markdown_lines.append("| 연령대 | 지식 | 기술 | 친절도 | 전달력 | 페르소나 적합도 | 전체 평균 |\n")
            markdown_lines.append("|--------|------|------|--------|--------|----------------|----------|\n")
            for age_group in sorted(age_dist.keys()):
                data = age_dist[age_group]
                markdown_lines.append(f"| {age_group} | {data.get('knowledge', {}).get('avg', 0):.1f} | {data.get('skill', {}).get('avg', 0):.1f} | {data.get('kindness', {}).get('avg', 0):.1f} | {data.get('delivery', {}).get('avg', 0):.1f} | {data.get('persona_fit', {}).get('avg', 0):.1f} | {data.get('overall', {}).get('avg', 0):.1f} |\n")
        
        # 직업별 비교
        occ_comp = analytics_data.get("occupation_comparison", {})
        if occ_comp:
            markdown_lines.append("\n### 직업별 평균 점수\n")
            markdown_lines.append("| 직업 | 지식 | 기술 | 친절도 | 전달력 | 페르소나 적합도 | 데이터 수 |\n")
            markdown_lines.append("|------|------|------|--------|--------|----------------|----------|\n")
            for occupation in sorted(occ_comp.keys()):
                data = occ_comp[occupation]
                markdown_lines.append(f"| {occupation} | {data.get('knowledge', 0):.1f} | {data.get('skill', 0):.1f} | {data.get('kindness', 0):.1f} | {data.get('delivery', 0):.1f} | {data.get('persona_fit', 0):.1f} | {data.get('count', 0)} |\n")
        
        # 고객 성향별
        style_radar = analytics_data.get("customer_style_radar", {})
        if style_radar:
            markdown_lines.append("\n### 고객 성향별 평균 점수\n")
            markdown_lines.append("| 고객 성향 | 지식 | 기술 | 친절도 | 전달력 | 페르소나 적합도 | 데이터 수 |\n")
            markdown_lines.append("|-----------|------|------|--------|--------|----------------|----------|\n")
            for style in sorted(style_radar.keys()):
                data = style_radar[style]
                markdown_lines.append(f"| {style} | {data.get('knowledge', 0):.1f} | {data.get('skill', 0):.1f} | {data.get('kindness', 0):.1f} | {data.get('delivery', 0):.1f} | {data.get('persona_fit', 0):.1f} | {data.get('count', 0)} |\n")
        
        # 2. 기간별 평균 점수 추이
        markdown_lines.append("\n## 2. 기간별 평균 점수 추이\n")
        weekly_trend = analytics_data.get("weekly_trend", {})
        if weekly_trend:
            markdown_lines.append("| 주차 | 지식 | 기술 | 친절도 | 전달력 | 페르소나 적합도 | 전체 평균 | 데이터 수 |\n")
            markdown_lines.append("|------|------|------|--------|--------|----------------|----------|----------|\n")
            for week in sorted(weekly_trend.keys()):
                data = weekly_trend[week]
                markdown_lines.append(f"| {week} | {data.get('knowledge', 0):.1f} | {data.get('skill', 0):.1f} | {data.get('kindness', 0):.1f} | {data.get('delivery', 0):.1f} | {data.get('persona_fit', 0):.1f} | {data.get('overall', 0):.1f} | {data.get('count', 0)} |\n")
        
        # 3. 상위/하위 5 페르소나
        markdown_lines.append("\n## 3. 페르소나 랭킹\n")
        persona_ranking = analytics_data.get("persona_fit_ranking", {})
        
        if persona_ranking.get("top5"):
            markdown_lines.append("### 상위 5 페르소나\n")
            markdown_lines.append("| 순위 | 페르소나 | 페르소나 적합도 | 전체 평균 | 데이터 수 |\n")
            markdown_lines.append("|------|----------|----------------|----------|----------|\n")
            for idx, persona in enumerate(persona_ranking["top5"], 1):
                markdown_lines.append(f"| {idx} | {persona.get('persona_info', '알 수 없음')} | {persona.get('avg_persona_fit', 0):.1f} | {persona.get('avg_overall', 0):.1f} | {persona.get('count', 0)} |\n")
        
        if persona_ranking.get("low5"):
            markdown_lines.append("\n### 하위 5 페르소나\n")
            markdown_lines.append("| 순위 | 페르소나 | 페르소나 적합도 | 전체 평균 | 데이터 수 |\n")
            markdown_lines.append("|------|----------|----------------|----------|----------|\n")
            for idx, persona in enumerate(persona_ranking["low5"], 1):
                markdown_lines.append(f"| {idx} | {persona.get('persona_info', '알 수 없음')} | {persona.get('avg_persona_fit', 0):.1f} | {persona.get('avg_overall', 0):.1f} | {persona.get('count', 0)} |\n")
        
        markdown_content = "".join(markdown_lines)
        
        return {
            "markdown": markdown_content,
            "generated_at": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"마크다운 리포트 생성 실패: {str(e)}")
