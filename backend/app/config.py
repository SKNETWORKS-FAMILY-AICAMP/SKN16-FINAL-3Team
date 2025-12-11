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
    
    # RAG 평가 설정
    USE_LLM_EXTRACTION: bool = False  # LLM 기반 product_code 추출 사용 여부 (기본: 키워드 매칭)
    RAG_VECTOR_SIMILARITY_THRESHOLD: float = 0.45  # 벡터 검색 정확도 기본값
    
    # LangSmith API 설정 (추적 및 모니터링)
    LANGSMITH_API_KEY: Optional[str] = None
    LANGSMITH_PROJECT: str = "CANT"  # 기본 프로젝트 이름

    # 공휴일 API
    HOLIDAY_API_KEY: Optional[str] = None
    HOLIDAY_API_BASE_URL: Optional[str] = None
    
    # JWT 설정
    SECRET_KEY: str = "your-default-secret-key-change-this"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # 파일 업로드 설정
    UPLOAD_DIR: str = "/app/data/rag_sources/uploads"
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10MB
    
    # CORS 설정
    # 환경 변수에서 읽거나 기본값 사용 (쉼표로 구분된 문자열 또는 리스트)
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:8000"
    
    def get_cors_origins(self) -> list:
        """CORS origins를 리스트로 반환"""
        if isinstance(self.CORS_ORIGINS, str):
            return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]
        return self.CORS_ORIGINS if isinstance(self.CORS_ORIGINS, list) else ["*"]
    
    class Config:
        # Docker 컨테이너 내부 경로와 로컬 개발 경로 모두 지원
        env_file = [".env", "/app/.env", "../.env", "backend/.env"]  # 여러 위치에서 .env 파일 찾기
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"


settings = Settings()


