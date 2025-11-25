"""
애플리케이션 설정 파일
환경 변수를 통해 설정을 관리합니다.
"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """애플리케이션 설정 클래스"""
    
    # 데이터베이스 설정
    DATABASE_URL: str = "postgresql://mentoruser:mentorpass@localhost:5432/mentordb"
    
    # OpenAI API 설정 (개발 환경에서는 선택적)
    OPENAI_API_KEY: Optional[str] = None
    
    # LangSmith API 설정 (추적 및 모니터링)
    LANGSMITH_API_KEY: Optional[str] = None
    LANGSMITH_PROJECT: str = "CANT"  # 기본 프로젝트 이름
    
    # JWT 설정
    SECRET_KEY: str = "your-default-secret-key-change-this"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # 파일 업로드 설정
    UPLOAD_DIR: str = "/app/uploads"
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10MB
    
    # CORS 설정
    CORS_ORIGINS: list = ["http://localhost:3000", "http://localhost:8000"]
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


settings = Settings()


