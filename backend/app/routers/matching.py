"""
멘토-멘티 매칭 API
"""
from datetime import date
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session

from app.database import get_session
from app.models.user import User
from app.services.matching_service import (
    MatchingService,
    LearningHistoryNotInitializedError,
)
from app.utils.auth import require_admin

router = APIRouter(prefix="/matching", tags=["matching"])


class MatchingResponse(BaseModel):
    message: str
    matched_count: int
    total_mentees: int
    total_mentors: int
    overall_score: float
    team_statistics: Dict[str, Any]
    report_id: Optional[int]


class MatchingResultsResponse(BaseModel):
    results: List[Dict[str, Any]]
    total: int
    page: int
    page_size: int


class MatchingRunRequest(BaseModel):
    cohort_date: Optional[date] = None


@router.post("/run", response_model=MatchingResponse)
async def run_matching(
    request: Optional[MatchingRunRequest] = None,
    current_user: User = Depends(require_admin),
    session: Session = Depends(get_session),
):
    """N차원 분류 기반 멘토-멘티 매칭 실행"""
    service = MatchingService(session)
    cohort_date = request.cohort_date if request else None
    try:
        result = service.match_all(cohort_date=cohort_date)
        return result
    except LearningHistoryNotInitializedError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        import traceback
        error_detail = f"매칭 실행 실패: {str(exc)}\n{traceback.format_exc()}"
        raise HTTPException(status_code=500, detail=error_detail) from exc


@router.get("/results", response_model=MatchingResultsResponse)
async def get_matching_results(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_admin),
    session: Session = Depends(get_session),
):
    """매칭 결과 조회"""
    service = MatchingService(session)
    return service.get_matching_results(page=page, page_size=page_size)


@router.get("/report")
async def get_matching_report(
    current_user: User = Depends(require_admin),
    session: Session = Depends(get_session),
):
    """최신 매칭 리포트 조회"""
    service = MatchingService(session)
    report = service.get_latest_report()
    
    if not report:
        raise HTTPException(status_code=404, detail="매칭 리포트가 없습니다.")
    
    # 멘티/멘토 정보 포함
    from app.models.training_center import TrainingCenterRecord
    
    report_data = {
        "id": report.id,
        "report_name": report.report_name,
        "report_date": report.report_date.isoformat(),
        "total_mentees": report.total_mentees,
        "total_mentors": report.total_mentors,
        "total_matched": report.total_matched,
        "overall_score": report.overall_score,
        "team_statistics": report.team_statistics,
        "matches": [],
    }
    
    # 매칭 상세 정보 추가
    for match_data in report.report_data.get("matches", []):
        mentee = session.get(TrainingCenterRecord, match_data["mentee_id"])
        mentor = session.get(TrainingCenterRecord, match_data["mentor_id"])
        
        if mentee and mentor:
            report_data["matches"].append({
                "mentee_id": mentee.id,
                "mentee_name": mentee.name,
                "mentee_employee_number": mentee.employee_number,
                "mentee_team": mentee.team,
                "mentee_city": mentee.city,
                "mentor_id": mentor.id,
                "mentor_name": mentor.name,
                "mentor_employee_number": mentor.employee_number,
                "mentor_team": mentor.team,
                "mentor_city": mentor.city,
                "total_score": match_data["total_score"],
                "team_score": match_data["team_score"],
                "city_score": match_data["city_score"],
                "hobby_score": match_data["hobby_score"],
                "weakness_strength_score": match_data.get("weakness_strength_score", 0.0),
                "career_score": match_data.get("career_score", 0.0),
                "major_score": match_data.get("major_score", 0.0),
            })
    
    return report_data

