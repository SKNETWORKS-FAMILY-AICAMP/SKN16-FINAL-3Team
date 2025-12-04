"""
고아 계정 정리 스크립트
"""
import sys
import os

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'backend')))

from app.database import Session, engine
from app.services.training_center_service import TrainingCenterService

def main():
    """고아 계정 정리 실행"""
    session = Session(engine)
    try:
        service = TrainingCenterService(session)
        deleted_count = service.cleanup_orphan_users()
        print(f"✅ {deleted_count}개의 고아 계정이 삭제되었습니다.")
        return deleted_count
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        session.rollback()
        return 0
    finally:
        session.close()

if __name__ == "__main__":
    main()


