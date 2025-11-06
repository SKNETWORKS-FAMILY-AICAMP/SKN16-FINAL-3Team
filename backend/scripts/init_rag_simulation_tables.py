"""
RAG 시뮬레이션 DB 테이블 초기화 스크립트
"""
from sqlmodel import SQLModel, create_engine, Session
from app.models.rag_simulation import (
    RAGSimulationSession,
    RAGSimulationTurn,
    RAGSimulationEvaluation
)
from app.database import engine
import sys


def create_rag_simulation_tables():
    """RAG 시뮬레이션 테이블 생성"""
    try:
        print("📊 RAG 시뮬레이션 테이블 생성 중...")
        
        # 테이블 생성
        SQLModel.metadata.create_all(engine, tables=[
            RAGSimulationSession.__table__,
            RAGSimulationTurn.__table__,
            RAGSimulationEvaluation.__table__
        ])
        
        print("✅ RAG 시뮬레이션 테이블 생성 완료!")
        print("   - rag_simulation_sessions")
        print("   - rag_simulation_turns")
        print("   - rag_simulation_evaluations")
        
        return True
        
    except Exception as e:
        print(f"❌ 테이블 생성 실패: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = create_rag_simulation_tables()
    sys.exit(0 if success else 1)

