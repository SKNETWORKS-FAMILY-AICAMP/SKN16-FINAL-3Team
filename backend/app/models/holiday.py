"""
공휴일 모델
"""
from datetime import date, datetime
from typing import Optional

from sqlmodel import SQLModel, Field
from sqlalchemy import UniqueConstraint


class Holiday(SQLModel, table=True):
    """공휴일 테이블"""

    __tablename__ = "holidays"
    __table_args__ = (UniqueConstraint("holiday_date", "name", name="uq_holidays_date_name"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    holiday_date: date = Field(index=True)
    name: str
    is_public_holiday: bool = Field(default=True)
    holiday_type: Optional[str] = Field(
        default=None, description="공공데이터포털 dateKind 값 등 분류 정보"
    )
    data_source: str = Field(default="data.go.kr", description="데이터 출처")
    raw_code: Optional[str] = Field(
        default=None, description="공공데이터포털 seq 등 원본 식별자"
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class HolidayRead(SQLModel):
    """공휴일 응답 모델"""

    holiday_date: date
    name: str
    is_public_holiday: bool = True
    holiday_type: Optional[str] = None
    data_source: Optional[str] = None

    class Config:
        orm_mode = True


