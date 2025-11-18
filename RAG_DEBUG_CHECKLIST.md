# RAG 평가 결과 디버깅 체크리스트

## 1. 브라우저 콘솔 확인 (F12 → Console)

### 테스트 모드 실행 중 확인할 로그:
- [ ] `🧪 ✅ RAG 평가 결과 수집 (음성 입력 - 전체 배열)` 또는 `🧪 ✅ RAG 평가 결과 수집 (텍스트 입력 - 전체 배열)` 로그가 각 턴마다 나타나는지
- [ ] 각 로그의 `total` 값이 0보다 큰지 (예: `total: 2`, `total: 4` 등)
- [ ] `🧪 피드백 생성 전 RAG 평가 결과 상태` 로그에서 `ragEvaluationsLength` 값 확인
- [ ] `🧪 ✅ 테스트 모드: RAG 평가 결과를 피드백 요청에 포함` 로그가 나타나는지

### 피드백 생성 시 확인할 로그:
- [ ] `🧪 피드백 데이터 수신 후 RAG 평가 결과 확인` 로그에서:
  - `ragEvaluationsLength` 값
  - `hasFeedbackRagEvaluations` 값 (true/false)
  - `feedbackRagEvaluationsLength` 값

### 피드백 페이지에서 확인할 로그:
- [ ] `📊 피드백 데이터 수신:` 로그에서:
  - `hasRagEvaluations` 값
  - `ragEvaluationsCount` 값
- [ ] `🧪 ⚠️ 피드백 데이터에 RAG 평가 결과가 없습니다!` 경고가 나타나는지
- [ ] `🧪 RAG 평가 결과 섹션 표시 조건 불만족` 로그가 나타나는지

## 2. 네트워크 탭 확인 (F12 → Network)

### `/rag-simulation/generate-feedback` 요청 확인:
1. **Request Payload** 확인:
   - `rag_evaluations` 필드가 있는지
   - `rag_evaluations`가 배열이고 길이가 0보다 큰지
   - 각 항목에 `turn_index`, `role`, `evaluation` 필드가 있는지

2. **Response** 확인:
   - `feedback.rag_evaluations` 필드가 있는지
   - `feedback.rag_summary` 필드가 있는지

### `/rag-simulation/process-voice-interaction` 요청 확인 (각 턴마다):
1. **Response** 확인:
   - `rag_evaluations` 필드가 있는지
   - `rag_evaluations`가 배열이고 각 턴마다 증가하는지

## 3. 백엔드 로그 확인

### 테스트 모드 실행 중 확인할 로그:
- [ ] `🧪 ===== 테스트 모드 처리 시작 =====` 로그
- [ ] `🧪 현재까지 RAG 평가 결과 수: X개` 로그 (각 턴마다 증가해야 함)
- [ ] `🧪 고객 발화 RAG 평가: X.X점` 또는 `🧪 직원 발화 RAG 평가: X.X점` 로그
- [ ] `🧪 ✅ 고객 발화 처리 완료 - RAG 평가 결과 X개 포함` 또는 `🧪 ✅ 직원 발화 처리 완료 - RAG 평가 결과 X개 포함` 로그

### 피드백 생성 시 확인할 로그:
- [ ] `🧪 RAG 평가 결과를 피드백 데이터에 포함: X개 평가, 평균 X.X점` 로그

## 4. 문제 진단 포인트

### Case 1: `ragEvaluationsLength`가 0인 경우
**원인**: 백엔드에서 RAG 평가 결과를 반환하지 않거나, 프론트엔드에서 수집하지 않음
**확인**: 
- 백엔드 로그에서 `🧪 RAG 평가 결과 X개 포함` 로그 확인
- 프론트엔드 콘솔에서 `🧪 ✅ RAG 평가 결과 수집` 로그 확인

### Case 2: 피드백 요청에 `rag_evaluations`가 없는 경우
**원인**: `handleEndSimulation`에서 `rag_evaluations`를 요청에 포함하지 않음
**확인**:
- 콘솔에서 `🧪 ✅ 테스트 모드: RAG 평가 결과를 피드백 요청에 포함` 로그 확인
- Network 탭에서 Request Payload 확인

### Case 3: 피드백 응답에 `rag_evaluations`가 없는 경우
**원인**: 백엔드에서 피드백 생성 시 `rag_evaluations`를 포함하지 않음
**확인**:
- 백엔드 로그에서 `🧪 RAG 평가 결과를 피드백 데이터에 포함` 로그 확인
- Network 탭에서 Response 확인

### Case 4: 피드백 페이지에서 `rag_evaluations`가 없는 경우
**원인**: `location.state`로 전달할 때 데이터가 손실됨
**확인**:
- 콘솔에서 `📊 피드백 데이터 수신:` 로그 확인
- `navigate` 호출 시 `state`에 `rag_evaluations` 포함 여부 확인

## 5. 수집할 정보

다음 정보를 제공해주시면 정확한 진단이 가능합니다:

1. **콘솔 로그 스크린샷**:
   - `🧪 피드백 생성 전 RAG 평가 결과 상태` 로그
   - `🧪 피드백 데이터 수신 후 RAG 평가 결과 확인` 로그
   - `📊 피드백 데이터 수신:` 로그

2. **Network 탭 스크린샷**:
   - `/rag-simulation/generate-feedback` 요청의 Request Payload
   - `/rag-simulation/generate-feedback` 요청의 Response

3. **백엔드 로그**:
   - 테스트 모드 실행 중 RAG 평가 관련 로그
   - 피드백 생성 시 로그

