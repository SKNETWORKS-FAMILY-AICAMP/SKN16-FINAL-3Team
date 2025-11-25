"""
RAG 기반 시뮬레이션 서비스
제공된 데이터를 활용한 STT/LLM/TTS 기반 음성 시뮬레이션
"""
import json
import os
import re
import tempfile
import base64
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from sqlmodel import Session, select
import openai
from pathlib import Path

from app.config import settings
from app.models.user import User
from app.services.promptOrchestrator import (
    compose_llm_messages,
    parse_llm_response,
    get_situation_defaults
)
from app.services.banking_normalizer import normalize_text, expand_search_query
from app.services.offtopic_detector import is_on_topic, detect_offtopic_category, generate_pivot_response
from app.services.persona_voice import get_voice_params, build_ssml
from app.services.product_knowledge_service import ProductKnowledgeService

try:
    from app.services.product_keyword_extractor import ProductKeywordExtractor
    KEYWORD_EXTRACTOR_AVAILABLE = True
except ImportError:
    KEYWORD_EXTRACTOR_AVAILABLE = False
    print("⚠️ ProductKeywordExtractor 없음 - 하드코딩된 키워드 사용")


CUSTOMER_STRONG_CLOSINGS = [
    "그럼 이만",
    "그럼 이제 가볼게요",
    "다음에 또 올게요",
    "오늘 도움 많이 됐어요",
    "덕분에 잘 알겠습니다",
    "수고하세요",
    "안녕히 계세요",
    "이제 됐습니다",
    "충분합니다",
]

CUSTOMER_SOFT_CLOSINGS = [
    "감사합니다",
    "네 알겠습니다",
    "네 알겠어요",
    "더 이상 없어요",
    "없습니다",
    "괜찮습니다",
    "이제 됐어요",
    "잘 알겠습니다",
    "질문 없어요",
    "더 이상 질문",
    "충분합니다",
    "이제 됐습니다",
    "이제 끝난 건가요",
    "더 할 건 없죠",
    "그럼 끊을게요",
    "그럼 여기까지",
]

# 종료 트리거 키워드 리스트 (고객 + 신입사원 통합)
END_CONVERSATION_TRIGGERS = [
    # 신입사원 종료 트리거
    "정리해서 말씀드리면",
    "오늘 안내드린 내용은",
    "추가로 도와드릴",
    "다른 문의 없으시면",
    "상담 마무리",
    "상담 여기까지",
    "이제 마무리",
    "모든 절차가 완료",
    "처리 끝났습니다",
    "하실 일은 없습니다",
    "좋은 하루",
    "감사합니다",
    "수고하세요",
    # 고객 종료 트리거
    "질문 없어요",
    "더 이상 질문",
    "충분합니다",
    "이제 됐습니다",
    "이제 끝난 건가요",
    "더 할 건 없죠",
    "그럼 끊을게요",
    "그럼 여기까지",
]

EMPLOYEE_CLOSING_PROMPTS = [
    "더 도와드릴",
    "추가로 필요하신",
    "추가로 궁금하신",
    "또 문의",
    "다른 도움",
    "무엇을 더",
    "더 궁금한",
    "더 필요한",
    "정리해서 말씀드리면",
    "오늘 안내드린 내용은",
    "추가로 도와드릴",
    "다른 문의 없으시면",
    "상담 마무리",
    "상담 여기까지",
    "이제 마무리",
    "모든 절차가 완료",
    "처리 끝났습니다",
    "하실 일은 없습니다",
    "좋은 하루",
    "감사합니다",
    "수고하세요",
    "더 궁금하신 점",
    "더 필요하신 점",
    "더 궁금하신 점 있으세요",
    "더 필요하신 점 있으세요",
    "추가로 도와드릴 부분",
    "다른 문의는 없으신가요",
    "없으시면 상담 마무리",
    "상담은 여기까지",
    "이제 마무리 도와드릴게요",
    "이용해주셔서 감사합니다",
    "언제든 문의 주세요",
    "더 필요하신 점 있으세요",
    "더 궁금하신 점 있으세요"
]


SITUATION_DEFAULTS = {
    "deposit": {
        "id": "deposit",
        "title": "수신 상담",
        "goals": ["고객 요구사항 파악", "적합한 상품 제안", "절차 안내"],
        "required_slots": ["목적", "금액", "기간"],
        "forbidden_claims": ["원금 보장", "수익률 보장"],
        "style_rules": ["수익률은 참고용 예시로만", "실제 수익률은 차등 적용"],
        "disclaimer": "실제 수익률은 상품 조건과 시장 상황에 따라 달라질 수 있습니다."
    },
    "loan": {
        "id": "loan",
        "title": "여신 상담",
        "goals": ["대출 목적 확인", "신용도 파악", "가능한 한도 안내"],
        "required_slots": ["목적", "직업", "소득"],
        "forbidden_claims": ["심사 통과 보장", "확정 금리 보장"],
        "style_rules": ["한도/금리는 심사 결과에 따름", "필요 서류 안내"],
        "disclaimer": "대출 한도 및 금리는 심사 결과에 따라 달라질 수 있습니다."
    },
    "card": {
        "id": "card",
        "title": "카드 상담",
        "goals": ["카드 용도 파악", "적합한 혜택 제안"],
        "required_slots": ["사용 목적", "월 사용 금액"],
        "forbidden_claims": ["승인 보장"],
        "style_rules": ["혜택은 카드 종류별 상이", "연회비 안내"],
        "disclaimer": "카드 승인은 신용평가에 따라 달라질 수 있습니다."
    },
    "fx": {
        "id": "fx",
        "title": "외환/송금 상담",
        "goals": ["송금 목적 확인", "수수료 안내", "절차 설명"],
        "required_slots": ["송금 국가", "금액"],
        "forbidden_claims": ["환율 보장"],
        "style_rules": ["환율은 변동 가능", "추가 서류 확인 필요 여부 안내"],
        "disclaimer": "환율은 환전 시점의 시장 환율이 적용됩니다.",
        "has_product_data": False  # 상품 데이터 없음 - 지식 평가 방식 변경
    }
}


def get_situation_defaults(situation_id: str) -> Dict:
    return SITUATION_DEFAULTS.get(situation_id, SITUATION_DEFAULTS["deposit"])


