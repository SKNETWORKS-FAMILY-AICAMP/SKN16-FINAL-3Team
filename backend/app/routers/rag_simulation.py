"""
RAG 기반 시뮬레이션 API 라우터
제공된 데이터를 활용한 STT/LLM/TTS 기반 음성 시뮬레이션
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request
from sqlmodel import Session
from typing import List, Dict, Optional
from pydantic import BaseModel

from app.database import get_session
from app.models.user import User
from app.services.rag_simulation_service import RAGSimulationService
from app.utils.auth import get_current_user

router = APIRouter(prefix="/rag-simulation", tags=["RAG Simulation"])


class StartRAGSimulationRequest(BaseModel):
    """RAG 시뮬레이션 시작 요청"""
    persona_id: str
    scenario_id: str
    gender: Optional[str] = 'male'  # 성별 추가


class RAGSimulationResponse(BaseModel):
    """RAG 시뮬레이션 응답"""
    session_id: str
    persona: Dict
    scenario: Dict
    initial_message: Dict


class VoiceInteractionRequest(BaseModel):
    """음성 상호작용 요청"""
    session_data: Dict
    user_message: Optional[str] = None


class VoiceInteractionResponse(BaseModel):
    """음성 상호작용 응답"""
    transcribed_text: str
    customer_response: str
    customer_audio: Optional[str]
    feedback: Optional[str]
    conversation_phase: str
    session_score: float


@router.get("/personas")
async def get_rag_personas(
    age_group: Optional[str] = None,
    occupation: Optional[str] = None,
    customer_type: Optional[str] = None,
    gender: Optional[str] = None,
    session: Session = Depends(get_session)
):
    """RAG 페르소나 목록 조회"""
    try:
        service = RAGSimulationService(session)
        
        filters = {}
        if age_group:
            filters["age_group"] = age_group
        if occupation:
            filters["occupation"] = occupation
        if customer_type:
            filters["type"] = customer_type
        if gender:
            filters["gender"] = gender
        
        personas = service.get_personas(filters)
        
        return {
            "personas": personas,
            "total_count": len(personas)
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"페르소나 조회 중 오류가 발생했습니다: {str(e)}"
        )


@router.get("/scenarios")
async def get_rag_scenarios(
    difficulty: Optional[str] = None,
    persona_id: Optional[str] = None,
    category: Optional[str] = None,
    session: Session = Depends(get_session)
):
    """RAG 시나리오 목록 조회"""
    try:
        service = RAGSimulationService(session)
        
        filters = {}
        if difficulty:
            filters["difficulty"] = difficulty
        if persona_id:
            filters["persona"] = persona_id
        if category:
            filters["category"] = category
        
        scenarios = service.get_scenarios(filters)
        
        return {
            "scenarios": scenarios,
            "total_count": len(scenarios)
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"시나리오 조회 중 오류가 발생했습니다: {str(e)}"
        )


@router.get("/situations")
async def get_rag_situations(
    category: Optional[str] = None,
    session: Session = Depends(get_session)
):
    """RAG 상황 목록 조회"""
    try:
        service = RAGSimulationService(session)
        
        filters = {}
        if category:
            filters["category"] = category
        
        situations = service.get_situations(filters)
        
        return {
            "situations": situations,
            "total_count": len(situations)
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"상황 조회 중 오류가 발생했습니다: {str(e)}"
        )


@router.post("/start-simulation", response_model=RAGSimulationResponse)
async def start_rag_simulation(
    request: StartRAGSimulationRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """RAG 시뮬레이션 시작"""
    try:
        service = RAGSimulationService(session)
        result = service.start_voice_simulation(
            current_user.id,
            request.persona_id,
            request.scenario_id,
            request.gender
        )
        
        return RAGSimulationResponse(**result)
    
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"RAG 시뮬레이션 시작 중 오류가 발생했습니다: {str(e)}"
        )


@router.post("/process-voice-interaction", response_model=VoiceInteractionResponse)
async def process_rag_voice_interaction(
    request: Request,
    session: Session = Depends(get_session)
):
    """RAG 음성 상호작용 처리 - JSON 또는 FormData 지원"""
    try:
        service = RAGSimulationService(session)
        
        # Content-Type 확인
        content_type = request.headers.get("content-type", "")
        print(f"Content-Type: {content_type}")
        
        session_data_dict = {}
        audio_data = None
        text_message = ""
        
        if "application/json" in content_type:
            # JSON 요청 처리
            print("JSON 요청 처리")
            json_data = await request.json()
            session_data_dict = json_data.get("session_data", {})
            text_message = json_data.get("user_message", "")
            audio_data = None  # JSON에서는 오디오 전송 안 함
            print(f"JSON 데이터: session_data keys = {list(session_data_dict.keys())}")
            print(f"user_message = '{text_message}'")
        else:
            # FormData 요청 처리
            print("FormData 요청 처리")
            form = await request.form()
            
            print(f"FormData 키들: {list(form.keys())}")
            
            # session_data JSON 파싱
            session_data_json = form.get("session_data")
            print(f"session_data_json 타입: {type(session_data_json)}")
            
            if session_data_json:
                import json
                try:
                    if isinstance(session_data_json, str):
                        session_data_dict = json.loads(session_data_json)
                    else:
                        session_data_dict = json.loads(str(session_data_json))
                    print(f"session_data_dict 파싱 성공: keys = {list(session_data_dict.keys())}")
                except Exception as e:
                    print(f"session_data JSON 파싱 실패: {e}")
                    session_data_dict = {}
            
            # audio_file 바이너리 읽기
            audio_file = form.get("audio_file")
            if audio_file:
                audio_data = await audio_file.read()
                print(f"오디오 파일 받음: {len(audio_data)} bytes, 타입: {audio_file.content_type}")
            
            # user_message
            text_message = form.get("user_message", "")
            print(f"user_message: '{text_message}'")
        
        print(f"최종 데이터: session_data keys = {list(session_data_dict.keys())}")
        print(f"text_message = '{text_message}'")
        print(f"audio_data 길이 = {len(audio_data) if audio_data else 0}")
        
        # 세션 데이터 검증
        if not session_data_dict or "persona" not in session_data_dict:
            print("❌ 세션 데이터가 비어있거나 페르소나 정보가 없습니다!")
            print(f"session_data_dict 내용: {session_data_dict}")
            raise ValueError("세션 데이터가 올바르지 않습니다.")
        
        result = service.process_voice_interaction(
            session_data_dict,
            audio_data,
            text_message
        )
        
        # JSON으로 응답
        return result
        
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"RAG 음성 상호작용 처리 중 오류가 발생했습니다: {str(e)}"
        )


@router.get("/categories")
async def get_rag_categories():
    """RAG 카테고리 정보 조회"""
    return {
        "age_groups": [
            {"id": "20s", "name": "20대", "description": "신입사원, 대학생"},
            {"id": "30s", "name": "30대", "description": "직장인, 신혼부부"},
            {"id": "40s", "name": "40대", "description": "경력직, 자녀 양육기"},
            {"id": "50s", "name": "50대", "description": "중간 관리직, 자녀 독립기"},
            {"id": "senior", "name": "60대 이상", "description": "은퇴자, 노후 준비기"}
        ],
        "occupations": [
            {"id": "student", "name": "학생", "description": "대학생, 대학원생"},
            {"id": "employee", "name": "직장인", "description": "회사원, 공무원"},
            {"id": "self_employed", "name": "자영업자", "description": "사업자, 프리랜서"},
            {"id": "retired", "name": "은퇴자", "description": "퇴직자, 노후자"},
            {"id": "foreigner", "name": "외국인", "description": "외국인 고객"}
        ],
        "customer_types": [
            {"id": "practical", "name": "실용형", "description": "빠르고 간결한 설명 선호"},
            {"id": "conservative", "name": "보수형", "description": "안정성 중시"},
            {"id": "angry", "name": "불만형", "description": "감정적 대응 필요"},
            {"id": "positive", "name": "긍정형", "description": "친근한 톤 선호"},
            {"id": "impatient", "name": "급함형", "description": "시간 압박 강조"}
        ],
        "difficulties": [
            {"id": "easy", "name": "쉬움", "description": "단순 질문, 고객 반응 온화"},
            {"id": "normal", "name": "보통", "description": "중간 수준의 정책/규정 포함"},
            {"id": "hard", "name": "어려움", "description": "복합 질문 + 예외상황 발생"}
        ],
        "categories": [
            {"id": "deposit", "name": "수신", "description": "예금, 적금 상품"},
            {"id": "loan", "name": "여신", "description": "대출, 신용 상품"},
            {"id": "card", "name": "카드", "description": "신용카드, 체크카드"},
            {"id": "foreign_exchange", "name": "외환/송금", "description": "해외송금, 외환거래"},
            {"id": "digital_banking", "name": "인터넷/모바일 뱅킹", "description": "디지털 뱅킹 서비스"},
            {"id": "complaint", "name": "민원/불만 처리", "description": "고객 민원 해결"}
        ]
    }


@router.get("/sample-data")
async def get_sample_data(session: Session = Depends(get_session)):
    """샘플 데이터 조회 (테스트용)"""
    try:
        service = RAGSimulationService(session)
        
        # 각 카테고리별 샘플 데이터 제공
        sample_personas = service.get_personas({"age_group": "30s"})[:3]
        sample_scenarios = service.get_scenarios({"difficulty": "easy"})[:3]
        sample_situations = service.get_situations({"category": "deposit"})[:3]
        
        return {
            "sample_personas": sample_personas,
            "sample_scenarios": sample_scenarios,
            "sample_situations": sample_situations
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"샘플 데이터 조회 중 오류가 발생했습니다: {str(e)}"
        )
