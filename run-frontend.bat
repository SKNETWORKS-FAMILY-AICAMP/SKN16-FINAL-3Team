@echo off
chcp 65001 >nul
echo ========================================
echo 🎨 프론트엔드 서버 실행
echo ========================================
echo.

cd frontend

REM node_modules 확인
if not exist "node_modules" (
    echo 📦 npm 패키지 설치 중...
    npm install
    if %errorLevel% neq 0 (
        echo ❌ 패키지 설치 실패
        pause
        exit /b 1
    )
)

REM 서버 실행
echo.
echo ========================================
echo ✅ 프론트엔드 서버 시작 중...
echo ========================================
echo.
echo 🌐 프론트엔드: http://localhost:3000
echo.
echo 💡 서버를 중지하려면 Ctrl+C를 누르세요.
echo.

npm run dev

