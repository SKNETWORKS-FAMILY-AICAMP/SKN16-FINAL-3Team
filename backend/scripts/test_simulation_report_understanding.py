"""
시뮬레이션 리포트 이해도 테스트
"""
import asyncio
import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from sqlmodel import Session
from app.database import engine
from app.services.rag_service import RAGService


# 시뮬레이션 리포트 관련 테스트 케이스
TEST_CASES = [
    {
        "category": "시뮬레이션 리포트 구조 이해",
        "query": "시뮬레이션 평가 리포트는 어떤 항목으로 구성되어 있나요?",
        "expected_keywords": ["지식", "기술", "공감도", "명확성", "친절도", "자신감", "평가", "점수"],
    },
    {
        "category": "시뮬레이션 리포트 점수 체계",
        "query": "시뮬레이션 평가에서 6가지 지표는 무엇인가요? 각각의 가중치는 어떻게 되나요?",
        "expected_keywords": ["지식", "기술", "공감도", "명확성", "친절도", "자신감", "가중치"],
    },
    {
        "category": "시뮬레이션 리포트 등급 체계",
        "query": "시뮬레이션 평가 결과의 등급은 어떻게 정해지나요? A+, A, B+ 같은 등급 기준이 있나요?",
        "expected_keywords": ["등급", "A+", "A", "B+", "B", "C", "점수", "기준"],
    },
    {
        "category": "시뮬레이션 리포트 피드백",
        "query": "시뮬레이션 평가 리포트에 포함되는 피드백 항목은 무엇인가요?",
        "expected_keywords": ["피드백", "강점", "개선점", "추천 학습", "상세 피드백"],
    },
    {
        "category": "시뮬레이션 리포트 해석",
        "query": "시뮬레이션 리포트를 받았는데 지식 점수가 35점이고 기술 점수가 25점이에요. 어떤 의미인가요?",
        "expected_keywords": ["지식", "기술", "점수", "의미", "개선", "학습"],
    },
]


