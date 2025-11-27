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
        
        # 1. Pending action 확인 (이전 대화에서 시간 또는 요일을 물어봤는지)
        # 우선 pending 플로우(시간 추가)인지부터 확인
        # - 이전에 날짜/제목은 정해져 있고, 이번 메시지로 '시간만' 받는 케이스
        user_pending = pending_actions.get(current_user.id)
        
        if user_pending and user_pending.get("action") == "schedule_create_pending":
            # 시간 정보 추출 시도
            time_info = schedule_service.extract_time_from_message(request.message)
            
            if time_info is None:
                return ChatResponse(
                    answer="시간 표현을 잘 못 알아들었어요. 예: `오후 2시`, `3시 30분`처럼 말해주세요.",
                    sources=[],
                    response_time=0.3,
                    model="schedule_service",
                    provider="internal"
                )
            
            # pending 에는 date 가 들어 있고, time_info 에는 start_time(datetime)이 들어 있음
            # → 날짜는 pending.date, 시간은 time_info.start_time의 hour/minute를 사용해서 다시 합치기
            from datetime import datetime, date
            hour = time_info["start_time"].hour
            minute = time_info["start_time"].minute
            
            schedule_info = user_pending.get("schedule_info", {})
            date_obj = schedule_info.get("date")
            
            if not date_obj:
                # 안전장치: date 가 없으면 오늘 기준으로
                date_obj = datetime.now().date()
            
            # date 객체인지 확인
            if isinstance(date_obj, datetime):
                date_obj = date_obj.date()
            elif not isinstance(date_obj, date):
                # 문자열이나 다른 타입이면 오늘로
                date_obj = datetime.now().date()
            
            start_time = datetime.combine(
                date_obj,
                datetime.min.time().replace(hour=hour, minute=minute)
            )
            
            final_info = {
                **schedule_info,
                "start_time": start_time,
                "end_time": time_info.get("end_time"),
                "needs_time": False,
            }
            
            # 이제 진짜로 일정 생성
            schedule = schedule_service.create_schedule(final_info, current_user)
            
            # pending 제거
            del pending_actions[current_user.id]
            
            answer = schedule_service.format_schedule_response(schedule, "create")
            
            return ChatResponse(
                answer=answer,
                sources=[],
                response_time=0.5,
                model="schedule_service",
                provider="internal"
            )
        
        # 요일이 필요한 경우 처리
        if user_pending and user_pending.get("action") == "schedule_weekday_pending":
            # 요일 정보 추출 시도
            weekday_names = {'월요일': 0, '화요일': 1, '수요일': 2, '목요일': 3, '금요일': 4, '토요일': 5, '일요일': 6}
            weekday = None
            message_lower = request.message.lower()
            
            for weekday_name, weekday_num in weekday_names.items():
                if weekday_name in message_lower:
                    weekday = weekday_num
                    break
            
            if weekday is not None:
                # pending 정보에서 month와 week_number 가져오기
                schedule_info = user_pending.get("schedule_info", {})
                month = schedule_info.get("month")
                week_number = schedule_info.get("week_number")
                
                if month and week_number:
                    # 날짜 계산
                    parsed_date = schedule_service._get_weekday_of_month(month, week_number, weekday)
                    schedule_info["date"] = parsed_date
                    schedule_info["needs_weekday"] = False
                    
                    # 시간 정보도 함께 추출 시도 (예: "그 주 수요일 오후 2시")
                    time_info = schedule_service.extract_time_from_message(request.message)
                    
                    if time_info:
                        # 시간 정보가 있으면 날짜와 시간을 합쳐서 바로 생성
                        from datetime import datetime
                        hour = time_info["start_time"].hour
                        minute = time_info["start_time"].minute
                        start_time = datetime.combine(
                            parsed_date,
                            datetime.min.time().replace(hour=hour, minute=minute)
                        )
                        schedule_info["start_time"] = start_time
                        schedule_info["end_time"] = time_info.get("end_time")
                        schedule_info["needs_time"] = False
                        schedule_info["has_explicit_time"] = True
                        
                        # 바로 일정 생성
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
                        # 시간 정보가 없으면 _parse_datetime을 호출하여 needs_time 플래그 확인
                        from datetime import datetime
                        schedule_info = schedule_service._parse_datetime(schedule_info)
                        
                        if schedule_info:
                            # needs_time 플래그 확인
                            if schedule_info.get("needs_time"):
                                # 시간을 물어봐야 함
                                pending_actions[current_user.id] = {
                                    "action": "schedule_create_pending",
                                    "schedule_info": schedule_info,
                                    "message": request.message
                                }
                                
                                date_str = parsed_date.strftime("%Y년 %m월 %d일")
                                title = schedule_info.get("title", "일정")
                                
                                answer = f"{date_str}에 **{title}** 잡을게요. 몇 시로 할까요? (예: 오후 2시, 3시 30분)"
                                
                                return ChatResponse(
                                    answer=answer,
                                    sources=[],
                                    response_time=0.4,
                                    model="schedule_service",
                                    provider="internal"
                                )
                            else:
                                # 시간 정보가 있으면 바로 생성 (예: 휴가 같은 종일 일정)
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
                # 요일을 이해 못함
                return ChatResponse(
                    answer="요일을 잘 못 알아들었어요. 예: '월요일', '수요일'처럼 말해주세요.",
                    sources=[],
                    response_time=0.3,
                    model="schedule_service",
                    provider="internal"
                )
        
        # 2. 공휴일 관련 질문인지 확인
        if schedule_service.is_holiday_query(request.message):
            # 공휴일 조회
            answer = schedule_service.query_holidays(request.message)
            return ChatResponse(
                answer=answer,
                sources=[],
                response_time=0.3,
                model="holiday_service",
                provider="internal"
            )
        
        # 3. 일정 관련 요청인지 확인
        action_type = schedule_service.get_schedule_action_type(request.message)
        
        # 일정과 상관 없는 경우 → 그냥 다른 RAG/챗봇 로직으로 넘기기
        if not action_type:
            # 일정 관련이 아니면 일반 RAG 처리로 넘어감 (아래 코드에서 처리)
            pass
        elif action_type == "create":
            # 일정 추가
            schedule_info = schedule_service.extract_schedule_info(request.message)
            
            print(f"🔍 [일정 생성] schedule_info: {schedule_info}")
            
            # 진짜로 일정 정보를 못 뽑았을 때만
            if not schedule_info:
                return ChatResponse(
                    answer="일정 정보를 잘 못 알아들었어요. 날짜를 몇월 몇일 정확히 말씀해주시면 감사하겠습니다.",
                    sources=[],
                    response_time=0.3,
                    model="schedule_service",
                    provider="internal"
                )
            
            # (1) 요일이 필요해서 아직 날짜가 확정 안 된 케이스 (예: "1월 둘째 주 회의 잡아줘")
            if schedule_info.get("needs_weekday"):
                month = schedule_info.get("month")
                week_number = schedule_info.get("week_number")
                title = schedule_info.get("title") or "일정"
                
                # pending 상태로 저장 (사용자가 요일을 답하면 처리하기 위해)
                # TODO: 실제 운영 환경에서는 DB나 Redis에 저장하는 것이 좋음
                pending_actions[current_user.id] = {
                    "action": "schedule_weekday_pending",
                    "schedule_info": schedule_info,
                    "message": request.message
                }
                
                answer = f"{month}월 {week_number}째 주에 **{title}**를 잡을게요. 요일은 언제로 할까요? (예: 월요일)"
                
                return ChatResponse(
                    answer=answer,
                    sources=[],
                    response_time=0.4,
                    model="schedule_service",
                    provider="internal"
                )
            
            # (2) 날짜는 있는데 시간이 없는 케이스 → pending 저장 후 시간 물어보기
            if schedule_info.get("needs_time"):
                # pending 저장
                # TODO: 실제 운영 환경에서는 DB나 Redis에 저장하는 것이 좋음
                # 현재는 메모리 dict에 저장 (서버 재시작 시 사라짐)
                pending_actions[current_user.id] = {
                    "action": "schedule_create_pending",
                    "schedule_info": schedule_info,
                    "message": request.message
                }
                
                from datetime import date
                date_obj = schedule_info.get("date")
                date_str = date_obj.strftime("%Y년 %m월 %d일") if date_obj and isinstance(date_obj, date) else "해당 날짜"
                title = schedule_info.get("title") or "일정"
                
                answer = f"{date_str}에 **{title}** 잡을게요. 몇 시로 할까요? (예: 오후 2시, 3시 30분)"
                
                return ChatResponse(
                    answer=answer,
                    sources=[],
                    response_time=0.4,
                    model="schedule_service",
                    provider="internal"
                )
            
            # 3) 날짜 + 시간 모두 있으니 바로 생성
            schedule = schedule_service.create_schedule(schedule_info, current_user)
            answer = schedule_service.format_schedule_response(schedule, "create")
            
            return ChatResponse(
                answer=answer,
                sources=[],
                response_time=0.5,
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
                    answer="삭제할 일정을 찾지 못했어요.",
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
                    answer="수정할 일정을 찾지 못했어요.",
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

