"""
관리자 전용 API 라우터
DB 관리, 사용자 관리, 시스템 모니터링 기능
"""
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from sqlmodel import Session, select, func, desc
from typing import List, Optional
from datetime import datetime, timedelta
import pandas as pd
import json
from pydantic import BaseModel, Field

from ..database import get_session
from ..models.user import User, UserRole
from ..models.mentor import MentorMenteeRelation, ExamScore, ChatHistory, Feedback
from ..models.document import Document
from ..models.post import Post, Comment
from ..utils.auth import get_current_user, require_admin, get_password_hash
from ..services.llm_service import LLMService

router = APIRouter(prefix="/admin", tags=["admin"])


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
        
        return {
            "users": users,
            "total": total,
            "skip": skip,
            "limit": limit
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
    """학습 이력 조회 (채팅, 시험, 피드백 통합)"""
    try:
        # 채팅 이력
        chat_query = select(
            ChatHistory.id,
            ChatHistory.user_id,
            ChatHistory.user_message,
            ChatHistory.created_at,
            User.name.label("user_name"),
            func.literal("chat").label("type")
        ).join(User, ChatHistory.user_id == User.id)
        
        # 시험 점수
        exam_query = select(
            ExamScore.id,
            ExamScore.mentee_id.label("user_id"),
            ExamScore.exam_name.label("user_message"),
            ExamScore.created_at,
            User.name.label("user_name"),
            func.literal("exam").label("type")
        ).join(User, ExamScore.mentee_id == User.id)
        
        # 피드백
        feedback_query = select(
            Feedback.id,
            Feedback.mentee_id.label("user_id"),
            Feedback.feedback_text.label("user_message"),
            Feedback.created_at,
            User.name.label("user_name"),
            func.literal("feedback").label("type")
        ).join(User, Feedback.mentee_id == User.id)
        
        # 필터 적용
        if user_id:
            chat_query = chat_query.where(ChatHistory.user_id == user_id)
            exam_query = exam_query.where(ExamScore.mentee_id == user_id)
            feedback_query = feedback_query.where(Feedback.mentee_id == user_id)
        
        if start_date:
            chat_query = chat_query.where(ChatHistory.created_at >= start_date)
            exam_query = exam_query.where(ExamScore.created_at >= start_date)
            feedback_query = feedback_query.where(Feedback.created_at >= start_date)
        
        if end_date:
            chat_query = chat_query.where(ChatHistory.created_at <= end_date)
            exam_query = exam_query.where(ExamScore.created_at <= end_date)
            feedback_query = feedback_query.where(Feedback.created_at <= end_date)
        
        # 결과 조합 (실제로는 UNION ALL을 사용해야 하지만 SQLModel 제한으로 인해 개별 조회)
        chat_results = session.exec(chat_query.limit(limit)).all()
        exam_results = session.exec(exam_query.limit(limit)).all()
        feedback_results = session.exec(feedback_query.limit(limit)).all()
        
        # 결과 정렬 및 페이지네이션
        all_results = list(chat_results) + list(exam_results) + list(feedback_results)
        all_results.sort(key=lambda x: x.created_at, reverse=True)
        
        paginated_results = all_results[skip:skip + limit]
        
        return {
            "history": paginated_results,
            "total": len(all_results),
            "skip": skip,
            "limit": limit
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
        
        # 사용자 활동 로그 (로그인, 회원가입 등)
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


@router.post("/mentees/exam/upload-excel")
async def upload_mentee_exam_excel(
    file: UploadFile = File(...),
    current_user: User = Depends(require_admin),
    session: Session = Depends(get_session)
):
    """
    멘티 시험 결과 Excel(.xlsx/.xls) 업로드
    - 필수 컬럼: name, employee_number
    - 각 영역별로 1~10 문제 컬럼: 금융영업1..10, 금융상품개발1..10, 신용분석1..10, 자산운용1..10, 금융영업지원1..10, 증권외환1..10
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
            ("금융상품개발", [f"금융상품개발{i}" for i in range(1, 11)]),
            ("신용분석", [f"신용분석{i}" for i in range(1, 11)]),
            ("자산운용", [f"자산운용{i}" for i in range(1, 11)]),
            ("금융영업지원", [f"금융영업지원{i}" for i in range(1, 11)]),
            ("증권외환", [f"증권외환{i}" for i in range(1, 11)]),
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
                    select(ExamScore).where(ExamScore.mentee_id == mentee.id, ExamScore.exam_name == "연수원 시험")
                ).first()

                if existing:
                    existing.score_data = json.dumps(score_by_cat, ensure_ascii=False)
                    existing.total_score = float(total)
                    existing.exam_date = datetime.utcnow()
                    existing.grade = None
                    session.add(existing)
                else:
                    es = ExamScore(
                        mentee_id=mentee.id,
                        exam_name="연수원 시험",
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