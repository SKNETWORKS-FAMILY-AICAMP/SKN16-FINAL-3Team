"""
일정 관리 API 라우터
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select, or_
from typing import List, Optional, Dict
from datetime import datetime, date, timedelta, time
import logging

from app.database import get_session
from app.models.user import User
from app.models.schedule import (
    Schedule, ScheduleCreate, ScheduleUpdate, ScheduleRead
)
from app.models.holiday import HolidayRead
from app.models.mentor import MentorMenteeRelation
from app.utils.auth import get_current_user, get_current_active_mentor
from app.services.holiday_service import HolidayService

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
            start_datetime = datetime.combine(start_date, time(0, 0, 0))
            statement = statement.where(Schedule.start_time >= start_datetime)
        if end_date:
            # 종료일의 끝까지 포함하기 위해 다음 날 00:00:00 미만으로 비교
            end_datetime = datetime.combine(end_date + timedelta(days=1), time(0, 0, 0))
            statement = statement.where(Schedule.start_time < end_datetime)
        
        statement = statement.order_by(Schedule.start_time.asc())
        
        schedules = session.exec(statement).all()
        
        logger.info(f"Found {len(schedules)} schedules for user {current_user.id} (including company schedules)")
        
        result = []
        for schedule in schedules:
            # None 체크 및 기본값 설정
            if schedule.id is None:
                logger.warning(f"Schedule with None id found, skipping: {schedule}")
                continue
            
            # created_at이 None인 경우 현재 시간 사용
            created_at = schedule.created_at if schedule.created_at else datetime.utcnow()
            
            result.append(
                ScheduleRead(
                    id=schedule.id,
                    title=schedule.title,
                    description=schedule.description,
                    start_time=schedule.start_time,
                    end_time=schedule.end_time,
                    location=schedule.location,
                    color=schedule.color or "#3B82F6",
                    author_id=schedule.author_id,
                    is_company_schedule=schedule.is_company_schedule,
                    created_at=created_at,
                    updated_at=schedule.updated_at
                )
            )
        
        return result
    except Exception as e:
        logger.error(f"Error getting schedules: {str(e)}", exc_info=True)
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to get schedules: {str(e)}")


@router.get("/holidays", response_model=List[HolidayRead])
async def get_holidays(
    year: Optional[int] = None,
    month: Optional[int] = None,
    force_refresh: bool = False,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    공휴일 조회
    - 기본: 현재 연도의 월간 공휴일
    - month를 지정하면 해당 월, 없으면 연 단위
    - force_refresh로 강제 동기화 가능
    """
    _ = current_user  # 접근 제어를 위해 의존성만 사용

    target_year = year or datetime.utcnow().year

    if month is not None and (month < 1 or month > 12):
        raise HTTPException(status_code=400, detail="month는 1~12 사이여야 합니다.")

    try:
        holidays = HolidayService.get_holidays(
            session=session,
            year=target_year,
            month=month,
            force_refresh=force_refresh,
        )

        return holidays
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error getting holidays: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get holidays: {str(e)}")


