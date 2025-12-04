# 문제별 정오답 확인 가능 여부

## 현재 상황

### ✅ 시험 (ExamScore) - **문제별 정오답 확인 가능**

**저장**: `ExamResult` 테이블
- 각 문제마다 정오답 정보가 저장됨

**확인 방법**: 
- API: `/api/exam/results/{exam_score_id}`
- 반환 정보:
  - `q_id`: 문제 ID
  - `user_answer`: 사용자 답변
  - `is_correct`: 정답/오답 여부
  - `learning_topic`: 학습 주제

**예시**:
```json
{
  "detailed_results": [
    {"q_id": "BO001", "user_answer": "1", "is_correct": true},
    {"q_id": "BO002", "user_answer": "3", "is_correct": false}
  ]
}
```

### ⚠️ 퀴즈 (QuizGenerationLog) - **데이터는 있지만 API에서 제공 안 됨**

**저장**: `QuizGenerationLog` 테이블
- `questions`: 문제 리스트 (각 문제에 q_id, answer 포함)
- `answers`: 사용자 답변 딕셔너리

**현재 문제**:
- 학습 이력 API는 카테고리별 통계만 제공
- 문제별로 "1번 문제 맞음, 2번 문제 틀림" 같은 상세 정보는 제공하지 않음

**확인하려면**:
- QuizGenerationLog를 직접 조회해야 함
- questions와 answers를 비교하여 정오답 계산 필요

## 답변: 몇 번 문제를 맞추고 틀렸는지 확인 가능?

### 시험의 경우
✅ **가능** - ExamResult에서 각 문제별로 확인 가능

### 퀴즈의 경우
⚠️ **부분 가능** - 데이터는 있지만 API에서 직접 제공하지 않음

### 학습 이력에서
❌ **현재 불가능** - 카테고리별 통계만 제공 (예: "금융영업 8/10")

## 개선 제안

학습 이력 API에 문제별 상세 정보를 추가하면:
- 각 문제의 q_id
- 문제 내용
- 사용자 답변
- 정답
- 정오답 여부

이 모든 정보를 한 번에 확인할 수 있습니다.
