"""
제품 지식 베이스 서비스 (Product Knowledge Base Service)

products/*.jsonl 파일을 로드하여 제품 정보 검색 및 검증 기능 제공
- 키워드 기반 검색
- 의미적 유사도 계산
- LLM 기반 사실 검증 (선택)

용어 정리:
- Product Knowledge Base: 제품 정보 저장소 (JSONL 파일)
- RAG (Retrieval-Augmented Generation): 검색 증강 생성 (별도 시스템)
- Knowledge Verification: 제품 지식 검증 프로세스
"""
import json
import re
import os
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from app.config import settings

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    print("⚠️ NumPy 없음 - 임베딩 유사도 계산 시 SequenceMatcher 사용")

try:
    from app.services.embedding_service import embed_text_sync
    EMBEDDING_AVAILABLE = True
except ImportError:
    EMBEDDING_AVAILABLE = False
    print("⚠️ EmbeddingService 없음 - 임베딩 유사도 비활성화")

try:
    from app.services.product_keyword_extractor import ProductKeywordExtractor
    KEYWORD_EXTRACTOR_AVAILABLE = True
except ImportError:
    KEYWORD_EXTRACTOR_AVAILABLE = False
    print("⚠️ ProductKeywordExtractor 없음 - 하드코딩된 키워드 사용")

try:
    from sqlmodel import Session, select, func, text
    from app.models import ProductChunk
    from pgvector.sqlalchemy import Vector as PgVector
    from sqlalchemy import bindparam
    SQLMODEL_AVAILABLE = True
except ImportError:
    SQLMODEL_AVAILABLE = False
    Session = None
    ProductChunk = None
    PgVector = None
    print("⚠️ SQLModel 없음 - 벡터 검색 비활성화")


DEFAULT_SUBSECTION_KEYWORDS: Dict[str, List[str]] = {
    "금리": ["금리", "이자율", "기본금리", "우대금리", "최고금리", "적용금리"],
    "한도": ["한도", "신용한도", "최대", "최소"],
    "가입금액": ["가입금액", "가입 금액", "최소", "최대", "납입금액", "납입 금액"],
    "기간": ["기간", "만기", "계약기간", "거치기간", "가입 기간", "계약 기간"],
    "우대금리": ["우대금리", "우대 금리", "우대"],
    "수수료": ["수수료", "연회비", "중도상환", "중도해지"],
    "혜택": ["혜택", "할인", "포인트", "적립", "서비스"],
    "이자지급": ["이자지급", "이자 지급", "이자 계산", "이자 계산 및 지급"],
    "예금자보호": ["예금자보호", "예금자 보호", "보호"],
    "필요서류": ["필요서류", "필요 서류", "서류"],
    "상환방식": ["상환방식", "상환 방식", "원리금", "원금"],
    "신용등급": ["신용등급", "신용 등급", "등급"],
    "LTV": ["LTV", "담보인정비율", "담보 인정 비율"],
    "DTI": ["DTI", "총부채상환비율"],
    "DSR": ["DSR", "총부채원리금상환비율"],
    "환율": ["환율", "환전", "외환"]
}

DEFAULT_CATEGORY_PATTERNS: Dict[str, List[str]] = {
    "금리": [r"금리\s*(?:는|:)?\s*([\d\.]+)%?", r"이자율?\s*([\d\.]+)%?", r"연\s*([\d\.]+)%"],
    "한도": [r"한도\s*(?:는|:)?\s*([\d,]+)원?", r"최대\s*([\d,]+)원?", r"([\d,]+)만원까지", r"최소\s*([\d,]+)원?"],
    "기간": [r"기간\s*(?:은|는)?\s*([\d]+)(?:개월|년)", r"만기\s*([\d]+)(?:개월|년)", r"거치기간\s*([\d]+)(?:개월|년)?"],
    "조건": [r"조건\s*(?:은|는)?", r"자격\s*(?:은|는)?", r"대상\s*(?:은|는)?"],
    "수수료": [
        r"수수료\s*([\d,]+)원?",
        r"수수료\s*면제",
        r"무료",
        r"수수료\s*([\d]+)원대",
        r"수수료\s*([\d]+)원\s*대",
        r"중도상환\s*수수료",
        r"중도해지\s*수수료"
    ],
    "환율": [
        r"환율\s*(?:은|는)?\s*([\d,\.]+)",
        r"환율\s*우대\s*([\d\.]+)%?",
        r"우대율\s*([\d\.]+)%?",
        r"([\d\.]+)%\s*우대",
        r"환율\s*([\d\.]+)%"
    ],
    "혜택": [r"혜택", r"할인", r"포인트", r"적립"],
    "우대금리": [
        r"우대금리\s*(?:는|:)?\s*([\d\.]+)%?",
        r"우대\s*([\d\.]+)%?p?",
        r"최대\s*([\d\.]+)%?p?\s*추가",
        r"최대\s*([\d\.]+)%?p?\s*차감",
        r"([\d\.]+)%?p?\s*우대"
    ],
    "LTV": [
        r"LTV\s*(?:는|:)?\s*([\d]+)%?",
        r"담보인정비율\s*(?:은|는)?\s*([\d]+)%?",
        r"담보\s*인정\s*비율\s*([\d]+)%?"
    ],
    "DTI": [r"DTI\s*(?:는|:)?\s*([\d]+)%?", r"총부채상환비율\s*(?:은|는)?\s*([\d]+)%?"],
    "DSR": [r"DSR\s*(?:는|:)?\s*([\d]+)%?", r"총부채원리금상환비율\s*(?:은|는)?\s*([\d]+)%?"],
    "상환방식": [r"상환\s*방식", r"원리금균등", r"원금균등", r"체증식", r"거치식", r"원리금\s*균등", r"원금\s*균등"],
    "신용등급": [r"신용등급\s*(?:은|는)?\s*([\d]+)\s*등급", r"([\d]+)\s*등급", r"신용\s*등급\s*([\d]+)"],
    "이자지급": [r"이자\s*지급", r"매월\s*이자", r"만기\s*이자", r"이자소득세\s*([\d\.]+)%?", r"이자\s*납부"],
    "예금자보호": [r"예금자보호", r"보호한도\s*([\d,]+)원?", r"([\d,]+)원\s*보호", r"5천만원\s*보호"],
    "필요서류": [r"필요\s*서류", r"등기부등본", r"감정평가서", r"소득증빙", r"재직증명서", r"신분증"],
    "가입금액": [r"가입금액\s*(?:은|는)?\s*([\d,]+)원?", r"최소\s*가입\s*([\d,]+)원?", r"([\d,]+)만원\s*부터"]
}


# ProductChunk는 딕셔너리로 표현 (유연한 필드 지원)
# 필수 필드: id, product_code, text, breadcrumb
# 선택 필드: chunking, legal_references 등


@dataclass
class ProductFactCheck:
    """제품 정보 팩트 체크 결과"""
    claim: str  # 사용자가 말한 내용
    ground_truth: str  # Knowledge Base에서 찾은 정답
    is_accurate: bool  # 정확성 여부
    similarity_score: float  # 유사도 점수 (0-1)
    product_code: str
    category: str  # 금리, 한도, 조건 등
    verification_method: str = "keyword"  # keyword, semantic, llm
    llm_reasoning: Optional[str] = None  # LLM 검증 이유 (선택)
    full_utterance: Optional[str] = None  # 전체 발화 (문맥 보존)