class RAGSimulationService:
    """RAG 기반 시뮬레이션 서비스"""
    
    def __init__(self, session: Session):
        self.session = session
        # OpenAI 클라이언트 초기화 (API 키가 있을 때만)
        api_key = settings.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY")
        if api_key:
            try:
                self.openai_client = openai.OpenAI(api_key=api_key)
            except Exception as e:
                print(f"OpenAI 클라이언트 초기화 실패: {e}")
                self.openai_client = None
        else:
            self.openai_client = None
        
        # 제품 지식 서비스 초기화 (벡터 검색 활성화를 위해 session 전달)
        try:
            self.product_knowledge_service = ProductKnowledgeService(
                use_llm=True,
                session=session  # 벡터 검색 활성화
            )
            print("✅ 제품 지식 검증 서비스 초기화 완료 (벡터 검색 활성화)")
        except Exception as e:
            print(f"⚠️ 제품 지식 서비스 초기화 실패: {e}")
            self.product_knowledge_service = None
        
        # 키워드 추출기 초기화 (하이브리드 접근)
        self.keyword_extractor = None
        if KEYWORD_EXTRACTOR_AVAILABLE:
            try:
                self.keyword_extractor = ProductKeywordExtractor(data_path=self.data_path, use_llm=False)
                print("✅ 키워드 자동 추출기 초기화 완료 (RAG 평가용)")
            except Exception as e:
                print(f"⚠️ 키워드 추출기 초기화 실패: {e}")
        
        # 데이터 파일 경로 설정 (로컬/Docker 환경 모두 지원)
        # Docker 환경: /app/data
        # 로컬 환경: backend/data
        if Path("/app/data").exists():
            self.data_path = Path("/app/data")
        else:
            # 로컬 환경: 현재 파일 기준으로 상대 경로 계산
            current_file = Path(__file__)  # backend/app/services/rag_simulation_service.py
            self.data_path = current_file.parent.parent.parent / "data"  # backend/data
        
        # 데이터 캐시
        self.personas_cache = None
        self.situations_cache = None
        self.product_catalog = None
    
    def load_simulation_data(self):
        """시뮬레이션 데이터 로드"""
        try:
            print(f"📁 데이터 경로 확인: {self.data_path}")
            print(f"📁 디렉토리 존재 여부: {self.data_path.exists()}")
            
            if not self.data_path.exists():
                print(f"❌ 데이터 디렉토리가 존재하지 않습니다: {self.data_path}")
                return
            
            # 페르소나 데이터 로드 (personas_expanded_minified2.json)
            personas_file = self.data_path / "personas_expanded_minified2.json"
            print(f"📄 페르소나 파일 경로: {personas_file}")
            print(f"📄 페르소나 파일 존재 여부: {personas_file.exists()}")
            
            if personas_file.exists():
                with open(personas_file, 'r', encoding='utf-8') as f:
                    personas_data = json.load(f)
                    if 'personas' in personas_data:
                        self.personas_cache = personas_data['personas']
                    else:
                        self.personas_cache = personas_data if isinstance(personas_data, list) else []
                print(f"✅ 페르소나 데이터 로드 완료: {len(self.personas_cache) if self.personas_cache else 0}개")
            else:
                print("❌ 페르소나 파일을 찾을 수 없습니다")
            
            # 상황 데이터 로드 (1hakyung_situations_4categories_50each_with_products.txt)
            situations_file = self.data_path / "1hakyung_situations_4categories_50each_with_products.txt"
            print(f"📄 상황 파일 경로: {situations_file}")
            print(f"📄 상황 파일 존재 여부: {situations_file.exists()}")
            
            if situations_file.exists():
                try:
                    with open(situations_file, 'r', encoding='utf-8') as f:
                        situations_data = json.load(f)
                        if 'situations' in situations_data:
                            # 새로운 파일 구조: situations 배열에서 각 상황의 starter_topics를 평탄화
                            raw_situations = situations_data['situations']
                            self.situations_cache = []
                            
                            # 각 카테고리별 상황을 처리
                            for category_situation in raw_situations:
                                category_id = category_situation.get('id', '')
                                category_title = category_situation.get('title', '')
                                starter_topics = category_situation.get('starter_topics', [])
                                
                                # 각 starter_topic을 개별 상황으로 변환
                                for idx, topic in enumerate(starter_topics):
                                    situation_item = {
                                        'id': f"{category_id}_{idx}",
                                        'category_id': category_id,
                                        'category_title': category_title,
                                        'title': topic.get('title', ''),
                                        'product': topic.get('product'),
                                        'product_code': topic.get('product_code'),
                                        'intent': topic.get('intent', ''),
                                        'is_from_product_manual': topic.get('is_from_product_manual', False),
                                        'goals': topic.get('goals', []),
                                        'starter_topics': [topic]  # 호환성을 위해 유지
                                    }
                                    self.situations_cache.append(situation_item)
                            
                            print(f"✅ 상황 데이터 로드 완료: {len(self.situations_cache)}개 (카테고리 {len(raw_situations)}개에서 변환)")
                        else:
                            self.situations_cache = situations_data if isinstance(situations_data, list) else []
                            print(f"✅ 상황 데이터 로드 완료: {len(self.situations_cache) if self.situations_cache else 0}개")
                except json.JSONDecodeError as e:
                    error_msg = f"상황 파일 JSON 파싱 실패: {situations_file} - {str(e)}"
                    print(f"❌ {error_msg}")
                    raise ValueError(error_msg) from e
                except Exception as e:
                    error_msg = f"상황 파일 로드 실패: {situations_file} - {str(e)}"
                    print(f"❌ {error_msg}")
                    raise RuntimeError(error_msg) from e
            else:
                error_msg = f"상황 파일을 찾을 수 없습니다: {situations_file}"
                print(f"❌ {error_msg}")
                raise FileNotFoundError(error_msg)
            
            # 상품 카탈로그 로드
            catalog_file = self.data_path / "product_catalog.json"
            print(f"📄 카탈로그 파일 경로: {catalog_file}")
            print(f"📄 카탈로그 파일 존재 여부: {catalog_file.exists()}")
            
            if catalog_file.exists():
                with open(catalog_file, 'r', encoding='utf-8') as f:
                    self.product_catalog = json.load(f)
                    print(f"✅ 상품 카탈로그 로드됨: {len(self.product_catalog.get('products', []))}개 상품")
            else:
                print("❌ 상품 카탈로그 파일을 찾을 수 없습니다")
                self.product_catalog = {"products": [], "categories": {}}
            
            print(f"✅ 데이터 로드 완료: 페르소나 {len(self.personas_cache) if self.personas_cache else 0}개, "
                  f"상황 {len(self.situations_cache) if self.situations_cache else 0}개, "
                  f"상품 {len(self.product_catalog.get('products', []))}개")
            
        except (FileNotFoundError, ValueError, RuntimeError) as e:
            # 이미 처리된 예외는 그대로 전달
            print(f"❌ 데이터 로드 실패 (명시적 예외): {e}")
            import traceback
            traceback.print_exc()
            raise
        except Exception as e:
            # 예상치 못한 예외
            error_msg = f"데이터 로드 중 예상치 못한 오류 발생: {str(e)}"
            print(f"❌ {error_msg}")
            import traceback
            traceback.print_exc()
            raise RuntimeError(error_msg) from e
    
    def get_personas(self, filters: Optional[Dict] = None) -> List[Dict]:
        """페르소나 목록 조회 (필드명 정규화하여 반환)"""
        if not self.personas_cache:
            print("📊 페르소나 데이터 로딩 중...")
            self.load_simulation_data()
        
        if not self.personas_cache:
            print("❌ 페르소나 데이터가 없습니다.")
            return []
        
        personas = self.personas_cache.copy()
        
        # 필드명 정규화 (personas_expanded_minified2.json 구조에 맞춤)
        normalized_personas = []
        for p in personas:
            normalized = {
                "id": p.get("id", ""),
                "persona_id": p.get("id", ""),  # id를 persona_id로도 사용
                "gender": p.get("gender", ""),
                "age_group": p.get("age_group", ""),
                "occupation": p.get("occupation", ""),
                "type": p.get("customer_style") or p.get("type", ""),  # customer_style -> type
                "customer_style": p.get("customer_style", ""),
                "tone": p.get("speech", {}).get("tone", "neutral") if isinstance(p.get("speech"), dict) else p.get("tone", "neutral"),
                "style": p.get("speech", {}) if isinstance(p.get("speech"), dict) else p.get("style", {}),
                "sample_utterances": p.get("utterance_hints", []) or p.get("sample_utterances", []),
                "utterance_hints": p.get("utterance_hints", []),
                "financial_literacy": p.get("financial_literacy", "중간"),  # 기본값
                "speech": p.get("speech", {})
            }
            normalized_personas.append(normalized)
        
        personas = normalized_personas
        
        if filters:
            # age_group 필터
            if filters.get("age_group"):
                personas = [p for p in personas if p.get("age_group") == filters["age_group"]]
            
            # occupation 필터 - 영어 키워드 매핑
            if filters.get("occupation"):
                occupation_map = {
                    "student": "학생",
                    "employee": "직장인",
                    "self_employed": "자영업자",
                    "retired": "은퇴자",
                    "foreigner": "외국인"
                }
                occupation_keyword = occupation_map.get(filters["occupation"], filters["occupation"])
                personas = [p for p in personas if occupation_keyword in p.get("occupation", "")]
            
            # type 필터 - 영어 키워드 매핑
            if filters.get("type"):
                type_map = {
                    "practical": "실용형",
                    "conservative": "보수형",
                    "angry": "불만형",
                    "positive": "긍정형",
                    "impatient": "급함형"
                }
                type_keyword = type_map.get(filters["type"], filters["type"])
                personas = [p for p in personas if type_keyword in p.get("type", "") or type_keyword in p.get("customer_style", "")]
            
            # gender 필터 - 성별 매핑
            if filters.get("gender"):
                gender_map = {
                    "male": "남성",
                    "female": "여성"
                }
                gender_keyword = gender_map.get(filters["gender"], filters["gender"])
                personas = [p for p in personas if p.get("gender") == gender_keyword]
        
        # 🚨 논리적 필터링: 비현실적인 연령-직업 조합 제외
        # 1. 10대/20대는 은퇴자 제외
        # 2. 10대는 직장인/자영업자 제외 (청소년)
        # 3. 60대 이상은 학생 제외
        personas = [
            p for p in personas 
            if not (
                # 10대/20대와 은퇴자 조합 방지
                ((p.get("age_group") == "10대" or p.get("age_group") == "20대") 
                 and "은퇴자" in p.get("occupation", "")) or
                # 10대와 직장인/자영업자 조합 방지
                (p.get("age_group") == "10대" 
                 and (("직장인" in p.get("occupation", "")) or ("자영업자" in p.get("occupation", "")))) or
                # 60대 이상과 학생 조합 방지
                ((p.get("age_group") == "60대 이상" or p.get("age_group") == "60대이상") 
                 and "학생" in p.get("occupation", ""))
            )
        ]
        
        print(f"✅ 페르소나 {len(personas)}개 반환 (비현실적 조합 제외: 10대/20대-은퇴자, 10대-직장인/자영업자, 60대 이상-학생)")
        return personas
    
    def normalize_user_text(self, text: str, confidence: float = 1.0) -> Dict:
        """사용자 텍스트를 은행 도메인에 맞게 정규화합니다."""
        try:
            result = normalize_text(text, confidence)
            return {
                "original": result.original,
                "normalized": result.normalized,
                "corrections": result.corrections,
                "needs_clarification": result.needs_clarification,
                "extracted_entities": result.extracted_entities
            }
        except Exception as e:
            print(f"❌ 텍스트 정규화 실패: {e}")
            return {
                "original": text,
                "normalized": text,
                "corrections": [],
                "needs_clarification": False,
                "extracted_entities": {}
            }
    
    def match_product_catalog(self, normalized_text: str) -> List[Dict]:
        """정규화된 텍스트로 상품 카탈로그를 매칭합니다."""
        if not self.product_catalog or not self.product_catalog.get("products"):
            return []
        
        matched_products = []
        products = self.product_catalog["products"]
        
        for product in products:
            # 상품명 직접 매칭
            if product["name"] in normalized_text:
                matched_products.append({
                    "product": product["name"],
                    "code": product["code"],
                    "category": product["category"],
                    "category_ko": product["category_ko"],
                    "match_type": "exact_name"
                })
                continue
            
            # 키워드 매칭
            keywords = product.get("keywords", [])
            for keyword in keywords:
                if keyword in normalized_text:
                    matched_products.append({
                        "product": product["name"],
                        "code": product["code"],
                        "category": product["category"],
                        "category_ko": product["category_ko"],
                        "match_type": "keyword",
                        "matched_keyword": keyword
                    })
                    break
        
        return matched_products
    
    def expand_search_query(self, normalized_text: str, catalog_hits: List[Dict] = None) -> List[str]:
        """검색 쿼리를 확장합니다."""
        try:
            return expand_search_query(normalized_text, catalog_hits)
        except Exception as e:
            print(f"❌ 쿼리 확장 실패: {e}")
            return [normalized_text]
    
    def get_business_categories(self) -> List[Dict]:
        """비즈니스 카테고리 목록 조회"""
        if not self.situations_cache:
            self.load_simulation_data()
        
        if not self.situations_cache:
            return []
        
        # 카테고리 추출
        categories = []
        seen_categories = set()
        
        for situation in self.situations_cache:
            title = situation.get('title', '')
            category_id = situation.get('id', '')
            
            # 카테고리 이름 추출 (예: "수신 (예금, 적금, 자동이체)" -> "수신")
            if '(' in title:
                category_name = title.split('(')[0].strip()
            else:
                category_name = title
            
            if category_name not in seen_categories:
                categories.append({
                    "id": category_id,
                    "name": category_name,
                    "title": title
                })
                seen_categories.add(category_name)
        
        return categories
    
    def get_situations(self, filters: Optional[Dict] = None, random_select: bool = True) -> List[Dict]:
        """
        상황 목록 조회
        - filters: 카테고리 필터 (예: {"category": "deposit"})
        - random_select: True면 카테고리별로 40개 중 1개 랜덤 선택, False면 전체 반환
        """
        if not self.situations_cache:
            self.load_simulation_data()
        
        if not self.situations_cache:
            print("⚠️ 상황 데이터가 없습니다.")
            return []
        
        import random
        
        situations = self.situations_cache
        print(f"📊 전체 상황 개수: {len(situations)}")
        
        if filters and filters.get("category"):
            category = filters["category"]
            print(f"🔍 카테고리 필터: {category}")
            
            # 카테고리 매핑 (프론트엔드에서 전달하는 값 -> 실제 카테고리 값)
            category_mapping = {
                "deposit": ["deposit", "수신"],
                "loan": ["loan", "여신"],
                "card": ["card", "카드"],
                "fx": ["foreign_exchange", "외환", "송금", "외환/송금"],
                "foreign_exchange": ["foreign_exchange", "외환", "송금", "외환/송금"],
                "complaint": ["complaint", "민원", "불만", "민원/불만 처리"]
            }
            
            # 매핑된 카테고리 값들 가져오기
            mapped_categories = category_mapping.get(category, [category])
            print(f"📋 매핑된 카테고리: {mapped_categories}")
            
            # 카테고리별로 필터링 (category_id, id, category, title 필드 모두 확인)
            filtered_situations = []
            for s in situations:
                category_id = s.get("category_id", "")
                situation_id = s.get("id", "")
                situation_category = s.get("category", "")
                situation_title = s.get("title", "")
                
                # 카테고리 매칭 확인
                matched = False
                for mapped_cat in mapped_categories:
                    if (category_id == mapped_cat or
                        situation_id == mapped_cat or 
                        situation_category == mapped_cat or 
                        mapped_cat in situation_title or
                        category_id.startswith(mapped_cat) or
                        situation_id.startswith(mapped_cat) or
                        situation_category.startswith(mapped_cat)):
                        matched = True
                        break
                
                if matched:
                    filtered_situations.append(s)
            
            print(f"✅ 필터링된 상황 개수: {len(filtered_situations)}")
            
            if random_select and filtered_situations:
                # 40개 중 1개 랜덤 선택
                random_situation = random.choice(filtered_situations)
                situation_id = random_situation.get('id', 'unknown')
                print(f"🎲 카테고리 '{category}'에서 랜덤 선택: {situation_id} ({len(filtered_situations)}개 중 1개 선택)")
                print(f"📄 선택된 상황: {random_situation.get('title', 'N/A')}")
                return [random_situation]
            else:
                return filtered_situations
        else:
            # 필터가 없으면 전체 반환
            if random_select and situations:
                # 전체 중 1개 랜덤 선택
                random_situation = random.choice(situations)
                situation_id = random_situation.get('id', 'unknown')
                print(f"🎲 전체 상황에서 랜덤 선택: {situation_id} ({len(situations)}개 중 1개 선택)")
                return [random_situation]
            else:
                return situations
    
    def _get_test_scenario_data(self, scenario_type: str) -> Dict:
        """시나리오 타입에 따른 테스트 시나리오 데이터 반환"""
        scenarios = {
            'deposit': {
                "turns": [
                    {"turn": 1, "role": "employee", "expected_text": "안녕하세요, 하경은행입니다. 무엇을 도와드릴까요?", "product_code": None, "keywords": ["인사"]},
                    {"turn": 1, "role": "customer", "expected_text": "정기예금 상품에 대해 상담받고 싶어요.", "product_code": "DEP-TIM", "keywords": ["정기예금", "상담", "상품"]},
                    {"turn": 2, "role": "employee", "expected_text": "하경은행 정기예금은 일정 금액을 정해진 기간 동안 예치하고 만기 시 원금과 이자를 한 번에 받는 원리금보장 예금상품입니다. 예금자보호법에 따라 1인당 원리금 합계 5천만원까지 보호됩니다.", "product_code": "DEP-TIM", "keywords": ["정기예금", "원리금보장", "만기", "예금자보호법", "5천만원"]},
                    {"turn": 2, "role": "customer", "expected_text": "가입 금액이랑 가입 기간은 어떻게 되나요?", "product_code": "DEP-TIM", "keywords": ["가입 금액", "가입 기간", "최소", "기간"]},
                    {"turn": 3, "role": "employee", "expected_text": "정기예금은 최소 50만원부터 가입 가능하고 상한은 따로 없어요. 가입 기간은 1개월 이상 36개월 이하에서 1개월 단위로 선택하실 수 있고, 주로 6개월이나 12개월 만기를 많이 선택하세요.", "product_code": "DEP-TIM", "keywords": ["가입 금액", "최소 50만원", "가입 기간", "1개월", "36개월", "6개월", "12개월"]},
                    {"turn": 3, "role": "customer", "expected_text": "그럼 12개월 정기예금 금리랑 우대금리는 어떻게 적용돼요?", "product_code": "DEP-TIM", "keywords": ["12개월", "기본금리", "최고금리", "우대금리"]},
                    {"turn": 4, "role": "employee", "expected_text": "현재 12개월 기준 기본 금리는 연 2.15%이고, 우대조건을 모두 충족하시면 최대 연 2.65%까지 가능해요. 급여이체, 카드 이용, 모바일·인터넷뱅킹 가입, 신규 고객, 자산 규모에 따라 0.1%p에서 0.2%p까지 우대금리가 더해지고, 최대 0.5%p까지 가산됩니다.", "product_code": "DEP-TIM", "keywords": ["12개월", "기본금리", "2.15%", "최고금리", "2.65%", "우대금리", "급여이체", "카드", "모바일", "인터넷뱅킹", "0.5%p"]},
                    {"turn": 4, "role": "customer", "expected_text": "혹시 중도해지하면 이자는 어떻게 되고, 세금도 얼마나 떼나요?", "product_code": "DEP-TIM", "keywords": ["중도해지", "이자", "세금", "이자소득세"]},
                    {"turn": 5, "role": "employee", "expected_text": "만기 이전에 중도해지하시면 가입 기간에 따라 중도해지 금리가 적용돼서 약정금리보다 낮은 이자만 받으실 수 있습니다. 1개월 미만은 이자가 없고, 1개월 이상은 중도해지율이 적용돼요. 또한 이자에는 이자소득세 15.4%가 원천징수된 후 세후 이자가 지급됩니다.", "product_code": "DEP-TIM", "keywords": ["중도해지", "이자", "중도해지율", "1개월 미만", "이자 없음", "이자소득세", "15.4%"]},
                    {"turn": 5, "role": "customer", "expected_text": "영업점 말고 인터넷이나 모바일 앱으로도 가입이 가능한가요?", "product_code": "DEP-TIM", "keywords": ["가입 방법", "영업점", "인터넷뱅킹", "모바일앱"]},
                    {"turn": 6, "role": "employee", "expected_text": "네, 영업점 방문은 물론 인터넷뱅킹과 하경 뱅킹 모바일앱으로도 가입 가능하세요. 디지털 채널로 가입하시고 종이통장을 발행하지 않으시면 디지털 우대금리도 추가로 받으실 수 있습니다. 더 궁금하신 점 없으시면 정리해서 가입 도와드릴까요?", "product_code": "DEP-TIM", "keywords": ["가입 방법", "영업점", "인터넷뱅킹", "모바일앱", "디지털 우대금리", "종이통장 미발행"]},
                    {"turn": 6, "role": "customer", "expected_text": "네 감사합니다.", "product_code": None, "keywords": []},
                    {"turn": 7, "role": "employee", "expected_text": "감사합니다.", "product_code": None, "keywords": []}
                ]
            },
            'loan': {
                "turns": [
                    {"turn": 1, "role": "employee", "expected_text": "안녕하세요 하경은행입니다 무엇을 도와드릴까요", "product_code": None, "keywords": ["인사"]},
                    {"turn": 1, "role": "customer", "expected_text": "주택담보대출 상담을 받고 싶은데요", "product_code": "LON-MTG", "keywords": ["주택담보대출", "상담"]},
                    {"turn": 2, "role": "employee", "expected_text": "하경은행 주택담보대출은 주택을 담보로 제공해서 주택 구입이나 전세 보증금 같은 자금을 대출받는 상품입니다 신용대출보다 금리가 낮고 상환기간이 길며 LTV DTI DSR 같은 규제가 적용됩니다", "product_code": "LON-MTG", "keywords": ["주택담보대출", "주택 담보", "주택 구입", "전세 보증금", "신용대출보다 낮은 금리", "긴 상환기간", "LTV", "DTI", "DSR", "규제"]},
                    {"turn": 2, "role": "customer", "expected_text": "대출 대상이랑 한도는 어느 정도까지 가능한가요", "product_code": "LON-MTG", "keywords": ["대출 대상", "대출 한도"]},
                    {"turn": 3, "role": "employee", "expected_text": "대출 대상은 만 19세 이상 65세 이하로 안정적인 소득이 있는 개인이고 주택을 구입하시거나 기존 주택을 담보로 하시는 분입니다 대출 한도는 최소 3천만원에서 최대 10억원까지 가능하고 담보인정비율 LTV는 일반지역은 주택 가격의 70% 조정대상지역은 60% 투기지역은 40% 투기과열지구는 30% 이내에서 결정됩니다", "product_code": "LON-MTG", "keywords": ["대출 대상", "만 19세", "만 65세", "안정적인 소득", "대출 한도", "최소 3천만원", "최대 10억원", "LTV", "담보인정비율", "일반지역 70%", "조정대상지역 60%", "투기지역 40%", "투기과열지구 30%"]},
                    {"turn": 3, "role": "customer", "expected_text": "대출 금리는 어느 정도 나오고 우대금리는 어떻게 적용되나요", "product_code": "LON-MTG", "keywords": ["대출 금리", "우대금리"]},
                    {"turn": 4, "role": "employee", "expected_text": "대출 금리는 신용등급에 따라 기본적으로 연 3%에서 8% 사이에서 결정되고 우대조건을 충족하시면 약 0.5%에서 최대 1.0%포인트까지 낮출 수 있습니다 주거래 우대는 급여이체와 예적금 3천만원 이상일 때 0.3%포인트 자동이체 우대는 공과금이나 보험료 자동이체 5건 이상일 때 0.2%포인트 생애최초 주택 구입과 신혼부부는 각각 0.3%포인트와 0.2%포인트가 추가로 감면되고 이 우대금리들을 합쳐서 최대 1.0%포인트까지 적용됩니다", "product_code": "LON-MTG", "keywords": ["대출 금리", "3.00~8.00%", "우대금리", "주거래 우대", "급여이체", "예적금 3천만원", "자동이체 우대", "공과금", "보험료", "생애최초", "신혼부부", "최대 1.0%p"]},
                    {"turn": 4, "role": "customer", "expected_text": "상환 기간이랑 상환 방식은 어떻게 선택할 수 있나요", "product_code": "LON-MTG", "keywords": ["상환 기간", "상환 방식"]},
                    {"turn": 5, "role": "employee", "expected_text": "대출 기간은 보통 최단 10년에서 최장 40년까지 가능하고 고객님 연령과 상환 능력에 맞춰 정하게 됩니다 상환 방식은 매월 같은 금액을 내는 원리금균등분할상환과 매월 같은 원금을 내는 원금균등분할상환 소득이 앞으로 늘어날 때 유리한 체증식 상환 그리고 1년에서 5년 정도는 이자만 내고 그 이후에 원리금 분할로 전환하는 거치식 상환 방식 중에서 선택하실 수 있습니다", "product_code": "LON-MTG", "keywords": ["상환 방식", "원리금균등분할상환", "원금균등분할상환", "체증식 상환", "거치식 상환", "대출 기간", "최단 10년", "최장 40년", "거치기간 1~5년"]},
                    {"turn": 5, "role": "customer", "expected_text": "준비해야 하는 서류는 어떤 것들이 있나요", "product_code": "LON-MTG", "keywords": ["필요 서류"]},
                    {"turn": 6, "role": "employee", "expected_text": "공통으로 신분증과 주민등록등본 인감증명서 같은 기본 서류와 소득증빙 서류가 필요하고 담보주택 관련해서는 등기부등본 건축물대장 토지대장 감정평가서와 주택을 구입하시는 경우에는 매매계약서가 필요합니다 직장인이시면 재직증명서와 최근 급여명세서도 추가로 준비해 주셔야 합니다 자세한 서류는 다시 한번 정리해서 안내해 드릴게요", "product_code": "LON-MTG", "keywords": ["필요 서류", "신분증", "주민등록등본", "인감증명서", "소득증빙", "등기부등본", "건축물대장", "토지대장", "감정평가서", "매매계약서", "재직증명서", "급여명세서"]},
                    {"turn": 6, "role": "customer", "expected_text": "네 감사합니다.", "product_code": None, "keywords": []},
                    {"turn": 7, "role": "employee", "expected_text": "감사합니다.", "product_code": None, "keywords": []}
                ]
            },
            'card': {
                "turns": [
                    {"turn": 1, "role": "employee", "expected_text": "안녕하세요 무엇을 도와드릴까요", "product_code": None, "keywords": ["인사", "도와드릴까요"]},
                    {"turn": 1, "role": "customer", "expected_text": "신용카드 발급 받고 싶은데요", "product_code": "CRD-CRE", "keywords": ["신용카드", "발급", "하경 프리미엄 신용카드"]},
                    {"turn": 2, "role": "employee", "expected_text": "하경 프리미엄 신용카드는 신용한도 내에서 후불로 결제하시고 결제일에 한 번에 상환하시는 카드입니다 일반 가맹점 이용금액의 1%가 포인트로 적립되고 주유나 통신비 커피 할인 같은 다양한 혜택이 제공됩니다", "product_code": "CRD-CRE", "keywords": ["신용카드", "후불결제", "신용한도", "포인트 적립", "할인 혜택", "CRD-CRE"]},
                    {"turn": 2, "role": "customer", "expected_text": "카드 한도는 얼마나 나오나요?", "product_code": "CRD-CRE", "keywords": ["카드 한도", "신용한도"]},
                    {"turn": 3, "role": "employee", "expected_text": "신용카드 한도는 고객님의 신용등급과 연소득에 따라 결정됩니다 하경 프리미엄 신용카드는 만 19세 이상이고 신용등급 1에서 6등급 연소득 2천만원 이상이시면 발급 가능하고 신용등급 1에서 2등급은 최대 1억원, 3에서 4등급은 최대 5천만원 5에서 6등급은 최대 3천만원까지 한도가 나올 수 있습니다 정확한 한도는 심사 후에 안내해 드립니다", "product_code": "CRD-CRE", "keywords": ["신용등급", "연소득", "1~2등급 최대 1억원", "3~4등급 최대 5000만원", "5~6등급 최대 3000만원", "발급 조건"]},
                    {"turn": 3, "role": "customer", "expected_text": "체크카드도 같이 발급 가능한가요?", "product_code": "CRD-DEB", "keywords": ["체크카드", "발급", "같이 발급"]},
                    {"turn": 4, "role": "employee", "expected_text": "네 가능합니다 하경 My 체크카드는 통장 잔액 범위 내에서 바로 출금되는 직불카드라서 신용등급과 거의 무관하게 사용하실 수 있고 과소비 위험이 적습니다 연회비는 국내전용 기본형은 무료부터 시작하고 체크카드 사용분은 소득공제율이 30%로 신용카드 15%보다 높아서 세제 혜택을 더 받으실 수 있는 장점이 있습니다", "product_code": "CRD-DEB", "keywords": ["체크카드", "통장 잔액 범위", "직불카드", "연회비", "소득공제 30%", "CRD-DEB"]},
                    {"turn": 4, "role": "customer", "expected_text": "신용카드 할부 이자율은 어떻게 되나요?", "product_code": "CRD-CRE", "keywords": ["신용카드", "할부", "이자율"]},
                    {"turn": 5, "role": "employee", "expected_text": "신용카드 일시불은 이자가 없고 할부는 2개월에서 12개월까지 선택하실 수 있는데 기간에 따라 연 5.9%에서 15.0% 수준으로 적용됩니다 리볼빙이나 현금서비스는 연 14%에서 17.9% 정도로 금리가 더 높기 때문에 가능하면 일시불이나 단기 할부 위주로 이용하시는 것을 권해드립니다", "product_code": "CRD-CRE", "keywords": ["일시불 무이자", "할부 5.9~15.0%", "리볼빙 14~17%", "현금서비스 17.9%", "이자율"]},
                    {"turn": 5, "role": "customer", "expected_text": "그럼 체크카드랑 신용카드 중에 어떤 게 저한테 더 나을까요?", "product_code": None, "keywords": ["체크카드 vs 신용카드", "비교", "추천"]},
                    {"turn": 6, "role": "employee", "expected_text": "체크카드는 결제 즉시 통장에서 출금되고 연회비가 거의 없고 소득공제율이 30%로 높아서 학생이나 사회초년생처럼 지출을 안전하게 관리하고 싶으신 분께 유리합니다 신용카드는 후불결제로 자금 운용이 편리하고 포인트와 할인 혜택이 더 많지만 과도하게 사용하시면 신용등급이 떨어질 수 있어 관리가 중요합니다 현재 소득과 사용 패턴을 고려해서 기본은 체크카드를 쓰시고 정기적인 지출과 혜택이 필요한 부분에만 신용카드를 보완적으로 쓰시는 것을 추천드립니다", "product_code": None, "keywords": ["체크카드 장점", "신용카드 장점", "즉시 출금", "후불결제", "연회비", "포인트", "소득공제", "신용등급 관리", "비교", "상담 마무리"]},
                    {"turn": 6, "role": "customer", "expected_text": "네 감사합니다.", "product_code": None, "keywords": []},
                    {"turn": 7, "role": "employee", "expected_text": "감사합니다.", "product_code": None, "keywords": []}
                ]
            },
            'fx': {
                "turns": [
                    {"turn": 1, "role": "employee", "expected_text": "안녕하세요 무엇을 도와드릴까요", "product_code": None, "keywords": []},
                    {"turn": 1, "role": "customer", "expected_text": "해외로 송금하고 싶은데요", "product_code": None, "keywords": ["해외", "송금"]},
                    {"turn": 2, "role": "employee", "expected_text": "해외송금은 전신환 송금과 전자송금 방식이 있습니다 전신환은 수수료가 낮지만 시간이 오래 걸리고 전자송금은 빠르지만 수수료가 조금 더 높습니다", "product_code": None, "keywords": ["해외송금", "전신환", "전자송금", "수수료"]},
                    {"turn": 2, "role": "customer", "expected_text": "미국으로 1만 달러 보내려면 얼마나 걸리나요?", "product_code": None, "keywords": ["미국", "달러", "송금"]},
                    {"turn": 3, "role": "employee", "expected_text": "전자송금의 경우 당일 또는 익일 도착 가능하며 수수료는 송금 금액과 환율에 따라 다릅니다 1만 달러 기준으로 약 2만원에서 5만원 수준입니다", "product_code": None, "keywords": ["전자송금", "수수료", "환율", "2만원", "5만원"]},
                    {"turn": 3, "role": "customer", "expected_text": "외화예금 계좌도 만들 수 있나요?", "product_code": None, "keywords": ["외화예금", "계좌"]},
                    {"turn": 4, "role": "employee", "expected_text": "네 외화예금 계좌 개설 가능합니다 달러, 유로, 엔화 등 주요 통화로 예금하실 수 있으며 통화별로 금리가 다르게 적용됩니다", "product_code": None, "keywords": ["외화예금", "계좌", "달러", "유로", "엔화", "금리"]},
                    {"turn": 4, "role": "customer", "expected_text": "환전도 여기서 할 수 있나요?", "product_code": None, "keywords": ["환전"]},
                    {"turn": 5, "role": "employee", "expected_text": "네 지점에서 현찰 환전 가능하며 인터넷뱅킹이나 모바일뱅킹에서도 외화예금 계좌로 환전하실 수 있습니다 환율은 실시간으로 변동됩니다", "product_code": None, "keywords": ["환전", "인터넷뱅킹", "모바일뱅킹", "환율"]},
                    {"turn": 5, "role": "customer", "expected_text": "네 감사합니다.", "product_code": None, "keywords": []},
                    {"turn": 6, "role": "employee", "expected_text": "감사합니다.", "product_code": None, "keywords": []}
                ]
            }
        }
        
        return scenarios.get(scenario_type, scenarios['deposit'])  # 기본값: 수신
    
    def start_test_simulation(self, user_id: int, scenario_type: str = 'deposit') -> Dict:
        """테스트 모드 시뮬레이션 시작 - 고정된 시나리오로 STT 성능 및 RAG 연동 테스트"""
        try:
            print(f"🧪 start_test_simulation 시작: user_id={user_id}, scenario_type={scenario_type}")
            # 데이터가 없으면 로드
            if not self.personas_cache or not self.situations_cache:
                print(f"🧪 데이터 캐시가 비어있음 - 로드 시작")
                print(f"🧪   personas_cache: {self.personas_cache is not None}, situations_cache: {self.situations_cache is not None}")
                self.load_simulation_data()
                print(f"🧪 데이터 로드 완료")
                print(f"🧪   personas_cache: {len(self.personas_cache) if self.personas_cache else 0}개")
                print(f"🧪   situations_cache: {len(self.situations_cache) if self.situations_cache else 0}개")
            else:
                print(f"🧪 데이터 캐시가 이미 로드됨")
                print(f"🧪   personas_cache: {len(self.personas_cache) if self.personas_cache else 0}개")
                print(f"🧪   situations_cache: {len(self.situations_cache) if self.situations_cache else 0}개")
            
            # 데이터 로드 검증
            if not self.personas_cache:
                error_msg = "페르소나 데이터를 로드할 수 없습니다. 데이터 파일을 확인해주세요."
                print(f"❌ {error_msg}")
                raise RuntimeError(error_msg)
            if not self.situations_cache:
                error_msg = "상황 데이터를 로드할 수 없습니다. 데이터 파일을 확인해주세요."
                print(f"❌ {error_msg}")
                raise RuntimeError(error_msg)
        except (FileNotFoundError, ValueError, RuntimeError) as e:
            # 이미 처리된 예외는 그대로 전달
            import traceback
            error_trace = traceback.format_exc()
            print(f"❌ start_test_simulation 데이터 로드 실패 (명시적 예외): {str(e)}")
            print(f"상세 오류:\n{error_trace}")
            raise
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            print(f"❌ start_test_simulation 데이터 로드 실패 (예상치 못한 예외): {str(e)}")
            print(f"상세 오류:\n{error_trace}")
            raise RuntimeError(f"시뮬레이션 데이터 로드 중 오류가 발생했습니다: {str(e)}") from e
        
        # 테스트용 고정 페르소나와 상황
        test_persona = {
            "id": "test_persona_001",
            "name": "테스트 고객",
            "gender": "female",
            "age_group": "40대",
            "occupation": "직장인",
            "type": "긍정형",
            "customer_style": "긍정형",
            "tone": "neutral",
            "speech": {"tone": "neutral", "speed": 1.0},
            "utterance_hints": []
        }
        
        # 시나리오 타입에 따른 제목 및 목표 설정
        scenario_titles = {
            'deposit': '수신 상품 상담 테스트',
            'loan': '여신 상품 상담 테스트',
            'card': '카드 상품 상담 테스트',
            'fx': '외환/송금 서비스 테스트'
        }
        
        scenario_intents = {
            'deposit': '정기예금상담',
            'loan': '주택담보대출상담',
            'card': '신용카드상담',
            'fx': '환전문의'
        }
        scenario_products = {
            'deposit': 'DEP-TIM',
            'loan': 'LON-MTG',
            'card': 'CRD-CRE',
            'fx': None
        }
        scenario_has_product_data = {
            'deposit': True,
            'loan': True,
            'card': True,
            'fx': False  # 외환/환전 시나리오는 상품 데이터 없음
        }

        test_situation = {
            "id": f"test_situation_{scenario_type}",
            "title": scenario_titles.get(scenario_type, "STT 성능 및 RAG 연동 테스트"),
            "category": "test",
            "intent": scenario_intents.get(scenario_type, "general"),
            "product": scenario_products.get(scenario_type),
            "has_product_data": scenario_has_product_data.get(scenario_type, True),
            "goals": [
                "금융 용어 STT 인식 정확도 평가",
                "RAG 상품 데이터 연동 확인",
                "지식 평가 로직 검증"
            ],
            "scenarios": []
        }
        
        # 시나리오 타입에 따른 테스트 시나리오 데이터 가져오기
        print(f"🧪 시나리오 타입: {scenario_type}")
        test_scenario = self._get_test_scenario_data(scenario_type)
        
        # 🧪 시나리오 검증 및 디버깅
        print(f"🧪 ========== start_test_simulation 시나리오 검증 ==========")
        print(f"🧪 요청된 scenario_type: {scenario_type}")
        print(f"🧪 반환된 test_scenario turns 개수: {len(test_scenario.get('turns', []))}")
        if test_scenario.get("turns"):
            first_turn = test_scenario["turns"][0]
            second_turn = test_scenario["turns"][1] if len(test_scenario["turns"]) > 1 else None
            print(f"🧪 첫 번째 턴: role='{first_turn.get('role')}', text='{first_turn.get('expected_text', '')[:50]}...'")
            if second_turn:
                print(f"🧪 두 번째 턴: role='{second_turn.get('role')}', text='{second_turn.get('expected_text', '')[:50]}...'")
        print(f"🧪 ======================================================")
        
        # 테스트 모드: 첫 번째 턴(직원 인사)의 expected_text를 초기 안내 메시지로 사용
        first_turn = test_scenario["turns"][0] if test_scenario.get("turns") else None
        first_employee_text = first_turn.get("expected_text", "") if first_turn and first_turn.get("role") == "employee" else ""
        
        initial_message = {
            "type": "instruction",
            "content": first_employee_text if first_employee_text else "안녕하세요, 무엇을 도와드릴까요?",
            "audio_url": None,
            "instruction": first_employee_text if first_employee_text else "테스트 시나리오를 진행합니다. 화면에 표시된 대사를 정확히 따라 말해주세요."
        }
        
        return {
            "session_id": f"test_session_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "persona": test_persona,
            "situation": test_situation,
            "initial_message": initial_message,
            "test_scenario": test_scenario,
            "is_test_mode": True,
            "conversation_history": []  # 빈 배열로 시작
        }
    
    def start_voice_simulation(self, user_id: int, persona_id: str, situation_id: str, gender: str = 'male') -> Dict:
        """음성 시뮬레이션 시작"""
        try:
            # 데이터가 없으면 로드
            if not self.personas_cache or not self.situations_cache:
                print(f"📊 시뮬레이션 데이터 로딩 시작...")
                self.load_simulation_data()
            
            # 데이터 로드 확인
            if not self.personas_cache:
                error_msg = f"페르소나 데이터를 로드할 수 없습니다. 데이터 파일 경로: {self.data_path}"
                print(f"❌ {error_msg}")
                raise ValueError(error_msg)
            
            if not self.situations_cache:
                error_msg = f"상황 데이터를 로드할 수 없습니다. 데이터 파일 경로: {self.data_path}"
                print(f"❌ {error_msg}")
                raise ValueError(error_msg)
            
            print(f"✅ 데이터 로드 확인: 페르소나 {len(self.personas_cache)}개, 상황 {len(self.situations_cache)}개")
            
            # 페르소나와 상황 조회
            persona = None
            situation = None
            
            if self.personas_cache:
                # id 필드로 조회 (personas_expanded_minified2.json은 id 필드만 사용)
                persona = next((p for p in self.personas_cache if p.get("id") == persona_id), None)
                print(f"페르소나 조회: {persona_id} -> {persona is not None}")
                if persona:
                    print(f"✅ 페르소나 찾음: {persona.get('id')}, gender={persona.get('gender')}, age_group={persona.get('age_group')}")
                else:
                    # 사용 가능한 페르소나 ID 샘플 출력
                    available_ids = [p.get('id', 'N/A') for p in self.personas_cache[:5]]
                    print(f"⚠️ 페르소나 {persona_id}를 찾지 못함. 사용 가능한 ID 샘플: {available_ids}")
            
            if self.situations_cache:
                situation = next((s for s in self.situations_cache if s.get("id") == situation_id), None)
                print(f"상황 조회: {situation_id} -> {situation is not None}")
                if not situation:
                    # 사용 가능한 상황 ID 샘플 출력
                    available_ids = [s.get('id', 'N/A') for s in self.situations_cache[:5]]
                    print(f"⚠️ 상황 {situation_id}를 찾지 못함. 사용 가능한 ID 샘플: {available_ids}")
            
            # 페르소나를 찾지 못했으면 첫 번째 페르소나 사용
            if not persona and self.personas_cache:
                persona = self.personas_cache[0]
                persona_id_found = persona.get('id', 'Unknown')
                print(f"⚠️ 페르소나 {persona_id}를 찾지 못해 첫 번째 페르소나 사용: {persona_id_found}")
            
            # 상황을 찾지 못했으면 첫 번째 상황 사용
            if not situation and self.situations_cache:
                situation = self.situations_cache[0]
                print(f"⚠️ 상황 {situation_id}를 찾지 못해 첫 번째 상황 사용: {situation.get('id')}")
            
            if not persona:
                error_msg = f"페르소나를 찾을 수 없습니다: {persona_id} (캐시에 {len(self.personas_cache) if self.personas_cache else 0}개 페르소나 존재)"
                print(f"❌ {error_msg}")
                raise ValueError(error_msg)
            
            if not situation:
                error_msg = f"상황을 찾을 수 없습니다: {situation_id} (캐시에 {len(self.situations_cache) if self.situations_cache else 0}개 상황 존재)"
                print(f"❌ {error_msg}")
                raise ValueError(error_msg)
        except ValueError as e:
            # ValueError는 그대로 전달 (400 에러로 처리)
            raise
        except Exception as e:
            # 예상치 못한 오류는 상세 로그와 함께 재발생
            import traceback
            error_trace = traceback.format_exc()
            print(f"❌ start_voice_simulation 오류 발생: {str(e)}")
            print(f"상세 오류:\n{error_trace}")
            raise RuntimeError(f"시뮬레이션 시작 중 오류가 발생했습니다: {str(e)}") from e
        
        # 성별 정보는 이미 페르소나 데이터에 포함되어 있으므로 추가하지 않음
        
        # 🚨 변경: 첫 시작은 사용자가 직접 말해야 함
        # 안내 메시지만 반환 (실제 대화는 사용자가 말을 시작하면 시작)
        initial_message = {
            "type": "instruction",
            "content": "안녕하세요, 무엇을 도와드릴까요?",
            "audio_url": None,  # 안내 메시지는 TTS 없음
            "instruction": "위 메시지로 시작하세요. 마이크 버튼을 눌러 말을 시작해주세요."
        }
        
        # 초기 고객 메시지는 생성하지 않음 (사용자가 말하면 그때부터 시작)
        initial_customer_message = None
        
        # 페르소나 ID와 필드명 처리 (persona_id 또는 id)
        persona_id_value = persona.get("id", "Unknown")
        # customer_style 필드가 있으면 type으로 사용
        persona_type = persona.get("customer_style") or persona.get("type", "")
        # tone은 speech.tone 또는 tone
        speech_obj = persona.get("speech", {})
        persona_tone = speech_obj.get("tone", "neutral") if isinstance(speech_obj, dict) else persona.get("tone", "neutral")
        
        return {
            "session_id": f"session_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "persona": {
                "id": persona_id_value,
                "persona_id": persona_id_value,
                "name": persona_id_value,
                "gender": persona.get("gender", ""),
                "age_group": persona.get("age_group", ""),
                "occupation": persona.get("occupation", ""),
                "type": persona_type,
                "customer_style": persona.get("customer_style", ""),
                "tone": persona_tone,
                "style": speech_obj if isinstance(speech_obj, dict) else persona.get("style", {}),
                "sample_utterances": persona.get("utterance_hints", []) or persona.get("sample_utterances", []),
                "utterance_hints": persona.get("utterance_hints", []),
                "speech": speech_obj
            },
            "situation": {
                "id": situation["id"],
                "title": situation.get("title", ""),
                "category": situation.get("category", "general"),
                "goals": situation.get("goals", []),
                "scenarios": situation.get("scenarios", [])
            },
            "initial_message": initial_message  # 안내 메시지 ("안녕하세요, 무엇을 도와드릴까요?"로 시작하라는 안내)
        }
    
    def process_voice_interaction(self, session_data: Dict, audio_data: bytes, 
                                user_message: str = "") -> Dict:
        """음성 상호작용 처리"""
        try:
            print(f"음성 상호작용 처리 시작: session_data keys = {list(session_data.keys())}")
            
            # 🧪 테스트 모드 체크 (로깅용으로만 사용, 처리 로직은 일반 모드와 동일)
            is_test_mode = session_data.get("is_test_mode", False)
            has_test_scenario = bool(session_data.get("test_scenario"))
            
            if is_test_mode or has_test_scenario:
                print("🧪 테스트 모드 감지 (일반 모드와 동일하게 처리)")
            else:
                print("✅ 일반 모드로 처리합니다.")
            
            if not session_data or "persona" not in session_data:
                raise ValueError("세션 데이터가 올바르지 않습니다.")
                
            persona = session_data["persona"]
            situation = session_data.get("situation", session_data.get("scenario", {}))
            
            print(f"페르소나: {persona.get('persona_id', persona.get('id', 'Unknown'))}")
            print(f"상황: {situation.get('id', situation.get('scenario_id', 'Unknown'))}")
            
            # 페르소나와 상황 정보를 실제 데이터에서 조회
            persona_id = persona.get('persona_id', persona.get('id', ''))
            situation_id = situation.get('id', situation.get('scenario_id', ''))
            
            # 실제 페르소나와 상황 데이터 조회
            actual_persona = None
            actual_situation = None
            
            if self.personas_cache and persona_id:
                # id 필드로 조회 (personas_expanded_minified2.json은 id 필드만 사용)
                actual_persona = next((p for p in self.personas_cache if p.get("id") == persona_id), None)
                if actual_persona:
                    print(f"✅ 실제 페르소나 데이터 조회 성공: {persona_id}")
                else:
                    print(f"❌ 실제 페르소나 데이터 조회 실패: {persona_id}")
                    print(f"   캐시에 있는 페르소나 ID 샘플: {[p.get('id')[:10] for p in list(self.personas_cache[:5])]}")
            
            if self.situations_cache and situation_id:
                actual_situation = next((s for s in self.situations_cache if s.get("id") == situation_id), None)
                if actual_situation:
                    print(f"실제 상황 데이터 조회 성공: {situation_id}")
                else:
                    print(f"실제 상황 데이터 조회 실패: {situation_id}")
            
            # STT: 음성을 텍스트로 변환 (사용자가 제공한 텍스트가 있으면 우선 사용)
            if not user_message:
                print(f"STT 처리 시작: 오디오 크기 {len(audio_data) if audio_data else 0} bytes")
                transcribed_text = self._speech_to_text(audio_data)
            else:
                print(f"텍스트 입력: '{user_message}'")
                transcribed_text = user_message
            
            print(f"최종 텍스트: '{transcribed_text}'")
            
            # 대화 히스토리 구성 (세션 데이터에서 추출 및 누적) - 먼저 초기화
            conversation_history = session_data.get("conversation_history", [])
            print(f"🧪 테스트 모드: 세션에서 가져온 conversation_history 길이={len(conversation_history)}")
            if conversation_history:
                for idx, msg in enumerate(conversation_history):
                    role = msg.get('role', 'MISSING')
                    text = msg.get('text', '')[:30]
                    print(f"🧪   기존 히스토리 [{idx}]: role='{role}' (type: {type(role).__name__}), text='{text}...'")
                    # 🧪 role 검증: 반드시 'employee' 또는 'customer'여야 함
                    if role not in ['employee', 'customer']:
                        print(f"🧪 ⚠️ 경고: 기존 히스토리 [{idx}]의 role이 잘못됨: '{role}', 올바른 role로 수정 필요")
            
            # 🧪 테스트 모드: 시나리오의 expected_text 사용 (LLM 호출 건너뛰기)
            if is_test_mode or has_test_scenario:
                # 테스트 모드: 시나리오에서 고객 응답 가져오기
                test_scenario = session_data.get("test_scenario", {})
                turns = test_scenario.get("turns", [])
                
                # 🧪 시나리오 검증 및 디버깅
                print(f"🧪 ========== 테스트 모드 시나리오 검증 ==========")
                print(f"🧪 test_scenario 존재 여부: {bool(test_scenario)}")
                print(f"🧪 turns 개수: {len(turns)}")
                if turns:
                    print(f"🧪 첫 번째 턴 정보: role='{turns[0].get('role')}', text='{turns[0].get('expected_text', '')[:50]}...'")
                    if len(turns) > 1:
                        print(f"🧪 두 번째 턴 정보: role='{turns[1].get('role')}', text='{turns[1].get('expected_text', '')[:50]}...'")
                else:
                    print(f"🧪 ⚠️ 경고: turns가 비어있습니다!")
                print(f"🧪 ============================================")
                
                # current_turn_index 초기화 (없으면 0)
                if "current_turn_index" not in session_data:
                    session_data["current_turn_index"] = 0
                current_turn_index = session_data.get("current_turn_index", 0)
                
                print(f"🧪 테스트 모드: current_turn_index={current_turn_index}, 전체 턴 수={len(turns)}")
                print(f"🧪 사용자가 말한 텍스트: '{transcribed_text}'")
                
                # 현재 턴 확인
                if current_turn_index >= len(turns):
                    print(f"🧪 테스트 모드: 모든 턴 완료")
                    customer_response_text = ""
                    next_turn_expected_text = ""
                    next_turn_role = None
                else:
                    current_turn = turns[current_turn_index]
                    current_turn_role = current_turn.get("role")
                    print(f"🧪 테스트 모드: 현재 턴={current_turn_index}, 역할={current_turn_role}, 텍스트={current_turn.get('expected_text', '')[:50]}...")
                    
                    # 현재 턴이 직원 턴인지 확인
                    if current_turn_role == "employee":
                        # 🧪 사용자가 녹음한 직원 발화를 conversation_history에 추가
                        # 중요: 사용자가 실제로 말한 것이므로 항상 추가해야 함
                        # 단, 같은 텍스트가 이미 마지막에 있으면 중복 방지
                        is_duplicate = False
                        if conversation_history:
                            last_msg = conversation_history[-1]
                            if (last_msg.get("role") == "employee" and 
                                last_msg.get("text") == transcribed_text):
                                print(f"🧪 ⚠️ 중복 감지: 마지막 메시지와 동일한 직원 발화, 추가하지 않음")
                                is_duplicate = True
                        
                        if not is_duplicate:
                            # 사용자가 실제로 녹음한 직원 발화를 conversation_history에 추가
                            # 🧪 중요: role은 반드시 'employee' 문자열이어야 함
                            new_employee_msg = {
                                "role": "employee",  # 문자열 'employee'
                                "text": transcribed_text,
                                "timestamp": datetime.now().isoformat()
                            }
                            conversation_history.append(new_employee_msg)
                            print(f"🧪 테스트 모드: 사용자 녹음 직원 발화를 conversation_history에 추가")
                            print(f"🧪   추가된 메시지: role='{new_employee_msg['role']}' (type: {type(new_employee_msg['role']).__name__}), text='{transcribed_text[:50]}...'")
                            print(f"🧪   conversation_history 현재 길이: {len(conversation_history)}")
                            # 마지막 메시지 확인
                            if conversation_history:
                                last_msg = conversation_history[-1]
                                print(f"🧪   마지막 메시지 확인: role='{last_msg.get('role')}', text='{last_msg.get('text', '')[:30]}...'")
                        else:
                            print(f"🧪 테스트 모드: 중복된 직원 발화이므로 추가하지 않음")
                        
                        # 🧪 다음 턴(고객)의 expected_text 가져오기
                        # 직원이 말한 후에는 반드시 고객 응답이 자동으로 나와야 함
                        next_turn_index = current_turn_index + 1
                        print(f"🧪 테스트 모드: 다음 턴 인덱스 계산 - current_turn_index={current_turn_index}, next_turn_index={next_turn_index}, 전체 턴 수={len(turns)}")
                        if next_turn_index < len(turns):
                            next_turn = turns[next_turn_index]
                            next_turn_role = next_turn.get("role")
                            print(f"🧪 테스트 모드: 다음 턴 정보 - 인덱스={next_turn_index}, role='{next_turn_role}', expected_text='{next_turn.get('expected_text', '')[:50]}...'")
                            if next_turn_role == "customer":
                                # 🧪 고객 응답을 자동으로 가져옴
                                customer_response_text = next_turn.get("expected_text", "")
                                print(f"🧪 ✅ 테스트 모드: 시나리오에서 고객 응답 가져옴 (턴 {next_turn_index}): '{customer_response_text}'")
                                print(f"🧪 ✅ 고객 응답 길이: {len(customer_response_text)}자")
                                
                                # 🧪 그 다음 턴(직원)의 expected_text 가져오기 (사용자가 다음에 말할 내용)
                                next_next_turn_index = next_turn_index + 1
                                if next_next_turn_index < len(turns):
                                    next_next_turn = turns[next_next_turn_index]
                                    if next_next_turn.get("role") == "employee":
                                        next_turn_expected_text = next_next_turn.get("expected_text", "")
                                        next_turn_role = "employee"
                                        # current_turn_index 업데이트 (다음 직원 턴으로 이동)
                                        session_data["current_turn_index"] = next_next_turn_index
                                        print(f"🧪 테스트 모드: 다음 직원 턴 expected_text (턴 {next_next_turn_index}): {next_turn_expected_text[:50]}...")
                                    else:
                                        # 다음 턴도 고객이면 (이상한 경우)
                                        next_turn_role = "customer"
                                        session_data["current_turn_index"] = next_next_turn_index
                                else:
                                    # 모든 턴 완료
                                    next_turn_role = None
                                    next_turn_expected_text = ""
                                    session_data["current_turn_index"] = next_next_turn_index
                            else:
                                # 다음 턴도 직원이면 고객 응답 없음 (이상한 경우)
                                print(f"🧪 ⚠️ 경고: 다음 턴({next_turn_index})도 직원입니다. 고객 응답이 없습니다.")
                                customer_response_text = ""
                                next_turn_expected_text = next_turn.get("expected_text", "")
                                next_turn_role = "employee"
                                session_data["current_turn_index"] = next_turn_index
                        else:
                            # 모든 턴 완료
                            print(f"🧪 테스트 모드: 모든 턴 완료 (다음 턴 인덱스 {next_turn_index} >= 전체 턴 수 {len(turns)})")
                            customer_response_text = ""
                            next_turn_expected_text = ""
                            next_turn_role = None
                    else:
                        # 현재 턴이 고객 턴이면 (이상한 경우, 로그만 남기고 처리)
                        print(f"🧪 ⚠️ 경고: 현재 턴이 고객 턴입니다. 직원이 말해야 하는데 고객 턴이 나왔습니다.")
                        customer_response_text = ""
                        next_turn_expected_text = ""
                        next_turn_role = None
                
                # 변수 초기화 (위에서 설정되지 않은 경우)
                if 'customer_response_text' not in locals():
                    customer_response_text = ""
                if 'next_turn_expected_text' not in locals():
                    next_turn_expected_text = ""
                if 'next_turn_role' not in locals():
                    next_turn_role = None
                
                # 🧪 고객 응답이 있으면 히스토리에 추가 및 TTS 생성
                print(f"🧪 ========== 고객 응답 처리 시작 ==========")
                print(f"🧪 customer_response_text 존재 여부: {bool(customer_response_text)}")
                if customer_response_text:
                    print(f"🧪 customer_response_text 내용: '{customer_response_text}'")
                    # 🧪 중복 체크: 같은 고객 응답이 이미 conversation_history에 있는지 확인
                    is_customer_duplicate = False
                    for existing_msg in conversation_history:
                        if existing_msg.get("role") == "customer" and existing_msg.get("text") == customer_response_text:
                            print(f"🧪 ⚠️ 중복 감지: 같은 고객 응답이 이미 conversation_history에 있음, 추가하지 않음")
                            is_customer_duplicate = True
                            break
                    
                    if not is_customer_duplicate:
                        # 🧪 중요: role은 반드시 'customer' 문자열이어야 함
                        new_customer_msg = {
                            "role": "customer",  # 문자열 'customer'
                            "text": customer_response_text,
                            "timestamp": datetime.now().isoformat()
                        }
                        conversation_history.append(new_customer_msg)
                        print(f"🧪 ✅ 테스트 모드: 고객 응답을 conversation_history에 자동 추가")
                        print(f"🧪   추가된 메시지: role='{new_customer_msg['role']}' (type: {type(new_customer_msg['role']).__name__}), text='{customer_response_text}'")
                        print(f"🧪   conversation_history 현재 길이={len(conversation_history)}")
                        # 전체 conversation_history 확인 (role 아이콘 포함)
                        print(f"🧪   conversation_history 전체 내용:")
                        for idx, msg in enumerate(conversation_history):
                            role_icon = "🔵" if msg.get('role') == 'employee' else "🟢"
                            print(f"🧪     [{idx}] {role_icon} role='{msg.get('role')}', text='{msg.get('text', '')[:50]}...'")
                        
                        # TTS: 고객 응답을 음성으로 변환
                        print(f"🧪 테스트 모드: 고객 응답 TTS 처리 시작 - '{customer_response_text[:30]}...'")
                        response_persona = actual_persona if actual_persona else persona
                        customer_audio = self._text_to_speech(customer_response_text, response_persona)
                        print(f"🧪 ✅ 테스트 모드: TTS 완료 - 오디오 길이 {len(customer_audio) if customer_audio else 0} bytes")
                        if customer_audio:
                            print(f"🧪 ✅ customer_audio 생성 성공 - 프론트엔드로 전송 예정")
                        else:
                            print(f"🧪 ❌ customer_audio 생성 실패")
                    else:
                        print(f"🧪 테스트 모드: 중복된 고객 응답이므로 추가하지 않음")
                        customer_audio = None
                else:
                    # 🧪 고객 응답이 없으면 TTS도 없음
                    print(f"🧪 ❌ 테스트 모드: 고객 응답이 없습니다 (customer_response_text가 비어있음)")
                    print(f"🧪 ❌ 이는 시나리오에서 다음 턴을 찾지 못했거나, 다음 턴이 customer가 아니라는 의미입니다.")
                    customer_audio = None
                print(f"🧪 ========== 고객 응답 처리 완료 ==========")
                
                # 응답 평가
                evaluation = self._evaluate_user_response(transcribed_text, actual_persona or persona, actual_situation or situation)
                
                # 🧪 RAG 평가 생성 (테스트 모드)
                # 상황에 상품 데이터가 없으면 RAG 평가/표시를 완전히 비활성화
                situation_context = actual_situation or situation or {}
                rag_enabled = situation_context.get("has_product_data", True)
                
                # session_data에서 rag_evaluations 가져오기 (없으면 초기화)
                rag_evaluations = session_data.get("rag_evaluations", [])
                if not rag_enabled and rag_evaluations:
                    # 상품 데이터가 없으면 기존에 누적된 평가도 제거
                    rag_evaluations = []
                    session_data["rag_evaluations"] = rag_evaluations
                
                # 현재 턴 정보 가져오기
                current_turn = turns[current_turn_index] if current_turn_index < len(turns) else None
                current_turn_role = current_turn.get("role") if current_turn else None
                
                # 직원 발화인 경우 RAG 평가 생성
                if rag_enabled and current_turn_role == "employee":
                    expected_product_code = current_turn.get("product_code") if current_turn else None
                    expected_keywords = current_turn.get("keywords", []) if current_turn else []
                    
                    # RAG 연동 평가
                    rag_eval = self._evaluate_rag_integration(
                        transcribed_text,
                        expected_product_code,
                        expected_keywords
                    )
                    # RAG 평가 결과 누적 저장
                    rag_evaluations.append({
                        "turn_index": current_turn_index,
                        "role": "employee",
                        "expected_product_code": expected_product_code,
                        "utterance": transcribed_text,  # 발화 내용 추가
                        "evaluation": rag_eval
                    })
                    print(f"🧪 ✅ 직원 발화 RAG 평가 생성: {rag_eval['score']:.1f}점 (턴 {current_turn_index})")
                    print(f"🧪   - 키워드 점수: {rag_eval.get('keyword_score', 0):.1f}점")
                    print(f"🧪   - RAG 상품 정보 점수: {rag_eval.get('rag_product_info_score', 0):.1f}점")
                    
                    # session_data에 저장
                    session_data["rag_evaluations"] = rag_evaluations
                
                # 🚫 테스트 모드에서는 고객 발화 RAG 평가를 생성하지 않음 (직원 발화 평가만 수행)
                # 고객 응답이 자동 생성된 경우에도 고객 발화 RAG 평가는 생성하지 않음
                # if customer_response_text:
                #     # 다음 턴(고객) 정보 가져오기
                #     next_turn_index_for_customer = current_turn_index + 1
                #     if next_turn_index_for_customer < len(turns):
                #         next_turn = turns[next_turn_index_for_customer]
                #         if next_turn.get("role") == "customer":
                #             expected_product_code_customer = next_turn.get("product_code")
                #             expected_keywords_customer = next_turn.get("keywords", [])
                #             
                #             # 고객 발화 RAG 평가 생성 (일반 모드와 동일한 평가 로직 사용)
                #             rag_eval_customer = self._evaluate_rag_integration(
                #                 customer_response_text,
                #                 expected_product_code_customer,
                #                 expected_keywords_customer,
                #                 role="customer"
                #             )
                #             # RAG 평가 결과 누적 저장
                #             rag_evaluations.append({
                #                 "turn_index": next_turn_index_for_customer,
                #                 "role": "customer",
                #                 "expected_product_code": expected_product_code_customer,
                #                 "utterance": customer_response_text,  # 발화 내용 추가
                #                 "evaluation": rag_eval_customer
                #             })
                #             print(f"🧪 ✅ 고객 발화 RAG 평가 생성: {rag_eval_customer['score']:.1f}점 (턴 {next_turn_index_for_customer})")
                #             
                #             # session_data에 저장
                #             session_data["rag_evaluations"] = rag_evaluations
                
                # RAG 평가 종합 결과 생성 (상품 데이터가 있을 때만)
                rag_summary = self._summarize_rag_evaluations(rag_evaluations) if (rag_enabled and rag_evaluations) else None
                
                # 종료 신호 체크 (모든 턴 완료 시)
                end_signal = False
                if session_data.get("current_turn_index", 0) >= len(turns):
                    end_signal = True
                    print(f"🧪 테스트 모드: 모든 턴 완료 - 종료 신호 설정")
                
                # conversation_history를 세션 데이터에 저장 (다음 요청에서 사용)
                session_data["conversation_history"] = conversation_history
                
                # conversation_history 디버깅
                print(f"🧪 테스트 모드: conversation_history 최종 상태 ({len(conversation_history)}개 메시지):")
                for idx, msg in enumerate(conversation_history):
                    print(f"🧪   [{idx}] role={msg.get('role')}, text={msg.get('text', '')[:50]}...")
                
                # 응답에 포함할 conversation_history 복사 (role 확인 및 강제 검증)
                response_history = []
                print(f"🧪 테스트 모드: response_history 생성 시작, conversation_history 길이={len(conversation_history)}")
                for idx, msg in enumerate(conversation_history):
                    # role이 명확하게 설정되어 있는지 확인
                    role = msg.get('role', '')
                    text = msg.get('text', '')
                    
                    print(f"🧪   원본 메시지 [{idx}]: role='{role}' (type: {type(role).__name__}), text='{text[:30]}...'")
                    
                    # 🧪 role 검증 및 수정
                    if role not in ['employee', 'customer']:
                        print(f"🧪 ⚠️ 경고 [{idx}]: 잘못된 role 값 '{role}' (type: {type(role).__name__}), text='{text[:30]}...'")
                        # 🧪 role이 없거나 잘못된 경우, conversation_history의 순서와 시나리오를 기반으로 추정
                        # 하지만 이건 임시 방편이고, 실제로는 role이 올바르게 설정되어야 함
                        # 시나리오를 확인하여 올바른 role 추정 시도
                        test_scenario = session_data.get("test_scenario", {})
                        turns = test_scenario.get("turns", [])
                        # 현재 인덱스에 해당하는 턴을 찾아서 role 추정
                        if idx < len(turns):
                            estimated_role = turns[idx].get("role", "customer")
                            print(f"🧪   시나리오 기반 role 추정: '{estimated_role}'")
                            role = estimated_role if estimated_role in ['employee', 'customer'] else 'customer'
                        else:
                            role = 'customer'  # 기본값
                        print(f"🧪   최종 role: '{role}'")
                    
                    # 🧪 role이 올바른지 최종 확인
                    if role not in ['employee', 'customer']:
                        print(f"🧪 ❌ 심각한 오류 [{idx}]: role이 여전히 잘못됨 '{role}', 강제로 'customer'로 설정")
                        role = 'customer'
                    
                    print(f"🧪   response_history에 추가: role='{role}', text='{text[:30]}...'")
                    
                    response_history.append({
                        "role": role,  # 🧪 명확하게 'employee' 또는 'customer'
                        "text": text,
                        "timestamp": msg.get('timestamp', datetime.now().isoformat())
                    })
                
                print(f"🧪 테스트 모드: response_history 생성 완료, 길이={len(response_history)}")
                for idx, msg in enumerate(response_history):
                    print(f"🧪   최종 response_history [{idx}]: role='{msg.get('role')}', text='{msg.get('text', '')[:30]}...'")
                
                result = {
                    "transcribed_text": transcribed_text,
                    "customer_response": customer_response_text,
                    "customer_audio": customer_audio,
                    "feedback": evaluation,
                    "followups": [],
                    "safety_notes": "",
                    "conversation_phase": "ongoing",
                    "session_score": self._calculate_session_score(session_data),
                    "conversation_history": response_history,  # 🧪 role이 명확하게 설정된 히스토리
                    "end_signal": end_signal,
                    "end_message": "테스트 시나리오가 완료되었습니다." if end_signal else None,
                    "offtopic_count": 0,
                    "is_test_mode": True,
                    "current_turn_index": session_data.get("current_turn_index", 0),
                    "next_turn_expected_text": next_turn_expected_text,
                    "next_turn_role": next_turn_role,
                    "rag_evaluations": rag_evaluations if rag_enabled else None,  # 🧪 RAG 평가 결과 (상품 데이터 없으면 표시 생략)
                    "rag_summary": rag_summary if rag_enabled else None  # 🧪 RAG 평가 종합 결과 (상품 데이터 없으면 표시 생략)
                }
                
                print(f"🧪 테스트 모드: 음성 상호작용 처리 완료 - conversation_history {len(response_history)}개 메시지 반환")
                print(f"🧪 응답 conversation_history role 확인:")
                for idx, msg in enumerate(response_history):
                    print(f"🧪   [{idx}] role='{msg.get('role')}', text='{msg.get('text', '')[:30]}...'")
                return result
            
            # 일반 모드 및 테스트 모드: LLM 사용 (테스트 모드도 일반 모드와 동일하게 처리)
            # STT에서 이미 정규화가 완료되었으므로 추가 처리 불필요
            normalized_text = transcribed_text
            corrections = []  # 이미 STT에서 처리됨
            needs_clarification = False  # 이미 STT에서 처리됨
            
            # 테스트 모드 관련 변수 초기화 (일반 모드에서도 사용)
            next_turn_expected_text = ""
            next_turn_role = None
            
            # 2. 상품 카탈로그 매칭
            print("📋 상품 카탈로그 매칭 시작")
            catalog_hits = self.match_product_catalog(normalized_text)
            print(f"카탈로그 매칭 결과: {len(catalog_hits)}개")
            for hit in catalog_hits:
                print(f"  - {hit['product']} ({hit['category_ko']})")
            
            # 3. RAG 검색 쿼리 확장
            print("🔍 RAG 검색 쿼리 확장")
            expanded_queries = self.expand_search_query(normalized_text, catalog_hits)
            print(f"확장된 쿼리: {expanded_queries}")
            
            # 고객 응답 생성 (프롬프트 오케스트레이터 사용)
            print("고객 응답 생성 시작")
            
            # 실제 페르소나와 상황 데이터 사용
            response_persona = actual_persona if actual_persona else persona
            response_situation = actual_situation if actual_situation else situation
            
            # 상황 정보 추출 (또는 기본값 사용)
            final_situation = response_situation
            if not final_situation or not final_situation.get('id'):
                # 기본값 사용
                final_situation = get_situation_defaults('deposit')
            else:
                # 상황 기본 구조 확보
                final_situation = {
                    'id': final_situation.get('id', 'deposit'),
                    'title': final_situation.get('title', '상담'),
                    'goals': final_situation.get('goals', ['고객 요구사항 파악', '핵심 정보 안내']),
                    'required_slots': final_situation.get('required_slots', []),
                    'forbidden_claims': final_situation.get('forbidden_claims', []),
                    'style_rules': final_situation.get('style_rules', ['숫자는 예시로만', '확인 후 안내']),
                    'disclaimer': final_situation.get('disclaimer', '실제 조건은 정책에 따라 달라질 수 있습니다.')
                }
            
            # 🚨 변경: 첫 메시지 처리 (안내 메시지는 히스토리에 추가하지 않음)
            # 사용자가 실제로 말을 시작하면 그때부터 대화 시작
            is_first_message = len(conversation_history) == 0
            
            # 🔥 이탈 감지 및 피벗 처리
            offtopic_count = session_data.get("offtopic_count", 0)
            is_offtopic = False
            
            # 첫 메시지가 아닌 경우에만 이탈 감지 (인사말은 허용)
            if not is_first_message:
                is_offtopic = not is_on_topic(transcribed_text)
                if is_offtopic:
                    offtopic_count += 1
                    print(f"⚠️ 이탈 감지 (횟수: {offtopic_count}): '{transcribed_text}'")
                else:
                    # 온토픽으로 돌아오면 카운터 리셋
                    if offtopic_count > 0:
                        print(f"✅ 온토픽으로 복귀")
                    offtopic_count = 0
            else:
                # 첫 메시지도 이탈 감지 (인사말 제외)
                is_offtopic = not is_on_topic(transcribed_text)
                if is_offtopic:
                    offtopic_count = 1
                    print(f"⚠️ 첫 메시지 이탈 감지: '{transcribed_text}'")
            
            # 이탈이 감지된 경우 에러 메시지만 반환 (대화에는 추가하지 않음)
            if is_offtopic and offtopic_count >= 1:
                # 4회 이상 이탈 시 세션 종료 (3번까지는 허용)
                if offtopic_count >= 4:
                    result = {
                        "transcribed_text": transcribed_text,
                        "customer_response": "",
                        "customer_audio": None,
                        "feedback": "이탈이 4회 이상 발생하여 세션이 종료되었습니다.",
                        "conversation_phase": "abandoned",
                        "session_score": 0,
                        "conversation_history": conversation_history,
                        "end_signal": True,
                        "offtopic_count": offtopic_count,
                        "error": "업무 맥락을 벗어난 발화가 반복되어 세션이 종료되었습니다."
                    }
                    
                    print(f"🔚 세션 종료: 이탈 {offtopic_count}회")
                    return result
                
                # 1-3회 이탈: 에러 메시지만 반환 (사용자 메시지는 대화에 추가) + 점수 감점
                # 사용자 발화는 히스토리에 추가 (프론트엔드에서 처리하도록)
                conversation_history.append({
                    "role": "employee", 
                    "text": transcribed_text,
                    "timestamp": datetime.now().isoformat()
                })
                
                current_score = self._calculate_session_score(session_data)
                penalty = offtopic_count * 5  # 이탈 1회당 5점 감점
                penalized_score = max(0, current_score - penalty)
                
                result = {
                    "transcribed_text": transcribed_text,
                    "customer_response": "",
                    "customer_audio": None,
                    "feedback": "",
                    "conversation_phase": "ongoing",
                    "session_score": penalized_score,
                    "conversation_history": conversation_history,  # 사용자 발화 포함
                    "end_signal": False,
                    "offtopic_count": offtopic_count,
                    "error": "은행 신입사원 온보딩입니다. 관련된 답변만 하십시오."
                }
                
                print(f"⚠️ 이탈 감지 (이탈 {offtopic_count}회) - 점수 감점: {penalty}점 (현재 점수: {penalized_score})")
                return result
            
            # 정상 진행: 온토픽으로 돌아왔으므로 이탈 카운터 리셋
            if not is_offtopic:
                offtopic_count = 0
            
            # 현재 직원 발화를 히스토리에 추가
            conversation_history.append({
                "role": "employee", 
                "text": transcribed_text,
                "timestamp": datetime.now().isoformat()
            })
            
            # 세션 데이터에 이탈 카운터 업데이트
            session_data["offtopic_count"] = offtopic_count
            
            print(f"대화 히스토리: {len(conversation_history)}턴")
            for i, msg in enumerate(conversation_history[-4:]):
                print(f"  {i+1}. {msg.get('role', 'unknown')}: {msg.get('text', '')[:50]}...")
            
            # 달성된 목표 정보 추출 (세션 데이터에서)
            achieved_goals = session_data.get("achieved_goals", [])  # 프론트엔드에서 분석한 결과
            achieved_goal_indices = (
                achieved_goals if isinstance(achieved_goals, list) else []
            )
            
            # 고객 감정형 추출 (페르소나 또는 세션 데이터에서)
            customer_emotion = response_persona.get("type", "긍정형") if response_persona else "긍정형"
            if "customer_emotion" in session_data:
                customer_emotion = session_data["customer_emotion"]
            
            # 최근 직원 질문 추출 (대화 히스토리에서)
            last_employee_questions = []
            for msg in conversation_history[-5:]:  # 최근 5턴만 확인
                if msg.get("role") == "employee":
                    text = msg.get("text", "")
                    if "?" in text or "질문" in text or "문의" in text:
                        last_employee_questions.append(text)

            # 🔚 직원 발화에서 종료 트리거 감지
            employee_has_closing_trigger = any(
                trigger in transcribed_text for trigger in END_CONVERSATION_TRIGGERS
            )
            
            if employee_has_closing_trigger:
                # 직원이 종료 신호를 보냈으면 고객도 자연스럽게 종료 응답
                customer_response_text = "네, 알겠습니다. 감사합니다!"
                end_signal = True
                print(f"🔚 직원 종료 트리거 감지 - 고객 종료 응답으로 변경")
                
                # 고객 응답을 히스토리에 추가
                conversation_history.append({
                    "role": "customer",
                    "text": customer_response_text,
                    "timestamp": datetime.now().isoformat()
                })
                
                # TTS: 고객 응답을 음성으로 변환
                print(f"TTS 처리 시작")
                customer_audio = self._text_to_speech(customer_response_text, response_persona)
                print(f"TTS 완료: 오디오 길이 {len(customer_audio) if customer_audio else 0}")
                
                result = {
                    "transcribed_text": transcribed_text,
                    "customer_response": customer_response_text,
                    "customer_audio": customer_audio,
                    "feedback": "",
                    "followups": [],
                    "safety_notes": "",
                    "conversation_phase": "ongoing",
                    "session_score": self._calculate_session_score(session_data),
                    "conversation_history": conversation_history,
                    "end_signal": end_signal,
                    "end_message": "대화가 자연스럽게 마무리되었습니다. 피드백을 확인하시겠습니까?",
                    "offtopic_count": offtopic_count
                }
                
                print("음성 상호작용 처리 완료 (종료 트리거 감지)")
                return result

            # 프롬프트 오케스트레이터로 메시지 구성
            messages = compose_llm_messages(
                persona=response_persona,
                situation=final_situation,
                user_text=normalized_text,  # 정규화된 텍스트 사용
                rag_hits=[],  # TODO: RAG 검색 결과 추가
                history=conversation_history[-10:],  # 최근 10턴까지 포함 (더 많은 맥락)
                extras={
                    "userText_raw": transcribed_text,  # 원본 텍스트
                    "corrections": corrections,  # 교정 정보
                    "catalogHits": catalog_hits,  # 카탈로그 매칭 결과
                    "needs_clarification": needs_clarification,  # 재확인 필요 여부
                    "expanded_queries": expanded_queries,  # 확장된 검색 쿼리
                    "achieved_goals": achieved_goals,  # 달성된 목표 인덱스 리스트
                    "customer_emotion": customer_emotion,  # 고객 감정형
                    "last_employee_questions": last_employee_questions,  # 최근 직원 질문 목록
                    "stuck_counter": session_data.get("stuck_counter", 0),  # 반복 카운터
                    "should_close": session_data.get("should_close", False)  # 종료 신호
                }
            )

            # OpenAI API 호출
            if not self.openai_client:
                raise RuntimeError("OpenAI 클라이언트가 초기화되지 않았습니다.")
            
            llm_response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                temperature=0.2,
                max_tokens=500
            )

            # 일반 모드: LLM 사용
            content = llm_response.choices[0].message.content
            parsed = parse_llm_response(content)

            print(f"고객 응답 (script): '{parsed.get('script', '')}'")

            # 고객 응답 텍스트 추출
            customer_response_text = parsed.get('script', '')
            if not customer_response_text:
                customer_response_text = "네, 알겠습니다."

            print(f"고객 응답: '{customer_response_text}'")
            
            # 고객 응답을 히스토리에 추가
            conversation_history.append({
                "role": "customer",
                "text": customer_response_text,
                "timestamp": datetime.now().isoformat()
            })
            
            # TTS: 고객 응답을 음성으로 변환
            print(f"TTS 처리 시작")
            customer_audio = self._text_to_speech(customer_response_text, response_persona)
            print(f"TTS 완료: 오디오 길이 {len(customer_audio) if customer_audio else 0}")
            
            # 응답 평가
            evaluation = self._evaluate_user_response(transcribed_text, actual_persona or persona, actual_situation or situation)
            
            # 종료 신호 (세션 데이터 플래그 및 자동 판단)
            auto_should_close = self._should_close_session(
                session_data=session_data,
                conversation_history=conversation_history,
                final_situation=final_situation,
                achieved_goal_indices=achieved_goal_indices,
                customer_response_text=customer_response_text,
                employee_latest_text=transcribed_text,
            )
            if auto_should_close:
                session_data["should_close"] = True

            should_close_flag = session_data.get("should_close", False)
            end_signal = bool(should_close_flag)
            
            # 종료 신호가 감지되면 사용자에게 안내할 메시지 생성
            end_message = None
            if end_signal:
                if auto_should_close:
                    end_message = "대화가 자연스럽게 마무리되었습니다. 피드백을 확인하시겠습니까?"
                else:
                    end_message = "시뮬레이션을 종료할 수 있습니다. 상단의 '피드백 보기' 버튼을 클릭하세요."
            
            result = {
                "transcribed_text": transcribed_text,
                "customer_response": customer_response_text,
                "customer_audio": customer_audio,
                "feedback": evaluation,
                "followups": [],
                "safety_notes": "",
                "conversation_phase": "ongoing",
                "session_score": self._calculate_session_score(session_data),
                "conversation_history": conversation_history,  # 업데이트된 히스토리 포함
                "end_signal": end_signal,  # LLM이 판단한 종료 신호 (문맥 기반)
                "end_message": end_message,  # 종료 안내 메시지
                "offtopic_count": offtopic_count,  # 이탈 카운터 포함
                "is_test_mode": is_test_mode or has_test_scenario,  # 🧪 테스트 모드 플래그
                "current_turn_index": session_data.get("current_turn_index", 0),  # 🧪 테스트 모드: 현재 턴 인덱스
                "next_turn_expected_text": next_turn_expected_text,  # 🧪 테스트 모드: 다음 턴 expected_text
                "next_turn_role": next_turn_role  # 🧪 테스트 모드: 다음 턴 역할
            }
            
            print("음성 상호작용 처리 완료")
            return result
            
        except Exception as e:
            print(f"음성 상호작용 처리 오류: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    def _normalize_percentage_text(self, text: str) -> str:
        """STT 결과에서 "퍼센트"를 "%"로 변환합니다."""
        import re
        # "퍼센트" 또는 "프로"를 "%"로 변환
        # 숫자 뒤에 오는 경우: "4퍼센트" → "4%", "6에서 8퍼센트" → "6에서 8%"
        text = re.sub(r'(\d+(?:\.\d+)?)\s*퍼센트', r'\1%', text)
        text = re.sub(r'(\d+(?:\.\d+)?)\s*프로', r'\1%', text)
        # 단독으로 사용되는 경우: "퍼센트" → "%" (드물지만)
        text = re.sub(r'\b퍼센트\b', '%', text)
        text = re.sub(r'\b프로\b', '%', text)
        return text
    
    def _speech_to_text(self, audio_data: bytes) -> str:
        """하이브리드 STT: whisper 기본 + gpt-4o-transcribe 보정용"""
        if not self.openai_client:
            return "OpenAI API 키가 설정되지 않았습니다."
            
        if not audio_data:
            return "오디오 데이터가 없습니다."

        try:
            # 임시 파일로 저장
            audio_file = tempfile.NamedTemporaryFile(delete=False, suffix=".webm")
            audio_file.write(audio_data)
            audio_file.close()
            
            print(f"STT 처리: 오디오 파일 크기 {len(audio_data)} bytes")
            
            # 1단계: whisper-1로 기본 인식
            print("🎤 1단계: whisper-1 기본 인식")
            with open(audio_file.name, "rb") as f:
                transcript = self.openai_client.audio.transcriptions.create(
                    model="whisper-1",
                    file=f,
                    language="ko"
                )
            
            initial_text = transcript.text
            print(f"초기 인식 결과: '{initial_text}'")
            
            # 1.5단계: "퍼센트" → "%" 변환 (STT 후처리)
            initial_text = self._normalize_percentage_text(initial_text)
            print(f"퍼센트 변환 후: '{initial_text}'")
            
            # 2단계: 의미 보정으로 품질 평가
            normalize_result = self.normalize_user_text(initial_text, confidence=0.8)
            corrections = normalize_result["corrections"]
            needs_clarification = normalize_result["needs_clarification"]
            
            print(f"교정 횟수: {len(corrections)}")
            print(f"재확인 필요: {needs_clarification}")
            
            # 3단계: 품질이 낮으면 gpt-4o-transcribe로 재인식
            should_reprocess = (
                len(corrections) >= 2 or  # 교정이 2개 이상
                needs_clarification or   # 재확인 필요
                len(initial_text) < 3     # 너무 짧은 텍스트
            )
            
            if should_reprocess:
                print("🔄 2단계: gpt-4o-transcribe 재인식 (품질 개선)")
                with open(audio_file.name, "rb") as f:
                    enhanced_transcript = self.openai_client.audio.transcriptions.create(
                        model="gpt-4o-transcribe",
                        file=f,
                        language="ko"
                    )
                
                enhanced_text = enhanced_transcript.text
                print(f"개선된 인식 결과: '{enhanced_text}'")
                
                # 1.5단계: "퍼센트" → "%" 변환 (STT 후처리)
                enhanced_text = self._normalize_percentage_text(enhanced_text)
                print(f"퍼센트 변환 후: '{enhanced_text}'")
                
                # 개선된 결과로 다시 정규화
                final_normalize = self.normalize_user_text(enhanced_text, confidence=0.9)
                final_text = final_normalize["normalized"]
                
                print(f"최종 정규화: '{final_text}'")
                os.unlink(audio_file.name)
                return final_text
            else:
                print("✅ whisper-1 결과 사용 (품질 양호)")
                os.unlink(audio_file.name)
                return normalize_result["normalized"]
            
        except Exception as e:
            print(f"STT 오류: {e}")
            import traceback
            traceback.print_exc()
            return "음성 인식에 실패했습니다."
    
    def _text_to_speech(self, text: str, persona: Dict) -> str:
        """텍스트를 음성으로 변환 (TTS) - gpt-4o-mini-tts 사용"""
        if not self.openai_client:
            print("TTS 오류: OpenAI 클라이언트가 초기화되지 않았습니다.")
            return ""
            
        if not text:
            print("TTS 오류: 변환할 텍스트가 없습니다.")
            return ""
            
        try:
            print(f"TTS 시작: '{text[:50]}...'")

            # 페르소나 기반 파라미터 산출
            params = get_voice_params(persona)
            print(f"TTS 파라미터: {params}")

            # OpenAI TTS API 호출 (gpt-4o-mini-tts 모델 사용, 기본 파라미터만)
            response = self.openai_client.audio.speech.create(
                model="gpt-4o-mini-tts",
                voice=params["voice"],
                speed=params["rate"],  # speed 파라미터 사용
                input=text  # SSML 대신 일반 텍스트 사용
            )

            audio_data = response.content
            audio_base64 = base64.b64encode(audio_data).decode('utf-8')
            print(f"TTS 성공: {len(audio_data)} bytes")

            return f"data:audio/mpeg;base64,{audio_base64}"
            
        except Exception as e:
            print(f"TTS 오류: {e}")
            import traceback
            traceback.print_exc()
            return ""
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # ❌ Dead Code 제거됨 (총 300+ 줄):
    # - _get_voice_characteristics() → persona_voice.get_voice_params() 사용
    # - _generate_initial_customer_message() → 호출 없음
    # - _generate_customer_response_with_rag() → promptOrchestrator 사용
    # - _get_rag_context() → 위 메서드에서만 사용
    # - _extract_persona_traits() → 위 메서드에서만 사용
    # - _determine_conversation_phase() → 위 메서드에서만 사용
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    def _evaluate_user_response(self, user_message: str, persona: Dict, situation: Dict) -> str:
        """사용자 응답 평가"""
        scenarios = situation.get('scenarios', [])
        
        if not scenarios:
            return "평가 기준이 없습니다."
        
        # 시나리오를 문자열로 변환
        scenarios_text = "\n".join([
            f"- {scenario}"
            for scenario in scenarios
        ])
        
        prompt = f"""
        은행 직원의 응답: "{user_message}"
        
        고객 정보:
        - 고객 타입: {persona.get('customer_style') or persona.get('type', '')}
        - 금융 이해도: {persona.get('financial_literacy', '중간')}
        - 톤: {persona.get('speech', {}).get('tone', 'neutral') if isinstance(persona.get('speech'), dict) else persona.get('tone', 'neutral')}
        
        시나리오:
        {scenarios_text}
        
        이 응답이 고객에게 적절했는지 평가하고, 개선점이 있다면 피드백을 제공해주세요.
        """
        
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            print(f"응답 평가 오류: {e}")
            return "응답 평가를 완료할 수 없습니다."
    
    def _calculate_session_score(self, session_data: Dict) -> float:
        """세션 점수 계산 (임시 구현)"""
        # 실제로는 대화 기록을 기반으로 점수를 계산해야 함
        return 75.0
    
    def _should_close_session(
        self,
        session_data: Dict,
        conversation_history: List[Dict],
        final_situation: Dict,
        achieved_goal_indices: List[int],
        customer_response_text: str,
        employee_latest_text: str,
    ) -> bool:
        """
        대화 종료 여부 자동 판단.
        
        종료 신호는 다음 요소들의 조합으로 판단한다.
          1. 직원의 마무리 질문 + 고객의 종료성 응답
          2. 상담 목표 달성 + 고객의 짧은 확인/감사 응답
          3. 충분한 턴 수 경과 + 고객의 종료성 응답
        """
        if not conversation_history:
            return False

        # 이미 종료 신호가 충분히 누적되었다면 그대로 유지
        closing_counter = session_data.get("closing_signal_counter", 0)
        if session_data.get("should_close"):
            return True

        customer_lower = (customer_response_text or "").strip().lower()
        employee_lower = (employee_latest_text or "").strip().lower()

        # 조건 1: 직원 마무리 질문 + 고객 종료 응답
        employee_closing_prompt = any(phrase in employee_lower for phrase in EMPLOYEE_CLOSING_PROMPTS)
        customer_strong_closing = any(phrase in customer_lower for phrase in CUSTOMER_STRONG_CLOSINGS)
        customer_soft_closing = any(phrase in customer_lower for phrase in CUSTOMER_SOFT_CLOSINGS)

        closing_pair = employee_closing_prompt and (customer_strong_closing or customer_soft_closing)

        # 조건 2: 목표 달성 여부
        goals = final_situation.get("goals") or []
        goals_met = bool(goals) and len(achieved_goal_indices) >= len(goals)

        # 조건 3: 충분한 턴 수 + 짧은 확인 응답
        employee_turns = sum(1 for msg in conversation_history if msg.get("role") == "employee")
        customer_turns = sum(1 for msg in conversation_history if msg.get("role") == "customer")
        conversation_long_enough = employee_turns >= 6 and customer_turns >= 6

        short_ack = (
            customer_response_text
            and len(customer_response_text) <= 25
            and "?" not in customer_response_text
            and (customer_soft_closing or "네" in customer_lower or "예" in customer_lower)
        )

        strong_signal = (
            (closing_pair and customer_strong_closing)
            or (customer_strong_closing and (goals_met or conversation_long_enough))
        )

        medium_signal = (
            closing_pair
            or (goals_met and short_ack)
            or (conversation_long_enough and (customer_soft_closing or customer_strong_closing))
        )

        if strong_signal:
            closing_counter = max(closing_counter, 1) + 1  # 강한 신호는 즉시 2 이상으로 상승
        elif medium_signal:
            closing_counter = min(closing_counter + 1, 3)
        else:
            closing_counter = max(closing_counter - 1, 0)

        session_data["closing_signal_counter"] = closing_counter

        # 강한 종료 신호이거나, 종료 신호가 누적되면 종료
        return strong_signal or closing_counter >= 2

    def generate_comprehensive_feedback(self, conversation_history: List[Dict], 
                                      persona: Dict, situation: Dict,
                                      saved_achieved_goals: Optional[Dict] = None) -> Dict:
        """
        5가지 역량 기반 종합 평가 및 피드백 생성
        - 지식 (Knowledge): 상품/서비스에 대한 정확성과 전문성
        - 기술 (Skill): 상담 프로세스 준수 + 목표 달성도
        - 친절도 (Kindness): 예의와 배려
        - 전달력 (Clarity + Confidence): 명확성과 자신감을 통합한 정보 전달 역량
        - 페르소나 정합도 (Persona Fit): 고객 페르소나 타입에 맞는 대응 전략 사용 여부
        """
        try:
            # KB 권장용어 사전 로드
            kb_terms_text = ""
            try:
                # __file__ 기반 절대 경로 사용 (score_metrics.py와 동일한 방식)
                kb_terms_path = Path(__file__).parent.parent.parent / "data" / "kb_recommended_terms.json"
                if kb_terms_path.exists():
                    with open(kb_terms_path, 'r', encoding='utf-8') as f:
                        kb_terms_data = json.load(f)
                        recommended_terms = kb_terms_data.get('recommended_terms', {})
                        
                        # 용어 목록을 프롬프트에 포함하기 쉬운 형식으로 변환
                        terms_list = []
                        for term, info in recommended_terms.items():
                            preferred = info.get('preferred', '')
                            explanation = info.get('explanation', '')
                            category = info.get('category', '')
                            terms_list.append(f'  - "{term}" → "{preferred}" (카테고리: {category})')
                            if explanation:
                                terms_list[-1] += f' - {explanation}'
                        
                        if terms_list:
                            kb_terms_text = "\n".join(terms_list)
                            print(f"✅ KB 권장용어 사전 로드 완료: {len(terms_list)}개 용어")
                else:
                    print(f"⚠️ KB 권장용어 사전 파일을 찾을 수 없습니다: {kb_terms_path}")
            except Exception as e:
                print(f"⚠️ KB 권장용어 사전 로드 실패: {e}")
            
            # 직원 발화만 추출 (평가 대상)
            employee_utterances = [
                msg['text'] for msg in conversation_history 
                if msg.get('role') == 'employee'
            ]
            
            if not employee_utterances:
                return self._get_default_feedback()
            
            # 전체 대화 컨텍스트
            conversation_context = "\n".join([
                f"{'고객' if msg.get('role') == 'customer' else '직원'}: {msg.get('text', '')}"
                for msg in conversation_history
            ])
            
            # 🎯 목표 달성 분석 (턴별 추적 포함)
            goals = situation.get('goals', [])
            achieved_goal_indices = []
            turn_tracking = {}
            goal_achievement_rate = 1.0  # 기본값: 목표가 없으면 100%
            
            # 🚨 중요: DB에 저장된 목표 달성 정보 우선 사용 (프론트엔드가 실시간으로 체크한 정보)
            if saved_achieved_goals:
                print(f"✅ DB에 저장된 목표 달성 정보 사용 (프론트엔드에서 체크한 정보)")
                achieved_goal_indices = saved_achieved_goals.get('achieved_indices', [])
                achievement_times = saved_achieved_goals.get('achievement_times', {})
                
                # achievement_times를 turn_tracking 형식으로 변환
                # 대화 히스토리에서 실제 발화 찾기
                for goal_idx_str, time_info in achievement_times.items():
                    goal_idx = int(goal_idx_str)
                    turn_num = time_info.get("turn", 0)
                    
                    # 대화 히스토리에서 해당 턴의 직원 발화 찾기
                    actual_evidence = None
                    if conversation_history and turn_num > 0:
                        # 직원 발화에 턴 번호 붙이기
                        employee_turn_count = 0
                        for msg in conversation_history:
                            role = msg.get("role", "")
                            text = msg.get("text", "")
                            if role in ["employee", "user"]:
                                employee_turn_count += 1
                                if employee_turn_count == turn_num:
                                    actual_evidence = text.strip()
                                    break
                    
                    # 실제 발화를 찾았으면 사용, 없으면 기본 메시지
                    if actual_evidence:
                        turn_tracking[goal_idx] = {
                            "turn": turn_num,
                            "evidence": actual_evidence[:300]  # 최대 300자
                        }
                        print(f"  ✓ 목표 {goal_idx} → 턴 {turn_num}: 실제 발화 발견 ({len(actual_evidence)}자)")
                    else:
                        # 실제 발화를 찾지 못했으면, 저장된 evidence가 있는지 확인
                        saved_evidence = time_info.get("evidence")
                        if saved_evidence and saved_evidence != f"{goal_idx}번 목표를 {turn_num}번째 턴에서 달성":
                            # 저장된 실제 발화가 있으면 사용
                            turn_tracking[goal_idx] = {
                                "turn": turn_num,
                                "evidence": saved_evidence[:300]
                            }
                            print(f"  ✓ 목표 {goal_idx} → 턴 {turn_num}: 저장된 발화 사용")
                        else:
                            # 발화를 찾지 못한 경우, GPT로 발화 찾기 시도
                            try:
                                if goals and goal_idx < len(goals):
                                    goal_text = goals[goal_idx]
                                    # 직원 발화만 추출
                                    employee_utterances = []
                                    employee_turn = 0
                                    for msg in conversation_history:
                                        if msg.get("role") in ["employee", "user"]:
                                            employee_turn += 1
                                            text = msg.get("text", "").strip()
                                            if text:
                                                employee_utterances.append(f"턴 {employee_turn}: {text}")
                                    
                                    if employee_utterances:
                                        employee_conversation = "\n".join(employee_utterances)
                                        tracking_prompt = f"""다음은 은행 직원의 발화입니다.
"{goal_text}" 목표가 달성된 발화를 찾아주세요.

직원 발화:
{employee_conversation}

목표: {goal_text}

**중요 평가 기준**: 
1. **직원이 실제로 구체적인 정보를 제공한 발화를 찾으세요**
   - 단순히 주제를 언급하는 것이 아니라, 목표를 실질적으로 달성한 발화여야 합니다
   
2. **목표 텍스트의 구체적 키워드 확인**:
   - 목표에 인용부호("")로 강조된 구체적 항목이 있으면, 그 항목들이 실제로 언급되었는지 확인
   - 예: 목표에 "\"기본구조·금리\""가 있으면 → 기본구조와 금리 둘 다 다룬 발화인지 확인
   - 예: 목표에 "\"금리, 한도, 우대조건, 수수료 등\""이 있으면 → 최소 2개 이상 언급된 발화인지 확인
   - 목표 텍스트에 나열된 구체적 항목(예: "소득, 거래 패턴 등")이 최소 1개 이상 언급되었는지 확인
   
3. **목표가 요구하는 행동 확인**:
   - "파악한다" → 고객의 의도/상황을 이해하고 확인하는 대화
   - "설명하고/이해시키는" → 구체적인 내용(수치, 절차, 조건 등) 포함
   - "안내하는" → 실제 방법이나 단계 제시
   - "고려한다/설명해" → 명시적인 경고나 정보 전달
   - "정리해 주고" → 다음 단계나 필요 사항 명확히 정리
   
4. **턴 {turn_num} 근처의 발화를 우선적으로 확인하세요**

출력 형식:
발화내용 (직원이 한 말만 출력, 턴 번호 제외)

예: 현재 달러 환율은 1,300원이며, 환전 수수료는 2%입니다.

찾을 수 없으면 "없음"이라고만 출력하세요."""
                                        
                                        tracking_response = self.openai_client.chat.completions.create(
                                            model="gpt-4o-mini",
                                            messages=[{"role": "user", "content": tracking_prompt}],
                                            max_tokens=200,
                                            temperature=0.2
                                        )
                                        
                                        tracking_result = tracking_response.choices[0].message.content.strip()
                                        
                                        if tracking_result and tracking_result.lower() not in ["없음", "none"]:
                                            # "턴 X:" 같은 접두사 제거
                                            evidence = tracking_result
                                            if ":" in evidence and evidence.split(":")[0].strip().isdigit():
                                                evidence = ":".join(evidence.split(":")[1:]).strip()
                                            
                                            turn_tracking[goal_idx] = {
                                                "turn": turn_num,
                                                "evidence": evidence[:300]
                                            }
                                            print(f"  ✓ 목표 {goal_idx} → 턴 {turn_num}: GPT로 발화 찾기 성공")
                                        else:
                                            turn_tracking[goal_idx] = {
                                                "turn": turn_num,
                                                "evidence": None  # 발화를 찾지 못함
                                            }
                                            print(f"  ⚠️ 목표 {goal_idx} → 턴 {turn_num}: 발화 찾기 실패")
                            except Exception as e:
                                print(f"  ⚠️ 목표 {goal_idx} 발화 찾기 오류: {e}")
                                turn_tracking[goal_idx] = {
                                    "turn": turn_num,
                                    "evidence": None
                                }
                
                if goals:
                    goal_achievement_rate = len(achieved_goal_indices) / len(goals)
                    print(f"📊 목표 달성률: {len(achieved_goal_indices)}/{len(goals)} ({goal_achievement_rate*100:.1f}%)")
                    print(f"📅 달성 시점 정보: {len(turn_tracking)}개 목표 (실제 발화 포함: {sum(1 for v in turn_tracking.values() if v.get('evidence'))}개)")
            elif goals:
                # DB에 정보가 없으면 새로 분석 (fallback)
                print(f"⚠️ DB에 저장된 목표 달성 정보 없음 - 새로 분석합니다 (총 {len(goals)}개 목표)")
                # 🔍 2단계: 턴별 추적 정보 포함
                detailed_result = self.analyze_goal_achievement(conversation_history, goals, return_detailed=True)
                
                if isinstance(detailed_result, dict):
                    achieved_goal_indices = detailed_result.get('achieved_indices', [])
                    turn_tracking = detailed_result.get('turn_tracking', {})
                else:
                    # 하위 호환성 (기본 모드)
                    achieved_goal_indices = detailed_result
                    turn_tracking = {}
                
                goal_achievement_rate = len(achieved_goal_indices) / len(goals)
                print(f"✅ 목표 달성률: {len(achieved_goal_indices)}/{len(goals)} ({goal_achievement_rate*100:.1f}%)")
                if turn_tracking:
                    print(f"📍 턴별 추적 정보: {len(turn_tracking)}개 목표에 대한 증거 확보")
            
            # 달성/미달성 목표 정보
            achieved_goals_text = ""
            if goals:
                achieved_goals = [goals[i] for i in achieved_goal_indices]
                unachieved_goals = [goals[i] for i in range(len(goals)) if i not in achieved_goal_indices]
                achieved_goals_text = f"""
달성된 목표: {', '.join(achieved_goals) if achieved_goals else '없음'}
미달성 목표: {', '.join(unachieved_goals) if unachieved_goals else '없음'}
"""
            
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            # 🎯 0단계: 대화 유형 자동 판별 (고도화 분석 기반)
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            # 상황 정보 추출
            situation_id = situation.get('id', '')
            is_from_product_manual = situation.get('is_from_product_manual', False)
            product_code = situation.get('product', None)
            intent = situation.get('intent', '')
            category = situation.get('category', '')
            has_product_data = situation.get('has_product_data', True)  # 기본값: True
            
            # 대화 유형 판별 (A/B/C/D)
            conversation_type = None
            conversation_type_description = ""
            
            if is_from_product_manual and product_code:
                # A. 상품 설명서 기반 상담
                conversation_type = "A"
                conversation_type_description = "상품 설명서 기반 상담 (특정 상품에 대한 구체적인 정보 안내)"
                print(f"📋 대화 유형: A (상품 설명서 기반) - 상품: {product_code}")
            elif not is_from_product_manual and not product_code:
                # 일반 상담 (intent로 세부 구분)
                if intent in ['환전문의', '송금문의', '외환문의']:
                    # D. 외환/송금 상담
                    conversation_type = "D"
                    conversation_type_description = "외환/송금 상담 (상품 데이터 없음, 절차 및 지식 중심)"
                    has_product_data = False
                    print(f"📋 대화 유형: D (외환/송금) - Intent: {intent}")
                elif intent in ['기타문의', '세금수수료', '이용방법', '계좌개설', '신분증확인']:
                    # C. 일반 상담 - 절차/규제 문의
                    conversation_type = "C"
                    conversation_type_description = "일반 상담 - 절차/규제 문의 (업무 절차, 금융 규정 중심)"
                    print(f"📋 대화 유형: C (절차/규제) - Intent: {intent}")
                else:
                    # B. 일반 상담 - 상품 관련
                    conversation_type = "B"
                    conversation_type_description = "일반 상담 - 상품 관련 (상품 추천, 비교, 설명 등)"
                    print(f"📋 대화 유형: B (일반 상품 상담) - Intent: {intent}")
            else:
                # 기본값: B (일반 상담)
                conversation_type = "B"
                conversation_type_description = "일반 상담"
                print(f"📋 대화 유형: B (기본값)")
            
            print(f"  ✓ 카테고리: {category}, Intent: {intent}")
            print(f"  ✓ 제품 데이터 존재: {has_product_data}")
            
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            # 🔍 1단계: 제품 지식 정확도 자동 검증 (Product Knowledge Verification)
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            product_accuracy_info = ""
            knowledge_verification_result = None
            
            if self.product_knowledge_service and has_product_data:
                try:
                    print("🔍 제품 지식 정확도 자동 검증 시작...")
                    # 🧪 테스트 모드에서는 LLM 기반 상품 코드 추출 강제 활성화
                    use_llm_extraction = True  # 테스트 모드에서는 항상 LLM 추출 사용
                    knowledge_verification_result = self.product_knowledge_service.batch_verify_conversation(
                        conversation_history,
                        use_llm=True,  # LLM 검증 포함
                        use_llm_extraction=use_llm_extraction  # 🆕 LLM 기반 상품 코드 추출
                    )
                    
                    accuracy_rate = knowledge_verification_result['accuracy_rate']
                    total_claims = knowledge_verification_result['total_claims']
                    accurate_claims = knowledge_verification_result['accurate_claims']
                    inaccurate_claims = knowledge_verification_result['inaccurate_claims']
                    
                    print(f"  ✓ 제품 정보 검증 완료: {accurate_claims}/{total_claims} 정확 ({accuracy_rate:.1%})")
                    
                    # 오류 상세 정보 및 LLM reasoning 수집
                    errors_detail = []
                    accurate_details = []  # 정확한 정보 목록 추가
                    llm_reasonings = []  # LLM reasoning 수집 (피드백 생성에 활용)
                    
                    for v in knowledge_verification_result.get('verifications', []):
                        # claim과 full_utterance를 함께 표시하여 문맥 제공
                        claim_display = v.claim
                        if hasattr(v, 'full_utterance') and v.full_utterance:
                            # full_utterance에서 claim이 포함된 부분을 강조
                            if v.claim in v.full_utterance:
                                claim_display = f"'{v.claim}' (대화: ...{v.full_utterance[max(0, v.full_utterance.find(v.claim)-20):min(len(v.full_utterance), v.full_utterance.find(v.claim)+len(v.claim)+20)]}...)"
                        
                        if not v.is_accurate:
                            errors_detail.append(f"• {claim_display} → 실제: {v.ground_truth[:80]}...")
                        else:
                            # 정확한 정보도 수집 (피드백에서 잘한 점으로 언급)
                            accurate_details.append(f"• {claim_display} (정확함)")
                        
                        # LLM reasoning이 있으면 수집 (피드백 생성에 활용)
                        if hasattr(v, 'llm_reasoning') and v.llm_reasoning:
                            llm_reasonings.append(f"• {v.claim}: {v.llm_reasoning}")
                    
                    # LLM 프롬프트에 포함할 정확도 정보
                    if total_claims > 0:
                        reasoning_section = ""
                        if llm_reasonings:
                            reasoning_section = f"""
💡 **검증 상세 분석 (LLM reasoning):**
{chr(10).join(llm_reasonings[:5])}  # 상위 5개만 표시
"""
                        
                        accurate_section = ""
                        if accurate_details:
                            accurate_section = f"""
✅ **정확한 정보 목록 (반드시 잘한 점에 언급):**
{chr(10).join(accurate_details[:5])}  # 상위 5개만 표시

⚠️ **위 정확한 정보 목록의 claim은 모두 정확한 정보입니다.**
⚠️ **위 목록에 있는 claim은 개선점에 절대 포함하지 마세요.**
⚠️ **위 목록에 있는 claim은 잘한 점에만 구체적으로 언급하세요.**
"""
                        
                        errors_section = ""
                        if errors_detail:
                            errors_section = f"""
⚠️ **부정확한 정보 목록 (개선점에만 언급):**
{chr(10).join(errors_detail[:5])}  # 상위 5개만 표시

⚠️ **위 부정확한 정보 목록의 claim만 개선점에 언급하세요.**
⚠️ **위 목록에 없는 claim은 개선점에 포함하지 마세요.**
⚠️ **정확한 정보 목록에 있는 claim과 부정확한 정보 목록에 있는 claim이 겹치면 안 됩니다.**
"""
                        else:
                            errors_section = """
⚠️ **부정확한 정보: 없음**
→ 개선점 섹션은 생략하거나 "제공한 모든 상품 정보가 정확합니다"와 같이 간단히 언급하세요.
"""
                        
                        product_accuracy_info = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔍 **제품 지식 자동 검증 결과** (객관적 데이터 - 반드시 정확히 반영하세요)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- 총 제품 정보 언급: {total_claims}개
- 정확한 정보: {accurate_claims}개
- 부정확한 정보: {inaccurate_claims}개
- 정확도: {accuracy_rate:.1%}
- 검증 방법: {knowledge_verification_result.get('verification_methods', {})}

{accurate_section}
{errors_section}
{reasoning_section}
💡 **지식 점수 평가 및 피드백 작성 가이드:**
- 정확도 {accuracy_rate:.1%} → 기본 점수 {int(accuracy_rate * 100)}점 (오류는 이미 정확도에 반영됨)
- ⚠️ 오류 개수는 점수 계산에 사용하지 말고, 피드백 작성 시에만 참고하세요
- ⚠️ 불확실한 표현("같아요", "모르겠" 등)은 전달력(자신감) 평가에서 다루므로 지식 점수에는 반영하지 않습니다
- ⚠️ **표현의 명확성(단위 명시 등)은 전달력에서 평가하므로, 지식 피드백에서는 상품 정보의 정확성만 언급하세요**

🚨 **중요 규칙 (반드시 준수):**
1. **정확한 정보 목록에 있는 claim은 반드시 잘한 점에만 언급하고, 개선점에 절대 포함하지 마세요.**
2. **부정확한 정보 목록에 있는 claim만 개선점에 언급하세요.**
3. **같은 claim이 잘한 점과 개선점에 동시에 나타나면 안 됩니다. (모순 금지)**
4. **실제 대화 내용을 정확히 참조하세요. 대화에서 "100만원"이라고 정확히 말했다면, "최소 100"이라는 오류로 인식하지 마세요.**
5. **제품 지식 자동 검증 결과가 정확한 정보로 판단했다면, 그것을 신뢰하고 잘한 점에 언급하세요.**
"""
                    else:
                        product_accuracy_info = """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔍 **제품 지식 자동 검증 결과**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- 구체적인 제품 정보 언급 없음 (금리, 한도 등 수치 정보 부재)
- 지식 점수는 일반적인 설명의 질로만 평가
"""
                
                except Exception as e:
                    print(f"⚠️ 제품 지식 검증 실패: {e}")
                    product_accuracy_info = ""
            
            elif not has_product_data:
                # 외환/송금 상담 등 상품 데이터가 없는 경우
                product_accuracy_info = """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔍 **지식 평가 방식** (상품 데이터 없음)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- 제품별 정확도 검증 불가 (상품 데이터 파일 없음)
- 지식 점수는 다음 기준으로 평가:
  ✓ 절차 설명의 정확성 (송금 절차, 수수료 안내 등)
  ✓ 일반적인 금융 지식의 정확성
  ✓ 금융 규정 및 정책 이해도
  ✓ 고객 질문에 대한 적절한 답변 제공
- 구체적인 수치 정보(환율, 수수료 등)의 정확성은 LLM이 일반 지식으로 평가
"""
            
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            # 대화 유형별 지식 평가 기준 생성
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            knowledge_criteria = ""
            if conversation_type == "A":
                # A. 상품 설명서 기반 상담
                category_specific = ""
                if category == "수신":
                    category_specific = "  * 수신: 예금자보호 한도, 중도해지 손실 등"
                elif category == "여신":
                    category_specific = "  * 여신: 상환방식, 연체 이자, 중도상환 수수료 등"
                elif category == "카드":
                    category_specific = "  * 카드: 리볼빙, 최소결제금, 연회비 등"
                
                knowledge_criteria = f"""**A. 상품 설명서 기반 상담 (100점)**
- 상품 정보 정확성 (70점): 금리, 한도, 조건 등 핵심 정보의 정확성
  * 제품 지식 자동 검증 결과 반영 (정확도 기반)
  * 정확한 정보 제공: 각 정보당 +점수
  * 부정확한 정보: 각 정보당 -점수
- 절차/규제 지식 (15점): 상품 가입 절차, 필요 서류 등
- 일반 금융 지식 (10점): 금융 상식, 상품 비교 기준 등
- 카테고리별 특화 지식 (5점):
{category_specific if category_specific else "  * 카테고리별 특화 지식"}"""
                
            elif conversation_type == "B":
                # B. 일반 상담 - 상품 관련
                knowledge_criteria = """**B. 일반 상담 - 상품 관련 (100점)**
- 일반 상품 지식 정확성 (40점): 상품 구조, 특징, 비교 기준 등
  * 상품 비교 기준의 정확성
  * 관련 상품 지식의 정확성
- 절차/규제 지식 (30점): 중도해지, 중도상환, 연체 대응 절차 등
  * 절차 설명의 정확성: 15점
  * 규제·리스크·불이익 설명의 정확성: 15점
- 일반 금융 지식 (20점): 금융 상식, 금융 용어 등
- 카테고리별 특화 지식 (10점): 적금 설계, 대출 관리, 카드 사용 등"""
                
            elif conversation_type == "C":
                # C. 일반 상담 - 절차/규제 문의
                knowledge_criteria = """**C. 일반 상담 - 절차/규제 문의 (100점)**
- 은행 업무 절차 지식 (50점): 계좌 개설, 신분증 확인, 서류 안내 등
  * 절차 설명의 정확성: 30점
  * 필요 서류 안내의 정확성: 10점
  * 다음 단계 안내의 정확성: 10점
- 금융 규정 및 정책 이해도 (30점): 예금자보호 한도, 신분증 확인 의무 등
  * 규정 이해의 정확성: 15점
  * 정책 이해의 정확성: 15점
- 일반적인 은행 창구 업무 지식 (20점): 수수료 안내, 서류 처리 등"""
                
            elif conversation_type == "D":
                # D. 외환/송금 상담
                knowledge_criteria = """**D. 외환/송금 상담 (100점)**
- 절차 설명 (40점): 송금 절차, 환전 절차 등
  * 절차 단계의 정확성
  * 필요 서류 안내
- 환율/수수료 정보 (40점): 환율 기준, 수수료 안내 등
  * 환율 정보의 정확성
  * 수수료 정보의 정확성
- 외환 규제 (20점): 제재 규제, 신고 의무 등
  * 규제 이해도
  * 신고 기준 안내"""
            
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            # 2단계: LLM을 사용하여 6가지 역량 종합 평가 (최종적으로 5가지로 통합)
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            # f-string에서 \n 사용을 위해 변수로 분리
            newline = "\n"
            evaluation_prompt = f"""
당신은 은행 신입행원 응대 시뮬레이션 평가 전문가입니다.
다음 대화를 분석하여 **단계별로 구조화된 평가**를 수행하고 피드백을 제공하세요.

⚠️ **중요: 평가 프로세스**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. 각 역량의 세부 항목을 하나씩 순서대로 평가하세요
2. 각 항목별 점수와 근거를 명확히 기록하세요
3. 점수를 합산하여 최종 점수 계산하세요
4. 체크리스트를 확인하여 누락 항목이 없는지 확인하세요

{product_accuracy_info}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📌 **평가 지표 및 상세 기준**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 **현재 대화 유형: {conversation_type} - {conversation_type_description}**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**1️⃣ 지식 (Knowledge, 0-100점)** ⚠️ 위 검증 결과 반영 필수

⚠️ **중요: 대화 유형에 따라 다른 평가 기준 적용**

{knowledge_criteria}

**공통 평가 원칙:**
  ✓ 정보의 정확성 (수치, 조건, 절차 등)
  ✓ 일반적인 금융 지식 및 규정 이해도
  ✗ 잘못된 정보나 오류 발견 시 감점
  ⚠️ **표현의 명확성은 전달력 평가에서 다루므로 지식에서는 평가하지 않음**
  ⚠️ 불확실한 표현은 전달력(자신감) 평가에서 다루므로 지식 점수에는 반영하지 않음

**피드백 작성 시:**
  ✓ **상품 정보의 정확성**에만 집중하여 피드백 작성 (A, B 유형)
  ✓ **절차 및 규제 지식의 정확성**에 집중하여 피드백 작성 (C, D 유형)
  ✓ **위 제품 지식 자동 검증 결과 반영** (있는 경우)
  ✓ 부정확한 정보는 정확한 정보와 함께 제시
  ✗ 표현의 명확성은 전달력에서 다루므로 지식 피드백에서 언급하지 않음

**2️⃣ 기술 (Skill, 0-100점)**
- 목적: 응대 절차가 체계적이며 목표를 달성했는가

**점수 구성 (100점):**
- **대화 흐름 (20점)**: 인사 → 요구파악 → 정보제공 → 마무리 순서
  * 인사 및 초기 관계 형성 (5점)
  * 고객 요구사항 파악 (7점)
  * 정보 제공 및 설명 (5점)
  * 적절한 마무리 (3점)
  
- **목표 달성도 (60점)**: {len(achieved_goal_indices)}/{len(goals) if goals else 0}개 달성 ({goal_achievement_rate*100:.0f}%)
  * 각 목표별 달성 여부 평가
  * 목표 텍스트에 명시된 구체적 키워드(인용부호 내 항목, 나열된 항목 등)가 실제로 다뤄졌는지 확인
  * 목표별 점수 = 60점 / 총 목표 수
  * 고객 성격 유형에 맞는 적절한 대응 여부 포함
  
- **질문 사용 (10점)**: 고객 니즈 파악을 위한 적절한 질문 사용
  * 개방형 질문 활용 여부
  * 고객 상황 파악을 위한 질문의 적절성
  * 추가 확인을 위한 질문 사용
  
- **피드백 루프 (10점)**: 요약 및 추가 확인 여부
  * 고객 말을 정리하여 확인
  * 추가 질문 유도
  * 고객의 이해도 확인

**평가 기준:**
  ✓ **고객 성격 유형에 맞는 적절한 대응**: 불만형은 공감 후 해결책 제시, 급함형은 빠르고 간결한 안내, 긍정형은 친절한 안내
  ✓ **목표별 구체적 요구사항 달성 여부**: 목표 텍스트에 명시된 구체적 키워드가 실제로 다뤄졌는지 확인
  ✓ 대화 흐름의 자연스러움
  ✓ 각 항목별 점수를 먼저 산정한 후 합산
  
**피드백 작성 시:** 
  ✓ 어떤 절차를 잘 따랐는지 구체적으로 언급
  ✓ 달성한 목표와 미달성한 목표를 명시 (목표 텍스트를 그대로 인용)
  ✓ 미달성한 목표의 경우, 목표 텍스트에 명시된 구체적 요구사항(예: "\"기본구조·금리\"", "\"금리, 한도, 우대조건, 수수료 등\"") 중 어떤 것이 누락되었는지 구체적으로 언급
  ✓ 목표 달성률이 낮은 경우, 어떤 목표를 놓쳤는지와 개선 방안 제시 (목표 텍스트의 구체적 키워드 참조)
  ✓ **각 항목별 점수와 근거를 제시** (예: "대화 흐름 15/20점, 목표 달성도 45/60점, 질문 사용 7/10점, 피드백 루프 5/10점")
  ✓ **고객 성격 유형에 맞는 대응 여부 평가** (불만형: 공감→해결책, 급함형: 빠른 처리, 긍정형: 친절한 안내)
  ✓ 예: "대화 흐름은 체계적이었지만, '고객의 문의 의도와 현재 금융 상황(소득, 거래 패턴 등)을 정확히 파악한다' 목표를 달성하지 못했습니다. 고객에게 소득이나 거래 패턴을 먼저 물어보는 것이 좋습니다."
  ✓ 예: "'기본구조·금리'와 관련된 조건을 안내하는 목표는 달성했지만, '금리, 한도, 우대조건, 수수료 등' 중 우대조건과 수수료에 대한 구체적 안내가 부족했습니다."
  ✓ 예: "급함형 고객에게는 불필요한 설명을 줄이고 핵심만 간결하게 전달하는 것이 좋습니다."

**3️⃣ 명확성 (Clarity, 0-100점)**
- 목적: 명확하고 이해하기 쉬운 언어를 사용했는가

**체크리스트 (모든 항목을 평가하세요):**
- [ ] 문장 구조 및 간결성 (30점)
- [ ] 논리성 및 구조 (25점)
- [ ] 용어 평이성 (30점)
- [ ] 숫자 표현의 명확성 (15점)

**단계별 평가:**

**1단계: 문장 구조 및 간결성 (30점)**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
평가 기준: 평균 문장 길이

| 평균 문장 길이 | 점수 | 판단 기준 |
|--------------|------|----------|
| 50자 이하 | 30점 | 모든 문장이 간결하고 이해하기 쉬움 |
| 50-80자 | 20점 | 대부분 간결하나 일부 긴 문장 있음 |
| 80-120자 | 10점 | 문장이 다소 길어 이해하기 어려울 수 있음 |
| 120자 이상 | 5점 | 문장이 너무 길어 이해하기 어려움 |

점수: ?/30점
근거: "평균 문장 길이 X자이므로 Y점 부여"

**2단계: 논리성 및 구조 (25점)**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
평가 기준: 논리적 순서, 연결어 적절 사용

| 평가 기준 | 점수 |
|----------|------|
| 논리적 순서, 연결어 적절 사용 | 25점 |
| 대부분 논리적이나 일부 어색 | 18점 |
| 논리적 순서 문제 | 10점 |
| 논리성 부족 | 3점 |

점수: ?/25점
근거: "..."

**3단계: 용어 평이성 (30점)**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
평가 기준: 전문용어 → 쉬운 말

| 평가 기준 | 점수 |
|----------|------|
| 전문용어 사용 0개 | 30점 |
| 전문용어 1-2개 사용 (쉬운 말로 설명 포함) | 20점 |
| 전문용어 3-4개 사용 (일부 설명) | 10점 |
| 전문용어 5개 이상 또는 설명 없음 | 5점 |

점수: ?/30점
근거: "전문용어 X개 사용, Y개는 쉬운 말로 설명했으므로 ?점 부여"

**4단계: 숫자 표현의 명확성 (15점)**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
평가 기준: 단위 명시 여부

| 평가 기준 | 점수 |
|----------|------|
| 모든 숫자에 단위 명시 | 15점 |
| 대부분 단위 명시 | 10점 |
| 일부 단위 누락 | 5점 |
| 단위 명시 없음 | 0점 |

점수: ?/15점
근거: "숫자 X개 중 Y개에 단위 명시했으므로 ?점 부여"

**최종 점수 계산:**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
문장 구조: ?점
논리성: ?점
용어 평이성: ?점
숫자 표현: ?점
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
총점: ?/100점

**용어 평이성 평가 기준 (KB 권장용어 사전):**
  다음은 전문용어를 쉬운 말로 변환한 KB 권장용어 사전입니다. 
  직원이 전문용어를 사용했을 때, 이 사전에 있는 권장 용어로 설명했는지 평가하세요:
  
{kb_terms_text if kb_terms_text else f'  - "거치기간" → "이자만 내는 기간"{newline}  - "언택트" → "비대면"{newline}  - "LTV" → "담보인정비율"{newline}  - "복리" → "이자에 이자가 붙는 방식"{newline}  - "DSR" → "총부채원리금상환비율"{newline}  - "실물출자" → "실제 물건으로 투자"'}
  
  ⚠️ 평가 시: 직원이 전문용어를 사용했을 때 위 사전에 있는 권장 용어로 설명했는지 확인하고,
              설명 없이 전문용어만 사용했으면 감점하세요.

**평가 기준:**
  ✓ 각 항목별 점수를 먼저 산정한 후 합산
  ✗ 너무 긴 문장이나 복잡한 표현 감점
  ✗ 모호한 숫자 표현 감점
  
**피드백 작성 시:** 
  ✓ **각 항목별 점수와 근거를 제시** (예: "문장 구조 25/30점, 논리성 20/25점, 용어 평이성 15/30점, 숫자 표현 10/15점")
  ✓ 어떤 설명이 명확했는지 구체적으로 언급
  ✓ 모호했던 표현은 Before → After 형식으로 제안
  ✓ 예: "'최소 100' → '최소 100만원'으로 명확히 표현하세요"
  ✓ 예: "'거치기간' → '이자만 내는 기간'으으로 쉽게 설명하세요"
  ✓ 예: "평균 문장 길이가 150자로 길어서 이해하기 어려울 수 있습니다. 80자 이내로 줄이세요"

**4️⃣ 친절도 (Kindness, 0-100점)**
- 목적: 고객 중심의 배려 있는 언어를 사용했는가

**점수 구성 (100점):**
- **기본 정중함 및 긍정 표현 (30점)**:
  * 전반적으로 정중한 어투 유지: 30점
  * 대부분 정중하나 일부 형식적: 20점
  * 정중함과 무뚝뚝함 혼재: 10점
  * 무뚝뚝하거나 부정적: 0점
  
- **고객 선택권 존중 및 배려 (25점)**:
  * 고객 선택권 존중 표현 사용 ("~하시면 편리할 수 있습니다"): 25점
  * 대부분 존중하나 일부 강제 느낌: 18점
  * 선택권 제한하는 표현 사용: 8점
  * 강제적인 표현: 0점
  
- **공감 및 이해 표현 (20점)**:
  * 고객 불편/불만에 대한 공감 표현: 20점
  * 일부 공감 표현: 12점
  * 공감 표현 부족: 5점
  * 공감 표현 없음: 0점
  
- **추가 도움 제공 의지 (10점)**:
  * 추가 도움 제공 의지 명확히 표현: 10점
  * 기본적인 마무리: 5점
  * 추가 도움 의지 없음: 0점
  
- **부정 표현 회피 (15점)**: (감점 방식)
  * 부정 표현 0개: 15점
  * 부정 표현 1개: 8점
  * 부정 표현 2개: 3점
  * 부정 표현 3개 이상: 0점

**긍정 표현 예시:**
  "감사합니다", "도와드리겠습니다", "안내해 드리겠습니다"
  "~해주세요", "~드리겠습니다"
  "추가로 궁금한 점 있으시면 언제든지 문의해 주세요"

**부정 표현 예시 (감점):**
  "안 됩니다", "불가능합니다", "모르겠어요"
  명령형/무뚝뚝한 표현
  강제적인 표현 ("더 빠르고 정확합니다")

**피드백 작성 시:** 
  ✓ **각 항목별 점수와 근거를 제시** (예: "기본 정중함 25/30점, 선택권 존중 20/25점, 공감 표현 15/20점, 추가 도움 의지 8/10점, 부정 표현 회피 12/15점")
  ✓ 친절했던 표현을 구체적으로 인용하여 칭찬
  ✓ 개선이 필요한 표현은 Before → After 형식으로 제시
  ✓ 고객의 불편/불만에 대한 대응 여부 평가
  ✓ 고객의 반복 질문이나 추가 질문에 대한 인내심 평가
  ✓ 예: "'더 빠르고 정확합니다' → '더 편리할 수 있습니다'로 바꾸면 고객 선택권을 존중하는 표현이 됩니다"
  ✓ 예: "고객이 답답해하실 때 '불편을 드려 죄송합니다' 같은 공감 표현을 사용하면 더 친절합니다"
  ✓ 예: "급함형 고객에게는 '바로 처리해 드리겠습니다'처럼 빠른 응답을 강조하면 좋습니다"

**5️⃣ 자신감 (Confidence, 0-100점)** - 전달력 평가의 일부
- 목적: 불확실한 어투 없이 확신 있게 안내했는가

**체크리스트 (모든 항목을 평가하세요):**
- [ ] 확정적 표현 비율 (80점)
- [ ] 모호 표현 감점 (20점)

**단계별 평가:**

**1단계: 확정적 표현 비율 (80점)**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
평가 기준: 전체 발언 중 확정적 표현 비율

| 확정적 표현 비율 | 점수 |
|----------------|------|
| 90% 이상 | 80점 |
| 70-90% | 65점 |
| 50-70% | 45점 |
| 30-50% | 25점 |
| 30% 미만 | 10점 |

점수: ?/80점
근거: "확정적 표현 비율 X%이므로 ?점 부여"

**2단계: 모호 표현 감점 (20점)**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
평가 기준: 모호 표현 감점 방식

| 모호 표현 개수 | 점수 |
|--------------|------|
| 0개 | 20점 |
| 1-2개 | 15점 |
| 3-4개 | 10점 |
| 5-6개 | 5점 |
| 7개 이상 | 0점 |

점수: ?/20점
근거: "모호 표현 X개 발견하므로 ?점 부여"

**최종 점수 계산:**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
확정적 표현 비율: ?점
모호 표현 회피: ?점
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
총점: ?/100점

**확정적 표현 예시:**
  "합니다", "됩니다", "가능합니다", "맞습니다"
  "~입니다", "~됩니다", "~가능합니다"

**모호 표현 예시 (감점):**
  "~같아요", "~일 수도 있어요", "~보이는데요"
  "확실하진 않지만", "아마도", "모르겠지만"

**평가 기준:**
  ✓ 각 항목별 점수를 먼저 산정한 후 합산
  ⚠️ 부정확한 정보를 확신 있게 말한 경우도 감점 (지식 평가와 연계)
  
**피드백 작성 시:** 
  ✓ **각 항목별 점수와 근거를 제시** (예: "확정적 표현 비율 70/80점, 모호 표현 회피 15/20점")
  ✓ 자신감 있었던 부분을 자연스럽게 인용하여 칭찬
  ✓ 불확실해 보였던 표현은 Before → After 형식으로 제안
  ✓ 예: "'~같아요' → '~입니다'로 바꾸면 더 확신 있게 들립니다"
  ✓ 모호 표현의 개수와 위치를 구체적으로 제시

**💡 전달력 (Clarity + Confidence, 0-100점)**
- 명확성과 자신감을 종합하여 정보 전달 역량을 평가
- 피드백 작성 시 [명확성]과 [자신감]을 자연스럽게 연결하여 작성
- 각 문단에서 잘한 점과 개선점을 구체적으로 제시
- 구체적인 예시와 개선 방안 포함

**6️⃣ 페르소나 정합도 (Persona Fit, 0-100점)**
- 목적: 고객 페르소나 타입에 맞는 대응 전략을 체계적으로 사용했는가
- 🎯 **고객 타입**: {persona.get('type', '일반')} 또는 {persona.get('customer_style', '일반')}
- ⚠️ **중요**: 평가 시 위에서 확인한 고객 타입에 맞는 평가 기준을 적용하세요

**평가 기준 (고객 타입별로 다른 기준 적용):**

**A. 불만형 고객 (타입이 "불만형"인 경우)**
점수 구성: 문맥적_공감사과 (50점) + 문맥적_해결책제시 (40점) + 부정패턴_회피 (10점) = 100점

**⚠️ 중요: 빈도보다 문맥(적절한 시점, 대화 흐름, 품질)을 중시하여 평가하세요**

1. **공감 및 사과 표현 (50점) - 문맥 중심 평가**
   
   **A-1. 적절한 시점 파악 및 대응 (25점)**
   ✓ 고객 불만 표현 직후 공감/사과 여부 평가:
     - 고객이 불만을 표현한 직후 (1-2턴 이내) 공감/사과: 25점
     - 고객이 불만을 표현한 후 약간 늦게 (3-4턴) 공감/사과: 15점
     - 고객이 불만을 표현한 후 너무 늦게 (5턴 이상) 공감/사과: 8점
     - 고객 불만 표현이 없는데도 공감/사과: 5점 (부적절한 시점)
     - 고객 불만 표현 후 공감/사과 없음: 0점
   
   **A-2. 공감 표현의 품질 및 맥락 적합성 (15점)**
   ✓ 공감 표현의 깊이와 구체성 평가:
     - 구체적이고 진정성 있는 공감 (예: "불편을 드려 정말 죄송합니다. 이해하시기 어려우셨을 것 같습니다"): 15점
     - 적절한 공감 표현 (예: "불편을 드려 죄송합니다"): 10점
     - 단순한 사과만 (예: "죄송합니다"): 5점
     - 형식적이거나 의미 없는 공감: 2점
     - 공감 표현 없음: 0점
   
   **A-3. 대화 흐름의 자연스러움 (10점)**
   ✓ 공감/사과가 대화 흐름상 자연스러운가:
     - 불만 표현 → 즉시 공감/사과 → 해결책 제시 순서: 10점
     - 불만 표현 → 공감/사과 (순서는 맞으나 약간 어색): 7점
     - 불만 표현 → 해결책만 → 나중에 공감/사과: 4점 (순서 문제)
     - 불만 표현과 무관한 시점에 공감/사과: 2점
     - 공감/사과가 전혀 없음: 0점
   
   ✗ 감점 요인:
     - 불만을 무시하거나 방어적인 태도 (예: "그건 우리 책임이 아닙니다"): -15점
     - 책임 회피 표현 (예: "저는 그런 지시를 받지 못했습니다"): -10점
     - 고객 불만 표현 직후에도 공감/사과 없이 본론만 진행: -10점
     - 최소 0점

2. **해결책 제시 (40점) - 문맥 중심 평가**
   
   **B-1. 해결책 제시의 타이밍 및 순서 (20점)**
   ✓ 공감 후 해결책 제시 여부 평가:
     - 고객 불만 → 공감/사과 → 즉시 해결책 제시: 20점 (완벽한 순서)
     - 고객 불만 → 공감/사과 → 약간 늦게 해결책 제시: 15점
     - 고객 불만 → 해결책만 제시 (공감 없음): 10점 (순서 문제)
     - 고객 불만 후 해결책 제시 없음: 0점
   
   **B-2. 해결책의 구체성 및 실현 가능성 (15점)**
   ✓ 해결책의 품질 평가:
     - 구체적이고 실현 가능한 해결 방안 제시 (예: "바로 수정 처리해 드리겠습니다. 10분 이내로 완료될 예정입니다"): 15점
     - 일반적인 해결책 제시 (예: "해결해 드리겠습니다"): 10점
     - 모호한 해결책 제시 (예: "검토해 보겠습니다"): 5점
     - 해결책 제시 없음: 0점
   
   **B-3. 해결책 제시의 적절성 (5점)**
   ✓ 고객의 구체적 불만에 맞는 해결책인가:
     - 고객의 불만 사항과 직접 관련된 해결책: 5점
     - 관련은 있으나 약간 다른 해결책: 3점
     - 관련 없는 해결책: 1점
     - 해결책 없음: 0점
   
   ✗ 감점 요인:
     - 해결책 제시 없이 시간만 끌기: -10점
     - 불가능한 해결책 약속: -15점

3. **부정 패턴 회피 (10점)**
   ✓ 기본 점수: 10점
   ✗ 감점 요인:
     - 부정 패턴 발견 시: "안 됩니다", "불가능합니다", "할 수 없습니다" 각 표현당 -3점
     - 불만형 고객에게 부정적 응답은 특히 감점 (각 표현당 -4점)
     - 최소 0점, 최대 10점

**점수 계산 예시 (불만형):**
- 고객이 "왜 이렇게 복잡하죠?" 불만 표현 직후 1턴 내 공감/사과: 25점
- 구체적이고 진정성 있는 공감 ("불편을 드려 정말 죄송합니다"): 15점
- 자연스러운 대화 흐름 (불만 → 공감 → 해결책): 10점
- 공감 후 즉시 해결책 제시: 20점
- 구체적이고 실현 가능한 해결책: 15점
- 고객 불만과 직접 관련된 해결책: 5점
- 부정 패턴 없음: 10점
- **총점: 100점**

**B. 급함형 고객 (타입이 "급함형"인 경우)**
점수 구성: 문맥적_빠른대응 (40점) + 문맥적_간결성 (40점) + 문맥적_핵심전달 (20점) = 100점

**⚠️ 중요: 빈도보다 문맥(고객의 급함 상황 파악, 적절한 시점 대응, 효율성)을 중시하여 평가하세요**

1. **빠른 처리 표현 및 대응 (40점) - 문맥 중심 평가**
   
   **A-1. 고객 급함 상황 파악 및 즉각 대응 (20점)**
   ✓ 고객이 급함을 표현한 직후 빠른 처리 의지 표명 여부:
     - 고객 급함 표현 직후 (1턴 이내) 빠른 처리 의지 명확히 표시 (예: "바로 처리해 드리겠습니다"): 20점
     - 고객 급함 표현 직후 빠른 처리 의지 있으나 약간 모호: 15점
     - 고객 급함 표현 후 약간 늦게 빠른 처리 의지 표시: 10점
     - 고객 급함 표현이 없는데도 빠른 처리 표현 사용: 5점 (부적절한 시점)
     - 고객 급함 표현 후 빠른 처리 의지 없음: 0점
   
   **A-2. 빠른 처리 표현의 품질 및 실현 가능성 (15점)**
   ✓ 빠른 처리 의지의 구체성 평가:
     - 구체적이고 즉시 실현 가능한 표현 (예: "지금 바로 처리해 드리겠습니다. 5분 내로 완료됩니다"): 15점
     - 일반적인 빠른 처리 표현 (예: "바로 처리해 드리겠습니다"): 10점
     - 모호한 빠른 처리 표현 (예: "빨리 해드리겠습니다"): 5점
     - 빠른 처리 표현 없음: 0점
   
   **A-3. 대화 흐름상 빠른 대응의 자연스러움 (5점)**
   ✓ 급함 상황에 맞는 빠른 대응이 자연스러운가:
     - 급함 표현 → 즉시 빠른 처리 의지 → 핵심 정보 전달: 5점
     - 급함 표현 → 빠른 처리 의지 (약간 어색): 3점
     - 급함 표현과 무관한 시점에 빠른 처리 표현: 1점
     - 빠른 처리 표현 없음: 0점
   
   ✗ 감점 요인 (맥락을 고려하여 평가):
     - **부적절한 시점/맥락에서 느린 처리 암시**: 
       * 고객 급함 표현 직후에도 빠른 처리 의지 없이 "잠시만 기다려주세요", "시간이 걸릴 수 있습니다"만 반복 → -15점
       * 고객이 급함을 표현했는데도 처리 시간에 대한 설명 없이 지연만 암시 → -10점
     - **적절한 맥락에서는 감점하지 않음**:
       * 고객을 달래면서 사용: "잠시만 기다려주세요. 바로 처리해 드리겠습니다" → 감점 없음
       * 정직하고 투명한 소통: "처리하는데 약 5분 정도 걸릴 수 있습니다. 최대한 빠르게 진행하겠습니다" → 감점 없음
       * 구체적인 시간 안내와 함께 사용: "약 3분 정도 소요될 수 있지만, 최대한 빠르게 진행하겠습니다" → 감점 없음
     - 최소 0점

2. **문장 간결성 및 효율성 (40점) - 문맥 중심 평가**
   
   **B-1. 급함 상황에 맞는 간결한 설명 (25점)**
   ✓ 고객의 급함 상황을 고려한 설명의 간결성:
     - 급함 상황에 맞게 매우 간결하고 핵심만 전달 (평균 40자 이하): 25점
     - 급함 상황에 맞게 간결한 설명 (평균 40-60자): 20점
     - 약간 장황하나 급함을 고려한 설명 (평균 60-80자): 12점
     - 급함을 고려하지 않은 장황한 설명 (평균 80자 이상): 5점
     - 매우 장황한 설명 (평균 120자 이상): 0점
   
   **B-2. 불필요한 설명 회피 여부 (10점)**
   ✓ 급함형 고객에게 불필요한 부가 설명을 피했는가:
     - 핵심 정보만 전달, 부가 설명 완전히 회피: 10점
     - 대부분 핵심 정보만, 약간의 부가 설명: 7점
     - 핵심과 부가 설명 혼재: 4점
     - 불필요한 부가 설명 많음: 1점
     - 핵심보다 부가 설명이 더 많음: 0점
   
   **B-3. 연결어 및 장황한 표현 사용 최소화 (5점)**
   ✓ 간결성을 해치는 표현 회피 여부:
     - 연결어 및 장황한 표현 최소 사용: 5점
     - 적절한 수준의 연결어 사용: 3점
     - 과도한 연결어 사용 (그리고, 또한, 추가로 등): 1점
     - 매우 과도한 연결어 사용: 0점

3. **핵심 정보 전달 및 순서 (20점) - 문맥 중심 평가**
   
   **C-1. 고객 질문에 대한 직접적 답변 (12점)**
   ✓ 급함형 고객의 질문에 바로 답변했는가:
     - 모든 질문에 즉시 직접 답변: 12점
     - 대부분 질문에 직접 답변: 8점
     - 일부 질문에만 직접 답변: 4점
     - 질문에 대한 직접 답변 없이 장황한 설명만: 1점
     - 질문에 대한 답변 없음: 0점
   
   **C-2. 핵심 정보 우선 전달 순서 (8점)**
   ✓ 급함형 고객에게 핵심 정보를 먼저 전달했는가:
     - 항상 핵심 정보를 먼저 전달: 8점
     - 대부분 핵심 정보 먼저: 6점
     - 핵심 정보가 중간에 위치: 3점
     - 핵심 정보가 뒤로 밀림: 1점
     - 핵심 정보 전달 순서 문제: 0점
   
   ✗ 감점 요인:
     - 핵심 정보를 뒤로 미루고 불필요한 설명 먼저: -10점
     - 급함형 고객 질문에 답하지 않고 다른 설명부터 시작: -12점

**점수 계산 예시 (급함형):**
- 고객 "빨리 해야 하는데요" 표현 직후 1턴 내 "바로 처리해 드리겠습니다": 20점
- 구체적이고 즉시 실현 가능한 표현: 15점
- 자연스러운 대화 흐름: 5점
- 급함 상황에 맞게 간결한 설명 (평균 50자): 20점
- 핵심 정보만 전달, 부가 설명 회피: 10점
- 연결어 최소 사용: 5점
- 모든 질문에 즉시 직접 답변: 12점
- 항상 핵심 정보 먼저: 8점
- **총점: 95점**

**C. 긍정형 고객 (타입이 "긍정형"인 경우)**
점수 구성: 문맥적_긍정대응 (60점) + 문맥적_추가안내 (40점) = 100점

**⚠️ 중요: 빈도보다 문맥(고객의 긍정적 반응에 적절히 대응, 자연스러운 친절도, 적절한 시점 추가 안내)을 중시하여 평가하세요**

1. **긍정 표현 및 대응 (60점) - 문맥 중심 평가**
   
   **A-1. 고객 긍정 반응에 대한 적절한 대응 (25점)**
   ✓ 고객의 긍정적 표현에 자연스럽게 긍정적으로 대응했는가:
     - 고객 긍정 표현에 즉시 자연스럽게 긍정적으로 대응 (예: 고객 "좋네요!" → 직원 "감사합니다. 더 도와드릴 것이 있으면 언제든 말씀해 주세요"): 25점
     - 고객 긍정 표현에 긍정적으로 대응하나 약간 어색: 18점
     - 고객 긍정 표현에 적절히 대응하나 반응이 약함: 12점
     - 고객 긍정 표현에도 형식적으로만 대응: 6점
     - 고객 긍정 표현에 부정적으로 대응하거나 무시: 0점
   
   **A-2. 긍정 표현의 품질 및 자연스러움 (20점)**
   ✓ 긍정 표현이 자연스럽고 적절한가:
     - 자연스럽고 진정성 있는 긍정 표현 (예: "감사합니다. 고객님께서 만족하시니 저도 기쁩니다"): 20점
     - 적절한 긍정 표현 (예: "감사합니다", "좋습니다", "도와드리겠습니다"): 15점
     - 형식적이지만 긍정적인 표현: 10점
     - 부자연스러운 긍정 표현: 5점
     - 긍정 표현 없음: 0점
   
   **A-3. 대화 흐름상 긍정 분위기 유지 (15점)**
   ✓ 긍정형 고객과의 대화 분위기를 잘 유지했는가:
     - 전반적으로 긍정적이고 친절한 분위기 유지: 15점
     - 대부분 긍정적 분위기 유지: 12점
     - 긍정적 분위기가 중간에 깨짐: 7점
     - 긍정적 분위기 유지 어려움: 3점
     - 긍정적 분위기 없음: 0점
   
   ✗ 감점 요인:
     - 부정적 표현: "안 됩니다", "불가능합니다" 각 표현당 -10점
     - 긍정형 고객에게 부정적 톤 사용: -15점
     - 최소 0점

2. **추가 안내 제공 (40점) - 문맥 중심 평가**
   
   **B-1. 적절한 시점 추가 안내 제공 (20점)**
   ✓ 고객이 추가 정보를 필요로 할 때 적절히 제공했는가:
     - 고객이 추가 정보를 묻거나 필요해 보일 때 적절히 제공 (예: 고객 "그 외에는?" → 직원 "추가로 이런 서비스도 있습니다"): 20점
     - 고객이 추가 정보를 묻지 않았지만 적절한 시점에 제공: 15점
     - 고객이 추가 정보를 필요로 하는데 제공하지 않음: 8점
     - 부적절한 시점에 추가 안내 제공: 5점
     - 추가 안내 전혀 제공하지 않음: 0점
   
   **B-2. 추가 안내의 품질 및 유용성 (15점)**
   ✓ 제공한 추가 안내가 고객에게 유용한가:
     - 고객 상황에 맞는 매우 유용한 추가 안내: 15점
     - 유용한 추가 안내: 12점
     - 일반적인 추가 안내: 8점
     - 유용성이 낮은 추가 안내: 4점
     - 추가 안내 없음: 0점
   
   **B-3. 친절한 마무리 및 지속적 관심 표현 (5점)**
   ✓ 대화 마무리 시 친절하고 지속적인 관심을 표현했는가:
     - 친절하고 지속적인 관심 표현 (예: "추가로 궁금한 점 있으시면 언제든지 문의해 주세요"): 5점
     - 기본적인 친절한 마무리: 3점
     - 형식적인 마무리: 1점
     - 마무리 없음: 0점

**점수 계산 예시 (긍정형):**
- 고객 "좋네요!" 긍정 표현에 즉시 자연스럽게 긍정적으로 대응: 25점
- 자연스럽고 진정성 있는 긍정 표현: 20점
- 전반적으로 긍정적이고 친절한 분위기 유지: 15점
- 고객이 추가 정보를 묻거나 필요해 보일 때 적절히 제공: 20점
- 고객 상황에 맞는 매우 유용한 추가 안내: 15점
- 친절하고 지속적인 관심 표현: 5점
- **총점: 100점**

**D. 알 수 없는 타입 또는 일반 고객 (타입이 위 3가지가 아닌 경우)**
- 기본 점수 50점 부여
- 일반적인 친절도 기준으로 평가

**⚠️ 평가 시 주의사항 (매우 중요):**

1. **반드시 위에서 확인한 고객 타입에 맞는 평가 기준을 적용하세요**

2. **빈도보다 문맥(적절한 시점, 대화 흐름, 품질)을 중시하여 평가하세요**
   - 단순히 키워드나 표현의 개수를 세는 것이 아닌, **언제, 어떤 상황에서, 어떻게** 사용했는지를 평가하세요
   - 예: 공감 표현이 3회 있어도 부적절한 시점에 사용했다면 점수가 낮아야 합니다
   - 예: 공감 표현이 1회만 있어도 고객 불만 표현 직후 적절한 시점에 구체적으로 사용했다면 높은 점수를 부여하세요

3. **대화 흐름과 맥락을 정확히 파악하세요**
   - 고객의 발화를 먼저 읽고, 그에 대한 직원의 응대가 적절한 시점인지, 자연스러운지 평가하세요
   - 대화의 앞뒤 맥락을 고려하여 평가하세요
   - 예: 고객이 불만을 표현하기 전에 공감/사과를 했다면 이는 부적절한 시점입니다

4. **각 항목별 점수를 문맥에 맞게 단계적으로 계산한 후 합산하세요**
   - 적절한 시점 파악 (0-25점) → 표현의 품질 (0-15점) → 대화 흐름의 자연스러움 (0-10점) 순으로 평가
   - 예: "불만형 고객 평가: 고객이 '왜 이렇게 복잡하죠?' 불만 표현 직후 1턴 내 공감/사과 → 25점 (적절한 시점), 구체적이고 진정성 있는 공감 ('불편을 드려 정말 죄송합니다') → 15점 (품질), 자연스러운 대화 흐름 (불만 → 공감 → 해결책) → 10점, 총 50점"

5. **점수 계산 과정을 명확히 기록하세요** (피드백에 반드시 포함)
   - 각 항목별로: 1) 고객의 발화 맥락, 2) 직원의 응대 시점, 3) 표현의 품질, 4) 대화 흐름의 자연스러움을 모두 기록
   - 예: "불만형 고객 평가: 고객이 '처리가 너무 오래 걸리네요' 불만 표현 직후, 직원이 1턴 내에 '불편을 드려 정말 죄송합니다. 이해하시기 어려우셨을 것 같습니다' 라고 구체적으로 공감 → 적절한 시점 25점 + 품질 15점 + 자연스러운 흐름 10점 = 50점"

