"""
시뮬레이션 관련 API 라우터
시뮬레이션 시나리오 관리, 실행, 결과 조회 등
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from typing import List, Dict, Optional
from pydantic import BaseModel

from app.database import get_session
from app.models.user import User
from app.services.simulation_service import SimulationService
from app.utils.auth import get_current_user

router = APIRouter(prefix="/simulation", tags=["Simulation"])


class StartSimulationRequest(BaseModel):
    """시뮬레이션 시작 요청"""
    scenario_id: int


class StepResponseRequest(BaseModel):
    """시뮬레이션 단계 응답 요청"""
    attempt_id: int
    step_number: int
    user_response: str
    user_action: Optional[str] = None


class StepResponseResponse(BaseModel):
    """시뮬레이션 단계 응답 결과"""
    step_result: Dict
    current_score: float
    next_step: Optional[Dict]
    is_completed: bool
    final_result: Optional[Dict] = None


@router.get("/scenarios")
async def get_simulation_scenarios(
    category: Optional[str] = None,
    difficulty: Optional[str] = None,
    session: Session = Depends(get_session)
):
    """시뮬레이션 시나리오 목록 조회"""
    try:
        service = SimulationService(session)
        scenarios = service.get_scenarios(category, difficulty)
        
        return {
            "scenarios": scenarios,
            "total_count": len(scenarios)
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"시나리오 조회 중 오류가 발생했습니다: {str(e)}"
        )


@router.get("/scenarios/{scenario_id}")
async def get_simulation_scenario_detail(
    scenario_id: int,
    session: Session = Depends(get_session)
):
    """시뮬레이션 시나리오 상세 정보 조회"""
    try:
        service = SimulationService(session)
        scenario = service.get_scenario_detail(scenario_id)
        
        if not scenario:
            raise HTTPException(
                status_code=404,
                detail="시나리오를 찾을 수 없습니다."
            )
        
        return scenario
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"시나리오 상세 정보 조회 중 오류가 발생했습니다: {str(e)}"
        )


@router.post("/start")
async def start_simulation(
    request: StartSimulationRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """시뮬레이션 시작"""
    try:
        service = SimulationService(session)
        result = service.start_simulation(current_user.id, request.scenario_id)
        
        return result
    
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"시뮬레이션 시작 중 오류가 발생했습니다: {str(e)}"
        )


@router.post("/submit-step", response_model=StepResponseResponse)
async def submit_step_response(
    request: StepResponseRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """시뮬레이션 단계 응답 제출"""
    try:
        service = SimulationService(session)
        result = service.submit_step_response(
            request.attempt_id,
            request.step_number,
            request.user_response,
            request.user_action
        )
        
        return StepResponseResponse(**result)
    
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"단계 응답 제출 중 오류가 발생했습니다: {str(e)}"
        )


@router.get("/progress")
async def get_user_progress(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """사용자 시뮬레이션 진행 상황 조회"""
    try:
        service = SimulationService(session)
        progress = service.get_user_progress(current_user.id)
        
        return progress
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"진행 상황 조회 중 오류가 발생했습니다: {str(e)}"
        )


@router.get("/history")
async def get_attempt_history(
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """시뮬레이션 시도 기록 조회"""
    try:
        service = SimulationService(session)
        history = service.get_attempt_history(current_user.id, limit)
        
        return {
            "attempts": history,
            "total_count": len(history)
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"시도 기록 조회 중 오류가 발생했습니다: {str(e)}"
        )


@router.get("/categories")
async def get_simulation_categories(session: Session = Depends(get_session)):
    """시뮬레이션 카테고리 목록 조회"""
    return {
        "categories": [
            {
                "id": "customer_service",
                "name": "고객상담",
                "description": "다양한 고객 상담 상황을 시뮬레이션합니다",
                "icon": "💬",
                "difficulty_levels": ["초급", "중급", "고급"]
            },
            {
                "id": "banking_operations",
                "name": "은행업무",
                "description": "실제 은행 업무 처리 과정을 연습합니다",
                "icon": "🏦",
                "difficulty_levels": ["초급", "중급", "고급"]
            },
            {
                "id": "emergency_situations",
                "name": "응급상황",
                "description": "예상치 못한 상황에 대한 대응 능력을 키웁니다",
                "icon": "🚨",
                "difficulty_levels": ["중급", "고급"]
            },
            {
                "id": "product_sales",
                "name": "상품판매",
                "description": "금융상품 판매 및 상담 스킬을 연습합니다",
                "icon": "💰",
                "difficulty_levels": ["초급", "중급", "고급"]
            },
            {
                "id": "compliance",
                "name": "법규준수",
                "description": "금융법규 준수 및 내부통제 상황을 시뮬레이션합니다",
                "icon": "⚖️",
                "difficulty_levels": ["중급", "고급"]
            }
        ]
    }


@router.get("/difficulty-levels")
async def get_difficulty_levels():
    """난이도 레벨 정보 조회"""
    return {
        "levels": [
            {
                "id": "beginner",
                "name": "초급",
                "description": "기본적인 업무 상황을 다룹니다",
                "target_audience": "신입사원, 1-2년차",
                "expected_duration": "10-15분"
            },
            {
                "id": "intermediate",
                "name": "중급",
                "description": "복잡한 업무 상황을 다룹니다",
                "target_audience": "3-5년차",
                "expected_duration": "15-25분"
            },
            {
                "id": "advanced",
                "name": "고급",
                "description": "전문적인 업무 상황을 다룹니다",
                "target_audience": "5년차 이상",
                "expected_duration": "25-40분"
            }
        ]
    }
