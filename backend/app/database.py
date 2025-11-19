"""
데이터베이스 연결 및 세션 관리
PostgreSQL + pgvector를 사용합니다.
"""
from sqlmodel import SQLModel, create_engine, Session
from pgvector.sqlalchemy import Vector
from sqlalchemy import text
from app.config import settings

# 모든 모델이 메타데이터에 등록되도록 명시적으로 임포트
import app.models  # noqa: F401

# 데이터베이스 엔진 생성
engine = create_engine(
    settings.DATABASE_URL,
    echo=True,  # SQL 쿼리 로깅 (개발 환경에서만 사용)
    pool_pre_ping=True,  # 연결 상태 확인
    pool_size=5,
    max_overflow=10
)


def init_db():
    """
    데이터베이스 초기화
    - 테이블 생성 (데이터 보존)
    - pgvector 확장 활성화
    """
    # pgvector 확장 활성화
    with Session(engine) as session:
        try:
            session.exec(text("CREATE EXTENSION IF NOT EXISTS vector"))
            session.commit()
            print("✅ pgvector extension enabled")
        except Exception as e:
            print(f"❌ Error enabling pgvector: {e}")
            session.rollback()
    
    # 모든 테이블 생성 (기존 테이블이 있으면 건너뜀)
    SQLModel.metadata.create_all(engine)
    print("✅ Database tables created/verified")

    # 게시글 카테고리 컬럼 보장
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "ALTER TABLE IF EXISTS posts ADD COLUMN IF NOT EXISTS category VARCHAR(50) DEFAULT '기타'"
        )
        connection.exec_driver_sql(
            "UPDATE posts SET category = '기타' WHERE category IS NULL"
        )
        connection.exec_driver_sql(
            "ALTER TABLE IF EXISTS posts ADD COLUMN IF NOT EXISTS subcategory VARCHAR(50)"
        )
        connection.exec_driver_sql(
            "UPDATE posts SET subcategory = NULL WHERE subcategory = ''"
        )
        connection.exec_driver_sql(
            "ALTER TABLE IF EXISTS comments ADD COLUMN IF NOT EXISTS join_status VARCHAR(20) DEFAULT 'none'"
        )
        connection.exec_driver_sql(
            "ALTER TABLE IF EXISTS comments ADD COLUMN IF NOT EXISTS join_approved_at TIMESTAMP"
        )
        connection.exec_driver_sql(
            "UPDATE comments SET join_status = 'none' WHERE join_status IS NULL OR join_status = ''"
        )
    print("✅ Post category column verified")


def get_session():
    """
    데이터베이스 세션 의존성
    FastAPI 엔드포인트에서 사용됩니다.
    """
    with Session(engine) as session:
        yield session