async def run_tests():
    print("=" * 80)
    print("시뮬레이션 리포트 이해도 테스트")
    print("=" * 80)
    
    total_tests = len(TEST_CASES)
    passed_tests = []
    failed_tests = []
    
    with Session(engine) as session:
        rag_service = RAGService(session)
        
        for idx, test_case in enumerate(TEST_CASES, 1):
            print(f"\n[테스트 {idx}/{total_tests}] {test_case['category']}")
            print(f"질문: {test_case['query']}")
            print("-" * 80)
            
            try:
                # RAG 검색 실행
                results = await rag_service.similarity_search(
                    query=test_case["query"],
                    top_k=5,
                )
                
                # 검색 결과 출력
                found_keywords = set()
                max_score = 0.0
                best_match_text = ""
                has_simulation_content = False
                
                print(f"검색 결과: {len(results)}개")
                for result in results:
                    score = result.get("similarity", 0.0)
                    content = result.get("content", "")
                    title = result.get("title", "")
                    file_path = result.get("file_path", "")
                    
                    if score > max_score:
                        max_score = score
                        best_match_text = content[:300]
                    
                    # 시뮬레이션 관련 키워드 확인
                    if any(kw in content.lower() or kw in title.lower() 
                           for kw in ["시뮬레이션", "평가", "evaluation", "simulation", "리포트", "report"]):
                        has_simulation_content = True
                    
                    print(f"  점수: {score:.3f} | 제목: {title[:50]}")
                    print(f"    파일: {file_path}")
                    print(f"    내용 미리보기: {content[:150]}...")
                    
                    for keyword in test_case["expected_keywords"]:
                        if keyword.lower() in content.lower():
                            found_keywords.add(keyword)
                
                # 검증
                passed = True
                reasons = []
                
                # 1. 유사도 점수 확인 (최소 0.3 이상)
                if max_score < 0.3:
                    passed = False
                    reasons.append(f"최고 점수 {max_score:.3f}가 너무 낮음 (최소 0.3 이상 필요)")
                
                # 2. 키워드 매칭 확인
                if len(found_keywords) < len(test_case["expected_keywords"]) / 3:  # 1/3 이상 매칭
                    passed = False
                    reasons.append(f"예상 키워드 매칭 부족 ({len(found_keywords)}/{len(test_case['expected_keywords'])})")
                
                # 3. 시뮬레이션 관련 내용 포함 여부
                if not has_simulation_content and max_score > 0.4:
                    # 높은 점수인데 시뮬레이션 내용이 없으면 다른 주제로 잘못 검색된 것
                    passed = False
                    reasons.append("시뮬레이션 관련 내용이 검색 결과에 포함되지 않음")
                
                if passed:
                    print(f"\n✓ 통과: 최고 점수 {max_score:.3f}, 키워드 매칭 {len(found_keywords)}/{len(test_case['expected_keywords'])}")
                    if found_keywords:
                        print(f"  매칭된 키워드: {', '.join(sorted(list(found_keywords)))}")
                    passed_tests.append(test_case)
                else:
                    print(f"\n❌ 실패: {'; '.join(reasons)}")
                    print(f"  최고 점수: {max_score:.3f}")
                    print(f"  매칭된 키워드: {', '.join(sorted(list(found_keywords)))} ({len(found_keywords)}/{len(test_case['expected_keywords'])})")
                    if best_match_text:
                        print(f"  최고 점수 결과 미리보기:\n  {best_match_text}")
                    failed_tests.append({
                        "test": test_case,
                        "reason": "; ".join(reasons),
                        "score": max_score,
                        "keywords_found": len(found_keywords),
                        "keywords_total": len(test_case["expected_keywords"]),
                    })
                
            except Exception as e:
                print(f"❌ 오류 발생: {e}")
                import traceback
                traceback.print_exc()
                failed_tests.append({
                    "test": test_case,
                    "reason": f"Exception: {e}",
                })
    
    print("\n" * 2)
    print("=" * 80)
    print("테스트 결과 요약")
    print("=" * 80)
    print(f"전체 테스트: {total_tests}개")
    print(f"통과: {len(passed_tests)}개 ({len(passed_tests) / total_tests * 100:.1f}%)")
    print(f"실패: {len(failed_tests)}개 ({len(failed_tests) / total_tests * 100:.1f}%)")
    print("=" * 80)
    
    if failed_tests:
        print("\n실패한 테스트 상세:")
        for failure in failed_tests:
            print(f"- [{failure['test']['category']}] {failure['test']['query']}")
            print(f"  원인: {failure['reason']}")
            if 'score' in failure:
                print(f"  점수: {failure['score']:.3f}, 키워드: {failure['keywords_found']}/{failure['keywords_total']}")
    
    print("\n" * 2)
    print("=" * 80)
    print("결론 및 권장사항")
    print("=" * 80)
    
    if len(passed_tests) == 0:
        print("❌ 챗봇이 시뮬레이션 리포트를 전혀 이해하지 못합니다.")
        print("   → RAG 인덱스에 시뮬레이션 리포트 관련 문서가 없습니다.")
        print("   → 시뮬레이션 리포트 구조/평가 기준 문서를 RAG 인덱스에 추가해야 합니다.")
    elif len(passed_tests) < total_tests / 2:
        print("⚠️ 챗봇이 시뮬레이션 리포트를 부분적으로만 이해합니다.")
        print("   → 일부 정보는 찾을 수 있지만, 전체적인 이해도는 낮습니다.")
        print("   → 시뮬레이션 리포트 관련 문서를 RAG 인덱스에 추가하는 것을 권장합니다.")
    else:
        print("✓ 챗봇이 시뮬레이션 리포트를 어느 정도 이해합니다.")
        print("   → 대부분의 질문에 대해 관련 정보를 찾을 수 있습니다.")


if __name__ == "__main__":
    asyncio.run(run_tests())














