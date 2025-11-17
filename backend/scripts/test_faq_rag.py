#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FAQ RAG 데이터 검색 테스트 스크립트

사용법:
    python test_faq_rag.py
"""
import asyncio
import json
import os
import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from sqlmodel import Session, select
from app.database import engine
from app.services.rag_service import RAGService


# 테스트 케이스 정의
TEST_CASES = [
    {
        "category": "은행업무 - 예금 상담",
        "query": "하경스타클럽이 무엇인가요?",
        "expected_keywords": ["하경스타클럽", "혜택", "우대"],
        "min_score": 0.7,
    },
    {
        "category": "은행업무 - 예금 상담",
        "query": "주택청약예금 비대면 상품 전환이 가능한가요?",
        "expected_keywords": ["주택청약예금", "비대면", "상품 전환"],
        "min_score": 0.7,
    },
    {
        "category": "은행업무 - 예금 상담",
        "query": "미성년자 자녀 예금 해지하려면 어떻게 하나요?",
        "expected_keywords": ["미성년자", "예금", "해지", "법정대리인"],
        "min_score": 0.65,
    },
    {
        "category": "은행업무 - 예금 상담",
        "query": "하경가맹점우대통장 법인도 가입 가능한가요?",
        "expected_keywords": ["가맹점우대통장", "법인", "개인사업자"],
        "min_score": 0.7,
    },
    {
        "category": "전자금융업무 - 홈페이지",
        "query": "키보드보안프로그램 오류가 발생했어요",
        "expected_keywords": ["키보드보안", "Keypress handler", "오류"],
        "min_score": 0.65,
    },
    {
        "category": "전자금융업무 - 홈페이지",
        "query": "보안프로그램 설치 오류",
        "expected_keywords": ["보안프로그램", "설치", "VeraPort"],
        "min_score": 0.6,
    },
    {
        "category": "은행업무 - 대출 상담",
        "query": "전세자금대출 한도는 얼마인가요?",
        "expected_keywords": ["전세자금", "한도", "LTV"],
        "min_score": 0.6,
    },
    {
        "category": "은행업무 - 외환 상담",
        "query": "해외송금 수수료는 어떻게 되나요?",
        "expected_keywords": ["해외송금", "수수료", "환율"],
        "min_score": 0.6,
    },
]


async def test_rag_search():
    """RAG 검색 테스트 실행"""
    print("=" * 80)
    print("FAQ RAG 데이터 검색 테스트")
    print("=" * 80)
    print()

    with Session(engine) as session:
        total_tests = len(TEST_CASES)
        passed_tests = 0
        failed_tests = []

        for idx, test_case in enumerate(TEST_CASES, 1):
            print(f"[테스트 {idx}/{total_tests}] {test_case['category']}")
            print(f"질문: {test_case['query']}")
            print("-" * 80)

            try:
                # RAG 검색 실행
                rag_service = RAGService(session)
                results = await rag_service.similarity_search(
                    query=test_case["query"],
                    top_k=5,
                )
                
                # 최소 점수 필터링
                min_score = test_case.get("min_score", 0.6)
                results = [
                    r for r in results 
                    if r.get("similarity", 0.0) >= min_score
                ]

                if not results:
                    print(f"❌ 실패: 검색 결과가 없습니다.")
                    failed_tests.append({
                        "test": test_case,
                        "reason": "검색 결과 없음",
                        "results": [],
                    })
                    print()
                    continue

                # 검색 결과 출력
                found_keywords = set()
                max_score = 0.0
                best_match_text = ""

                for result in results:
                    score = result.get("similarity", 0.0)
                    content = result.get("content", "")
                    metadata = result.get("metadata", {})
                    
                    if score > max_score:
                        max_score = score
                        best_match_text = content[:200]

                    # 키워드 확인
                    content_lower = content.lower()
                    for keyword in test_case["expected_keywords"]:
                        if keyword.lower() in content_lower:
                            found_keywords.add(keyword)

                    # FAQ인지 확인 (metadata에 question이나 big_category가 있는지)
                    is_faq = any(
                        key in metadata
                        for key in ["question", "big_category", "sub_category", "id"]
                    )

                    print(f"  점수: {score:.3f} | FAQ: {'✓' if is_faq else '✗'}")
                    if metadata:
                        faq_id = metadata.get("id", "N/A")
                        big_cat = metadata.get("big_category", "N/A")
                        sub_cat = metadata.get("sub_category", "N/A")
                        print(f"    ID: {faq_id}")
                        print(f"    카테고리: {big_cat} > {sub_cat}")
                    print(f"    내용: {content[:150]}...")
                    print()

                # 테스트 통과 여부 판단
                keyword_match_ratio = len(found_keywords) / len(test_case["expected_keywords"])
                is_faq_found = any(
                    any(key in str(result.get("metadata", {})).lower() 
                        for key in ["question", "big_category", "faq"])
                    for result in results
                )

                if keyword_match_ratio >= 0.5 and max_score >= test_case["min_score"]:
                    print(f"✓ 통과: 최고 점수 {max_score:.3f}, 키워드 매칭 {len(found_keywords)}/{len(test_case['expected_keywords'])}")
                    print(f"  매칭된 키워드: {', '.join(found_keywords)}")
                    print(f"  FAQ 소스 발견: {'✓' if is_faq_found else '⚠️'}")
                    passed_tests += 1
                else:
                    print(f"❌ 실패: 점수 {max_score:.3f} (최소 {test_case['min_score']}), 키워드 매칭 {len(found_keywords)}/{len(test_case['expected_keywords'])}")
                    failed_tests.append({
                        "test": test_case,
                        "reason": f"점수 또는 키워드 매칭 부족 (점수: {max_score:.3f}, 키워드: {len(found_keywords)}/{len(test_case['expected_keywords'])})",
                        "results": results[:2],
                    })

            except Exception as e:
                print(f"❌ 오류 발생: {e}")
                failed_tests.append({
                    "test": test_case,
                    "reason": f"예외 발생: {str(e)}",
                    "results": [],
                })
                import traceback
                traceback.print_exc()

            print("=" * 80)
            print()

        # 결과 요약
        print("\n" + "=" * 80)
        print("테스트 결과 요약")
        print("=" * 80)
        print(f"전체 테스트: {total_tests}개")
        print(f"통과: {passed_tests}개 ({passed_tests/total_tests*100:.1f}%)")
        print(f"실패: {len(failed_tests)}개 ({len(failed_tests)/total_tests*100:.1f}%)")
        print()

        if failed_tests:
            print("실패한 테스트:")
            for idx, failed in enumerate(failed_tests, 1):
                print(f"  {idx}. {failed['test']['category']}")
                print(f"     질문: {failed['test']['query']}")
                print(f"     이유: {failed['reason']}")
                print()

        return passed_tests == total_tests


if __name__ == "__main__":
    success = asyncio.run(test_rag_search())
    sys.exit(0 if success else 1)

