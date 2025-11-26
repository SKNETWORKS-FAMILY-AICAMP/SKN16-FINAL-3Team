# 연수원 DB 500 오류 해결 가이드

## 문제 증상

연수원 데이터를 조회하거나 동기화할 때 다음과 같은 500 오류가 발생합니다:

```
Failed to load resource: the server responded with a status of 500 (Internal Server Error)
api/training-center/mentees?page=1&page_size=10000:1
POST http://localhost:3000/api/training-center/sync 500 (Internal Server Error)
```

## 원인 분석

이 오류는 주로 다음과 같은 경우에 발생합니다:

1. **데이터베이스 테이블이 존재하지 않음** (가장 흔한 원인)
   - Git pull 후 새로운 모델이 추가되었지만 데이터베이스 마이그레이션이 실행되지 않음
   - 로컬 환경에서 데이터베이스가 초기화되지 않음

2. **데이터베이스 연결 문제**
   - PostgreSQL 서비스가 실행되지 않음
   - DATABASE_URL 환경 변수가 잘못 설정됨

3. **데이터베이스 스키마 불일치**
   - 기존 테이블과 새로운 모델 정의가 일치하지 않음

## 해결 방법

### 방법 1: Docker 환경에서 해결 (권장)

```bash
# 1. Docker 컨테이너 재시작 (데이터베이스 초기화 포함)
docker-compose down
docker-compose up -d

# 2. 백엔드 컨테이너 로그 확인
docker-compose logs backend

# 3. 데이터베이스 테이블 확인
docker-compose exec backend python -c "from app.database import init_db; init_db()"
```

### 방법 2: 로컬 환경에서 해결

#### 2-1. PostgreSQL이 실행 중인지 확인

**Windows:**
```powershell
# PostgreSQL 서비스 상태 확인
Get-Service -Name postgresql*

# 서비스가 중지되어 있으면 시작
Start-Service -Name postgresql-x64-15
```

**Linux/Mac:**
```bash
# PostgreSQL 상태 확인
sudo systemctl status postgresql
# 또는
brew services list | grep postgresql
```

#### 2-2. 데이터베이스 초기화

```bash
# 백엔드 디렉토리로 이동
cd backend

# 데이터베이스 초기화 (테이블 생성)
python -c "from app.database import init_db; init_db()"

# 또는 직접 스크립트 실행
python -m app.database init_db
```

#### 2-3. 환경 변수 확인

`.env` 파일 또는 환경 변수에서 `DATABASE_URL`이 올바르게 설정되어 있는지 확인:

```bash
# Windows PowerShell
$env:DATABASE_URL

# Linux/Mac
echo $DATABASE_URL
```

기본값:
- Docker: `postgresql://mentoruser:mentorpass@postgres:5432/mentordb`
- 로컬: `postgresql://mentoruser:mentorpass@localhost:5432/mentordb`

### 방법 3: 수동으로 테이블 생성

```bash
# 백엔드 디렉토리에서
cd backend

# 데이터베이스 테이블 초기화 스크립트 실행
python scripts/init_database_tables.py
```

### 방법 4: 데이터베이스 완전 재초기화 (주의: 모든 데이터 삭제)

```bash
# Docker 환경
docker-compose down -v  # 볼륨까지 삭제
docker-compose up -d

# 로컬 환경
# PostgreSQL에 직접 접속하여 데이터베이스 삭제 후 재생성
psql -U mentoruser -d postgres
DROP DATABASE mentordb;
CREATE DATABASE mentordb;
\q

# 그 다음 초기화
cd backend
python -c "from app.database import init_db; init_db()"
```

## 예방 방법

### Git Pull 후 자동 초기화

Git pull 후 항상 다음을 실행하세요:

```bash
# Docker 환경
docker-compose restart backend

# 로컬 환경
# 백엔드 서버를 재시작하면 자동으로 init_db()가 실행됩니다
```

### 데이터베이스 마이그레이션 확인

새로운 모델이 추가되었는지 확인:

```bash
# 백엔드 디렉토리에서
cd backend

# 모든 모델이 제대로 임포트되는지 확인
python -c "from app.models import *; print('✅ 모든 모델 임포트 성공')"
```

## 디버깅 팁

### 1. 백엔드 로그 확인

```bash
# Docker 환경
docker-compose logs -f backend

# 로컬 환경
# 백엔드 서버 콘솔에서 에러 메시지 확인
```

### 2. 데이터베이스 연결 테스트

```bash
# PostgreSQL에 직접 접속 테스트
psql -U mentoruser -d mentordb -h localhost

# 테이블 목록 확인
\dt

# training_center_records 테이블 확인
\d training_center_records
```

### 3. API 직접 테스트

```bash
# Swagger UI에서 테스트
http://localhost:8000/docs

# 또는 curl 사용
curl -X GET "http://localhost:8000/training-center/mentees?page=1&page_size=10" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## 개선된 에러 메시지

이제 500 오류가 발생하면 더 명확한 에러 메시지가 표시됩니다:

- **테이블이 없는 경우**: "데이터베이스 테이블이 존재하지 않습니다. 데이터베이스를 초기화해주세요."
- **연결 오류**: "데이터베이스 연결에 실패했습니다."
- **기타 오류**: 구체적인 오류 메시지와 함께 표시

## 추가 지원

문제가 계속되면 다음 정보를 확인하세요:

1. 백엔드 로그 전체 내용
2. 데이터베이스 버전 및 상태
3. 환경 변수 설정
4. Git pull 전후 변경사항

