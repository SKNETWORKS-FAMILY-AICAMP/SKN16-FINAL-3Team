"""
RAG 기반 시뮬레이션 API 라우터
제공된 데이터를 활용한 STT/LLM/TTS 기반 음성 시뮬레이션
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request
from sqlmodel import Session
from typing import List, Dict, Optional
from pydantic import BaseModel
import os
import json
from pathlib import Path
from datetime import datetime

from app.database import get_session
from app.models.user import User
from app.models.mentor import SimulationRecording
from app.models.simulation_feedback import SimulationFeedback
from app.services.rag_simulation_service import RAGSimulationService
from app.utils.auth import get_current_user
from app.config import settings

router = APIRouter(prefix="/rag-simulation", tags=["RAG Simulation"])


class StartRAGSimulationRequest(BaseModel):
    """RAG 시뮬레이션 시작 요청"""
    persona_id: str
    situation_id: str
    gender: Optional[str] = 'male'  # 성별 추가


class RAGSimulationResponse(BaseModel):
    """RAG 시뮬레이션 응답"""
    session_id: str
    persona: Dict
    situation: Dict
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


class AnalyzeGoalAchievementRequest(BaseModel):
    """목표 달성 분석 요청"""
    conversation_history: List[Dict]
    goals: List[str]


class AnalyzeGoalAchievementResponse(BaseModel):
    """목표 달성 분석 응답"""
    achieved_goal_indices: List[int]


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


@router.get("/business-categories")
async def get_business_categories(
    session: Session = Depends(get_session)
):
    """비즈니스 카테고리 목록 조회"""
    try:
        service = RAGSimulationService(session)
        categories = service.get_business_categories()
        
        return {
            "categories": categories,
            "total_count": len(categories)
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"카테고리 조회 중 오류가 발생했습니다: {str(e)}"
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
            request.situation_id,
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


@router.post("/upload-recording")
async def upload_recording(
    video: UploadFile = File(...),
    session_data: str = Form(...),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """시뮬레이션 녹화 파일 업로드"""
    try:
        # 세션 데이터 파싱
        try:
            session_data_dict = json.loads(session_data)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=400,
                detail="세션 데이터 형식이 올바르지 않습니다."
            )
        
        # 업로드 디렉토리 설정 (시뮬레이션 녹화 파일용)
        recordings_dir = Path(settings.UPLOAD_DIR) / "simulations" / "recordings"
        recordings_dir.mkdir(parents=True, exist_ok=True)
        
        # 고유한 파일명 생성
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        user_id = session_data_dict.get("user_id", current_user.id if current_user else "anonymous")
        simulation_id = session_data_dict.get("simulation_id", timestamp)
        filename = f"sim_{simulation_id}_user_{user_id}_{timestamp}.webm"
        
        file_path = recordings_dir / filename
        
        # 파일 저장
        with open(file_path, "wb") as f:
            content = await video.read()
            f.write(content)
        
        # 파일 크기 확인
        file_size = file_path.stat().st_size
        
        # 공개 URL 생성
        public_url = f"/uploads/simulations/recordings/{filename}"
        
        # 데이터베이스에 녹화 기록 저장 (멘티만)
        if current_user and current_user.role == "mentee":
            recording = SimulationRecording(
                mentee_id=current_user.id,
                simulation_id=simulation_id,
                persona_id=session_data_dict.get("persona_id"),
                situation_id=session_data_dict.get("situation_id"),
                video_url=public_url,
                filename=filename,
                file_size=file_size,
                duration=None  # TODO: 비디오 길이 계산
            )
            session.add(recording)
            session.commit()
            session.refresh(recording)
            print(f"✅ 녹화 기록이 데이터베이스에 저장되었습니다: ID={recording.id}")
        
        return {
            "success": True,
            "video_url": public_url,
            "filename": filename,
            "file_size": file_size,
            "simulation_id": simulation_id,
            "uploaded_at": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"녹화 파일 업로드 중 오류가 발생했습니다: {str(e)}"
        )


class GenerateFeedbackRequest(BaseModel):
    """피드백 생성 요청"""
    conversation_history: List[Dict]
    persona: Dict
    situation: Dict


@router.post("/generate-feedback")
async def generate_simulation_feedback(
    request: GenerateFeedbackRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    시뮬레이션 종합 평가 및 피드백 생성
    6가지 역량(지식, 기술, 공감도, 명확성, 친절도, 자신감) 기반 평가
    """
    try:
        service = RAGSimulationService(session)
        
        feedback_data = service.generate_comprehensive_feedback(
            conversation_history=request.conversation_history,
            persona=request.persona,
            situation=request.situation
        )
        
        # DB에 피드백 저장 (히스토리용)
        try:
            feedback_record = SimulationFeedback(
                user_id=current_user.id,
                persona_id=request.persona.get('id') or request.persona.get('persona_id'),
                situation_id=request.situation.get('id') or request.situation.get('situation_id'),
                overall_score=feedback_data['overallScore'],
                grade=feedback_data['grade'],
                performance_level=feedback_data['performanceLevel'],
                knowledge_score=feedback_data['detailedFeedback']['knowledge']['score'],
                skill_score=feedback_data['detailedFeedback']['skill']['score'],
                empathy_score=feedback_data['detailedFeedback']['empathy']['score'],
                clarity_score=feedback_data['detailedFeedback']['clarity']['score'],
                kindness_score=feedback_data['detailedFeedback']['kindness']['score'],
                confidence_score=feedback_data['detailedFeedback']['confidence']['score'],
                knowledge_feedback=feedback_data['detailedFeedback']['knowledge']['feedback'],
                skill_feedback=feedback_data['detailedFeedback']['skill']['feedback'],
                empathy_feedback=feedback_data['detailedFeedback']['empathy']['feedback'],
                clarity_feedback=feedback_data['detailedFeedback']['clarity']['feedback'],
                kindness_feedback=feedback_data['detailedFeedback']['kindness']['feedback'],
                confidence_feedback=feedback_data['detailedFeedback']['confidence']['feedback'],
                summary=feedback_data['summary'],
                improvements=feedback_data['improvements'],
                total_turns=len(request.conversation_history)
            )
            
            session.add(feedback_record)
            session.commit()
            session.refresh(feedback_record)
            
            print(f"✅ 피드백이 DB에 저장되었습니다: ID={feedback_record.id}, User={current_user.id}")
            
            # 피드백 데이터에 ID 추가
            feedback_data['feedback_id'] = feedback_record.id
            
        except Exception as db_error:
            print(f"⚠️ DB 저장 실패 (피드백은 반환됨): {db_error}")
            import traceback
            traceback.print_exc()
        
        return {
            "success": True,
            "feedback": feedback_data
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"피드백 생성 중 오류가 발생했습니다: {str(e)}"
        )


