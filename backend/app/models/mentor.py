"""
멘토-멘티 관계 및 학습 관리 모델
"""
from sqlmodel import SQLModel, Field, Column
from sqlalchemy import Text, JSON
from typing import Optional, List, Dict
from datetime import datetime


class MentorMenteeRelation(SQLModel, table=True):
    """멘토-멘티 관계 테이블"""
    __tablename__ = "mentor_mentee_relations"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    mentor_id: int = Field(foreign_key="users.id")
    mentee_id: int = Field(foreign_key="users.id")
    
    # 매칭 정보
    matched_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = Field(default=True)
    
    # 메모 (멘토가 멘티에 대해 작성)
    notes: Optional[str] = Field(default=None, sa_column=Column(Text))


class ExamScore(SQLModel, table=True):
    """연수원 시험 점수 (멘티용)"""
    __tablename__ = "exam_scores"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    mentee_id: int = Field(foreign_key="users.id")
    
    # 시험 정보
    exam_name: str  # 시험명
    exam_date: datetime
    
    # 점수 (레이더 차트용 - 최대 6개 항목)
    score_data: str = Field(sa_column=Column(Text))  # JSON 형태: {"은행업무": 85, "상품지식": 90, ...}
    total_score: float
    
    # 평가
    grade: Optional[str] = None  # A, B, C 등급
    feedback: Optional[str] = Field(default=None, sa_column=Column(Text))
    
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ExamQuestion(SQLModel, table=True):
    """시험 문제 데이터베이스"""
    __tablename__ = "exam_questions"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    q_id: str = Field(unique=True, index=True)  # BO001, PK001 등
    question: str = Field(sa_column=Column(Text))
    question_type: str = Field(default="multiple_choice")  # multiple_choice, essay 등
    options: str = Field(sa_column=Column(Text))  # JSON 형태로 저장
    correct_answer: str
    difficulty: str = Field(default="basic")  # basic, intermediate, advanced
    learning_topic: str  # RAG 검색용 키워드
    explanation: str = Field(sa_column=Column(Text))
    
    # 섹션 정보
    section_id: int
    section_name: str
    
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ExamResult(SQLModel, table=True):
    """상세 시험 결과 (문제별 정답/오답)"""
    __tablename__ = "exam_results"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    mentee_id: int = Field(foreign_key="users.id")
    exam_score_id: int = Field(foreign_key="exam_scores.id")
    
    # 문제별 결과
    q_id: str = Field(foreign_key="exam_questions.q_id")
    user_answer: str
    is_correct: bool
    time_spent: Optional[int] = None  # 초 단위
    
    # 취약점 분석용
    learning_topic: str  # 해당 문제의 학습 주제
    
    created_at: datetime = Field(default_factory=datetime.utcnow)


class LearningTopic(SQLModel, table=True):
    """학습 주제별 진도 관리"""
    __tablename__ = "learning_topics"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    mentee_id: int = Field(foreign_key="users.id")
    topic_name: str  # "예금상품의 이해", "파생결합증권" 등
    topic_category: str  # "은행업무", "상품지식" 등
    
    # 학습 진도
    is_studied: bool = Field(default=False)
    study_date: Optional[datetime] = None
    study_duration: Optional[int] = None  # 초 단위
    
    # 관련 문제들
    related_questions: str = Field(default="[]", sa_column=Column(Text))  # JSON 배열
    
    # AI 추천 관련
    priority_score: float = Field(default=0.0)  # 우선순위 점수 (0-100)
    weak_areas: str = Field(default="[]", sa_column=Column(Text))  # JSON 배열
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ChatHistory(SQLModel, table=True):
    """챗봇 대화 기록"""
    __tablename__ = "chat_histories"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id")
    
    # 대화 내용
    user_message: str = Field(sa_column=Column(Text))
    bot_response: str = Field(sa_column=Column(Text))
    
    # RAG 관련 메타데이터
    source_documents: Optional[str] = None  # JSON 형태로 참조 문서 저장
    response_time: Optional[float] = None  # 응답 시간 (초)
    
    # 피드백
    is_helpful: Optional[bool] = None  # 사용자 피드백
    
    created_at: datetime = Field(default_factory=datetime.utcnow)


class LearningProgress(SQLModel):
    """학습 진행도 (응답용 모델)"""
    mentee_id: int
    total_chats: int
    documents_accessed: int
    recent_topics: List[str]
    progress_percentage: float


class MentorDashboard(SQLModel):
    """멘토 대시보드 데이터"""
    mentor_id: int
    mentees: List[Dict]  # 담당 멘티 목록
    frequent_questions: List[Dict]  # 자주 묻는 질문 키워드
    mentee_scores: Dict  # 멘티별 성적


class Feedback(SQLModel, table=True):
    """멘토 피드백 테이블"""
    __tablename__ = "feedbacks"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    mentor_id: int = Field(foreign_key="users.id")
    mentee_id: int = Field(foreign_key="users.id")
    
    # 피드백 내용
    feedback_text: str = Field(sa_column=Column(Text))
    feedback_type: str = Field(default="general")  # general, performance, improvement
    
    # 색상 섹션 (red, orange, yellow, gray)
    color_section: Optional[str] = Field(default="red")
    
    # 피드백 상태
    is_read: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    read_at: Optional[datetime] = None


class FeedbackComment(SQLModel, table=True):
    """피드백 댓글 테이블"""
    __tablename__ = "feedback_comments"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    feedback_id: int = Field(foreign_key="feedbacks.id")
    user_id: int = Field(foreign_key="users.id")  # 댓글 작성자 (멘토 또는 멘티)
    
    # 댓글 내용
    comment_text: str = Field(sa_column=Column(Text))
    
    # 댓글 상태
    is_deleted: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class MenteeDashboard(SQLModel):
    """멘티 대시보드 데이터"""
    mentee_id: int
    mentor_info: Optional[Dict] = None  # 담당 멘토 정보
    exam_scores: List[Dict] = []  # 시험 점수 목록
    learning_progress: Optional[LearningProgress] = None
    recent_chats: List[Dict] = []
    performance_scores: Optional[Dict] = None  # 6가지 지표 성적표
    recent_feedbacks: List[Dict] = []  # 최근 피드백 목록



