# 문제별 정오답 정보 확인 가능 여부 보고서

## 현재 상황

### ✅ 1. 시험 (ExamScore) - 문제별 정오답 정보 저장됨

**저장 위치**: `ExamResult` 테이블

**저장되는 정보**:
- `q_id`: 문제 ID (예: "BO001", "PK001")
- `user_answer`: 사용자가 선택한 답변
- `is_correct`: 정답/오답 여부 (boolean)
- `learning_topic`: 학습 주제
- `exam_score_id`: 어떤 시험인지 연결

**조회 방법**:
- API: `/api/exam/results/{exam_score_id}`
- 반환 형식:
  ```json
  {
    "exam_score": {
      "id": 1,
      "exam_name": "연수원 초기 평가",
      "total_score": 45.0,
      ...
    },
    "detailed_results": [
      {
        "q_id": "BO001",
        "user_answer": "1",
        "is_correct": true,
        "learning_topic": "예금상품의 이해"
      },
      {
        "q_id": "BO002",
        "user_answer": "3",
        "is_correct": false,
        "learning_topic": "예금상품의 이해"
      }
    ]
  }
  ```

**확인 가능 여부**: ✅ **가능**

### ✅ 2. 퀴즈 (QuizGenerationLog) - 문제별 정오답 정보 저장됨

**저장 위치**: `QuizGenerationLog` 테이블

**저장되는 정보**:
- `questions`: 문제 리스트 (JSON 배열)
  - 각 문제에 `q_id`, `answer` (정답) 포함
- `answers`: 사용자 답변 딕셔너리 (JSON)
  - 형식: `{"q_id": "user_answer", ...}`

**조회 방법**:
- 현재 학습 이력 API에서 `questions`와 `answers`를 비교하여 정오답 계산
- 하지만 문제별 상세 정보는 API에서 직접 반환하지 않음

**확인 가능 여부**: ⚠️ **부분 가능** (데이터는 있지만 API에서 상세 제공 안 함)

### ❌ 3. 학습 이력 API - 문제별 상세 정보 미제공

**현재 제공되는 정보**:
- 카테고리별 통계만 제공 (예: 금융영업 8/10, 하경은행 7/10)
- 문제별로 몇 번 문제를 맞췄는지/틀렸는지는 제공하지 않음

**API**: `/api/admin/learning-history`

**반환 형식**:
```json
{
  "history": [
    {
      "id": "quiz_123",
      "mode": "random",
      "score": 85.5,
      "category_stats": {
        "금융영업": {"correct": 8, "total": 10},
        "하경은행": {"correct": 7, "total": 10}
      }
      // 문제별 상세 정보 없음 ❌
    }
  ]
}
```

## 개선 방안

### 제안 1: 학습 이력 API에 문제별 상세 정보 추가

**학습 이력 항목에 `question_details` 필드 추가**:

```json
{
  "id": "quiz_123",
  "mode": "random",
  "score": 85.5,
  "category_stats": {...},
  "question_details": [
    {
      "q_id": "BO001",
      "question": "문제 내용...",
      "user_answer": "1",
      "correct_answer": "1",
      "is_correct": true,
      "category": "금융영업"
    },
    {
      "q_id": "BO002",
      "question": "문제 내용...",
      "user_answer": "3",
      "correct_answer": "1",
      "is_correct": false,
      "category": "금융영업"
    }
  ]
}
```

### 제안 2: 별도 API 엔드포인트 추가

**새로운 API 엔드포인트**:
- `/api/admin/learning-history/{history_id}/questions` - 특정 학습 이력의 문제별 상세 정보

## 현재 가능한 확인 방법

### 시험의 경우
✅ **완전히 가능**
1. 학습 이력에서 시험 점수 확인
2. `exam_score_id`를 이용하여 `/api/exam/results/{exam_score_id}` 호출
3. `detailed_results`에서 각 문제별 정오답 확인

### 퀴즈의 경우
⚠️ **부분 가능** (API 개선 필요)
1. 학습 이력에서 퀴즈 로그 확인
2. QuizGenerationLog에서 `questions`와 `answers` 직접 조회 필요
3. 현재는 프론트엔드에서 직접 계산해야 함

## 요약

| 항목 | 문제별 정오답 확인 가능 여부 | API 제공 여부 |
|------|---------------------------|--------------|
| 시험 (ExamScore) | ✅ 가능 | ✅ `/api/exam/results/{exam_score_id}` |
| 퀴즈 (QuizGenerationLog) | ⚠️ 데이터는 있으나 API 미제공 | ❌ 학습 이력 API에 없음 |
| 학습 이력 API | ❌ 카테고리별 통계만 제공 | ❌ 문제별 상세 정보 없음 |

## 권장 사항

1. **즉시 가능**: 시험의 경우 이미 문제별 정오답 확인 가능
2. **개선 필요**: 퀴즈의 경우 학습 이력 API에 문제별 상세 정보 추가
3. **프론트엔드**: 문제별 상세 정보를 표시할 수 있도록 UI 개선
