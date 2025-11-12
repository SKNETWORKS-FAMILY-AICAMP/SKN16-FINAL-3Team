# 은행 신입사원 멘토 시스템 - 설치 가이드

## 📋 목차
- [시스템 요구사항](#시스템-요구사항)
- [빠른 시작 (Docker)](#빠른-시작-docker)
- [로컬 개발 환경](#로컬-개발-환경)
- [초기 설정](#초기-설정)
- [테스트 계정](#테스트-계정)
- [문제 해결](#문제-해결)

## 시스템 요구사항

### 필수 소프트웨어
- Docker 20.10+ 및 Docker Compose 2.0+
- (로컬 개발 시) Python 3.11+
- (로컬 개발 시) Node.js 18+
- (로컬 개발 시) PostgreSQL 15+

### 환경 변수
프로젝트에 OpenAI API 키가 필요합니다.

## 빠른 시작 (Docker)

### 1. 프로젝트 클론
```bash
cd c:/cant
# 또는 원하는 디렉토리로 이동
```

### 2. 환경 변수 설정
`docker-compose.yml` 파일의 OpenAI API 키가 설정되어 있는지 확인하세요.

### 3. Docker Compose 실행
```bash
docker-compose up --build
```

첫 실행 시 이미지 빌드 및 종속성 설치로 5-10분 정도 소요될 수 있습니다.

### 4. 초기 데이터 생성
새 터미널을 열고:
```bash
docker-compose exec backend python -m app.init_data
```

### 5. 접속
- **프론트엔드**: http://localhost:3000
- **백엔드 API**: http://localhost:8000
- **API 문서**: http://localhost:8000/docs

## 로컬 개발 환경

### 백엔드 설정

#### 1. PostgreSQL 설치 및 pgvector 확장
```bash
# PostgreSQL 15 설치 (Windows)
# https://www.postgresql.org/download/windows/

# pgvector 확장 설치
# https://github.com/pgvector/pgvector#installation
```

#### 2. 데이터베이스 생성
```sql
CREATE DATABASE mentordb;
CREATE USER mentoruser WITH PASSWORD 'mentorpass';
GRANT ALL PRIVILEGES ON DATABASE mentordb TO mentoruser;
```

#### 3. Python 환경 설정
```bash
cd backend

# 가상환경 생성
python -m venv venv

# 가상환경 활성화 (Windows)
venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt
```

#### 4. 환경 변수 설정
`backend/.env` 파일 생성:
```env
DATABASE_URL=postgresql://mentoruser:mentorpass@localhost:5432/mentordb
OPENAI_API_KEY=your-openai-api-key-here
SECRET_KEY=your-secret-key-change-this-in-production-min-32-chars
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
UPLOAD_DIR=./uploads
```

#### 5. 백엔드 실행
```bash
# 서버 시작 (초기 데이터는 자동 생성됨)
uvicorn app.main:app --reload
```

### 프론트엔드 설정

#### 1. Node.js 설치
```bash
# Node.js 18+ 설치
# https://nodejs.org/
```

#### 2. 의존성 설치
```bash
cd frontend
npm install
```

#### 3. 환경 변수 설정
`frontend/.env` 파일 생성:
```env
VITE_API_URL=http://localhost:8000
```

#### 4. 프론트엔드 실행
```bash
npm run dev
```

브라우저에서 http://localhost:3000 접속

## 초기 설정

### 1. 데이터베이스 초기화
백엔드 서버가 처음 실행되면 자동으로 테이블이 생성됩니다.

### 2. 초기 사용자 및 데이터 생성
```bash
# Docker 환경 - 자동으로 초기화됩니다!
# 별도 실행 불필요

# 로컬 환경에서 수동 실행이 필요한 경우
cd backend
python -m app.init_data
```

## 테스트 계정

시스템에는 다음과 같은 테스트 계정이 생성됩니다:

### 관리자
- **이메일**: admin@bank.com
- **비밀번호**: admin123
- **권한**: 문서 업로드, 사용자 관리, 전체 기능 접근

### 멘토
- **이메일**: mentor@bank.com
- **비밀번호**: mentor123
- **권한**: 멘티 관리, 대시보드 조회

### 멘티
- **이메일**: mentee@bank.com
- **비밀번호**: mentee123
- **권한**: 기본 사용자 기능

## 주요 기능 사용법

### 1. AI 챗봇 사용
- 로그인 후 우측 하단의 채팅 아이콘 클릭
- 궁금한 점을 자유롭게 질문
- RAG 기반으로 업로드된 문서에서 답변 검색

### 2. 자료실 사용
- 관리자: 상단의 "문서 업로드" 버튼으로 파일 추가
- 일반 사용자: 문서 검색, 카테고리별 필터링, 다운로드

### 3. 동아리 라운지 (취미 게시판)
- 완전 익명으로 게시글 및 댓글 작성
- 게시글 작성자는 "익명1", 댓글은 순서대로 "익명2", "익명3"...

### 4. 대시보드
- 멘티: 담당 멘토 정보, 시험 점수 차트, 학습 진행도
- 멘토: 담당 멘티 목록, 성적 관리, 자주 묻는 질문

## 문제 해결

### PostgreSQL 연결 오류
```bash
# Windows에서 PostgreSQL 서비스 시작
net start postgresql-x64-15

# 연결 테스트
psql -U mentoruser -d mentordb
```

### Docker 빌드 오류
```bash
# 캐시 없이 재빌드
docker-compose build --no-cache

# 모든 컨테이너 및 볼륨 제거 후 재시작
docker-compose down -v
docker-compose up --build
```

### pgvector 확장 오류
```sql
-- PostgreSQL에서 수동으로 확장 활성화
\c mentordb
CREATE EXTENSION IF NOT EXISTS vector;
```

### OpenAI API 오류
- API 키가 올바른지 확인
- 잔액이 충분한지 확인
- 네트워크 연결 확인

### 포트 충돌
```bash
# 사용 중인 포트 확인 (Windows)
netstat -ano | findstr :3000
netstat -ano | findstr :8000

# docker-compose.yml에서 포트 변경 가능
```

## 개발 팁

### Hot Reload
- 백엔드: `uvicorn app.main:app --reload`로 실행 시 코드 변경 시 자동 재시작
- 프론트엔드: Vite가 자동으로 Hot Module Replacement 지원

### API 문서
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### 데이터베이스 관리
```bash
# Docker 환경에서 PostgreSQL 접속
docker-compose exec db psql -U mentoruser -d mentordb

# 테이블 확인
\dt

# 사용자 조회
SELECT * FROM users;
```

## 배포 (프로덕션)

### 환경 변수 변경
1. `SECRET_KEY`: 강력한 무작위 문자열로 변경
2. `OPENAI_API_KEY`: 유효한 프로덕션 API 키 사용
3. 데이터베이스 비밀번호 변경

### HTTPS 설정
- Nginx 또는 Caddy를 리버스 프록시로 사용
- Let's Encrypt로 SSL 인증서 발급

### 성능 최적화
- PostgreSQL 연결 풀 크기 조정
- 정적 파일 CDN 사용
- Redis 캐싱 추가 고려

## 라이선스
이 프로젝트는 교육용 목적으로 개발되었습니다.

## 지원
문제가 발생하면 GitHub Issues에 등록해주세요.