@router.get("/feedback-history")
async def get_feedback_history(
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    사용자의 피드백 히스토리 조회
    최신순으로 정렬하여 반환
    """
    try:
        from sqlmodel import select
        
        statement = (
            select(SimulationFeedback)
            .where(SimulationFeedback.user_id == current_user.id)
            .order_by(SimulationFeedback.created_at.desc())
            .limit(limit)
        )
        
        feedbacks = session.exec(statement).all()
        
        # 응답 형식으로 변환
        history = []
        for fb in feedbacks:
            history.append({
                "id": fb.id,
                "created_at": fb.created_at.isoformat(),
                "overall_score": fb.overall_score,
                "grade": fb.grade,
                "performance_level": fb.performance_level,
                "competencies": [
                    {"name": "지식", "score": fb.knowledge_score},
                    {"name": "기술", "score": fb.skill_score},
                    {"name": "공감도", "score": fb.empathy_score},
                    {"name": "명확성", "score": fb.clarity_score},
                    {"name": "친절도", "score": fb.kindness_score},
                    {"name": "자신감", "score": fb.confidence_score}
                ],
                "persona_id": fb.persona_id,
                "situation_id": fb.situation_id,
                "total_turns": fb.total_turns
            })
        
        return {
            "success": True,
            "history": history,
            "total_count": len(history)
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"피드백 히스토리 조회 중 오류가 발생했습니다: {str(e)}"
        )


@router.get("/feedback/{feedback_id}")
async def get_feedback_detail(
    feedback_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    특정 피드백 상세 정보 조회
    """
    try:
        feedback = session.get(SimulationFeedback, feedback_id)
        
        if not feedback:
            raise HTTPException(status_code=404, detail="피드백을 찾을 수 없습니다.")
        
        # 권한 확인 (본인의 피드백만 조회 가능)
        if feedback.user_id != current_user.id and current_user.role != 'admin':
            raise HTTPException(status_code=403, detail="접근 권한이 없습니다.")
        
        return {
            "success": True,
            "feedback": {
                "overallScore": feedback.overall_score,
                "grade": feedback.grade,
                "performanceLevel": feedback.performance_level,
                "summary": feedback.summary,
                "competencies": [
                    {"name": "지식", "score": feedback.knowledge_score, "maxScore": 100},
                    {"name": "기술", "score": feedback.skill_score, "maxScore": 100},
                    {"name": "공감도", "score": feedback.empathy_score, "maxScore": 100},
                    {"name": "명확성", "score": feedback.clarity_score, "maxScore": 100},
                    {"name": "친절도", "score": feedback.kindness_score, "maxScore": 100},
                    {"name": "자신감", "score": feedback.confidence_score, "maxScore": 100}
                ],
                "detailedFeedback": {
                    "knowledge": {"score": feedback.knowledge_score, "feedback": feedback.knowledge_feedback},
                    "skill": {"score": feedback.skill_score, "feedback": feedback.skill_feedback},
                    "empathy": {"score": feedback.empathy_score, "feedback": feedback.empathy_feedback},
                    "clarity": {"score": feedback.clarity_score, "feedback": feedback.clarity_feedback},
                    "kindness": {"score": feedback.kindness_score, "feedback": feedback.kindness_feedback},
                    "confidence": {"score": feedback.confidence_score, "feedback": feedback.confidence_feedback}
                },
                "improvements": feedback.improvements,
                "created_at": feedback.created_at.isoformat(),
                "total_turns": feedback.total_turns
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"피드백 조회 중 오류가 발생했습니다: {str(e)}"
        )


@router.post("/analyze-goal-achievement")
async def analyze_goal_achievement(
    request: AnalyzeGoalAchievementRequest,
    session: Session = Depends(get_session)
):
    """목표 달성 여부 자동 분석"""
    try:
        service = RAGSimulationService(session)
        
        # 목표 달성 분석
        achieved_indices = service.analyze_goal_achievement(
            conversation_history=request.conversation_history,
            goals=request.goals
        )
        
        return {
            "achieved_goal_indices": achieved_indices,
            "total_goals": len(request.goals),
            "achieved_count": len(achieved_indices)
        }
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"목표 달성 분석 중 오류가 발생했습니다: {str(e)}"
        )
