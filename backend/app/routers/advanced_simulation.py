"""
고도화된 시뮬레이션 API 라우터
STT/LLM/TTS 기반 음성 시뮬레이션 및 AI 기반 고객 페르소나 시스템
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlmodel import Session
from typing import List, Dict, Optional
from pydantic import BaseModel

from app.database import get_session
from app.models.user import User
from app.services.advanced_simulation_service import AdvancedSimulationService
from app.utils.auth import get_current_user

router = APIRouter(prefix="/advanced-simulation", tags=["Advanced Simulation"])


class StartVoiceSimulationRequest(BaseModel):
    """음성 시뮬레이션 시작 요청"""
    persona_id: int
    situation_id: int
    session_name: str


class VoiceInteractionRequest(BaseModel):
    """음성 상호작용 요청"""
    session_id: int
    interaction_type: str = "user_speech"


class VoiceInteractionResponse(BaseModel):
    """음성 상호작용 응답"""
    transcribed_text: str
    customer_response: str
    customer_audio: Optional[str]
    feedback: Optional[str]
    conversation_phase: str
    session_score: float


@router.get("/personas")
async def get_customer_personas(
    age_group: Optional[str] = None,
    occupation: Optional[str] = None,
    customer_type: Optional[str] = None,
    session: Session = Depends(get_session)
):
    """고객 페르소나 목록 조회"""
    try:
        service = AdvancedSimulationService(session)
        
        filters = {}
        if age_group:
            filters["age_group"] = age_group
        if occupation:
            filters["occupation"] = occupation
        if customer_type:
            filters["customer_type"] = customer_type
        
        personas = service.get_customer_personas(filters)
        
        return {
            "personas": personas,
            "total_count": len(personas)
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"고객 페르소나 조회 중 오류가 발생했습니다: {str(e)}"
        )


@router.get("/situations")
async def get_simulation_situations(
    business_category: Optional[str] = None,
    difficulty_level: Optional[str] = None,
    session: Session = Depends(get_session)
):
    """시뮬레이션 상황 목록 조회"""
    try:
        service = AdvancedSimulationService(session)
        
        filters = {}
        if business_category:
            filters["business_category"] = business_category
        if difficulty_level:
            filters["difficulty_level"] = difficulty_level
        
        situations = service.get_simulation_situations(filters)
        
        return {
            "situations": situations,
            "total_count": len(situations)
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"시뮬레이션 상황 조회 중 오류가 발생했습니다: {str(e)}"
        )


@router.post("/start-voice-simulation")
async def start_voice_simulation(
    request: StartVoiceSimulationRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """음성 시뮬레이션 시작"""
    try:
        service = AdvancedSimulationService(session)
        result = service.start_voice_simulation(
            current_user.id,
            request.persona_id,
            request.situation_id,
            request.session_name
        )
        
        return result
    
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"음성 시뮬레이션 시작 중 오류가 발생했습니다: {str(e)}"
        )


@router.post("/process-voice-interaction", response_model=VoiceInteractionResponse)
async def process_voice_interaction(
    session_id: int,
    audio_file: UploadFile = File(...),
    interaction_type: str = "user_speech",
    session: Session = Depends(get_session)
):
    """음성 상호작용 처리"""
    try:
        # 오디오 파일 읽기
        audio_data = await audio_file.read()
        
        service = AdvancedSimulationService(session)
        result = service.process_voice_interaction(
            session_id,
            audio_data,
            interaction_type
        )
        
        return VoiceInteractionResponse(**result)
    
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"음성 상호작용 처리 중 오류가 발생했습니다: {str(e)}"
        )


@router.post("/complete-simulation")
async def complete_simulation(
    session_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """시뮬레이션 완료 처리"""
    try:
        service = AdvancedSimulationService(session)
        result = service.complete_simulation(session_id)
        
        return result
    
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"시뮬레이션 완료 처리 중 오류가 발생했습니다: {str(e)}"
        )


@router.get("/simulation-history")
async def get_simulation_history(
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """시뮬레이션 기록 조회"""
    try:
        service = AdvancedSimulationService(session)
        history = service.get_simulation_history(current_user.id, limit)
        
        return {
            "sessions": history,
            "total_count": len(history)
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"시뮬레이션 기록 조회 중 오류가 발생했습니다: {str(e)}"
        )


@router.get("/persona-categories")
async def get_persona_categories():
    """페르소나 카테고리 정보 조회"""
    return {
        "age_groups": [
            {"id": "20대", "name": "20대", "description": "신입사원, 대학생"},
            {"id": "30대", "name": "30대", "description": "직장인, 신혼부부"},
            {"id": "40대", "name": "40대", "description": "경력직, 자녀 양육기"},
            {"id": "50대", "name": "50대", "description": "중간 관리직, 자녀 독립기"},
            {"id": "60대 이상", "name": "60대 이상", "description": "은퇴자, 노후 준비기"}
        ],
        "occupations": [
            {"id": "학생", "name": "학생", "description": "대학생, 대학원생"},
            {"id": "직장인", "name": "직장인", "description": "회사원, 공무원"},
            {"id": "자영업자", "name": "자영업자", "description": "사업자, 프리랜서"},
            {"id": "은퇴자", "name": "은퇴자", "description": "퇴직자, 노후자"},
            {"id": "외국인", "name": "외국인", "description": "외국인 고객"}
        ],
        "customer_types": [
            {"id": "실용형", "name": "실용형", "description": "빠르고 간결한 설명 선호"},
            {"id": "보수형", "name": "보수형", "description": "안정성 중시"},
            {"id": "불만형", "name": "불만형", "description": "감정적 대응 필요"},
            {"id": "긍정형", "name": "긍정형", "description": "친근한 톤 선호"},
            {"id": "급함형", "name": "급함형", "description": "시간 압박 강조"}
        ]
    }


@router.get("/situation-categories")
async def get_situation_categories():
    """상황 카테고리 정보 조회"""
    return {
        "business_categories": [
            {"id": "수신", "name": "수신", "description": "예금, 적금 상품"},
            {"id": "여신", "name": "여신", "description": "대출, 신용 상품"},
            {"id": "카드", "name": "카드", "description": "신용카드, 체크카드"},
            {"id": "외환/송금", "name": "외환/송금", "description": "해외송금, 외환거래"},
            {"id": "인터넷/모바일 뱅킹", "name": "인터넷/모바일 뱅킹", "description": "디지털 뱅킹 서비스"},
            {"id": "민원/불만 처리", "name": "민원/불만 처리", "description": "고객 민원 해결"}
        ],
        "difficulty_levels": [
            {"id": "쉬움", "name": "쉬움", "description": "단순 질문, 고객 반응 온화"},
            {"id": "보통", "name": "보통", "description": "중간 수준의 정책/규정 포함"},
            {"id": "어려움", "name": "어려움", "description": "복합 질문 + 예외상황 발생"}
        ]
    }
