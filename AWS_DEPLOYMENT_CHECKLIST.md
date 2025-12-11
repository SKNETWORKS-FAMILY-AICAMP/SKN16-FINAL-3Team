# AWS 배포 호환성 점검 리포트

## 📋 개요
AWS 배포를 위한 호환성 점검 및 수정 사항 정리

---

## ✅ 확인 완료 사항

### 1. Docker 설정
- ✅ Dockerfile 존재 (backend, frontend)
- ✅ docker-compose.yml 구성 완료
- ✅ 멀티 스테이지 빌드 가능
- ✅ 포트 노출 설정 (8000, 3000, 5432)

### 2. 데이터베이스
- ✅ PostgreSQL + pgvector 사용
- ✅ 마이그레이션 자동 실행
- ✅ Health check 설정

### 3. 환경 변수 관리
- ✅ Pydantic Settings 사용
- ✅ .env 파일 지원

---

## ⚠️ 수정 필요 사항

### 1. **프로덕션 Dockerfile 수정 필요**

#### Backend Dockerfile
**현재 문제:**
```dockerfile
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
```
- `--reload` 옵션이 프로덕션에 부적합 (메모리 사용량 증가)

**수정 필요:**
```dockerfile
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

#### Frontend Dockerfile
**현재 문제:**
- 개발 모드(`npm run dev`)로 실행 중
- 프로덕션 빌드가 없음

**수정 필요:**
```dockerfile
# 빌드 단계 추가
RUN npm run build

# Nginx 또는 정적 파일 서버 사용
FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
```

### 2. **환경 변수 설정**

#### 필수 환경 변수 (AWS에서 설정 필요)
```bash
# 데이터베이스 (RDS 사용 시)
DATABASE_URL=postgresql://user:password@rds-endpoint:5432/mentordb

# 보안
SECRET_KEY=<최소 32자 랜덤 문자열>  # ⚠️ 반드시 변경 필요
OPENAI_API_KEY=<실제 API 키>
LANGSMITH_API_KEY=<실제 API 키>

# 프론트엔드
VITE_API_URL=https://your-api-domain.com/api  # ⚠️ 프로덕션 도메인으로 변경
```

#### 현재 문제점
- `SECRET_KEY` 기본값이 너무 약함 (`your-default-secret-key-change-this`)
- `CORS_ORIGINS`가 localhost만 허용
- `VITE_API_URL`이 localhost로 하드코딩됨

### 3. **docker-compose.yml 프로덕션 버전 필요**

**현재 문제:**
- 개발 환경용 설정 (볼륨 마운트, --reload 등)
- 하드코딩된 비밀번호
- 모든 포트 노출

**필요한 작업:**
`docker-compose.prod.yml` 파일 생성 필요

### 4. **CORS 설정 수정**

**현재 (`backend/app/config.py`):**
```python
CORS_ORIGINS: list = ["http://localhost:3000", "http://localhost:8000"]
```

**수정 필요:**
```python
CORS_ORIGINS: list = [
    "https://your-frontend-domain.com",
    "https://www.your-frontend-domain.com"
]
```

### 5. **데이터베이스 연결**

**현재 (`docker-compose.yml`):**
```yaml
DATABASE_URL=postgresql://mentoruser:mentorpass@postgres:5432/mentordb
```

**AWS RDS 사용 시:**
- 컨테이너 내부 서비스명(`postgres`) 대신 RDS 엔드포인트 사용
- SSL 연결 활성화 권장

### 6. **프론트엔드 API URL 설정**

**현재 (`frontend/src/utils/api.ts`):**
```typescript
const API_URL = import.meta.env.VITE_API_URL || '/api'
```

**문제:**
- 빌드 타임에 환경 변수가 주입됨
- 런타임 변경 불가능

**해결 방안:**
- 환경 변수를 빌드 시점에 주입하거나
- Nginx reverse proxy 사용

### 7. **보안 설정**

#### 필수 수정 사항
1. **SECRET_KEY 변경**
   ```python
   # backend/app/config.py
   SECRET_KEY: str = "your-default-secret-key-change-this"  # ⚠️ 변경 필요
   ```

2. **데이터베이스 비밀번호**
   ```yaml
   # docker-compose.yml
   POSTGRES_PASSWORD: mentorpass  # ⚠️ 강력한 비밀번호로 변경
   ```

3. **환경 변수 파일 보안**
   - `.env` 파일을 Git에 커밋하지 않도록 확인
   - AWS Secrets Manager 또는 Parameter Store 사용 권장

### 8. **파일 업로드 경로**

**현재 (`backend/app/config.py`):**
```python
UPLOAD_DIR: str = "/app/data/rag_sources/uploads"
```

**AWS 배포 시:**
- EFS 또는 S3 사용 권장
- 컨테이너 재시작 시 데이터 손실 방지

### 9. **로그 설정**

**현재:**
- 콘솔 출력만 사용
- CloudWatch 연동 없음

**권장:**
- CloudWatch Logs 드라이버 설정
- 구조화된 로깅 (JSON 형식)

### 10. **Health Check**

**현재:**
- PostgreSQL health check만 존재
- Backend/Frontend health check 없음

**추가 필요:**
```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
  interval: 30s
  timeout: 10s
  retries: 3
