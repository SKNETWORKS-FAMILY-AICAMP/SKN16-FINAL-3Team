"""
연수원(Training Center) 데이터 API
"""
from datetime import date
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session

from app.database import get_session
from app.models.user import User
from app.services.training_center_service import TrainingCenterService
from app.utils.auth import require_admin

router = APIRouter(prefix="/training-center", tags=["training_center"])


class TrainingCenterSyncRequest(BaseModel):
    selected_cohort_dates: List[str]
    create_accounts: bool = False
    create_mentees: bool = True
    create_mentors: bool = True


class TrainingCenterSyncResponse(BaseModel):
    message: str
    generated_months: int
    generated_mentees: int
    generated_mentors: int
    total_mentees: int
    total_mentors: int
    last_synced_at: Optional[str]
    created_accounts: int = 0


class TrainingCenterRecordsResponse(BaseModel):
    records: List[Dict[str, Any]]
    total: int
    page: int
    page_size: int
    total_cohorts: int
    cohorts: List[Dict[str, Any]]
    employee_type: Optional[str]
    last_synced_at: Optional[str]


class DeleteRecordsRequest(BaseModel):
    record_ids: List[int]


class DeleteRecordsResponse(BaseModel):
    message: str
    deleted_count: int


@router.post("/sync", response_model=TrainingCenterSyncResponse)
async def sync_training_center_data(
    request: TrainingCenterSyncRequest,
    current_user: User = Depends(require_admin),
    session: Session = Depends(get_session),
):
    """연수원 DB 재구성 (신입 멘티, 멘토 풀 생성)
    
    Request body:
        selected_cohort_dates: List[str] - 생성할 기수 날짜 리스트 (YYYY-MM-DD 형식)
        create_accounts: bool - User 계정도 함께 생성할지 여부
        create_mentees: bool - 멘티 생성 여부
        create_mentors: bool - 멘토 생성 여부
    """
    from datetime import datetime
    
    service = TrainingCenterService(session)
    
    selected_cohort_dates = [
        datetime.fromisoformat(d).date() 
        for d in request.selected_cohort_dates
    ]
    
    result = service.rebuild_dataset(
        selected_cohort_dates=selected_cohort_dates,
        create_accounts=request.create_accounts,
        create_mentees=request.create_mentees,
        create_mentors=request.create_mentors,
    )
    return result


@router.get("/records", response_model=TrainingCenterRecordsResponse)
async def list_training_center_records(
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=10000),
    cohort_date: Optional[date] = Query(
        None,
        description="기수 수료 날짜(YYYY-MM-DD)",
    ),
    search: Optional[str] = Query(
        None, description="이름 또는 사번 검색 키워드"
    ),
    current_user: User = Depends(require_admin),
    session: Session = Depends(get_session),
):
    """전체 연수원 데이터 조회"""
    service = TrainingCenterService(session)
    try:
        data = service.list_records(
            page=page,
            page_size=page_size,
            cohort_date=cohort_date,
            search=search,
        )
        return data
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/mentees", response_model=TrainingCenterRecordsResponse)
async def list_training_center_mentees(
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=10000),
    cohort_date: Optional[date] = Query(None, description="기수 수료 날짜"),
    search: Optional[str] = Query(None, description="이름 또는 사번 검색"),
    current_user: User = Depends(require_admin),
    session: Session = Depends(get_session),
):
    """신입 멘티 데이터 조회"""
    service = TrainingCenterService(session)
    return service.list_records(
        page=page,
        page_size=page_size,
        cohort_date=cohort_date,
        search=search,
        employee_type="mentee",
    )


@router.get("/mentors", response_model=TrainingCenterRecordsResponse)
async def list_training_center_mentors(
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=10000),
    cohort_date: Optional[date] = Query(None, description="코호트 선택"),
    search: Optional[str] = Query(None, description="이름 또는 사번 검색"),
    current_user: User = Depends(require_admin),
    session: Session = Depends(get_session),
):
    """기존 사원(멘토) 데이터 조회"""
    service = TrainingCenterService(session)
    return service.list_records(
        page=page,
        page_size=page_size,
        cohort_date=cohort_date,
        search=search,
        employee_type="mentor",
    )


@router.delete("/records", response_model=DeleteRecordsResponse)
async def delete_training_center_records(
    request: DeleteRecordsRequest,
    current_user: User = Depends(require_admin),
    session: Session = Depends(get_session),
):
    """선택된 연수원 레코드 삭제"""
    service = TrainingCenterService(session)
    try:
        deleted_count = service.delete_records(request.record_ids)
        return DeleteRecordsResponse(
            message=f"{deleted_count}개의 레코드가 삭제되었습니다.",
            deleted_count=deleted_count,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.delete("/records/all", response_model=DeleteRecordsResponse)
async def delete_all_training_center_records(
    current_user: User = Depends(require_admin),
    session: Session = Depends(get_session),
):
    """전체 연수원 데이터 삭제 (매칭 결과 포함)"""
    service = TrainingCenterService(session)
    try:
        deleted_count = service.delete_all_records()
        return DeleteRecordsResponse(
            message=f"전체 {deleted_count}개의 레코드가 삭제되었습니다.",
            deleted_count=deleted_count,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


