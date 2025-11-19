"""
은행용 의미 보정 API 엔드포인트
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any
from ..services.banking_normalizer import normalize_text, expand_search_query, NormalizeRequest, NormalizeResponse

router = APIRouter(prefix="/normalize", tags=["normalize"])

class NormalizeRequest(BaseModel):
    text: str
    confidence: float = 1.0

class QueryExpandRequest(BaseModel):
    normalized_text: str
    catalog_hits: List[Dict[str, Any]] = None

@router.post("/", response_model=NormalizeResponse)
async def normalize_banking_text(request: NormalizeRequest):
    """
    은행 도메인 텍스트를 정규화합니다.
    
    Args:
        request: 정규화 요청 (원본 텍스트, 신뢰도)
        
    Returns:
        NormalizeResponse: 정규화 결과
    """
    try:
        result = normalize_text(request.text, request.confidence)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"정규화 중 오류 발생: {str(e)}")

@router.post("/expand-query")
async def expand_query(request: QueryExpandRequest):
    """
    검색 쿼리를 확장합니다.
    
    Args:
        request: 쿼리 확장 요청
        
    Returns:
        List[str]: 확장된 검색 용어들
    """
    try:
        expanded_terms = expand_search_query(
            request.normalized_text, 
            request.catalog_hits
        )
        return {"expanded_terms": expanded_terms}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"쿼리 확장 중 오류 발생: {str(e)}")

@router.get("/test")
async def test_normalizer():
    """정규화기 테스트 엔드포인트"""
    test_cases = [
        "전기예금 금리 알려줘",
        "자유 적금 상품이 궁금해요",
        "전세 대출 한도는 얼마인가요",
        "정기 이체 서비스 신청하고 싶어요"
    ]
    
    results = []
    for test_text in test_cases:
        result = normalize_text(test_text, 0.9)
        results.append({
            "original": result.original,
            "normalized": result.normalized,
            "corrections": result.corrections,
            "needs_clarification": result.needs_clarification
        })
    
    return {"test_results": results}
