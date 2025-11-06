"""
시뮬레이션 피드백 테이블 초기화 스크립트
6가지 역량 평가 기반 피드백 저장
"""
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlmodel import SQLModel, create_engine, Session
from app.config import settings
from app.models.simulation_feedback import SimulationFeedback


def create_feedback_tables():
    """피드백 테이블 생성"""
    try:
        # 데이터베이스 연결
        engine = create_engine(str(settings.DATABASE_URL))
        
        print("📊 시뮬레이션 피드백 테이블 생성 중...")
        
        # 테이블 생성
        SQLModel.metadata.create_all(engine, tables=[SimulationFeedback.__table__])
        
        print("✅ 피드백 테이블 생성 완료!")
        print(f"   - simulation_feedbacks")
        
        return True
        
    except Exception as e:
        print(f"❌ 테이블 생성 실패: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = create_feedback_tables()
    if success:
        print("\n🎉 피드백 히스토리 기능을 사용할 수 있습니다!")
        sys.exit(0)
    else:
        print("\n❌ 테이블 생성에 실패했습니다.")
        sys.exit(1)

