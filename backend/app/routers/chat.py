"""
챗봇 API 라우터
RAG 기반 대화 처리
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from pydantic import BaseModel
from typing import List, Dict, Optional
import re
import time

from app.database import get_session
from app.models.user import User
from app.models.post import Post
from app.utils.auth import get_current_user
from app.services.rag_service import RAGService
from app.services.schedule_chat_service import ScheduleChatService

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


# 동아리 관련 질문 감지 함수
def is_club_question(message: str) -> bool:
    """동아리 라운지 관련 질문인지 확인"""
    club_patterns = [
        r'동아리',
        r'취미',
        r'같이\s*(하|할)',
        r'모임',
        r'라운지',
        r'(스포츠|운동|게임|독서|영화|음악|맛집|여행|예술).+(동아리|모임|좋아하는|같이|함께)',
        r'(축구|농구|배드민턴|테니스|등산|러닝|수영|헬스|요가).+(동아리|모임|같이)',
        r'(게임|롤|배그|피파|오버워치).+(동아리|모임|같이|함께)',
        r'(영화|드라마|넷플릭스).+(동아리|모임|같이|함께|추천)',
        r'(책|독서|소설).+(동아리|모임|같이|함께)',
        r'(음악|노래|악기|밴드).+(동아리|모임|같이|함께)',
        r'(요리|베이킹|맛집|카페).+(동아리|모임|같이|함께)',
        r'(여행|캠핑).+(동아리|모임|같이|함께)',
        r'(그림|미술|사진|예술).+(동아리|모임|같이|함께)',
    ]
    
    message_lower = message.lower()
    for pattern in club_patterns:
        if re.search(pattern, message_lower):
            return True
    return False


# 동아리 질문 처리 함수
async def handle_club_question(message: str, session: Session) -> ChatResponse:
    """동아리 라운지 질문 처리"""
    start_time = time.time()
    
    # 카테고리 추출 (실제 시스템 카테고리에 맞춤)
    categories = {
        "스포츠": ["운동", "축구", "농구", "배드민턴", "테니스", "등산", "러닝", "수영", "헬스", "요가", "스포츠", "야구", "배구", "탁구", "골프"],
        "게임": ["게임", "롤", "배그", "피파", "오버워치", "스팀", "게이밍", "e스포츠"],
        "영화": ["영화", "드라마", "넷플릭스", "디즈니", "영화관", "시네마"],
        "독서": ["책", "독서", "소설", "에세이", "자기계발", "도서", "북클럽", "문학"],
        "음악": ["음악", "노래", "악기", "밴드", "힙합", "재즈", "클래식", "콘서트", "공연"],
        "맛집": ["요리", "베이킹", "맛집", "카페", "음식", "레시피", "쿠킹"],
        "여행": ["여행", "캠핑", "해외여행", "국내여행", "관광", "투어"],
        "예술": ["그림", "미술", "전시", "미술관", "박물관", "사진", "디자인", "예술"],
    }
    
    detected_category = None
    for category, keywords in categories.items():
        for keyword in keywords:
            if keyword in message:
                detected_category = category
                break
        if detected_category:
            break
    
    # 게시글 검색
    query = select(Post).where(
        Post.is_deleted == False
    )
    
    if detected_category:
        query = query.where(Post.category == detected_category)
    
    query = query.order_by(Post.created_at.desc()).limit(5)
    posts = list(session.exec(query).all())
    
    # 응답 생성
    response_time = time.time() - start_time
    
    if not posts:
        answer = f"🎭 동아리 라운지 게시물\n\n"
        if detected_category:
            answer += f"'{detected_category}' 카테고리에는 아직 게시물이 없어요.\n\n"
        else:
            answer += "아직 게시물이 없어요.\n\n"
        answer += "첫 번째 게시물을 작성해보시는 건 어떨까요? 😊"
    elif len(posts) == 1:
        post = posts[0]
        answer = f"🎭 동아리 라운지 게시물을 찾았어요!\n\n"
        answer += f"**{post.title}**\n"
        answer += f"📂 {post.category}"
        if post.subcategory:
            answer += f" > {post.subcategory}"
        answer += f"\n👀 조회 {post.view_count}회 | 💬 댓글 {post.comment_count}개\n\n"
        
        # 내용 미리보기 (100자)
        preview = post.content[:100]
        if len(post.content) > 100:
            preview += "..."
        answer += f"{preview}\n\n"
        answer += "자세한 내용은 동아리 라운지에서 확인하세요!"
    else:
        answer = f"🎭 동아리 라운지 게시물 ({len(posts)}개)\n\n"
        if detected_category:
            answer += f"**{detected_category}** 카테고리\n\n"
        
        for idx, post in enumerate(posts, 1):
            answer += f"{idx}. **{post.title}**\n"
            answer += f"   📂 {post.category}"
            if post.subcategory:
                answer += f" > {post.subcategory}"
            answer += f" | 👀 {post.view_count}회 | 💬 {post.comment_count}개\n"
        
        answer += "\n자세한 내용은 동아리 라운지에서 확인하세요!"
    
    sources = []
    for post in posts:
        sources.append({
            "title": f"[동아리 라운지] {post.title}",
            "document_id": post.id,
            "post_id": post.id,  # 동아리 게시물 ID
            "type": "club_post",  # 타입 구분
            "category": post.category,
        })
    
    return ChatResponse(
        answer=answer,
        sources=sources,
        response_time=round(response_time, 2),
        model="club_service",
        provider="internal"
    )


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
        # 동아리 관련 질문인지 확인
        if is_club_question(request.message):
            return await handle_club_question(request.message, session)
        
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