class ProductKnowledgeService:
    """
    제품 지식 베이스 서비스 (Product Knowledge Base Service)
    
    제품 정보를 로드하고 검증하는 서비스
    - Keyword-based Search: 키워드 매칭
    - Semantic Similarity: 의미적 유사도
    - LLM Verification: GPT 기반 사실 검증 (선택)
    """
    
    def __init__(self, data_path: Optional[Path] = None, use_llm: bool = True, session: Optional[Session] = None):
        """
        초기화
        
        Args:
            data_path: 데이터 디렉토리 경로 (기본: backend/data)
            use_llm: LLM 기반 검증 사용 여부 (기본: True)
            session: DB 세션 (벡터 검색 사용 시 필요, 선택적)
        """
        if data_path is None:
            # Docker 환경 우선, 없으면 로컬
            if Path("/app/data").exists():
                self.data_path = Path("/app/data")
            else:
                self.data_path = Path(__file__).parent.parent.parent / "data"
        else:
            self.data_path = data_path
        
        self.products_dir = self.data_path / "rag_sources" / "products" / "hakyung"
        self.product_knowledge: Dict[str, List[Dict]] = {}  # ProductChunk를 Dict로 변경
        self.product_catalog = None
        self.category_keyword_mapping: Dict[str, List[str]] = {}
        self.category_patterns: Dict[str, List[str]] = {}
        
        # LLM 설정
        self.use_llm = use_llm and OPENAI_AVAILABLE
        self.openai_client = None
        
        if self.use_llm:
            api_key = settings.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY")
            if api_key:
                try:
                    self.openai_client = OpenAI(api_key=api_key)
                    print("✅ LLM 검증 활성화 (GPT-4 사용)")
                except Exception as e:
                    print(f"⚠️ OpenAI 초기화 실패: {e}")
                    self.use_llm = False
            else:
                print("⚠️ OPENAI_API_KEY 없음 - LLM 검증 비활성화")
                self.use_llm = False
        
        # DB 세션 설정 (벡터 검색용)
        self.session = session
        self.use_vector_search = SQLMODEL_AVAILABLE and session is not None and EMBEDDING_AVAILABLE
        
        # 임베딩 기반 Semantic 유사도 설정
        self.use_embedding = EMBEDDING_AVAILABLE and NUMPY_AVAILABLE
        self.embedding_cache: Dict[str, List[float]] = {}  # 임베딩 캐시 (성능 최적화)
        
        if self.use_embedding:
            print("✅ 임베딩 기반 Semantic 유사도 활성화")
        else:
            print("⚠️ 임베딩 비활성화 - SequenceMatcher 사용")
        
        if self.use_vector_search:
            print("✅ 벡터 검색 활성화 (pgvector)")
        else:
            print("⚠️ 벡터 검색 비활성화 - 키워드 검색만 사용")
        
        # 키워드 추출기 초기화 (하이브리드 접근)
        self.keyword_extractor = None
        if KEYWORD_EXTRACTOR_AVAILABLE:
            try:
                self.keyword_extractor = ProductKeywordExtractor(data_path=self.data_path, use_llm=False)
                print("✅ 키워드 자동 추출기 초기화 완료")
            except Exception as e:
                print(f"⚠️ 키워드 추출기 초기화 실패: {e}")
        
        # 초기 로드
        self._load_all_products()
        self._load_product_catalog()
        self._load_category_config()

    def _load_category_config(self) -> None:
        """카테고리 관련 구성 로드 (JSON 우선, 없으면 기본값)"""
        def clone_default(mapping: Dict[str, List[str]]) -> Dict[str, List[str]]:
            return {k: list(v) for k, v in mapping.items()}

        self.category_keyword_mapping = clone_default(DEFAULT_SUBSECTION_KEYWORDS)
        self.category_patterns = clone_default(DEFAULT_CATEGORY_PATTERNS)

        config_path = self.data_path / "category_config.json"
        if not config_path.exists():
            print(f"ℹ️ 카테고리 구성 파일 없음 (기본값 사용): {config_path}")
            return

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config_data = json.load(f)

            subsection_keywords = config_data.get("subsection_keywords")
            if isinstance(subsection_keywords, dict):
                self.category_keyword_mapping = {
                    key: list(value) for key, value in subsection_keywords.items() if isinstance(value, list)
                }

            category_patterns = config_data.get("category_patterns")
            if isinstance(category_patterns, dict):
                self.category_patterns = {
                    key: list(value) for key, value in category_patterns.items() if isinstance(value, list)
                }

            print(f"✅ 카테고리 구성 로드 완료: {config_path}")
        except Exception as e:
            print(f"⚠️ 카테고리 구성 로드 실패 (기본값 사용): {e}")
    
    def _load_all_products(self):
        """모든 제품 jsonl 파일 로드"""
        if not self.products_dir.exists():
            print(f"⚠️ 제품 디렉토리 없음: {self.products_dir}")
            return
        
        print(f"📦 제품 지식 로드 시작: {self.products_dir}")
        
        for jsonl_file in self.products_dir.glob("*.jsonl"):
            product_code = jsonl_file.stem  # CRD-CRE, DEP-TIM 등
            chunks = []
            
            try:
                with open(jsonl_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.strip():  # 빈 줄 건너뛰기
                            data = json.loads(line.strip())
                            chunks.append(data)  # 딕셔너리 그대로 저장
                
                self.product_knowledge[product_code] = chunks
                print(f"  ✓ {product_code}: {len(chunks)}개 청크")
            
            except Exception as e:
                print(f"  ✗ {product_code} 로드 실패: {e}")
        
        print(f"✅ 총 {len(self.product_knowledge)}개 제품 로드 완료")
    
    def index_product_data_to_vector_db(self, product_code: Optional[str] = None, force_reindex: bool = False) -> Dict[str, int]:
        """
        상품 데이터를 pgvector에 인덱싱
        
        **프로세스:**
        1. JSONL 파일에서 상품 데이터 로드
        2. 각 청크를 임베딩 벡터로 변환
        3. pgvector에 저장 (ProductChunk 테이블)
        
        Args:
            product_code: 특정 제품만 인덱싱 (None이면 전체)
            force_reindex: 기존 데이터 삭제 후 재인덱싱 여부
        
        Returns:
            {"product_code": indexed_count} 딕셔너리
        """
        if not self.use_vector_search or not self.session:
            print("⚠️ 벡터 검색 비활성화 - 인덱싱 불가")
            return {}
        
        indexed_counts = {}
        
        try:
            # 인덱싱할 제품 목록 결정
            products_to_index = []
            if product_code:
                products_to_index = [product_code] if product_code in self.product_knowledge else []
            else:
                products_to_index = list(self.product_knowledge.keys())
            
            if not products_to_index:
                print("⚠️ 인덱싱할 제품이 없습니다")
                return {}
            
            print(f"📦 상품 데이터 벡터 인덱싱 시작: {len(products_to_index)}개 제품")
            
            for product_code in products_to_index:
                try:
                    chunks = self.product_knowledge.get(product_code, [])
                    if not chunks:
                        print(f"  ⚠️ {product_code}: 청크 없음")
                        continue
                    
                    # 기존 데이터 삭제 (force_reindex가 True이거나 처음 인덱싱 시)
                    if force_reindex:
                        existing_chunks = self.session.exec(
                            select(ProductChunk).where(ProductChunk.product_code == product_code)
                        ).all()
                        for chunk in existing_chunks:
                            self.session.delete(chunk)
                        self.session.commit()
                        print(f"  🗑️ {product_code}: 기존 데이터 삭제 완료")
                    
                    # 중복 체크 (이미 인덱싱된 청크 제외)
                    existing_chunk_ids = set()
                    if not force_reindex:
                        existing = self.session.exec(
                            select(ProductChunk.id, ProductChunk.chunk_index).where(
                                ProductChunk.product_code == product_code
                            )
                        ).all()
                        existing_chunk_ids = {(product_code, row.chunk_index) for row in existing}
                    
                    indexed_count = 0
                    skipped_count = 0
                    
                    # 청크별로 임베딩 생성 및 저장
                    for chunk_data in chunks:
                        chunk_index = chunk_data.get("chunk_index", 0)
                        chunk_id_key = (product_code, chunk_index)
                        
                        # 이미 인덱싱된 청크는 건너뛰기
                        if chunk_id_key in existing_chunk_ids:
                            skipped_count += 1
                            continue
                        
                        chunk_text = chunk_data.get("text", "")
                        if not chunk_text:
                            continue
                        
                        try:
                            # 임베딩 생성
                            embedding = embed_text_sync(chunk_text)
                            
                            if not embedding:
                                print(f"  ⚠️ {product_code} 청크 {chunk_index}: 임베딩 생성 실패")
                                continue
                            
                            # 메타데이터 준비
                            metadata = {
                                "subsection_title": chunk_data.get("subsection_title", ""),
                                "part_title": chunk_data.get("part_title", ""),
                                "breadcrumb": chunk_data.get("breadcrumb", ""),
                                "source": chunk_data.get("source", ""),
                                "product": chunk_data.get("product", ""),
                                "document_id": chunk_data.get("document_id", "")
                            }
                            
                            # ProductChunk 생성
                            product_chunk = ProductChunk(
                                product_code=product_code,
                                content=chunk_text,
                                chunk_index=chunk_index,
                                embedding=embedding,
                                subsection_title=chunk_data.get("subsection_title"),
                                part_title=chunk_data.get("part_title"),
                                breadcrumb=chunk_data.get("breadcrumb"),
                                chunk_metadata=json.dumps(metadata, ensure_ascii=False)
                            )
                            
                            self.session.add(product_chunk)
                            indexed_count += 1
                            
                        except Exception as e:
                            print(f"  ⚠️ {product_code} 청크 {chunk_index} 인덱싱 실패: {e}")
                            continue
                    
                    # 커밋
                    self.session.commit()
                    indexed_counts[product_code] = indexed_count
                    
                    print(f"  ✅ {product_code}: {indexed_count}개 청크 인덱싱 완료 (건너뜀: {skipped_count}개)")
                    
                except Exception as e:
                    print(f"  ❌ {product_code} 인덱싱 실패: {e}")
                    self.session.rollback()
                    continue
            
            print(f"✅ 벡터 인덱싱 완료: 총 {sum(indexed_counts.values())}개 청크")
            return indexed_counts
            
        except Exception as e:
            print(f"❌ 벡터 인덱싱 오류: {e}")
            import traceback
            traceback.print_exc()
            self.session.rollback()
            return {}
    
    def _load_product_catalog(self):
        """제품 카탈로그 로드"""
        catalog_path = self.data_path / "product_catalog.json"
        
        if not catalog_path.exists():
            print(f"⚠️ 제품 카탈로그 없음: {catalog_path}")
            return
        
        try:
            with open(catalog_path, 'r', encoding='utf-8') as f:
                self.product_catalog = json.load(f)
            print(f"✅ 제품 카탈로그 로드: {len(self.product_catalog.get('products', []))}개")
        except Exception as e:
            print(f"❌ 제품 카탈로그 로드 실패: {e}")
    
    def _get_category_keywords_for_subsection(self, category: str) -> List[str]:
        """
        카테고리 → subsection_title 매칭 키워드 반환
        
        Args:
            category: 정보 카테고리 (예: "금리", "한도", "가입금액")
        
        Returns:
            subsection_title에서 매칭할 키워드 리스트
        """
        keywords = self.category_keyword_mapping.get(category)
        return keywords if keywords else [category]  # 기본값: 카테고리 자체
    
    def _category_matches_subsection(self, category: str, subsection_title: str) -> bool:
        """
        카테고리가 subsection_title과 매칭되는지 확인
        
        Args:
            category: 정보 카테고리
            subsection_title: 청크의 subsection_title
        
        Returns:
            매칭 여부
        """
        if not subsection_title:
            return False
        
        keywords = self._get_category_keywords_for_subsection(category)
        subsection_lower = subsection_title.lower()
        
        # 키워드 중 하나라도 subsection_title에 포함되면 매칭
        return any(keyword.lower() in subsection_lower for keyword in keywords)
    
    def search_by_vector_similarity(
        self,
        query: str,
        category: Optional[str] = None,
        product_codes: Optional[List[str]] = None,
        top_k: int = 5,
        similarity_threshold: float = 0.3
    ) -> List[Dict]:
        """
        벡터 유사도 기반 제품 정보 검색 (pgvector 사용)
        
        **프로세스:**
        1. 쿼리를 임베딩 벡터로 변환
        2. pgvector에서 코사인 유사도 검색
        3. 유사도 임계값 이상만 반환
        
        Args:
            query: 검색 쿼리
            category: 정보 카테고리 (필터링용)
            product_codes: 검색할 제품 코드 리스트
            top_k: 반환할 최대 결과 수
            similarity_threshold: 유사도 임계값 (0.0 ~ 1.0)
        
        Returns:
            관련 제품 청크 리스트 (유사도 높은 순)
        """
        print(f"🔍 [벡터 검색] 함수 호출됨: use_vector_search={self.use_vector_search}, session={self.session is not None}")
        
        if not self.use_vector_search or not self.session:
            print(f"❌ [벡터 검색] 비활성화됨: use_vector_search={self.use_vector_search}, session={self.session is not None}")
            return []  # 벡터 검색 불가 시 빈 리스트 반환
        
        try:
            print(f"🔍 [벡터 검색] 시작: query='{query[:100]}...', product_codes={product_codes}, threshold={similarity_threshold}")
            
            # 1. 쿼리 임베딩 생성
            query_embedding = embed_text_sync(query)
            
            if not query_embedding:
                print(f"❌ [벡터 검색] 임베딩 생성 실패: query_embedding=None")
                return []
            
            print(f"✅ [벡터 검색] 임베딩 생성 성공: 차원={len(query_embedding)}")
            
            # 2. SQL 쿼리 구성 (동적 WHERE 조건 추가)
            where_conditions = ["pc.embedding IS NOT NULL"]
            params = {
                "query_embedding": query_embedding,
                "similarity_threshold": similarity_threshold,
                "top_k": top_k
            }
            
            # 🚨 제품 코드 필터링 (필수)
            if product_codes:
                # SQL injection 방지: 각 코드를 따옴표로 감싸기
                sanitized_codes = [code.replace("'", "''") for code in product_codes]  # SQL injection 방지
                placeholders = ",".join([f"'{code}'" for code in sanitized_codes])
                where_conditions.append(f"pc.product_code IN ({placeholders})")
                print(f"🔍 [벡터 검색 SQL] product_code 필터 적용: {product_codes}")
            else:
                print(f"⚠️ [벡터 검색 SQL] product_code 필터 없음: 전체 상품 검색")
            
            # 카테고리 필터링 (subsection_title 기반)
            if category:
                category_keywords = self._get_category_keywords_for_subsection(category)
                if category_keywords:
                    # subsection_title에 카테고리 키워드가 포함된 청크만 필터링
                    keyword_conditions = " OR ".join([
                        f"pc.subsection_title ILIKE '%{kw.replace('%', '%%')}%'" for kw in category_keywords
                    ])
                    where_conditions.append(f"({keyword_conditions})")
            
            # WHERE 절 구성
            where_clause = " AND ".join(where_conditions)
            
            # SQL 쿼리 생성
            sql_query_str = f"""
                SELECT 
                    pc.id,
                    pc.product_code,
                    pc.content,
                    pc.chunk_index,
                    pc.subsection_title,
                    pc.part_title,
                    pc.breadcrumb,
                    pc.chunk_metadata,
                    1 - (pc.embedding <=> :query_embedding) AS similarity
                FROM product_chunks pc
                WHERE {where_clause}
                AND 1 - (pc.embedding <=> :query_embedding) >= :similarity_threshold
                ORDER BY pc.embedding <=> :query_embedding
                LIMIT :top_k
            """
            
            sql_query = text(sql_query_str)
            
            # 3. 쿼리 실행 (pgvector 타입 바인딩)
            print(f"🔍 [벡터 검색] SQL 쿼리 실행: WHERE={where_clause[:200]}...")
            print(f"🔍 [벡터 검색] SQL 전체 쿼리:\n{sql_query_str}")
            
            if PgVector:
                # pgvector 타입으로 바인딩 (RAGService 참고)
                sql_query = sql_query.bindparams(
                    bindparam("query_embedding", type_=PgVector(1536))
                )
                # 파라미터 전달 (query_embedding은 Vector 타입으로, 나머지는 일반)
                result = self.session.execute(
                    sql_query, 
                    {
                        "query_embedding": query_embedding,
                        "similarity_threshold": similarity_threshold,
                        "top_k": top_k
                    }
                ).fetchall()
            else:
                # PgVector 없을 때는 일반 파라미터로 (fallback)
                result = self.session.execute(sql_query, params).fetchall()
            
            print(f"🔍 [벡터 검색] SQL 쿼리 결과: {len(result)}개 행 반환")
            
            # 🔍 결과의 상품 코드 확인 (SQL 쿼리 결과)
            if result:
                result_product_codes = []
                for row in result[:5]:  # 처음 5개만 확인
                    if hasattr(row, 'product_code'):
                        result_product_codes.append(row.product_code)
                print(f"🔍 [벡터 검색] SQL 결과 상품 코드 (샘플): {list(set(result_product_codes))}")
                if product_codes:
                    mismatched = [code for code in result_product_codes if code not in product_codes]
                    if mismatched:
                        print(f"❌ [벡터 검색] SQL 오류: 필터와 다른 상품 코드 발견! 요청: {product_codes}, 발견: {mismatched}")
            
            # 4. 결과 변환
            results = []
            print(f"🔍 [벡터 검색] 결과 변환 시작: {len(result)}개 행")
            for i, row in enumerate(result):
                try:
                    similarity_value = float(row.similarity) if row.similarity is not None else 0.0
                    row_product_code = row.product_code if hasattr(row, 'product_code') else "UNKNOWN"
                    print(f"  📊 행 {i+1}: 유사도={similarity_value:.3f}, product_code={row_product_code}, 제목={row.subsection_title[:50] if row.subsection_title else 'N/A'}...")
                    
                    metadata = None
                    if row.chunk_metadata:
                        try:
                            metadata = json.loads(row.chunk_metadata)
                        except json.JSONDecodeError:
                            metadata = None
                    
                    chunk_dict = {
                        "text": row.content,
                        "subsection_title": row.subsection_title,
                        "part_title": row.part_title,
                        "breadcrumb": row.breadcrumb,
                        "product_code": row.product_code,
                        "chunk_index": row.chunk_index,
                        "similarity": similarity_value,
                        "metadata": metadata
                    }
                    results.append(chunk_dict)
                except Exception as e:
                    print(f"  ⚠️ 행 {i+1} 변환 실패: {e}")
                    continue
            
            if results:
                max_similarity = max(r.get('similarity', 0) for r in results)
                print(f"✅ [벡터 검색] 완료: {len(results)}개 결과 반환 (최고 유사도: {max_similarity:.3f})")
            else:
                print(f"⚠️ [벡터 검색] 결과 변환 후 빈 리스트: SQL 쿼리는 {len(result)}개 행 반환했지만 변환 실패")
            return results
            
        except Exception as e:
            print(f"❌ [벡터 검색] 예외 발생: {e}")
            import traceback
            traceback.print_exc()
            return []  # 실패 시 빈 리스트 반환
    
    def search_by_keyword(
        self, 
        query: str,
        category: Optional[str] = None,  # 카테고리 추가
        product_codes: Optional[List[str]] = None,
        top_k: int = 5
    ) -> List[Dict]:
        """
        제품 정보 검색 (벡터 검색 우선, 키워드 검색 fallback)
        
        **검색 순서:**
        1. 벡터 검색 시도 (pgvector 사용, 유사도 기반)
        2. 벡터 검색 실패 시 키워드 검색 사용
        
        **개선 사항:**
        - 벡터 검색: 의미적 유사도 기반
        - 키워드 검색: 구조화된 필드 활용
        - 카테고리 기반 subsection_title 우선 매칭
        - 쿼리를 키워드로 분리하여 부분 매칭 지원
        - 숫자와 텍스트를 분리하여 검색
        - 여러 키워드 매칭 시 관련도 점수 증가
        
        개선 사항:
        - 카테고리 기반 subsection_title 우선 매칭
        - 쿼리를 키워드로 분리하여 부분 매칭 지원
        - 숫자와 텍스트를 분리하여 검색
        - 여러 키워드 매칭 시 관련도 점수 증가
        
        Args:
            query: 검색 쿼리 (예: "금리 연 2.15%")
            category: 정보 카테고리 (예: "금리", "한도", "가입금액") - 구조화된 매칭에 사용
            product_codes: 검색할 제품 코드 리스트 (None이면 전체)
            top_k: 반환할 최대 결과 수
        
        Returns:
            관련 제품 청크 리스트 (유사도/관련도 점수 높은 순)
        """
        # 🎯 1단계: 벡터 검색 시도
        if self.use_vector_search:
            vector_results = self.search_by_vector_similarity(
                query=query,
                category=category,
                product_codes=product_codes,
                top_k=top_k,
                similarity_threshold=0.3  # 유사도 임계값 (0.5에서 0.3으로 낮춤 - 진단 결과 기반)
            )
            
            if vector_results:
                print(f"✅ 벡터 검색 성공: {len(vector_results)}개 청크 발견")
                return vector_results
        
        # 🔄 2단계: 벡터 검색 실패 시 키워드 검색 (fallback)
        print("🔄 벡터 검색 실패 또는 결과 없음, 키워드 검색 사용")
        return self._search_by_keyword_fallback(query, category, product_codes, top_k)
    
    def _search_by_keyword_fallback(
        self,
        query: str,
        category: Optional[str] = None,
        product_codes: Optional[List[str]] = None,
        top_k: int = 5
    ) -> List[Dict]:
        """
        키워드 기반 제품 정보 검색 (fallback)
        
        구조화된 필드 활용 개선 버전
        """
        # 🔍 디버깅: 키워드 검색 시작 로그
        print(f"🔍 [키워드 검색 fallback] 시작: query='{query[:50]}...', product_codes={product_codes}, category={category}")
        
        results = []
        query_lower = query.lower()
        
        # 🚨 검색 대상 필터링: product_codes가 지정되면 반드시 해당 상품만 검색
        if product_codes:
            search_space = {k: v for k, v in self.product_knowledge.items() if k in product_codes}
            print(f"🔍 [키워드 검색] 필터링: {len(product_codes)}개 상품 코드로 제한, 검색 대상: {list(search_space.keys())}")
        else:
            search_space = self.product_knowledge
            print(f"🔍 [키워드 검색] 필터링 없음: 전체 상품 검색 ({len(search_space)}개 상품)")
        
        # 쿼리를 키워드로 분리 (숫자, 카테고리, 주요 단어)
        query_keywords = self._extract_search_keywords(query)
        
        for product_code, chunks in search_space.items():
            for chunk in chunks:
                # 텍스트 매칭
                chunk_text = chunk.get("text", "")
                subsection = chunk.get("subsection_title", "")
                part_title = chunk.get("part_title", "")
                chunk_text_lower = chunk_text.lower()
                subsection_lower = subsection.lower()
                part_title_lower = part_title.lower()
                
                score = 0.0
                match_type = None
                
                # === 1단계: 카테고리 기반 subsection_title 매칭 (최우선) ===
                if category and self._category_matches_subsection(category, subsection):
                    # 카테고리 매칭: 매우 높은 우선순위
                    score = 1.0
                    match_type = "category_subsection"
                    
                    # 추가 점수: 쿼리 키워드도 매칭되면
                    matched_query_keywords = sum(1 for kw in query_keywords if kw in chunk_text_lower or kw in subsection_lower)
                    if matched_query_keywords > 0:
                        score = min(1.0, score + 0.1 * (matched_query_keywords / len(query_keywords)))
                
                # === 2단계: 전체 쿼리 포함 여부 확인 ===
                elif query_lower in chunk_text_lower or query_lower in subsection_lower:
                    score = self._calculate_relevance_score(query, chunk_text)
                    match_type = "full_query"
                
                # === 3단계: 키워드 부분 매칭 ===
                else:
                    matched_keywords = []
                    for keyword in query_keywords:
                        if keyword in chunk_text_lower or keyword in subsection_lower or keyword in part_title_lower:
                            matched_keywords.append(keyword)
                    
                    if matched_keywords:
                        match_ratio = len(matched_keywords) / len(query_keywords) if query_keywords else 0
                        # 최소 50% 이상 매칭되어야 함 (또는 숫자가 포함되어야 함)
                        has_number = any(char.isdigit() for char in query)
                        if match_ratio >= 0.5 or (has_number and any(char.isdigit() for kw in matched_keywords for char in kw)):
                            # 관련도 점수: 매칭 비율 기반
                            score = match_ratio * 0.7  # 부분 매칭은 최대 0.7점
                            match_type = "partial_keyword"
                            
                            # 숫자가 정확히 매칭되면 추가 점수
                            if has_number:
                                query_numbers = self._extract_numbers(query)
                                chunk_numbers = self._extract_numbers(chunk_text)
                                if query_numbers and chunk_numbers:
                                    # 숫자가 일치하면 추가 점수
                                    if any(qn in cn for qn in query_numbers for cn in chunk_numbers):
                                        score = min(0.9, score + 0.2)
                
                # 점수가 있는 경우에만 결과에 추가
                if score > 0:
                    results.append((score, chunk))
        
        # RAG 데이터가 없고 product_codes가 지정된 경우, product_catalog에서 fallback 검색
        if not results and product_codes and self.product_catalog:
            for product_code in product_codes:
                product_info = self._get_product_from_catalog(product_code)
                if product_info:
                    # product_catalog 정보를 청크 형식으로 변환
                    catalog_chunk = {
                        "text": self._format_catalog_as_text(product_info),
                        "product": product_info.get("name", ""),
                        "product_code": product_code,
                        "subsection_title": "",
                        "source": "product_catalog"
                    }
                    score = self._calculate_relevance_score(query, catalog_chunk["text"])
                    results.append((score, catalog_chunk))
        
        # 점수순 정렬 후 상위 k개 반환
        results.sort(key=lambda x: x[0], reverse=True)
        final_results = [chunk for _, chunk in results[:top_k]]
        
        # 🔍 최종 결과의 상품 코드 확인
        if final_results:
            found_product_codes = [chunk.get("product_code", "UNKNOWN") for chunk in final_results]
            print(f"✅ [키워드 검색] 완료: {len(final_results)}개 결과, 상품 코드: {found_product_codes}")
            
            # 🚨 상품 코드 필터 검증
            if product_codes:
                mismatched = [code for code in found_product_codes if code not in product_codes]
                if mismatched:
                    print(f"❌ [키워드 검색] 오류: 필터와 다른 상품 코드 발견! 요청: {product_codes}, 발견: {mismatched}")
                    # 다른 상품 코드는 제외
                    final_results = [chunk for chunk in final_results if chunk.get("product_code") in product_codes]
                    print(f"🔍 [키워드 검색] 필터링 후: {len(final_results)}개 결과")
        
        return final_results
    
    def _get_product_from_catalog(self, product_code: str) -> Optional[Dict]:
        """product_catalog에서 제품 정보 가져오기"""
        if not self.product_catalog:
            return None
        
        products = self.product_catalog.get("products", [])
        for product in products:
            if product.get("code") == product_code:
                return product
        return None
    
    def _format_catalog_as_text(self, product_info: Dict) -> str:
        """product_catalog 정보를 텍스트로 포맷팅"""
        parts = []
        
        if product_info.get("name"):
            parts.append(f"제품명: {product_info['name']}")
        
        if product_info.get("description"):
            parts.append(f"설명: {product_info['description']}")
        
        if product_info.get("features"):
            features = ", ".join(product_info["features"])
            parts.append(f"주요 특징: {features}")
        
        if product_info.get("keywords"):
            keywords = ", ".join(product_info["keywords"])
            parts.append(f"관련 키워드: {keywords}")
        
        return " ".join(parts)
    
    def _calculate_relevance_score(self, query: str, text: str) -> float:
        """간단한 관련도 점수 계산"""
        query_lower = query.lower()
        text_lower = text.lower()
        
        # 완전 일치
        if query_lower == text_lower:
            return 1.0
        
        # 포함 여부
        if query_lower in text_lower:
            return 0.8
        
        # SequenceMatcher 유사도
        return SequenceMatcher(None, query_lower, text_lower).ratio()
    
    def extract_product_facts_from_conversation(
        self, 
        conversation: List[Dict],
        use_llm_extraction: Optional[bool] = None
    ) -> List[Dict]:
        """
        대화에서 제품 관련 사실(Fact) 추출
        
        **추출 방식:**
        - LLM 기반 추출 (기본, use_llm=True): 문맥 이해, 다양한 표현 처리
        - 정규식 기반 추출 (fallback, use_llm=False): 빠른 처리, 패턴 기반
        
        Args:
            conversation: [{"role": "employee"|"customer", "text": "..."}]
            use_llm_extraction: LLM 기반 추출 사용 여부 (None이면 인스턴스 설정 따름)
        
        Returns:
            [
                {
                    "claim": "정기예금 금리는 연 2.5%입니다",
                    "product_code": "DEP-TIM",
                    "category": "금리",
                    "matched_value": "2.5"
                }
            ]
        """
        # LLM 사용 여부 결정
        should_use_llm = use_llm_extraction if use_llm_extraction is not None else self.use_llm
        
        employee_utterances = [msg["text"] for msg in conversation if msg.get("role") == "employee"]
        
        if not employee_utterances:
            return []
        
        # 🎯 LLM 기반 추출 (기본)
        if should_use_llm and self.openai_client:
            return self._extract_facts_with_llm(employee_utterances, conversation)
        else:
            # 정규식 기반 추출 (fallback)
            return self._extract_facts_with_regex(employee_utterances)
    
    def _extract_facts_with_llm(self, employee_utterances: List[str], conversation: List[Dict]) -> List[Dict]:
        """
        LLM 기반 사실 추출 (상품 코드 감지 우선)
        
        장점:
        - 문맥 이해: "10만원"과 "100000원"을 같은 값으로 인식
        - 다양한 표현 처리: "연 2.5%", "연이율 2.5퍼센트" 등
        - 카테고리 자동 분류: 금리, 한도, 수수료 등
        - 대화 문맥 고려: 이전 대화에서 언급된 상품을 추론
        - LLM 기반 상품 코드 직접 추론 (키워드 매칭보다 우선)
        """
        facts = []
        
        # 제품별 키워드 매핑 (fallback용)
        product_keywords = self._get_product_keywords()
        
        # 모든 직원 발화를 하나의 텍스트로 결합
        combined_text = " ".join(employee_utterances)
        
        # 🆕 대화 히스토리 구성 (문맥 정보 제공)
        conversation_context = self._format_conversation_for_llm(conversation)
        
        # 🆕 상품 코드 리스트와 키워드 정보를 LLM에 제공 (상품 코드 직접 추론 지원)
        product_codes_list = list(product_keywords.keys())
        product_info_text = "\n".join([
            f"- {code}: {', '.join(keywords[:5])}"  # 각 상품의 주요 키워드
            for code, keywords in list(product_keywords.items())[:20]  # 상위 20개 상품
        ])
        
        # LLM 프롬프트 구성
        categories_list = list(self.category_patterns.keys())
        prompt = f"""다음은 은행 직원과 고객의 대화입니다. 제품 관련 정보(금리, 한도, 수수료, 기간 등)를 추출해주세요.

**대화 히스토리 (문맥 참고용):**
{conversation_context}

**현재 직원 발화:**
{combined_text}

**사용 가능한 상품 코드 리스트:**
{', '.join(product_codes_list[:30])}  # 상위 30개 상품 코드

**상품 키워드 참고 (상품 코드 추론용):**
{product_info_text}

**⚠️ 중요: 문맥 기반 상품 코드 추론 (우선순위)**
1. **🚨 최우선: 대화 히스토리에서 이전에 언급된 상품 확인**
   - 대화 히스토리를 역순으로 확인하여 가장 최근에 언급된 상품을 우선적으로 사용하세요
   - 예: 고객이 "정기예금"을 언급했고, 직원이 "금리는 연 2.15%입니다"라고 말했다면
   - → 정기예금(DEP-TIM)의 금리로 추론 (다른 상품의 12개월 금리와 겹치더라도!)
   - **여러 상품에 동일한 수치가 있어도, 대화 히스토리에서 언급된 상품을 우선 선택하세요**
2. **현재 발화 분석**: 현재 발화에서 직접 언급된 상품을 확인하세요
3. **문맥 추론**: 현재 발화에 상품명이 없어도 이전 대화에서 언급된 상품을 참고하여 추론하세요
4. **🚨 수치 정보 기반 추론 (대화 히스토리에 상품 언급이 없을 때만)**: 
   - 카테고리(금리, 한도, 수수료 등)와 수치 정보를 조합하여 상품을 추론하세요
   - **주의**: 여러 상품에 동일한 수치가 있을 수 있습니다 (예: 정기예금 12개월 2.15%, 자유적금 12개월 2.80%)
   - 이 경우 대화 히스토리에서 언급된 상품이 없으면, 가장 가능성 높은 상품을 선택하거나 여러 상품을 리스트로 제공하세요
   - 예: "금리 연 2.15%" + "12개월" → 대화 히스토리에 "정기예금" 언급이 있으면 DEP-TIM, 없으면 DEP-TIM 우선 고려
   - 예: "대출 한도 최대 10억원" + "주택 담보" → 주택담보대출(LON-MTG)로 추론
   - 예: "연회비 10만원" → 신용카드(CRD-DEB, CRD-CRE 등)로 추론
5. **상품 코드 직접 추론**: inferred_product_code 필드에 상품 코드를 직접 명시하세요 (예: "DEP-TIM", "LON-MTG")
   - 상품 코드 리스트에서 가장 적합한 코드를 선택하세요
   - 여러 상품이 관련되면 리스트로 제공하세요 (예: ["DEP-TIM", "SAV-FRE"])
   - **명시적 키워드가 없어도 수치와 카테고리로 추론 가능합니다!**

**추출할 카테고리:**
{', '.join(categories_list)}

**추출 규칙:**
1. **문맥 기반 상품 추론**: 현재 발화에 상품명이 없어도 대화 히스토리에서 언급된 상품을 참고하여 추론
   - 예: 고객 "정기예금에 대해 알고 싶어요" → 직원 "금리는 연 2.5%입니다" → 정기예금의 금리로 추출
2. 각 카테고리별로 언급된 정보를 추출
3. 수치는 정확히 추출하되, 단위를 고려하여 정규화:
   - "10만원" → value: "100000", unit: "원"
   - "2.5%" → value: "2.5", unit: "%"
   - "5천만원" → value: "50000000", unit: "원"
   - "1억원" → value: "100000000", unit: "원"
4. 카테고리 분류: {', '.join(categories_list)}
5. claim은 발화에서 해당 정보가 언급된 원문 그대로 (문장 또는 문구)
6. 수치가 없는 경우(예: "혜택", "조건") value는 빈 문자열, unit도 빈 문자열

**출력 형식 (JSON):**
{{
  "facts": [
    {{
      "category": "금리",
      "claim": "연 2.5%",
      "value": "2.5",
      "unit": "%",
      "inferred_product_code": "DEP-TIM"  // 🆕 문맥에서 추론한 상품 코드 (우선)
    }},
    {{
      "category": "수수료",
      "claim": "연회비는 연 10만원",
      "value": "100000",
      "unit": "원",
      "inferred_product_code": "CRD-DEB"  // 🆕 문맥에서 추론한 상품 코드 (우선)
    }},
    {{
      "category": "한도",
      "claim": "최대 1억원까지 가능합니다",
      "value": "100000000",
      "unit": "원",
      "inferred_product_code": ["DEP-TIM", "SAV-FRE"]  // 🆕 여러 상품 관련 시 리스트
    }}
  ]
}}

**⚠️ 중요:**
- **🚨 최우선: 대화 히스토리에서 이전에 언급된 상품을 먼저 확인하세요!**
  - 여러 상품에 동일한 수치가 있어도, 대화 히스토리에서 언급된 상품을 우선 선택하세요
  - 예: "12개월 금리 2.15%"는 정기예금(DEP-TIM), 자유적금(SAV-FRE), 정기적금(SAV-FIX) 모두에 있을 수 있지만
  - 대화 히스토리에서 "정기예금"이 언급되었다면 → DEP-TIM을 선택하세요
- inferred_product_code는 대화 히스토리와 현재 발화를 종합 분석하여 추론하세요
- **명시적 키워드가 없어도 수치 정보(금리, 한도, 수수료 등)와 카테고리를 조합하여 추론하세요**
- 상품 코드 리스트에서 가장 적합한 코드를 선택하세요
- 여러 상품이 관련되면 배열로 제공하세요 (예: ["DEP-TIM", "SAV-FRE"])
- 상품을 추론할 수 없으면 inferred_product_code 필드를 생략하세요 (하지만 최대한 추론을 시도하세요!)
- 상품 코드는 정확히 일치해야 합니다 (예: "DEP-TIM", "LON-MTG")

JSON만 출력하세요 (코드 블록 없이):"""

        try:
            print(f"🔍 [LLM 추출] 시작: 직원 발화 {len(employee_utterances)}개, 대화 턴 {len(conversation)}개")
            print(f"🔍 [LLM 추출] 사용 가능한 상품 코드 수: {len(product_codes_list)}개")
            print(f"🔍 [LLM 추출] 대화 히스토리 길이: {len(conversation_context)}자")
            
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",  # 빠른 응답을 위해 mini 사용
                messages=[
                    {"role": "system", "content": "당신은 은행 상품 정보 추출 전문가입니다. 정확하고 구조화된 JSON만 출력하세요."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,  # 일관성 향상
                max_tokens=1000
            )
            
            response_text = response.choices[0].message.content.strip()
            print(f"🔍 [LLM 추출] LLM 응답 받음: {len(response_text)}자")
            print(f"🔍 [LLM 추출] LLM 응답 일부: {response_text[:300]}...")
            
            # JSON 파싱 (안전한 파싱)
            # JSON 코드 블록 제거
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                # ```로 시작하는 코드 블록 제거
                parts = response_text.split("```")
                if len(parts) >= 2:
                    response_text = parts[1].strip()
                    if response_text.startswith("json"):
                        response_text = response_text[4:].strip()
            
            # JSON 파싱 시도
            try:
                llm_result = json.loads(response_text)
                print(f"✅ [LLM 추출] JSON 파싱 성공: facts {len(llm_result.get('facts', []))}개")
            except json.JSONDecodeError:
                # JSON 파싱 실패 시 마지막 시도: 중괄호로 감싸진 부분만 추출
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    response_text = json_match.group(0)
                    llm_result = json.loads(response_text)
                    print(f"✅ [LLM 추출] JSON 파싱 성공 (재시도): facts {len(llm_result.get('facts', []))}개")
                else:
                    raise
            
            # LLM 결과를 fact 형식으로 변환
            for i, fact_data in enumerate(llm_result.get("facts", [])):
                category = fact_data.get("category", "")
                claim = fact_data.get("claim", "")
                value = fact_data.get("value", "")
                
                # 🆕 LLM이 추론한 상품 코드 (우선 사용)
                inferred_product_code = fact_data.get("inferred_product_code", None)
                
                print(f"🔍 [LLM 추출] Fact {i+1}: category={category}, claim={claim[:50]}..., inferred_product_code={inferred_product_code}")
                
                if not category or not claim:
                    print(f"⚠️ [LLM 추출] Fact {i+1} 건너뜀: category 또는 claim이 비어있음")
                    continue
                
                # 🆕 LLM 기반 상품 코드 추론 우선 사용
                final_product_codes = []
                
                # 1. LLM이 추론한 상품 코드 사용 (우선순위 1)
                if inferred_product_code:
                    print(f"🔍 [LLM 추출] Fact {i+1}: LLM이 추론한 상품 코드 발견: {inferred_product_code} (타입: {type(inferred_product_code).__name__})")
                    if isinstance(inferred_product_code, list):
                        # 여러 상품 코드 리스트
                        final_product_codes = [code for code in inferred_product_code if code in product_codes_list]
                        print(f"🔍 [LLM 추출] Fact {i+1}: 리스트에서 유효한 상품 코드: {final_product_codes}")
                    elif isinstance(inferred_product_code, str):
                        # 단일 상품 코드
                        if inferred_product_code in product_codes_list:
                            final_product_codes = [inferred_product_code]
                            print(f"🔍 [LLM 추출] Fact {i+1}: 단일 상품 코드 유효: {final_product_codes}")
                        else:
                            print(f"⚠️ [LLM 추출] Fact {i+1}: LLM이 추론한 상품 코드 '{inferred_product_code}'가 유효한 상품 코드 리스트에 없음")
                else:
                    print(f"⚠️ [LLM 추출] Fact {i+1}: LLM이 inferred_product_code를 제공하지 않음")
                
                # 2. LLM 추론 실패 시 키워드 매칭 사용 (fallback)
                if not final_product_codes:
                    print(f"⚠️ [LLM 추출] Fact {i+1}: LLM 추론 실패, 키워드 매칭 fallback 사용")
                    # 대화 히스토리에서 언급된 상품 추적 (문맥 기반)
                    context_mentioned_products = self._extract_products_from_conversation_context(conversation, product_keywords)
                    print(f"🔍 [LLM 추출] Fact {i+1}: 문맥에서 발견된 상품: {context_mentioned_products}")
                    
                    # 현재 발화에서 언급된 제품 감지
                    current_mentioned_products = []
                    for product_code, keywords in product_keywords.items():
                        if any(keyword in combined_text for keyword in keywords):
                            current_mentioned_products.append(product_code)
                    print(f"🔍 [LLM 추출] Fact {i+1}: 현재 발화에서 발견된 상품: {current_mentioned_products}")
                    
                    # 문맥과 현재 발화를 결합
                    final_product_codes = list(set(context_mentioned_products + current_mentioned_products))
                
                # 3. 상품 코드가 없으면 UNKNOWN
                if not final_product_codes:
                    print(f"⚠️ [LLM 추출] Fact {i+1}: 상품 코드를 찾지 못함 → UNKNOWN")
                    final_product_codes = ["UNKNOWN"]
                else:
                    print(f"✅ [LLM 추출] Fact {i+1}: 최종 상품 코드: {final_product_codes}")
                
                fact = {
                    "claim": claim,
                    "full_utterance": combined_text,
                    "product_codes": final_product_codes,
                    "category": category,
                    "matched_value": value,
                    "inferred_product_code": inferred_product_code if inferred_product_code else None  # 🆕 LLM 추론 상품 코드 저장
                }
                facts.append(fact)
            
            print(f"✅ LLM 기반 추출 완료: {len(facts)}개 사실 발견")
            
        except json.JSONDecodeError as e:
            print(f"⚠️ LLM 응답 JSON 파싱 실패: {e}")
            print(f"응답 내용: {response_text[:200]}")
            # LLM 실패 시 정규식으로 fallback
            return self._extract_facts_with_regex(employee_utterances, conversation)
        except Exception as e:
            print(f"⚠️ LLM 추출 실패: {e}")
            # LLM 실패 시 정규식으로 fallback
            return self._extract_facts_with_regex(employee_utterances, conversation)
        
        return facts
    
    def _extract_products_from_conversation_context(self, conversation: List[Dict], product_keywords: Dict[str, List[str]]) -> List[str]:
        """
        대화 히스토리에서 언급된 상품 코드 추출 (문맥 기반)
        
        Args:
            conversation: 전체 대화 히스토리
            product_keywords: 상품별 키워드 매핑
        
        Returns:
            언급된 상품 코드 리스트
        """
        mentioned_products = []
        all_text = " ".join([msg.get("text", "") for msg in conversation])
        
        for product_code, keywords in product_keywords.items():
            if any(keyword in all_text for keyword in keywords):
                if product_code not in mentioned_products:
                    mentioned_products.append(product_code)
        
        return mentioned_products
    
    def _format_conversation_for_llm(self, conversation: List[Dict], max_turns: int = 10) -> str:
        """
        대화 히스토리를 LLM 프롬프트용 텍스트로 포맷팅
        
        Args:
            conversation: 대화 히스토리
            max_turns: 최대 포함할 턴 수 (최근 대화 우선)
        
        Returns:
            포맷팅된 대화 텍스트
        """
        if not conversation:
            return "대화 히스토리가 없습니다."
        
        # 최근 대화만 포함 (너무 길어지지 않도록)
        recent_conversation = conversation[-max_turns:] if len(conversation) > max_turns else conversation
        
        formatted_lines = []
        for i, msg in enumerate(recent_conversation, 1):
            role = msg.get("role", "unknown")
            text = msg.get("text", "")
            
            # 🆕 상품 코드 정보 추출 (직원 턴에 포함된 경우)
            product_code = msg.get("product_code") or msg.get("productCode") or None
            
            if role == "employee":
                if product_code:
                    formatted_lines.append(f"[직원 {i} {product_code}]: {text}")
                else:
                    formatted_lines.append(f"[직원 {i}]: {text}")
            elif role == "customer":
                formatted_lines.append(f"[고객 {i}]: {text}")
            else:
                formatted_lines.append(f"[{role} {i}]: {text}")
        
        return "\n".join(formatted_lines)
    
    def _extract_facts_with_regex(self, employee_utterances: List[str], conversation: Optional[List[Dict]] = None) -> List[Dict]:
        """
        정규식 기반 사실 추출 (fallback)
        
        기존 정규식 패턴 기반 추출 로직
        문맥 기반 상품 추출 지원 추가
        """
        facts = []
        
        # 제품별 키워드 매핑 (캐시 우선, 없으면 하드코딩)
        product_keywords = self._get_product_keywords()
        
        # 🆕 대화 히스토리에서 언급된 상품 추적 (문맥 기반)
        context_mentioned_products = []
        if conversation:
            context_mentioned_products = self._extract_products_from_conversation_context(conversation, product_keywords)
        
        # 상품별 중요 정보 카테고리 (캐시 우선, 없으면 하드코딩)
        product_category_priority = self._get_product_category_priority()
        
        # 정보 카테고리 패턴 (구성에서 로드)
        category_patterns = self.category_patterns
        
        for utterance in employee_utterances:
            # 현재 발화에서 언급된 제품 감지
            current_mentioned_products = []
            for product_code, keywords in product_keywords.items():
                if any(keyword in utterance for keyword in keywords):
                    current_mentioned_products.append(product_code)
            
            # 🆕 문맥과 현재 발화를 결합 (중복 제거)
            mentioned_products = list(set(context_mentioned_products + current_mentioned_products))
            
            # 상품별 우선순위 카테고리 결정
            # 언급된 상품이 있으면 해당 상품의 우선 카테고리만, 없으면 모든 카테고리 검사
            categories_to_check = set()
            if mentioned_products:
                for product_code in mentioned_products:
                    if product_code in product_category_priority:
                        categories_to_check.update(product_category_priority[product_code])
            else:
                # 🆕 문맥에서 상품이 감지되었지만 현재 발화에 없으면, 문맥 상품의 카테고리 사용
                if context_mentioned_products:
                    for product_code in context_mentioned_products:
                        if product_code in product_category_priority:
                            categories_to_check.update(product_category_priority[product_code])
                # 문맥에도 없으면 모든 카테고리 검사
                if not categories_to_check:
                    categories_to_check = set(category_patterns.keys())
            
            # 정보 카테고리 추출 (우선순위 카테고리만)
            for category in categories_to_check:
                if category not in category_patterns:
                    continue
                patterns = category_patterns[category]
                for pattern in patterns:
                    matches = re.finditer(pattern, utterance)
                    for match in matches:
                        # claim 추출: 매칭된 부분의 앞뒤 문맥을 포함하여 더 정확한 claim 생성
                        matched_text = match.group(0)
                        match_start = match.start()
                        match_end = match.end()
                        
                        # 앞뒤로 최대 10글자씩 포함하여 문맥 보존
                        context_start = max(0, match_start - 10)
                        context_end = min(len(utterance), match_end + 10)
                        claim_with_context = utterance[context_start:context_end].strip()
                        
                        # claim은 매칭된 부분을 포함하되, 문맥이 있으면 문맥 포함
                        # 단, 너무 길면 매칭된 부분만 사용
                        if len(claim_with_context) <= 50:
                            claim = claim_with_context
                        else:
                            claim = matched_text
                        
                        # 🆕 문맥에서 상품이 감지되었지만 현재 발화에 없으면, 문맥 상품 사용
                        final_product_codes = mentioned_products if mentioned_products else (context_mentioned_products if context_mentioned_products else ["UNKNOWN"])
                        
                        fact = {
                            "claim": claim,
                            "full_utterance": utterance,
                            "product_codes": final_product_codes,
                            "category": category,
                            "matched_value": match.group(1) if match.lastindex and match.lastindex >= 1 else None
                        }
                        facts.append(fact)
        
        return facts
    
    def verify_fact_accuracy(
        self, 
        claim: str,
        product_code: str,
        category: str,
        use_llm: Optional[bool] = None
    ) -> ProductFactCheck:
        """
        제품 정보 사실 확인 (RAG 기반 2단계 검증)
        
        1단계 (항상 수행): RAG 검색 (벡터 검색 우선) + Semantic Similarity
           - 🎯 벡터 검색 시도 (pgvector 기반, RAG 검색)
           - 벡터 검색 실패 시 키워드 검색으로 fallback
           - 의미적 유사도 계산 (임베딩 또는 SequenceMatcher)
           - 숫자 정확도 비교
           - 휴리스틱 정확도 판단
        
        2단계 (선택적): LLM Verification
           - LLM이 사용 가능하고 성공하면 → LLM 결과를 최종 판단으로 사용
           - LLM이 없거나 실패하면 → 1단계의 휴리스틱 결과를 최종 판단으로 사용
        
        verification_method는 최종 판단에 사용된 방법을 나타냅니다:
        - "llm": LLM 검증 성공 → LLM 결과 사용
        - "vector_semantic": 벡터 검색 사용 + 임베딩 유사도 → 휴리스틱 결과 사용
        - "vector_keyword": 벡터 검색 사용 + SequenceMatcher → 휴리스틱 결과 사용
        - "semantic": 키워드 검색 사용 + 임베딩 유사도 → 휴리스틱 결과 사용
        - "keyword": 키워드 검색 사용 + SequenceMatcher → 휴리스틱 결과 사용
        
        Args:
            claim: 검증할 주장 (예: "금리는 연 2.5%입니다")
            product_code: 제품 코드
            category: 정보 카테고리 (금리, 한도 등)
            use_llm: LLM 검증 사용 여부 (None이면 인스턴스 설정 따름)
        
        Returns:
            팩트 체크 결과
        """
        # LLM 사용 여부 결정
        should_use_llm = use_llm if use_llm is not None else self.use_llm
        
        # full_utterance는 fact에서 가져오기 (batch_verify_conversation에서 전달)
        # 여기서는 None으로 설정하고, batch_verify_conversation에서 설정
        full_utterance = getattr(self, '_current_full_utterance', None)
        
        # 🎯 RAG 검색: 벡터 검색을 우선 사용 (pgvector 기반)
        relevant_chunks = None
        verification_method_base = "keyword"  # 기본값
        
        # 🔍 디버깅: 검증 시작 로그
        print(f"🔍 [검증 시작] claim='{claim[:50]}...', product_code={product_code}, category={category}")
        
        # 🚨 UNKNOWN일 때 문맥에서 상품 코드 추론 시도
        original_product_code = product_code
        if product_code == "UNKNOWN":
            print(f"⚠️ [검증] product_code가 UNKNOWN, 문맥에서 상품 코드 추론 시도")
            # full_utterance나 conversation에서 상품 코드 추론
            if hasattr(self, '_current_full_utterance') and self._current_full_utterance:
                # 키워드 매칭으로 상품 코드 추론
                product_keywords = self._get_product_keywords()
                utterance_text = self._current_full_utterance
                
                for code, keywords in product_keywords.items():
                    if any(keyword in utterance_text for keyword in keywords):
                        print(f"✅ [검증] 문맥에서 상품 코드 추론: {code}")
                        product_code = code
                        break
            
            # 🚨 추론 실패 시 claim 자체에서도 상품 코드 추론 시도
            if product_code == "UNKNOWN":
                print(f"⚠️ [검증] full_utterance에서 추론 실패, claim에서 상품 코드 추론 시도")
                product_keywords = self._get_product_keywords()
                for code, keywords in product_keywords.items():
                    if any(keyword in claim for keyword in keywords):
                        print(f"✅ [검증] claim에서 상품 코드 추론: {code}")
                        product_code = code
                        break
        
        # 🚨 UNKNOWN이면 벡터 검색 건너뛰기 (다른 상품 정보와 혼동 방지)
        # 하지만 문맥에서 추론한 상품 코드가 있으면 그것을 사용하여 검증 수행
        if product_code == "UNKNOWN":
            print(f"⚠️ [검증] product_code가 여전히 UNKNOWN, 벡터 검색 건너뜀 (다른 상품 정보 혼동 방지)")
            print(f"   → 이 claim은 검증되지 않음 (상품 코드를 추론할 수 없음)")
            return ProductFactCheck(
                claim=claim,
                ground_truth="",
                is_accurate=False,
                similarity_score=0.0,
                product_code=original_product_code,  # 원래 UNKNOWN 유지
                category=category,
                verification_method="unknown_product",
                full_utterance=full_utterance
            )
        
        # 1단계: 벡터 검색 시도 (RAG 검색)
        # 🚨 중요: product_code 필터를 반드시 적용하여 해당 상품의 정보만 검색
        if self.use_vector_search:
            filter_product_codes = [product_code]  # UNKNOWN은 이미 처리됨
            print(f"🔍 [벡터 검색] 시도: product_code={filter_product_codes}, threshold=0.3")
            
            vector_chunks = self.search_by_vector_similarity(
                query=claim,
                category=None,  # 카테고리 필터 제거: 전체 상품에서 검색하여 정확도 유지
                product_codes=filter_product_codes,  # 🚨 상품 코드 필터 필수 적용
                top_k=3,
                similarity_threshold=0.3  # 유사도 임계값 (0.5에서 0.3으로 낮춤 - 진단 결과 기반)
            )
            
            if vector_chunks:
                # 🔍 검색된 청크의 상품 코드 확인
                found_product_codes = [chunk.get("product_code", "UNKNOWN") for chunk in vector_chunks]
                print(f"✅ [벡터 검색] 성공: {len(vector_chunks)}개 청크 발견, 상품 코드: {found_product_codes}")
                
                # 🚨 검색된 청크가 요청한 상품 코드와 일치하는지 확인
                if product_code != "UNKNOWN":
                    mismatched = [code for code in found_product_codes if code != product_code]
                    if mismatched:
                        print(f"⚠️ [벡터 검색] 경고: 다른 상품 코드 발견! 요청: {product_code}, 발견: {mismatched}")
                        # 다른 상품 코드는 제외
                        vector_chunks = [chunk for chunk in vector_chunks if chunk.get("product_code") == product_code]
                        print(f"🔍 [벡터 검색] 필터링 후: {len(vector_chunks)}개 청크")
                
                relevant_chunks = vector_chunks
                verification_method_base = "vector"  # 벡터 검색 사용
            else:
                print(f"⚠️ [벡터 검색] 결과 없음, 키워드 검색으로 fallback (product_code={product_code})")
        
        # 2단계: 벡터 검색 실패 시 키워드 검색 (fallback)
        if not relevant_chunks:
            filter_product_codes = [product_code] if product_code != "UNKNOWN" else None
            print(f"🔍 [키워드 검색] 시도: product_code={filter_product_codes}")
            
            relevant_chunks = self.search_by_keyword(
                query=claim,
                category=category,
                product_codes=filter_product_codes,  # 🚨 상품 코드 필터 필수 적용
                top_k=3
            )
            
            if relevant_chunks:
                # 🔍 검색된 청크의 상품 코드 확인
                found_product_codes = [chunk.get("product_code", "UNKNOWN") for chunk in relevant_chunks]
                print(f"✅ [키워드 검색] 성공: {len(relevant_chunks)}개 청크 발견, 상품 코드: {found_product_codes}")
                
                # 🚨 검색된 청크가 요청한 상품 코드와 일치하는지 확인
                if product_code != "UNKNOWN":
                    mismatched = [code for code in found_product_codes if code != product_code]
                    if mismatched:
                        print(f"⚠️ [키워드 검색] 경고: 다른 상품 코드 발견! 요청: {product_code}, 발견: {mismatched}")
                        # 다른 상품 코드는 제외
                        relevant_chunks = [chunk for chunk in relevant_chunks if chunk.get("product_code") == product_code]
                        print(f"🔍 [키워드 검색] 필터링 후: {len(relevant_chunks)}개 청크")
        
        if not relevant_chunks:
            return ProductFactCheck(
                claim=claim,
                ground_truth="",
                is_accurate=False,
                similarity_score=0.0,
                product_code=product_code,
                category=category,
                verification_method=verification_method_base,
                full_utterance=full_utterance
            )
        
        # === 1단계: RAG 검색 결과 분석 ===
        if not relevant_chunks:
            print(f"❌ [검증 실패] 관련 청크 없음: product_code={product_code}, claim='{claim[:50]}...'")
            return ProductFactCheck(
                claim=claim,
                ground_truth="",
                is_accurate=False,
                similarity_score=0.0,
                product_code=product_code,
                category=category,
                verification_method=verification_method_base,
                full_utterance=full_utterance
            )
        
        best_chunk = relevant_chunks[0]
        best_chunk_text = best_chunk.get("text", "")
        best_chunk_product_code = best_chunk.get("product_code", "UNKNOWN")
        
        # 🔍 최종 사용된 청크의 상품 코드 확인
        print(f"🔍 [검증 진행] 사용할 청크: product_code={best_chunk_product_code}, breadcrumb={best_chunk.get('breadcrumb', '')[:50]}...")
        print(f"🔍 [검증 진행] 사용할 청크 텍스트 일부: {best_chunk_text[:200]}...")
        print(f"🔍 [검증 진행] 검증할 claim: {claim[:100]}...")
        
        # 🚨 상품 코드 불일치 경고
        if product_code != "UNKNOWN" and best_chunk_product_code != product_code:
            print(f"❌ [검증 오류] 상품 코드 불일치! 요청: {product_code}, 사용: {best_chunk_product_code}")
        
        # 벡터 검색 결과에는 이미 similarity가 포함되어 있음
        if verification_method_base == "vector" and "similarity" in best_chunk:
            # 벡터 검색 결과의 유사도 사용 (이미 코사인 유사도로 계산됨)
            similarity_score = float(best_chunk.get("similarity", 0.0))
            print(f"  📊 벡터 검색 유사도: {similarity_score:.3f}")
        else:
            # 키워드 검색 결과인 경우 유사도 계산
            similarity_score = self._semantic_similarity(claim, best_chunk_text)
            print(f"  📊 키워드 검색 후 유사도 계산: {similarity_score:.3f}")
        
        # === 🚨 중요: 숫자 정보 추출 및 정확도 비교 (필수) ===
        claim_numbers = self._extract_numbers(claim)
        truth_numbers = self._extract_numbers(best_chunk_text)
        
        # 숫자 정확도 검증 (숫자가 있으면 반드시 비교)
        numbers_match = True
        if claim_numbers and truth_numbers:
            # 주장과 정답 모두에 숫자가 있는 경우: 정확히 일치해야 함
            # 허용 오차: 0.01 (소수점 둘째 자리까지 정확)
            # 빈 문자열 필터링
            claim_numbers_clean = [n for n in claim_numbers if n.strip()]
            truth_numbers_clean = [n for n in truth_numbers if n.strip()]
            
            if claim_numbers_clean and truth_numbers_clean:
                numbers_match = any(
                    abs(float(claim_num) - float(truth_num)) < 0.01
                    for claim_num in claim_numbers_clean
                    for truth_num in truth_numbers_clean
                )
            else:
                # 숫자가 추출되었지만 빈 문자열인 경우: 비교 불가
                numbers_match = False
        elif claim_numbers and not truth_numbers:
            # 주장에만 숫자가 있고 정답에 없으면: 부정확 (숫자 정보가 잘못되었을 가능성)
            numbers_match = False
        elif not claim_numbers and truth_numbers:
            # 주장에 숫자가 없고 정답에 있으면: 정보 부족 (부정확으로 간주)
            numbers_match = False
        
        # === 초기 정확도 판단 (숫자 정확도 우선) ===
        if claim_numbers or truth_numbers:
            # 숫자가 있는 경우: 숫자 정확도가 최우선
            # 숫자가 다르면 유사도가 높아도 부정확
            is_accurate_heuristic = numbers_match
            if not numbers_match:
                # 숫자가 다르면 유사도 점수도 낮춤 (명확한 오류)
                similarity_score = min(similarity_score, 0.5)
        else:
            # 숫자가 없는 경우: 유사도만으로 판단
            # 임베딩 사용 시: 0.75 이상, SequenceMatcher 사용 시: 0.7 이상
            threshold = 0.75 if self.use_embedding else 0.7
            is_accurate_heuristic = similarity_score >= threshold
        
        # === 2단계: LLM Verification (선택) ===
        if should_use_llm and self.openai_client:
            llm_result = self._verify_with_llm(claim, best_chunk_text, category, product_code)
            
            if llm_result["success"]:
                # LLM 결과 우선 사용
                return ProductFactCheck(
                    claim=claim,
                    ground_truth=best_chunk_text,
                    is_accurate=llm_result["is_accurate"],
                    similarity_score=llm_result["confidence"],
                    product_code=product_code,
                    category=category,
                    verification_method="llm",
                    llm_reasoning=llm_result["reasoning"],
                    full_utterance=full_utterance
                )
        
        # LLM 사용 안 하거나 실패 시 휴리스틱 결과 사용
        # verification_method 결정: 벡터 검색 사용 여부에 따라
        if verification_method_base == "vector":
            # 벡터 검색 사용 + 임베딩 유사도 계산
            final_method = "vector_semantic" if self.use_embedding else "vector_keyword"
        else:
            # 키워드 검색 사용
            final_method = "semantic" if self.use_embedding else "keyword"
        
        return ProductFactCheck(
            claim=claim,
            ground_truth=best_chunk_text,
            is_accurate=is_accurate_heuristic,
            similarity_score=similarity_score,
            product_code=product_code,
            category=category,
            verification_method=final_method,
            full_utterance=full_utterance
        )
    
    def _verify_with_llm(
        self, 
        claim: str, 
        ground_truth: str, 
        category: str,
        product_code: str
    ) -> Dict:
        """
        LLM 기반 사실 검증
        
        Args:
            claim: 사용자 주장
            ground_truth: 제품 지식 베이스의 정답
            category: 정보 카테고리
            product_code: 제품 코드
        
        Returns:
            {
                "success": True,
                "is_accurate": True/False,
                "confidence": 0.95,
                "reasoning": "..."
            }
        """
        try:
            prompt = f"""제품 정보 사실 검증을 수행하세요.

**제품 코드:** {product_code}
**카테고리:** {category}

**사용자 주장 (Claim):**
{claim}

**제품 지식 베이스 정보 (Ground Truth):**
{ground_truth}

**🚨 중요한 검증 지침:**
1. **사용자가 실제로 언급한 내용만 평가하세요!**
   - 사용자 주장(Claim)에 포함된 정보만 검증 대상입니다
   - Ground Truth에 있지만 사용자가 언급하지 않은 정보는 평가하지 마세요
   - 예: Ground Truth에 "연회비"가 있지만 사용자가 "수수료"만 언급했다면, "수수료"만 평가하세요

2. **숫자 정보 검증:**
   - 금리, 한도, 수수료 등 숫자는 정확히 일치해야 함
   - 약간의 오차도 부정확으로 판단

3. **의미적 동일성 판단:**
   - 표현이 다르더라도 의미가 같으면 정확하다고 판단
   - 예: "연 2.5%" = "연간 2.5%" (정확함)

4. **불확실한 표현:**
   - "같아요", "아마도", "대략" 등 모호한 표현은 부정확으로 판단

**출력 형식 (JSON):**
{{
  "is_accurate": true/false,
  "confidence": 0.0~1.0,
  "reasoning": "판단 근거 설명 (사용자가 실제로 언급한 내용을 기준으로 설명)"
}}

JSON으로만 응답하세요."""

            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "당신은 은행 제품 정보 검증 전문가입니다. 사용자 주장과 실제 제품 정보를 비교하여 정확성을 판단합니다."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,
                max_tokens=500,
                response_format={"type": "json_object"}
            )
            
            result_text = response.choices[0].message.content
            result = json.loads(result_text)
            
            return {
                "success": True,
                "is_accurate": result.get("is_accurate", False),
                "confidence": result.get("confidence", 0.0),
                "reasoning": result.get("reasoning", "")
            }
            
        except Exception as e:
            print(f"⚠️ LLM 검증 실패: {e}")
            return {
                "success": False,
                "is_accurate": False,
                "confidence": 0.0,
                "reasoning": f"LLM 검증 오류: {str(e)}"
            }
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """
        코사인 유사도 계산
        
        Args:
            vec1: 첫 번째 벡터 (임베딩 벡터)
            vec2: 두 번째 벡터 (임베딩 벡터)
        
        Returns:
            유사도 점수 (0.0 ~ 1.0)
        
        알고리즘:
            cosine_similarity = (vec1 · vec2) / (||vec1|| × ||vec2||)
        """
        if not NUMPY_AVAILABLE:
            # NumPy 없으면 간단한 계산
            dot_product = sum(a * b for a, b in zip(vec1, vec2))
            norm_a = sum(a * a for a in vec1) ** 0.5
            norm_b = sum(b * b for b in vec2) ** 0.5
        else:
            # NumPy 사용 (더 빠름)
            a = np.array(vec1)
            b = np.array(vec2)
            dot_product = np.dot(a, b)
            norm_a = np.linalg.norm(a)
            norm_b = np.linalg.norm(b)
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        similarity = dot_product / (norm_a * norm_b)
        # 임베딩은 보통 0~1 범위이지만, 음수 나올 수 있으므로 클리핑
        return max(0.0, min(1.0, similarity))
    
    def _semantic_similarity_embedding(self, text1: str, text2: str) -> float:
        """
        임베딩 기반 의미적 유사도 계산
        
        Args:
            text1: 첫 번째 텍스트
            text2: 두 번째 텍스트
        
        Returns:
            유사도 점수 (0.0 ~ 1.0)
        
        프로세스:
            1. 텍스트를 임베딩 벡터로 변환 (캐시 활용)
            2. 코사인 유사도 계산
        """
        try:
            # 캐시에서 임베딩 가져오기 (성능 최적화)
            if text1 not in self.embedding_cache:
                self.embedding_cache[text1] = embed_text_sync(text1)
            if text2 not in self.embedding_cache:
                self.embedding_cache[text2] = embed_text_sync(text2)
            
            vec1 = self.embedding_cache[text1]
            vec2 = self.embedding_cache[text2]
            
            # 코사인 유사도 계산
            return self._cosine_similarity(vec1, vec2)
        except Exception as e:
            print(f"⚠️ 임베딩 계산 실패: {e}")
            raise
    
    def _semantic_similarity(self, text1: str, text2: str) -> float:
        """
        의미적 유사도 계산
        
        우선순위:
        1. 임베딩 기반 (가능하면)
        2. SequenceMatcher (fallback)
        
        Args:
            text1: 첫 번째 텍스트
            text2: 두 번째 텍스트
        
        Returns:
            유사도 점수 (0.0 ~ 1.0)
        """
        if self.use_embedding:
            try:
                return self._semantic_similarity_embedding(text1, text2)
            except Exception as e:
                # Fallback: 기존 방식
                print(f"⚠️ 임베딩 실패, SequenceMatcher 사용: {e}")
                return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()
        else:
            # 기존 방식 (SequenceMatcher)
            return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()
    
    def _extract_search_keywords(self, query: str) -> List[str]:
        """
        검색 쿼리에서 키워드 추출
        
        예시:
        "금리 연 2.15%" → ["금리", "연", "2.15%", "2.15"]
        "최소 50만원부터" → ["최소", "50만원", "50", "만원", "부터"]
        """
        keywords = []
        query_lower = query.lower()
        
        # 1. 숫자 추출 (소수점 포함)
        numbers = self._extract_numbers(query)
        keywords.extend(numbers)
        
        # 2. 숫자 + 단위 조합 (예: "2.15%", "50만원")
        number_patterns = re.findall(r'[\d,]+\.?\d*[%만원개월년]?', query)
        keywords.extend([p.replace(',', '') for p in number_patterns])
        
        # 3. 주요 단어 추출 (불용어 제외)
        stopwords = {"은", "는", "이", "가", "을", "를", "에", "의", "로", "으로", "와", "과", "도", "만", "부터", "까지", "에서", "에게", "한테", "연", "년"}
        words = re.findall(r'[가-힣]+', query)
        keywords.extend([w for w in words if w not in stopwords and len(w) > 1])
        
        # 4. 카테고리 키워드 (금리, 한도, 기간 등)
        category_keywords = ["금리", "이자율", "한도", "기간", "만기", "가입금액", "수수료", "우대금리", "최고금리", "기본금리"]
        for cat_kw in category_keywords:
            if cat_kw in query:
                keywords.append(cat_kw)
        
        # 중복 제거 및 정리
        keywords = list(set([k.strip() for k in keywords if k.strip()]))
        
        return keywords
    
    def _extract_numbers(self, text: str) -> List[str]:
        """
        텍스트에서 숫자 추출 (한국어 금액 단위 인식 포함)
        
        한국어 단위 지원:
        - 만원 = 10000
        - 천원 = 1000
        - 억원 = 100000000
        - 천만원 = 10000000
        
        예시:
        - "10만원" → ["100000"]
        - "100000원" → ["100000"]
        - "5천만원" → ["50000000"]
        - "연 2.15%" → ["2.15"] (일반 숫자)
        """
        numbers = []
        processed_indices = set()  # 한국어 단위로 처리된 부분 추적
        
        # 1. 한국어 금액 단위 패턴 (우선순위: 큰 단위 먼저)
        # 패턴: (숫자)(단위)원? 형식
        korean_unit_patterns = [
            # 복합 단위 (먼저 매칭)
            (r'([\d,]+\.?\d*)\s*천만\s*원?', 10000000),  # 천만원: 10,000,000
            # 기본 단위
            (r'([\d,]+\.?\d*)\s*억\s*원?', 100000000),   # 억원: 100,000,000
            (r'([\d,]+\.?\d*)\s*만\s*원?', 10000),       # 만원: 10,000
            (r'([\d,]+\.?\d*)\s*천\s*원?', 1000),        # 천원: 1,000
        ]
        
        # 한국어 단위로 처리된 텍스트 위치 기록 (일반 숫자 추출 시 제외하기 위함)
        unit_matched_spans = []
        
        for pattern, multiplier in korean_unit_patterns:
            for match in re.finditer(pattern, text):
                matched_text = match.group(0)
                num_str = match.group(1).replace(',', '').strip()
                
                try:
                    num_value = float(num_str) * multiplier
                    # 정수면 정수로, 소수면 소수로 반환
                    if num_value.is_integer():
                        numbers.append(str(int(num_value)))
                    else:
                        numbers.append(str(num_value))
                    
                    # 이 범위는 나중에 일반 숫자 추출에서 제외
                    unit_matched_spans.append((match.start(), match.end()))
                except ValueError:
                    continue
        
        # 2. 일반 숫자 패턴 추출 (한국어 단위 패턴과 겹치지 않는 부분만)
        # 콤마 포함 숫자, 소수점 숫자 모두 추출
        regular_numbers = re.finditer(r'[\d,]+\.?\d*', text)
        
        for match in regular_numbers:
            # 한국어 단위로 이미 처리된 부분인지 확인
            start, end = match.start(), match.end()
            is_covered = any(
                span_start <= start and end <= span_end
                for span_start, span_end in unit_matched_spans
            )
            
            if not is_covered:
                # "원" 뒤에 있는 숫자는 금액일 가능성이 높지만, 단위 없으면 그대로 추출
                # (예: "100000원" 같은 경우는 일반 패턴으로 처리됨)
                num_str = match.group(0).replace(',', '').strip()
                if num_str:
                    numbers.append(num_str)
        
        # 중복 제거 및 정리
        # 같은 값이 문자열로 다른 형태("100000" vs "100000.0")로 들어올 수 있으므로
        # float로 변환해서 비교
        unique_numbers = []
        seen_values = set()
        for num_str in numbers:
            try:
                num_value = float(num_str)
                # 0.01 오차 범위 내에서 같은 값으로 간주
                found_duplicate = False
                for seen_val in seen_values:
                    if abs(num_value - seen_val) < 0.01:
                        found_duplicate = True
                        break
                
                if not found_duplicate:
                    seen_values.add(num_value)
                    # 정수면 정수 문자열로, 소수면 소수 문자열로 저장
                    if num_value.is_integer():
                        unique_numbers.append(str(int(num_value)))
                    else:
                        unique_numbers.append(str(num_value))
            except ValueError:
                # 변환 실패하면 원본 유지
                if num_str not in unique_numbers:
                    unique_numbers.append(num_str)
        
        return unique_numbers
    
    def batch_verify_conversation(
        self,
        conversation: List[Dict],
        use_llm: Optional[bool] = None,
        use_llm_extraction: Optional[bool] = None
    ) -> Dict:
        """
        대화 전체에 대한 제품 지식 정확도 검증
        
        Args:
            conversation: 대화 로그
            use_llm: LLM 검증 사용 여부 (None이면 인스턴스 설정 따름)
            use_llm_extraction: LLM 기반 product_code 추출 사용 여부 (None이면 인스턴스 설정 따름)
                               - True: LLM이 발화를 분석하여 제품 코드 추출 (문맥 이해, 다양한 표현 처리)
                               - False: 키워드 매칭으로 제품 코드 추출 (빠른 처리, 패턴 기반)
        
        Returns:
            {
                "facts": [...],  # 추출된 사실들
                "verifications": [...],  # 검증 결과들
                "accuracy_rate": 0.85,
                "total_claims": 10,
                "accurate_claims": 8,
                "inaccurate_claims": 2,
                "verification_methods": {"llm": 5, "semantic": 3, "keyword": 2}
            }
        """
        # 1. 대화에서 사실 추출
        facts = self.extract_product_facts_from_conversation(
            conversation,
            use_llm_extraction=use_llm_extraction
        )
        
        if not facts:
            return {
                "facts": [],
                "verifications": [],
                "accuracy_rate": 1.0,  # 정보 제공 없으면 오류도 없음
                "total_claims": 0,
                "accurate_claims": 0,
                "inaccurate_claims": 0,
                "details": {
                    "by_category": {},
                    "by_product": {}
                },
                "verification_methods": {}
            }
        
        # 2. 각 사실 검증
        verifications = []
        accurate_count = 0
        method_counts = {}
        
        for fact in facts:
            fact_product_codes = fact.get("product_codes", [])
            print(f"🔍 [Fact 검증] claim='{fact['claim'][:50]}...', product_codes={fact_product_codes}, category={fact.get('category')}")
            
            # 🚨 UNKNOWN이 있으면 먼저 문맥에서 추론 시도
            if "UNKNOWN" in fact_product_codes and len(fact_product_codes) > 1:
                # UNKNOWN이 있지만 다른 상품 코드도 있으면 UNKNOWN 제외하고 검증
                valid_product_codes = [code for code in fact_product_codes if code != "UNKNOWN"]
                print(f"🔍 [Fact 검증] UNKNOWN 제외, 유효한 상품 코드만 검증: {valid_product_codes}")
                fact_product_codes = valid_product_codes
            
            for product_code in fact_product_codes:
                # full_utterance를 임시로 저장하여 verify_fact_accuracy에서 사용
                self._current_full_utterance = fact.get("full_utterance")
                
                verification = self.verify_fact_accuracy(
                    claim=fact["claim"],
                    product_code=product_code,
                    category=fact["category"],
                    use_llm=use_llm
                )
                
                # 🔍 검증 결과 로그
                verification_product_code = getattr(verification, 'product_code', product_code)
                if verification_product_code != product_code and verification_product_code != "UNKNOWN":
                    print(f"⚠️ [검증 결과] 상품 코드 변경됨! 요청: {product_code}, 결과: {verification_product_code}")
                
                verifications.append(verification)
                
                # 임시 저장값 제거
                self._current_full_utterance = None
                
                if verification.is_accurate:
                    accurate_count += 1
                
                # 검증 방법 통계
                method = verification.verification_method
                method_counts[method] = method_counts.get(method, 0) + 1
        
        total_claims = len(verifications)
        accuracy_rate = accurate_count / total_claims if total_claims > 0 else 1.0
        
        return {
            "facts": facts,
            "verifications": verifications,
            "accuracy_rate": accuracy_rate,
            "total_claims": total_claims,
            "accurate_claims": accurate_count,
            "inaccurate_claims": total_claims - accurate_count,
            "details": {
                "by_category": self._group_by_category(verifications),
                "by_product": self._group_by_product(verifications)
            },
            "verification_methods": method_counts
        }
    
    def _group_by_category(self, verifications: List[ProductFactCheck]) -> Dict:
        """카테고리별 정확도 통계"""
        stats = {}
        for v in verifications:
            if v.category not in stats:
                stats[v.category] = {"total": 0, "accurate": 0}
            stats[v.category]["total"] += 1
            if v.is_accurate:
                stats[v.category]["accurate"] += 1
        
        # 정확도 비율 추가
        for category in stats:
            total = stats[category]["total"]
            accurate = stats[category]["accurate"]
            stats[category]["accuracy_rate"] = accurate / total if total > 0 else 0
        
        return stats
    
    def _group_by_product(self, verifications: List[ProductFactCheck]) -> Dict:
        """제품별 정확도 통계"""
        stats = {}
        for v in verifications:
            if v.product_code not in stats:
                stats[v.product_code] = {"total": 0, "accurate": 0}
            stats[v.product_code]["total"] += 1
            if v.is_accurate:
                stats[v.product_code]["accurate"] += 1
        
        # 정확도 비율 추가
        for product in stats:
            total = stats[product]["total"]
            accurate = stats[product]["accurate"]
            stats[product]["accuracy_rate"] = accurate / total if total > 0 else 0
        
        return stats
    
    def _get_product_keywords(self) -> Dict[str, List[str]]:
        """제품별 키워드 가져오기 (캐시 우선, 없으면 하드코딩)"""
        # 캐시에서 가져오기 시도
        if self.keyword_extractor:
            cached_keywords = {}
            for product_code in self.product_knowledge.keys():
                if product_code == "DOC-GDE":
                    continue
                keywords_data = self.keyword_extractor.get_keywords(product_code)
                if keywords_data and keywords_data.get("product_keywords"):
                    cached_keywords[product_code] = keywords_data["product_keywords"]
            
            if cached_keywords:
                return cached_keywords
        
        # 하드코딩된 키워드 (fallback)
        return {
            # 예금 상품
            "DEP-TIM": ["정기예금", "정기 예금", "만기예금"],
            "DEP-FLX": ["자유적금", "자유 적금"],
            "DEP-MMD": ["입출금자유", "자유통장", "입출금 통장", "MMDA", "MMA"],
            # 적금 상품
            "SAV-FIX": ["정기적금", "정기 적금"],
            "SAV-FRE": ["자유적금", "자유 적금"],  # DEP-FLX와 유사하지만 별도 상품
            # 카드 상품
            "CRD-CRE": ["신용카드", "프리미엄 카드", "신용 카드"],
            "CRD-DEB": ["체크카드", "체크 카드"],
            "CRD-YTH": ["청년카드", "청년 카드", "청년"],
            # 대출 상품
            "LON-MTG": ["주택담보대출", "주택담보", "주택 담보 대출"],
            "LON-STU": ["학자금대출", "학자금", "학생 대출"],
            "LON-DCL": ["신용대출", "무담보대출", "직장인 대출", "예금담보대출"],
            "LON-JNS": ["전세자금대출", "전세자금", "전세 대출", "전세"],
            "LON-ODL": ["마이너스통장", "마이너스 통장", "마통"],
            "LON-UNS": ["신용대출", "무담보대출"],  # LON-DCL과 유사하지만 별도 상품
            "LON-YHP": ["청년희망대출", "청년희망", "청년 대출", "청년희망"],
            # 외환 상품 (현재 파일 없음, 향후 추가 가능)
            # "FX001": ["외환", "외환상품", "환전", "외화거래"],
            # "FX002": ["송금", "송금서비스", "해외송금", "해외 송금", "해외송금서비스"],
        }
    
    def _get_product_category_priority(self) -> Dict[str, List[str]]:
        """상품별 중요 정보 카테고리 가져오기 (캐시 우선, 없으면 하드코딩)"""
        # 캐시에서 가져오기 시도
        if self.keyword_extractor:
            cached_categories = {}
            for product_code in self.product_knowledge.keys():
                if product_code == "DOC-GDE":
                    continue
                keywords_data = self.keyword_extractor.get_keywords(product_code)
                if keywords_data and keywords_data.get("categories"):
                    cached_categories[product_code] = keywords_data["categories"]
            
            if cached_categories:
                return cached_categories
        
        # 하드코딩된 카테고리 (fallback)
        return {
            # 예금 상품
            "DEP-MMD": ["금리", "가입금액", "우대금리", "이자지급", "예금자보호", "한도"],  # 입출금 자유는 키워드로만
            "DEP-TIM": ["금리", "기간", "가입금액", "우대금리", "이자지급", "예금자보호"],
            "DEP-FLX": ["금리", "가입금액", "우대금리", "기간", "이자지급", "예금자보호"],
            # 적금 상품
            "SAV-FRE": ["금리", "가입금액", "우대금리", "기간", "이자지급", "예금자보호"],
            "SAV-FIX": ["금리", "가입금액", "우대금리", "기간", "이자지급", "예금자보호"],
            # 대출 상품
            "LON-MTG": ["금리", "한도", "기간", "LTV", "DTI", "DSR", "상환방식", "우대금리", "필요서류"],
            "LON-DCL": ["금리", "한도", "기간", "상환방식", "가입금액"],  # 예금잔액의 95%
            "LON-STU": ["금리", "한도", "기간", "조건", "필요서류"],
            "LON-UNS": ["금리", "한도", "기간", "신용등급", "필요서류"],
            "LON-JNS": ["금리", "한도", "기간", "LTV", "상환방식", "필요서류"],  # 전세자금대출
            "LON-ODL": ["금리", "한도", "이자지급", "수수료"],  # 마이너스통장
            "LON-YHP": ["금리", "한도", "기간", "조건", "필요서류"],  # 청년희망대출
            # 카드 상품
            "CRD-CRE": ["한도", "수수료", "혜택", "신용등급", "이자지급"],  # 연회비, 할인율 등
            "CRD-DEB": ["한도", "수수료", "혜택"],
            "CRD-YTH": ["한도", "수수료", "혜택", "조건"],  # 청년카드
            # 외환 상품 (현재 파일 없음, 향후 추가 가능)
            # "FX001": ["환율", "수수료", "한도"],
            # "FX002": ["환율", "수수료", "한도"],
        }
    
    def get_product_info(self, product_code: str) -> Optional[Dict]:
        """특정 제품의 모든 정보 반환"""
        if product_code not in self.product_knowledge:
            return None
        
        chunks = self.product_knowledge[product_code]
        
        return {
            "product_code": product_code,
            "product_name": chunks[0].get("product", "Unknown") if chunks else "Unknown",
            "total_chunks": len(chunks),
            "parts": self._organize_by_parts(chunks)
        }
    
    def _organize_by_parts(self, chunks: List[Dict]) -> Dict:
        """청크를 PART별로 정리"""
        parts = {}
        for chunk in chunks:
            part_no = chunk.get("part_no", 0)
            part_title = chunk.get("part_title", "Unknown")
            part_key = f"PART {part_no}: {part_title}"
            if part_key not in parts:
                parts[part_key] = []
            parts[part_key].append({
                "subsection": chunk.get("subsection_title", ""),
                "text": chunk.get("text", ""),
                "breadcrumb": chunk.get("breadcrumb", "")
            })
        return parts