6. **문맥 평가 기준을 엄격히 적용하세요**
   - 적절한 시점: 고객의 상황 변화(불만/급함/긍정 표현) 직후 1-2턴 내 대응이 가장 중요
   - 표현의 품질: 단순 반복이 아닌 구체적이고 진정성 있는 표현인가
   - 대화 흐름: 자연스러운 순서(불만 → 공감 → 해결책 등)를 따랐는가

7. **중복 제거**: 기술(Skill) 평가에서 이미 언급한 고객 타입별 대응은 간단히 참조만 하고, 페르소나 정합도에서는 문맥적 대응 전략(시점, 품질, 흐름) 사용 여부를 평가하세요

# **피드백 작성 형식:**
# ```
# [명확성]
# 문장이 간결하고 명확했습니다. 복잡한 금융용어를 쉽게 풀어서 설명한 점이 좋았습니다. 
# 다만 지식 평가에서 언급한 "최소 100" 표현은 "최소 100만원"으로 명확히 설명하는 것이 좋습니다. 
# "초저금리" 대신 "아주 낮은 금리" 같은 쉬운 표현을 사용하면 고객이 더 쉽게 이해할 수 있습니다.

# [자신감]
# 대부분의 정보를 확신 있게 전달했습니다. "가능합니다", "됩니다" 같은 확정적 표현을 잘 사용했습니다. 
# 다만 "~같아요", "~보이는데요" 같은 불확실한 표현이 일부 있어 아쉬웠습니다. 
# 지식 평가에서 언급한 부정확한 정보를 확신 있게 말한 부분도 자신감 측면에서 개선이 필요합니다.
# ```

