"""
일정 관리 모델
"""
from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime


class Schedule(SQLModel, table=True):
    """일정 모델"""
    __tablename__ = "schedules"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    description: Optional[str] = None
    start_time: datetime
    end_time: Optional[datetime] = None
    location: Optional[str] = None
    color: Optional[str] = Field(default="#3B82F6")  # 기본 파란색
    
    # 작성자 정보
    author_id: int = Field(foreign_key="users.id")
    
    # 회사 일정 여부 (관리자가 생성한 일정은 모든 사용자에게 표시)
    is_company_schedule: bool = Field(default=False)
    
    # 시스템 필드
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    is_deleted: bool = Field(default=False)


class ScheduleCreate(SQLModel):
    """일정 생성 요청 모델"""
    title: str
    description: Optional[str] = None
    start_time: datetime
    end_time: Optional[datetime] = None
    location: Optional[str] = None
    color: Optional[str] = "#3B82F6"


class ScheduleUpdate(SQLModel):
    """일정 수정 요청 모델"""
    title: Optional[str] = None
    description: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    location: Optional[str] = None
    color: Optional[str] = None


class ScheduleRead(SQLModel):
    """일정 응답 모델"""
    id: int
    title: str
    description: Optional[str] = None
    start_time: datetime
    end_time: Optional[datetime] = None
    location: Optional[str] = None
    color: Optional[str] = "#3B82F6"
    author_id: int
    is_company_schedule: bool = False
    created_at: datetime
    updated_at: Optional[datetime] = None

