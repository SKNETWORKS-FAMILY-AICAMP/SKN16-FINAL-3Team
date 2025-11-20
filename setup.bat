@echo off
chcp 65001 >nul
echo 🚀 FastAPI 멘토 시스템 로컬 환경 설정을 시작합니다...

REM 관리자 권한 확인
net session >nul 2>&1
if not %errorLevel% == 0 (
    echo ⚠️ 관리자 권한으로 실행해주세요.
    pause
    exit /b 1
)

REM 현재 디렉토리 확인
if not exist "backend\requirements.txt" (
    echo ❌ backend\requirements.txt 파일을 찾을 수 없습니다.
    echo 💡 프로젝트 루트 디렉토리에서 실행해주세요.
    pause
    exit /b 1
)

REM Python 버전 확인
echo.
echo 📋 Python 버전 확인 중...
python --version >nul 2>&1
if %errorLevel% neq 0 (
    echo ❌ Python이 설치되지 않았거나 PATH에 추가되지 않았습니다.
    echo 💡 Python 3.8 이상을 설치해주세요.
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo 현재 Python 버전: %PYTHON_VERSION%

REM conda 환경 비활성화 (활성화되어 있는 경우)
if defined CONDA_DEFAULT_ENV (
    echo.
    echo 🐍 conda 환경이 감지되었습니다. 비활성화합니다...
    call conda deactivate 2>nul
)

REM 가상환경 설정
echo.
echo 🌍 가상환경 설정 중...
if not exist "backend\venv" (
    echo 가상환경 생성 중...
    cd backend
    python -m venv venv
    if %errorLevel% neq 0 (
        echo ❌ 가상환경 생성 실패
        pause
        exit /b 1
    )
    echo ✅ 가상환경 생성 완료
    cd ..
) else (
    echo ✅ 기존 가상환경 발견
)

REM 가상환경 활성화
echo 가상환경 활성화 중...
cd backend
call venv\Scripts\activate.bat
if %errorLevel% neq 0 (
    echo ❌ 가상환경 활성화 실패
    pause
    exit /b 1
)
echo ✅ 가상환경 활성화 완료

REM 필수 패키지 설치
echo.
echo 📦 필수 패키지 설치 중...
python -m pip install --upgrade pip
pip install -r requirements.txt
if %errorLevel% neq 0 (
    echo ❌ 패키지 설치 실패
    pause
    exit /b 1
)
echo ✅ 패키지 설치 완료

REM 환경 변수 파일 설정
echo.
echo ⚙️ 환경 변수 설정 중...
if not exist ".env" (
    if exist ".env.example" (
        copy ".env.example" ".env" >nul
        echo ✅ .env 파일 생성 완료
        echo ⚠️ .env 파일에서 OPENAI_API_KEY를 설정해주세요!
    ) else (
        echo ⚠️ .env.example 파일이 없습니다. 수동으로 .env 파일을 생성해주세요.
    )
) else (
    echo ✅ .env 파일이 이미 존재합니다
)

cd ..

REM Docker 및 PostgreSQL 확인
echo.
echo 🐘 PostgreSQL 설정 확인 중...
docker --version >nul 2>&1
if %errorLevel% == 0 (
    docker-compose --version >nul 2>&1
    if %errorLevel% == 0 (
        echo ✅ Docker 및 Docker Compose 발견
        echo.
        echo 🐳 PostgreSQL 컨테이너 시작 중...
        docker-compose up postgres -d
        if %errorLevel% == 0 (
            echo ✅ PostgreSQL 컨테이너 시작 완료
            timeout /t 10 /nobreak >nul
            echo 🔄 데이터베이스 연결 대기 중...
        ) else (
            echo ⚠️ PostgreSQL 컨테이너 시작 실패
        )
    ) else (
        echo ⚠️ Docker Compose를 찾을 수 없습니다
    )
) else (
    echo ⚠️ Docker가 설치되지 않았습니다
    echo 📝 PostgreSQL을 수동으로 설치하거나 Docker를 설치해주세요
)

REM 업로드 디렉토리 생성
if not exist "uploads" (
    mkdir uploads
    echo ✅ uploads 디렉토리 생성 완료
)

echo.
echo 🎉 로컬 환경 설정이 완료되었습니다!
echo.
echo 📋 다음 단계:
echo 1. .env 파일에서 OPENAI_API_KEY 설정
echo 2. 전체 시스템 실행: docker-compose up -d
echo 3. API 문서 확인: http://localhost:8000/docs
echo 4. pgAdmin 접속: http://localhost:5050 (개발 환경)
echo.
echo 🔑 테스트 계정:
echo - 관리자: admin@bank.com / admin123
echo - 멘토: mentor@bank.com / mentor123
echo - 멘티: mentee@bank.com / mentee123
echo.
echo 💡 문제가 발생하면 README.md를 확인하세요!
echo.

REM 사용자 선택 메뉴
echo 다음 중 선택하세요:
echo [1] 전체 시스템 실행 (권장)
echo [2] 개발 모드로 실행 
echo [3] 데이터베이스만 실행
echo [4] RAG 데이터 임포트 (최초 1회 필수)
echo [5] 종료
echo.
set /p choice="선택 (1-5): "

if "%choice%"=="1" (
    echo.
    echo 🚀 전체 시스템을 실행합니다...
    docker-compose up -d
    echo ✅ 시스템 실행 완료
    echo 📱 웹 브라우저에서 http://localhost:8000/docs 를 열어보세요
) else if "%choice%"=="2" (
    echo.
    echo 🔧 개발 모드로 실행합니다...
    docker-compose up postgres -d
    timeout /t 5 /nobreak >nul
    cd backend
    call venv\Scripts\activate.bat
    python -m app.main
) else if "%choice%"=="3" (
    echo.
    echo 🐘 데이터베이스만 실행합니다...
    docker-compose up postgres -d
    echo ✅ PostgreSQL 실행 완료
) else if "%choice%"=="4" (
    echo.
    echo 📚 RAG 데이터를 임포트합니다...
    docker-compose up postgres -d
    timeout /t 5 /nobreak >nul
    cd backend
    call venv\Scripts\activate.bat
    python -m scripts.ingest_rag_sources --base-path data/rag_sources
    echo ✅ 데이터 임포트 완료!
) else (
    echo.
    echo 👋 설정이 완료되었습니다. 필요시 다시 실행해주세요.
)

echo.
pause