**⚠️ 중복 제거 가이드:**
- 지식 평가에서 이미 상세히 다룬 오류(예: "최소 100")는 전달력에서 간단히 참조만
- 예: "지식 평가에서 언급한 '최소 100' 표현은 명확성 측면에서도 개선이 필요합니다"
- 같은 오류를 여러 역량에서 반복 설명하지 말고, 각 역량의 관점에서만 평가

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 **평가 대상 정보**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**고객 정보:**
- 고객 유형: {persona.get('type', '일반')}
- 금융 이해도: {persona.get('financial_literacy', '보통')}
- 연령대: {persona.get('age_group', '')}
- 직업: {persona.get('occupation', '')}

**상담 상황:**
- 제목: {situation.get('title', '')}
- 카테고리: {situation.get('category', '')}
- 설정된 목표: {', '.join(goals) if goals else '없음'}
- 목표 달성 현황: {len(achieved_goal_indices)}/{len(goals) if goals else 0}개 달성 ({goal_achievement_rate*100:.0f}%)
{achieved_goals_text}

**대화 내용:**
{conversation_context}

⚠️ **중요: 대화 내용을 정확히 참조하세요**
- 실제 대화에서 직원이 정확히 말한 내용을 자연스럽게 인용하세요
- 제품 지식 자동 검증 결과와 실제 대화 내용을 대조하여 정확히 평가하세요

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 **피드백 작성 가이드**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

