# 🔍 RAG 시뮬레이션 평가 검증 가이드

## 📌 개요

RAG 기반 시뮬레이션의 평가 결과를 검증하는 다양한 방법과 도구를 제공합니다.

---

## 🎯 검증 방법론

### 1. **일관성 검증 (Consistency Validation)**

**목적**: 같은 대화에 대한 반복 평가 시 일관된 결과가 나오는지 확인

**방법**:
- 동일한 세션에 대해 여러 번 평가 실행
- 점수 분포의 표준편차 및 변동계수(CV) 계산
- 허용 기준: 변동계수 < 20%

**장점**:
- 평가 시스템의 안정성 확인
- 평가자의 일관성 측정

**사용 스크립트**: `validate_evaluation_quality.py` - `validate_consistency()`

---

### 2. **제품 지식 정확도 검증 (Knowledge Accuracy Validation)**

**목적**: 평가 시스템의 지식 점수가 실제 제품 지식 정확도와 일치하는지 확인

**방법**:
- `ProductKnowledgeService`를 사용하여 직원 발화 검증
- 평가 결과의 지식 점수와 검증 정확도 비교
- 상관관계 분석

**장점**:
- 객관적인 지식 검증 기준 제공
- 평가 시스템의 정확성 검증

**사용 스크립트**: `validate_evaluation_quality.py` - `validate_knowledge_accuracy()`

---

### 3. **평가 점수 분포 분석 (Score Distribution Analysis)**

**목적**: 전체 평가 데이터의 점수 분포가 합리적인지 확인

**방법**:
- 모든 평가 데이터의 통계 분석
- 평균, 중앙값, 표준편차, 사분위수 계산
- 점수 구간별 분포 확인
- 비정상적인 분포 패턴 감지 (예: 모든 점수가 90점대)

**장점**:
- 평가 시스템의 편향성 감지
- 데이터 품질 문제 발견

**사용 스크립트**: `validate_evaluation_quality.py` - `analyze_score_distribution()`

---

### 4. **평가 기준 준수 검증 (Criteria Compliance Validation)**

**목적**: 평가 결과가 정의된 평가 기준을 준수하는지 확인

**검증 항목**:
- 점수 범위: 지식(0-40), 기술(0-30), 태도(0-30), 총점(0-100)
- 점수 합계: 지식 + 기술 + 태도 = 총점
- 필수 필드 존재: 강점, 개선점, 추천 학습 등

**장점**:
- 데이터 무결성 보장
- 시스템 버그 조기 발견

**사용 스크립트**: `validate_evaluation_quality.py` - `validate_evaluation_criteria()`

---

### 5. **Ground Truth 비교 검증 (Ground Truth Validation)**

**목적**: 사전에 정의된 기준 답안과 평가 결과를 비교

**방법**:
1. 전문 평가자가 작성한 기준 답안(Ground Truth) 준비
2. 실제 평가 결과와 비교
3. 허용 오차 내 일치 여부 확인

**장점**:
- 평가 시스템의 정확도 정량화
- 개선 방향 제시

**사용 스크립트**: `validate_with_ground_truth.py`

**Ground Truth 파일 형식**:
```json
{
  "description": "RAG 시뮬레이션 평가 Ground Truth 데이터",
  "version": "1.0",
  "evaluations": [
    {
      "session_key": "session_example_1",
      "expected_scores": {
        "knowledge": 35,
        "skill": 25,
        "attitude": 28,
        "total": 88
      },
      "expected_strengths": [
        "친절한 응대",
        "정확한 정보 제공"
      ],
      "expected_improvements": [
        "고객 동의 확인 부족",
        "속도 조절 필요"
      ],
      "tolerance": {
        "knowledge": 5,
        "skill": 3,
        "attitude": 3,
        "total": 10
      }
    }
  ]
}
```

---

### 6. **인간 평가자 간 일관성 검증 (Inter-Annotator Agreement)**

**목적**: 여러 인간 평가자가 동일한 대화를 평가할 때 일치하는 정도 측정

**방법**:
- Cohen's Kappa 또는 Fleiss' Kappa 계산
- 여러 평가자 간 점수 상관관계 분석

**장점**:
- 평가 기준의 명확성 확인
- 평가 시스템의 신뢰도 측정

**구현 필요**: 현재는 미구현, 필요 시 추가

---

### 7. **A/B 테스트 (A/B Testing)**

**목적**: 평가 프롬프트나 기준 변경 시 효과 측정

**방법**:
- 기존 평가 시스템과 새로운 평가 시스템 비교
- 동일한 데이터셋에 대해 두 시스템 평가 실행
- 사용자 피드백과 비교

**장점**:
- 평가 시스템 개선 효과 정량화
- 점진적 개선 가능

---

## 🛠️ 사용 방법

### 1. 일관성 검증 실행

```bash
cd backend
python scripts/validate_evaluation_quality.py
```

