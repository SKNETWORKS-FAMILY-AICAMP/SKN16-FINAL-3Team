# 근본 원인 분석 결과

## 문제 상황

사용자가 보고한 대시보드 분포:
- 1기: 4명
- 2기: 5명  
- 3기: 9명
- 4기: 35명

## 근본 원인

### 1. 백엔드 cohort 집계 방식

백엔드 `list_records` 메서드에서 `cohorts` 배열을 구성할 때:

```python
cohort_query = (
    select(
        TrainingCohort.cohort_date,
        TrainingCohort.label,
        func.count(TrainingCenterRecord.id).label("count"),
    )
    .join(
        TrainingCenterRecord,
        TrainingCenterRecord.cohort_id == TrainingCohort.id,
        isouter=True,
    )
    .group_by(...)
)
```

**문제점:**
- `TrainingCenterRecord.cohort_id`를 기준으로 집계
- 멘토의 경우 `cohort_id`는 원래 입사년도 기반 cohort를 가리킴
- 멘토가 여러 기수의 멘티를 맡아도 `cohort_id`는 변하지 않음

**결과:**
- 2025년 4기: 15명 (cohort_id=186인 멘토)
- 2025년 3기: 10명 (cohort_id=185인 멘토)
- 2025년 2기: 13명 (cohort_id=184인 멘토)
- 2025년 1기: 15명 (cohort_id=183인 멘토)

### 2. 프론트엔드 표시 방식

프론트엔드에서:
1. `cohortOptions`를 백엔드에서 받음 (각 cohort별 `count` 포함)
2. `records` 배열도 받음 (각 record는 `_serialize_record`를 통해 변환)
3. 각 record의 `cohort_label`은 `_serialize_record`에서 동적으로 변경됨

**문제점:**
- `_serialize_record`가 멘토의 경우 `MentorMenteeRelation`을 확인하여 가장 최근 기수를 `cohort_label`로 표시
- 멘토가 여러 기수를 담당하면 가장 최근 기수(기수 인덱스가 큰 것)로만 표시됨
- 따라서 1기 멘토 15명이 4기도 담당하면 모두 4기로만 표시됨

**실제 표시 결과:**
- 프론트엔드에서 `cohort_label` 기준으로 필터링/집계하면:
  - 1기: 0명 (1기 멘토가 4기로만 표시됨)
  - 2기: 15명
  - 3기: 15명
  - 4기: 15명

### 3. 사용자가 본 분포

사용자가 보고한 "1기 4명, 2기 5명, 3기 9명, 4기 35명"은:
- 아마도 대시보드에서 `cohortOptions`의 `count`를 보고 있는 것 같습니다
- 하지만 실제로는 각 기수에 배정된 멘토 수와 다를 수 있습니다
- 또는 프론트엔드에서 실제로 필터링했을 때의 결과일 수 있습니다

## 해결 방법

1. **백엔드 cohort 집계 로직 수정**: `_serialize_record`를 통해 변환된 `cohort_label` 기준으로 집계
2. **멘토를 각 기수별로 독립적으로 배정**: 멘토가 여러 기수를 담당하지 않도록
3. **프론트엔드에서 동적 집계**: `records`를 받아서 `cohort_label` 기준으로 집계

가장 근본적인 해결책은: **백엔드에서 `_serialize_record`를 통해 변환된 데이터를 기준으로 집계하도록 수정**

