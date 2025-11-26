@echo off
chcp 65001 >nul
echo 🔍 Training Center Records 테이블 스키마 확인 중...
echo ========================================

REM Docker 환경 확인
docker-compose ps | findstr "backend" >nul
if %errorLevel% == 0 (
    echo ✅ Docker 환경 감지됨
    echo.
    echo 📊 스키마 확인 중...
    docker-compose exec backend python backend/scripts/check_training_center_schema.py
) else (
    echo ⚠️ Docker 컨테이너가 실행되지 않음
    echo.
    echo 💡 Docker 환경에서 실행하려면:
    echo    docker-compose up -d
    echo.
    echo 💡 로컬 환경에서 실행하려면:
    echo    cd backend
    echo    python scripts/check_training_center_schema.py
)

echo.
pause

