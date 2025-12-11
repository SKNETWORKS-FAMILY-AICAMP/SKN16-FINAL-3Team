"""
STT 버그 신고 모델
사용자가 STT 오인식 문제를 신고할 수 있는 기능
"""
from sqlmodel import SQLModel, Field, Column
from sqlalchemy import Text
from typing import Optional
from datetime import datetime


class STTBugReport(SQLModel, table=True):
    """STT 버그 신고"""
    __tablename__ = "stt_bug_reports"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    
    # 피드백 정보 (어떤 평가서에서 신고했는지)
    feedback_id: Optional[int] = Field(foreign_key="simulation_feedbacks.id", index=True)
    
    # 대화 로그 정보
    conversation_index: int  # 대화 로그에서 몇 번째 메시지인지
    message_role: str  # 'employee' 또는 'customer'
    original_text: str = Field(sa_column=Column(Text))  # 사용자가 실제로 말한 내용
    recognized_text: str = Field(sa_column=Column(Text))  # STT가 인식한 내용 (오인식된 내용)
    
    # 상세 설명
    description: Optional[str] = Field(default=None, sa_column=Column(Text))  # 사용자가 작성한 상세 설명
    
    # 상태
    status: str = Field(default="pending", max_length=20)  # pending, resolved, rejected
    admin_comment: Optional[str] = Field(default=None, sa_column=Column(Text))  # 관리자 답변
    
    # 메타 정보
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[int] = Field(default=None, foreign_key="users.id")  # 해결한 관리자 ID


class STTBugReportCreate(SQLModel):
    """STT 버그 신고 생성 요청 모델"""
    feedback_id: Optional[int] = None
    conversation_index: int
    message_role: str
    original_text: str
    recognized_text: str
    description: Optional[str] = None


class STTBugReportRead(SQLModel):
    """STT 버그 신고 조회 모델"""
    id: int
    user_id: int
    feedback_id: Optional[int]
    conversation_index: int
    message_role: str
    original_text: str
    recognized_text: str
    description: Optional[str]
    status: str
    admin_comment: Optional[str]
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime]
    resolved_by: Optional[int]
    # 추가 정보
    user_name: Optional[str] = None
    feedback_overall_score: Optional[float] = None

