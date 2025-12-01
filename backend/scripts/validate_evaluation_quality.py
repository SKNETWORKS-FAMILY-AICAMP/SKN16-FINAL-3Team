#!/usr/bin/env python3
"""
RAG 시뮬레이션 평가 품질 검증 스크립트

평가 결과의 품질을 검증하는 다양한 방법을 제공합니다:
1. 일관성 검증 (같은 대화에 대한 반복 평가)
2. 제품 지식 정확도 검증 (ProductKnowledgeService와 비교)
3. 평가 점수 분포 분석
4. 평가 기준 준수 검증
5. Ground Truth 비교 (옵션)
"""

import sys
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from collections import defaultdict
import statistics

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from sqlmodel import Session, select
from app.database import get_db
from app.models.rag_simulation import (
    RAGSimulationSession,
    RAGSimulationTurn,
    RAGSimulationEvaluation
)
from app.services.product_knowledge_service import ProductKnowledgeService


class EvaluationValidator:
    """평가 품질 검증 클래스"""
    
    def __init__(self, session: Session):
        self.session = session
        self.product_service = ProductKnowledgeService(use_llm=True)
    
    def validate_consistency(self, session_key: str, num_runs: int = 3) -> Dict:
        """
        같은 대화에 대한 반복 평가 일관성 검증
        
        Args:
            session_key: 검증할 세션 키
            num_runs: 반복 평가 횟수
        
        Returns:
            일관성 검증 결과
        """
        print(f"\n{'='*60}")
        print(f"🔍 일관성 검증: {session_key}")
        print(f"{'='*60}")
        
        # 세션과 대화 기록 가져오기
        session_record = self._get_session(session_key)
        if not session_record:
            return {"error": "세션을 찾을 수 없습니다."}
        
        turns = self._get_turns(session_record.id)
        conversation = self._build_conversation(turns)
        
        # 여러 번 평가 실행 (실제로는 평가 엔드포인트 호출)
        # 여기서는 기존 평가 결과가 여러 개 있을 경우를 가정
        evaluations = self._get_evaluations(session_record.id)
        
        if len(evaluations) < 2:
            return {
                "status": "insufficient_data",
                "message": "일관성 검증을 위해서는 최소 2개 이상의 평가가 필요합니다.",
                "evaluations_found": len(evaluations)
            }
        
        # 점수 추출
        scores = {
            "knowledge": [e.knowledge_score for e in evaluations],
            "skill": [e.skill_score for e in evaluations],
            "attitude": [e.attitude_score for e in evaluations],
            "total": [e.total_score for e in evaluations]
        }
        
        # 통계 계산
        consistency_results = {}
        for category, score_list in scores.items():
            if len(score_list) > 1:
                consistency_results[category] = {
                    "scores": score_list,
                    "mean": statistics.mean(score_list),
                    "std_dev": statistics.stdev(score_list) if len(score_list) > 1 else 0,
                    "min": min(score_list),
                    "max": max(score_list),
                    "range": max(score_list) - min(score_list),
                    "cv": (statistics.stdev(score_list) / statistics.mean(score_list) * 100 
                           if statistics.mean(score_list) > 0 else 0)  # 변동계수
                }
        
        # 일관성 판단 기준
        # 변동계수(CV) < 10%: 매우 일관적
        # 변동계수(CV) < 20%: 일관적
        # 변동계수(CV) >= 20%: 불일관적
        consistency_status = {}
        for category, stats in consistency_results.items():
            cv = stats["cv"]
            if cv < 10:
                status = "very_consistent"
                status_text = "매우 일관적 ✅"
            elif cv < 20:
                status = "consistent"
                status_text = "일관적 ✅"
            else:
                status = "inconsistent"
                status_text = "불일관적 ⚠️"
            
            consistency_status[category] = {
                "status": status,
                "status_text": status_text,
                "cv": round(cv, 2)
            }
        
        result = {
            "session_key": session_key,
            "num_evaluations": len(evaluations),
            "consistency_stats": consistency_results,
            "consistency_status": consistency_status,
            "overall_status": "consistent" if all(
                s["status"] in ["consistent", "very_consistent"] 
                for s in consistency_status.values()
            ) else "inconsistent"
        }
        
        # 출력
        print(f"\n📊 평가 일관성 결과:")
        print(f"   평가 횟수: {len(evaluations)}회")
        for category, stats in consistency_results.items():
            print(f"\n   [{category.upper()}]")
            print(f"      점수 범위: {stats['min']} ~ {stats['max']} (범위: {stats['range']})")
            print(f"      평균: {stats['mean']:.2f}")
            print(f"      표준편차: {stats['std_dev']:.2f}")
            print(f"      변동계수: {stats['cv']:.2f}%")
            print(f"      상태: {consistency_status[category]['status_text']}")
        
        return result
    
    def validate_knowledge_accuracy(self, session_key: str) -> Dict:
        """
        제품 지식 정확도 검증
        ProductKnowledgeService를 사용하여 직원 발화의 제품 지식 정확성 검증
        
        Args:
            session_key: 검증할 세션 키
        
        Returns:
            지식 정확도 검증 결과
        """
        print(f"\n{'='*60}")
        print(f"📚 제품 지식 정확도 검증: {session_key}")
        print(f"{'='*60}")
        
        # 세션과 대화 기록 가져오기
        session_record = self._get_session(session_key)
        if not session_record:
            return {"error": "세션을 찾을 수 없습니다."}
        
        turns = self._get_turns(session_record.id)
        conversation = self._build_conversation(turns)
        
        # 직원 발화만 추출
        employee_utterances = [
            turn["text"] for turn in conversation 
            if turn.get("role") in ["employee", "teller"]
        ]
        
        if not employee_utterances:
            return {"error": "직원 발화를 찾을 수 없습니다."}
        
        # ProductKnowledgeService로 검증
        print(f"\n🔍 직원 발화 {len(employee_utterances)}개 검증 중...")
        verification_result = self.product_service.batch_verify_conversation(
            conversation,
            use_llm=True
        )
        
        # 평가 결과와 비교
        evaluation = self._get_latest_evaluation(session_record.id)
        if not evaluation:
            return {
                "verification": verification_result,
                "note": "평가 결과가 없어 비교할 수 없습니다."
            }
        
        # 정확도 비교
        knowledge_accuracy_rate = verification_result.get("accuracy_rate", 0)
        knowledge_score_from_eval = evaluation.knowledge_score / 40 * 100  # 40점 만점을 백분율로
        
        accuracy_diff = abs(knowledge_accuracy_rate - knowledge_score_from_eval)
        
        result = {
            "session_key": session_key,
            "verification": {
                "total_claims": verification_result.get("total_claims", 0),
                "accurate_claims": verification_result.get("accurate_claims", 0),
                "inaccurate_claims": verification_result.get("inaccurate_claims", 0),
                "accuracy_rate": knowledge_accuracy_rate
            },
            "evaluation": {
                "knowledge_score": evaluation.knowledge_score,
                "knowledge_score_percent": knowledge_score_from_eval
            },
            "comparison": {
                "accuracy_diff": round(accuracy_diff, 2),
                "correlation": "high" if accuracy_diff < 10 else "medium" if accuracy_diff < 20 else "low"
            }
        }
        
        # 출력
        print(f"\n📊 제품 지식 정확도 결과:")
        print(f"   검증 정확도: {knowledge_accuracy_rate:.1f}%")
        print(f"   평가 지식 점수: {evaluation.knowledge_score}/40 ({knowledge_score_from_eval:.1f}%)")
        print(f"   차이: {accuracy_diff:.2f}%p")
        print(f"   상관관계: {result['comparison']['correlation']}")
        
        return result
    
    def analyze_score_distribution(self, limit: int = 100) -> Dict:
        """
        평가 점수 분포 분석
        
        Args:
            limit: 분석할 평가 개수 제한
        
        Returns:
            점수 분포 분석 결과
        """
        print(f"\n{'='*60}")
        print(f"📊 평가 점수 분포 분석 (최대 {limit}개)")
        print(f"{'='*60}")
        
        # 모든 평가 가져오기
        query = select(RAGSimulationEvaluation).limit(limit)
        evaluations = list(self.session.exec(query).all())
        
        if not evaluations:
            return {"error": "평가 데이터가 없습니다."}
        
        # 점수 추출
        knowledge_scores = [e.knowledge_score for e in evaluations]
        skill_scores = [e.skill_score for e in evaluations]
        attitude_scores = [e.attitude_score for e in evaluations]
        total_scores = [e.total_score for e in evaluations]
        
        def analyze_distribution(scores: List[float], name: str) -> Dict:
            """점수 분포 분석"""
            return {
                "count": len(scores),
                "mean": round(statistics.mean(scores), 2),
                "median": round(statistics.median(scores), 2),
                "std_dev": round(statistics.stdev(scores), 2) if len(scores) > 1 else 0,
                "min": min(scores),
                "max": max(scores),
                "q1": round(statistics.quantiles(scores, n=4)[0], 2) if len(scores) > 3 else min(scores),
                "q3": round(statistics.quantiles(scores, n=4)[2], 2) if len(scores) > 3 else max(scores),
                # 점수 구간별 분포
                "distribution": {
                    "0-20": sum(1 for s in scores if 0 <= s < 20),
                    "20-40": sum(1 for s in scores if 20 <= s < 40),
                    "40-60": sum(1 for s in scores if 40 <= s < 60),
                    "60-80": sum(1 for s in scores if 60 <= s < 80),
                    "80-100": sum(1 for s in scores if 80 <= s <= 100)
                }
            }
        
        result = {
            "total_evaluations": len(evaluations),
            "knowledge": analyze_distribution(knowledge_scores, "지식"),
            "skill": analyze_distribution(skill_scores, "기술"),
            "attitude": analyze_distribution(attitude_scores, "태도"),
            "total": analyze_distribution(total_scores, "총점")
        }
        
        # 출력
        print(f"\n📈 점수 분포 요약:")
        for category in ["knowledge", "skill", "attitude", "total"]:
            stats = result[category]
            print(f"\n   [{category.upper()}]")
            print(f"      평균: {stats['mean']:.2f}")
            print(f"      중앙값: {stats['median']:.2f}")
            print(f"      표준편차: {stats['std_dev']:.2f}")
            print(f"      범위: {stats['min']} ~ {stats['max']}")
            print(f"      사분위수: Q1={stats['q1']:.2f}, Q3={stats['q3']:.2f}")
            print(f"      분포:")
            for range_label, count in stats["distribution"].items():
                percentage = count / stats["count"] * 100
                print(f"         {range_label}점: {count}개 ({percentage:.1f}%)")
        
        return result
    
    def validate_evaluation_criteria(self, session_key: str) -> Dict:
        """
        평가 기준 준수 검증
        - 점수 범위 검증 (0-40, 0-30, 0-30, 0-100)
        - 점수 합계 검증 (knowledge + skill + attitude = total)
        - 필수 필드 존재 검증
        
        Args:
            session_key: 검증할 세션 키
        
        Returns:
            평가 기준 준수 검증 결과
        """
        print(f"\n{'='*60}")
        print(f"✅ 평가 기준 준수 검증: {session_key}")
        print(f"{'='*60}")
        
        session_record = self._get_session(session_key)
        if not session_record:
            return {"error": "세션을 찾을 수 없습니다."}
        
        evaluation = self._get_latest_evaluation(session_record.id)
        if not evaluation:
            return {"error": "평가 결과를 찾을 수 없습니다."}
        
        issues = []
        
        # 점수 범위 검증
        if not (0 <= evaluation.knowledge_score <= 40):
            issues.append(f"지식 점수 범위 초과: {evaluation.knowledge_score} (0-40)")
        
        if not (0 <= evaluation.skill_score <= 30):
            issues.append(f"기술 점수 범위 초과: {evaluation.skill_score} (0-30)")
        
        if not (0 <= evaluation.attitude_score <= 30):
            issues.append(f"태도 점수 범위 초과: {evaluation.attitude_score} (0-30)")
        
        if not (0 <= evaluation.total_score <= 100):
            issues.append(f"총점 범위 초과: {evaluation.total_score} (0-100)")
        
        # 점수 합계 검증
        expected_total = evaluation.knowledge_score + evaluation.skill_score + evaluation.attitude_score
        if abs(evaluation.total_score - expected_total) > 0.01:  # 부동소수점 오차 허용
            issues.append(
                f"점수 합계 불일치: 총점={evaluation.total_score}, "
                f"합계={expected_total} (차이: {abs(evaluation.total_score - expected_total)})"
            )
        
        # 필수 필드 검증
        if not evaluation.strengths:
            issues.append("강점(strengths) 필드 누락")
        
        if not evaluation.improvements:
            issues.append("개선점(improvements) 필드 누락")
        
        result = {
            "session_key": session_key,
            "evaluation_id": evaluation.id,
            "scores": {
                "knowledge": evaluation.knowledge_score,
                "skill": evaluation.skill_score,
                "attitude": evaluation.attitude_score,
                "total": evaluation.total_score,
                "expected_total": expected_total
            },
            "validation": {
                "is_valid": len(issues) == 0,
                "issues": issues,
                "issue_count": len(issues)
            }
        }
        
        # 출력
        if result["validation"]["is_valid"]:
            print(f"\n✅ 모든 평가 기준을 준수합니다.")
        else:
            print(f"\n⚠️ {len(issues)}개의 문제가 발견되었습니다:")
            for issue in issues:
                print(f"   - {issue}")
        
        return result
    
    def _get_session(self, session_key: str) -> Optional[RAGSimulationSession]:
        """세션 조회"""
        query = select(RAGSimulationSession).where(
            RAGSimulationSession.session_key == session_key
        )
        return self.session.exec(query).first()
    
    def _get_turns(self, session_id: int) -> List[RAGSimulationTurn]:
        """세션의 모든 턴 조회"""
        query = select(RAGSimulationTurn).where(
            RAGSimulationTurn.session_id == session_id
        ).order_by(RAGSimulationTurn.turn_index)
        return list(self.session.exec(query).all())
    
    def _get_evaluations(self, session_id: int) -> List[RAGSimulationEvaluation]:
        """세션의 모든 평가 조회"""
        query = select(RAGSimulationEvaluation).where(
            RAGSimulationEvaluation.session_id == session_id
        ).order_by(RAGSimulationEvaluation.created_at)
        return list(self.session.exec(query).all())
    
    def _get_latest_evaluation(self, session_id: int) -> Optional[RAGSimulationEvaluation]:
        """세션의 최신 평가 조회"""
        query = select(RAGSimulationEvaluation).where(
            RAGSimulationEvaluation.session_id == session_id
        ).order_by(RAGSimulationEvaluation.created_at.desc()).limit(1)
        return self.session.exec(query).first()
    
    def _build_conversation(self, turns: List[RAGSimulationTurn]) -> List[Dict]:
        """턴 리스트를 대화 형식으로 변환"""
        return [
            {
                "role": turn.role,
                "text": turn.text,
                "timestamp": turn.created_at.isoformat() if turn.created_at else None
            }
            for turn in turns
        ]


