"""
일정 관리 API 라우터
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from typing import List, Optional
from datetime import datetime, date

from app.database import get_session
from app.models.user import User
from app.models.schedule import (
    Schedule, ScheduleCreate, ScheduleUpdate, ScheduleRead
)
from app.utils.auth import get_current_user

router = APIRouter(prefix="/schedules", tags=["Schedule"])


@router.post("/", response_model=ScheduleRead)
async def create_schedule(
    schedule_data: ScheduleCreate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    일정 생성
    """
    schedule = Schedule(
        title=schedule_data.title,
        description=schedule_data.description,
        start_time=schedule_data.start_time,
        end_time=schedule_data.end_time,
        location=schedule_data.location,
        color=schedule_data.color or "#3B82F6",
        author_id=current_user.id
    )
    
    session.add(schedule)
    session.commit()
    session.refresh(schedule)
    
    return ScheduleRead(
        id=schedule.id,
        title=schedule.title,
        description=schedule.description,
        start_time=schedule.start_time,
        end_time=schedule.end_time,
        location=schedule.location,
        color=schedule.color,
        author_id=schedule.author_id,
        created_at=schedule.created_at,
        updated_at=schedule.updated_at
    )


@router.get("/", response_model=List[ScheduleRead])
async def get_schedules(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    일정 목록 조회
    - 날짜 범위로 필터링 가능
    - 사용자 본인의 일정만 조회
    """
    statement = select(Schedule).where(
        Schedule.author_id == current_user.id,
        Schedule.is_deleted == False
    )
    
    # 날짜 범위 필터링
    if start_date:
        statement = statement.where(Schedule.start_time >= datetime.combine(start_date, datetime.min.time()))
    if end_date:
        statement = statement.where(Schedule.start_time <= datetime.combine(end_date, datetime.max.time()))
    
    statement = statement.order_by(Schedule.start_time.asc())
    
    schedules = session.exec(statement).all()
    
    return [
        ScheduleRead(
            id=schedule.id,
            title=schedule.title,
            description=schedule.description,
            start_time=schedule.start_time,
            end_time=schedule.end_time,
            location=schedule.location,
            color=schedule.color,
            author_id=schedule.author_id,
            created_at=schedule.created_at,
            updated_at=schedule.updated_at
        )
        for schedule in schedules
    ]


@router.get("/{schedule_id}", response_model=ScheduleRead)
async def get_schedule(
    schedule_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    일정 상세 조회
    """
    statement = select(Schedule).where(
        Schedule.id == schedule_id,
        Schedule.is_deleted == False
    )
    schedule = session.exec(statement).first()
    
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    
    # 작성자 본인 또는 관리자만 조회 가능
    if schedule.author_id != current_user.id and current_user.role.value != "admin":
        raise HTTPException(status_code=403, detail="Not authorized to view this schedule")
    
    return ScheduleRead(
        id=schedule.id,
        title=schedule.title,
        description=schedule.description,
        start_time=schedule.start_time,
        end_time=schedule.end_time,
        location=schedule.location,
        color=schedule.color,
        author_id=schedule.author_id,
        created_at=schedule.created_at,
        updated_at=schedule.updated_at
    )


@router.put("/{schedule_id}", response_model=ScheduleRead)
async def update_schedule(
    schedule_id: int,
    schedule_data: ScheduleUpdate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    일정 수정
    - 작성자 본인 또는 관리자만 수정 가능
    """
    statement = select(Schedule).where(
        Schedule.id == schedule_id,
        Schedule.is_deleted == False
    )
    schedule = session.exec(statement).first()
    
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    
    # 작성자 본인 또는 관리자만 수정 가능
    if schedule.author_id != current_user.id and current_user.role.value != "admin":
        raise HTTPException(status_code=403, detail="Not authorized to update this schedule")
    
    # 일정 수정
    if schedule_data.title is not None:
        schedule.title = schedule_data.title
    if schedule_data.description is not None:
        schedule.description = schedule_data.description
    if schedule_data.start_time is not None:
        schedule.start_time = schedule_data.start_time
    if schedule_data.end_time is not None:
        schedule.end_time = schedule_data.end_time
    if schedule_data.location is not None:
        schedule.location = schedule_data.location
    if schedule_data.color is not None:
        schedule.color = schedule_data.color
    
    schedule.updated_at = datetime.utcnow()
    session.add(schedule)
    session.commit()
    session.refresh(schedule)
    
    return ScheduleRead(
        id=schedule.id,
        title=schedule.title,
        description=schedule.description,
        start_time=schedule.start_time,
        end_time=schedule.end_time,
        location=schedule.location,
        color=schedule.color,
        author_id=schedule.author_id,
        created_at=schedule.created_at,
        updated_at=schedule.updated_at
    )


@router.delete("/{schedule_id}")
async def delete_schedule(
    schedule_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    일정 삭제
    - 작성자 본인 또는 관리자만 삭제 가능
    """
    statement = select(Schedule).where(Schedule.id == schedule_id)
    schedule = session.exec(statement).first()
    
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    
    # 작성자 본인 또는 관리자만 삭제 가능
    if schedule.author_id != current_user.id and current_user.role.value != "admin":
        raise HTTPException(status_code=403, detail="Not authorized to delete this schedule")
    
    schedule.is_deleted = True
    session.add(schedule)
    session.commit()
    
    return {"message": "Schedule deleted successfully"}

