#!/usr/bin/env python3
"""
Ground Truth 기반 평가 검증 스크립트

사전에 정의된 기준 답안(Ground Truth)과 평가 결과를 비교하여
평가 시스템의 정확도를 검증합니다.
"""

import sys
import json
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from sqlmodel import Session, select
from app.database import get_db
from app.models.rag_simulation import RAGSimulationEvaluation


@dataclass
class GroundTruthEvaluation:
    """Ground Truth 평가 데이터"""
    session_key: str
    expected_scores: Dict[str, float]  # {"knowledge": 35, "skill": 25, "attitude": 28, "total": 88}
    expected_strengths: List[str]
    expected_improvements: List[str]
    tolerance: Dict[str, float] = None  # 허용 오차 {"knowledge": 5, "skill": 3, ...}
    
    def __post_init__(self):
        if self.tolerance is None:
            # 기본 허용 오차: 점수의 10%
            self.tolerance = {
                "knowledge": self.expected_scores.get("knowledge", 40) * 0.1,
                "skill": self.expected_scores.get("skill", 30) * 0.1,
                "attitude": self.expected_scores.get("attitude", 30) * 0.1,
                "total": self.expected_scores.get("total", 100) * 0.1
            }


class GroundTruthValidator:
    """Ground Truth 기반 검증 클래스"""
    
    def __init__(self, session: Session, ground_truth_path: Optional[Path] = None):
        self.session = session
        self.ground_truth_path = ground_truth_path or Path(__file__).parent / "evaluation_ground_truth.json"
        self.ground_truth_data: Dict[str, GroundTruthEvaluation] = {}
        self._load_ground_truth()
    
    def _load_ground_truth(self):
        """Ground Truth 데이터 로드"""
        if not self.ground_truth_path.exists():
            print(f"⚠️ Ground Truth 파일이 없습니다: {self.ground_truth_path}")
            print("샘플 Ground Truth 파일을 생성합니다...")
            self._create_sample_ground_truth()
            return
        
        with open(self.ground_truth_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        for item in data.get("evaluations", []):
            gt = GroundTruthEvaluation(**item)
            self.ground_truth_data[gt.session_key] = gt
        
        print(f"✅ Ground Truth 데이터 로드 완료: {len(self.ground_truth_data)}개")
    
    def _create_sample_ground_truth(self):
        """샘플 Ground Truth 파일 생성"""
        sample_data = {
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
        
        with open(self.ground_truth_path, 'w', encoding='utf-8') as f:
            json.dump(sample_data, f, ensure_ascii=False, indent=2)
        
        print(f"✅ 샘플 Ground Truth 파일 생성: {self.ground_truth_path}")
    
    def validate_against_ground_truth(self, session_key: str) -> Dict:
        """
        Ground Truth와 평가 결과 비교
        
        Args:
            session_key: 검증할 세션 키
        
        Returns:
            검증 결과
        """
        print(f"\n{'='*60}")
        print(f"🎯 Ground Truth 검증: {session_key}")
        print(f"{'='*60}")
        
        # Ground Truth 조회
        ground_truth = self.ground_truth_data.get(session_key)
        if not ground_truth:
            return {
                "error": f"Ground Truth를 찾을 수 없습니다: {session_key}",
                "available_keys": list(self.ground_truth_data.keys())
            }
        
        # 평가 결과 조회
        query = select(RAGSimulationEvaluation).join(
            RAGSimulationEvaluation.session
        ).where(
            RAGSimulationEvaluation.session.has(session_key=session_key)
        ).order_by(
            RAGSimulationEvaluation.created_at.desc()
        ).limit(1)
        
        evaluation = self.session.exec(query).first()
        if not evaluation:
            return {"error": "평가 결과를 찾을 수 없습니다."}
        
        # 점수 비교
        actual_scores = {
            "knowledge": evaluation.knowledge_score,
            "skill": evaluation.skill_score,
            "attitude": evaluation.attitude_score,
            "total": evaluation.total_score
        }
        
        score_comparison = {}
        all_within_tolerance = True
        
        for category in ["knowledge", "skill", "attitude", "total"]:
            expected = ground_truth.expected_scores.get(category, 0)
            actual = actual_scores.get(category, 0)
            diff = abs(expected - actual)
            tolerance = ground_truth.tolerance.get(category, 0)
            within_tolerance = diff <= tolerance
            
            if not within_tolerance:
                all_within_tolerance = False
            
            score_comparison[category] = {
                "expected": expected,
                "actual": actual,
                "difference": round(diff, 2),
                "tolerance": tolerance,
                "within_tolerance": within_tolerance,
                "status": "✅" if within_tolerance else "❌"
            }
        
        # 피드백 비교 (선택적)
        strengths_match = self._compare_feedback(
            evaluation.strengths or [],
            ground_truth.expected_strengths,
            "강점"
        )
        
        improvements_match = self._compare_feedback(
            evaluation.improvements or [],
            ground_truth.expected_improvements,
            "개선점"
        )
        
        result = {
            "session_key": session_key,
            "score_comparison": score_comparison,
            "feedback_comparison": {
                "strengths": strengths_match,
                "improvements": improvements_match
            },
            "overall": {
                "scores_within_tolerance": all_within_tolerance,
                "accuracy_rate": self._calculate_accuracy_rate(score_comparison),
                "status": "✅ 통과" if all_within_tolerance else "❌ 실패"
            }
        }
        
        # 출력
        print(f"\n📊 점수 비교:")
        for category, comparison in score_comparison.items():
            print(f"\n   [{category.upper()}]")
            print(f"      예상: {comparison['expected']}점")
            print(f"      실제: {comparison['actual']}점")
            print(f"      차이: {comparison['difference']}점 (허용 오차: ±{comparison['tolerance']}점)")
            print(f"      상태: {comparison['status']}")
        
        print(f"\n📝 피드백 비교:")
        print(f"   강점 일치율: {strengths_match['match_rate']:.1f}%")
        print(f"   개선점 일치율: {improvements_match['match_rate']:.1f}%")
        
        print(f"\n🎯 전체 결과: {result['overall']['status']}")
        print(f"   정확도: {result['overall']['accuracy_rate']:.1f}%")
        
        return result
    
    def _compare_feedback(self, actual: List[str], expected: List[str], category: str) -> Dict:
        """피드백 비교 (유사도 기반)"""
        if not expected:
            return {
                "match_rate": 100.0,
                "note": "예상 피드백이 없어 비교 불가"
            }
        
        # 간단한 키워드 매칭 기반 비교
        matched = 0
        for expected_item in expected:
            for actual_item in actual:
                # 키워드 기반 유사도 계산 (간단한 버전)
                if self._similarity_score(actual_item, expected_item) > 0.5:
                    matched += 1
                    break
        
        match_rate = (matched / len(expected)) * 100 if expected else 0
        
        return {
            "expected_count": len(expected),
            "actual_count": len(actual),
            "matched_count": matched,
            "match_rate": round(match_rate, 2),
            "expected_items": expected,
            "actual_items": actual
        }
    
    def _similarity_score(self, text1: str, text2: str) -> float:
        """간단한 텍스트 유사도 계산"""
        # 간단한 집합 기반 유사도
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1 & words2
        union = words1 | words2
        
        return len(intersection) / len(union) if union else 0.0
    
    def _calculate_accuracy_rate(self, score_comparison: Dict) -> float:
        """전체 정확도 계산"""
        within_tolerance_count = sum(
            1 for comp in score_comparison.values() 
            if comp["within_tolerance"]
        )
        total_count = len(score_comparison)
        
        return (within_tolerance_count / total_count * 100) if total_count > 0 else 0.0
    
    def batch_validate(self) -> Dict:
        """모든 Ground Truth에 대해 배치 검증"""
        print(f"\n{'='*60}")
        print(f"🔄 배치 Ground Truth 검증")
        print(f"{'='*60}")
        
        results = []
        for session_key in self.ground_truth_data.keys():
            result = self.validate_against_ground_truth(session_key)
            if "error" not in result:
                results.append(result)
        
        # 전체 통계
        if results:
            total_accuracy = sum(r["overall"]["accuracy_rate"] for r in results) / len(results)
            passed_count = sum(1 for r in results if r["overall"]["scores_within_tolerance"])
            
            summary = {
                "total_validated": len(results),
                "passed": passed_count,
                "failed": len(results) - passed_count,
                "average_accuracy": round(total_accuracy, 2),
                "results": results
            }
            
            print(f"\n📊 배치 검증 요약:")
            print(f"   총 검증: {summary['total_validated']}개")
            print(f"   통과: {summary['passed']}개")
            print(f"   실패: {summary['failed']}개")
            print(f"   평균 정확도: {summary['average_accuracy']:.1f}%")
            
            return summary
        
        return {"error": "검증할 데이터가 없습니다."}


def main():
    """메인 함수"""
    print("="*80)
    print("🎯 Ground Truth 기반 평가 검증 도구")
    print("="*80)
    
    # DB 세션 생성
    db_gen = get_db()
    db_session = next(db_gen)
    
    try:
        validator = GroundTruthValidator(db_session)
        
        # 배치 검증 실행
        batch_result = validator.batch_validate()
        
        # 특정 세션 검증 예시
        # result = validator.validate_against_ground_truth("session_example_1")
        
    finally:
        db_session.close()


if __name__ == "__main__":
    main()











