# 🔑 OpenAI API 키 사용 및 보관 최종 정리

## ✅ 질문에 대한 답변

### **Q1: API 키가 필요한 모든 부분에서 잘 사용되고 있는거야?**

**A: 네, 모든 부분에서 안전하게 사용되고 있습니다! ✅**

---

## 📊 API 키 사용 현황

### **1️⃣ `rag_simulation_service.py`** (메인 시뮬레이션) ✅

**초기화:**
```python
api_key = os.getenv("OPENAI_API_KEY")
if api_key:
    try:
        self.openai_client = openai.OpenAI(api_key=api_key)
    except:
        self.openai_client = None
else:
    self.openai_client = None  # API 키 없으면 None
```

**사용 메서드:**
| 메서드 | 기능 | 안전 체크 |
|--------|------|-----------|
| `_speech_to_text()` | STT (음성→텍스트) | ✅ `if not self.openai_client` |
| `_text_to_speech()` | TTS (텍스트→음성) | ✅ `if not self.openai_client` |
| `process_voice_interaction()` | 고객 응답 생성 | ✅ `if not self.openai_client` |
| `generate_comprehensive_feedback()` | 종합 평가 | ✅ `if not self.openai_client` |
| `analyze_goal_achievement()` | 목표 달성 분석 | ✅ `if not self.openai_client` |

---

### **2️⃣ `product_knowledge_service.py`** (제품 지식 검증) ✅

**초기화:**
```python
api_key = os.getenv("OPENAI_API_KEY")
if api_key:
    try:
        self.openai_client = OpenAI(api_key=api_key)
        self.use_llm = use_llm
    except:
        self.openai_client = None
        self.use_llm = False  # LLM 검증 비활성화
else:
    print("⚠️ OPENAI_API_KEY 없음 - LLM 검증 비활성화")
    self.openai_client = None
    self.use_llm = False
```

**사용 메서드:**
| 메서드 | 기능 | 안전 체크 |
|--------|------|-----------|
| `verify_fact_accuracy()` | 제품 정보 검증 (3단계) | ✅ `if should_use_llm and self.openai_client` |
| `_verify_with_llm()` | LLM 검증 (3단계) | ✅ 부모 메서드에서 체크됨 |

**3단계 하이브리드 검증:**
1. **Keyword Matching** → API 키 불필요 ✅
2. **Semantic Similarity** → API 키 불필요 ✅
3. **LLM Verification** → API 키 필요, 안전 체크 완료 ✅

---

### **3️⃣ `advanced_simulation_service.py`** (고급 시뮬레이션) ✅

**초기화:**
```python
api_key = os.getenv("OPENAI_API_KEY")
if api_key:
    try:
        self.openai_client = openai.OpenAI(api_key=api_key)
    except:
        self.openai_client = None
else:
    print("⚠️ OPENAI_API_KEY 없음 - STT/TTS/LLM 기능 비활성화")
    self.openai_client = None
```

**사용 메서드:**
| 메서드 | 기능 | 안전 체크 |
|--------|------|-----------|
| `_speech_to_text()` | STT | ✅ `if not self.openai_client` |
| `_text_to_speech()` | TTS | ✅ `if not self.openai_client` |
| `_generate_initial_customer_message()` | 초기 메시지 생성 | ✅ `if not self.openai_client` |
| `_generate_customer_response()` | 고객 응답 생성 | ✅ `if not self.openai_client` |
| `_evaluate_user_response()` | 응답 평가 | ✅ `if not self.openai_client` |

---

## 🎯 결론

### **모든 OpenAI API 사용 부분에 안전 체크 완료!**

✅ **초기화 체크** - API 키 없으면 `openai_client = None`
✅ **사용 전 체크** - 모든 메서드에서 `if not self.openai_client` 체크
✅ **예외 처리** - try-except로 오류 처리
✅ **Fallback 제공** - API 키 없어도 기본 기능 작동

---

## 🔐 Q2: API 키는 어디서 보관해?

**A: `.env` 파일에 안전하게 보관됩니다!**

---

## 📂 API 키 보관 위치

### **권장 방법: `.env` 파일** ✅

```
프로젝트 구조:
cant/
├── backend/
│   ├── .env                    ← API 키 여기 저장!
│   ├── .env.example            ← 템플릿 (Git에 포함)
│   ├── README_API_KEY.md       ← 상세 가이드
│   └── app/
│       └── services/
│           ├── rag_simulation_service.py
│           ├── product_knowledge_service.py
│           └── advanced_simulation_service.py
└── .gitignore                  ← .env 제외 설정
```

---

## 📝 `.env` 파일 내용

```bash
# backend/.env (실제 파일, Git에서 제외됨)
OPENAI_API_KEY=sk-proj-your-actual-key-here
DATABASE_URL=postgresql://mentoruser:mentorpass@localhost:5432/mentordb
SECRET_KEY=your-secret-key
```

---

## 🔒 보안 설정