@router.post("/mentor-mentee-meal")
async def create_mentor_mentee_meal_schedule(
    request: dict,
    current_user: User = Depends(get_current_active_mentor),
    session: Session = Depends(get_session)
):
    """
    멘토-멘티 식사 일정 생성
    - 멘토와 멘티 모두의 일정에 추가됨
    """
    try:
        mentee_id = request.get("mentee_id")
        date_string = request.get("date")  # YYYY-MM-DD 형식
        title = request.get("title", "멘토-멘티와의 식사")
        mentor_description = request.get("mentor_description", "")
        mentee_description = request.get("mentee_description", "")

        logger.info(f"Creating meal schedule - mentor_description: '{mentor_description}', mentee_description: '{mentee_description}'")

        if not mentee_id or not date_string:
            raise HTTPException(status_code=400, detail="mentee_id and date are required")
        
        # 멘티 확인
        mentee = session.exec(select(User).where(User.id == mentee_id)).first()
        if not mentee:
            raise HTTPException(status_code=404, detail="Mentee not found")
        
        # 멘토-멘티 관계 확인
        relation = session.exec(
            select(MentorMenteeRelation).where(
                MentorMenteeRelation.mentor_id == current_user.id,
                MentorMenteeRelation.mentee_id == mentee_id,
                MentorMenteeRelation.is_active == True
            )
        ).first()
        
        if not relation:
            raise HTTPException(status_code=403, detail="No active mentor-mentee relationship found")
        
        # 날짜 파싱 및 시간 설정 (12:00 ~ 13:00)
        try:
            # ISO 형식 (YYYY-MM-DD) 또는 다른 형식 지원
            if 'T' in date_string:
                selected_date = datetime.fromisoformat(date_string.replace('Z', '+00:00')).date()
            else:
                selected_date = datetime.strptime(date_string, "%Y-%m-%d").date()
        except ValueError:
            # 다른 형식 시도
            try:
                selected_date = datetime.fromisoformat(date_string.split('T')[0]).date()
            except:
                raise HTTPException(status_code=400, detail=f"Invalid date format: {date_string}. Expected YYYY-MM-DD")
        
        start_datetime = datetime.combine(selected_date, time(12, 0, 0))
        end_datetime = datetime.combine(selected_date, time(13, 0, 0))
        
        logger.info(f"Creating meal schedule: mentor_id={current_user.id}, mentee_id={mentee_id}, date={selected_date}")
        
        # 멘토 일정 생성
        now = datetime.utcnow()
        mentor_schedule = Schedule(
            title=title,
            description=mentor_description or f"{mentee.name}님과의 식사",
            start_time=start_datetime,
            end_time=end_datetime,
            location=None,
            color="#10B981",  # 초록색
            author_id=current_user.id,
            is_company_schedule=False,
            created_at=now,
            updated_at=now
        )
        session.add(mentor_schedule)
        logger.info(f"Added mentor schedule to session: author_id={current_user.id}, title={title}, description={mentor_schedule.description}")

        # 멘티 일정 생성
        mentee_schedule = Schedule(
            title=title,
            description=mentee_description or f"{current_user.name}님과의 식사",
            start_time=start_datetime,
            end_time=end_datetime,
            location=None,
            color="#10B981",  # 초록색
            author_id=mentee_id,
            is_company_schedule=False,
            created_at=now,
            updated_at=now
        )
        session.add(mentee_schedule)
        logger.info(f"Added mentee schedule to session: author_id={mentee_id}, title={title}")
        
        try:
            session.commit()
            logger.info(f"Committed schedules to database successfully")
        except Exception as commit_error:
            logger.error(f"Error committing schedules: {str(commit_error)}", exc_info=True)
            session.rollback()
            raise
        
        session.refresh(mentor_schedule)
        session.refresh(mentee_schedule)
        
        logger.info(f"Created meal schedule successfully: mentor_schedule_id={mentor_schedule.id}, mentee_schedule_id={mentee_schedule.id}")
        logger.info(f"Mentor schedule details: id={mentor_schedule.id}, author_id={mentor_schedule.author_id}, start_time={mentor_schedule.start_time}")
        logger.info(f"Mentee schedule details: id={mentee_schedule.id}, author_id={mentee_schedule.author_id}, start_time={mentee_schedule.start_time}")
        
        return {
            "message": "Meal schedule created successfully",
            "mentor_schedule_id": mentor_schedule.id,
            "mentee_schedule_id": mentee_schedule.id
        }
        
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Validation error creating meal schedule: {str(e)}")
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Invalid date format: {str(e)}")
    except Exception as e:
        logger.error(f"Error creating meal schedule: {str(e)}", exc_info=True)
        session.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create meal schedule: {str(e)}")


