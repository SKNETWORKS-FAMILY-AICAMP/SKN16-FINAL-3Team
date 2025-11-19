# 🎯 RAG 시뮬레이션 평가 기능 통합 가이드

## 📌 개요

RAG 시뮬레이션에 **평가 및 피드백 기능**을 통합했습니다. 사용자가 시뮬레이션을 완료하면 GPT-4 기반 평가 모델이 자동으로 점수를 매기고 개선 제안을 제공합니다.

---

## ✅ 구현된 기능

### 1. **DB 스키마 (3개 테이블)**

#### `rag_simulation_sessions`
- 세션 기본 정보 (session_key, user_id, persona_id, scenario_id)
- 시작/종료 시간, 완료 여부

#### `rag_simulation_turns`
- 대화 턴 기록 (직원/고객 발화)
- 음성 특성 (속도, 톤 점수)

#### `rag_simulation_evaluations`
- 평가 점수 (지식 40 / 기술 30 / 태도 30 = 총 100점)
- 상세 피드백 (강점, 개선점, 추천 학습)

### 2. **EvaluationService**

**파일**: `backend/app/services/evaluation_service.py`

주요 메서드:
- `evaluate_session(session_key)`: 세션 평가 실행
- `_build_payload()`: 대화 기록을 평가용 JSON으로 변환
- `_call_eval_model()`: GPT-4 호출 (temperature=0.0)
- `_parse_eval_json()`: JSON 파싱 및 검증
- `_save_evaluation()`: 평가 결과 DB 저장

### 3. **API 엔드포인트**

#### `POST /rag-simulation/evaluate`
시뮬레이션 평가 실행

**요청**:
```json
{
  "session_key": "session_1_20241201_120000"
}
```

**응답**:
```json
{
  "session_id": "session_1_20241201_120000",
  "score": {
    "knowledge": {"point": 35, "reason": "..."},
    "skill": {"point": 25, "reason": "..."},
    "attitude": {"point": 28, "reason": "..."},
    "total": 88
  },
  "detail_feedback": {
    "strengths": ["친절한 응대", "정확한 정보 제공"],
    "improvements": ["고객 동의 확인 부족", "속도 조절 필요"],
    "recommended_training": ["고객심리학", "은행법규"]
  }
}
```

---

## 🔧 사용 방법

### 1. DB 테이블 생성

```bash
cd backend
python scripts/init_rag_simulation_tables.py
```

### 2. 시뮬레이션 시작

기존과 동일하게 `/rag-simulation/start-simulation` 호출

**개선사항** (미구현):
- 세션 정보를 DB에 자동 저장해야 함
- 현재는 평가 엔드포인트만 준비됨

### 3. 대화 기록 저장

매 `process-voice-interaction` 호출마다:
- 직원 발화 (`role="teller"`) 저장
- 고객 발화 (`role="customer"`) 저장

**현재 상태**: 엔드포인트 로직에 추가 필요

### 4. 시뮬레이션 종료 감지

시뮬레이션 종료 조건 (예정):
- "시뮬레이션 종료" 버튼 클릭
- 특정 문구 감지 ("감사합니다", "끝내기" 등)

**현재**: 엔드포인트 없음 (프론트엔드에서 명시적 호출)

### 5. 평가 실행

```bash
curl -X POST http://localhost:8000/rag-simulation/evaluate \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"session_key": "session_1_20241201_120000"}'
```

---

## 🚧 TODO: 추가 구현 필요

### 1. **세션/Turn 기록 자동화** ⚠️

**파일**: `backend/app/routers/rag_simulation.py`

#### `start_rag_simulation` 수정
```python
# 결과 반환 전에 추가:
sim_session = RAGSimulationSession(
    session_key=result["session_id"],
    user_id=current_user.id,
    persona_id=result["persona"]["id"],
    scenario_id=result["scenario"]["id"],
    # ...
)
session.add(sim_session)
session.commit()
```

#### `process_rag_voice_interaction` 수정
```python
# result 반환 전에 추가:
# 1. 직원 발화 저장
turn_teller = RAGSimulationTurn(
    session_id=sim_session.id,
    turn_index=get_next_turn_index(),
    role="teller",
    text=result["transcribed_text"]
)
session.add(turn_teller)

# 2. 고객 발화 저장
turn_customer = RAGSimulationTurn(
    session_id=sim_session.id,
    turn_index=get_next_turn_index(),
    role="customer",
    text=result["customer_response"]
)
session.add(turn_customer)
session.commit()
```

### 2. **시뮬레이션 종료 감지**

프론트엔드에서 "시뮬레이션 종료" 버튼 추가:
```typescript
const endSimulation = async () => {
  // 세션 완료 플래그 설정 (옵션)
  await api.post('/rag-simulation/mark-complete', {
    session_key: sessionId
  });
  
  // 평가 실행
  const evaluation = await api.post('/rag-simulation/evaluate', {
    session_key: sessionId
  });
  
  // 결과 페이지로 이동
  navigate('/evaluation', { state: evaluation.data });
};
```

### 3. **프론트엔드 UI**

**페이지**: `frontend/src/pages/EvaluationResults.tsx` (신규 생성)

표시 내용:
- **레이더 차트**: 지식/기술/태도 점수
- **강점 리스트**: `strengths`
- **개선점 리스트**: `improvements`
- **추천 학습**: `recommended_training`
- **다시 훈련하기** 버튼

---

## 📊 GPT-4 평가 모델

### 시스템 프롬프트
```
당신은 "신입 은행원 고객 응대 시뮬레이션 평가 모델"입니다.
NCS 국가직무능력기준을 기반으로 지식(40) / 기술(30) / 태도(30)로 평가합니다.
대화 속 teller 발화만 평가하고, 반드시 JSON 스키마를 준수하며 출력합니다.
근거는 반드시 발화 문장을 직접 인용합니다.
개선안은 행동 기반 문장으로 제시합니다.
불필요한 설명 없이 JSON ONLY 출력.
```

### 평가 기준

#### 지식 (40점)
- 은행 상품/서비스 정확성
- 법규/정책 이해
- 업무 프로세스 정확성

#### 기술 (30점)
- 의사소통 능력
- 상황 대응 능력
- 고객 응대 기법

#### 태도 (30점)
- 친절성
- 공감 능력
- 서비스 마인드

---

## 🧪 테스트 예제

### 1. 시뮬레이션 시작

```bash
POST /rag-simulation/start-simulation
{
  "persona_id": "persona_1",
  "scenario_id": "scenario_1",
  "gender": "male"
}
```

**응답의 `session_id` 저장**

### 2. 대화 진행 (2-3턴)

```bash
POST /rag-simulation/process-voice-interaction
# ... 여러 번 반복
```

### 3. 평가 실행

```bash
POST /rag-simulation/evaluate
{
  "session_key": "session_1_20241201_120000"
}
```

**예상 응답**:
```json
{
  "session_id": "session_1_20241201_120000",
  "score": {
    "knowledge": {"point": 35, "reason": ""},
    "skill": {"point": 25, "reason": ""},
    "attitude": {"point": 28, "reason": ""},
    "total": 88
  },
  "detail_feedback": {
    "strengths": ["친절한 응대", "정확한 정보 제공"],
    "improvements": ["고객 동의 확인 부족"],
    "recommended_training": ["고객심리학"]
  }
}
```

---

## ⚠️ 주의사항

1. **세션/Turn 기록이 완료되어야 평가 가능**
   - 현재는 엔드포인트만 구현됨
   - 실제 기록 로직 추가 필요

2. **GPT-4 API 키 필수**
   - `OPENAI_API_KEY` 환경변수 설정

3. **DB 테이블 생성 필수**
   - `init_rag_simulation_tables.py` 실행

4. **세션 완료 처리**
   - 프론트엔드에서 명시적으로 평가 호출
   - 자동 종료 감지는 미구현

---

## ✅ 완료된 작업

- [x] DB 스키마 설계 (3개 테이블)
- [x] EvaluationService 구현
- [x] `/evaluate` API 엔드포인트 추가
- [x] GPT-4 평가 모델 통합
- [x] JSON 파싱 및 검증
- [x] DB 저장 로직

---

## 🔄 남은 작업

- [ ] 세션 시작 시 DB 저장 (`start_rag_simulation`)
- [ ] 대화 턴 DB 저장 (`process_voice_interaction`)
- [ ] 시뮬레이션 종료 감지 로직
- [ ] 프론트엔드 평가 결과 UI
- [ ] 레이더 차트 컴포넌트
- [ ] "다시 훈련하기" 기능

