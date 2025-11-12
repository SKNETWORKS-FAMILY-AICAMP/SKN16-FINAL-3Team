"""
동아리 라운지 게시판 모델
멘토·멘티 취미 공유 커뮤니티
"""
from sqlmodel import SQLModel, Field, Column
from sqlalchemy import Text
from typing import Optional, List
from datetime import datetime


class Post(SQLModel, table=True):
    """게시글 모델"""
    __tablename__ = "posts"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    content: str = Field(sa_column=Column(Text))
    category: str = Field(default="기타", max_length=50, description="취미 카테고리")
    subcategory: Optional[str] = Field(default=None, max_length=50, description="취미 세부 카테고리")
    
    # 익명성 보장: 작성자 ID는 저장하지만 표시하지 않음
    author_id: int = Field(foreign_key="users.id")
    
    # 통계
    view_count: int = Field(default=0)
    comment_count: int = Field(default=0)
    
    # 시스템 필드
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    is_deleted: bool = Field(default=False)


class PostCreate(SQLModel):
    """게시글 작성 요청 모델"""
    title: str
    content: str
    category: str = Field(default="기타", max_length=50)
    subcategory: Optional[str] = Field(default=None, max_length=50)


class PostRead(SQLModel):
    """게시글 응답 모델 (익명 처리)"""
    id: int
    title: str
    content: str
    category: str
    subcategory: Optional[str] = None
    view_count: int
    comment_count: int
    created_at: datetime
    updated_at: datetime
    author_alias: str = ""
    author_name: Optional[str] = None
    author_role_label: Optional[str] = None


class Comment(SQLModel, table=True):
    """댓글 모델"""
    __tablename__ = "comments"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    post_id: int = Field(foreign_key="posts.id")
    content: str = Field(sa_column=Column(Text))
    
    # 익명성 보장
    author_id: int = Field(foreign_key="users.id")
    
    # 댓글 순서 (익명2, 익명3... 순서 결정)
    comment_order: int = Field(default=0)

    # 같이하기 기능 확장 필드
    join_status: str = Field(default="none", max_length=20, description="같이하기 상태 (none|pending|approved)")
    join_approved_at: Optional[datetime] = Field(default=None)
    
    # 시스템 필드
    created_at: datetime = Field(default_factory=datetime.utcnow)
    is_deleted: bool = Field(default=False)


class CommentCreate(SQLModel):
    """댓글 작성 요청 모델"""
    post_id: int
    content: str


class CommentRead(SQLModel):
    """댓글 응답 모델 (익명 처리)"""
    id: int
    post_id: int
    content: str
    join_status: str = "none"
    join_approved_at: Optional[datetime] = None
    created_at: datetime
    author_alias: str  # 익명2, 익명3... 형태
    is_author: bool = False  # 현재 사용자가 작성자인지
    is_admin: bool = False   # 현재 사용자가 관리자인지
    author_name: Optional[str] = None
    author_role_label: Optional[str] = None


class PostDetail(SQLModel):
    """게시글 상세 정보 (댓글 포함)"""
    post: PostRead
    comments: List[CommentRead] = []
    is_author: bool = False  # 현재 사용자가 작성자인지
    is_admin: bool = False   # 현재 사용자가 관리자인지
