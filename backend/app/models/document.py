"""
문서 및 벡터 임베딩 모델
자료실 관리 및 RAG 시스템용
"""
from sqlmodel import SQLModel, Field, Column
from sqlalchemy import Text
from typing import Optional, List
from datetime import datetime
from pgvector.sqlalchemy import Vector


class Document(SQLModel, table=True):
    """자료실 문서 모델"""
    __tablename__ = "documents"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    category: str  
    file_path: str  # 실제 파일 저장 경로
    file_type: str  # pdf, txt, docx 등
    file_size: int  # 바이트 단위
    description: Optional[str] = None
    
    # 업로드 정보
    uploaded_by: int  # User ID (관리자만 가능)
    upload_date: datetime = Field(default_factory=datetime.utcnow)
    
    # 다운로드 통계
    download_count: int = Field(default=0)
    
    # 인덱싱 상태
    is_indexed: bool = Field(default=False)  # RAG에 인덱싱 완료 여부


class DocumentCreate(SQLModel):
    """문서 업로드 요청 모델"""
    title: str
    category: str
    description: Optional[str] = None


class DocumentRead(SQLModel):
    """문서 정보 응답 모델"""
    id: int
    title: str
    category: str
    file_type: str
    file_size: int
    description: Optional[str] = None
    uploaded_by: int
    upload_date: datetime
    download_count: int
    is_indexed: bool


class DocumentChunk(SQLModel, table=True):
    """문서 청크 및 벡터 임베딩 저장"""
    __tablename__ = "document_chunks"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    document_id: int = Field(foreign_key="documents.id")
    
    # 청크 내용
    content: str = Field(sa_column=Column(Text))
    chunk_index: int  # 문서 내 청크 순서
    
    # 벡터 임베딩 (OpenAI text-embedding-ada-002: 1536 차원)
    embedding: Optional[List[float]] = Field(
        default=None,
        sa_column=Column(Vector(1536))
    )
    
    # 메타데이터
    chunk_metadata: Optional[str] = None  # JSON 문자열
    created_at: datetime = Field(default_factory=datetime.utcnow)


class DocumentCategory(SQLModel):
    """문서 카테고리 목록"""
    categories: List[str] = [
        "금융영업",
        "상품개발 및 운용",
        "신용분석 및 리스크관리",
        "외환",
        "은행지식 및 관련법률",
        "하경은행"
    ]


class ProductChunk(SQLModel, table=True):
    """상품 데이터 청크 및 벡터 임베딩 저장"""
    __tablename__ = "product_chunks"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    product_code: str = Field(index=True)  # CRD-CRE, DEP-TIM 등
    
    # 청크 내용
    content: str = Field(sa_column=Column(Text))
    chunk_index: int  # 상품 내 청크 순서
    
    # 벡터 임베딩 (OpenAI text-embedding-ada-002: 1536 차원)
    embedding: Optional[List[float]] = Field(
        default=None,
        sa_column=Column(Vector(1536))
    )
    
    # 메타데이터 (JSON 문자열로 저장)
    subsection_title: Optional[str] = None
    part_title: Optional[str] = None
    breadcrumb: Optional[str] = None
    chunk_metadata: Optional[str] = None  # 전체 메타데이터 JSON
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
