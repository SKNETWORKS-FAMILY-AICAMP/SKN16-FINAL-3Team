# 🚀 빠른 시작 가이드

## 은행 신입사원 멘토 시스템에 오신 것을 환영합니다!

이 시스템은 RAG 기반 AI 챗봇을 중심으로 한 종합 온보딩 플랫폼입니다.

## ⚡ 가장 빠른 시작 방법 (Docker 사용)

### 1. Docker가 설치되어 있나요?
- **예**: 아래 명령어를 실행하세요
- **아니오**: [Docker Desktop](https://www.docker.com/products/docker-desktop) 설치

### 2. 시스템 시작
```bash
# 현재 디렉토리에서 (c:\cant)
docker-compose up --build
```

### 3. 자동 초기화
시스템이 자동으로 초기 데이터를 생성합니다. 별도 실행 불필요!

### 4. 브라우저로 접속
- 🌐 프론트엔드: http://localhost:3000
- 🔧 API 문서: http://localhost:8000/docs

### 5. 로그인
```
이메일: mentee@bank.com
비밀번호: mentee123
```

## 🎯 주요 기능

### 1️⃣ AI 챗봇
- 우측 하단 채팅 아이콘 클릭
- 은행 업무 관련 질문 입력
- RAG 기반 정확한 답변 제공

### 2️⃣ 자료실
- 상단 메뉴 "자료실" 클릭
- 카테고리별 문서 검색
- 필요한 자료 다운로드

### 3️⃣ 동아리 라운지 (취미 게시판)
- 완전 익명 보장
- 자유로운 소통
- 게시글 작성 및 댓글

### 4️⃣ 대시보드
- 학습 진행도 확인
- 시험 점수 차트
- 담당 멘토 정보

## 👥 테스트 계정

### 멘티 (신입사원)
```
이메일: mentee@bank.com
비밀번호: mentee123
```

### 멘토
```
이메일: mentor@bank.com
비밀번호: mentor123
```

### 관리자
```
이메일: admin@bank.com
비밀번호: admin123
```

## 📚 더 자세한 정보

- **설치 가이드**: `SETUP_GUIDE.md` 참조
- **프로젝트 소개**: `README.md` 참조
- **API 문서**: http://localhost:8000/docs

## 🛠️ 문제 해결

### Docker가 시작되지 않는 경우
```bash
# 기존 컨테이너 제거
docker-compose down -v

# 재시작
docker-compose up --build
```

### 포트가 이미 사용 중인 경우
- `docker-compose.yml`에서 포트 번호 변경
- 3000 → 3001, 8000 → 8001 등

### 데이터베이스 오류
```bash
# 컨테이너 재시작
docker-compose restart db

# 초기 데이터 다시 생성
docker-compose exec backend python -m app.init_data
```

## 💡 개발 팁

### 백엔드 로그 확인
```bash
docker-compose logs -f backend
```

### 프론트엔드 로그 확인
```bash
docker-compose logs -f frontend
```

### 데이터베이스 접속
```bash
docker-compose exec db psql -U mentoruser -d mentordb
```

## 🎉 즐거운 개발 되세요!

궁금한 점이 있으시면 언제든 질문해주세요.