또는 Python 코드에서:

```python
from app.database import get_db
from scripts.validate_evaluation_quality import EvaluationValidator

db_session = next(get_db())
validator = EvaluationValidator(db_session)

# 일관성 검증
result = validator.validate_consistency("session_key_here")
```

### 2. 제품 지식 정확도 검증 실행

```python
# 제품 지식 정확도 검증
result = validator.validate_knowledge_accuracy("session_key_here")
```

### 3. 평가 점수 분포 분석 실행

```python
# 점수 분포 분석
result = validator.analyze_score_distribution(limit=100)
```

### 4. Ground Truth 비교 검증 실행

```bash
# Ground Truth 파일 생성 (처음 실행 시)
python scripts/validate_with_ground_truth.py

# Ground Truth 비교 검증
# 코드에서 실행:
from scripts.validate_with_ground_truth import GroundTruthValidator

validator = GroundTruthValidator(db_session)
result = validator.validate_against_ground_truth("session_key_here")

# 배치 검증
batch_result = validator.batch_validate()
```

---

## 📊 검증 결과 해석

### 일관성 검증 결과

- **변동계수 < 10%**: 매우 일관적 ✅
- **변동계수 10-20%**: 일관적 ✅
- **변동계수 > 20%**: 불일관적 ⚠️

**개선 방법**:
- 평가 프롬프트 개선
- temperature 파라미터 조정 (더 낮게 설정)
- 평가 기준 명확화

### 제품 지식 정확도 검증 결과

- **차이 < 10%p**: 높은 상관관계 ✅
- **차이 10-20%p**: 중간 상관관계 ⚠️
- **차이 > 20%p**: 낮은 상관관계 ❌

**개선 방법**:
- 지식 평가 기준 재검토
- ProductKnowledgeService와 평가 프롬프트 정렬

### 점수 분포 분석 결과

**정상적인 분포**:
- 점수가 다양한 범위에 분포
- 정규분포 또는 자연스러운 분포

**비정상적인 분포**:
- 대부분 점수가 90점대 (과도한 관대함)
- 대부분 점수가 30점대 (과도한 엄격함)
- 극단적인 점수만 존재

**개선 방법**:
- 평가 기준 조정
- 점수 스케일 재조정
- 평가자 교육

---

## 🔄 검증 프로세스

### 1. 정기 검증 (주간/월간)

```bash
# 점수 분포 분석 (자동화 가능)
python scripts/validate_evaluation_quality.py

# 결과를 파일로 저장
python scripts/validate_evaluation_quality.py > validation_report_$(date +%Y%m%d).txt
```

### 2. 새로운 평가 시스템 배포 시

1. Ground Truth 데이터 준비
2. 배치 검증 실행
3. 정확도 기준 확인 (예: 80% 이상)
4. 배포 승인/거부 결정

### 3. 평가 기준 변경 시

1. 변경 전후 비교 평가 실행
2. 일관성 검증
3. 사용자 피드백 수집
4. 점진적 롤아웃

---

## 📈 검증 메트릭 요약

| 검증 방법 | 메트릭 | 목표 값 | 중요도 |
|----------|--------|---------|--------|
| 일관성 검증 | 변동계수(CV) | < 20% | 높음 |
| 지식 정확도 검증 | 정확도 차이 | < 10%p | 높음 |
| 점수 분포 분석 | 점수 범위 분포 | 균등 분포 | 중간 |
| 기준 준수 검증 | 준수율 | 100% | 높음 |
| Ground Truth 검증 | 일치율 | > 80% | 높음 |

---

## ⚠️ 주의사항

1. **일관성 검증은 비용이 많이 듭니다**
   - 같은 세션에 대해 여러 번 평가를 실행해야 함
   - GPT-4 API 비용 발생
   - 필요 시 샘플링 사용

2. **Ground Truth 데이터 준비 필요**
   - 전문 평가자의 시간 투자 필요
   - 주기적인 업데이트 필요
   - 충분한 샘플 수 확보 (최소 20-30개)

3. **검증 결과는 참고용**
   - 절대적인 기준이 아닌 상대적인 지표
   - 사용자 피드백과 함께 종합 판단
   - 점진적 개선 접근

---

## 🔗 관련 파일

- `backend/scripts/validate_evaluation_quality.py`: 주요 검증 스크립트
- `backend/scripts/validate_with_ground_truth.py`: Ground Truth 비교 검증
- `backend/scripts/evaluation_ground_truth.json`: Ground Truth 데이터 (생성 필요)
- `backend/app/services/product_knowledge_service.py`: 제품 지식 검증 서비스

---

## 📝 추가 개선 사항

- [ ] 자동화된 검증 리포트 생성
- [ ] 검증 결과 대시보드
- [ ] 알림 시스템 (검증 실패 시)
- [ ] 인간 평가자 간 일관성 검증 구현
- [ ] 평가 시스템 버전 관리 및 비교 기능






