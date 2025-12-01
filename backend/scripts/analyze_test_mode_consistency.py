"""
테스트 모드 시뮬레이션 일관성 분석 스크립트
admin@bank.com 계정의 최근 2개 테스트 모드 시뮬레이션 결과를 비교
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlmodel import Session, select
from app.database import engine
from app.models.rag_simulation import RAGSimulationSession, RAGSimulationEvaluation
from app.models.user import User
import json
from datetime import datetime

def analyze_test_mode_consistency():
    """테스트 모드 시뮬레이션 일관성 분석"""
    with Session(engine) as session:
        # admin@bank.com 사용자 찾기
        user = session.exec(
            select(User).where(User.email == "admin@bank.com")
        ).first()
        
        if not user:
            print("❌ admin@bank.com 사용자를 찾을 수 없습니다.")
            return
        
        print(f"✅ 사용자 찾음: {user.email} (ID: {user.id})")
        
        # 최근 2개의 테스트 모드 시뮬레이션 세션 찾기
        # 테스트 모드는 scenario_id가 "test_"로 시작하고 완료된 세션만
        test_sessions = session.exec(
            select(RAGSimulationSession)
            .where(RAGSimulationSession.user_id == user.id)
            .where(RAGSimulationSession.scenario_id.like("test_%"))
            .where(RAGSimulationSession.is_completed == True)
            .order_by(RAGSimulationSession.started_at.desc())
            .limit(2)
        ).all()
        
        # 완료된 세션이 없으면 완료 여부와 관계없이 조회
        if len(test_sessions) < 2:
            test_sessions = session.exec(
                select(RAGSimulationSession)
                .where(RAGSimulationSession.user_id == user.id)
                .where(RAGSimulationSession.scenario_id.like("test_%"))
                .order_by(RAGSimulationSession.started_at.desc())
                .limit(2)
            ).all()
        
        if len(test_sessions) < 2:
            print(f"❌ 테스트 모드 시뮬레이션이 2개 미만입니다. (현재: {len(test_sessions)}개)")
            return
        
        print(f"\n📊 최근 2개 테스트 모드 시뮬레이션 분석")
        print("=" * 80)
        
        evaluations = []
        for idx, session_obj in enumerate(test_sessions, 1):
            print(f"\n[시뮬레이션 {idx}]")
            print(f"  세션 ID: {session_obj.id}")
            print(f"  세션 키: {session_obj.session_key}")
            print(f"  시나리오: {session_obj.scenario_id}")
            print(f"  페르소나: {session_obj.persona_id}")
            print(f"  시작 시간: {session_obj.started_at}")
            print(f"  완료 여부: {session_obj.is_completed}")
            print(f"  총 턴 수: {session_obj.total_turns}")
            
            # 평가 결과 찾기
            evaluation = session.exec(
                select(RAGSimulationEvaluation)
                .where(RAGSimulationEvaluation.session_id == session_obj.id)
            ).first()
            
            if not evaluation:
                print(f"  ⚠️ 평가 결과가 없습니다.")
                continue
            
            evaluations.append({
                "session": session_obj,
                "evaluation": evaluation
            })
            
            print(f"\n  📈 평가 점수:")
            print(f"    지식 (knowledge): {evaluation.knowledge_point}점")
            print(f"    기술 (skill): {evaluation.skill_point}점")
            print(f"    공감도 (empathy): {evaluation.empathy_point}점")
            print(f"    명확성 (clarity): {evaluation.clarity_point}점")
            print(f"    친절도 (kindness): {evaluation.kindness_point}점")
            print(f"    자신감 (confidence): {evaluation.confidence_point}점")
            print(f"    종합 점수: {evaluation.total_point}점")
            print(f"    등급: {evaluation.grade}")
            
            # detail_json 분석
            if evaluation.detail_json:
                try:
                    detail = json.loads(evaluation.detail_json)
                    print(f"\n  📋 상세 정보:")
                    if "knowledge" in detail:
                        print(f"    지식 상세: {detail['knowledge']}")
                    if "skill" in detail:
                        print(f"    기술 상세: {detail['skill']}")
                except:
                    pass
        
        # 두 시뮬레이션 비교
        if len(evaluations) == 2:
            print("\n" + "=" * 80)
            print("🔍 두 시뮬레이션 비교 분석")
            print("=" * 80)
            
            eval1 = evaluations[0]["evaluation"]
            eval2 = evaluations[1]["evaluation"]
            
            print(f"\n[시나리오 비교]")
            print(f"  시뮬레이션 1: {evaluations[0]['session'].scenario_id}")
            print(f"  시뮬레이션 2: {evaluations[1]['session'].scenario_id}")
            print(f"  동일 시나리오: {evaluations[0]['session'].scenario_id == evaluations[1]['session'].scenario_id}")
            
            print(f"\n[점수 차이 분석]")
            metrics = [
                ("지식", "knowledge_point"),
                ("기술", "skill_point"),
                ("공감도", "empathy_point"),
                ("명확성", "clarity_point"),
                ("친절도", "kindness_point"),
                ("자신감", "confidence_point"),
                ("종합 점수", "total_point")
            ]
            
            differences = []
            for name, attr in metrics:
                score1 = getattr(eval1, attr)
                score2 = getattr(eval2, attr)
                diff = abs(score1 - score2)
                print(f"  {name}: {score1}점 vs {score2}점 (차이: {diff}점)")
                if diff > 0:
                    differences.append((name, score1, score2, diff))
            
            if differences:
                print(f"\n⚠️ 차이가 발생한 역량:")
                for name, score1, score2, diff in differences:
                    print(f"  - {name}: {score1}점 → {score2}점 (차이: {diff}점)")
                
                # 이유 비교
                print(f"\n[이유 비교]")
                reason_attrs = [
                    ("지식", "knowledge_reason"),
                    ("기술", "skill_reason"),
                    ("공감도", "empathy_reason"),
                    ("명확성", "clarity_reason"),
                    ("친절도", "kindness_reason"),
                    ("자신감", "confidence_reason")
                ]
                
                for name, attr in reason_attrs:
                    reason1 = getattr(eval1, attr, "")
                    reason2 = getattr(eval2, attr, "")
                    if reason1 != reason2:
                        print(f"\n  {name} 이유:")
                        print(f"    시뮬레이션 1: {reason1[:100] if reason1 else '없음'}...")
                        print(f"    시뮬레이션 2: {reason2[:100] if reason2 else '없음'}...")
            else:
                print(f"\n✅ 모든 역량 점수가 동일합니다.")
            
            # detail_json 비교
            if eval1.detail_json and eval2.detail_json:
                try:
                    detail1 = json.loads(eval1.detail_json)
                    detail2 = json.loads(eval2.detail_json)
                    
                    print(f"\n[상세 정보 비교]")
                    for key in ["knowledge", "skill", "empathy", "clarity", "kindness", "confidence"]:
                        if key in detail1 and key in detail2:
                            if detail1[key] != detail2[key]:
                                print(f"\n  {key} 상세 정보 차이:")
                                print(f"    시뮬레이션 1: {json.dumps(detail1[key], ensure_ascii=False, indent=2)[:200]}...")
                                print(f"    시뮬레이션 2: {json.dumps(detail2[key], ensure_ascii=False, indent=2)[:200]}...")
                except Exception as e:
                    print(f"  ⚠️ 상세 정보 비교 실패: {e}")

if __name__ == "__main__":
    analyze_test_mode_consistency()

