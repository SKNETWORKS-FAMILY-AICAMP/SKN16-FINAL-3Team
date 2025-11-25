#!/usr/bin/env python3
"""
시뮬레이션 DB에 저장된 데이터 확인 스크립트
"""
from sqlmodel import Session, select
from app.database import engine
from app.models.rag_simulation import RAGSimulationSession, RAGSimulationTurn, RAGSimulationEvaluation

def check_simulation_data():
    """시뮬레이션 DB 데이터 확인"""
    with Session(engine) as session:
        # 세션 데이터 확인
        sessions = session.exec(select(RAGSimulationSession)).all()
        print(f"\n{'='*60}")
        print(f"📊 RAG 시뮬레이션 세션 데이터")
        print(f"{'='*60}")
        print(f"총 세션 수: {len(sessions)}개\n")
        
        if len(sessions) == 0:
            print("⚠️ 저장된 시뮬레이션 세션이 없습니다.")
            return
        
        # 최근 10개 세션 상세 정보
        print("최근 세션 목록:")
        print("-" * 60)
        for idx, s in enumerate(sessions[:10], 1):
            print(f"\n{idx}. Session ID: {s.id}")
            print(f"   Session Key: {s.session_key}")
            print(f"   User ID: {s.user_id}")
            print(f"   Persona ID: {s.persona_id}")
            print(f"   Scenario ID: {s.scenario_id}")
            print(f"   Started At: {s.started_at}")
            print(f"   Ended At: {s.ended_at}")
            print(f"   Total Turns: {s.total_turns}")
            print(f"   Is Completed: {s.is_completed}")
            print(f"   Duration: {s.duration_seconds}초" if s.duration_seconds else "   Duration: N/A")
        
        # 턴 데이터 확인
        turns = session.exec(select(RAGSimulationTurn)).all()
        print(f"\n{'='*60}")
        print(f"📊 RAG 시뮬레이션 턴 데이터")
        print(f"{'='*60}")
        print(f"총 턴 수: {len(turns)}개\n")
        
        if len(turns) > 0:
            # 세션별 턴 수 집계
            from collections import defaultdict
            turns_by_session = defaultdict(int)
            for turn in turns:
                turns_by_session[turn.session_id] += 1
            
            print("세션별 턴 수:")
            for session_id, count in list(turns_by_session.items())[:10]:
                print(f"  Session {session_id}: {count}턴")
        
        # 평가 데이터 확인
        evaluations = session.exec(select(RAGSimulationEvaluation)).all()
        print(f"\n{'='*60}")
        print(f"📊 RAG 시뮬레이션 평가 데이터")
        print(f"{'='*60}")
        print(f"총 평가 수: {len(evaluations)}개\n")
        
        if len(evaluations) > 0:
            print("최근 평가 목록:")
            print("-" * 60)
            for idx, eval in enumerate(evaluations[:5], 1):
                print(f"\n{idx}. Evaluation ID: {eval.id}")
                print(f"   Session ID: {eval.session_id}")
                print(f"   User ID: {eval.user_id}")
                print(f"   Total Point: {eval.total_point}")
                print(f"   Grade: {eval.grade}")
                print(f"   Created At: {eval.created_at}")
        
        print(f"\n{'='*60}\n")

if __name__ == "__main__":
    check_simulation_data()

