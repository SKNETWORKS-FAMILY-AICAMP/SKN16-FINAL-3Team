"""
챗봇 API 라우터
RAG 기반 대화 처리
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from pydantic import BaseModel
from typing import List, Dict, Optional
import re

from app.database import get_session
from app.models.user import User
from app.utils.auth import get_current_user
from app.services.rag_service import RAGService
from app.services.schedule_chat_service import ScheduleChatService
from app.services.learning_progress_chat_service import LearningProgressChatService

router = APIRouter(prefix="/chat", tags=["Chatbot"])

# 대화 상태 저장소 (user_id -> pending_action)
pending_actions: Dict[int, Dict] = {}


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
    - 일정 추가 요청 처리
    - RAG 기반 답변 생성
    - 관련 문서 검색
    - 대화 기록 저장
    """
    try:
        schedule_service = ScheduleChatService(session)
        
        # 1. Pending action 확인 (이전 대화에서 시간을 물어봤는지)
        user_pending = pending_actions.get(current_user.id)
        
        if user_pending and user_pending.get("action") == "schedule_create_pending":
            # 시간 정보 추출 시도
            time_info = schedule_service.extract_time_from_message(request.message)
            
            if time_info:
                # pending 정보와 시간 정보 병합
                schedule_info = user_pending.get("schedule_info", {})
                
                # 날짜 정보는 유지하고 시간만 업데이트
                from datetime import datetime
                pending_start = schedule_info.get("start_time")
                if pending_start and isinstance(pending_start, datetime):
                    # 기존 날짜에 새로운 시간 적용
                    new_start_time = time_info["start_time"]
                    schedule_info["start_time"] = pending_start.replace(
                        hour=new_start_time.hour,
                        minute=new_start_time.minute
                    )
                    if time_info.get("end_time"):
                        new_end_time = time_info["end_time"]
                        schedule_info["end_time"] = pending_start.replace(
                            hour=new_end_time.hour,
                            minute=new_end_time.minute
                        )
                else:
                    # 날짜 정보가 없으면 시간 정보 그대로 사용
                    schedule_info["start_time"] = time_info["start_time"]
                    schedule_info["end_time"] = time_info.get("end_time")
                
                # 일정 생성
                schedule = schedule_service.create_schedule(schedule_info, current_user)
                answer = schedule_service.format_schedule_response(schedule, "create")
                
                # pending 상태 제거
                del pending_actions[current_user.id]
                
                return ChatResponse(
                    answer=answer,
                    sources=[],
                    response_time=0.5,
                    model="schedule_service",
                    provider="internal"
                )
            else:
                # 여전히 시간 정보를 이해 못함
                return ChatResponse(
                    answer="시간을 정확히 이해하지 못했습니다. 다시 말씀해주시겠어요?\n\n예시: \"오후 2시\", \"14시\", \"2시 30분\"",
                    sources=[],
                    response_time=0.3,
                    model="schedule_service",
                    provider="internal"
                )
        
        # 2. 일정 관련 요청인지 확인
        action_type = schedule_service.get_schedule_action_type(request.message)
        
        if action_type == "create":
            # 일정 추가
            schedule_info = schedule_service.extract_schedule_info(request.message)
            
            print(f"🔍 [일정 생성] schedule_info: {schedule_info}")
            
            if schedule_info:
                # 시간 정보가 명시적으로 제공되었는지 확인
                has_time = schedule_info.get("has_explicit_time", False)
                
                print(f"⏰ [일정 생성] has_explicit_time: {has_time}")
                
                if not has_time:
                    # 시간이 없으면 물어보고 pending 상태로 저장
                    pending_actions[current_user.id] = {
                        "action": "schedule_create_pending",
                        "schedule_info": schedule_info,
                        "message": request.message
                    }
                    
                    # 날짜와 제목 정보로 응답 생성
                    from datetime import datetime
                    date_info = schedule_info.get("start_time")
                    if date_info and isinstance(date_info, datetime):
                        date_str = date_info.strftime("%m월 %d일")
                    else:
                        date_str = "해당 날짜"
                    
                    title = schedule_info.get("title", "일정")
                    
                    answer = f"📅 {date_str}에 '{title}' 일정을 추가하시는군요!\n\n⏰ 몇 시에 잡아드릴까요?\n\n예시: \"오후 2시\", \"14시\", \"오후 2시 30분\""
                    
                    return ChatResponse(
                        answer=answer,
                        sources=[],
                        response_time=0.4,
                        model="schedule_service",
                        provider="internal"
                    )
                else:
                    # 시간 정보가 있으면 바로 생성
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
        
        # 학습현황 및 시뮬레이션 관련 요청인지 확인
        learning_service = LearningProgressChatService(session)
        if learning_service.is_learning_progress_query(request.message):
            # 학습현황 분석 및 응답 생성 (시뮬레이션도 포함)
            import time
            from app.models.mentor import ChatHistory
            from sqlmodel import select
            
            start_time = time.time()
            
            # 최근 대화 히스토리 조회 (맥락 파악용)
            history_statement = (
                select(ChatHistory)
                .where(ChatHistory.user_id == current_user.id)
                .order_by(ChatHistory.created_at.desc())
                .limit(5)
            )
            recent_histories = list(session.exec(history_statement).all())
            context_history = [
                {
                    "user_message": h.user_message or "",
                    "bot_response": h.bot_response or "",
                    "created_at": h.created_at.isoformat() if h.created_at else ""
                }
                for h in recent_histories
            ]
            
            answer = learning_service.generate_response(current_user, request.message, context_history)
            
            response_time = time.time() - start_time
            
            # 대화 기록 저장
            try:
                chat_history = ChatHistory(
                    user_id=current_user.id,
                    user_message=request.message,
                    bot_response=answer,
                    source_documents=None,  # 학습현황 서비스는 문서 참조 없음
                    response_time=response_time
                )
                session.add(chat_history)
                session.commit()
                print(f"✅ [대화 기록 저장] 사용자 {current_user.id}의 대화 저장 완료")
            except Exception as e:
                print(f"❌ [대화 기록 저장 오류] {str(e)}")
                session.rollback()
                # 저장 실패해도 응답은 반환
            
            return ChatResponse(
                answer=answer,
                sources=[],
                response_time=response_time,
                model="learning_progress_service",
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