@router.delete("/mentor-mentee-meal/{schedule_id}")
async def delete_mentor_mentee_meal_schedule(
    schedule_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    멘토-멘티 식사 일정 삭제 (양쪽 모두 삭제)
    - 멘토 또는 멘티 모두 호출 가능
    - 해당 일정이 멘토-멘티 식사 일정인지 확인 후 양쪽 모두 삭제
    """
    try:
        # 삭제할 일정 조회
        schedule_statement = select(Schedule).where(
            Schedule.id == schedule_id,
            Schedule.is_deleted == False
        )
        schedule = session.exec(schedule_statement).first()

        if not schedule:
            raise HTTPException(status_code=404, detail="일정을 찾을 수 없습니다.")

        # 현재 사용자가 이 일정의 소유자인지 확인
        if schedule.author_id != current_user.id:
            raise HTTPException(status_code=403, detail="이 일정을 삭제할 권한이 없습니다.")

        # 이 일정이 멘토-멘티 식사 일정인지 확인
        is_meal_schedule = (
            schedule.title == "멘토-멘티와의 식사" and
            schedule.color == "#10B981" and
            schedule.description and
            ("님과 점심식사" in schedule.description)
        )

        if not is_meal_schedule:
            # 일반 일정이면 그냥 현재 일정만 삭제
            schedule.is_deleted = True
            schedule.updated_at = datetime.utcnow()
            session.commit()
            return {"message": "일정이 삭제되었습니다."}

        # 멘토-멘티 식사 일정이면 상대방의 일정도 찾아서 삭제
        target_description = schedule.description

        # 상대방 찾기 로직
        if current_user.role == "mentor":
            # 멘토가 삭제하는 경우: 설명에서 멘티 이름 추출
            mentee_name_match = target_description.replace("님과 점심식사", "")
            if not mentee_name_match:
                raise HTTPException(status_code=400, detail="멘티 이름을 찾을 수 없습니다.")

            # 멘티 찾기
            mentee_statement = select(User).where(
                User.name == mentee_name_match,
                User.role == "mentee"
            )
            mentee = session.exec(mentee_statement).first()

            if not mentee:
                raise HTTPException(status_code=404, detail="짝꿍 멘티를 찾을 수 없습니다.")

            # 상대방(멘티)의 일정 찾기
            partner_schedule_statement = select(Schedule).where(
                Schedule.author_id == mentee.id,
                Schedule.title == "멘토-멘티와의 식사",
                Schedule.color == "#10B981",
                Schedule.start_time == schedule.start_time,
                Schedule.is_deleted == False
            )
            partner_schedule = session.exec(partner_schedule_statement).first()

        else:  # current_user.role == "mentee"
            # 멘티가 삭제하는 경우: 설명에서 멘토 이름 추출
            mentor_name_match = target_description.replace("님과 점심식사", "")
            if not mentor_name_match:
                raise HTTPException(status_code=400, detail="멘토 이름을 찾을 수 없습니다.")

            # 멘토 찾기
            mentor_statement = select(User).where(
                User.name == mentor_name_match,
                User.role == "mentor"
            )
            mentor = session.exec(mentor_statement).first()

            if not mentor:
                raise HTTPException(status_code=404, detail="짝꿍 멘토를 찾을 수 없습니다.")

            # 상대방(멘토)의 일정 찾기
            partner_schedule_statement = select(Schedule).where(
                Schedule.author_id == mentor.id,
                Schedule.title == "멘토-멘티와의 식사",
                Schedule.color == "#10B981",
                Schedule.start_time == schedule.start_time,
                Schedule.is_deleted == False
            )
            partner_schedule = session.exec(partner_schedule_statement).first()

        # 현재 일정 삭제
        schedule.is_deleted = True
        schedule.updated_at = datetime.utcnow()

        # 상대방 일정이 있으면 함께 삭제
        if partner_schedule:
            partner_schedule.is_deleted = True
            partner_schedule.updated_at = datetime.utcnow()
            logger.info(f"짝꿍 일정도 함께 삭제: {partner_schedule.id}")

        session.commit()

        return {"message": "식사 일정이 양쪽 모두 삭제되었습니다."}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting meal schedule: {str(e)}", exc_info=True)
        session.rollback()
        raise HTTPException(status_code=500, detail=f"일정 삭제에 실패했습니다: {str(e)}")


@router.put("/mentor-mentee-meal/{schedule_id}")
async def update_mentor_mentee_meal_schedule(
    schedule_id: int,
    update_data: dict,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    멘토-멘티 식사 일정 수정 (양쪽 모두 수정)
    - 멘토 또는 멘티 모두 호출 가능
    - 해당 일정이 멘토-멘티 식사 일정인지 확인 후 양쪽 모두 수정
    """
    try:
        # 수정할 일정 조회
        schedule_statement = select(Schedule).where(
            Schedule.id == schedule_id,
            Schedule.is_deleted == False
        )
        schedule = session.exec(schedule_statement).first()

        if not schedule:
            raise HTTPException(status_code=404, detail="일정을 찾을 수 없습니다.")

        # 현재 사용자가 이 일정의 소유자인지 확인
        if schedule.author_id != current_user.id:
            raise HTTPException(status_code=403, detail="이 일정을 수정할 권한이 없습니다.")

        # 이 일정이 멘토-멘티 식사 일정인지 확인
        is_meal_schedule = (
            schedule.title == "멘토-멘티와의 식사" and
            schedule.color == "#10B981" and
            schedule.description and
            ("님과 점심식사" in schedule.description)
        )

        if not is_meal_schedule:
            # 일반 일정이면 그냥 현재 일정만 수정
            for key, value in update_data.items():
                if hasattr(schedule, key):
                    setattr(schedule, key, value)
            schedule.updated_at = datetime.utcnow()
            session.commit()
            return {"message": "일정이 수정되었습니다."}

        # 멘토-멘티 식사 일정이면 상대방의 일정도 찾아서 함께 수정
        target_description = schedule.description

        # 상대방 찾기 로직
        if current_user.role == "mentor":
            # 멘토가 수정하는 경우: 설명에서 멘티 이름 추출
            mentee_name_match = target_description.replace("님과 점심식사", "")
            if not mentee_name_match:
                raise HTTPException(status_code=400, detail="멘티 이름을 찾을 수 없습니다.")

            # 멘티 찾기
            mentee_statement = select(User).where(
                User.name == mentee_name_match,
                User.role == "mentee"
            )
            mentee = session.exec(mentee_statement).first()

            if not mentee:
                raise HTTPException(status_code=404, detail="짝꿍 멘티를 찾을 수 없습니다.")

            # 상대방(멘티)의 일정 찾기
            partner_schedule_statement = select(Schedule).where(
                Schedule.author_id == mentee.id,
                Schedule.title == "멘토-멘티와의 식사",
                Schedule.color == "#10B981",
                Schedule.start_time == schedule.start_time,
                Schedule.is_deleted == False
            )
            partner_schedule = session.exec(partner_schedule_statement).first()

        else:  # current_user.role == "mentee"
            # 멘티가 수정하는 경우: 설명에서 멘토 이름 추출
            mentor_name_match = target_description.replace("님과 점심식사", "")
            if not mentor_name_match:
                raise HTTPException(status_code=400, detail="멘토 이름을 찾을 수 없습니다.")

            # 멘토 찾기
            mentor_statement = select(User).where(
                User.name == mentor_name_match,
                User.role == "mentor"
            )
            mentor = session.exec(mentor_statement).first()

            if not mentor:
                raise HTTPException(status_code=404, detail="짝꿍 멘토를 찾을 수 없습니다.")

            # 상대방(멘토)의 일정 찾기
            partner_schedule_statement = select(Schedule).where(
                Schedule.author_id == mentor.id,
                Schedule.title == "멘토-멘티와의 식사",
                Schedule.color == "#10B981",
                Schedule.start_time == schedule.start_time,
                Schedule.is_deleted == False
            )
            partner_schedule = session.exec(partner_schedule_statement).first()

        # 현재 일정 수정
        for key, value in update_data.items():
            if hasattr(schedule, key):
                setattr(schedule, key, value)
        schedule.updated_at = datetime.utcnow()

        # 상대방 일정이 있으면 함께 수정
        if partner_schedule:
            for key, value in update_data.items():
                if hasattr(partner_schedule, key):
                    setattr(partner_schedule, key, value)
            partner_schedule.updated_at = datetime.utcnow()
            logger.info(f"짝꿍 일정도 함께 수정: {partner_schedule.id}")

        session.commit()

        return {"message": "식사 일정이 양쪽 모두 수정되었습니다."}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating meal schedule: {str(e)}", exc_info=True)
        session.rollback()
        raise HTTPException(status_code=500, detail=f"일정 수정에 실패했습니다: {str(e)}")


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
        start_datetime = datetime.combine(monday, time(0, 0, 0))
        # 금요일의 끝까지 포함하기 위해 토요일 00:00:00 미만으로 비교
        end_datetime = datetime.combine(friday + timedelta(days=1), time(0, 0, 0))
        
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
                lunch_start = datetime.combine(check_date, time(11, 0))
                lunch_end = datetime.combine(check_date, time(14, 0))
                
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

