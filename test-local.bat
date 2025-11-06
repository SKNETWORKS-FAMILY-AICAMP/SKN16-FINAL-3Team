@echo off
chcp 65001 >nul
echo ========================================
echo 🧪 로컬 테스트 환경 실행
echo ========================================
echo.

REM PostgreSQL 확인
echo 📊 PostgreSQL 상태 확인 중...
docker ps --filter "name=mentor-postgres" --format "table {{.Names}}\t{{.Status}}" 2>nul
if %errorLevel% neq 0 (
    echo ⚠️ PostgreSQL 컨테이너를 찾을 수 없습니다.
    echo 💡 docker-compose up postgres -d 를 실행해주세요.
    echo.
)

REM 백엔드 확인
echo.
echo 🔍 백엔드 서버 확인 중...
timeout /t 2 /nobreak >nul
curl -s http://localhost:8000/health >nul 2>&1
if %errorLevel% equ 0 (
    echo ✅ 백엔드 서버 실행 중: http://localhost:8000
    echo    - API 문서: http://localhost:8000/docs
) else (
    echo ❌ 백엔드 서버가 실행되지 않았습니다.
    echo.
    echo 💡 백엔드 실행 방법:
    echo    cd backend
    echo    .\venv\Scripts\activate.bat
    echo    python -m app.main
    echo.
)

REM 프론트엔드 확인
echo.
echo 🔍 프론트엔드 서버 확인 중...
timeout /t 1 /nobreak >nul
curl -s http://localhost:3000 >nul 2>&1
if %errorLevel% equ 0 (
    echo ✅ 프론트엔드 서버 실행 중: http://localhost:3000
) else (
    echo ❌ 프론트엔드 서버가 실행되지 않았습니다.
    echo.
    echo 💡 프론트엔드 실행 방법:
    echo    cd frontend
    echo    npm install
    echo    npm run dev
    echo.
)

echo.
echo ========================================
echo 📋 테스트 체크리스트
echo ========================================
echo.
echo 1. 로그인 테스트:
echo    - 사번/생년월일 로그인: 2023001 / 19970127
echo    - 기존 이메일 로그인: mentee@bank.com / mentee123
echo.
echo 2. 마이페이지 테스트:
echo    - 주소, 직책 수정 기능 확인
echo.
echo 3. 관리자 기능 테스트:
echo    - Excel 파일 업로드 (사번, 생년월일 포함)
echo    - 시험 점수 확인
echo.
echo 4. 비밀번호 재설정 테스트:
echo    - 사번 + 생년월일로 재설정
echo.
echo ========================================
echo.
pause