def main():
    """메인 함수"""
    print("="*80)
    print("🎯 RAG 시뮬레이션 평가 품질 검증 도구")
    print("="*80)
    
    # DB 세션 생성
    db_gen = get_db()
    db_session = next(db_gen)
    
    try:
        validator = EvaluationValidator(db_session)
        
        # 사용 예시
        print("\n📋 사용 가능한 검증 방법:")
        print("   1. 일관성 검증: 같은 대화에 대한 반복 평가 일관성")
        print("   2. 제품 지식 정확도 검증: ProductKnowledgeService와 비교")
        print("   3. 평가 점수 분포 분석: 전체 평가 데이터의 통계 분석")
        print("   4. 평가 기준 준수 검증: 점수 범위 및 필수 필드 검증")
        
        # 점수 분포 분석 (항상 가능)
        print("\n" + "="*80)
        distribution_result = validator.analyze_score_distribution(limit=100)
        
        if "error" not in distribution_result:
            print("\n✅ 점수 분포 분석 완료")
        
        # 특정 세션에 대한 검증 예시 (세션 키를 제공한 경우)
        # session_key = "session_example"
        # validator.validate_consistency(session_key)
        # validator.validate_knowledge_accuracy(session_key)
        # validator.validate_evaluation_criteria(session_key)
        
    finally:
        db_session.close()


if __name__ == "__main__":
    main()






