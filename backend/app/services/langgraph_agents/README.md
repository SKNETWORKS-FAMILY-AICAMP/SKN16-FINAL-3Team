# LangGraph 멀티 에이전트 시스템

## 개요

은행 멘토 시스템의 멀티 에이전트 아키텍처를 시각화하고 관리하는 LangGraph 시스템입니다.

## 아키텍처

- **구조**: Hierarchical + Network (하이라키 + 네트워크)
- **에이전트 수**: 10개
- **연결**: 10개의 데이터 플로우

## 에이전트 목록

### 1. Prompt Orchestrator (오케스트레이터)
- **역할**: 페르소나/시츄에이션 기반 프롬프트 구성 및 대화 흐름 관리
- **입력**: persona, situation, user_text, rag_hits, history
- **출력**: llm_messages, conversation_state
- **파일**: `promptOrchestrator.py`

### 2. RAG Simulation Service (프로세서)
- **역할**: STT/LLM/TTS 음성 시뮬레이션 처리
- **입력**: audio_data, session_data, user_message
- **출력**: transcription, customer_response, audio_output, evaluation
- **파일**: `rag_simulation_service.py`

### 3. Advanced Simulation Service (프로세서)
- **역할**: 고도화된 AI 고객 페르소나 시뮬레이션
- **입력**: persona_id, situation_id, audio_input
- **출력**: persona_response, analytics, voice_output
- **파일**: `advanced_simulation_service.py`

### 4. RAG Service (검색기)
- **역할**: 벡터 검색 기반 문서 검색 및 답변 생성
- **입력**: query, chat_history, user_id
- **출력**: search_results, answer, sources
- **파일**: `rag_service.py`

### 5. Banking Normalizer (프로세서)
- **역할**: 은행 용어 및 음성인식 텍스트 정규화
- **입력**: raw_text
- **출력**: normalized_text, corrections
- **파일**: `banking_normalizer.py`

### 6. Offtopic Detector (감지기)
- **역할**: 은행 업무 범위 이탈 감지 및 피벗 응답 생성
- **입력**: user_message, context
- **출력**: is_ontopic, category, pivot_response
- **파일**: `offtopic_detector.py`

### 7. Persona Voice (생성기)
- **역할**: 페르소나별 음성 파라미터 및 SSML 생성
- **입력**: persona, script, age_group
- **출력**: voice_params, ssml
- **파일**: `persona_voice.py`

### 8. Product Knowledge Service (검색기)
- **역할**: 은행 상품 정보 검색 및 매칭
- **입력**: query, product_type
- **출력**: product_matches, product_details
- **파일**: `product_knowledge_service.py`

### 9. Feedback Service (평가자)
- **역할**: 시뮬레이션 피드백 및 평가 생성
- **입력**: session_id, transcript, evaluation_data
- **출력**: feedback, scores, improvement_tips
- **파일**: `feedback_service.py`

### 10. Exam Service (평가자)
- **역할**: 은행원 시험 채점 및 평가
- **입력**: answers, exam_data
- **출력**: scores, analysis, recommendations
- **파일**: `exam_service.py`

## API 엔드포인트

### 그래프 구조 조회
```
GET /api/langgraph/graph
```
전체 LangGraph 구조 반환 (노드 + 엣지)

### 노드 목록
```
GET /api/langgraph/nodes
```
모든 에이전트 노드 목록

### 노드 상세 정보
```
GET /api/langgraph/nodes/{node_id}
```
특정 노드의 상세 정보, 입출력 엣지, 의존성

### 엣지 목록
```
GET /api/langgraph/edges
```
모든 데이터 플로우 연결

### 실행 순서
```
GET /api/langgraph/execution-order
```
토폴로지 정렬된 에이전트 실행 순서

### 통계
```
GET /api/langgraph/statistics
```
에이전트 통계 및 LangSmith 연동 상태

### 세션 추적
```
GET /api/langgraph/trace/{session_id}
```
특정 세션의 실행 추적 (LangSmith)

### 에이전트 통계
```
GET /api/langgraph/agent/{agent_id}/statistics?days=7
```
특정 에이전트의 통계 (LangSmith)

## LangSmith 연동

### 환경 변수 설정
```bash
LANGSMITH_API_KEY=your_api_key_here
LANGSMITH_PROJECT=bank-mentor-system
```

### 사용 예시

#### 1. 자동 추적 데코레이터
```python
from app.services.langgraph_agents.langsmith_integration import trace_agent

@trace_agent("rag_service", "RAG Service")
def process_query(query: str):
    # 함수 실행이 자동으로 추적됨
    pass
```

#### 2. 수동 추적
```python
from app.services.langgraph_agents.langsmith_integration import get_langsmith_tracer

tracer = get_langsmith_tracer()

# 에이전트 실행 추적
tracer.trace_agent_execution(
    agent_id="rag_service",
    agent_name="RAG Service",
    inputs={"query": "예금 상품"},
    outputs={"answer": "..."},
    execution_time=1.5,
    status="success"
)

# 세션 추적
tracer.trace_session(
    session_id="session_123",
    session_type="simulation",
    agents_used=["prompt_orchestrator", "rag_simulation"],
    total_time=5.2,
    status="completed"
)
```

## 프론트엔드 사용법

### 관리자 대시보드
1. 관리자로 로그인
2. Dashboard 페이지 접속
3. "LangGraph" 탭 클릭

### 기능
- **아키텍처 다이어그램**: 인터랙티브 그래프 시각화
- **노드 클릭**: 에이전트 상세 정보 표시
- **레이아웃 변경**: 세로/가로 레이아웃 전환
- **미니맵**: 전체 구조 미리보기
- **줌/팬**: 확대/축소 및 드래그

## 파일 구조

```
backend/app/services/langgraph_agents/
├── graph_definition.py          # 그래프 구조 정의
├── langsmith_integration.py     # LangSmith 연동
└── README.md                    # 이 파일

backend/app/routers/
└── langgraph.py                 # API 엔드포인트

frontend/src/components/
├── LangGraphView.tsx            # React Flow 다이어그램
└── NodeDetailPanel.tsx          # 노드 상세 패널

frontend/src/pages/
└── Dashboard.tsx                # LangGraph 탭 추가
```

## 개발 가이드

### 새 에이전트 추가
1. `graph_definition.py`의 `_build_graph()`에 노드 추가
2. `_build_edges()`에 연결 추가
3. 실제 서비스 파일 구현
4. LangSmith 추적 추가 (선택)

### 테스트
```bash
# 백엔드 API 테스트
curl -H "Authorization: Bearer YOUR_TOKEN" http://localhost:8000/api/langgraph/graph

# 프론트엔드
npm run dev
```

## 향후 계획

- [ ] LangSmith 실제 API 연동
- [ ] 실시간 에이전트 상태 모니터링
- [ ] 에이전트 성능 분석 대시보드
- [ ] A/B 테스트 지원
- [ ] 에이전트 버전 관리