### **1. `.gitignore` 확인** ✅

```bash
# .gitignore
.env
.env.local
.env.*.local
```

→ `.env` 파일은 **Git에 커밋되지 않음** ✅

### **2. 하드코딩 없음** ✅

❌ **나쁜 예:**
```python
# 절대 이렇게 하지 마세요!
OPENAI_API_KEY = "sk-proj-abc123..."  # Git에 노출됨!
```

✅ **좋은 예:**
```python
# 모든 서비스에서 이렇게 사용 중
api_key = os.getenv("OPENAI_API_KEY")  # .env에서 로드
```

### **3. API 키 로드 흐름**

```
1. 개발자가 .env 파일에 API 키 입력
   └─ backend/.env
      OPENAI_API_KEY=sk-proj-...

2. Python 실행 시 환경 변수로 로드
   └─ os.getenv("OPENAI_API_KEY")

3. 각 서비스에서 안전하게 사용
   └─ if api_key:
          self.openai_client = OpenAI(api_key=api_key)
      else:
          self.openai_client = None
```

---

## ⚙️ 설정 방법

### **Step 1: `.env` 파일 생성**

```bash
cd backend
cp .env.example .env
```

### **Step 2: API 키 발급**

1. https://platform.openai.com/api-keys 접속
2. "Create new secret key" 클릭
3. 키 복사 (한 번만 표시됨!)

### **Step 3: `.env` 파일에 추가**

```bash
# backend/.env 파일 편집
OPENAI_API_KEY=sk-proj-<복사한-키-붙여넣기>
```

### **Step 4: 확인**

```bash
cd backend
python scripts/check_api_key_setup.py
```

**출력 예시:**
```
✅ OPENAI_API_KEY 설정됨
✅ 올바른 형식 (sk-로 시작)
✅ .env 파일 존재
✅ .gitignore에 .env 포함됨 (보안 안전)
```

---

## 🧪 현재 상태

### **API 키 설정 상태**

```
❌ OPENAI_API_KEY 없음
✅ .env 파일 존재
✅ .env.example 파일 존재
✅ .gitignore에 .env 포함됨 (보안 안전)
```

### **서비스별 체크 상태**

| 서비스 | API 키 로드 | 안전 체크 | 상태 |
|--------|------------|-----------|------|
| `rag_simulation_service.py` | ✅ | ✅ | **완벽** |
| `product_knowledge_service.py` | ✅ | ✅ | **완벽** |
| `advanced_simulation_service.py` | ✅ | ✅ | **완벽** |

---

## 🎮 API 키 없이 사용 가능한 기능

| 기능 | API 키 없이 | 비고 |
|------|------------|------|
| 페르소나 조회 | ✅ | 완전 작동 |
| 상황 조회 | ✅ | 완전 작동 |
| 제품 정보 조회 | ✅ | 완전 작동 |
| Keyword Matching | ✅ | 완전 작동 |
| Semantic Similarity | ✅ | 완전 작동 |
| **STT (음성 인식)** | ❌ | API 키 필요 |
| **TTS (음성 합성)** | ❌ | API 키 필요 |
| **고객 응답 생성** | ❌ | API 키 필요 |
| **종합 평가** | ⚠️ | 기본 점수 반환 (70점) |
| **LLM 검증** | ⚠️ | Semantic까지만 사용 |

---

## 📚 추가 문서

- **상세 가이드:** `backend/README_API_KEY.md`
- **확인 스크립트:** `backend/scripts/check_api_key_setup.py`
- **템플릿:** `backend/.env.example`

---

## ✅ 최종 체크리스트

| 항목 | 상태 | 비고 |
|------|------|------|
| **모든 API 사용 부분 체크** | ✅ | 3개 서비스 모두 완료 |
| **안전한 초기화** | ✅ | API 키 없으면 None |
| **사용 전 체크** | ✅ | 모든 메서드에 추가 |
| **예외 처리** | ✅ | try-except 완비 |
| **Fallback 제공** | ✅ | 기본 동작 보장 |
| **.env 파일 보관** | ✅ | Git 제외 설정 |
| **.gitignore 설정** | ✅ | .env 포함됨 |
| **하드코딩 없음** | ✅ | os.getenv 사용 |
| **템플릿 제공** | ✅ | .env.example 생성 |
| **문서화** | ✅ | README 작성 |

---

## 🎉 결론

### **1. API 키 사용 - 완벽 ✅**
- 모든 OpenAI API 사용 부분에 안전 체크 완료
- API 키 없어도 기본 기능 작동
- 명확한 에러 메시지 제공

### **2. API 키 보관 - 안전 ✅**
- `.env` 파일에 보관 (Git 제외)
- 하드코딩 없음
- 보안 설정 완료

### **3. 개발자 경험 - 우수 ✅**
- `.env.example` 템플릿 제공
- 확인 스크립트 제공
- 상세 문서 제공

---

**작성일:** 2025-11-11
**상태:** 완료 ✅

