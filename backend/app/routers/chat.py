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
        rag_service = RAGService(session)
        
        # RAG로 답변 생성
        result = await rag_service.process_query(request.message)
        
        return ChatResponse(
            answer=result["answer"],
            sources=result["sources"],
            response_time=result["response_time"]
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
            response_time=result["response_time"]
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Chat processing error: {str(e)}"
        )

