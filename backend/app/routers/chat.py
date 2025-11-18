"""
챗봇 API 라우터
RAG 기반 대화 처리
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from pydantic import BaseModel
from typing import List, Dict, Optional

from app.database import get_session
from app.models.user import User
from app.utils.auth import get_current_user
from app.services.rag_service import RAGService

router = APIRouter(prefix="/chat", tags=["Chatbot"])


class ChatRequest(BaseModel):
    """채팅 요청 모델"""
    message: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    """채팅 응답 모델"""
    answer: str
    sources: List[Dict]
    response_time: float
    model: Optional[str] = None
    provider: Optional[str] = None


class ChatHistoryItem(BaseModel):
    """채팅 기록 항목"""
    user_message: str
    bot_response: str
    created_at: str
    sources: List[Dict]


@router.post("/", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    챗봇과 대화하기
    - RAG 기반 답변 생성
    - 관련 문서 검색
    - 대화 기록 저장
    """
    try:
        # 일정 관련 요청인지 확인
        schedule_service = ScheduleChatService(session)
        action_type = schedule_service.get_schedule_action_type(request.message)
        
        if action_type == "create":
            # 일정 추가
            schedule_info = schedule_service.extract_schedule_info(request.message)
            
            if schedule_info:
                schedule = schedule_service.create_schedule(schedule_info, current_user)
                answer = schedule_service.format_schedule_response(schedule, "create")
                
                return ChatResponse(
                    answer=answer,
                    sources=[],
                    response_time=0.5,
                    model="schedule_service",
                    provider="internal"
                )
            else:
                return ChatResponse(
                    answer="죄송합니다. 일정 정보를 제대로 이해하지 못했습니다. 다시 말씀해주시겠어요?\n\n예시: \"내일 오후 2시에 회의 일정 추가해줘\"",
                    sources=[],
                    response_time=0.3,
                    model="schedule_service",
                    provider="internal"
                )
        
        elif action_type == "delete":
            # 일정 삭제
            schedule = schedule_service.delete_schedule(request.message, current_user)
            
            if schedule:
                answer = schedule_service.format_schedule_response(schedule, "delete")
                return ChatResponse(
                    answer=answer,
                    sources=[],
                    response_time=0.3,
                    model="schedule_service",
                    provider="internal"
                )
            else:
                return ChatResponse(
                    answer="❌ 삭제할 일정을 찾을 수 없습니다. 일정 제목이나 날짜를 포함해서 다시 말씀해주세요.\n\n예시: \"점심식사 일정 삭제해줘\" 또는 \"11월 18일 일정 지워줘\"",
                    sources=[],
                    response_time=0.3,
                    model="schedule_service",
                    provider="internal"
                )
        
        elif action_type == "update":
            # 일정 수정
            result = schedule_service.update_schedule(request.message, current_user)
            
            if result and result.get("schedule"):
                schedule = result["schedule"]
                answer = schedule_service.format_schedule_response(schedule, "update")
                return ChatResponse(
                    answer=answer,
                    sources=[],
                    response_time=0.4,
                    model="schedule_service",
                    provider="internal"
                )
            else:
                return ChatResponse(
                    answer="❌ 수정할 일정을 찾을 수 없거나 수정할 정보를 이해하지 못했습니다.\n\n예시: \"점심식사 일정을 오후 3시로 변경해줘\"",
                    sources=[],
                    response_time=0.3,
                    model="schedule_service",
                    provider="internal"
                )
        
        elif action_type == "list":
            # 일정 목록 조회
            schedules = schedule_service.list_schedules(current_user, limit=10)
            answer = schedule_service.format_schedule_list_response(schedules)
            
            return ChatResponse(
                answer=answer,
                sources=[],
                response_time=0.2,
                model="schedule_service",
                provider="internal"
            )
        
        elif action_type == "query":
            # 특정 일정 검색 (예: "오늘 회의 몇시야?")
            schedules = schedule_service.query_schedules(request.message, current_user)
            answer = schedule_service.format_schedule_query_response(schedules, request.message)
            
            return ChatResponse(
                answer=answer,
                sources=[],
                response_time=0.3,
                model="schedule_service",
                provider="internal"
            )
        
        # 일반 RAG 처리
        rag_service = RAGService(session)
        
        # RAG로 답변 생성
        result = await rag_service.process_query(
            request.message,
            user_id=current_user.id if current_user else None,
        )
        
        return ChatResponse(
            answer=result["answer"],
            sources=result["sources"],
            response_time=result["response_time"],
            model=result.get("model"),
            provider=result.get("provider"),
        )
    
    except Exception as e:
        print(f"Chat error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate response: {str(e)}"
        )


@router.get("/history", response_model=List[ChatHistoryItem])
async def get_chat_history(
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    사용자의 채팅 기록 조회
    """
    # 간단한 구현 - 빈 리스트 반환
    return []


@router.post("/feedback/{chat_id}")
async def provide_feedback(
    chat_id: int,
    is_helpful: bool,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    챗봇 답변에 대한 피드백 제공
    """
    from app.models.mentor import ChatHistory
    from sqlmodel import select
    
    statement = select(ChatHistory).where(
        ChatHistory.id == chat_id,
        ChatHistory.user_id == current_user.id
    )
    chat = session.exec(statement).first()
    
    if not chat:
        raise HTTPException(
            status_code=404,
            detail="Chat history not found"
        )
    
    chat.is_helpful = is_helpful
    session.add(chat)
    session.commit()
    
    return {"message": "Feedback recorded"}


@router.post("/test", response_model=ChatResponse)
async def test_chat(
    request: ChatRequest,
    session: Session = Depends(get_session)
):
    """
    테스트용 챗봇 엔드포인트 (인증 없음)
    """
    try:
        rag_service = RAGService(session)
        result = await rag_service.process_query(request.message)
        
        return ChatResponse(
            answer=result["answer"],
            sources=result["sources"],
            response_time=result["response_time"],
            model=result.get("model"),
            provider=result.get("provider"),
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Chat processing error: {str(e)}"
        )

