"""
conversation_log 컬럼 마이그레이션
다른 개발자들이 git pull 후 이 스크립트를 실행해야 합니다.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlmodel import create_engine
from sqlalchemy import text
from app.config import settings

def migrate():
    """conversation_log 컬럼 추가"""
    engine = create_engine(str(settings.DATABASE_URL))
    
    print("=" * 80)
    print("🔄 DB 마이그레이션: conversation_log 컬럼 추가")
    print("=" * 80)
    
    with engine.connect() as conn:
        # 컬럼 존재 여부 확인
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'simulation_feedbacks' 
            AND column_name = 'conversation_log'
        """))
        
        if result.fetchone():
            print("\n✅ conversation_log 컬럼이 이미 존재합니다.")
            print("   마이그레이션이 필요하지 않습니다.")
            return
        
        # 컬럼 추가
        print("\n📊 conversation_log 컬럼 추가 중...")
        try:
            conn.execute(text("""
                ALTER TABLE simulation_feedbacks 
                ADD COLUMN conversation_log TEXT
            """))
            conn.commit()
            print("✅ conversation_log 컬럼 추가 완료!")
            print("\n📝 참고:")
            print("   - 대화 로그가 JSON 문자열 형식으로 저장됩니다.")
            print("   - 기존 데이터는 NULL 값으로 유지됩니다.")
            print("   - 새로운 시뮬레이션부터 대화 로그가 저장됩니다.")
        except Exception as e:
            print(f"❌ 마이그레이션 실패: {e}")
            raise
    
    print("\n" + "=" * 80)
    print("🎉 마이그레이션 완료!")
    print("=" * 80)

if __name__ == "__main__":
    migrate()

