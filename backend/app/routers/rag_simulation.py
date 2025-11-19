"""
RAG 기반 시뮬레이션 API 라우터
제공된 데이터를 활용한 STT/LLM/TTS 기반 음성 시뮬레이션
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request
from sqlmodel import Session
from sqlalchemy.exc import IntegrityError
from typing import List, Dict, Optional
from pydantic import BaseModel, root_validator, validator
import os
import json
from pathlib import Path
from datetime import datetime

from app.database import get_session
from app.models.user import User
from app.models.mentor import SimulationRecording
from app.models.simulation_feedback import SimulationFeedback
from app.models.rag_simulation import RAGSimulationSession
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
    test_scenario: Optional[Dict] = None  # 🧪 테스트 모드: 고정 시나리오
    is_test_mode: Optional[bool] = None  # 🧪 테스트 모드 플래그
    conversation_history: Optional[List[Dict]] = None  # 🧪 테스트 모드: 초기 대화 히스토리


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
    rag_evaluations: Optional[List[Dict]] = None  # 🧪 테스트 모드: 전체 RAG 평가 기록
    rag_evaluation: Optional[Dict] = None  # 단일 RAG 평가 (직원 발화)
    rag_evaluation_customer: Optional[Dict] = None  # 단일 RAG 평가 (고객 발화)
    rag_summary: Optional[Dict] = None  # RAG 평가 요약
    current_turn_index: Optional[int] = None  # 현재 턴 인덱스 (테스트 모드)
    next_turn_expected_text: Optional[str] = None  # 다음 턴 예상 멘트
    next_turn_role: Optional[str] = None  # 다음 턴 역할 (employee/customer)
    is_test_mode: Optional[bool] = None  # 테스트 모드 플래그
    stt_evaluations: Optional[List[Dict]] = None  # STT 평가 기록 (선택)
    test_completed: Optional[bool] = None  # 테스트 시나리오 완료 여부
    end_signal: Optional[bool] = None  # 백엔드 종료 신호


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
    random: bool = True,
    session: Session = Depends(get_session)
):
    """
    RAG 상황 목록 조회
    - category: 카테고리 필터 (예: "deposit", "loan")
    - random: True면 카테고리별로 40개 중 1개 랜덤 선택 (기본값: True)
    """
    try:
        service = RAGSimulationService(session)
        
        filters = {}
        if category:
            filters["category"] = category
        
        situations = service.get_situations(filters, random_select=random)
        
        return {
            "situations": situations,
            "total_count": len(situations)
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"상황 조회 중 오류가 발생했습니다: {str(e)}"
        )


class StartTestSimulationRequest(BaseModel):
    """테스트 시뮬레이션 시작 요청"""
    scenario_type: Optional[str] = 'deposit'  # 수신(deposit), 여신(loan), 카드(card), 외환/송금(fx)


@router.post("/start-test-simulation", response_model=RAGSimulationResponse)
async def start_test_simulation(
    request: StartTestSimulationRequest = StartTestSimulationRequest(),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """테스트 모드 시뮬레이션 시작 - STT 성능 및 RAG 연동 테스트"""
    try:
        scenario_type = request.scenario_type or 'deposit'
        print(f"🧪 테스트 시뮬레이션 시작 요청: user_id={current_user.id}, scenario_type={scenario_type}")
        service = RAGSimulationService(session)
        print(f"🧪 RAGSimulationService 인스턴스 생성 완료")
        
        result = service.start_test_simulation(current_user.id, scenario_type=scenario_type)
        print(f"🧪 start_test_simulation 완료: session_id={result.get('session_id')}")
        
        return RAGSimulationResponse(**result)
    
    except ValueError as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"❌ 테스트 시뮬레이션 시작 실패 (ValueError): {str(e)}")
        print(f"상세 오류:\n{error_trace}")
        raise HTTPException(
            status_code=400,
            detail=f"테스트 시뮬레이션 시작 중 오류가 발생했습니다: {str(e)}"
        )
    except FileNotFoundError as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"❌ 테스트 시뮬레이션 시작 실패 (FileNotFoundError): {str(e)}")
        print(f"상세 오류:\n{error_trace}")
        raise HTTPException(
            status_code=500,
            detail=f"필요한 데이터 파일을 찾을 수 없습니다: {str(e)}"
        )
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"❌ 테스트 시뮬레이션 시작 실패 (Exception): {str(e)}")
        print(f"상세 오류:\n{error_trace}")
        raise HTTPException(
            status_code=500,
            detail=f"테스트 시뮬레이션 시작 중 오류가 발생했습니다: {str(e)}"
        )


@router.post("/start-simulation", response_model=RAGSimulationResponse)
async def start_rag_simulation(
    request: StartRAGSimulationRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """RAG 시뮬레이션 시작"""
    try:
        print(f"🚀 시뮬레이션 시작 요청: user_id={current_user.id}, persona_id={request.persona_id}, situation_id={request.situation_id}, gender={request.gender}")
        
        service = RAGSimulationService(session)
        result = service.start_voice_simulation(
            current_user.id,
            request.persona_id,
            request.situation_id,
            request.gender
        )

        # 세션 정보 DB 저장 (목표 달성 상태 연동용)
        try:
            persona_payload = result.get("persona", {}) if isinstance(result, dict) else {}
            situation_payload = result.get("situation", {}) if isinstance(result, dict) else {}
            session_key = result.get("session_id") if isinstance(result, dict) else None

            if session_key:
                session_record = RAGSimulationSession(
                    session_key=session_key,
                    user_id=current_user.id,
                    persona_id=persona_payload.get("id") or persona_payload.get("persona_id"),
                    scenario_id=situation_payload.get("id") or situation_payload.get("situation_id"),
                    persona_name=persona_payload.get("name"),
                    scenario_title=situation_payload.get("title"),
                    persona_info=json.dumps(persona_payload, ensure_ascii=False) if persona_payload else None,
                    situation_info=json.dumps(situation_payload, ensure_ascii=False) if situation_payload else None,
                    total_turns=0
                )
                session.add(session_record)
                session.commit()
                print(f"✅ 시뮬레이션 세션 저장: {session_record.session_key}")
            else:
                print("⚠️ 세션 키가 없어 DB 저장을 건너뜁니다.")
        except IntegrityError:
            session.rollback()
            print(f"⚠️ 세션 키 중복으로 기존 레코드 활용: {result.get('session_id')}")
        except Exception as e:
            session.rollback()
            print(f"⚠️ 시뮬레이션 세션 저장 실패: {e}")
            import traceback
            traceback.print_exc()
        
        return RAGSimulationResponse(**result)
    
    except ValueError as e:
        print(f"❌ 시뮬레이션 시작 실패 (400): {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
    except RuntimeError as e:
        print(f"❌ 시뮬레이션 시작 실패 (500 - RuntimeError): {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"시뮬레이션 시작 중 오류가 발생했습니다: {str(e)}"
        )
    except Exception as e:
        print(f"❌ 시뮬레이션 시작 실패 (500 - 예상치 못한 오류): {str(e)}")
        import traceback
        error_trace = traceback.format_exc()
        print(f"상세 오류:\n{error_trace}")
        raise HTTPException(
            status_code=500,
            detail=f"시뮬레이션 시작 중 예상치 못한 오류가 발생했습니다: {str(e)}"
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
        
        # 🧪 테스트 모드 체크 (세션 데이터 검증 전에)
        is_test_mode = session_data_dict.get("is_test_mode", False)
        has_test_scenario = bool(session_data_dict.get("test_scenario"))
        
        if is_test_mode or has_test_scenario:
            print("🧪 테스트 모드 감지: 세션 데이터 검증 스킵")
        else:
            # 일반 모드: 세션 데이터 검증
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
    file: UploadFile = File(...),
    meta: str = Form(...),
    current_user: User = Depends(get_current_user)
):
    """시뮬레이션 녹화 파일 업로드 (파일 시스템 + JSON 메타데이터)"""
    try:
        import uuid
        
        print(f"📤 녹화 파일 업로드 요청 수신: filename={file.filename}, size={file.size if hasattr(file, 'size') else 'unknown'}")
        
        # 메타데이터 파싱
        try:
            meta_obj = json.loads(meta)
            print(f"📋 메타데이터 파싱 완료: {meta_obj}")
        except json.JSONDecodeError as e:
            print(f"❌ 메타데이터 파싱 실패: {e}")
            raise HTTPException(
                status_code=400,
                detail="메타데이터 형식이 올바르지 않습니다."
            )
        
        # 녹화 디렉토리 설정: /recordings/YYYY-MM-DD/
        day = datetime.now().strftime("%Y-%m-%d")
        recordings_base = Path(settings.UPLOAD_DIR) / "recordings"
        folder = recordings_base / day
        folder.mkdir(parents=True, exist_ok=True)
        print(f"📁 녹화 디렉토리: {folder}")
        
        # 고유 ID 생성
        rec_id = str(uuid.uuid4())
        print(f"🆔 녹화 ID 생성: {rec_id}")
        
        # 파일 저장
        video_path = folder / f"{rec_id}.webm"
        print(f"💾 파일 저장 시작: {video_path}")
        
        content = await file.read()
        print(f"📦 파일 내용 읽기 완료: {len(content)} bytes")
        
        with open(video_path, "wb") as f:
            f.write(content)
        
        # 파일 크기 확인
        file_size = video_path.stat().st_size
        print(f"✅ 파일 저장 완료: {video_path}, 크기: {file_size} bytes")
        
        # 메타데이터 업데이트 및 저장
        meta_obj.update({
            "id": rec_id,
            "user_id": current_user.id if current_user else None,
            "saved_at": datetime.now().isoformat(),
            "video_url": f"/recordings/{day}/{rec_id}.webm",
            "meta_url": f"/recordings/{day}/{rec_id}.json",
            "file_size": file_size,
            "thumbnail_url": None  # 나중에 ffmpeg로 썸네일 생성 시 사용
        })
        
        meta_path = folder / f"{rec_id}.json"
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta_obj, f, ensure_ascii=False, indent=2)
        
        print(f"✅ 녹화 파일 저장 완료: {video_path}, 메타데이터: {meta_path}")
        print(f"📹 비디오 URL: {meta_obj['video_url']}")
        
        return {
            "ok": True,
            "id": rec_id,
            "video_url": meta_obj["video_url"],
            "meta": meta_obj
        }
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"❌ 녹화 파일 업로드 중 오류 발생: {str(e)}")
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"녹화 파일 업로드 중 오류가 발생했습니다: {str(e)}"
        )


@router.get("/recordings/list")
async def list_recordings(
    current_user: User = Depends(get_current_user)
):
    """녹화 목록 조회 (파일 시스템 기반)"""
    try:
        recordings_base = Path(settings.UPLOAD_DIR) / "recordings"
        
        if not recordings_base.exists():
            return []
        
        out = []
        
        # 날짜별 폴더 순회
        for day in sorted(recordings_base.iterdir(), reverse=True):
            if not day.is_dir():
                continue
            
            # JSON 파일 찾기
            for json_file in day.glob("*.json"):
                try:
                    with open(json_file, "r", encoding="utf-8") as f:
                        meta = json.load(f)
                    
                    # 사용자 필터링 (본인 것만 또는 관리자면 전체)
                    if current_user:
                        if current_user.role == "admin" or meta.get("user_id") == current_user.id:
                            out.append(meta)
                except Exception as e:
                    print(f"⚠️ 메타데이터 파일 읽기 실패: {json_file}, {e}")
                    continue
        
        # 최신순 정렬
        out.sort(key=lambda x: x.get("saved_at", ""), reverse=True)
        
        return out
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"녹화 목록 조회 중 오류가 발생했습니다: {str(e)}"
        )


class UpdateRecordingFeedbackRequest(BaseModel):
    """녹화 feedback_id 업데이트 요청"""
    feedback_id: int

@router.put("/recordings/{recording_id}/feedback")
async def update_recording_feedback(
    recording_id: str,
    request: UpdateRecordingFeedbackRequest,
    current_user: User = Depends(get_current_user)
):
    """녹화의 feedback_id 업데이트 (JSON 파일 수정)"""
    try:
        recordings_base = Path(settings.UPLOAD_DIR) / "recordings"
        
        # 모든 날짜 폴더에서 해당 recording_id 찾기
        json_file = None
        for day in recordings_base.iterdir():
            if not day.is_dir():
                continue
            
            candidate = day / f"{recording_id}.json"
            if candidate.exists():
                json_file = candidate
                break
        
        if not json_file or not json_file.exists():
            raise HTTPException(
                status_code=404,
                detail="녹화 기록을 찾을 수 없습니다."
            )
        
        # JSON 파일 읽기
        with open(json_file, "r", encoding="utf-8") as f:
            meta = json.load(f)
        
        # 권한 확인
        if current_user:
            if current_user.role != "admin" and meta.get("user_id") != current_user.id:
                raise HTTPException(
                    status_code=403,
                    detail="이 녹화 기록에 대한 권한이 없습니다."
                )
        
        # feedback_id 업데이트
        meta["feedback_id"] = request.feedback_id
        
        # JSON 파일 저장
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        
        print(f"✅ 녹화 기록의 feedback_id 업데이트 완료: recording_id={recording_id}, feedback_id={request.feedback_id}")
        
        return {
            "success": True,
            "id": recording_id,
            "feedback_id": request.feedback_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"녹화 기록 업데이트 중 오류가 발생했습니다: {str(e)}"
        )


class GenerateFeedbackRequest(BaseModel):
    """피드백 생성 요청"""
    conversation_history: List[Dict]
    persona: Dict
    situation: Dict
    duration_seconds: Optional[int] = None  # 세션 지속 시간 (초)
    session_key: Optional[str] = None  # 세션 키 (DB에 저장된 목표 달성 정보 조회용)
    session_id: Optional[str] = None  # 호환용 (프론트에서 sessionId로 전달하는 경우)
    rag_evaluations: Optional[List[Dict]] = None  # 🧪 테스트 모드: RAG 평가 결과
    rag_summary: Optional[Dict] = None  # 🧪 테스트 모드: RAG 평가 종합 결과
    is_test_mode: Optional[bool] = False  # 테스트 모드 여부 (None이면 False로 처리)
    
    @validator('is_test_mode', pre=True)
    def validate_is_test_mode(cls, v):
        """is_test_mode가 None이거나 없으면 False로 처리"""
        if v is None:
            return False
        return bool(v)

    @root_validator(pre=True)
    def populate_session_key(cls, values):
        if values.get("session_key"):
            return values
        for key in ("sessionKey", "session_id", "sessionId"):
            if values.get(key):
                values["session_key"] = values.get(key)
                break
        return values


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
        print(f"📊 피드백 생성 요청 수신: user_id={current_user.id}, is_test_mode={request.is_test_mode}, conversation_turns={len(request.conversation_history)}")
        print(f"🧪 테스트 모드 상세 정보:")
        print(f"   - request.is_test_mode: {request.is_test_mode} (type: {type(request.is_test_mode)})")
        print(f"   - request.rag_evaluations: {len(request.rag_evaluations) if request.rag_evaluations else 0}개")
        print(f"   - request.rag_summary: {bool(request.rag_summary)}")
        if request.rag_evaluations:
            print(f"   - RAG 평가 상세: {[{'turn': e.get('turn_index'), 'role': e.get('role'), 'score': e.get('evaluation', {}).get('score')} for e in request.rag_evaluations[:3]]}")
        
        from sqlmodel import select
        from app.models.rag_simulation import RAGSimulationSession
        
        service = RAGSimulationService(session)
        
        # 🚨 중요: DB에 저장된 목표 달성 정보 조회 (프론트엔드가 저장한 정보 우선 사용)
        saved_achieved_goals = None
        if request.session_key:
            stmt = select(RAGSimulationSession).where(RAGSimulationSession.session_key == request.session_key)
            simulation_session = session.exec(stmt).first()
            
            raw_goal_payload = None
            if simulation_session:
                raw_goal_payload = simulation_session.goal_achievement_data or simulation_session.achieved_goals

            if raw_goal_payload:
                try:
                    import json as json_module
                    saved_achieved_goals = json_module.loads(raw_goal_payload)
                    print(f"✅ DB에서 목표 달성 정보 조회 성공: {saved_achieved_goals.get('achieved_count', 0)}/{saved_achieved_goals.get('total_goals', 0)}")
                    print(f"   달성 시점 정보: {'있음' if saved_achieved_goals.get('achievement_times') else '없음'}")
                except Exception as e:
                    print(f"⚠️ 목표 달성 정보 파싱 실패: {e}")
                    saved_achieved_goals = None
        
        feedback_data = service.generate_comprehensive_feedback(
            conversation_history=request.conversation_history,
            persona=request.persona,
            situation=request.situation,
            saved_achieved_goals=saved_achieved_goals  # DB에 저장된 목표 달성 정보 전달
        )
        
        # persona_info와 situation_info 생성 (DB 저장 전에 미리 생성)
        import json as json_module
        
        # persona_info 생성: "나이대 성별 직업" 형식
        persona_info = None
        if request.persona:
            parts = []
            age_group = request.persona.get('age_group', '')
            gender = request.persona.get('gender', '')
            occupation = request.persona.get('occupation', '')
            
            # 성별 한글 변환
            if gender == '남성' or gender == 'male':
                gender_kr = '남성'
            elif gender == '여성' or gender == 'female':
                gender_kr = '여성'
            else:
                gender_kr = gender
            
            if age_group:
                parts.append(age_group)
            if gender_kr:
                parts.append(gender_kr)
            if occupation:
                parts.append(occupation)
            
            persona_info = ' '.join(parts) if parts else None
            print(f"💾 Persona 정보 생성: {persona_info}")
        
        # situation_info 생성: 카테고리만 (여신, 수신, 카드, 외환/송금, 민원/불만 처리)
        situation_info = None
        if request.situation:
            # 먼저 request.situation에서 category와 id 가져오기
            category = request.situation.get('category', '')
            situation_id = request.situation.get('id') or request.situation.get('situation_id')
            
            # 상황 데이터에서 카테고리 정보 가져오기 (필요한 경우)
            situation_data = None
            if not category or category == 'general':
                if situation_id:
                    # 상황 데이터 캐시에서 찾기
                    situations = service.get_situations({}, random_select=False)
                    situation_data = next((s for s in situations if s.get('id') == situation_id), None)
                    if situation_data:
                        category = situation_data.get('category', '')
                        print(f"📋 상황 데이터에서 카테고리 찾음: {category} (situation_id={situation_id})")
            
            # 카테고리 한글 매핑
            category_map = {
                'deposit': '수신',
                'loan': '여신',
                'card': '카드',
                'foreign_exchange': '외환/송금',
                'fx': '외환/송금',
                'complaint': '민원/불만 처리',
                'general': '일반'
            }
            
            # 카테고리 매핑 적용
            if category in category_map:
                category_kr = category_map[category]
            elif category in ['수신', '여신', '카드', '외환/송금', '민원/불만 처리']:
                # 이미 한글이면 그대로 사용
                category_kr = category
            else:
                # 알 수 없는 카테고리면 상황 ID나 title에서 추출 시도
                if not situation_data and situation_id:
                    situations = service.get_situations({}, random_select=False)
                    situation_data = next((s for s in situations if s.get('id') == situation_id), None)
                
                if situation_data:
                    # title이나 id에서 카테고리 추출
                    title = situation_data.get('title', '')
                    sid = situation_data.get('id', '')
                    
                    # ID나 title에서 카테고리 키워드 찾기
                    if 'deposit' in sid.lower() or '수신' in title or '예금' in title or '적금' in title:
                        category_kr = '수신'
                    elif 'loan' in sid.lower() or '여신' in title or '대출' in title:
                        category_kr = '여신'
                    elif 'card' in sid.lower() or '카드' in title:
                        category_kr = '카드'
                    elif 'foreign' in sid.lower() or 'fx' in sid.lower() or '외환' in title or '송금' in title:
                        category_kr = '외환/송금'
                    elif 'complaint' in sid.lower() or '민원' in title or '불만' in title:
                        category_kr = '민원/불만 처리'
                    else:
                        category_kr = category  # 원본 그대로
                else:
                    category_kr = category
            
            situation_info = category_kr if category_kr and category_kr != 'general' else None
            print(f"💾 Situation 정보 생성: {situation_info} (원본 category={category}, situation_id={situation_id})")
        
        # DB에 피드백 저장 (히스토리용)
        try:
            print(f"💾 피드백 저장 시작: is_test_mode={request.is_test_mode}, user_id={current_user.id}")
            
            # improvements 필드 처리: 배열인 경우 JSON 문자열로 저장
            improvements_value = feedback_data['improvements']
            if isinstance(improvements_value, list):
                improvements_str = json_module.dumps(improvements_value, ensure_ascii=False)
            else:
                improvements_str = improvements_value
            
            feedback_record = SimulationFeedback(
                user_id=current_user.id,
                persona_id=request.persona.get('id') or request.persona.get('persona_id') if request.persona else None,
                situation_id=request.situation.get('id') or request.situation.get('situation_id') if request.situation else None,
                persona_info=persona_info,
                situation_info=situation_info,
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
                improvements=improvements_str,
                total_turns=len(request.conversation_history),
                duration_seconds=request.duration_seconds,
                conversation_log=json_module.dumps(request.conversation_history, ensure_ascii=False) if request.conversation_history else None,
                goal_achievement_data=json_module.dumps(feedback_data.get('goalAchievement', {}), ensure_ascii=False) if feedback_data.get('goalAchievement') else None,
                is_test_mode=bool(request.is_test_mode) if request.is_test_mode is not None else False,  # 테스트 모드 여부 저장 (None 체크 포함)
                # 🧪 테스트 모드: RAG 평가 결과 저장
                rag_evaluations=json_module.dumps(request.rag_evaluations, ensure_ascii=False) if request.rag_evaluations else None,
                rag_summary=json_module.dumps(request.rag_summary, ensure_ascii=False) if request.rag_summary else None
            )
            
            print(f"💾 피드백 레코드 생성:")
            print(f"   - is_test_mode (request): {request.is_test_mode} (type: {type(request.is_test_mode)})")
            print(f"   - is_test_mode (record): {feedback_record.is_test_mode} (type: {type(feedback_record.is_test_mode)})")
            print(f"   - rag_evaluations: {len(request.rag_evaluations) if request.rag_evaluations else 0}개")
            print(f"   - rag_summary: {bool(request.rag_summary)}")
            if request.rag_evaluations:
                print(f"   - RAG 평가 첫 3개: {[{'turn': e.get('turn_index'), 'role': e.get('role'), 'score': e.get('evaluation', {}).get('score')} for e in request.rag_evaluations[:3]]}")
            
            session.add(feedback_record)
            session.commit()
            session.refresh(feedback_record)
            
            print(f"✅ 피드백이 DB에 저장되었습니다:")
            print(f"   - ID: {feedback_record.id}")
            print(f"   - User: {current_user.id}")
            print(f"   - is_test_mode: {feedback_record.is_test_mode} (type: {type(feedback_record.is_test_mode)})")
            print(f"   - rag_evaluations 저장 여부: {bool(feedback_record.rag_evaluations)}")
            print(f"   - rag_summary 저장 여부: {bool(feedback_record.rag_summary)}")
            
            # 🔧 테스트 모드 평가서 자동 확인 및 업데이트 (저장 직후)
            # request.is_test_mode가 True인데 저장된 값이 False인 경우 강제 업데이트
            if request.is_test_mode and not feedback_record.is_test_mode:
                print(f"⚠️ 테스트 모드 평가서인데 is_test_mode가 False입니다. 강제 업데이트합니다.")
                feedback_record.is_test_mode = True
                session.add(feedback_record)
                session.commit()
                session.refresh(feedback_record)
                print(f"✅ 테스트 모드 평가서 업데이트 완료: ID={feedback_record.id}, is_test_mode={feedback_record.is_test_mode}")
            
            # 추가 확인: persona_id나 situation_id가 test로 시작하는 경우도 테스트 모드로 간주
            if not feedback_record.is_test_mode:
                is_test_persona = feedback_record.persona_id and 'test_persona' in str(feedback_record.persona_id).lower()
                is_test_situation = feedback_record.situation_id and 'test_situation' in str(feedback_record.situation_id).lower()
                if is_test_persona or is_test_situation:
                    print(f"🔧 테스트 모드 평가서 감지 (persona/situation 기반): persona_id={feedback_record.persona_id}, situation_id={feedback_record.situation_id}")
                    feedback_record.is_test_mode = True
                    session.add(feedback_record)
                    session.commit()
                    session.refresh(feedback_record)
                    print(f"✅ 테스트 모드 평가서 업데이트 완료: ID={feedback_record.id}, is_test_mode={feedback_record.is_test_mode}")
            
            # 피드백 데이터에 ID, 대화 로그, 경과 시간 추가
            feedback_data['feedback_id'] = feedback_record.id
            feedback_data['conversation_history'] = request.conversation_history
            feedback_data['duration_seconds'] = request.duration_seconds
            feedback_data['is_test_mode'] = feedback_record.is_test_mode  # 테스트 모드 여부도 응답에 포함
            
        except Exception as db_error:
            print(f"⚠️ DB 저장 실패 (피드백은 반환됨): {db_error}")
            import traceback
            traceback.print_exc()
            # 저장 실패 시에도 is_test_mode는 응답에 포함
            feedback_data['is_test_mode'] = request.is_test_mode
        
        # DB 저장 실패 시에도 대화 로그와 경과 시간은 포함
        if 'conversation_history' not in feedback_data:
            feedback_data['conversation_history'] = request.conversation_history
            feedback_data['duration_seconds'] = request.duration_seconds
        
        # persona_info와 situation_info를 응답에 포함
        feedback_data['persona_info'] = persona_info
        feedback_data['situation_info'] = situation_info
        
        # 🧪 테스트 모드: RAG 평가 결과를 피드백 데이터에 포함
        if request.rag_evaluations:
            feedback_data['rag_evaluations'] = request.rag_evaluations
            # rag_summary가 있으면 사용, 없으면 자동 생성
            if request.rag_summary:
                feedback_data['rag_summary'] = request.rag_summary
            else:
                # rag_evaluations에서 자동으로 summary 생성
                feedback_data['rag_summary'] = service._summarize_rag_evaluations(request.rag_evaluations)
            print(f"🧪 RAG 평가 결과를 피드백 데이터에 포함: {len(request.rag_evaluations)}개 평가, 평균 {feedback_data['rag_summary'].get('average_score', 0):.1f}점")
        
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


class UpdateRecordingFeedbackRequest(BaseModel):
    """녹화 feedback_id 업데이트 요청"""
    feedback_id: int

@router.put("/recording/{recording_id}/feedback")
async def update_recording_feedback(
    recording_id: int,
    request: UpdateRecordingFeedbackRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """녹화 기록의 feedback_id 업데이트"""
    try:
        # 녹화 기록 조회
        recording = session.get(SimulationRecording, recording_id)
        if not recording:
            raise HTTPException(
                status_code=404,
                detail="녹화 기록을 찾을 수 없습니다."
            )
        
        # 권한 확인 (본인의 녹화만 수정 가능)
        if recording.mentee_id != current_user.id:
            raise HTTPException(
                status_code=403,
                detail="이 녹화 기록에 대한 권한이 없습니다."
            )
        
        # feedback_id 업데이트
        recording.feedback_id = request.feedback_id
        session.add(recording)
        session.commit()
        session.refresh(recording)
        
        print(f"✅ 녹화 기록의 feedback_id 업데이트 완료: recording_id={recording_id}, feedback_id={request.feedback_id}")
        
        return {
            "success": True,
            "recording_id": recording.id,
            "feedback_id": recording.feedback_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"녹화 기록 업데이트 중 오류가 발생했습니다: {str(e)}"
        )


@router.get("/feedback-history")
async def get_feedback_history(
    limit: int = 10,
    is_test_mode: Optional[bool] = None,  # 테스트 모드 필터링 옵션
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    사용자의 피드백 히스토리 조회
    최신순으로 정렬하여 반환
    is_test_mode가 True이면 테스트 모드 평가서만, False이면 일반 평가서만, None이면 전체 반환
    관리자도 본인이 테스트 모드로 시뮬레이션한 평가서만 조회
    """
    try:
        from sqlmodel import select
        
        # 모든 사용자(관리자 포함)는 본인의 피드백만 조회
        statement = (
            select(SimulationFeedback)
            .where(SimulationFeedback.user_id == current_user.id)
        )
        
        # 테스트 모드 필터링
        if is_test_mode is not None:
            statement = statement.where(SimulationFeedback.is_test_mode == is_test_mode)
            print(f"🔍 피드백 히스토리 조회: user_id={current_user.id}, is_test_mode={is_test_mode}, role={current_user.role}")
        else:
            print(f"🔍 피드백 히스토리 조회: user_id={current_user.id}, is_test_mode=None (전체), role={current_user.role}")
        
        statement = statement.order_by(SimulationFeedback.created_at.desc()).limit(limit)
        
        feedbacks = session.exec(statement).all()
        print(f"📊 조회된 피드백 수: {len(feedbacks)}개")
        
        # 디버깅: 각 피드백의 is_test_mode 확인
        for fb in feedbacks:
            print(f"  - 피드백 ID={fb.id}, is_test_mode={fb.is_test_mode}, user_id={fb.user_id}, created_at={fb.created_at}")
        
        # 🔧 이전에 저장된 테스트 모드 평가서 자동 업데이트 (하위 호환성)
        # persona_id가 "test_persona_001"이거나 situation_id가 "test_situation_001"인 경우
        # is_test_mode가 False로 저장되어 있을 수 있으므로 True로 업데이트
        # 전체 평가서를 조회하여 업데이트 (필터링 전에 실행)
        if is_test_mode is True or is_test_mode is None:  # 테스트 모드 조회 시 또는 전체 조회 시
            # 본인의 평가서만 조회 (관리자 포함)
            all_feedbacks_stmt = (
                select(SimulationFeedback)
                .where(SimulationFeedback.user_id == current_user.id)
            )
            all_feedbacks = session.exec(all_feedbacks_stmt).all()
            
            test_feedbacks_to_update = [
                fb for fb in all_feedbacks 
                if not fb.is_test_mode and (
                    (fb.persona_id and 'test_persona' in str(fb.persona_id).lower()) or
                    (fb.situation_id and 'test_situation' in str(fb.situation_id).lower())
                )
            ]
            if test_feedbacks_to_update:
                print(f"🔧 테스트 모드 평가서 자동 업데이트: {len(test_feedbacks_to_update)}개 발견")
                for fb in test_feedbacks_to_update:
                    fb.is_test_mode = True
                    session.add(fb)
                session.commit()
                print(f"✅ 테스트 모드 평가서 업데이트 완료: {len(test_feedbacks_to_update)}개")
                # 업데이트 후 다시 조회
                feedbacks = session.exec(statement).all()
        
        # 페르소나와 상황 데이터 로드를 위한 서비스
        from app.services.rag_simulation_service import RAGSimulationService
        rag_service = RAGSimulationService(session)
        
        # 🔥 개선: 데이터를 한 번만 로드하고 재사용 (성능 + 안정성)
        personas = []
        situations = []
        try:
            personas = rag_service.get_personas({})
            situations = rag_service.get_situations({}, random_select=False)  # 🔥 전체 데이터 가져오기
            print(f"✅ RAG 데이터 로드 성공: Personas {len(personas)}개, Situations {len(situations)}개")
        except Exception as e:
            print(f"⚠️ RAG 데이터 로드 실패: {e}")
            import traceback
            traceback.print_exc()
        
        # 응답 형식으로 변환
        history = []
        for fb in feedbacks:
            # 페르소나와 상황 정보 조회
            persona_info = None
            situation_info = None
            
            try:
                # 페르소나 매칭
                if fb.persona_id and personas:
                    print(f"🔍 피드백 {fb.id}: 페르소나 ID '{fb.persona_id}' 매칭 시도...")
                    persona = next((p for p in personas if str(p.get('id')) == str(fb.persona_id) or str(p.get('persona_id')) == str(fb.persona_id)), None)
                    if persona:
                        # 타입, 연령대, 직업 모두 포함
                        parts = []
                        if persona.get('type'):
                            parts.append(persona.get('type'))
                        if persona.get('age_group'):
                            parts.append(persona.get('age_group'))
                        if persona.get('occupation'):
                            parts.append(persona.get('occupation'))
                        persona_info = ' '.join(parts) if parts else None
                        print(f"  ✅ 페르소나 매칭 성공: {persona_info}")
                    else:
                        print(f"  ❌ 페르소나 매칭 실패: ID '{fb.persona_id}' 찾을 수 없음")
                        print(f"     사용 가능한 ID 샘플: {[str(p.get('id') or p.get('persona_id')) for p in personas[:3]]}")
                
                # 상황 매칭
                if fb.situation_id and situations:
                    print(f"🔍 피드백 {fb.id}: 상황 ID '{fb.situation_id}' 매칭 시도...")
                    situation = next((s for s in situations if str(s.get('id')) == str(fb.situation_id) or str(s.get('situation_id')) == str(fb.situation_id)), None)
                    if situation:
                        situation_info = situation.get('title', '')
                        print(f"  ✅ 상황 매칭 성공: {situation_info}")
                    else:
                        print(f"  ❌ 상황 매칭 실패: ID '{fb.situation_id}' 찾을 수 없음")
                        print(f"     사용 가능한 ID 샘플: {[str(s.get('id') or s.get('situation_id')) for s in situations[:3]]}")
                else:
                    if not fb.situation_id:
                        print(f"⚠️ 피드백 {fb.id}: situation_id가 DB에 저장되지 않음")
                    if not situations:
                        print(f"⚠️ 피드백 {fb.id}: situations 데이터가 로드되지 않음")
                        
            except Exception as e:
                print(f"❌ 피드백 ID {fb.id} 시나리오 매칭 중 예외 발생: {e}")
                import traceback
                traceback.print_exc()
                pass  # 개별 피드백 실패는 무시
            
            # RAG 평가 결과 파싱 (테스트 모드인 경우)
            rag_evaluations = None
            rag_summary = None
            if fb.is_test_mode:
                import json as json_module
                if fb.rag_evaluations:
                    try:
                        rag_evaluations = json_module.loads(fb.rag_evaluations)
                    except:
                        pass
                if fb.rag_summary:
                    try:
                        rag_summary = json_module.loads(fb.rag_summary)
                    except:
                        pass
            
            history.append({
                "id": fb.id,
                "created_at": fb.created_at.isoformat(),
                "overall_score": fb.overall_score,
                "grade": fb.grade,
                "performance_level": fb.performance_level,
                # 통합된 4가지 역량으로 변환
                "competencies": [
                    {"name": "지식", "score": fb.knowledge_score},
                    {"name": "기술", "score": fb.skill_score},
                    {"name": "친절도", "score": fb.kindness_score},
                    {"name": "전달력", "score": round((fb.clarity_score + fb.confidence_score) / 2)}
                ],
                # 개별 역량 점수 (차트용) - 하위 호환성 유지
                "knowledge_score": fb.knowledge_score,
                "skill_score": fb.skill_score,
                "empathy_score": fb.empathy_score,
                "clarity_score": fb.clarity_score,
                "kindness_score": fb.kindness_score,
                "confidence_score": fb.confidence_score,
                # 시나리오 정보
                "persona_id": fb.persona_id,
                "situation_id": fb.situation_id,
                "persona_info": persona_info,
                "situation_info": situation_info,
                "total_turns": fb.total_turns,
                "duration_seconds": fb.duration_seconds,
                "is_test_mode": fb.is_test_mode,  # 테스트 모드 여부 포함
                # 🧪 테스트 모드: RAG 평가 결과 포함
                "rag_evaluations": rag_evaluations,
                "rag_summary": rag_summary
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
        
        # conversation_log JSON 파싱
        import json as json_module
        conversation_history = None
        if feedback.conversation_log:
            try:
                conversation_history = json_module.loads(feedback.conversation_log)
            except:
                conversation_history = None
        
        # goal_achievement_data JSON 파싱 및 형식 변환
        goal_achievement = None
        if feedback.goal_achievement_data:
            try:
                raw_goal_data = json_module.loads(feedback.goal_achievement_data)
                
                # 🚨 중요: 두 가지 저장 형식 지원
                # 형식 1 (프론트엔드 형식): {total, achieved, rate, goals: [...]}
                # 형식 2 (백엔드 형식): {total_goals, achieved_indices, achievement_times}
                
                # 형식 1 (프론트엔드 형식)이면 그대로 사용
                if 'goals' in raw_goal_data and isinstance(raw_goal_data.get('goals'), list):
                    print(f"✅ 프론트엔드 형식 데이터 감지 - 그대로 사용")
                    goal_achievement = raw_goal_data
                    print(f"   달성: {raw_goal_data.get('achieved', 0)}/{raw_goal_data.get('total', 0)}")
                
                # 형식 2 (백엔드 형식)이면 변환 필요
                elif 'achieved_indices' in raw_goal_data or 'total_goals' in raw_goal_data:
                    print(f"✅ 백엔드 형식 데이터 감지 - 변환 필요")
                    achieved_indices = raw_goal_data.get('achieved_indices', [])
                    total_goals = raw_goal_data.get('total_goals', 0)
                    achievement_times = raw_goal_data.get('achievement_times', {})
                    
                    # 🔍 situation 데이터에서 실제 goals 목록 가져오기
                    goals_list = []
                    if feedback.situation_id:
                        from app.services.rag_simulation_service import RAGSimulationService
                        rag_service = RAGSimulationService(session)
                        
                        # situations 데이터 조회
                        situations = rag_service.get_situations({}, random_select=False)
                        situation_data = next((s for s in situations if s.get('id') == feedback.situation_id), None)
                        
                        if situation_data and situation_data.get('goals'):
                            goals_list = situation_data.get('goals', [])
                            print(f"   Situation 데이터에서 목표 목록 조회 성공: {len(goals_list)}개")
                        else:
                            print(f"   ⚠️ Situation 데이터 조회 실패: situation_id={feedback.situation_id}")
                            goals_list = [f"목표 {i+1}" for i in range(total_goals)]
                    else:
                        goals_list = [f"목표 {i+1}" for i in range(total_goals)]
                    
                    # 프론트엔드 형식으로 변환
                    goal_achievement = {
                        "total": total_goals,
                        "achieved": len(achieved_indices),
                        "rate": raw_goal_data.get('achievement_rate', 0) / 100,  # 백분율 → 비율
                        "goals": [
                            {
                                "text": goals_list[i] if i < len(goals_list) else f"목표 {i+1}",
                                "achieved": i in achieved_indices,
                                "turn": achievement_times.get(str(i), {}).get("turn") if i in achieved_indices else None,
                                "evidence": None
                            }
                            for i in range(total_goals)
                        ]
                    }
                    
                    print(f"   달성: {len(achieved_indices)}/{total_goals} (달성 시점: {len(achievement_times)}개)")
                
                else:
                    print(f"⚠️ 알 수 없는 데이터 형식 - 그대로 사용")
                    goal_achievement = raw_goal_data
                
            except Exception as e:
                print(f"⚠️ 목표 달성 정보 파싱 실패: {e}")
                import traceback
                traceback.print_exc()
                goal_achievement = None
        
        # improvements JSON 파싱 (배열인 경우 처리)
        improvements_data = feedback.improvements
        if improvements_data and isinstance(improvements_data, str):
            # JSON 배열 문자열인 경우 파싱 시도
            if improvements_data.strip().startswith('['):
                try:
                    improvements_data = json_module.loads(improvements_data)
                except:
                    # 파싱 실패 시 원본 그대로 사용
                    pass
        
        # situation_info가 'general'이거나 없으면 상황 데이터에서 직접 찾기
        situation_info = feedback.situation_info
        if not situation_info or situation_info == 'general' or situation_info == '일반':
            if feedback.situation_id:
                try:
                    from app.services.rag_simulation_service import RAGSimulationService
                    rag_service = RAGSimulationService(session)
                    situations = rag_service.get_situations({}, random_select=False)
                    situation_data = next((s for s in situations if s.get('id') == feedback.situation_id), None)
                    if situation_data:
                        category = situation_data.get('category', '')
                        # 카테고리 한글 매핑
                        category_map = {
                            'deposit': '수신',
                            'loan': '여신',
                            'card': '카드',
                            'foreign_exchange': '외환/송금',
                            'fx': '외환/송금',
                            'complaint': '민원/불만 처리'
                        }
                        if category in category_map:
                            situation_info = category_map[category]
                        elif category in ['수신', '여신', '카드', '외환/송금', '민원/불만 처리']:
                            situation_info = category
                        else:
                            # title이나 id에서 카테고리 추출 시도
                            title = situation_data.get('title', '')
                            sid = situation_data.get('id', '')
                            if 'deposit' in sid.lower() or '수신' in title or '예금' in title or '적금' in title:
                                situation_info = '수신'
                            elif 'loan' in sid.lower() or '여신' in title or '대출' in title:
                                situation_info = '여신'
                            elif 'card' in sid.lower() or '카드' in title:
                                situation_info = '카드'
                            elif 'foreign' in sid.lower() or 'fx' in sid.lower() or '외환' in title or '송금' in title:
                                situation_info = '외환/송금'
                            elif 'complaint' in sid.lower() or '민원' in title or '불만' in title:
                                situation_info = '민원/불만 처리'
                        print(f"📋 피드백 조회: 상황 카테고리 업데이트 ({feedback.situation_info} → {situation_info})")
                except Exception as e:
                    print(f"⚠️ 피드백 조회 중 상황 정보 추출 실패: {e}")
        
        feedback_response = {
            "overallScore": feedback.overall_score,
            "grade": feedback.grade,
            "performanceLevel": feedback.performance_level,
            "summary": feedback.summary,
            "persona_info": feedback.persona_info,
            "situation_info": situation_info,  # 업데이트된 상황 정보 사용
            # 통합된 4가지 역량으로 변환
            "competencies": [
                {"name": "지식", "score": feedback.knowledge_score, "maxScore": 100},
                {"name": "기술", "score": feedback.skill_score, "maxScore": 100},
                {"name": "친절도", "score": feedback.kindness_score, "maxScore": 100},
                {"name": "전달력", "score": round((feedback.clarity_score + feedback.confidence_score) / 2), "maxScore": 100}
            ],
            "detailedFeedback": {
                "knowledge": {"score": feedback.knowledge_score, "feedback": feedback.knowledge_feedback},
                "skill": {"score": feedback.skill_score, "feedback": feedback.skill_feedback},
                "kindness": {
                    "score": feedback.kindness_score,
                    "feedback": feedback.kindness_feedback or '평가 정보가 없습니다.'
                },
                "clarity_confidence": {
                    "score": round((feedback.clarity_score + feedback.confidence_score) / 2),
                    "feedback": f"""명확성과 자신감을 종합 평가한 결과입니다.

명확성 측면: {feedback.clarity_feedback or '평가 정보가 없습니다.'}

자신감 측면: {feedback.confidence_feedback or '평가 정보가 없습니다.'}

전반적으로 정보를 명확하고 확신 있게 전달하는 역량입니다."""
                },
                # 하위 호환성을 위해 기존 필드도 유지 (deprecated)
                "empathy": {"score": feedback.empathy_score, "feedback": feedback.empathy_feedback},
                "clarity": {"score": feedback.clarity_score, "feedback": feedback.clarity_feedback},
                "confidence": {"score": feedback.confidence_score, "feedback": feedback.confidence_feedback}
            },
            "improvements": improvements_data,
            "created_at": feedback.created_at.isoformat(),
            "total_turns": feedback.total_turns,
            "duration_seconds": feedback.duration_seconds,
            "conversation_history": conversation_history
        }
        
        # 목표 달성 정보 추가 (있는 경우에만)
        if goal_achievement:
            feedback_response["goalAchievement"] = goal_achievement
        
        # 🧪 테스트 모드: RAG 평가 결과 추가 (있는 경우에만)
        if feedback.is_test_mode:
            print(f"🧪 테스트 모드 피드백 감지: ID={feedback.id}, rag_evaluations 존재={bool(feedback.rag_evaluations)}, rag_summary 존재={bool(feedback.rag_summary)}")
            
            if feedback.rag_evaluations:
                try:
                    feedback_response["rag_evaluations"] = json_module.loads(feedback.rag_evaluations)
                    print(f"🧪 RAG 평가 결과 포함: {len(feedback_response['rag_evaluations'])}개 평가")
                except Exception as e:
                    print(f"⚠️ RAG 평가 결과 파싱 실패: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                print(f"⚠️ 테스트 모드인데 rag_evaluations가 없습니다. DB 확인 필요.")
            
            if feedback.rag_summary:
                try:
                    feedback_response["rag_summary"] = json_module.loads(feedback.rag_summary)
                    print(f"🧪 RAG 평가 종합 결과 포함: 평균 {feedback_response['rag_summary'].get('average_score', 0):.1f}점")
                except Exception as e:
                    print(f"⚠️ RAG 평가 종합 결과 파싱 실패: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                print(f"⚠️ 테스트 모드인데 rag_summary가 없습니다. DB 확인 필요.")
        
        return {
            "success": True,
            "feedback": feedback_response
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


class GoalAchievementDetail(BaseModel):
    """목표 달성 세부 정보"""
    index: int
    turn: int  # 달성한 턴 번호


class UpdateGoalAchievementRequest(BaseModel):
    """목표 달성 현황 업데이트 요청"""
    session_key: str
    achieved_indices: List[int]
    total_goals: int
    achievement_details: Optional[List[GoalAchievementDetail]] = None  # 달성 시점 정보

    @root_validator(pre=True)
    def ensure_session_key(cls, values):
        if values.get("session_key"):
            return values
        for key in ("sessionKey", "sessionId", "session_id"):
            if values.get(key):
                values["session_key"] = values.get(key)
                break
        return values


@router.post("/update-goal-achievement")
async def update_goal_achievement(
    request: UpdateGoalAchievementRequest,
    session: Session = Depends(get_session)
):
    """
    시뮬레이션 세션의 목표 달성 현황을 DB에 저장
    프론트엔드에서 세션 종료 전에 호출하여 목표 달성 정보를 저장
    """
    try:
        from sqlmodel import select
        from app.models.rag_simulation import RAGSimulationSession
        
        # 세션 조회
        stmt = select(RAGSimulationSession).where(RAGSimulationSession.session_key == request.session_key)
        simulation_session = session.exec(stmt).first()
        
        if not simulation_session:
            raise HTTPException(
                status_code=404,
                detail=f"세션을 찾을 수 없습니다: {request.session_key}"
            )
        
        # 목표 달성 정보를 JSON 형식으로 저장
        achieved_goals_data = {
            "achieved_indices": request.achieved_indices,
            "total_goals": request.total_goals,
            "achieved_count": len(request.achieved_indices),
            "achievement_rate": round(len(request.achieved_indices) / request.total_goals * 100, 2) if request.total_goals > 0 else 0,
            "updated_at": datetime.now().isoformat()
        }
        
        # 달성 시점 정보 추가 (프론트엔드에서 전달된 경우)
        if request.achievement_details:
            achievement_times = {}
            for detail in request.achievement_details:
                achievement_times[str(detail.index)] = {
                    "turn": detail.turn,
                    "timestamp": datetime.now().isoformat()
                }
            achieved_goals_data["achievement_times"] = achievement_times
            print(f"  📅 달성 시점 정보 포함: {len(achievement_times)}개 목표")
        
        # DB 업데이트
        encoded_goals = json.dumps(achieved_goals_data, ensure_ascii=False)
        simulation_session.achieved_goals = encoded_goals
        simulation_session.goal_achievement_data = encoded_goals
        session.add(simulation_session)
        session.commit()
        session.refresh(simulation_session)
        
        print(f"✅ 목표 달성 현황 저장 완료: session_key={request.session_key}, achieved={len(request.achieved_indices)}/{request.total_goals}")
        
        return {
            "success": True,
            "session_key": request.session_key,
            "achieved_count": len(request.achieved_indices),
            "total_goals": request.total_goals,
            "achievement_rate": achieved_goals_data["achievement_rate"],
            "message": "목표 달성 현황이 저장되었습니다."
        }
    
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"목표 달성 현황 저장 중 오류가 발생했습니다: {str(e)}"
        )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ❌ 사용하지 않는 /evaluate, /evaluation 엔드포인트 제거됨
# ✅ 메인 평가는 /generate-feedback 사용 (rag_simulation_service)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