각 지표별 피드백은 **마크다운 형식**으로 작성하세요. 가독성을 높이기 위해 다음 형식을 사용하세요:

**피드백 작성 형식:**
1. **잘한 점** 섹션: `**잘한 점**` 제목 사용 (필수)
   - 구체적인 예시를 `**볼드**`로 강조
   - 예: `**"감사합니다"**, **"도와드리겠습니다"** 같은 정중한 표현을 잘 사용했습니다.`
   
2. **개선점** 섹션: `**개선점**` 제목 사용 (개선할 점이 있을 때만 작성)
   - Before → After 형식: `**"최소 100"** → **"최소 100만원"**` (양쪽 모두 볼드)
   - 중요 키워드는 `**볼드**`로 강조
   - ⚠️ **점수가 100점이거나 개선할 점이 없으면 개선점 섹션을 생략하거나 "현재 제공한 정보는 모두 정확합니다"와 같이 간단히 언급하세요**
   
3. **구체적인 예시**: 대화에서 실제로 사용한 표현을 `**따옴표와 볼드**`로 인용
   - 예: `**"거치기간"**이라는 용어 대신 **"이자만 내는 기간"**으로 설명하면 좋습니다.`

4. **실용적 조언**: 다음 시뮬레이션에서 바로 적용 가능한 팁

