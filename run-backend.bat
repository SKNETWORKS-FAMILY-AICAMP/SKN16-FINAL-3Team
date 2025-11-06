@echo off
chcp 65001 >nul
echo ========================================
echo 🚀 백엔드 서버 실행
echo ========================================
echo.

cd backend

REM 가상환경 확인 및 생성
if not exist "venv" (
    echo 📦 가상환경 생성 중...
    python -m venv venv
    if %errorLevel% neq 0 (
        echo ❌ 가상환경 생성 실패
        pause
        exit /b 1
    )
)

REM 가상환경 활성화
echo 🔧 가상환경 활성화 중...
call venv\Scripts\activate.bat
if %errorLevel% neq 0 (
    echo ❌ 가상환경 활성화 실패
    pause
    exit /b 1
)

REM 의존성 설치
echo 📦 필요한 패키지 확인 중...
pip install -q -r requirements.txt
if %errorLevel% neq 0 (
    echo ❌ 패키지 설치 실패
    pause
    exit /b 1
)

REM 데이터베이스 연결 확인
echo.
echo 🔍 데이터베이스 연결 확인 중...
timeout /t 2 /nobreak >nul

REM 서버 실행
echo.
echo ========================================
echo ✅ 백엔드 서버 시작 중...
echo ========================================
echo.
echo 📚 API 문서: http://localhost:8000/docs
echo 🔗 Health Check: http://localhost:8000/health
echo.
echo 💡 서버를 중지하려면 Ctrl+C를 누르세요.
echo.

python -m app.main

