# LangGraph 관리자 대시보드 가이드

## 🎯 개선 사항 (v1.1)

### ✅ 완료된 개선
1. **화살표 시각화 강화**
   - 화살표 굵기 증가 (2px → 3px)
   - 파란색으로 강조 (#3b82f6)
   - 화살표 헤드 크기 증가 (20px → 25px)
   - 레이블 폰트 크기 및 두께 증가

2. **정적 다이어그램으로 전환**
   - 노드 드래그 비활성화 (nodesDraggable=false)
   - 노드 연결 비활성화 (nodesConnectable=false)
   - 고정 레이아웃 유지
   - 줌 범위 제한 (0.5x ~ 1.5x)

3. **노드 디자인 개선**
   - 노드 크기 증가 (220px)
   - 호버 효과 강화 (scale-105)
   - 입출력 표시 개선 (← IN / OUT →)
   - 그림자 효과 강화

4. **범례 개선**
   - 화살표 의미 설명 추가
   - 에이전트 타입 구분 명확화

5. **LangSmith 연동 준비**
   - docker-compose.yml에 환경변수 추가
   - LANGSMITH_API_KEY 및 LANGSMITH_PROJECT 설정

## 🚀 사용 방법

### 1. 환경 설정
`.env` 파일에 LangSmith API 키 추가:
```bash
LANGSMITH_API_KEY=your_api_key_here
LANGSMITH_PROJECT=bank-mentor-system
```

### 2. Docker 재시작
```bash
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### 3. 대시보드 접속
1. http://localhost:3000 접속
2. 관리자 계정으로 로그인
3. Dashboard → **LangGraph 탭** 클릭

## 📊 화면 구성

### 주요 영역
```
┌─────────────────────────────────────────────────┐
│  LangGraph 아키텍처 (좌측 상단)                 │
│  - 총 에이전트: 10                              │
│  - 연결: 10                                     │
│  - 구조: Hierarchical + Network                 │
│  - 레이아웃: 세로 / 가로 전환                   │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│  에이전트 타입 (우측 상단)                      │
│  🟣 Orchestrator - 오케스트레이터               │
│  🔵 Processor - 프로세서                        │
│  🟢 Evaluator - 평가자                          │
│  🟠 Detector - 감지기                           │
│  🌸 Generator - 생성기                          │
│  🟡 Retriever - 검색기                          │
│                                                 │
│  화살표 의미:                                   │
│  ──→ 데이터 흐름                                │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│           [다이어그램 영역]                     │
│                                                 │
│  ┌──────────────┐                              │
│  │ Orchestrator │──→ ┌──────────┐             │
│  │ ← 5 IN       │    │ RAG Sim. │             │
│  │ 2 OUT →      │    │ ← 3 IN   │             │
│  └──────────────┘    │ 4 OUT →  │             │
│         ↓            └──────────┘             │
│  ┌──────────────┐         ↓                   │
│  │ RAG Service  │    ┌──────────┐             │
│  │ ← 3 IN       │    │ Feedback │             │
│  │ 3 OUT →      │    │ ← 3 IN   │             │
│  └──────────────┘    │ 3 OUT →  │             │
│                      └──────────┘             │
│                                                 │
└─────────────────────────────────────────────────┘
```

## 🎨 UI 특징

### 노드 표시
- **색상**: 타입별로 다른 색상 (보라색=오케스트레이터, 파란색=프로세서 등)
- **아이콘**: 각 타입에 맞는 아이콘 표시
- **입출력**: `← 5 IN` / `2 OUT →` 형태로 명확하게 표시
- **호버**: 마우스 오버 시 확대 효과

### 화살표 표시
- **굵기**: 3px의 굵은 파란색 선
- **애니메이션**: 데이터 흐름을 나타내는 애니메이션
- **레이블**: 전달되는 데이터 타입 표시 (예: "정규화된 텍스트")

### 정적 레이아웃
- **고정 위치**: 노드는 드래그 불가능
- **줌**: 마우스 휠로 확대/축소 (0.5x ~ 1.5x)
- **레이아웃 전환**: 세로/가로 버튼으로 레이아웃 변경

## 🔍 상세 정보 패널

노드를 클릭하면 우측에 패널이 표시됩니다:

```
┌─────────────────────────────────┐
│  [노드 이름]                    │
│  Type: orchestrator             │
├─────────────────────────────────┤
│  📝 설명                        │
│  페르소나/시츄에이션 기반       │
│  프롬프트 구성 및 대화 흐름 관리│
├─────────────────────────────────┤
│  💻 서비스 정보                 │
│  파일: promptOrchestrator.py    │
│  함수: compose_llm_messages()   │
│  상태: idle                     │
├─────────────────────────────────┤
│  → 입력 (Inputs)                │
│  - persona                      │
│  - situation                    │
│  - user_text                    │
│  - rag_hits                     │
│  - history                      │
├─────────────────────────────────┤
│  ← 출력 (Outputs)               │
│  - llm_messages                 │
│  - conversation_state           │
├─────────────────────────────────┤
│  🔗 의존성                      │
│  - rag_simulation               │
│  - banking_normalizer           │
│  - offtopic_detector            │
├─────────────────────────────────┤
│  📥 들어오는 연결 (3)           │
│  banking_normalizer → 정규화된  │
│  offtopic_detector → 주제 적합성│
│  rag_service → RAG 검색 결과    │
├─────────────────────────────────┤
│  📤 나가는 연결 (2)             │
│  → rag_simulation (LLM 메시지) │
│  → advanced_simulation (프롬프트)│
└─────────────────────────────────┘
```

## 📈 API 엔드포인트

### 그래프 구조
```
GET /api/langgraph/graph
```
전체 LangGraph 구조 (노드 + 엣지)

### 통계
```
GET /api/langgraph/statistics
```
- 총 노드 수
- 총 엣지 수
- 노드 타입별 통계
- LangSmith 연동 상태

### 노드 상세
```
GET /api/langgraph/nodes/{node_id}
```
특정 노드의 상세 정보

## 🔧 트러블슈팅

### 화살표가 보이지 않는 경우
- 브라우저 캐시 삭제 후 새로고침
- React Flow 라이브러리 재설치: `npm install reactflow`

### 노드가 드래그되는 경우
- `nodesDraggable={false}` 설정 확인
- 브라우저 개발자 도구에서 콘솔 에러 확인

### LangSmith 연동이 안 되는 경우
- `.env` 파일에 API 키 확인
- `docker-compose logs backend` 로그 확인
- 환경변수가 제대로 전달되었는지 확인

## 📚 추가 정보

### 에이전트 설명

1. **Prompt Orchestrator** (오케스트레이터)
   - 역할: 전체 프롬프트 및 대화 흐름 관리
   - 의존성: 3개 (RAG Sim, Normalizer, Detector)

2. **RAG Simulation Service** (프로세서)
   - 역할: STT/LLM/TTS 음성 시뮬레이션
   - 주요 기능: 음성 처리, 평가 생성

3. **Advanced Simulation Service** (프로세서)
   - 역할: 고도화된 AI 고객 페르소나
   - 특징: 페르소나별 음성 생성

4. **RAG Service** (검색기)
   - 역할: 벡터 검색 기반 문서 검색
   - 기술: pgvector, OpenAI embeddings

5. **Banking Normalizer** (프로세서)
   - 역할: 은행 용어 정규화
   - 특징: 음성인식 보정

6. **Offtopic Detector** (감지기)
   - 역할: 주제 이탈 감지
   - 기능: 피벗 응답 생성

7. **Persona Voice** (생성기)
   - 역할: 페르소나별 음성 생성
   - 기술: SSML, TTS

8. **Product Knowledge Service** (검색기)
   - 역할: 은행 상품 정보 검색
   - 데이터: 상품 카탈로그

9. **Feedback Service** (평가자)
   - 역할: 시뮬레이션 피드백 생성
   - 평가 항목: 지식, 기술, 태도

10. **Exam Service** (평가자)
    - 역할: 시험 채점 및 평가
    - 분석: 성적 분석, 개선점 제안

## 🎯 향후 개선 계획

- [ ] 실시간 실행 추적 (LangSmith)
- [ ] 에이전트 성능 메트릭 표시
- [ ] 에러 발생 시 노드 색상 변경
- [ ] 실행 중인 노드 애니메이션 효과
- [ ] 데이터 플로우 시뮬레이션
- [ ] A/B 테스트 지원

