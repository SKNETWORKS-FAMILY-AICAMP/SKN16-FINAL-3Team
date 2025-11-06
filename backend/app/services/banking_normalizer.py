"""
은행용 의미 보정기 (Banking Normalizer)
STT 결과를 은행 도메인에 맞게 정규화하고 오인식을 교정합니다.
"""

import json
import re
from typing import Dict, List, Tuple, Any
from rapidfuzz import process, fuzz
from pydantic import BaseModel
import os

class NormalizeRequest(BaseModel):
    text: str
    confidence: float = 1.0  # Whisper confidence score

class NormalizeResponse(BaseModel):
    original: str
    normalized: str
    corrections: List[Tuple[str, str, str]]  # (original, corrected, method)
    confidence_score: float
    needs_clarification: bool
    extracted_entities: Dict[str, Any]

class BankingNormalizer:
    def __init__(self, domain_dict_path: str = "backend/data/banking_domain_dictionary.json"):
        """은행 도메인 사전을 로드하고 정규화기를 초기화합니다."""
        self.domain_dict = self._load_domain_dictionary(domain_dict_path)
        self.aliases = self.domain_dict["aliases"]
        self.stopwords = set(self.domain_dict["stopwords"])
        self.protect_words = set(self.domain_dict["protect"])
        self.numbers = self.domain_dict["numbers"]
        self.currencies = self.domain_dict["currencies"]
        self.time_periods = self.domain_dict["time_periods"]
        self.products = self.domain_dict["products"]
        
        # 정규화된 키워드 리스트 생성
        self.canonical_terms = list(self.aliases.keys())
        
        # 별칭 → 정규용어 매핑 생성
        self.alias_to_canonical = {}
        for canonical, aliases_list in self.aliases.items():
            for alias in aliases_list:
                self.alias_to_canonical[alias] = canonical
    
    def _load_domain_dictionary(self, path: str) -> Dict:
        """도메인 사전을 로드합니다."""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Warning: Domain dictionary not found at {path}")
            return self._get_default_dictionary()
    
    def _get_default_dictionary(self) -> Dict:
        """기본 도메인 사전을 반환합니다."""
        return {
            "aliases": {
                "정기예금": ["전기예금", "정기예굼"],
                "자유적금": ["자유 적금", "자유저금"],
                "입출금자유": ["자유예금", "입출금통장"]
            },
            "stopwords": ["그", "음", "어", "저기"],
            "protect": ["확정금리", "보장"],
            "numbers": {},
            "currencies": {},
            "time_periods": {},
            "products": {}
        }
    
    def normalize(self, text: str, confidence: float = 1.0) -> NormalizeResponse:
        """
        텍스트를 은행 도메인에 맞게 정규화합니다.
        
        Args:
            text: 원본 텍스트
            confidence: Whisper 신뢰도 점수
            
        Returns:
            NormalizeResponse: 정규화 결과
        """
        original_text = text.strip()
        
        # 1. 전처리: 불필요한 문자 제거 및 토큰화
        cleaned_text = self._preprocess_text(original_text)
        tokens = cleaned_text.split()
        
        # 2. 정규화 및 교정 수행
        normalized_tokens = []
        corrections = []
        
        for token in tokens:
            if token in self.stopwords:
                continue  # 불용어 제거
                
            # 별칭 매칭
            if token in self.alias_to_canonical:
                canonical = self.alias_to_canonical[token]
                normalized_tokens.append(canonical)
                if token != canonical:
                    corrections.append((token, canonical, "alias"))
                continue
            
            # 퍼지 매칭
            match_result = process.extractOne(
                token, 
                self.canonical_terms, 
                scorer=fuzz.WRatio,
                score_cutoff=85  # 임계값 조정 가능
            )
            
            if match_result:
                match_term, score, _ = match_result
                normalized_tokens.append(match_term)
                if token != match_term:
                    corrections.append((token, match_term, f"fuzzy:{score}"))
            else:
                normalized_tokens.append(token)
        
        # 3. 엔티티 추출
        extracted_entities = self._extract_entities(" ".join(normalized_tokens))
        
        # 4. 신뢰도 평가 및 재확인 필요성 판단
        needs_clarification = self._needs_clarification(
            corrections, confidence, len(original_text)
        )
        
        normalized_text = " ".join(normalized_tokens)
        
        return NormalizeResponse(
            original=original_text,
            normalized=normalized_text,
            corrections=corrections,
            confidence_score=confidence,
            needs_clarification=needs_clarification,
            extracted_entities=extracted_entities
        )
    
    def _preprocess_text(self, text: str) -> str:
        """텍스트 전처리를 수행합니다."""
        # 특수문자 정리
        text = re.sub(r'[^\w\s가-힣]', ' ', text)
        # 연속 공백 제거
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    def _extract_entities(self, text: str) -> Dict[str, Any]:
        """엔티티를 추출합니다."""
        entities = {
            "amounts": [],
            "currencies": [],
            "time_periods": [],
            "products": [],
            "numbers": []
        }
        
        # 금액 추출 (예: "100만원", "5천만원")
        amount_pattern = r'(\d+(?:,\d{3})*(?:\.\d+)?)\s*(만|천|억|조)?\s*(원|달러|엔|위안)?'
        amounts = re.findall(amount_pattern, text)
        for amount in amounts:
            entities["amounts"].append({
                "value": amount[0],
                "unit": amount[1] if amount[1] else "",
                "currency": amount[2] if amount[2] else "원"
            })
        
        # 상품명 추출
        for product_type, product_list in self.products.items():
            for product in product_list:
                if product in text:
                    entities["products"].append({
                        "name": product,
                        "category": product_type
                    })
        
        # 숫자 추출
        number_pattern = r'(\d+(?:,\d{3})*(?:\.\d+)?)'
        numbers = re.findall(number_pattern, text)
        entities["numbers"] = numbers
        
        return entities
    
    def _needs_clarification(self, corrections: List[Tuple], confidence: float, text_length: int) -> bool:
        """재확인이 필요한지 판단합니다."""
        # 교정이 많거나 신뢰도가 낮으면 재확인 필요
        if len(corrections) >= 2:
            return True
        if confidence < 0.7:
            return True
        if text_length > 50 and len(corrections) >= 1:
            return True
        return False
    
    def expand_query(self, normalized_text: str, catalog_hits: List[Dict] = None) -> List[str]:
        """검색 쿼리를 확장합니다."""
        expanded_terms = [normalized_text]
        
        # 카탈로그 히트가 있으면 관련 용어 추가
        if catalog_hits:
            for hit in catalog_hits:
                product_name = hit.get("product", "")
                if product_name in self.aliases:
                    expanded_terms.extend(self.aliases[product_name][:3])  # 상위 3개만
        
        # 상품 카테고리 관련 용어 추가
        for product_type, products in self.products.items():
            if any(product in normalized_text for product in products):
                expanded_terms.extend(products[:2])  # 해당 카테고리 상품 2개
        
        return list(set(expanded_terms))  # 중복 제거

# 전역 정규화기 인스턴스
normalizer = BankingNormalizer()

def normalize_text(text: str, confidence: float = 1.0) -> NormalizeResponse:
    """텍스트 정규화를 수행합니다."""
    return normalizer.normalize(text, confidence)

def expand_search_query(normalized_text: str, catalog_hits: List[Dict] = None) -> List[str]:
    """검색 쿼리를 확장합니다."""
    return normalizer.expand_query(normalized_text, catalog_hits)
