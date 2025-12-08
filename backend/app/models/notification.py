"""
알림 모델
사용자에게 표시되는 알림 메시지
"""
from sqlmodel import SQLModel, Field, Column
from sqlalchemy import Text
from typing import Optional
from datetime import datetime


class Notification(SQLModel, table=True):
    """알림 모델"""
    __tablename__ = "notifications"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)  # 알림을 받을 사용자
    
    # 알림 내용
    title: str = Field(max_length=200)  # 알림 제목
    message: str = Field(sa_column=Column(Text))  # 알림 메시지
    type: str = Field(default="info", max_length=50)  # 알림 타입 (info, success, warning, error)
    
    # 관련 정보
    related_type: Optional[str] = Field(default=None, max_length=50)  # 관련 타입 (stt_bug_report, schedule 등)
    related_id: Optional[int] = Field(default=None)  # 관련 ID
    
    # 읽음 상태
    is_read: bool = Field(default=False, index=True)
    read_at: Optional[datetime] = None
    
    # 시스템 필드
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)


class NotificationCreate(SQLModel):
    """알림 생성 요청 모델"""
    user_id: int
    title: str
    message: str
    type: Optional[str] = "info"
    related_type: Optional[str] = None
    related_id: Optional[int] = None


class NotificationRead(SQLModel):
    """알림 조회 모델"""
    id: int
    user_id: int
    title: str
    message: str
    type: str
    related_type: Optional[str]
    related_id: Optional[int]
    is_read: bool
    read_at: Optional[datetime]
    created_at: datetime

