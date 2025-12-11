# 환경 변수 템플릿

이 파일을 참고하여 `.env` 파일을 생성하세요.

```bash
# ============================================
# 데이터베이스 설정
# ============================================
# 로컬 개발 환경
DATABASE_URL=postgresql://mentoruser:mentorpass@localhost:5432/mentordb

# AWS RDS 사용 시 (프로덕션)
# DATABASE_URL=postgresql://user:password@your-rds-endpoint.region.rds.amazonaws.com:5432/mentordb

# ============================================
# 보안 설정 (⚠️ 반드시 변경 필요)
# ============================================
# 최소 32자 이상의 강력한 랜덤 문자열 사용
# 생성 방법: openssl rand -hex 32
SECRET_KEY=your-default-secret-key-change-this-to-a-strong-random-string-min-32-chars

# JWT 설정
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# ============================================
# API Keys
# ============================================
OPENAI_API_KEY=your-openai-api-key-here
LANGSMITH_API_KEY=your-langsmith-api-key-here
LANGSMITH_PROJECT=bank-mentor-system
LANGCHAIN_API_KEY=your-langchain-api-key-here

# ============================================
# 프론트엔드 설정
# ============================================
# 로컬 개발 환경
# VITE_API_URL=http://localhost:8000

# 프로덕션 환경
# VITE_API_URL=https://api.yourdomain.com/api

# ============================================
# 환경 설정
# ============================================
# development (기본값) 또는 production
ENVIRONMENT=development

# ============================================
# CORS 설정 (프로덕션 환경에서만 사용)
# ============================================
# 프로덕션 환경에서 허용할 도메인 목록 (쉼표로 구분)
# CORS_ORIGINS=https://yourdomain.com,https://www.yourdomain.com

# ============================================
# 파일 업로드 설정
# ============================================
UPLOAD_DIR=/app/data/rag_sources/uploads
MAX_UPLOAD_SIZE=10485760

# ============================================
# 데이터베이스 설정 (docker-compose.yml용)
# ============================================
DB_USER=mentoruser
DB_PASSWORD=mentorpass
DB_NAME=mentordb
```

