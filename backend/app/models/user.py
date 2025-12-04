"""
사용자 모델
역할: admin, mentor, mentee
"""
from sqlmodel import SQLModel, Field, Column
from sqlalchemy import JSON
from typing import Optional, List
from datetime import datetime
from enum import Enum


class UserRole(str, Enum):
    """사용자 역할"""
    ADMIN = "admin"
    MENTOR = "mentor"
    MENTEE = "mentee"


class User(SQLModel, table=True):
    """사용자 모델"""
    __tablename__ = "users"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    hashed_password: str
    name: str
    role: UserRole = Field(default=UserRole.MENTEE)
    
    # 프로필 정보
    photo_url: Optional[str] = None
    phone: Optional[str] = None
    interests: Optional[str] = None  # JSON 문자열로 저장
    hobbies: Optional[str] = None
    specialties: Optional[str] = None
    team: Optional[str] = None  # 부서
    team_number: Optional[str] = None  # 팀 번호
    mbti: Optional[str] = None  # MBTI 성격유형
    
    # 회사 정보
    employee_number: Optional[str] = None  # 사원번호
    join_year: Optional[int] = None  # 입사년도
    position: Optional[str] = None  # 직책
    extension: Optional[str] = None  # 내선번호
    emergency_contact: Optional[str] = None  # 비상 연락망
    
    # 멘토 전용 필드
    encouragement_message: Optional[str] = None  # 응원 메시지
    
    # 기수 정보 (예: "2025년 4기 멘티", "2025년 4기 멘토")
    cohort_label: Optional[str] = None  # 기수 라벨
    
    # 시스템 필드
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class UserCreate(SQLModel):
    """사용자 생성 모델"""
    email: str
    password: str
    name: str
    role: UserRole = UserRole.MENTEE
    photo_url: Optional[str] = None
    phone: Optional[str] = None
    interests: Optional[str] = None
    hobbies: Optional[str] = None
    specialties: Optional[str] = None
    team: Optional[str] = None
    team_number: Optional[str] = None
    employee_number: Optional[str] = None
    join_year: Optional[int] = None
    position: Optional[str] = None
    extension: Optional[str] = None
    emergency_contact: Optional[str] = None
    encouragement_message: Optional[str] = None
    mbti: Optional[str] = None
    cohort_label: Optional[str] = None


class UserRead(SQLModel):
    """사용자 정보 응답 모델 (비밀번호 제외)"""
    id: int
    email: str
    name: str
    role: UserRole
    photo_url: Optional[str] = None
    phone: Optional[str] = None
    interests: Optional[str] = None
    hobbies: Optional[str] = None
    specialties: Optional[str] = None
    team: Optional[str] = None
    team_number: Optional[str] = None
    mbti: Optional[str] = None
    employee_number: Optional[str] = None
    join_year: Optional[int] = None
    position: Optional[str] = None
    extension: Optional[str] = None
    emergency_contact: Optional[str] = None
    encouragement_message: Optional[str] = None
    cohort_label: Optional[str] = None
    is_active: bool
    created_at: datetime


class UserUpdate(SQLModel):
    """사용자 정보 수정 모델"""
    name: Optional[str] = None
    photo_url: Optional[str] = None
    phone: Optional[str] = None
    interests: Optional[str] = None
    hobbies: Optional[str] = None
    specialties: Optional[str] = None
    team: Optional[str] = None
    team_number: Optional[str] = None
    mbti: Optional[str] = None
    employee_number: Optional[str] = None
    join_year: Optional[int] = None
    position: Optional[str] = None
    extension: Optional[str] = None
    emergency_contact: Optional[str] = None
    encouragement_message: Optional[str] = None
    password: Optional[str] = None
    cohort_label: Optional[str] = None


class Token(SQLModel):
    """JWT 토큰 응답 모델"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenData(SQLModel):
    """토큰 페이로드 데이터"""
    email: Optional[str] = None
    role: Optional[str] = None