**마크다운 사용 가이드:**
- 중요 키워드: `**키워드**` (볼드)
- 인용 표현: `**"표현"**` (따옴표 + 볼드)
- Before → After: `**"Before"** → **"After"**`
- 섹션 제목: `**잘한 점**`, `**개선점**`
- 리스트: `- 항목` (필요시)

**중복 제거 원칙:**
- 같은 오류를 여러 역량에서 반복하지 않기

**피드백 예시 (마크다운 형식):**
```
**잘한 점**
**"금리 2.15%"**를 명확히 제시하여 좋았습니다. **"~입니다."**, **"~됩니다."** 같은 확정적 표현을 잘 사용했습니다.

**개선점**
**"거치기간"**이라는 용어 대신 **"이자만 내는 기간"**으로 설명하면 고객이 더 쉽게 이해할 수 있습니다. **"최소 100"** → **"최소 100만원"**으로 명확히 표현하세요.
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📤 **출력 형식 (JSON)**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ **중요: 반드시 다음 JSON 형식으로 응답하세요. 각 역량의 breakdown 필드에 세부 항목별 점수와 근거를 명확히 기록하세요.**

다음 JSON 형식으로 응답하세요:
{{
    "knowledge": {{
        "score": <0-100 점수, breakdown의 모든 항목 점수 합산>,
        "breakdown": {{
            "product_accuracy": {{"score": <점수>, "max": <최대점수>, "reason": "<근거>"}},
            "procedure_knowledge": {{"score": <점수>, "max": <최대점수>, "reason": "<근거>"}},
            "general_finance": {{"score": <점수>, "max": <최대점수>, "reason": "<근거>"}},
            "category_specific": {{"score": <점수>, "max": <최대점수>, "reason": "<근거>"}}
        }},
        "feedback": "<마크다운 형식, **잘한 점** 섹션은 필수, **개선점** 섹션은 개선할 점이 있을 때만 작성. **상품 정보의 정확성**에만 집중하여 피드백 작성. 🚨 **중요: 위 제품 지식 자동 검증 결과의 '정확한 정보 목록'에 있는 claim만 잘한 점에 언급하고, '부정확한 정보 목록'에 있는 claim만 개선점에 언급하세요. 같은 claim이 잘한 점과 개선점에 동시에 나타나면 안 됩니다 (모순 금지).** 구체적 예시는 **볼드**로 강조. 부정확한 정보는 정확한 정보와 함께 제시 (예: **'금리 3.5%'** → **'실제로는 2.15%'**). 제품 지식 자동 검증 결과의 LLM reasoning 활용. ⚠️ 표현의 명확성(단위 명시, 용어 평이성)은 전달력에서 다루므로 지식 피드백에서 언급하지 않음. ⚠️ 점수가 100점이면 모든 정보가 정확하다는 의미이므로 개선점 섹션은 생략하거나 '제공한 모든 상품 정보가 정확합니다'와 같이 간단히 언급>"
    }},
    "skill": {{
        "score": <0-100 점수, breakdown의 모든 항목 점수 합산>,
        "breakdown": {{
            "conversation_flow": {{"score": <점수>, "max": 20, "reason": "<근거>"}},
            "goal_achievement": {{"score": <점수>, "max": 60, "reason": "<근거>"}},
            "question_usage": {{"score": <점수>, "max": 10, "reason": "<근거>"}},
            "feedback_loop": {{"score": <점수>, "max": 10, "reason": "<근거>"}}
        }},
        "feedback": "<마크다운 형식, **잘한 점**과 **개선점** 섹션으로 구분. 대화 흐름과 목표 달성도 평가, 구체적 개선 제안. 달성한 목표와 미달성한 목표를 명시하고, 미달성 목표에 대한 개선 방안 제시>"
    }},
    "clarity": {{
        "score": <0-100 점수, breakdown의 모든 항목 점수 합산>,
        "breakdown": {{
            "sentence_structure": {{"score": <점수>, "max": 30, "reason": "<근거>"}},
            "logic": {{"score": <점수>, "max": 25, "reason": "<근거>"}},
            "terminology": {{"score": <점수>, "max": 30, "reason": "<근거>"}},
            "number_clarity": {{"score": <점수>, "max": 15, "reason": "<근거>"}}
        }},
        "feedback": "<마크다운 형식, **잘한 점**과 **개선점** 섹션으로 구분. 문장 구조와 용어 사용 평가, 쉬운 표현 제안. 모호한 표현은 Before → After 형식으로 제안 (예: **'최소 100'** → **'최소 100만원'**)>"
    }},
    "kindness": {{
        "score": <0-100 점수, breakdown의 모든 항목 점수 합산>,
        "breakdown": {{
            "politeness": {{"score": <점수>, "max": 30, "reason": "<근거>"}},
            "choice_respect": {{"score": <점수>, "max": 25, "reason": "<근거>"}},
            "empathy": {{"score": <점수>, "max": 20, "reason": "<근거>"}},
            "help_willingness": {{"score": <점수>, "max": 10, "reason": "<근거>"}},
            "negative_avoidance": {{"score": <점수>, "max": 15, "reason": "<근거>"}}
        }},
        "feedback": "<마크다운 형식, **잘한 점**과 **개선점** 섹션으로 구분. 친절한 표현 사례와 개선 필요 표현 지적. Before → After 형식으로 제안 (예: **'더 빠르고 정확합니다'** → **'더 편리할 수 있습니다'**)>"
    }},
    "confidence": {{
        "score": <0-100 점수, breakdown의 모든 항목 점수 합산>,
        "breakdown": {{
            "assertive_ratio": {{"score": <점수>, "max": 80, "reason": "<근거>"}},
            "uncertain_avoidance": {{"score": <점수>, "max": 20, "reason": "<근거>"}}
        }},
        "feedback": "<마크다운 형식, **잘한 점**과 **개선점** 섹션으로 구분. 자신감 있는 어투와 불확실한 표현 비교. Before → After 형식으로 제안 (예: **'~같아요'** → **'~입니다'**). 지식 평가에서 언급한 부정확한 정보를 확신 있게 말한 경우도 언급>"
    }},
    "clarity_confidence": {{
        "score": <(clarity + confidence) / 2, 0-100 점수>,
        "feedback": "<마크다운 형식, 반드시 **[명확성]**과 **[자신감]**을 별도 문단으로 구분하여 작성. 각 문단에서 **잘한 점**과 **개선점**을 구체적으로 제시. 지식 평가에서 이미 상세히 다룬 오류는 간단히 참조만 하고 전달력 관점에서만 평가 (예: '지식 평가에서 언급한 **최소 100** 표현은...'). 구체적인 예시와 Before → After 형식의 개선 방안 포함. 중복 설명 지양>"
    }},
    "persona_fit": {{
        "score": <0-100 점수, 위에서 확인한 고객 타입에 맞는 문맥 중심 평가 기준 적용하여 단계적으로 계산>,
        "feedback": f"<마크다운 형식, **잘한 점**과 **개선점** 섹션으로 구분. **⚠️ 필수: 문맥 중심 점수 계산 과정을 명확히 기록하세요**{newline}{newline}**문맥 중심 점수 계산 과정 기록 예시:**{newline}불만형 고객 평가 기준 적용 (빈도가 아닌 문맥 중시):{newline}- 공감 및 사과 표현 (50점): {newline}  * 적절한 시점 파악 (25점): 고객이 '왜 이렇게 복잡하죠?' 불만 표현 직후 1턴 내에 공감/사과 → 25점{newline}  * 표현의 품질 (15점): '불편을 드려 정말 죄송합니다. 이해하시기 어려우셨을 것 같습니다' - 구체적이고 진정성 있는 공감 → 15점{newline}  * 대화 흐름 (10점): 불만 표현 → 즉시 공감/사과 → 해결책 제시 순서 자연스러움 → 10점{newline}  * 합계 50점{newline}- 해결책 제시 (40점):{newline}  * 타이밍 및 순서 (20점): 공감 후 즉시 해결책 제시 → 20점{newline}  * 구체성 및 실현 가능성 (15점): '바로 수정 처리해 드리겠습니다. 10분 이내로 완료될 예정입니다' - 구체적이고 실현 가능 → 15점{newline}  * 적절성 (5점): 고객의 구체적 불만과 직접 관련된 해결책 → 5점{newline}  * 합계 40점{newline}- 부정 패턴 회피 (10점): 부정 패턴 없음 → 10점{newline}**총점: 100점**{newline}{newline}각 평가 항목별로: 1) 고객의 발화 맥락, 2) 직원의 응대 시점이 적절한지, 3) 표현의 품질 및 구체성, 4) 대화 흐름의 자연스러움을 모두 평가하고 기록하세요. 실제 대화에서 발견한 패턴을 구체적으로 인용하여 설명하세요. 개선점이 있을 경우 문맥적 개선 방안을 구체적으로 제안하세요 (예: '고객 불만 표현 직후 1턴 내에 공감/사과를 하는 것이 좋습니다').>"
    }},
    "summary": "<2-3문장, 전반적인 강점과 핵심 개선점 요약>",
    "improvements": "<3-4개 항목, 다음 시뮬레이션에서 즉시 적용 가능한 구체적 실천 방안>"
}}
"""
            
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": evaluation_prompt}],
                temperature=0.3,
                max_tokens=4000  # 구조화된 응답이 길어질 수 있으므로 토큰 수 증가
            )
            
            # JSON 파싱
            content = response.choices[0].message.content
            print(f"📝 LLM 원본 응답 (처음 500자): {content[:500]}")
            
            # JSON 블록 추출 (```json ... ``` 형식 처리)
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            # JSON 파싱 시도
            try:
                evaluation = json.loads(content)
                print(f"✅ JSON 파싱 성공")
            except json.JSONDecodeError as e:
                print(f"❌ JSON 파싱 실패: {e}")
                print(f"📝 파싱 시도한 내용 (처음 1000자): {content[:1000]}")
                # JSON 파싱 재시도: 마지막 } 찾기
                try:
                    last_brace = content.rfind('}')
                    if last_brace > 0:
                        content_trimmed = content[:last_brace+1]
                        evaluation = json.loads(content_trimmed)
                        print(f"✅ JSON 파싱 재시도 성공 (마지막 }} 기준으로 자름)")
                    else:
                        raise e
                except:
                    print(f"❌ JSON 파싱 재시도도 실패, 기본 피드백 반환")
                    raise e
            
            print(f"📈 기술 점수: {evaluation['skill']['score']}점 (상담 프로세스 + 목표 달성도 종합 평가)")
            
            # 🧪 테스트 모드용: breakdown 데이터 추출 및 로깅
            breakdown_data = {}
            for competency in ['knowledge', 'skill', 'clarity', 'kindness', 'confidence', 'persona_fit']:
                if competency in evaluation and 'breakdown' in evaluation[competency]:
                    breakdown_data[competency] = evaluation[competency]['breakdown']
                    print(f"📊 {competency} breakdown: {len(breakdown_data[competency])}개 세부 항목")
            
            # 🎯 역량 통합: 5가지 → 4가지 (전달력 통합)
            # 친절도만 사용 (공감도 제거)
            kindness_score = evaluation['kindness']['score']
            kindness_feedback = evaluation['kindness']['feedback']

            # 전달력 = (명확성 + 자신감) / 2
            # GPT가 clarity_confidence를 생성했으면 사용, 없으면 평균 계산
            if 'clarity_confidence' in evaluation:
                clarity_confidence_score = evaluation['clarity_confidence']['score']
                clarity_confidence_feedback = evaluation['clarity_confidence']['feedback']
            else:
                # Fallback: 명확성과 자신감의 평균
                clarity_confidence_score = round((evaluation['clarity']['score'] + evaluation['confidence']['score']) / 2)
                # 명확성과 자신감 피드백을 자연스럽게 통합
                clarity_feedback = evaluation['clarity']['feedback']
                confidence_feedback = evaluation['confidence']['feedback']
                clarity_confidence_feedback = f"{clarity_feedback} {confidence_feedback}".replace("  ", " ").strip()
                if len(clarity_confidence_feedback) > 300:
                    clarity_confidence_feedback = clarity_confidence_feedback[:300] + "..."
            
            # 페르소나 정합도 추출
            persona_fit_score = evaluation.get('persona_fit', {}).get('score', 50)  # 기본값 50
            persona_fit_feedback = evaluation.get('persona_fit', {}).get('feedback', '평가되지 않음')
            
            print(f"🎭 페르소나 정합도 점수: {persona_fit_score}점 (고객 타입: {persona.get('type', persona.get('customer_style', '일반'))})")

            # 종합 점수 계산 (5가지 역량: 지식, 기술, 친절도, 전달력, 페르소나 정합도)
            # 가중치: 각 20% (동일 가중치)
            overall_score = (
                evaluation['knowledge']['score'] * 0.20 +
                evaluation['skill']['score'] * 0.20 +
                kindness_score * 0.20 +
                clarity_confidence_score * 0.20 +
                persona_fit_score * 0.20
            )
            
            # 등급 산정
            if overall_score >= 90:
                grade = 'A'
                performance_level = '탁월한 성과'
            elif overall_score >= 80:
                grade = 'B'
                performance_level = '우수한 성과'
            elif overall_score >= 70:
                grade = 'C'
                performance_level = '양호한 성과'
            elif overall_score >= 60:
                grade = 'D'
                performance_level = '보통 수준'
            else:
                grade = 'F'
                performance_level = '개선 필요'
            
            return {
                "overallScore": round(overall_score, 1),
                "grade": grade,
                "performanceLevel": performance_level,
                "summary": evaluation.get('summary', '평가를 완료했습니다.'),
                "competencies": [
                    {"name": "지식", "score": evaluation['knowledge']['score'], "maxScore": 100},
                    {"name": "기술", "score": evaluation['skill']['score'], "maxScore": 100},
                    {"name": "친절도", "score": kindness_score, "maxScore": 100},
                    {"name": "전달력", "score": clarity_confidence_score, "maxScore": 100},
                    {"name": "페르소나 정합도", "score": persona_fit_score, "maxScore": 100}
                ],
                "detailedFeedback": {
                    "knowledge": {
                        **evaluation['knowledge'],
                        # breakdown이 있으면 포함
                        **({"breakdown": evaluation['knowledge'].get('breakdown')} if evaluation['knowledge'].get('breakdown') else {})
                    },
                    "skill": {
                        **evaluation['skill'],
                        # breakdown이 있으면 포함
                        **({"breakdown": evaluation['skill'].get('breakdown')} if evaluation['skill'].get('breakdown') else {})
                    },
                    "kindness": {
                        "score": kindness_score,
                        "feedback": kindness_feedback,
                        # breakdown이 있으면 포함
                        **({"breakdown": evaluation['kindness'].get('breakdown')} if evaluation['kindness'].get('breakdown') else {})
                    },
                    "clarity_confidence": {
                        "score": clarity_confidence_score,
                        "feedback": clarity_confidence_feedback,
                        # clarity와 confidence의 breakdown 통합
                        **({"breakdown": {
                            "clarity": evaluation['clarity'].get('breakdown'),
                            "confidence": evaluation['confidence'].get('breakdown')
                        }} if (evaluation['clarity'].get('breakdown') or evaluation['confidence'].get('breakdown')) else {})
                    },
                    "persona_fit": {
                        "score": persona_fit_score,
                        "feedback": persona_fit_feedback,
                        # breakdown이 있으면 포함
                        **({"breakdown": evaluation['persona_fit'].get('breakdown')} if evaluation['persona_fit'].get('breakdown') else {})
                    },
                    # 하위 호환성을 위해 기존 필드도 유지 (deprecated)
                    "clarity": evaluation['clarity'],
                    "confidence": evaluation['confidence'],
                    # 공감도는 제거되었지만 하위 호환성을 위해 빈 값 제공
                    "empathy": evaluation.get('empathy', {"score": 0, "feedback": "평가되지 않음"})
                },
                # 🧪 테스트 모드용: 전체 breakdown 데이터 (세부 항목별 점수와 근거)
                "breakdown": breakdown_data if breakdown_data else None,
                "improvements": evaluation.get('improvements', '지속적인 연습을 통해 개선하세요.'),
                "goalAchievement": {  # 🎯 목표 달성 정보 추가
                    "total": len(goals) if goals else 0,
                    "achieved": len(achieved_goal_indices),
                    "rate": goal_achievement_rate,
                    "goals": [
                        {
                            "text": goals[i],
                            "achieved": i in achieved_goal_indices,
                            # 🔍 3단계: 달성 증거 포함
                            "turn": turn_tracking.get(i, {}).get("turn") if i in achieved_goal_indices else None,
                            "evidence": turn_tracking.get(i, {}).get("evidence") if i in achieved_goal_indices else None
                        }
                        for i in range(len(goals))
                    ] if goals else []
                }
            }
            
        except Exception as e:
            print(f"❌ 종합 피드백 생성 실패: {e}")
            import traceback
            traceback.print_exc()
            return self._get_default_feedback()
    
    def _get_default_feedback(self) -> Dict:
        """기본 피드백 (오류 발생 시)"""
        # 통합된 5가지 역량으로 반환 (페르소나 정합도 포함)
        return {
            "overallScore": 70.0,
            "grade": "C",
            "performanceLevel": "양호한 성과",
            "summary": "시뮬레이션을 완료했습니다. 더 많은 연습을 통해 역량을 향상시켜보세요.",
            "competencies": [
                {"name": "지식", "score": 70, "maxScore": 100},
                {"name": "기술", "score": 70, "maxScore": 100},
                {"name": "친절도", "score": 70, "maxScore": 100},
                {"name": "전달력", "score": 70, "maxScore": 100},
                {"name": "페르소나 정합도", "score": 50, "maxScore": 100}  # 페르소나 정합도 추가
            ],
            "detailedFeedback": {
                "knowledge": {"score": 70, "feedback": "기본적인 지식은 갖추고 있습니다."},
                "skill": {"score": 70, "feedback": "상담 흐름을 잘 따르고 있습니다."},
                "kindness": {
                    "score": 70,
                    "feedback": "친절한 응대를 하고 있습니다."
                },
                "clarity_confidence": {
                    "score": 70,
                    "feedback": "설명이 대체로 명확하고 자신감 있는 어투를 유지하세요."
                },
                "persona_fit": {
                    "score": 50,
                    "feedback": "평가 중 오류가 발생하여 기본값으로 표시됩니다. 다시 시도해주세요."
                },
                # 하위 호환성을 위해 기존 필드도 유지 (deprecated)
                "empathy": {"score": 70, "feedback": "고객에게 공감하는 태도를 보입니다."},
                "clarity": {"score": 70, "feedback": "설명이 대체로 명확합니다."},
                "confidence": {"score": 70, "feedback": "자신감있는 어투를 유지하세요."}
            },
            "improvements": "지속적인 연습을 통해 역량을 향상시켜보세요."
        }
    
    def analyze_goal_achievement(
        self,
        conversation_history: List[Dict],
        goals: List[str],
        return_detailed: bool = False
    ) -> List[int] | Dict:
        """
        대화 내용을 분석하여 달성된 목표 인덱스 리스트 반환
        
        Args:
            conversation_history: 대화 히스토리 (예: [{"role": "user", "text": "..."}, ...])
            goals: 목표 목록 (예: ["고객의 요구사항 파악", "적절한 상품 추천", ...])
            return_detailed: True면 턴별 추적 정보 포함 (2단계용)
        
        Returns:
            기본: 달성된 목표의 인덱스 리스트 (예: [0, 2])
            상세: {
                "achieved_indices": [0, 2],
                "turn_tracking": {
                    0: {"turn": 3, "evidence": "..."},
                    2: {"turn": 5, "evidence": "..."}
                }
            }
        """
        if not self.openai_client:
            print("⚠️ OpenAI 클라이언트가 초기화되지 않았습니다.")
            return []
        
        if not goals or not conversation_history:
            return []
        
        # 전체 대화 내용 추출 (고객과 직원 모두 포함)
        conversation_parts = []
        for msg in conversation_history:
            role = msg.get("role", "")
            text = msg.get("text", "")
            if role == "user":
                conversation_parts.append(f"직원: {text}")
            elif role == "customer":
                conversation_parts.append(f"고객: {text}")
        
        if not conversation_parts:
            return []
        
        # 대화 내용 요약 (전체 맥락 포함)
        conversation_text = "\n".join(conversation_parts)
        
        # 목표 목록 문자열 생성
        goals_text = "\n".join([
            f"{i}. {goal}"
            for i, goal in enumerate(goals)
        ])
        
        # LLM 프롬프트 구성
        prompt = f"""당신은 은행 직원의 고객 상담 대화를 평가하는 전문가입니다.

다음은 은행 직원과 고객의 전체 대화 내용입니다:
---
{conversation_text}
---

다음은 이 상담에서 달성해야 하는 목표 목록입니다:
---
{goals_text}
---

위 대화 내용을 자세히 분석하여, 각 목표가 달성되었는지 판단해주세요.

**판단 기준 (매우 중요):**

1. **구체성 요구**: 목표는 "실질적인 정보 제공"이 있을 때만 달성으로 인정
   - ❌ 나쁜 예: "환율에 대해 설명드리겠습니다" (실제 설명 없음)
   - ✅ 좋은 예: "현재 달러 환율은 1,300원이며, 환전 수수료는 2%입니다"

2. **정보의 충실성**: 모호하거나 불완전한 답변은 미달성
   - ❌ "이러이러합니다", "그렇습니다", "확인해보겠습니다" (구체적 정보 없음)
   - ❌ "송금 절차는 복잡합니다" (절차 내용 설명 없음)
   - ✅ "송금은 1) 신청서 작성 2) 신분증 제시 3) 송금 완료 순으로 진행됩니다"

3. **목표 텍스트의 구체적 키워드 활용** (🚨 새 형식 특화):
   - 목표 텍스트에 인용부호("")로 강조된 구체적 항목이 있으면, 그 항목들을 모두 다뤘는지 확인
   - 예: 목표에 "\"기본구조·금리\""가 있으면 → 기본구조와 금리 둘 다 다뤘는지 확인
   - 예: 목표에 "\"금리, 한도, 우대조건, 수수료 등\""이 있으면 → 최소 2개 이상 다뤘는지 확인
   - 목표 텍스트에 나열된 구체적 항목(예: "소득, 거래 패턴 등")이 있으면, 최소 1개 이상 언급되었는지 확인
   - 목표가 요구하는 행동 동사(예: "파악한다", "설명하고", "안내하는", "정리해 주고")가 실제로 수행되었는지 확인

4. **목표 키워드 확인**:
   - "파악한다": 고객의 의도/상황을 이해하고 확인하는 대화가 있어야 함 (질문-답변 형식)
   - "설명하고/이해시키는": 구체적인 내용(수치, 절차, 조건 등)이 포함되어야 함
   - "안내하는": 실제 방법이나 단계가 제시되어야 함
   - "고려한다/설명해": 명시적인 경고나 정보 전달이 있어야 함
   - "정리해 주고": 다음 단계나 필요 사항을 명확히 정리해야 함

5. **직원 발화만 평가**: 고객이 말한 내용은 달성 근거가 될 수 없음
   - 직원이 실제로 해당 정보를 제공했는지만 확인
   - 고객의 질문에 대한 직원의 답변으로 달성 판단

6. **엄격한 평가**: 의심스러우면 미달성으로 판단
   - 목표가 요구하는 것의 70% 이상을 충족해야 달성으로 인정
   - 단순히 주제를 언급하는 것만으로는 부족
   - 목표 텍스트에 명시된 구체적 항목들이 모두 다뤄지지 않았으면 미달성

**판단 프로세스:**
각 목표에 대해:
1) 목표 텍스트에서 구체적인 키워드와 요구사항 추출 (인용부호 내 항목, 나열된 항목, 행동 동사)
2) 직원 발화에서 관련 키워드와 정보 찾기
3) 목표에 명시된 구체적 항목들이 다뤄졌는지 확인
4) 목표가 요구하는 행동(파악/설명/안내 등)이 실제로 수행되었는지 확인
5) 목표가 요구하는 수준의 70% 이상을 충족하는지 판단
6) 충족하면 달성, 아니면 미달성

**출력 형식:**
달성된 목표 번호만 쉼표로 구분하여 출력하세요. 예를 들어, 0번과 2번 목표가 달성되었다면:
0,2

달성된 목표가 하나도 없다면:
없음

달성된 목표 번호만 출력하세요. 추가 설명이나 다른 텍스트는 포함하지 마세요."""
        
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=100,
                temperature=0.3  # 일관된 평가를 위해 낮은 temperature 사용
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # 결과 파싱
            if result_text.lower() in ["없음", "none", "없습니다", ""]:
                return []
            
            # 쉼표로 구분된 숫자들 추출
            achieved_indices = []
            for part in result_text.split(","):
                part = part.strip()
                try:
                    index = int(part)
                    if 0 <= index < len(goals):
                        achieved_indices.append(index)
                except ValueError:
                    continue
            
            # 기본 모드: 인덱스만 반환
            if not return_detailed:
                return achieved_indices
            
            # 🔍 2단계: 턴별 추적 분석
            turn_tracking = {}
            
            if achieved_indices:
                print(f"\n🔍 턴별 추적 분석 시작 (달성된 목표: {len(achieved_indices)}개)")
                
                for goal_idx in achieved_indices:
                    goal_text = goals[goal_idx]
                    
                    # 🔍 직원 발화에 턴 번호 붙이기
                    employee_utterances_with_turn = []
                    turn_number = 0
                    for msg in conversation_history:
                        turn_number += 1
                        if msg.get('role') in ['employee', 'user']:
                            text = msg.get('text', '')
                            employee_utterances_with_turn.append(f"턴 {turn_number} [직원]: {text}")
                    
                    employee_conversation = "\n".join(employee_utterances_with_turn)
                    
                    # 각 달성된 목표에 대해 어느 턴에서 달성되었는지 GPT에게 물어보기
                    tracking_prompt = f"""다음은 은행 신입사원(직원)의 발화만 추출한 대화입니다.
"{goal_text}" 목표가 달성된 턴을 찾아주세요.

직원 발화:
{employee_conversation}

목표: {goal_text}

**중요 평가 기준**: 
1. **직원이 실제로 구체적인 정보를 제공한 발화를 찾으세요**
   - 단순히 주제를 언급하는 것이 아니라, 목표를 실질적으로 달성한 발화여야 합니다
   
2. **목표 텍스트의 구체적 키워드 확인**:
   - 목표에 인용부호("")로 강조된 구체적 항목이 있으면, 그 항목들이 실제로 언급되었는지 확인
   - 예: 목표에 "\"기본구조·금리\""가 있으면 → 기본구조와 금리 둘 다 다룬 발화인지 확인
   - 예: 목표에 "\"금리, 한도, 우대조건, 수수료 등\""이 있으면 → 최소 2개 이상 언급된 발화인지 확인
   - 목표 텍스트에 나열된 구체적 항목(예: "소득, 거래 패턴 등")이 최소 1개 이상 언급되었는지 확인
   
3. **목표가 요구하는 행동 확인**:
   - "파악한다" → 고객의 의도/상황을 이해하고 확인하는 대화
   - "설명하고/이해시키는" → 구체적인 내용(수치, 절차, 조건 등) 포함
   - "안내하는" → 실제 방법이나 단계 제시
   - "고려한다/설명해" → 명시적인 경고나 정보 전달
   - "정리해 주고" → 다음 단계나 필요 사항 명확히 정리
   
4. **여러 턴에서 달성되었다면 가장 명확한 턴을 선택하세요**

출력 형식:
턴번호: 발화내용 (직원이 한 말)

예: 5: 현재 달러 환율은 1,300원이며, 환전 수수료는 2%입니다.

찾을 수 없으면 "없음"이라고만 출력하세요."""
                    
                    try:
                        tracking_response = self.openai_client.chat.completions.create(
                            model="gpt-4o-mini",
                            messages=[{"role": "user", "content": tracking_prompt}],
                            max_tokens=200,
                            temperature=0.2
                        )
                        
                        tracking_result = tracking_response.choices[0].message.content.strip()
                        
                        if tracking_result and tracking_result.lower() not in ["없음", "none"]:
                            # "3: 발화내용" 형식 파싱
                            if ":" in tracking_result:
                                parts = tracking_result.split(":", 1)
                                try:
                                    turn_num = int(parts[0].strip())
                                    evidence = parts[1].strip()
                                    
                                    # 증거가 직원 발화인지 재확인 (고객 발화 제외)
                                    # "고객:", "저는", "제가" 등이 포함되면 의심
                                    evidence_lower = evidence.lower()
                                    if any(word in evidence_lower for word in ['고객:', '고객님이', '저는', '제가', '나는', '내가']):
                                        print(f"  ⚠️ 목표 {goal_idx} → 턴 {turn_num}: 고객 발화로 의심됨, 재확인 필요")
                                        # 그래도 저장은 함 (사용자가 판단할 수 있도록)
                                    
                                    turn_tracking[goal_idx] = {
                                        "turn": turn_num,
                                        "evidence": evidence[:200]  # 최대 200자로 증가
                                    }
                                    print(f"  ✓ 목표 {goal_idx} '{goal_text[:30]}...' → 턴 {turn_num}에서 달성")
                                except Exception as parse_error:
                                    print(f"  ⚠️ 목표 {goal_idx} 파싱 실패: {parse_error}")
                                    print(f"     응답: {tracking_result}")
                        else:
                            print(f"  ⚠️ 목표 {goal_idx} '{goal_text[:30]}...' → 증거 찾기 실패 (GPT 응답: {tracking_result})")
                        
                    except Exception as e:
                        print(f"  ⚠️ 목표 {goal_idx} 추적 API 호출 실패: {e}")
            
            return {
                "achieved_indices": achieved_indices,
                "turn_tracking": turn_tracking
            }
            
        except Exception as e:
            print(f"목표 달성 분석 오류: {e}")
            import traceback
            traceback.print_exc()
            if return_detailed:
                return {"achieved_indices": [], "turn_tracking": {}}
            return []
    
    def _process_test_mode_interaction(self, session_data: Dict, audio_data: bytes, user_message: str = "") -> Dict:
        """테스트 모드 음성 상호작용 처리 - 고정 시나리오만 사용, 고객 응답 자동 생성 안 함"""
        print("🧪 ===== 테스트 모드 처리 시작 =====")
        
        test_scenario = session_data.get("test_scenario", {})
        turns = test_scenario.get("turns", [])
        current_turn_index = session_data.get("current_turn_index", 0)
        conversation_history = session_data.get("conversation_history", [])
        stt_evaluations = session_data.get("stt_evaluations", [])
        
        print(f"🧪 현재 턴 인덱스: {current_turn_index}, 전체 턴 수: {len(turns)}")
        
        if current_turn_index >= len(turns):
            # 모든 턴 완료 - 일반 모드와 동일한 지식 평가 수행
            print(f"🧪 ===== 테스트 모드 완료 =====")
            print(f"🧪 STT 평가: {len(stt_evaluations)}개")
            
            # STT 평가 결과
            stt_evaluation_result = self._evaluate_stt_performance(stt_evaluations)
            
            # 🔍 일반 모드와 동일한 지식 평가 로직 수행
            knowledge_verification_result = None
            knowledge_evaluation_result = None
            product_accuracy_info = ""
            
            # 직원 발화만 필터링 (일반 모드와 동일)
            employee_utterances = [
                msg for msg in conversation_history 
                if msg.get("role") == "employee"
            ]
            
            # 상황 정보 가져오기 (일반 모드와 동일한 방식)
            situation = session_data.get("situation", {})
            situation_id = situation.get('id', '')
            has_product_data = situation.get('has_product_data', True)
            
            # 외환/송금 상담은 상품 데이터가 없으므로 제품 검증 스킵
            if situation_id == 'fx':
                has_product_data = False
                print("🧪 ℹ️ 외환/송금 상담: 상품 데이터 없음 - 제품 검증 스킵")
            
            if self.product_knowledge_service and has_product_data and employee_utterances:
                try:
                    print("🧪 🔍 제품 지식 정확도 자동 검증 시작 (일반 모드와 동일한 로직)...")
                    # 🆕 LLM 기반 상품 코드 추출 사용 여부 (설정 파일에서 제어)
                    # 🧪 테스트 모드에서는 LLM 기반 상품 코드 추출 강제 활성화
                    use_llm_extraction = True  # 테스트 모드에서는 항상 LLM 추출 사용
                    knowledge_verification_result = self.product_knowledge_service.batch_verify_conversation(
                        employee_utterances,
                        use_llm=True,  # LLM 검증 포함
                        use_llm_extraction=use_llm_extraction  # 🆕 LLM 기반 상품 코드 추출
                    )
                    
                    accuracy_rate = knowledge_verification_result['accuracy_rate']
                    total_claims = knowledge_verification_result['total_claims']
                    accurate_claims = knowledge_verification_result['accurate_claims']
                    inaccurate_claims = knowledge_verification_result['inaccurate_claims']
                    
                    print(f"🧪   ✓ 제품 정보 검증 완료: {accurate_claims}/{total_claims} 정확 ({accuracy_rate:.1%})")
                    
                    # 일반 모드와 동일한 방식으로 product_accuracy_info 생성
                    errors_detail = []
                    accurate_details = []
                    llm_reasonings = []
                    
                    for v in knowledge_verification_result.get('verifications', []):
                        claim_display = v.claim
                        if hasattr(v, 'full_utterance') and v.full_utterance:
                            if v.claim in v.full_utterance:
                                claim_display = f"'{v.claim}' (대화: ...{v.full_utterance[max(0, v.full_utterance.find(v.claim)-20):min(len(v.full_utterance), v.full_utterance.find(v.claim)+len(v.claim)+20)]}...)"
                        
                        if not v.is_accurate:
                            errors_detail.append(f"• {claim_display} → 실제: {v.ground_truth[:80]}...")
                        else:
                            accurate_details.append(f"• {claim_display} (정확함)")
                        
                        if hasattr(v, 'llm_reasoning') and v.llm_reasoning:
                            llm_reasonings.append(f"• {v.claim}: {v.llm_reasoning}")
                    
                    if total_claims > 0:
                        reasoning_section = ""
                        if llm_reasonings:
                            reasoning_section = f"""
💡 **검증 상세 분석 (LLM reasoning):**
{chr(10).join(llm_reasonings[:5])}
"""
                        
                        accurate_section = ""
                        if accurate_details:
                            accurate_section = f"""
✅ **정확한 정보 목록 (반드시 잘한 점에 언급):**
{chr(10).join(accurate_details[:5])}

⚠️ **위 정확한 정보 목록의 claim은 모두 정확한 정보입니다.**
⚠️ **위 목록에 있는 claim은 개선점에 절대 포함하지 마세요.**
⚠️ **위 목록에 있는 claim은 잘한 점에만 구체적으로 언급하세요.**
"""
                        
                        errors_section = ""
                        if errors_detail:
                            errors_section = f"""
⚠️ **부정확한 정보 목록 (개선점에만 언급):**
{chr(10).join(errors_detail[:5])}

⚠️ **위 부정확한 정보 목록의 claim만 개선점에 언급하세요.**
⚠️ **위 목록에 없는 claim은 개선점에 포함하지 마세요.**
⚠️ **정확한 정보 목록에 있는 claim과 부정확한 정보 목록에 있는 claim이 겹치면 안 됩니다.**
"""
                        else:
                            errors_section = """
⚠️ **부정확한 정보: 없음**
→ 개선점 섹션은 생략하거나 "제공한 모든 상품 정보가 정확합니다"와 같이 간단히 언급하세요.
"""
                        
                        product_accuracy_info = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔍 **제품 지식 자동 검증 결과** (객관적 데이터 - 반드시 정확히 반영하세요)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- 총 제품 정보 언급: {total_claims}개
- 정확한 정보: {accurate_claims}개
- 부정확한 정보: {inaccurate_claims}개
- 정확도: {accuracy_rate:.1%}
- 검증 방법: {knowledge_verification_result.get('verification_methods', {})}

{accurate_section}
{errors_section}
{reasoning_section}
💡 **지식 점수 평가 및 피드백 작성 가이드:**
- 정확도 {accuracy_rate:.1%} → 기본 점수 {int(accuracy_rate * 100)}점 (오류는 이미 정확도에 반영됨)
- ⚠️ 오류 개수는 점수 계산에 사용하지 말고, 피드백 작성 시에만 참고하세요
- ⚠️ 불확실한 표현("같아요", "모르겠" 등)은 전달력(자신감) 평가에서 다루므로 지식 점수에는 반영하지 않습니다
- ⚠️ **표현의 명확성(단위 명시 등)은 전달력에서 평가하므로, 지식 피드백에서는 상품 정보의 정확성만 언급하세요**

🚨 **중요 규칙 (반드시 준수):**
1. **정확한 정보 목록에 있는 claim은 반드시 잘한 점에만 언급하고, 개선점에 절대 포함하지 마세요.**
2. **부정확한 정보 목록에 있는 claim만 개선점에 언급하세요.**
3. **같은 claim이 잘한 점과 개선점에 동시에 나타나면 안 됩니다. (모순 금지)**
4. **실제 대화 내용을 정확히 참조하세요. 대화에서 "100만원"이라고 정확히 말했다면, "최소 100"이라는 오류로 인식하지 마세요.**
5. **제품 지식 자동 검증 결과가 정확한 정보로 판단했다면, 그것을 신뢰하고 잘한 점에 언급하세요.**
"""
                    else:
                        product_accuracy_info = """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔍 **제품 지식 자동 검증 결과**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- 구체적인 제품 정보 언급 없음 (금리, 한도 등 수치 정보 부재)
- 지식 점수는 일반적인 설명의 질로만 평가
"""
                    
                    # 일반 모드와 동일한 방식으로 지식 평가서 생성 (검증용)
                    # 실제로는 LLM을 호출하지 않고 검증 결과만 반환하지만,
                    # 일반 모드와 동일한 구조로 평가서 항목 생성 가능 여부 확인
                    knowledge_evaluation_result = {
                        "accuracy_rate": accuracy_rate,
                        "knowledge_score": int(accuracy_rate * 100),  # 일반 모드와 동일한 점수 산정
                        "total_claims": total_claims,
                        "accurate_claims": accurate_claims,
                        "inaccurate_claims": inaccurate_claims,
                        "product_accuracy_info": product_accuracy_info,
                        "verifications": knowledge_verification_result.get('verifications', [])
                    }
                    
                    # 🆕 각 turn의 RAG 평가 결과에 해당 turn의 claim 검증 결과 매핑
                    rag_evaluations = session_data.get("rag_evaluations", [])
                    if rag_evaluations and knowledge_verification_result:
                        # 각 RAG 평가 결과에 해당 turn의 발화 텍스트로 claim 검증 결과 필터링
                        for rag_eval in rag_evaluations:
                            if rag_eval.get("role") != "employee":
                                continue
                                
                            turn_index = rag_eval.get("turn_index")
                            # 해당 turn의 발화 텍스트 찾기
                            turn_text = None
                            test_scenario = session_data.get("test_scenario", {})
                            turns = test_scenario.get("turns", [])
                            if turn_index < len(turns):
                                # 실제 발화는 conversation_history에서 찾기
                                employee_utterance_count = 0
                                for msg in conversation_history:
                                    if msg.get("role") == "employee":
                                        if employee_utterance_count == turn_index:
                                            turn_text = msg.get("text", "")
                                            break
                                        employee_utterance_count += 1
                            
                            if turn_text:
                                # 해당 turn의 발화 텍스트와 일치하는 claim 검증 결과 필터링
                                turn_verifications = []
                                for v in knowledge_verification_result.get('verifications', []):
                                    full_utterance = getattr(v, 'full_utterance', None) or getattr(v, 'utterance', None)
                                    if full_utterance and turn_text in full_utterance:
                                        turn_verifications.append(v)
                                
                                if turn_verifications:
                                    # 해당 turn의 claim 검증 결과를 RAG 평가 결과에 추가
                                    rag_eval["evaluation"]["claim_verifications"] = [
                                        {
                                            "claim": v.claim,
                                            "is_accurate": v.is_accurate,
                                            "ground_truth": getattr(v, 'ground_truth', None),
                                            "similarity": getattr(v, 'similarity', None),
                                            "verification_method": getattr(v, 'verification_method', None),
                                            "llm_reasoning": getattr(v, 'llm_reasoning', None)
                                        }
                                        for v in turn_verifications
                                    ]
                                    print(f"🧪 ✅ 턴 {turn_index}의 RAG 평가에 {len(turn_verifications)}개 claim 검증 결과 추가")
                                else:
                                    print(f"🧪 ⚠️ 턴 {turn_index}의 발화에서 claim 검증 결과를 찾지 못했습니다.")
                    
                except Exception as e:
                    print(f"🧪 ⚠️ 제품 지식 검증 실패: {e}")
                    import traceback
                    traceback.print_exc()
                    product_accuracy_info = ""
            
            elif not has_product_data:
                # 외환/송금 상담 등 상품 데이터가 없는 경우
                product_accuracy_info = """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔍 **지식 평가 방식** (상품 데이터 없음)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- 제품별 정확도 검증 불가 (상품 데이터 파일 없음)
- 지식 점수는 다음 기준으로 평가:
  ✓ 절차 설명의 정확성 (송금 절차, 수수료 안내 등)
  ✓ 일반적인 금융 지식의 정확성
  ✓ 금융 규정 및 정책 이해도
  ✓ 고객 질문에 대한 적절한 답변 제공
- 구체적인 수치 정보(환율, 수수료 등)의 정확성은 LLM이 일반 지식으로 평가
"""
            
            return {
                "transcribed_text": "",
                "customer_response": "",
                "customer_audio": None,
                "feedback": "테스트 시나리오가 완료되었습니다.",
                "conversation_phase": "completed",
                "session_score": 0,
                "conversation_history": conversation_history,
                "end_signal": True,
                "stt_evaluation": stt_evaluation_result,  # 턴별 STT 평가 결과
                "knowledge_verification_result": knowledge_verification_result,  # 일반 모드와 동일한 검증 결과
                "knowledge_evaluation_result": knowledge_evaluation_result,  # 지식 평가서 항목 (검증용)
                "product_accuracy_info": product_accuracy_info,  # LLM 프롬프트용 정보 (일반 모드와 동일)
                "test_completed": True
            }
        
        current_turn = turns[current_turn_index]
        print(f"🧪 현재 턴: {current_turn.get('role')} - {current_turn.get('expected_text', '')[:50]}...")
        
        # STT 처리
        if not user_message:
            transcribed_text = self._speech_to_text(audio_data) if audio_data else ""
        else:
            transcribed_text = user_message
        
        print(f"🧪 ===== 테스트 모드 턴 처리 시작 ======")
        print(f"🧪 current_turn_index: {current_turn_index}")
        print(f"🧪 current_turn role: {current_turn.get('role')}")
        print(f"🧪 current_turn expected_text: {current_turn.get('expected_text', '')[:50]}...")
        print(f"🧪 STT 결과: {transcribed_text}")
        print(f"🧪 conversation_history 현재 길이: {len(conversation_history)}")
        
        # STT 평가 (고객 발화인 경우)
        if current_turn["role"] == "customer":
            expected_text = current_turn.get("expected_text", "")
            expected_product_code = current_turn.get("product_code")
            expected_keywords = current_turn.get("keywords", [])
            
            # 1. STT 평가 (금융 용어 인식 정확도)
            stt_eval = self._evaluate_single_stt(transcribed_text, expected_text, expected_keywords)
            stt_evaluations.append(stt_eval)
            
            # 2. 고객 발화는 STT 평가만 수행 (지식 평가는 대화 종료 후 직원 발화만 평가)
            # 테스트 모드 목적: STT 검증 + 지식 파트 점수 산정 로직 검증
            # 지식 평가는 일반 모드와 동일하게 대화 종료 후 batch_verify_conversation()으로 수행
            
            # 🧪 테스트 모드: 고객 발화는 정해진 스크립트로 자동 생성
            # STT로 받은 텍스트는 평가용으로만 사용하고, 실제 고객 응답은 expected_text 사용
            customer_response_text = expected_text  # 정해진 고객 응답 사용
            
            # 고객 발화를 히스토리에 추가 (정해진 스크립트 사용)
            conversation_history.append({
                "role": "customer",
                "text": customer_response_text,  # 정해진 스크립트 사용
                "timestamp": datetime.now().isoformat()
            })
            
            # 고객 응답을 TTS로 변환
            print(f"🧪 고객 응답 TTS 생성: {customer_response_text[:50]}...")
            # 세션 데이터에서 persona 가져오기
            persona = session_data.get("persona", {})
            customer_audio = self._text_to_speech(customer_response_text, persona)
            print(f"🧪 고객 응답 TTS 완료")
            
            # 다음 턴으로 이동 (직원 응답은 사용자가 따라 말해야 함)
            next_turn_index = current_turn_index + 1
            if next_turn_index < len(turns):
                next_turn = turns[next_turn_index]
                if next_turn["role"] == "employee":
                    # 테스트 모드에서는 직원 응답을 자동 생성하지 않고, 사용자가 따라 말하도록 함
                    # 다음 턴의 expected_text를 반환하여 프론트엔드에 표시
                    next_expected_text = next_turn.get("expected_text", "")
                    print(f"🧪 고객 발화 완료. 다음 턴(직원): {next_expected_text[:50]}...")
                    print(f"🧪 고객 응답은 정해진 스크립트로 자동 생성됨")
                    
                    print(f"🧪 ✅ 고객 발화 처리 완료")
                    return {
                        "transcribed_text": transcribed_text,  # STT 결과 (평가용)
                        "customer_response": customer_response_text,  # 🧪 정해진 고객 응답
                        "customer_audio": customer_audio,  # 🧪 고객 응답 TTS
                        "feedback": f"STT 정확도: {stt_eval['accuracy']:.1f}%",
                        "conversation_phase": "ongoing",
                        "session_score": 0,
                        "conversation_history": conversation_history,
                        "current_turn_index": next_turn_index,  # 다음 턴(직원 응답)으로 이동
                        "stt_evaluations": stt_evaluations,
                        "stt_evaluation": stt_eval,
                        "next_turn_expected_text": next_expected_text,  # 다음 턴의 기대 텍스트 (직원 응답)
                        "next_turn_role": "employee",  # 다음 턴 역할
                        "is_test_mode": True  # 🧪 테스트 모드 플래그 명시
                    }
        
        # 직원 발화인 경우 (STT 평가 + RAG 연동 평가)
        if current_turn["role"] == "employee":
            expected_text = current_turn.get("expected_text", "")
            expected_product_code = current_turn.get("product_code")
            expected_keywords = current_turn.get("keywords", [])
            
            # 1. STT 평가 (직원 발화의 금융 용어 인식 정확도)
            stt_eval = self._evaluate_single_stt(transcribed_text, expected_text, expected_keywords)
            stt_evaluations.append(stt_eval)
            
            # 2. 직원 발화는 STT 평가만 수행 (지식 평가는 대화 종료 후 일괄 수행)
            # 테스트 모드 목적: STT 검증 + 지식 파트 점수 산정 로직 검증
            # 지식 평가는 일반 모드와 동일하게 대화 종료 후 batch_verify_conversation()으로 수행
            
            # 🧪 직원 발화를 conversation_history에 추가 (프론트엔드에서도 동일하게 표시되도록)
            # 중요: 프론트엔드에서 role='user'로 표시되므로, 여기서는 'employee'로 저장
            conversation_history.append({
                "role": "employee",
                "text": transcribed_text,
                "timestamp": datetime.now().isoformat()
            })
            print(f"🧪 직원 발화를 conversation_history에 추가: {transcribed_text[:50]}...")
            print(f"🧪 conversation_history 길이: {len(conversation_history)}")
            
            # 다음 턴으로 이동
            next_turn_index = current_turn_index + 1
            next_turn_expected_text = ""
            customer_response_text = ""
            customer_audio = None
            
            # 🧪 테스트 모드: 다음 턴이 고객이면 자동으로 고객 응답 생성
            if next_turn_index < len(turns):
                next_turn = turns[next_turn_index]
                if next_turn.get("role") == "customer":
                    # 고객 응답 자동 생성
                    customer_response_text = next_turn.get("expected_text", "")
                    print(f"🧪 직원 발화 완료. 다음 턴(고객) 자동 생성: {customer_response_text[:50]}...")
                    
                    # 고객 응답을 히스토리에 추가
                    conversation_history.append({
                        "role": "customer",
                        "text": customer_response_text,
                        "timestamp": datetime.now().isoformat()
                    })
                    
                    # 고객 응답 TTS 생성
                    persona = session_data.get("persona", {})
                    customer_audio = self._text_to_speech(customer_response_text, persona)
                    print(f"🧪 고객 응답 TTS 완료")
                    
                    # 그 다음 턴(직원)의 expected_text 가져오기
                    next_next_turn_index = next_turn_index + 1
                    if next_next_turn_index < len(turns):
                        next_next_turn = turns[next_next_turn_index]
                        if next_next_turn.get("role") == "employee":
                            next_turn_expected_text = next_next_turn.get("expected_text", "")
                            next_turn_index = next_next_turn_index  # 직원 턴으로 이동
                elif next_turn.get("role") == "employee":
                    next_turn_expected_text = next_turn.get("expected_text", "")
            
            # 🧪 테스트 모드: 모든 턴이 끝난 후에만 종료 트리거 체크
            # 다음 턴이 없고 (모든 테스트 대화 완료), 직원 발화에 종료 트리거가 있으면 종료
            all_turns_completed = next_turn_index >= len(turns)
            employee_has_closing_trigger = any(
                trigger in transcribed_text for trigger in END_CONVERSATION_TRIGGERS
            )
            
            if all_turns_completed and employee_has_closing_trigger:
                # 모든 테스트 대화가 끝나고 종료 트리거가 감지되면 종료
                # 일반 모드와 동일한 지식 평가 수행 (위의 if current_turn_index >= len(turns) 블록과 동일)
                print(f"🧪 테스트 모드: 모든 턴 완료 + 종료 트리거 감지 - 시뮬레이션 종료")
                # 지식 평가는 위의 if current_turn_index >= len(turns) 블록에서 수행되므로
                # 여기서는 단순히 종료 신호만 반환 (실제로는 위 블록이 먼저 실행됨)
                return {
                    "transcribed_text": transcribed_text,
                    "customer_response": "",
                    "customer_audio": None,
                    "feedback": "테스트 시나리오가 완료되었습니다.",
                    "conversation_phase": "completed",
                    "session_score": 0,
                    "conversation_history": conversation_history,
                    "end_signal": True,
                    "stt_evaluation": self._evaluate_stt_performance(stt_evaluations),
                    "test_completed": True
                }
            
            print(f"🧪 직원 발화 완료. 다음 턴: {next_turn_expected_text[:50] if next_turn_expected_text else '없음'}...")
            if customer_response_text:
                print(f"🧪 고객 응답 자동 생성됨: {customer_response_text[:50]}...")
            else:
                print(f"🧪 customer_response는 빈 문자열로 반환 (다음 턴이 직원)")
            
            print(f"🧪 ✅ 직원 발화 처리 완료")
            
            # 다음 턴 역할 결정
            next_role = None
            if next_turn_index < len(turns):
                next_role = turns[next_turn_index].get("role")
            
            return {
                "transcribed_text": transcribed_text,
                "customer_response": customer_response_text,  # 🧪 다음 턴이 고객이면 자동 생성, 아니면 빈 문자열
                "customer_audio": customer_audio,  # 🧪 다음 턴이 고객이면 TTS 생성, 아니면 None
                "feedback": f"STT 정확도: {stt_eval['accuracy']:.1f}%",
                "conversation_phase": "ongoing",
                "session_score": 0,
                "conversation_history": conversation_history,
                "current_turn_index": next_turn_index,
                "stt_evaluations": stt_evaluations,
                "stt_evaluation": stt_eval,
                "next_turn_expected_text": next_turn_expected_text,  # 다음 턴의 기대 텍스트 (직원 응답)
                "next_turn_role": next_role,  # 다음 턴 역할
                "is_test_mode": True,  # 🧪 테스트 모드 플래그 명시
                "end_signal": False  # 테스트 대화가 모두 끝나지 않았으면 종료 안 함
            }
        
        return {
            "transcribed_text": transcribed_text,
            "customer_response": "",
            "customer_audio": None,
            "feedback": "처리 완료",
            "conversation_phase": "ongoing",
            "session_score": 0,
            "conversation_history": conversation_history
        }
    
    def _evaluate_single_stt(self, transcribed: str, expected: str, keywords: List[str]) -> Dict:
        """단일 STT 결과 평가"""
        from difflib import SequenceMatcher
        accuracy = SequenceMatcher(None, transcribed, expected).ratio() * 100
        
        recognized_keywords = [kw for kw in keywords if kw in transcribed]
        keyword_recognition_rate = (len(recognized_keywords) / len(keywords) * 100) if keywords else 100
        
        return {
            "transcribed": transcribed,
            "expected": expected,
            "accuracy": accuracy,
            "keyword_recognition_rate": keyword_recognition_rate,
            "recognized_keywords": recognized_keywords,
            "missing_keywords": [kw for kw in keywords if kw not in transcribed]
        }
    
    def _evaluate_stt_performance(self, stt_evaluations: List[Dict]) -> Dict:
        """전체 STT 성능 평가"""
        if not stt_evaluations:
            return {
                "overall_accuracy": 0,
                "average_keyword_recognition": 0,
                "total_evaluations": 0
            }
        
        avg_accuracy = sum(eval["accuracy"] for eval in stt_evaluations) / len(stt_evaluations)
        avg_keyword_recognition = sum(eval["keyword_recognition_rate"] for eval in stt_evaluations) / len(stt_evaluations)
        
        return {
            "overall_accuracy": avg_accuracy,
            "average_keyword_recognition": avg_keyword_recognition,
            "total_evaluations": len(stt_evaluations),
            "detailed_evaluations": stt_evaluations
        }
    
    def _generate_test_employee_response(self, turn: Dict, customer_text: str, conversation_history: List[Dict]) -> str:
        """테스트 모드 직원 응답 생성 (RAG 활용)"""
        product_code = turn.get("product_code")
        expected_keywords = turn.get("keywords", [])
        
        if product_code:
            # RAG를 통한 상품 정보 검색
            try:
                product_info = self._search_product_info(product_code)
                if product_info:
                    return f"{product_info.get('summary', '')} {product_info.get('details', '')}"
            except Exception as e:
                print(f"RAG 검색 오류: {e}")
        
        return "네, 알겠습니다. 관련 정보를 안내해드리겠습니다."
    
    def _search_product_info(self, product_code: str) -> Optional[Dict]:
        """상품 정보 검색 (RAG)"""
        product_mapping = {
            "DEP-MMD": {
                "summary": "MMDA는 입출금이 자유로우면서도 높은 금리를 받을 수 있는 예금상품입니다.",
                "details": "최소 100만원부터 가입 가능하며, 잔액에 따라 차등 금리가 적용됩니다."
            },
            "LON-MTG": {
                "summary": "주택담보대출은 주택을 담보로 제공하여 대출받는 상품입니다.",
                "details": "LTV(담보인정비율)는 일반지역 70%, DTI(총부채상환비율)는 60%까지 가능합니다."
            },
            "LON-DCL": {
                "summary": "예금담보대출은 예금을 담보로 제공하여 초저금리로 대출받는 상품입니다.",
                "details": "예금잔액의 95%까지 대출 가능하며, 수취은행과 무관하게 본행 예금만 가능합니다."
            }
        }
        return product_mapping.get(product_code)
    
    def _load_product_data(self, product_code: str) -> List[Dict]:
        """상품 코드에 해당하는 실제 상품 데이터 로드"""
        try:
            product_file = self.data_path / "rag_sources" / "products" / "hakyung" / f"{product_code}.jsonl"
            if not product_file.exists():
                print(f"⚠️ 상품 데이터 파일을 찾을 수 없습니다: {product_file}")
                return []
            
            product_data = []
            with open(product_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            product_data.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
            
            print(f"✅ 상품 데이터 로드 완료: {product_code} ({len(product_data)}개 청크)")
            return product_data
        except Exception as e:
            print(f"❌ 상품 데이터 로드 실패: {e}")
            return []
    
    def _extract_product_evidence(self, product_code: str, text: str, product_data: List[Dict]) -> Dict:
        """
        상품 데이터에서 평가 근거 추출
        
        **개선: 벡터 검색 및 유사도 판별 추가**
        - ProductKnowledgeService의 search_by_keyword() 사용
        - 의미적 유사도 계산 (임베딩 기반)
        - 유사도 점수 기반 정렬
        
        **프로세스:**
        1. ProductKnowledgeService로 벡터 검색 수행
        2. 유사도 점수 계산
        3. 유사도 높은 순으로 정렬
        4. 관련 청크 반환
        """
        evidence = {
            "matched_chunks": [],
            "key_information": [],
            "missing_information": [],
            "similarity_scores": []  # 유사도 점수 추가
        }
        
        if not product_data:
            return evidence
        
        # 🎯 ProductKnowledgeService 사용 (벡터 검색 우선, 실패 시 키워드 fallback)
        if self.product_knowledge_service:
            try:
                # 1단계: 벡터 검색 우선 수행 (pgvector 사용)
                # 유사도 임계값을 낮춰서 더 많은 결과를 찾을 수 있도록 조정 (0.5 → 0.3)
                print(f"🔍 [벡터 검색 시작] query='{text[:100]}...', product_code={product_code}")
                relevant_chunks = self.product_knowledge_service.search_by_vector_similarity(
                    query=text,
                    category=None,
                    product_codes=[product_code],
                    top_k=5,
                    similarity_threshold=0.3  # 0.5에서 0.3으로 낮춤 (진단 결과: 0.3에서는 결과가 나옴)
                )
                
                # 벡터 검색 결과 확인
                if not relevant_chunks:
                    # 벡터 검색 결과가 아예 없음
                    print(f"⚠️ [벡터 검색] 결과 없음 (빈 리스트 반환), 키워드 매칭으로 fallback")
                    fallback_evidence = self._extract_product_evidence_keyword_fallback(product_code, text, product_data)
                    fallback_evidence["error"] = "vector_no_results"
                    fallback_evidence["error_detail"] = "벡터 검색 결과가 없습니다. 키워드 매칭 fallback 사용됨."
                    print(f"  📝 fallback 결과: {len(fallback_evidence.get('matched_chunks', []))}개 청크 발견")
                    return fallback_evidence
                
                # 2단계: 근거 청크 구성
                # 벡터 검색에서 이미 유사도 필터링을 했으므로, 여기서는 추가 필터링 없이 사용
                # (벡터 검색에서 0.3 이상만 반환되므로, 여기서 다시 0.5로 필터링하면 결과가 없을 수 있음)
                print(f"🔍 [벡터 검색 후처리] {len(relevant_chunks)}개 청크 수신, 유사도 필터링 없이 모두 사용")
                
                processed_count = 0
                for i, chunk in enumerate(relevant_chunks):
                    chunk_text = chunk.get("text") or chunk.get("content", "")
                    if not chunk_text:
                        print(f"  ⚠️ 청크 {i+1}: 텍스트 없음, 건너뜀")
                        continue
                    
                    # 벡터 검색 결과에 similarity가 있으면 사용
                    similarity = chunk.get("similarity")
                    if similarity is None:
                        print(f"  🔍 청크 {i+1}: similarity 없음, 계산 중...")
                        # similarity가 없으면 계산
                        similarity = self.product_knowledge_service._semantic_similarity(
                            text,  # 직원 발화
                            chunk_text  # 상품 데이터 청크
                        )
                        print(f"  📊 청크 {i+1}: 계산된 유사도={similarity:.3f}")
                    else:
                        print(f"  📊 청크 {i+1}: 벡터 검색 유사도={similarity:.3f}")
                    
                    # 벡터 검색에서 이미 유사도 필터링을 했으므로, 여기서는 모든 결과 사용
                    # (추가 필터링 제거: 벡터 검색에서 0.3 이상만 반환되므로)
                    evidence["matched_chunks"].append({
                        "subsection_title": chunk.get("subsection_title", ""),
                        "text": chunk_text[:200] + "..." if len(chunk_text) > 200 else chunk_text,
                        "breadcrumb": chunk.get("breadcrumb", ""),
                        "similarity": round(similarity, 3)  # 유사도 점수 추가
                    })
                    evidence["similarity_scores"].append(similarity)
                    processed_count += 1
                
                print(f"🔍 [벡터 검색 후처리] 완료: {processed_count}개 청크 처리됨")
                
                # 벡터 검색 결과가 있는 경우
                if evidence["similarity_scores"]:
                    avg_similarity = sum(evidence["similarity_scores"]) / len(evidence["similarity_scores"])
                    print(f"✅ 벡터 검색 완료: {len(evidence['matched_chunks'])}개 청크 발견 (평균 유사도: {avg_similarity:.3f})")
                    
                    # 키워드 정보도 함께 제공 (참고용)
                    key_info_keywords = self._get_key_info_keywords()
                    relevant_keywords = key_info_keywords.get(product_code, [])
                    found_keywords_in_text = [kw for kw in relevant_keywords if kw in text]
                    missing_keywords = [kw for kw in relevant_keywords if kw not in text]
                    
                    evidence["key_information"] = found_keywords_in_text
                    evidence["missing_information"] = missing_keywords
                    
                    return evidence
                else:
                    # 벡터 검색 결과가 없으면 키워드 매칭으로 fallback
                    print(f"⚠️ [벡터 검색] 결과 없음: 유사도 점수가 없거나 0, 키워드 매칭으로 fallback")
                    fallback_evidence = self._extract_product_evidence_keyword_fallback(product_code, text, product_data)
                    # 벡터 검색 실패 정보 추가
                    fallback_evidence["error"] = "vector_no_results"
                    fallback_evidence["error_detail"] = f"벡터 검색 결과가 없거나 유사도 임계값(0.3) 미달. 키워드 매칭 fallback 사용됨."
                    print(f"  📝 fallback 결과: {len(fallback_evidence.get('matched_chunks', []))}개 청크 발견")
                    return fallback_evidence
                
            except Exception as e:
                print(f"⚠️ 벡터 검색 실패, 키워드 매칭으로 fallback: {e}")
                import traceback
                traceback.print_exc()
                # Fallback: 기존 키워드 매칭 로직
                fallback_evidence = self._extract_product_evidence_keyword_fallback(product_code, text, product_data)
                # 벡터 검색 실패 정보 추가
                fallback_evidence["error"] = "vector_search_error"
                fallback_evidence["error_detail"] = f"벡터 검색 중 오류 발생: {str(e)}. 키워드 매칭 fallback 사용됨."
                print(f"  📝 fallback 결과: {len(fallback_evidence.get('matched_chunks', []))}개 청크 발견")
                return fallback_evidence
        
        # ProductKnowledgeService 없으면 기존 로직 사용
        return self._extract_product_evidence_keyword_fallback(product_code, text, product_data)
    
    def _extract_product_evidence_keyword_fallback(self, product_code: str, text: str, product_data: List[Dict]) -> Dict:
        """키워드 매칭 기반 근거 추출 (fallback)"""
        evidence = {
            "matched_chunks": [],
            "key_information": [],
            "missing_information": []
        }
        
        if not product_data:
            return evidence
        
        # 상품별 핵심 정보 키워드
        key_info_keywords = self._get_key_info_keywords()
        relevant_keywords = key_info_keywords.get(product_code, [])
        
        # 텍스트에서 찾은 키워드
        found_keywords_in_text = [kw for kw in relevant_keywords if kw in text]
        missing_keywords = [kw for kw in relevant_keywords if kw not in text]
        
        # 상품 데이터에서 관련 청크 찾기 (단순 키워드 매칭)
        for chunk in product_data:
            chunk_text = chunk.get("text", "")
            for keyword in found_keywords_in_text:
                if keyword in chunk_text:
                    evidence["matched_chunks"].append({
                        "subsection_title": chunk.get("subsection_title", ""),
                        "text": chunk_text[:200] + "..." if len(chunk_text) > 200 else chunk_text,
                        "breadcrumb": chunk.get("breadcrumb", "")
                    })
                    break
        
        evidence["key_information"] = found_keywords_in_text
        evidence["missing_information"] = missing_keywords
        
        return evidence
    
    def _evaluate_rag_integration(self, text: str, expected_product_code: Optional[str], expected_keywords: List[str], role: str = "employee") -> Dict:
        """
        RAG 연동 평가 - 피드백 생성과 동일한 batch_verify_conversation() 로직 사용
        
        🎯 유지보수 관점에서 피드백 생성과 동일한 로직을 사용하여:
        - 테스트 결과가 실제 피드백과 일치
        - 하나의 로직만 수정하면 둘 다 적용
        - claim 단위 검증으로 벡터 검색 실패 시에도 정확성 평가 가능
        
        Args:
            text: 평가할 발화 텍스트 (고객 또는 직원)
            expected_product_code: 참고용 예상 제품 코드 (테스트 시나리오)
            expected_keywords: STT 인식률 확인용 키워드 (테스트 시나리오)
            role: 발화 역할 ("employee" 또는 "customer"), 기본값은 "employee"
        """
        score = 0
        max_score = 100
        
        # 변수 초기화
        keyword_score = 0
        product_score = 0
        product_evidence = None
        extracted_product_codes = set()
        extracted_categories = set()
        extracted_claims = []
        claim_verifications = []
        
        # 🎯 피드백 생성과 동일한 로직: batch_verify_conversation() 사용
        if self.product_knowledge_service:
            # 대화 히스토리 구성
            conversation = [{"role": role, "text": text}]
            
            # 1. 키워드 매칭 점수 (50점) - STT 인식률 확인용
            if expected_keywords:
                found_keywords = [kw for kw in expected_keywords if kw in text]
                keyword_score = (len(found_keywords) / len(expected_keywords)) * 50 if expected_keywords else 0
                missing_keywords = [kw for kw in expected_keywords if kw not in text]
            else:
                found_keywords = []
                missing_keywords = []
            
            # 2. RAG 상품 정보 정확도 검증 (50점) - batch_verify_conversation() 사용
            try:
                # 피드백 생성과 동일한 방식으로 claim 추출 및 검증
                # 🧪 테스트 모드에서는 LLM 기반 product_code 추출 강제 활성화
                # use_llm: LLM 기반 사실 검증 사용 여부
                use_llm_extraction = True  # 테스트 모드에서는 항상 LLM 추출 사용
                verification_result = self.product_knowledge_service.batch_verify_conversation(
                    conversation,
                    use_llm=True,  # LLM 검증 포함
                    use_llm_extraction=use_llm_extraction  # LLM 기반 추출 (설정 파일에서 제어)
                )
                
                # 검증 결과에서 정보 추출
                total_claims = verification_result.get('total_claims', 0)
                accurate_claims = verification_result.get('accurate_claims', 0)
                accuracy_rate = verification_result.get('accuracy_rate', 0.0)
                verifications = verification_result.get('verifications', [])
                
                # 추출된 제품 코드 및 카테고리 수집
                for v in verifications:
                    if hasattr(v, 'product_code') and v.product_code:
                        extracted_product_codes.add(v.product_code)
                    if hasattr(v, 'category') and v.category:
                        extracted_categories.add(v.category)
                    if hasattr(v, 'claim') and v.claim:
                        extracted_claims.append(v.claim)
                
                # RAG 상품 정보 점수: 검증 정확도 기반 (50점 만점)
                product_score = accuracy_rate * 50
                
                # claim 검증 결과 수집 (프론트엔드 표시용)
                claim_verifications = [
                    {
                        "claim": v.claim,
                        "is_accurate": v.is_accurate,
                        "ground_truth": getattr(v, 'ground_truth', None),
                        "similarity": getattr(v, 'similarity', None),
                        "verification_method": getattr(v, 'verification_method', None),
                        "llm_reasoning": getattr(v, 'llm_reasoning', None)
                    }
                    for v in verifications
                ]
                
                # 벡터 검색 결과 수집 (product_evidence 구성)
                # 🆕 개선: 여러 상품을 한 번에 검색하여 성능 향상
                matched_chunks = []
                similarity_scores = []
                all_vector_chunks = set()  # 중복 제거용
                
                # 🆕 fact별로 그룹화하여 여러 상품을 한 번에 검색
                fact_groups = {}  # {claim: [product_codes]}
                for v in verifications:
                    if hasattr(v, 'claim') and v.claim:
                        claim = v.claim
                        product_code = getattr(v, 'product_code', None)
                        
                        if claim not in fact_groups:
                            fact_groups[claim] = []
                        if product_code and product_code not in fact_groups[claim]:
                            fact_groups[claim].append(product_code)
                
                # 🔍 디버깅: fact_groups 로그 출력
                print(f"🔍 [벡터 검색] fact_groups: {len(fact_groups)}개 claim 그룹")
                for claim, product_codes in fact_groups.items():
                    print(f"  - claim: {claim[:50]}... → product_codes: {product_codes}")
                
                # 각 claim에 대해 여러 상품을 한 번에 검색
                for claim, product_codes in fact_groups.items():
                    if not product_codes:
                        print(f"⚠️ [벡터 검색] 건너뜀: product_codes가 비어있음 (claim: {claim[:50]}...)")
                        continue
                    
                    # UNKNOWN 제외 (벡터 검색 불가)
                    valid_product_codes = [code for code in product_codes if code != "UNKNOWN"]
                    if not valid_product_codes:
                        print(f"⚠️ [벡터 검색] 건너뜀: 유효한 상품 코드 없음 (모두 UNKNOWN) (claim: {claim[:50]}...)")
                        continue
                    
                    # 🆕 여러 상품을 한 번에 검색 (성능 향상)
                    print(f"🔍 [벡터 검색] 시작: claim='{claim[:50]}...', product_codes={valid_product_codes}")
                    vector_results = self.product_knowledge_service.search_by_vector_similarity(
                        query=claim,
                        category=None,
                        product_codes=valid_product_codes,  # 여러 상품 코드 리스트 (UNKNOWN 제외)
                        top_k=3,
                        similarity_threshold=0.5
                    )
                    print(f"🔍 [벡터 검색] 결과: {len(vector_results)}개 청크 발견")
                    
                    for chunk in vector_results[:3]:  # Top 3만 수집
                            chunk_text = chunk.get("text") or chunk.get("content", "")
                            chunk_id = f"{chunk.get('subsection_title', '')}_{chunk_text[:50]}"
                            
                            if chunk_id not in all_vector_chunks and chunk_text:
                                all_vector_chunks.add(chunk_id)
                                similarity = chunk.get("similarity", 0.0)
                                
                                matched_chunks.append({
                                    "subsection_title": chunk.get("subsection_title", ""),
                                    "text": chunk_text[:200] + "..." if len(chunk_text) > 200 else chunk_text,
                                    "breadcrumb": chunk.get("breadcrumb", ""),
                                "product_code": chunk.get("product_code", ""),  # 🆕 상품 코드 정보 추가
                                    "similarity": round(similarity, 3)
                                })
                                similarity_scores.append(similarity)
                
                # product_evidence 구성
                product_evidence = {
                    "matched_chunks": matched_chunks[:5],  # 최대 5개만 표시
                    "similarity_scores": similarity_scores[:5],
                    "key_information": extracted_claims,  # 추출된 claim 목록
                    "missing_information": []  # claim 검증 결과에서 정확하지 않은 claim은 missing_information에 포함할 수 있음
                }
                
                # 벡터 검색 실패 여부 확인
                if not matched_chunks:
                    product_evidence["error"] = "vector_no_results"
                    product_evidence["error_detail"] = "벡터 검색 결과가 없거나 유사도 임계값(0.5) 미달. claim 단위 검증은 LLM으로 수행됨."
                
                print(f"✅ RAG 평가 완료: {total_claims}개 claim, {accurate_claims}개 정확 ({accuracy_rate:.1%})")
                
            except Exception as e:
                print(f"⚠️ RAG 평가 실패: {e}")
                import traceback
                traceback.print_exc()
                product_score = 0
                product_evidence = {
                    "error": "evaluation_error",
                    "error_detail": f"RAG 평가 중 오류 발생: {str(e)}"
                }
            
            # 3. 총점 계산
            total_score = keyword_score + product_score
            
            # 4. 결과 반환 (피드백과 동일한 형식 유지)
            return {
                "score": total_score,
                "max_score": max_score,
                "keyword_score": keyword_score,
                "rag_product_info_score": product_score,
                "expected_product_code": expected_product_code,  # 참고용
                "extracted_product_code": list(extracted_product_codes)[0] if extracted_product_codes else None,  # 자동 추출된 제품 코드
                "extracted_product_codes": list(extracted_product_codes),  # 모든 추출된 제품 코드
                "extracted_categories": list(extracted_categories),  # 자동 추출된 카테고리
                "found_keywords": found_keywords,  # STT 인식된 키워드 (expected_keywords 기반)
                "expected_keywords": expected_keywords,  # 참고용 (테스트 시나리오)
                "missing_keywords": missing_keywords,  # STT 미인식 키워드
                "rag_info_keywords_found": extracted_claims,  # 추출된 claim 목록
                "claim_verifications": claim_verifications,  # 🆕 claim 검증 결과 (피드백과 동일)
                "product_evidence": product_evidence,  # 벡터 검색 결과 및 근거
                "extraction_method": "batch_verify_conversation"  # 피드백과 동일한 방법
            }
        else:
            # ProductKnowledgeService 없으면 기본값 반환
            return {
                "score": 0,
                "max_score": max_score,
                "keyword_score": 0,
                "rag_product_info_score": 0,
                "expected_product_code": expected_product_code,
                "extracted_product_code": None,
                "extracted_product_codes": [],
                "extracted_categories": [],
                "found_keywords": [],
                "expected_keywords": expected_keywords,
                "missing_keywords": expected_keywords if expected_keywords else [],
                "rag_info_keywords_found": [],
                "claim_verifications": [],
                "product_evidence": None,
                "extraction_method": "none"
            }
    
    def _filter_info_keywords_by_categories(self, info_keywords: List[str], categories: set, text: str = "") -> List[str]:
        """
        카테고리 기반으로 info_keywords 필터링
        
        **매칭 원리:**
        1. category_config.json의 subsection_keywords를 사용하여 카테고리와 관련된 키워드 확인
        2. info_keywords에서 해당 키워드가 포함된 항목만 필터링
        3. 예: "수수료" 카테고리 → subsection_keywords["수수료"] = ["수수료", "연회비", "중도상환", ...]
           → info_keywords에서 "연회비", "10,000원" 등이 포함된 키워드만 추출
        
        **명확한 매칭 규칙:**
        - info_keywords의 용어가 subsection_keywords의 키워드와 정확히 일치하거나
        - info_keywords의 용어에 subsection_keywords의 키워드가 포함되어 있으면 해당 카테고리로 분류
        - 예: "연회비" 키워드가 있으면 → "수수료" 카테고리
        - 예: "10,000원"은 숫자 제거 후 "원"만 남으므로 단독으로는 매칭 어려움
          → 하지만 직원 발화에 "연회비"가 함께 있으면 수수료 카테고리로 추출됨
        
        Args:
            info_keywords: 전체 info_keywords 리스트
            categories: 추출된 카테고리 집합 (예: {"수수료", "한도"})
            text: 직원 발화 텍스트 (카테고리 매칭 확인용, 선택적)
        
        Returns:
            필터링된 info_keywords 리스트 (빈 리스트면 카테고리와 관련된 키워드 없음)
        """
        if not categories or not info_keywords:
            return []
        
        # category_config.json 로드
        category_config_path = self.data_path / "category_config.json"
        if not category_config_path.exists():
            # category_config가 없으면 전체 키워드 반환 (하위 호환)
            return info_keywords
        
        try:
            with open(category_config_path, 'r', encoding='utf-8') as f:
                category_config = json.load(f)
            
            subsection_keywords = category_config.get("subsection_keywords", {})
        except Exception as e:
            print(f"⚠️ category_config 로드 실패: {e}")
            return info_keywords
        
        # 각 카테고리와 관련된 키워드 수집
        # 예: categories = {"수수료"} → subsection_keywords["수수료"] = ["수수료", "연회비", "중도상환", "중도해지"]
        category_related_keywords = set()
        for category in categories:
            if category in subsection_keywords:
                category_keywords = subsection_keywords[category]
                category_related_keywords.update(category_keywords)
        
        if not category_related_keywords:
            # 카테고리 키워드가 없으면 전체 반환
            return info_keywords
        
        # info_keywords에서 카테고리 관련 키워드가 포함된 것만 필터링
        filtered_keywords = []
        text_lower = text.lower() if text else ""
        
        for kw in info_keywords:
            kw_lower = kw.lower()
            
            # 방법 1: info_keywords의 용어가 subsection_keywords와 직접 매칭
            # 예: info_keywords에 "연회비"가 있으면 → "수수료" 카테고리 키워드와 매칭
            for cat_kw in category_related_keywords:
                cat_kw_lower = cat_kw.lower()
                # 정확 일치
                if kw_lower == cat_kw_lower:
                    filtered_keywords.append(kw)
                    break
                # 부분 포함 (카테고리 키워드가 info_keywords에 포함되거나 그 반대)
                if cat_kw_lower in kw_lower or kw_lower in cat_kw_lower:
                    filtered_keywords.append(kw)
                    break
            
            # 방법 2: 숫자 포함 키워드의 경우 (예: "10,000원", "1.0%")
            # 숫자 제거 후 남은 부분이 카테고리 키워드와 매칭되는지 확인
            if kw not in filtered_keywords:
                kw_without_numbers = re.sub(r'[\d,\.]+', '', kw_lower).strip()
                # 남은 부분이 의미 있는 단어인지 확인 (최소 2글자 이상)
                if len(kw_without_numbers) >= 2:
                    for cat_kw in category_related_keywords:
                        cat_kw_lower = cat_kw.lower()
                        if cat_kw_lower in kw_without_numbers or kw_without_numbers in cat_kw_lower:
                            filtered_keywords.append(kw)
                            break
            
            # 방법 3: 직원 발화에 카테고리 키워드가 있고, info_keywords의 수치/용어가 함께 언급된 경우
            # 예: 발화에 "연회비"가 있고 info_keywords에 "10,000원"이 있으면 → 수수료 카테고리
            if text and kw not in filtered_keywords:
                # info_keywords가 수치만 있는 경우 (예: "10,000원", "1.0%")
                if re.match(r'^[\d,\.%원]+$', kw):
                    # 발화에 해당 카테고리 키워드가 언급되어 있으면 포함
                    for cat_kw in category_related_keywords:
                        if cat_kw.lower() in text_lower:
                            filtered_keywords.append(kw)
                            break
        
        # 필터링된 키워드가 없으면 빈 리스트 반환 (전체 키워드 사용하지 않음)
        return filtered_keywords
    
    def _get_key_info_keywords(self) -> Dict[str, List[str]]:
        """상품 데이터 근거 추출용 키워드 가져오기 (캐시 우선, 없으면 하드코딩)"""
        if self.keyword_extractor:
            cached_keywords = {}
            # 캐시에서 모든 제품 키워드 가져오기
            cache = self.keyword_extractor.cache
            for product_code, keywords_data in cache.items():
                if keywords_data and keywords_data.get("info_keywords"):
                    cached_keywords[product_code] = keywords_data["info_keywords"]
            
            if cached_keywords:
                return cached_keywords
        
        # 하드코딩된 키워드 (fallback)
        return {
            "DEP-MMD": ["MMDA", "입출금", "금리", "예금", "100만원", "차등", "최소", "가입금액"],
            "LON-MTG": ["주택담보", "LTV", "DTI", "DSR", "담보인정비율", "70%", "60%", "규제"],
            "LON-DCL": ["예금담보", "수취은행", "담보", "95%", "예금잔액", "초저금리"]
        }
    
    def _get_product_keywords_map(self) -> Dict[str, List[str]]:
        """고객 발화 평가용 키워드 가져오기 (캐시 우선, 없으면 하드코딩)"""
        if self.keyword_extractor:
            cached_keywords = {}
            # 캐시에서 모든 제품 키워드 가져오기
            cache = self.keyword_extractor.cache
            for product_code, keywords_data in cache.items():
                if keywords_data and keywords_data.get("product_keywords"):
                    # product_keywords를 사용하되, 추가 키워드도 포함
                    cached_keywords[product_code] = keywords_data["product_keywords"].copy()
                    # info_keywords에서 일부 추가 (제품 특성 키워드)
                    if keywords_data.get("info_keywords"):
                        # 제품 특성 키워드만 추가 (수치 제외)
                        product_specific = [kw for kw in keywords_data["info_keywords"] 
                                         if not kw.replace("%", "").replace(",", "").replace("원", "").isdigit()
                                         and kw not in cached_keywords[product_code]]
                        cached_keywords[product_code].extend(product_specific)
            
            if cached_keywords:
                return cached_keywords
        
        # 하드코딩된 키워드 (fallback)
        return {
            "DEP-MMD": ["MMDA", "엠엠디에이", "입출금", "예금", "적금"],
            "LON-MTG": ["주택담보", "주택담보대출", "LTV", "DTI", "DSR", "담보"],
            "LON-DCL": ["예금담보", "예금담보대출", "수취은행", "담보"]
        }
    
    def _get_product_info_keywords(self) -> Dict[str, List[str]]:
        """RAG 평가용 제품 정보 키워드 가져오기 (캐시 우선, 없으면 하드코딩)"""
        if self.keyword_extractor:
            cached_keywords = {}
            # 캐시에서 모든 제품 키워드 가져오기
            cache = self.keyword_extractor.cache
            for product_code, keywords_data in cache.items():
                if keywords_data and keywords_data.get("info_keywords"):
                    cached_keywords[product_code] = keywords_data["info_keywords"]
            
            if cached_keywords:
                return cached_keywords
        
        # 하드코딩된 키워드 (fallback)
        return {
            "DEP-MMD": ["MMDA", "입출금", "금리", "예금", "100만원", "차등"],
            "LON-MTG": ["주택담보", "LTV", "DTI", "DSR", "담보인정비율", "70%", "60%"],
            "LON-DCL": ["예금담보", "수취은행", "담보", "95%", "예금잔액"]
        }
    
    def _summarize_rag_evaluations(self, rag_evaluations: List[Dict]) -> Dict:
        """RAG 평가 결과 종합"""
        if not rag_evaluations:
            return {
                "total_evaluations": 0,
                "average_score": 0,
                "employee_evaluations": [],
                "customer_evaluations": []
            }
        
        employee_evals = [e for e in rag_evaluations if e.get("role") == "employee"]
        customer_evals = [e for e in rag_evaluations if e.get("role") == "customer"]
        
        all_scores = [e["evaluation"]["score"] for e in rag_evaluations]
        avg_score = sum(all_scores) / len(all_scores) if all_scores else 0
        
        return {
            "total_evaluations": len(rag_evaluations),
            "average_score": avg_score,
            "employee_count": len(employee_evals),
            "customer_count": len(customer_evals),
            "employee_average": sum(e["evaluation"]["score"] for e in employee_evals) / len(employee_evals) if employee_evals else 0,
            "customer_average": sum(e["evaluation"]["score"] for e in customer_evals) / len(customer_evals) if customer_evals else 0,
            "employee_evaluations": employee_evals,
            "customer_evaluations": customer_evals
        }
