"""
일정 관리 API 라우터
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select, or_
from typing import List, Optional, Dict
from datetime import datetime, date, timedelta
import logging

from app.database import get_session
from app.models.user import User
from app.models.schedule import (
    Schedule, ScheduleCreate, ScheduleUpdate, ScheduleRead
)
from app.models.mentor import MentorMenteeRelation
from app.utils.auth import get_current_user, get_current_active_mentor

router = APIRouter(prefix="/schedules", tags=["Schedule"])
logger = logging.getLogger(__name__)


@router.post("/", response_model=ScheduleRead)
async def create_schedule(
    schedule_data: ScheduleCreate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    일정 생성
    """
    try:
        logger.info(f"Creating schedule for user {current_user.id}: {schedule_data.title}")
        logger.info(f"Schedule data received: title={schedule_data.title}, start_time={schedule_data.start_time}, end_time={schedule_data.end_time}")
        logger.debug(f"Full schedule data: {schedule_data.dict()}")
        
        # 데이터 검증
        if not schedule_data.start_time:
            raise ValueError("start_time is required")
        
        # 관리자가 생성한 일정은 회사 일정으로 설정 (모든 사용자에게 표시)
        is_company_schedule = current_user.role.value == "admin"
        
        schedule = Schedule(
            title=schedule_data.title,
            description=schedule_data.description,
            start_time=schedule_data.start_time,
            end_time=schedule_data.end_time,
            location=schedule_data.location,
            color=schedule_data.color or "#3B82F6",
            author_id=current_user.id,
            is_company_schedule=is_company_schedule
        )
        
        logger.info(f"Schedule object created, adding to session...")
        session.add(schedule)
        logger.info(f"Committing to database...")
        session.commit()
        logger.info(f"Schedule committed, refreshing...")
        session.refresh(schedule)
        logger.info(f"Schedule created successfully with id={schedule.id}")
        
        return ScheduleRead(
            id=schedule.id,
            title=schedule.title,
            description=schedule.description,
            start_time=schedule.start_time,
            end_time=schedule.end_time,
            location=schedule.location,
            color=schedule.color,
            author_id=schedule.author_id,
            is_company_schedule=schedule.is_company_schedule,
            created_at=schedule.created_at,
            updated_at=schedule.updated_at
        )
    except ValueError as e:
        logger.error(f"Validation error creating schedule: {str(e)}")
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Invalid schedule data: {str(e)}")
    except Exception as e:
        logger.error(f"Error creating schedule: {str(e)}", exc_info=True)
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        session.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create schedule: {str(e)}")


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
    - 사용자 본인의 일정 + 회사 일정(관리자가 생성한 일정) 조회
    """
    try:
        logger.info(f"Getting schedules for user {current_user.id}, start_date={start_date}, end_date={end_date}")
        
        # 사용자 본인의 일정 또는 회사 일정 조회
        statement = select(Schedule).where(
            or_(
                Schedule.author_id == current_user.id,
                Schedule.is_company_schedule == True
            ),
            Schedule.is_deleted == False
        )
        
        # 날짜 범위 필터링
        if start_date:
            statement = statement.where(Schedule.start_time >= datetime.combine(start_date, datetime.min.time()))
        if end_date:
            statement = statement.where(Schedule.start_time <= datetime.combine(end_date, datetime.max.time()))
        
        statement = statement.order_by(Schedule.start_time.asc())
        
        schedules = session.exec(statement).all()
        
        logger.info(f"Found {len(schedules)} schedules for user {current_user.id} (including company schedules)")
        
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
                is_company_schedule=schedule.is_company_schedule,
                created_at=schedule.created_at,
                updated_at=schedule.updated_at
            )
            for schedule in schedules
        ]
    except Exception as e:
        logger.error(f"Error getting schedules: {str(e)}", exc_info=True)
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to get schedules: {str(e)}")


@router.get("/common-free-slots")
async def get_common_free_slots(
    current_user: User = Depends(get_current_active_mentor),
    session: Session = Depends(get_session)
):
    """
    멘토-멘티 공통 빈 일정 찾기
    - 월요일부터 금요일까지 1주일 범위
    - 오전 11시부터 오후 2시까지 빈 시간 찾기
    - 멘토만 접근 가능
    """
    try:
        logger.info(f"Getting common free slots for mentor {current_user.id}")
        # 멘토의 매칭된 멘티 목록 조회
        relation_statement = select(MentorMenteeRelation).where(
            MentorMenteeRelation.mentor_id == current_user.id,
            MentorMenteeRelation.is_active == True
        )
        relations = session.exec(relation_statement).all()
        
        if not relations:
            return {
                "common_free_slots": [],
                "mentees": []
            }
        
        # 오늘 날짜 기준으로 이번 주 월요일 찾기
        today = datetime.now().date()
        days_since_monday = today.weekday()  # 0=월요일, 6=일요일
        monday = today - timedelta(days=days_since_monday)
        friday = monday + timedelta(days=4)  # 금요일
        
        # 멘티 정보 수집
        mentee_ids = [rel.mentee_id for rel in relations]
        if not mentee_ids:
            return {
                "common_free_slots": [],
                "mentees": []
            }
        
        mentee_statement = select(User).where(User.id.in_(mentee_ids))
        mentees = session.exec(mentee_statement).all()
        mentee_dict = {mentee.id: mentee for mentee in mentees}
        
        # 멘토와 멘티들의 일정 조회 (월요일~금요일, 오전 11시~오후 2시)
        start_datetime = datetime.combine(monday, datetime.min.time())
        end_datetime = datetime.combine(friday, datetime.max.time())
        
        # 멘토 일정
        mentor_schedules_statement = select(Schedule).where(
            Schedule.author_id == current_user.id,
            Schedule.is_deleted == False,
            Schedule.start_time >= start_datetime,
            Schedule.start_time <= end_datetime
        )
        mentor_schedules = session.exec(mentor_schedules_statement).all()
        
        # 멘티 일정
        mentee_schedules_statement = select(Schedule).where(
            Schedule.author_id.in_(mentee_ids),
            Schedule.is_deleted == False,
            Schedule.start_time >= start_datetime,
            Schedule.start_time <= end_datetime
        )
        mentee_schedules = session.exec(mentee_schedules_statement).all()
        
        # 각 멘티별로 공통 빈 시간 찾기
        result = []
        
        for relation in relations:
            mentee_id = relation.mentee_id
            mentee = mentee_dict.get(mentee_id)
            
            if not mentee:
                continue
            
            # 해당 멘티의 일정만 필터링
            current_mentee_schedules = [s for s in mentee_schedules if s.author_id == mentee_id]
            
            # 월요일~금요일, 각 날짜의 11:00~14:00 시간대 확인
            common_free_dates = []
            
            for day_offset in range(5):  # 월요일(0) ~ 금요일(4)
                check_date = monday + timedelta(days=day_offset)
                
                # 11:00~14:00 시간대가 비어있는지 확인
                lunch_start = datetime.combine(check_date, datetime.min.time().replace(hour=11, minute=0))
                lunch_end = datetime.combine(check_date, datetime.min.time().replace(hour=14, minute=0))
                
                # 멘토 일정 확인
                mentor_busy = False
                for schedule in mentor_schedules:
                    schedule_start = schedule.start_time
                    schedule_end = schedule.end_time if schedule.end_time else schedule.start_time
                    
                    # 일정이 점심 시간대와 겹치는지 확인
                    if schedule_start < lunch_end and schedule_end > lunch_start:
                        mentor_busy = True
                        break
                
                # 멘티 일정 확인
                mentee_busy = False
                for schedule in current_mentee_schedules:
                    schedule_start = schedule.start_time
                    schedule_end = schedule.end_time if schedule.end_time else schedule.start_time
                    
                    # 일정이 점심 시간대와 겹치는지 확인
                    if schedule_start < lunch_end and schedule_end > lunch_start:
                        mentee_busy = True
                        break
                
                # 둘 다 비어있으면 공통 빈 시간
                if not mentor_busy and not mentee_busy:
                    common_free_dates.append(check_date.isoformat())
            
            if common_free_dates:
                result.append({
                    "mentee_id": mentee_id,
                    "mentee_name": mentee.name,
                    "free_dates": common_free_dates
                })
        
        response_data = {
            "common_free_slots": result,
            "mentees": [
                {
                    "id": mentee.id,
                    "name": mentee.name
                }
                for mentee in mentees
            ]
        }
        
        logger.info(f"Returning {len(result)} common free slots for {len(mentees)} mentees")
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting common free slots: {str(e)}", exc_info=True)
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to get common free slots: {str(e)}")


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
    
    # 작성자 본인, 관리자, 또는 회사 일정인 경우 조회 가능
    if schedule.author_id != current_user.id and current_user.role.value != "admin" and not schedule.is_company_schedule:
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
        is_company_schedule=schedule.is_company_schedule,
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
    try:
        logger.info(f"Updating schedule {schedule_id} for user {current_user.id}")
        logger.debug(f"Update data: {schedule_data.dict()}")
        
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
            is_company_schedule=schedule.is_company_schedule,
            created_at=schedule.created_at,
            updated_at=schedule.updated_at
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating schedule {schedule_id}: {str(e)}", exc_info=True)
        session.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update schedule: {str(e)}")


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
    try:
        logger.info(f"Deleting schedule {schedule_id} for user {current_user.id} (role: {current_user.role.value})")
        
        statement = select(Schedule).where(
            Schedule.id == schedule_id,
            Schedule.is_deleted == False
        )
        schedule = session.exec(statement).first()
        
        if not schedule:
            logger.warning(f"Schedule {schedule_id} not found or already deleted")
            raise HTTPException(status_code=404, detail="Schedule not found")
        
        logger.info(f"Schedule found: id={schedule.id}, author_id={schedule.author_id}, current_user_id={current_user.id}")
        
        # 작성자 본인 또는 관리자만 삭제 가능
        if schedule.author_id != current_user.id and current_user.role.value != "admin":
            logger.warning(f"User {current_user.id} (role: {current_user.role.value}) attempted to delete schedule {schedule_id} owned by user {schedule.author_id}")
            raise HTTPException(status_code=403, detail="Not authorized to delete this schedule")
        
        schedule.is_deleted = True
        session.add(schedule)
        session.commit()
        
        logger.info(f"Schedule {schedule_id} deleted successfully by user {current_user.id}")
        return {"message": "Schedule deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting schedule {schedule_id}: {str(e)}", exc_info=True)
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        session.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete schedule: {str(e)}")

