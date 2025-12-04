# 학습 이력 필터 기능 점검 보고서

## 발견된 문제점

### 1. ⚠️ 기수 ID 불일치 (심각)

**문제:**
- 프론트엔드에서 하드코딩된 기수 ID (1, 2, 3, 4)를 사용
- 실제 DB의 기수 ID는 (183, 202, 203, 205)
- 필터가 제대로 작동하지 않음

**현재 상태:**
```typescript
// frontend/src/pages/Dashboard.tsx
<option value="1">2025년 1기</option>
<option value="2">2025년 2기</option>
<option value="3">2025년 3기</option>
<option value="4">2025년 4기</option>
```

**실제 DB:**
- ID: 183, 라벨: 2025년 1기
- ID: 202, 라벨: 2025년 2기
- ID: 203, 라벨: 2025년 3기
- ID: 205, 라벨: 2025년 4기

**해결 방법:**
1. 백엔드에 기수 목록 조회 API 추가
2. 프론트엔드에서 동적으로 기수 목록 로드

### 2. ✅ 모드 필터링 (정상 작동)

**현재 상태:**
- 프론트엔드: 'pre', 'midterm', 'final', 'random', 'custom'
- 백엔드: ExamType.BEGINNING → 'pre' 변환 정상
- 모드 필터링 로직 정상 작동

### 3. ⚠️ 퀴즈 로그 데이터 문제

**문제:**
- 퀴즈 로그에 시험 모드 값('final', 'midterm')이 존재
- 이는 데이터 생성 시 오류일 가능성

**데이터 분포:**
- random: 470개
- custom: 466개
- final: 473개 (이상)
- midterm: 434개 (이상)

**해결 방법:**
- 퀴즈 로그 생성 로직 점검 필요

## 권장 해결 방안

### 우선순위 1: 기수 필터 동적 로딩

1. **백엔드에 기수 목록 API 추가**
```python
@router.get("/admin/cohorts")
async def get_cohorts(session: Session = Depends(get_session)):
    cohorts = session.exec(select(TrainingCohort).order_by(TrainingCohort.cohort_date)).all()
    return [{"id": c.id, "label": c.label} for c in cohorts]
```

2. **프론트엔드에서 동적 로딩**
```typescript
const [cohorts, setCohorts] = useState([])
useEffect(() => {
  // 기수 목록 로드
  adminAPI.getCohorts().then(setCohorts)
}, [])
```

### 우선순위 2: 퀴즈 로그 데이터 정리

- 퀴즈 생성 로직에서 mode 값 검증 추가
- 기존 데이터 정리 스크립트 실행

