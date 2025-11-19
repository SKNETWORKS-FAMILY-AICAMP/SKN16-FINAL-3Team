# 🎤 STT 모델 성능 평가 가이드

이 문서는 Speech-to-Text(STT) 모델의 성능을 평가하는 방법을 안내합니다.

## 📋 목차

1. [평가 메트릭 소개](#평가-메트릭-소개)
2. [평가 준비](#평가-준비)
3. [평가 실행](#평가-실행)
4. [결과 해석](#결과-해석)
5. [개선 방안](#개선-방안)

---

## 📊 평가 메트릭 소개

### 1. WER (Word Error Rate, 단어 오류율)
- **정의**: 단어 수준에서의 오류율 (띄어쓰기 기준으로 단어 분리)
- **계산**: `(치환 + 삭제 + 삽입) / 총 단어 수`
- **해석**: 낮을수록 좋음 (0% = 완벽)
- **예시**:
  - 정답: "예금 상품 문의 드립니다" (4개 단어)
  - 인식: "예금 상품 문외 드립니다" (4개 단어)
  - WER: 1/4 = 25% (1개 단어 치환: "문의" → "문외")

### 2. CER (Character Error Rate, 문자 오류율)
- **정의**: 문자 수준에서의 오류율
- **계산**: `(치환 + 삭제 + 삽입) / 총 문자 수`
- **해석**: WER보다 세밀한 측정, 낮을수록 좋음
- **예시**:
  - 정답: "대출금리"
  - 인식: "대충금리"
  - CER: 1/4 = 25% (1개 문자 오류)

### 3. Accuracy (완전 일치율)
- **정의**: 정답과 100% 일치한 샘플의 비율
- **해석**: 높을수록 좋음 (100% = 모든 샘플 완벽 인식)

### 4. Latency (처리 시간)
- **정의**: STT 처리에 걸린 시간 (초)
- **해석**: 짧을수록 좋음 (실시간 응답 품질)

---

## 🛠️ 평가 준비

### 1단계: 테스트 데이터셋 준비

평가를 위해서는 **음성 파일**과 **정답 텍스트**가 필요합니다.

#### 1.1 샘플 템플릿 생성

```bash
python backend/scripts/evaluate_stt_performance.py --create-sample
```

이 명령어는 `stt_test_data.json` 파일을 생성합니다:

```json
[
  {
    "audio_path": "path/to/sample1.webm",
    "ground_truth": "예금 상품에 대해 문의드립니다"
  },
  {
    "audio_path": "path/to/sample2.webm",
    "ground_truth": "대출 금리가 어떻게 되나요"
  }
]
```

#### 1.2 테스트 데이터 수집

**방법 1: 기존 녹음 파일 활용**
```bash
# uploads/recordings/ 폴더의 실제 사용자 녹음 파일 활용
uploads/recordings/2025-11-10/xxxxx.webm
```

**방법 2: 직접 녹음**
- 프론트엔드 시뮬레이션 페이지에서 녹음
- 또는 외부 도구로 음성 파일 생성

**방법 3: 다양한 시나리오 구성**
- 짧은 발화 (1-2단어)
- 중간 발화 (5-10단어)
- 긴 발화 (20단어 이상)
- 전문 용어 포함 (예: "주택담보대출", "예금자보호법")
- 배경 소음 포함
- 다양한 화자 (남/여, 연령대별)

#### 1.3 Ground Truth 작성

정답 텍스트는 **음성 파일의 정확한 내용**을 작성합니다.

**작성 원칙:**
- 띄어쓰기 정확히
- 구두점 불필요 (STT는 일반적으로 구두점 미제공)
- 음성에 정확히 맞춰 작성

**예시:**
```json
{
  "audio_path": "uploads/recordings/2025-11-10/sample1.webm",
  "ground_truth": "안녕하세요 주택담보대출 상품에 대해 문의드리고 싶습니다"
}
```

### 2단계: 환경 변수 확인

`.env` 파일에 OpenAI API 키가 설정되어 있는지 확인:

```bash
OPENAI_API_KEY=sk-...
```

---

## 🚀 평가 실행

### 기본 평가 (Whisper-1만)

```bash
python backend/scripts/evaluate_stt_performance.py \
  --test-data stt_test_data.json
```

### 다중 모델 비교 평가

```bash
python backend/scripts/evaluate_stt_performance.py \
  --test-data stt_test_data.json \
  --models whisper-1 gpt-4o-transcribe
```

### 결과 저장 경로 지정

```bash
python backend/scripts/evaluate_stt_performance.py \
  --test-data stt_test_data.json \
  --output my_evaluation_results.json
```

---

## 📈 결과 해석

### 콘솔 출력 예시

```
==========================================================
📊 whisper-1 모델 평가 시작
==========================================================

[1/5] 처리 중: sample1.webm
  정답: 예금 상품에 대해 문의드립니다
  인식: 예금 상품에 대해 문의드립니다
  WER: 0.00%, CER: 0.00%, 처리시간: 1.23초

[2/5] 처리 중: sample2.webm
  정답: 대출 금리가 어떻게 되나요
  인식: 대출 금리가 어떻게 되나요
  WER: 0.00%, CER: 0.00%, 처리시간: 1.45초

...

==========================================================
📈 평가 결과 요약 - whisper-1
==========================================================
총 샘플 수:       5개
평균 WER:         5.20%
평균 CER:         2.15%
완전 일치율:      80.00% (4/5)
평균 처리 시간:   1.34초
==========================================================
```

### 성능 기준 (참고)

| 메트릭 | 우수 | 양호 | 보통 | 개선 필요 |
|--------|------|------|------|-----------|
| WER    | <5%  | 5-10% | 10-20% | >20% |
| CER    | <3%  | 3-7%  | 7-15% | >15% |
| 정확도 | >90% | 80-90% | 60-80% | <60% |
| 처리시간 | <1초 | 1-2초 | 2-3초 | >3초 |

### 모델 비교 출력 예시

```
==========================================================
🔍 모델 성능 비교
==========================================================

모델                      WER        CER        정확도      처리시간
----------------------------------------------------------------------
whisper-1                5.20%      2.15%      80.00%     1.34초
gpt-4o-transcribe        3.10%      1.42%      90.00%     2.87초
```

### 결과 JSON 파일

`stt_evaluation_results.json` 파일에 상세한 결과가 저장됩니다:

```json
{
  "evaluation_date": "2025-11-11T10:30:00",
  "summaries": [
    {
      "model": "whisper-1",
      "total_samples": 5,
      "avg_wer": 0.052,
      "avg_cer": 0.0215,
      "accuracy": 0.8,
      "exact_matches": 4,
      "avg_latency": 1.34,
      "results": [
        {
          "audio_path": "...",
          "ground_truth": "...",
          "hypothesis": "...",
          "wer": 0.0,
          "cer": 0.0,
          "exact_match": true,
          "latency": 1.23
        }
      ]
    }
  ]
}
```

---

## 🔧 개선 방안

### 1. WER/CER이 높은 경우

**원인 분석:**
- 음성 품질이 낮음 (배경 소음, 잡음)
- 전문 용어나 고유명사가 많음
- 발음이 불명확함

**개선 방법:**
- 음성 전처리 (노이즈 제거, 음량 정규화)
- 하이브리드 접근 (현재 구현처럼 whisper + gpt-4o-transcribe)
- 은행 도메인 특화 용어 사전 활용 (`banking_normalizer.py`)

### 2. 특정 단어가 자주 틀리는 경우

**개선 방법:**
- `banking_normalizer.py`에 용어 추가:
  ```python
  {
      "pattern": r"주택담보대출|주담대",
      "corrections": ["주택담보대출"]
  }
  ```

### 3. 처리 시간이 느린 경우

**개선 방법:**
- 오디오 파일 압축 (비트레이트 낮추기)
- 불필요한 2단계 처리 최소화 (품질 임계값 조정)
- 배치 처리 (여러 파일 동시 처리)

### 4. 비용 최적화

현재 하이브리드 방식의 비용:
- Whisper-1: 저렴 (~$0.006/분)
- gpt-4o-transcribe: 상대적으로 비싸지만 품질 높음

**최적화 전략:**
- 품질 임계값 조정 (2단계 처리 빈도 줄이기)
- 짧은 발화는 whisper-1만 사용
- 긴 발화나 중요한 대화만 gpt-4o-transcribe 사용

---

## 📌 실전 예시: 단계별 가이드

### 1️⃣ 테스트 데이터 준비

```bash
# 1. 샘플 파일 생성
python backend/scripts/evaluate_stt_performance.py --create-sample

# 2. stt_test_data.json 파일 수정 (실제 음성 파일 경로와 정답 입력)
```

**stt_test_data.json 예시:**
```json
[
  {
    "audio_path": "uploads/recordings/2025-11-10/test_deposit.webm",
    "ground_truth": "정기예금 상품 금리가 어떻게 되나요"
  },
  {
    "audio_path": "uploads/recordings/2025-11-10/test_loan.webm",
    "ground_truth": "주택담보대출 신청하려고 하는데 필요한 서류가 뭔가요"
  },
  {
    "audio_path": "uploads/recordings/2025-11-10/test_card.webm",
    "ground_truth": "신용카드 발급받고 싶습니다"
  }
]
```

### 2️⃣ 평가 실행

```bash
# Whisper-1과 gpt-4o-transcribe 비교
python backend/scripts/evaluate_stt_performance.py \
  --test-data stt_test_data.json \
  --models whisper-1 gpt-4o-transcribe \
  --output evaluation_2025_11_11.json
```

### 3️⃣ 결과 분석

결과 파일(`evaluation_2025_11_11.json`)을 열어서:
1. 평균 WER/CER 확인
2. 어떤 샘플에서 오류가 많이 발생했는지 확인
3. 두 모델의 성능 차이 비교

### 4️⃣ 개선 작업

오류가 많은 단어를 찾아서 `banking_normalizer.py`에 추가하거나
하이브리드 STT 로직을 조정합니다.

---

## 💡 추가 팁

### 테스트 데이터 다양화
- **음성 품질 다양화**: 깨끗한 환경 vs 소음 환경
- **발화 길이 다양화**: 짧은 문장 vs 긴 설명
- **전문 용어 포함**: 은행 업무 관련 용어 포함
- **화자 다양화**: 다양한 연령대, 성별

### 주기적 평가
- 모델 업데이트 시 재평가
- 새로운 도메인 용어 추가 후 재평가
- 사용자 피드백 기반 테스트 케이스 추가

### A/B 테스트
- 프로덕션 환경에서 일부 사용자에게 새 모델 적용
- 사용자 만족도와 메트릭 비교

---

## 🔗 관련 파일

- **평가 스크립트**: `backend/scripts/evaluate_stt_performance.py`
- **STT 구현**: `backend/app/services/rag_simulation_service.py` (Line 765-836)
- **정규화 로직**: `backend/app/services/banking_normalizer.py`
- **라우터**: `backend/app/routers/rag_simulation.py`

---

## ❓ FAQ

### Q1: 테스트 데이터는 몇 개가 적당한가요?
**A**: 최소 20-30개 이상을 권장합니다. 다양한 시나리오를 포함하면 더 신뢰성 있는 결과를 얻을 수 있습니다.

### Q2: WER과 CER 중 어떤 메트릭을 중요하게 봐야 하나요?
**A**: 
- **한국어의 경우 CER**이 더 유용할 수 있습니다 (단어 분리가 명확하지 않은 경우)
- **영어의 경우 WER**이 표준입니다.
- **둘 다** 함께 보는 것을 권장합니다.

### Q3: gpt-4o-transcribe는 언제 사용하나요?
**A**: 현재 하이브리드 로직:
1. 먼저 whisper-1로 인식
2. 품질이 낮으면 (교정 2개 이상, 너무 짧은 텍스트 등) gpt-4o-transcribe로 재인식

### Q4: 비용이 얼마나 드나요?
**A**: 
- Whisper-1: ~$0.006/분
- gpt-4o-transcribe: 가격은 OpenAI 공식 문서 참조
- 예산에 맞춰 테스트 샘플 수를 조절하세요.

### Q5: 평가 결과를 시각화할 수 있나요?
**A**: 현재는 JSON 결과 파일을 제공합니다. 추가로 시각화가 필요하면:
- pandas + matplotlib로 그래프 생성
- 대시보드 도구 활용 (Grafana, Streamlit 등)

---

## 📞 문의

평가 과정에서 문제가 발생하거나 추가 기능이 필요하면 개발팀에 문의하세요.

**Happy Testing! 🎉**

