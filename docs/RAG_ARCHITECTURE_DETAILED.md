# 🏦 시뮬레이션 모듈 RAG 아키텍처 상세 설명

> **은행 신입사원 온보딩 플랫폼 - 시뮬레이션 파트 RAG 구조**  
> 처음 보는 사람도 이해할 수 있도록 작성된 기술 문서

---

## 📋 목차

1. [RAG란 무엇인가?](#1-rag란-무엇인가)
2. [전체 아키텍처 개요](#2-전체-아키텍처-개요)
3. [Ingestion Pipeline (사전 구축)](#3-ingestion-pipeline-사전-구축)
4. [Query & Retrieval Pipeline (실시간 질의)](#4-query--retrieval-pipeline-실시간-질의)
5. [데이터 저장 구조](#5-데이터-저장-구조)
6. [핵심 컴포넌트 상세](#6-핵심-컴포넌트-상세)
7. [흐름 예시](#7-흐름-예시)

---

## 1. RAG란 무엇인가?

### 개념
**RAG (Retrieval-Augmented Generation)** 은 LLM(대규모 언어 모델)의 응답 품질을 높이기 위해 
**외부 지식 베이스에서 관련 정보를 검색**하여 프롬프트에 포함시키는 기술입니다.

### 왜 필요한가?
```
❌ 순수 LLM만 사용할 경우:
   - "정기예금 금리가 얼마인가요?" → "일반적으로 2~3% 정도입니다" (부정확)

✅ RAG를 사용할 경우:
   - 벡터 DB에서 "정기예금 금리" 관련 청크 검색
   - 검색된 실제 상품 정보를 프롬프트에 포함
   - "하경은행 정기예금 12개월 기준 연 2.15%입니다" (정확)
```

### 이 프로젝트에서의 역할
- **AI 고객 역할 수행**: 시뮬레이션에서 AI가 실제 은행 상품 정보를 바탕으로 질문
- **직원 응답 평가**: 직원(신입사원)이 말한 내용이 실제 상품 정보와 맞는지 검증
- **정확한 피드백 제공**: RAG로 검색된 정답과 비교하여 구체적인 피드백 생성

---

## 2. 전체 아키텍처 개요

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         📥 Ingestion Pipeline (사전 구축)                    │
│                              [서버 시작 시 / 스크립트 실행]                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   📄 JSONL 파일                🔪 사전 청킹됨              🔢 임베딩 생성       │
│   (상품 정보)                   (구조+크기 기반)            (ada-002)          │
│                                                                             │
│   DEP-TIM.jsonl  ──────────▶  청크 1: 상품 개요     ──────▶  [0.12, -0.34,  │
│   LON-MTG.jsonl              청크 2: 가입 조건              0.56, ...]      │
│   CRD-CRE.jsonl              청크 3: 금리 정보              1536차원         │
│   ...                        청크 4: 우대금리                               │
│                              ...                                            │
│                                                                             │
│                                        │                                    │
│                                        ▼                                    │
│                          ┌─────────────────────────────┐                    │
│                          │  💾 PostgreSQL + pgvector   │                    │
│                          │     product_chunks 테이블   │                    │
│                          └─────────────────────────────┘                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

                                        │
                                        │ 인덱싱 완료
                                        ▼

┌─────────────────────────────────────────────────────────────────────────────┐
│                    🔍 Query & Retrieval Pipeline (실시간 질의)               │
│                           [시뮬레이션 대화 중 실행]                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  👤 신입사원              🎤 STT               🏦 정규화                      │
│  음성 입력   ──────────▶  Whisper  ──────────▶  BankingNormalizer            │
│                          음성→텍스트            은행 용어 교정                 │
│                                                                             │
│                                        │                                    │
│                                        ▼                                    │
│                                                                             │
│                          ┌─────────────────────────────┐                    │
│                          │  🔢 Query Embedding 생성    │                    │
│                          │     (ada-002, 1536차원)     │                    │
│                          └─────────────────────────────┘                    │
│                                        │                                    │
│                                        ▼                                    │
│                                                                             │
│    ┌──────────────────────────────────────────────────────────────────┐     │
│    │                    🎯 Vector Search (pgvector)                   │     │
│    │                                                                  │     │
│    │   SELECT * FROM product_chunks                                   │     │
│    │   WHERE 1 - (embedding <=> query_vector) > 0.45  -- 유사도 임계값  │     │
│    │   ORDER BY embedding <=> query_vector                            │     │
│    │   LIMIT 5;                                                       │     │
│    │                                                                  │     │
│    └──────────────────────────────────────────────────────────────────┘     │
│                                        │                                    │
│                                        ▼                                    │
│                                                                             │
│                          ┌─────────────────────────────┐                    │
│                          │  📋 결과 필터링 & 재순위화   │                    │
│                          │  - product_code 필터        │                    │
│                          │  - category 매칭            │                    │
│                          │  - subsection_title 우선순위│                    │
│                          └─────────────────────────────┘                    │
│                                        │                                    │
│                                        ▼                                    │
│                                                                             │
│                          ┌─────────────────────────────┐                    │
│                          │  📝 Context 구성            │                    │
│                          │  (PromptOrchestrator)       │                    │
│                          │  페르소나 + 상황 + RAG 결과  │                    │
│                          └─────────────────────────────┘                    │
│                                        │                                    │
│                                        ▼                                    │
│                                                                             │
│                          ┌─────────────────────────────┐                    │
│                          │  🧠 LLM 호출 (GPT-4o-mini)  │                    │
│                          │  AI 고객 응답 생성          │                    │
│                          └─────────────────────────────┘                    │
│                                        │                                    │
│                                        ▼                                    │
│                                                                             │
│                          ┌─────────────────────────────┐                    │
│                          │  🔊 TTS (Text-to-Speech)    │                    │
│                          │  페르소나 음성 특성 적용     │                    │
│                          └─────────────────────────────┘                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Ingestion Pipeline (사전 구축)

### 3.1 데이터 소스

```
backend/data/rag_sources/products/hakyung/
├── DEP-TIM.jsonl    # 정기예금
├── DEP-FLX.jsonl    # 자유적금
├── SAV-FIX.jsonl    # 정기적금
├── LON-MTG.jsonl    # 주택담보대출
├── LON-UNS.jsonl    # 신용대출
├── CRD-CRE.jsonl    # 신용카드
├── CRD-DEB.jsonl    # 체크카드
└── ... (총 17개 상품)
```

### 3.2 JSONL 파일 구조 (청크 단위)

각 JSONL 파일은 **이미 청킹이 완료된 상태**로 저장되어 있습니다:

```json
{
  "id": "DEP-TIM-P03-S01-C001",
  "document_id": "DEP-TIM",
  "product": "하경은행 정기예금 (Hakyung Bank Time Deposit)",
  "product_code": "DEP-TIM",
  "part_no": 3,
  "part_title": "금리 정보",
  "subsection_title": "기본 금리 (2025년 10월 28일 기준, 연이율)",
  "breadcrumb": "PART 3. 금리 정보 > 기본 금리",
  "chunk_index": 1,
  "text": "▣ 기본 금리\n 12개월 │ 2.15% │ 2.65% │ 최고인기\n ...",
  "source": "하경은행_정기예금_완전판.txt",
  "chunking": {
    "strategy": "structure+size",
    "max_len": 800,
    "overlap": 120
  }
}
```

### 3.3 청킹 전략

| 항목 | 값 | 설명 |
|------|-----|------|
| **전략** | `structure+size` | 문서 구조(PART/섹션) + 크기 제한 |
| **최대 크기** | 800자 | 한 청크의 최대 문자 수 |
| **오버랩** | 120자 | 청크 간 중복 (문맥 연결) |

### 3.4 메타데이터 필드

```python
# 청크에 포함되는 메타데이터
{
    "product_code": "DEP-TIM",           # 상품 코드 (검색 필터용)
    "part_title": "금리 정보",           # PART 제목
    "subsection_title": "기본 금리",      # 섹션 제목 (검색 우선순위)
    "breadcrumb": "PART 3 > 기본 금리",  # 경로 (UI 표시용)
    "legal_references": [...]            # 관련 법령 (선택)
}
```

### 3.5 임베딩 생성 및 저장

```python
# backend/app/services/product_knowledge_service.py

async def index_all_products_to_vector_db(self, force_reindex=False):
    """모든 상품 청크를 벡터 DB에 인덱싱"""
    
    for product_code, chunks in self.product_knowledge.items():
        for chunk_data in chunks:
            chunk_text = chunk_data.get("text", "")
            
            # 1️⃣ 임베딩 생성 (OpenAI ada-002)
            embedding = embed_text_sync(chunk_text)  # 1536차원 벡터
            
            # 2️⃣ ProductChunk 모델로 저장
            product_chunk = ProductChunk(
                product_code=product_code,
                content=chunk_text,
                chunk_index=chunk_data.get("chunk_index"),
                embedding=embedding,  # 벡터 저장
                subsection_title=chunk_data.get("subsection_title"),
                part_title=chunk_data.get("part_title"),
                breadcrumb=chunk_data.get("breadcrumb"),
                chunk_metadata=json.dumps(metadata)
            )
            
            session.add(product_chunk)
    
    session.commit()
```

---

## 4. Query & Retrieval Pipeline (실시간 질의)

### 4.1 전체 흐름

```
사용자 음성 → STT → 정규화 → 키워드 추출 → 임베딩 → 벡터 검색 → 필터링 → Context 구성 → LLM
```

### 4.2 STT (Speech-to-Text)

```python
# 하이브리드 STT: whisper + gpt-4o-transcribe 보정

# 1단계: whisper-1 기본 인식
transcript = openai_client.audio.transcriptions.create(
    model="whisper-1",
    file=audio_file,
    language="ko"
)

# 2단계: 품질이 낮으면 gpt-4o-transcribe로 재인식
if len(corrections) >= 2 or needs_clarification:
    enhanced_transcript = openai_client.audio.transcriptions.create(
        model="gpt-4o-transcribe",
        file=audio_file,
        language="ko"
    )
```

### 4.3 BankingNormalizer (은행 용어 정규화)

```python
# backend/app/services/banking_normalizer.py

class BankingNormalizer:
    """은행 도메인 용어 정규화"""
    
    # 동의어 사전
    ALIASES = {
        "정기예금": ["정기 예금", "정예금", "정예"],
        "금리": ["이율", "이자율", "이자"],
        "우대금리": ["우대 금리", "우대이율", "추가금리"],
        "중도해지": ["중도 해지", "조기해지", "만기전해지"],
        ...
    }
    
    def normalize(self, text: str) -> str:
        """STT 결과를 은행 용어로 정규화"""
        # 1. 불용어 제거
        # 2. 동의어 → 표준어 변환
        # 3. 오타 교정
        return normalized_text
```

### 4.4 벡터 유사도 검색

```python
# backend/app/services/product_knowledge_service.py

def search_by_vector_similarity(
    self,
    query: str,
    product_codes: Optional[List[str]] = None,
    top_k: int = 5,
    similarity_threshold: float = 0.45  # 유사도 임계값
) -> List[Dict]:
    """벡터 유사도 기반 검색 (pgvector 사용)"""
    
    # 1️⃣ 쿼리를 임베딩 벡터로 변환
    query_embedding = embed_text_sync(query)  # 1536차원
    
    # 2️⃣ pgvector 코사인 유사도 검색
    # SQL: 1 - (embedding <=> query_vector) 로 유사도 계산
    results = session.exec(
        select(ProductChunk)
        .where(ProductChunk.product_code.in_(product_codes))
        .order_by(ProductChunk.embedding.cosine_distance(query_embedding))
        .limit(top_k)
    ).all()
    
    # 3️⃣ 유사도 임계값 필터링
    filtered = [r for r in results if r.similarity > similarity_threshold]
    
    return filtered
```

### 4.5 카테고리 매칭 및 재순위화

```python
# subsection_title 우선순위 매핑
DEFAULT_SUBSECTION_KEYWORDS = {
    "금리": ["금리", "이율", "이자", "연이율", "기본금리"],
    "한도": ["한도", "최대금액", "최소금액", "가입금액"],
    "가입조건": ["가입", "조건", "자격", "대상"],
    "우대금리": ["우대", "추가금리", "보너스"],
    "중도해지": ["중도해지", "해지", "위약금"],
    ...
}

def _category_matches_subsection(self, category: str, subsection_title: str) -> bool:
    """카테고리와 subsection_title 매칭 확인"""
    keywords = DEFAULT_SUBSECTION_KEYWORDS.get(category, [category])
    return any(kw in subsection_title.lower() for kw in keywords)
```

### 4.6 Context 구성 (PromptOrchestrator)

```python
# backend/app/services/promptOrchestrator.py

def compose_llm_messages(
    persona: Dict,
    situation: Dict,
    user_text: str,
    rag_hits: List[Dict],  # 검색된 상품 정보
    history: List[Dict],
    extras: Dict
) -> List[Dict]:
    """LLM 프롬프트 구성"""
    
    system_prompt = f"""
    당신은 은행 고객 역할을 수행합니다.
    
    ## 페르소나
    - 이름: {persona['id']}
    - 연령대: {persona['age_group']}
    - 고객 유형: {persona['customer_style']}
    - 말투: {persona['speech']['tone']}
    
    ## 상황
    - 카테고리: {situation['category']}
    - 목표: {situation['goals']}
    
    ## 상품 정보 (RAG 검색 결과)
    {format_rag_hits(rag_hits)}
    
    ## 대화 히스토리
    {format_history(history)}
    
    위 정보를 바탕으로 자연스러운 고객 응답을 생성하세요.
    """
    
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_text}
    ]
```

---

## 5. 데이터 저장 구조

### 5.1 PostgreSQL + pgvector

```sql
-- product_chunks 테이블
CREATE TABLE product_chunks (
    id SERIAL PRIMARY KEY,
    product_code VARCHAR(20) NOT NULL,  -- 상품 코드 인덱스
    content TEXT NOT NULL,               -- 청크 텍스트
    chunk_index INTEGER,                  -- 청크 순서
    
    -- 벡터 임베딩 (OpenAI ada-002: 1536차원)
    embedding VECTOR(1536),
    
    -- 메타데이터
    subsection_title VARCHAR(200),
    part_title VARCHAR(100),
    breadcrumb VARCHAR(300),
    chunk_metadata JSONB,
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 벡터 검색 성능을 위한 IVFFlat 인덱스
CREATE INDEX idx_product_chunks_embedding 
ON product_chunks 
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- 상품 코드 인덱스
CREATE INDEX idx_product_chunks_product_code 
ON product_chunks (product_code);
```

### 5.2 인덱스 종류 및 성능

| 인덱스 타입 | 용도 | 성능 |
|------------|------|------|
| **IVFFlat** | 벡터 유사도 검색 | 빠름 (근사 최근접 이웃) |
| **B-tree** | product_code 필터 | 매우 빠름 |

---

## 6. 핵심 컴포넌트 상세

### 6.1 EmbeddingService

```python
# backend/app/services/embedding_service.py

class EmbeddingService:
    """OpenAI 임베딩 서비스 래퍼"""
    
    def __init__(self):
        self._model = "text-embedding-ada-002"  # 1536차원
        
    async def embed_query(self, query: str) -> List[float]:
        """단일 쿼리 임베딩"""
        response = await self._client.embeddings.create(
            model=self._model,
            input=query
        )
        return response.data[0].embedding  # 1536차원 벡터
```

### 6.2 ProductKnowledgeService

| 메서드 | 설명 |
|--------|------|
| `_load_all_products()` | JSONL 파일에서 청크 로드 |
| `index_all_products_to_vector_db()` | 벡터 DB에 인덱싱 |
| `search_by_vector_similarity()` | 벡터 유사도 검색 |
| `search_by_keyword()` | 키워드 기반 검색 |
| `verify_claim()` | 사실 검증 (LLM 기반) |

### 6.3 PromptOrchestrator

| 함수 | 설명 |
|------|------|
| `compose_llm_messages()` | LLM 프롬프트 구성 |
| `parse_llm_response()` | LLM 응답 파싱 |
| `get_situation_defaults()` | 상황별 기본값 |

---

## 7. 흐름 예시

### 시나리오: 정기예금 금리 문의

```
1️⃣ 신입사원: "정기예금 금리가 어떻게 되나요?" (음성)
          ↓
2️⃣ STT (Whisper): "정기예금 금리가 어떻게 되나요?"
          ↓
3️⃣ BankingNormalizer: "정기예금 금리" (키워드 추출)
          ↓
4️⃣ 임베딩 생성: [0.12, -0.34, 0.56, ...] (1536차원)
          ↓
5️⃣ 벡터 검색 (pgvector):
   - 쿼리: "정기예금 금리"
   - 결과: DEP-TIM-P03-S01-C001 (유사도 0.87)
   
   매칭된 청크:
   "▣ 기본 금리 (2025년 10월 28일 기준)
    12개월 │ 2.15% │ 2.65% │ 최고인기"
          ↓
6️⃣ Context 구성 (PromptOrchestrator):
   - 페르소나: 30대 직장인, 급함형
   - 상황: 정기예금 가입 상담
   - RAG 결과: 12개월 기본금리 2.15%, 최고금리 2.65%
          ↓
7️⃣ LLM 호출 (GPT-4o-mini):
   "12개월 정기예금 금리가 2.15%라고요? 
    우대금리 받으면 얼마까지 가능한가요?"
          ↓
8️⃣ TTS: AI 고객 음성 생성 (급한 말투, 빠른 속도)
          ↓
9️⃣ 신입사원에게 음성 재생 + 평가 피드백 제공
```

---

## 📊 기술 스택 요약

| 컴포넌트 | 기술 | 용도 |
|----------|------|------|
| 벡터 DB | PostgreSQL + pgvector | 벡터 저장 및 검색 |
| 임베딩 | OpenAI text-embedding-ada-002 | 1536차원 벡터 생성 |
| LLM | GPT-4o-mini | AI 고객 응답 생성 |
| STT | Whisper + gpt-4o-transcribe | 음성 → 텍스트 |
| TTS | OpenAI TTS | 텍스트 → 음성 |
| 백엔드 | FastAPI + Python | API 서버 |
| 데이터 형식 | JSONL | 사전 청킹된 상품 정보 |

---

**작성일**: 2025년 12월 4일  
**버전**: 1.0