```

---

## 🔧 권장 수정 작업

### 1. 프로덕션 Dockerfile 생성

#### `backend/Dockerfile.prod`
```dockerfile
FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

#### `frontend/Dockerfile.prod`
```dockerfile
# 빌드 단계
FROM node:18-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci --legacy-peer-deps
COPY . .
RUN npm run build

# 프로덕션 단계
FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

### 2. docker-compose.prod.yml 생성

```yaml
version: '3.8'

services:
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile.prod
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - SECRET_KEY=${SECRET_KEY}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - LANGSMITH_API_KEY=${LANGSMITH_API_KEY}
    ports:
      - "8000:8000"
    restart: always
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile.prod
    ports:
      - "80:80"
    restart: always
    depends_on:
      - backend
```

### 3. 환경 변수 템플릿 생성

#### `.env.example`
```bash
# 데이터베이스
DATABASE_URL=postgresql://user:password@host:5432/dbname

# 보안
SECRET_KEY=change-this-to-a-strong-random-string-min-32-chars

# API Keys
OPENAI_API_KEY=your-openai-api-key
LANGSMITH_API_KEY=your-langsmith-api-key
LANGSMITH_PROJECT=bank-mentor-system

# 프론트엔드
VITE_API_URL=https://api.yourdomain.com/api
```

### 4. Health Check 엔드포인트 추가

#### `backend/app/main.py`에 추가
```python
@app.get("/health")
async def health_check():
    return {"status": "healthy"}
```

---

## 📝 AWS 배포 체크리스트

### 배포 전 필수 작업
- [ ] SECRET_KEY를 강력한 랜덤 문자열로 변경
- [ ] 데이터베이스 비밀번호 변경
- [ ] CORS_ORIGINS를 프로덕션 도메인으로 수정
- [ ] VITE_API_URL을 프로덕션 API 도메인으로 설정
- [ ] 프로덕션 Dockerfile 생성
- [ ] docker-compose.prod.yml 생성
- [ ] Health check 엔드포인트 추가
- [ ] .env 파일을 Git에서 제외 확인
- [ ] AWS Secrets Manager에 민감 정보 저장

### AWS 인프라 설정
- [ ] ECS/EKS 클러스터 생성
- [ ] RDS PostgreSQL 인스턴스 생성 (또는 컨테이너 DB)
- [ ] Application Load Balancer 설정
- [ ] Security Group 설정 (포트 제한)
- [ ] CloudWatch Logs 설정
- [ ] EFS 또는 S3 파일 스토리지 설정
- [ ] SSL/TLS 인증서 설정 (ACM)

### 모니터링 및 로깅
- [ ] CloudWatch 대시보드 설정
- [ ] 알람 설정 (에러율, CPU, 메모리)
- [ ] 로그 그룹 생성 및 보존 정책 설정

---

## 🚀 배포 순서

1. **환경 변수 설정**
   ```bash
   # AWS Systems Manager Parameter Store 또는 Secrets Manager에 저장
   ```

2. **이미지 빌드 및 푸시**
   ```bash
   docker build -f backend/Dockerfile.prod -t your-ecr-repo/backend:latest ./backend
   docker push your-ecr-repo/backend:latest
   
   docker build -f frontend/Dockerfile.prod -t your-ecr-repo/frontend:latest ./frontend
   docker push your-ecr-repo/frontend:latest
   ```

3. **ECS Task Definition 생성**
   - 환경 변수 주입
   - 로그 설정
   - 리소스 제한 설정

4. **서비스 배포**
   - ECS Service 생성
   - Load Balancer 연결
   - Health check 확인

---

## ⚠️ 주의 사항

1. **메모리 제한**
   - 현재 설정: Backend 4GB, Postgres 2GB
   - AWS 인스턴스 타입 선택 시 고려

2. **공유 메모리 (shm_size)**
   - ECS에서 지원 여부 확인 필요
   - 필요 시 EFS 사용 고려

3. **볼륨 마운트**
   - 로컬 볼륨(`./postgres_data`)은 ECS에서 사용 불가
   - EFS 또는 RDS 사용 권장

4. **네트워크**
   - 컨테이너 간 통신은 VPC 내부에서만
   - ALB를 통한 외부 접근만 허용

---

## 📚 참고 자료

- [AWS ECS 배포 가이드](https://docs.aws.amazon.com/ecs/)
- [Docker 보안 모범 사례](https://docs.docker.com/engine/security/)
- [FastAPI 프로덕션 배포](https://fastapi.tiangolo.com/deployment/)

