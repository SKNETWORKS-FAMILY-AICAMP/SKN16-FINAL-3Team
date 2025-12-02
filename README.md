# 🏦 하경은행 스마트 온보딩 플랫폼

![Python](https://img.shields.io/badge/Python-3.11-blue.svg)
![React](https://img.shields.io/badge/React-18-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104-green.svg)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-blue.svg)
![Docker](https://img.shields.io/badge/Docker-Enabled-blue.svg)

**RAG 기반 LLM 챗봇을 중심으로 한 종합적인 은행 신입사원 온보딩 플랫폼**

## 📋 프로젝트 소개

### 🎯 목적
은행 신입사원의 효과적인 온보딩과 지속적인 학습을 위한 AI 기반 멘토링 플랫폼입니다.

### 💎 핵심 가치
- **지능형 학습**: RAG 기술을 활용한 개인화된 학습 경험
- **접근성**: 언제 어디서나 학습할 수 있는 웹 기반 플랫폼
- **안전성**: 은행 업무에 특화된 보안 및 권한 관리
- **확장성**: 다양한 학습 콘텐츠와 기능 확장 가능

### ✨ 주요 기능
- **🤖 RAG 챗봇**: LangChain + OpenAI + pgvector 기반 지능형 멘토링 챗봇 (관리자 대시보드에서 LLM 제공자·응답 형식·응답 길이 설정 가능)
- **📚 자료실**: 업로드된 문서의 벡터 검색 및 지능형 추천
- **📝 시험 시스템**: 은행 업무 관련 시험 및 자동 채점
- **📊 대시보드**: 멘토/멘티별 맞춤형 학습 현황 분석
- **💬 동아리 라운지**: 멘토·멘티 취미 공유 커뮤니티
- **👥 사용자 관리**: 관리자, 멘토, 멘티 역할 기반 시스템
- **🎯 학습 추천**: 개인별 학습 패턴 분석 및 맞춤 추천

## 🛠️ 기술 스택

### 백엔드
- **Framework**: FastAPI 0.104+
- **Database**: PostgreSQL 15 + pgvector (벡터 검색)
- **ORM**: SQLModel (SQLAlchemy 기반)
- **AI/ML**: LangChain, OpenAI API
- **Authentication**: JWT + bcrypt
- **File Processing**: PyPDF2, python-docx

### 프론트엔드
- **Framework**: React 18 + TypeScript
- **Styling**: Tailwind CSS
- **State Management**: Zustand
- **Charts**: Recharts (데이터 시각화)
- **Animation**: Framer Motion
- **Build Tool**: Vite

### 인프라
- **Containerization**: Docker + Docker Compose
- **Database Management**: pgAdmin
- **Development**: Hot reload, Auto-restart

## 🚀 빠른 시작

### 🎯 처음 설정하는 팀원

```bash
# 1. 프로젝트 클론
git clone https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN16-4th-2Team.git
cd SKN16-4th-2Team

# 2. 시스템 시작 (모든 것이 자동으로 설정됩니다!)
docker-compose up -d

# 3. 잠시 기다린 후 브라우저에서 접속
# - 프론트엔드: http://localhost:3000
# - API 문서: http://localhost:8000/docs
# - pgAdmin: http://localhost:5050

# 4. 테스트 계정으로 로그인
# - 관리자: admin@bank.com / admin123
# - 멘토: mentor@bank.com / mentor123
# - 멘티: mentee@bank.com / mentee123
```

### 🔄 기존 환경 업데이트하는 팀원

```bash
# 1. 기존 컨테이너 정리
docker-compose down -v

# 2. 최신 코드 가져오기
git pull origin main

# 3. 새로운 설정으로 시작
docker-compose up -d
```

### 🚨 문제가 발생한 경우

```bash
# 자동 진단 도구 실행 (Windows)
.\diagnose.bat

# 또는 수동으로 초기 데이터 재생성
docker-compose exec backend python -m app.init_data
```

## 🌐 서비스 접속

| 서비스 | URL | 설명 |
|--------|-----|------|
| **프론트엔드** | http://localhost:3000 | 메인 웹 애플리케이션 |
| **백엔드 API** | http://localhost:8000 | REST API 서버 |
| **API 문서** | http://localhost:8000/docs | Swagger UI |
| **pgAdmin** | http://localhost:5050 | 데이터베이스 관리 |

## 🔑 테스트 계정

| 역할 | 이메일 | 비밀번호 | 권한 |
|------|--------|----------|------|
| **관리자** | admin@bank.com | admin123 | 전체 관리, 문서 업로드 |
| **멘토** | mentor@bank.com | mentor123 | 멘티 관리, 학습 지도 |
| **멘티** | mentee@bank.com | mentee123 | 학습, 시험 응시 |

## 🤖 RAG 챗봇 설정 가이드

### 1. OpenAI Key 설정
- `.env` 또는 호스트 환경 변수에 `OPENAI_API_KEY`를 설정합니다.
- 백엔드는 OpenAI Chat/Embedding 호출 시 환경 변수만 사용하며, UI나 DB에 API Key를 저장하지 않습니다.

### 2. RAG 소스 인덱싱
업데이트된 RAG 벡터 파이프라인은 `pgvector`를 활용합니다. JSONL 형식의 원천 데이터를 데이터베이스에 적재하려면 아래 스크립트를 실행하세요.

```bash
# 가상환경(또는 Docker 컨테이너)에서 실행
python -m backend.scripts.ingest_rag_sources \
    --base-path backend/data/rag_sources \
    --uploaded-by 1
```

- `--dry-run` 옵션을 추가하면 실제 DB 반영 없이 처리 대상만 확인할 수 있습니다.
- 스크립트는 파일명을 기반으로 문서를 생성하고 각 청크에 포함된 메타데이터(법령명, 조문, 상품 섹션 등)를 함께 저장합니다.

### 3. 로컬 Qwen 모델 연결 (선택)
RTX 3060 + Ryzen 5900 환경에서 권장 구성:

1. Hugging Face에서 `Qwen/Qwen2.5-7B-Instruct` 계열 모델을 다운로드합니다. (4bit GGUF / GPTQ 권장)
2. OpenAI 호환 서버(vLLM, llama.cpp-server, LM Studio 등)를 실행합니다.
3. 서버 기동 시 예시:
   - `llama.cpp` : `./server -m qwen2.5-7b-instruct-q4_k_m.gguf --host 0.0.0.0 --port 8001`
   - `LM Studio` : "OpenAI Compatible Server"를 켜고 모델을 로드합니다.
4. 필요 시 토큰 인증(Authorization 헤더)을 활성화합니다.

### 4. 관리자 대시보드에서 모델 전환
1. 관리자 계정으로 로그인 후 `대시보드 > 챗봇 설정` 탭으로 이동합니다.
2. `OpenAI (GPT)` 또는 `로컬 Qwen`을 선택합니다.
3. 로컬 Qwen을 선택했다면 다음 정보를 입력합니다.
   - Qwen 모델명 (예: `qwen2.5-7b-instruct`)
   - OpenAI 호환 Base URL (예: `http://localhost:8001/v1`)
   - 필요 시 API Key (LM Studio 등)
4. Temperature, Max Tokens, Top-K 값을 조정하고 **설정 저장**을 클릭합니다.
5. 설정 후 `챗봇 성능 검증` 탭이나 실제 챗봇 화면에서 응답 모델을 확인할 수 있습니다.

## 📁 프로젝트 구조

```
mentor-system/
├── backend/
│   ├── app/
│   │   ├── models/              # 데이터베이스 모델
│   │   │   ├── user.py          # 사용자 모델
│   │   │   ├── document.py      # 문서 모델
│   │   │   ├── post.py          # 게시글 모델
│   │   │   └── mentor.py        # 멘토링 모델
│   │   ├── routers/             # API 엔드포인트
│   │   │   ├── auth.py          # 인증 관련
│   │   │   ├── chat.py          # 챗봇 API
│   │   │   ├── documents.py     # 문서 관리
│   │   │   ├── exam.py          # 시험 시스템
│   │   │   ├── dashboard.py     # 대시보드
│   │   │   └── anonymous_board.py # 익명 게시판
│   │   ├── services/            # 비즈니스 로직
│   │   │   ├── rag_service.py   # RAG 챗봇 서비스
│   │   │   ├── exam_service.py  # 시험 채점 서비스
│   │   │   └── feedback_service.py # 피드백 서비스
│   │   ├── utils/               # 유틸리티 함수
│   │   │   ├── auth.py          # 인증 유틸리티
│   │   │   └── file_handler.py  # 파일 처리
│   │   ├── database.py          # DB 설정
│   │   ├── init_data.py         # 초기 데이터 생성
│   │   └── main.py              # FastAPI 앱
│   ├── data/                    # 학습 데이터
│   │   ├── bank_training_exam.json
│   │   ├── learning_materials_for_RAG.txt
│   │   └── mentee_exam_result.csv
│   ├── scripts/                 # 초기화 스크립트
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/          # React 컴포넌트
│   │   │   ├── ChatBot.tsx      # 챗봇 컴포넌트
│   │   │   ├── Layout.tsx       # 레이아웃 컴포넌트
│   │   │   └── DefaultUserIcon.tsx
│   │   ├── pages/               # 페이지 컴포넌트
│   │   │   ├── Landing.tsx      # 랜딩 페이지
│   │   │   ├── ProjectIntro.tsx # 프로젝트 소개
│   │   │   ├── Dashboard.tsx    # 대시보드
│   │   │   ├── RAG.tsx          # RAG 챗봇 페이지
│   │   │   ├── Documents.tsx    # 자료실
│   │   │   └── AnonymousBoard.tsx # 익명 게시판
│   │   ├── store/               # 상태 관리
│   │   │   ├── authStore.ts     # 인증 상태
│   │   │   └── chatStore.ts     # 채팅 상태
│   │   └── utils/
│   │       └── api.ts           # API 유틸리티
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml           # Docker 구성
├── setup.bat                    # Windows 설정 스크립트
├── setup.sh                     # Linux/Mac 설정 스크립트
├── diagnose.bat                 # 시스템 진단 도구
└── README.md
```

## 🔧 주요 API 엔드포인트

### 인증
- `POST /auth/login` - 사번/비밀번호 로그인
- `POST /auth/qr-login` - 사원증 QR 로그인
- `GET /auth/me` - 현재 사용자 정보
- `POST /auth/refresh` - 토큰 갱신

### 챗봇 & RAG
- `POST /chat/` - 챗봇 대화
- `GET /chat/history` - 채팅 기록 조회
- `POST /chat/feedback` - 챗봇 피드백
- `GET /admin/chatbot/config` - 챗봇 LLM 설정 조회 (관리자)
- `PUT /admin/chatbot/config` - 챗봇 LLM 설정 변경 (관리자)

### 문서 관리
- `POST /documents/upload` - 문서 업로드 (관리자만)
- `GET /documents/` - 문서 목록 조회
- `GET /documents/{id}` - 문서 상세 조회
- `DELETE /documents/{id}` - 문서 삭제

### 시험 시스템
- `GET /exam/questions` - 시험 문제 조회
- `POST /exam/submit` - 시험 답안 제출
- `GET /exam/results` - 시험 결과 조회
- `GET /exam/recommendations` - 학습 추천

### 대시보드
- `GET /dashboard/mentee` - 멘티 대시보드
- `GET /dashboard/mentor` - 멘토 대시보드
- `GET /dashboard/admin` - 관리자 대시보드

### 게시판
- `GET /posts/` - 게시글 목록
- `POST /posts/` - 게시글 작성
- `GET /posts/{id}` - 게시글 상세
- `POST /posts/{id}/comments` - 댓글 작성

## 🛡️ 보안

### 인증 & 권한
- **JWT 기반 인증**: 안전한 토큰 기반 인증
- **bcrypt 해싱**: 강력한 비밀번호 암호화
- **역할 기반 접근 제어 (RBAC)**: 관리자, 멘토, 멘티 권한 분리
- **CORS 설정**: 안전한 크로스 오리진 요청

### 데이터 보호
- **SQL 인젝션 방지**: SQLModel ORM 사용
- **파일 업로드 검증**: 허용된 파일 형식만 업로드
- **익명 게시판**: 완전한 익명성 보장

## 🛠️ 문제 해결

### 자동 진단 도구
```bash
# Windows
.\diagnose.bat

# 시스템 상태를 자동으로 진단하고 해결방안을 제시합니다
```

### 자주 발생하는 문제

1. **로그인 실패**: 테스트 계정으로 로그인이 안 되는 경우
   ```bash
   docker-compose exec backend python -m app.init_data
   ```

2. **데이터베이스 연결 실패**: PostgreSQL 연결 오류
   ```bash
   docker-compose down -v && docker-compose up -d --build
   ```

3. **포트 충돌**: 3000, 8000, 5432 포트가 이미 사용 중인 경우
   ```bash
   docker-compose down -v
   # 다른 서비스 종료 후 재시작
   ```

4. **CSP 오류**: 브라우저에서 `unsafe-eval` 오류가 발생하는 경우
   - 해결: 브라우저 캐시 삭제 후 새로고침

### 로그 확인

```bash
# 백엔드 로그
docker-compose logs -f backend

# 프론트엔드 로그
docker-compose logs -f frontend

# 데이터베이스 로그
docker-compose logs -f postgres
```

### 개발 환경 도구

```bash
# pgAdmin 실행 (데이터베이스 관리 UI)
docker-compose up -d

# 접속: http://localhost:5050
# 이메일: admin@admin.com
# 비밀번호: admin
```

## ⚡ 로컬 UI 개발 (npm run dev)

Docker 대신 Vite 개발 서버로 빠르게 화면을 수정하고 싶다면 아래 순서를 따르면 됩니다.

1. **백엔드 & DB 구동**
   ```bash
   # Docker를 사용하는 경우
   docker-compose up -d backend postgres

   # 또는 직접 실행 (예: Powershell)
   cd backend
   poetry install
   poetry run uvicorn app.main:app --reload --port 8000
   ```

2. **로컬 전용 가상 계정 생성**
   ```bash
   # Docker 컨테이너 안에서 실행
   docker-compose exec backend python -m app.init_local_dev_user

   # 또는 로컬에서 직접 실행
   cd backend
   poetry run python -m app.init_local_dev_user
   ```
   - 이메일: `202504075@bank.com`
   - 비밀번호: `19990512`
   - 이름: `임동우`

3. **프론트엔드 Vite 개발 서버 실행**
   ```powershell
   cd frontend
   npm install
   $env:VITE_PROXY_TARGET="http://localhost:8000"  # PowerShell
   npm run dev
   ```
   ```bash
   # macOS / Linux / Git Bash
   export VITE_PROXY_TARGET=http://localhost:8000
   npm run dev
   ```
   - 프록시 타겟을 지정하지 않으면 기본값(`http://backend:8000`)이 사용되므로
     Docker 없이 실행할 때는 반드시 `VITE_PROXY_TARGET`을 세팅하세요.

## 🆕 최신 업데이트 (v2.1)

### ✨ 새로운 기능들

- **📝 시험 시스템**: 은행 업무 관련 시험 및 자동 채점 기능
- **🎯 학습 추천**: 개인별 학습 패턴 분석 및 맞춤 추천
- **📊 고급 대시보드**: 상세한 학습 현황 분석 및 시각화
- **📄 프로젝트 소개 페이지**: 상세한 프로젝트 설명 및 기술 스택 소개
- **🔍 향상된 검색**: 벡터 기반 문서 검색 성능 개선

### 🔧 주요 개선사항

- **RAG 챗봇 성능 향상**: 더 정확하고 관련성 높은 답변 제공
- **사용자 경험 개선**: 직관적인 UI/UX 및 반응형 디자인
- **데이터 지속성 보장**: 컨테이너 재시작 시에도 데이터 유지
- **자동 초기화 시스템**: 컨테이너 시작 시 자동으로 초기 데이터 생성

### 📋 마이그레이션 가이드

기존 환경에서 업데이트하는 경우:

```bash
# 1. 기존 컨테이너 정리
docker-compose down -v

# 2. 최신 코드 가져오기
git pull origin main

# 3. 새로운 설정으로 시작
docker-compose up -d
```

## 📚 추가 문서

- [협업 가이드](./GIT_COLLABORATION_GUIDE.md) - 팀 협업을 위한 Git 워크플로우
- [보안 가이드](./SECURITY.md) - 보안 설정 및 모범 사례
- [시작 가이드](./START_HERE.md) - 프로젝트 시작을 위한 상세 가이드
- [시험 시스템 가이드](./EXAM_README.md) - 시험 기능 사용법
- [변경사항 기록](./CHANGELOG.md) - 버전별 변경사항

## 🤝 기여하기

1. 이 저장소를 포크합니다
2. 새로운 기능 브랜치를 생성합니다 (`git checkout -b feature/새기능`)
3. 변경사항을 커밋합니다 (`git commit -am '새 기능 추가'`)
4. 브랜치에 푸시합니다 (`git push origin feature/새기능`)
5. Pull Request를 생성합니다

## 📄 라이선스

이 프로젝트는 교육용 목적으로 개발되었습니다.

## 👥 팀원

- **프로젝트**: AI 활용 어플리케이션 개발 - 하경은행 스마트 온보딩 플랫폼
- **기간**: 2025년 10월
- **팀**: SKN16 4기 2팀

---

**🚀 지금 바로 시작해보세요!**

```bash
git clone https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN16-4th-2Team.git
cd SKN16-4th-2Team
docker-compose up -d
```