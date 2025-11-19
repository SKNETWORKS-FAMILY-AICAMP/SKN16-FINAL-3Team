"""
FastAPI 메인 애플리케이션
은행 신입사원 멘토 시스템
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import os

from app.config import settings
from app.database import init_db
from app.migrations import run_migrations
from app.routers import auth, chat, documents, anonymous_board, dashboard, admin, exam, simulation, advanced_simulation, rag_simulation, normalize, schedule


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    애플리케이션 시작/종료 시 실행되는 코드
    """
    # 시작 시
    print("🚀 Starting Bank Mentor System...")
    
    # 데이터베이스 초기화
    init_db()
    
    # 자동 마이그레이션 실행
    run_migrations()
    
    # 업로드 디렉토리 생성
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    
    print("✅ Database initialized")
    print(f"✅ Upload directory created: {settings.UPLOAD_DIR}")
    print(f"📚 API Documentation: http://localhost:8000/docs")
    
    yield
    
    # 종료 시
    print("👋 Shutting down...")


# FastAPI 앱 생성
app = FastAPI(
    title="Bank Mentor System API",
    description="은행 신입사원 멘토 시스템 - RAG 기반 챗봇 플랫폼",
    version="1.0.0",
    lifespan=lifespan
)

# CORS 설정 - Docker 환경을 위해 모든 origin 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Docker 환경에서는 모든 origin 허용
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(documents.router)
app.include_router(anonymous_board.router)
app.include_router(dashboard.router)
app.include_router(admin.router)
app.include_router(exam.router)
app.include_router(simulation.router)
app.include_router(rag_simulation.router)
app.include_router(normalize.router)
app.include_router(schedule.router)

# 정적 파일 서빙 (업로드된 파일)
if os.path.exists(settings.UPLOAD_DIR):
    app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")


@app.get("/")
async def root():
    """루트 엔드포인트"""
    return {
        "message": "Welcome to Bank Mentor System API",
        "version": "1.0.0",
        "docs": "/docs",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """헬스 체크 엔드포인트"""
    return {
        "status": "healthy",
        "database": "connected"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )

