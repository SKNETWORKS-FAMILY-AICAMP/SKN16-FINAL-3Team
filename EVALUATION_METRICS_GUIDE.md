# 🎯 시뮬레이션 평가 모듈 개발 가이드

## 📊 개요

은행 신입행원 온보딩 AI 플랫폼의 **고객 응대 시뮬레이션 평가 모듈**입니다. 6가지 세부 지표를 기반으로 신입행원의 응대 품질을 정량적으로 평가합니다.

---

## 🎯 평가 지표 (6가지)

### 1️⃣ 지식 (Knowledge) - 가중치 20%

**목적**: 은행 상품(여신/수신 등)에 대한 설명이 정확한가

**평가 기준**:
- 상품 정보(금리, 한도, 조건 등)의 정확성
- 명백한 오류나 잘못된 정보 제공 시 감점 (-10점/건)
- 불확실한 표현("~같아요", "~보이는데") 사용 시 감점

**산출 로직**:
```
knowledge_score = (정확정보매칭수 / 전체핵심정보항목수) × 100
- 명백한 오류 감점: -10점/건
```

**구현**: `score_metrics.py::calculate_knowledge_score()`

---

### 2️⃣ 기술 (Skill) - 가중치 20%

**목적**: 응대 절차가 체계적이며 목표를 달성했는가

**평가 기준**:
- **대화 흐름 (40%)**: 인사 → 요구파악 → 정보제공 → 마무리
- **목표 달성도 (40%)**: 시뮬레이션 목표(goal_list) 달성률
- **피드백 루프 (20%)**: 요약 및 추가 확인 여부

**산출 로직**:
```
skill_score = (0.4 × Flow점수) + (0.4 × Goal달성률×100) + (0.2 × Feedback점수)
```

**구현**: `score_metrics.py::calculate_skill_score()`

---

### 3️⃣ 공감도 (Empathy) - 가중치 15%

**목적**: 고객 감정에 적절히 공감했는가

**평가 기준**:
- **빈도 적정성 (40%)**: 공감 표현이 전체 발화의 3~10% 범위
- **맥락 적합성 (60%)**: 고객의 감정 표현 직후 공감 응답

**공감 표현 예시**:
- "불편을 드려 죄송합니다"
- "이해합니다", "그러셨군요"
- "걱정되시겠어요", "힘드셨겠어요"

**산출 로직**:
```
empathy_score = (빈도적정성 × 0.4) + (맥락적합성 × 0.6)
```

**구현**: `score_metrics.py::calculate_empathy_score()`

---

### 4️⃣ 명확성 (Clarity) - 가중치 15%

**목적**: 명확하고 이해하기 쉬운 언어를 사용했는가

**평가 기준**:
- **문장 구조 (40%)**: 간결하고 명료한 문장 (100자 이내 권장)
- **논리성 (30%)**: 논리적 연결어 사용, 구체적 정보 제공
- **용어 평이성 (30%)**: KB 권장용어 사용 비율

**KB 권장용어 예시**:
| 전문용어 | 권장용어 |
|---------|---------|
| 거치기간 | 이자만 내는 기간 |
| 언택트 | 비대면 |
| LTV | 담보인정비율 |
| 복리 | 이자에 이자가 붙는 방식 |

**산출 로직**:
```
clarity_score = (0.4×문장구조점수) + (0.3×논리성점수) + (0.3×용어평이성점수)
용어평이성 = (권장용어 사용수 / 전체용어기회수) × 100
```

**구현**: 
- `score_metrics.py::calculate_clarity_score()`
- 권장용어 사전: `backend/data/kb_recommended_terms.json`

---

### 5️⃣ 친절도 (Kindness) - 가중치 15%

**목적**: 고객 중심의 배려 있는 언어를 사용했는가

**평가 기준**:
- **긍정 표현**: "감사합니다", "도와드리겠습니다", "안내해 드리겠습니다"
- **부정 표현 감점**: "안 됩니다", "불가능합니다", "모르겠어요"

**산출 로직**:
```
kindness_score = (배려표현비율×100) - (부정/명령형표현비율×50)
```

**구현**: `score_metrics.py::calculate_kindness_score()`

---

### 6️⃣ 자신감 (Confidence) - 가중치 15%

**목적**: 불확실한 어투 없이 확신 있게 안내했는가

**평가 기준**:
- **단정형 어미**: "합니다", "됩니다", "가능합니다" (+2점/회)
- **모호 표현 감점**: "~같아요", "~일 수도", "확실하진 않지만"

**산출 로직**:
```
confidence_score = 100 - (모호표현비율 × 150) + (단정형어미수 × 2)
```

**구현**: `score_metrics.py::calculate_confidence_score()`

---

## 🏆 종합 점수

### 가중 평균
```
total_score = 0.2×knowledge + 0.2×skill + 0.15×empathy 
            + 0.15×clarity + 0.15×kindness + 0.15×confidence
```

### 등급 산정
| 점수 | 등급 |
|-----|------|
| 90점 이상 | A+ |
| 85~89점 | A |
| 80~84점 | B+ |
| 75~79점 | B |
| 70~74점 | C+ |
| 65~69점 | C |
| 64점 이하 | D |

---

## 🛠️ 구현 구조

### 파일 구조
```
backend/
├── app/
│   ├── models/
│   │   └── rag_simulation.py          # DB 모델 (6가지 지표)
│   ├── services/
│   │   ├── score_metrics.py           # 지표별 계산 로직
│   │   └── evaluation_service.py      # 통합 평가 서비스
│   └── routers/
│       └── rag_simulation.py          # API 엔드포인트
├── data/
│   └── kb_recommended_terms.json      # KB 권장용어 사전
└── scripts/
    └── migrate_evaluation_schema.py   # DB 마이그레이션
```

### 주요 클래스

#### 1. `ScoreMetrics` (score_metrics.py)
6가지 지표별 계산 함수를 제공하는 핵심 클래스

```python
from app.services.score_metrics import ScoreMetrics

config = {
    "weights": {
        "knowledge": 0.20,
        "skill": 0.20,
        "empathy": 0.15,
        "clarity": 0.15,
        "kindness": 0.15,
        "confidence": 0.15
    }
}

metrics = ScoreMetrics(config)

# 각 지표 계산
knowledge_score = metrics.calculate_knowledge_score(conversation, product_data, rag_context)
skill_score = metrics.calculate_skill_score(conversation, goal_list, achieved_goals)
empathy_score = metrics.calculate_empathy_score(conversation)
clarity_score = metrics.calculate_clarity_score(conversation)
kindness_score = metrics.calculate_kindness_score(conversation)
confidence_score = metrics.calculate_confidence_score(conversation)

# 종합 점수
total_result = metrics.calculate_total_score({
    "knowledge": knowledge_score,
    "skill": skill_score,
    "empathy": empathy_score,
    "clarity": clarity_score,
    "kindness": kindness_score,
    "confidence": confidence_score
})
```

#### 2. `EvaluationService` (evaluation_service.py)
통합 평가 서비스 (Rule-based + LLM 평가 병합 가능)

```python
from app.services.evaluation_service import EvaluationService

service = EvaluationService(session, config)

# 평가 실행
result = await service.evaluate_session(
    session_key="session_1_20241110_120000",
    use_llm=True,  # LLM 평가 사용 여부
    llm_model="gpt-4o"
)
```

**평가 방식**:
- `use_llm=False`: Rule-based 평가만 사용 (빠름, 비용 없음)
- `use_llm=True`: Rule-based (40%) + LLM (60%) 가중 평균 (정확함, OpenAI API 비용 발생)

---

## 🔌 API 사용법

### 1. 평가 실행

**POST** `/rag-simulation/evaluate`

**Request Body**:
```json
{
  "session_key": "session_1_20241110_120000",
  "use_llm": true,
  "llm_model": "gpt-4o"
}
```

**Response**:
```json
{
  "success": true,
  "message": "평가가 완료되었습니다.",
  "data": {
    "session_id": "session_1_20241110_120000",
    "evaluation_id": 42,
    "score": {
      "knowledge": {"point": 85, "reason": "상품 정보를 정확하게 설명했습니다."},
      "skill": {"point": 88, "reason": "응대 절차가 체계적이며 대부분의 목표 달성."},
      "empathy": {"point": 82, "reason": "고객 감정에 적절히 공감했으나 타이밍 개선 여지."},
      "clarity": {"point": 86, "reason": "명확하고 이해하기 쉬운 설명."},
      "kindness": {"point": 92, "reason": "매우 친절하고 배려 있는 응대."},
      "confidence": {"point": 80, "reason": "대체로 자신 있으나 일부 모호한 표현 있음."},
      "total": 86
    },
    "grade": "A",
    "detail_feedback": {
      "feedback_summary": "친절도는 우수하나, 공감 표현의 타이밍 개선 필요.",
      "knowledge_details": {...},
      "skill_details": {...}
    }
  }
}
```

### 2. 평가 결과 조회

**GET** `/rag-simulation/evaluation/{session_key}`

**Response**: (위와 동일)

---

## 🗄️ 데이터베이스 스키마

### `rag_simulation_evaluations` 테이블

| 컬럼 | 타입 | 설명 |
|-----|------|------|
| `id` | INTEGER | Primary Key |
| `session_id` | INTEGER | 세션 FK |
| `user_id` | INTEGER | 사용자 FK |
| `knowledge_point` | INTEGER | 지식 점수 (0-100) |
| `skill_point` | INTEGER | 기술 점수 (0-100) |
| `empathy_point` | INTEGER | 공감도 점수 (0-100) |
| `clarity_point` | INTEGER | 명확성 점수 (0-100) |
| `kindness_point` | INTEGER | 친절도 점수 (0-100) |
| `confidence_point` | INTEGER | 자신감 점수 (0-100) |
| `total_point` | INTEGER | 총점 (0-100) |
| `grade` | VARCHAR | 등급 (A+, A, B+, B, C+, C, D) |
| `knowledge_reason` | TEXT | 지식 평가 이유 |
| `skill_reason` | TEXT | 기술 평가 이유 |
| `empathy_reason` | TEXT | 공감도 평가 이유 |
| `clarity_reason` | TEXT | 명확성 평가 이유 |
| `kindness_reason` | TEXT | 친절도 평가 이유 |
| `confidence_reason` | TEXT | 자신감 평가 이유 |
| `feedback_summary` | TEXT | 피드백 요약 |
| `detail_json` | TEXT | 세부 정보 JSON |
| `created_at` | TIMESTAMP | 생성 시각 |

---

## 🚀 설치 및 실행

### 1. DB 마이그레이션
```bash
cd backend
python scripts/migrate_evaluation_schema.py
```

### 2. 애플리케이션 재시작
```bash
cd backend
uvicorn app.main:app --reload
```

### 3. API 테스트
```bash
# 평가 실행
curl -X POST "http://localhost:8000/rag-simulation/evaluate" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "session_key": "session_1_20241110_120000",
    "use_llm": true
  }'

# 결과 조회
curl -X GET "http://localhost:8000/rag-simulation/evaluation/session_1_20241110_120000" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

## 🎨 프론트엔드 시각화

### Radar Chart 예시 (Chart.js)

```javascript
const radarData = {
  labels: ['지식', '기술', '공감도', '명확성', '친절도', '자신감'],
  datasets: [{
    label: '평가 점수',
    data: [85, 88, 82, 86, 92, 80],
    backgroundColor: 'rgba(54, 162, 235, 0.2)',
    borderColor: 'rgb(54, 162, 235)',
    pointBackgroundColor: 'rgb(54, 162, 235)',
  }]
};

new Chart(ctx, {
  type: 'radar',
  data: radarData,
  options: {
    scales: {
      r: {
        beginAtZero: true,
        max: 100
      }
    }
  }
});
```

---

## ⚙️ 가중치 조정

평가 가중치는 `config` 파라미터로 자유롭게 조정 가능합니다.

```python
# 예: 지식과 기술을 더 중요하게
custom_config = {
    "weights": {
        "knowledge": 0.25,  # 25%
        "skill": 0.25,      # 25%
        "empathy": 0.10,    # 10%
        "clarity": 0.15,    # 15%
        "kindness": 0.15,   # 15%
        "confidence": 0.10  # 10%
    },
    "clarity_weights": {
        "structure": 0.5,
        "logic": 0.3,
        "terminology": 0.2
    }
}

service = EvaluationService(session, custom_config)
```

---

## 🧪 테스트

### Unit Test 예시
```python
import pytest
from app.services.score_metrics import ScoreMetrics

def test_knowledge_score():
    metrics = ScoreMetrics()
    conversation = [
        {"role": "employee", "text": "정기예금 금리는 연 3.5%입니다."},
        {"role": "customer", "text": "그럼 1년 만기로 하면 얼마죠?"}
    ]
    
    result = metrics.calculate_knowledge_score(conversation)
    
    assert result["score"] >= 0
    assert result["score"] <= 100
    assert "reason" in result
    assert "details" in result
```

---

## 📚 참고 자료

- **메모리**: [[memory:10037564]] - 실제 시험 결과 기반 피드백 생성
- **KB 권장용어 사전**: `backend/data/kb_recommended_terms.json`
- **학습 자료**: `backend/data/learning_materials_for_RAG.txt`
- **문제 은행**: `backend/data/bank_training_exam.json`

---

## 🔧 문제 해결

### 1. "OPENAI_API_KEY 환경 변수가 설정되지 않았습니다."
```bash
export OPENAI_API_KEY="sk-..."
```

### 2. DB 스키마 오류
```bash
# 마이그레이션 재실행
python scripts/migrate_evaluation_schema.py
```

### 3. KB 권장용어 사전 로드 실패
- 경로 확인: `backend/data/kb_recommended_terms.json`
- JSON 형식 검증

---

## 📝 TODO

- [ ] 실제 상품 데이터와 비교하는 Knowledge 평가 강화
- [ ] LLM 평가 프롬프트 고도화 (Few-shot Examples 추가)
- [ ] 평가 결과 히스토리 및 추세 분석 기능
- [ ] 사용자별 평가 리포트 자동 생성
- [ ] A/B 테스트를 통한 가중치 최적화

---

**개발 완료일**: 2024-11-10  
**버전**: 1.0.0  
**작성자**: AI Assistant (Cursor)

