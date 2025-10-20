# 보안 가이드

## 개발 환경 vs 프로덕션 환경

### 개발 환경 (현재)
- Vite 개발 서버는 HMR(Hot Module Replacement)을 위해 `eval` 사용
- CSP 경고는 **정상적인 동작**이며 보안 문제가 아님
- 로컬 환경에서만 실행되므로 외부 공격 위험 없음

### 프로덕션 환경
프로덕션에 배포할 때는 반드시 아래 보안 설정을 적용하세요.

## 프로덕션 배포 시 필수 보안 설정

### 1. 환경 변수 보안
```bash
# .env 파일을 절대 Git에 커밋하지 마세요!
# 프로덕션에서는 환경 변수로 관리

DATABASE_URL=postgresql://secure_user:strong_password@db:5432/mentordb
SECRET_KEY=<최소 32자 이상의 랜덤 문자열>
OPENAI_API_KEY=<실제 프로덕션 API 키>
```

### 2. Nginx 설정 (프로덕션 웹 서버)

#### `/etc/nginx/conf.d/mentor-system.conf`
```nginx
server {
    listen 80;
    server_name your-domain.com;
    
    # HTTP를 HTTPS로 리다이렉트
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;
    
    # SSL 인증서 (Let's Encrypt 권장)
    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
    
    # 보안 헤더
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    
    # Content Security Policy (안전한 설정)
    add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data: https:; connect-src 'self' https://api.openai.com;" always;
    
    # HSTS (HTTP Strict Transport Security)
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    
    # 프론트엔드 정적 파일
    root /var/www/mentor-system/dist;
    index index.html;
    
    location / {
        try_files $uri $uri/ /index.html;
    }
    
    # 백엔드 API 프록시
    location /api/ {
        proxy_pass http://backend:8000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # 타임아웃 설정 (RAG 처리 시간 고려)
        proxy_read_timeout 300;
        proxy_connect_timeout 300;
        proxy_send_timeout 300;
    }
    
    # 파일 업로드 크기 제한
    client_max_body_size 10M;
}
```

### 3. Docker 프로덕션 설정

#### `docker-compose.prod.yml`
```yaml
version: '3.8'

services:
  db:
    image: ankane/pgvector:latest
    environment:
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: ${DB_NAME}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: always
    networks:
      - internal

  backend:
    build: ./backend
    environment:
      - DATABASE_URL=postgresql://${DB_USER}:${DB_PASSWORD}@db:5432/${DB_NAME}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - SECRET_KEY=${SECRET_KEY}
      - ALGORITHM=HS256
      - ACCESS_TOKEN_EXPIRE_MINUTES=30
    restart: always
    networks:
      - internal
    depends_on:
      - db

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./frontend/dist:/var/www/mentor-system/dist
      - ./nginx.conf:/etc/nginx/conf.d/default.conf
      - ./certbot/conf:/etc/letsencrypt
      - ./certbot/www:/var/www/certbot
    restart: always
    networks:
      - internal
    depends_on:
      - backend

networks:
  internal:
    driver: bridge

volumes:
  postgres_data:
```

### 4. 프로덕션 빌드 명령

```bash
# 프론트엔드 빌드
cd frontend
npm run build

# Docker 이미지 빌드 (프로덕션)
docker-compose -f docker-compose.prod.yml build

# 실행
docker-compose -f docker-compose.prod.yml up -d
```

### 5. 보안 체크리스트

#### 필수 사항
- [ ] `.env` 파일을 Git에서 제외 (.gitignore에 추가됨)
- [ ] SECRET_KEY를 강력한 랜덤 문자열로 변경
- [ ] 데이터베이스 비밀번호 변경
- [ ] HTTPS/SSL 인증서 설정 (Let's Encrypt)
- [ ] CORS 설정을 프로덕션 도메인만 허용하도록 제한
- [ ] 파일 업로드 크기 제한 설정
- [ ] Rate limiting 설정 (API 호출 제한)

#### 권장 사항
- [ ] 정기적인 보안 업데이트
- [ ] 로그 모니터링 시스템
- [ ] 백업 자동화
- [ ] 침입 탐지 시스템 (IDS)
- [ ] 2FA (Two-Factor Authentication) 추가

### 6. Rate Limiting (API 호출 제한)

백엔드에 Rate Limiting을 추가하려면:

```bash
# requirements.txt에 추가
slowapi==0.1.9
```

```python
# backend/app/main.py
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# 라우터에 적용
@app.post("/auth/login")
@limiter.limit("5/minute")  # 1분에 5번까지만 허용
async def login(...):
    ...
```

## 보안 모니터링

### 로그 확인
```bash
# 백엔드 로그
docker-compose logs -f backend

# Nginx 액세스 로그
docker-compose exec nginx tail -f /var/log/nginx/access.log

# 에러 로그
docker-compose exec nginx tail -f /var/log/nginx/error.log
```

### 의심스러운 활동 탐지
- 짧은 시간에 많은 로그인 시도
- 비정상적인 API 호출 패턴
- 대용량 파일 업로드 시도
- SQL Injection 시도

## 문의

보안 취약점을 발견하면 즉시 보고해주세요.





