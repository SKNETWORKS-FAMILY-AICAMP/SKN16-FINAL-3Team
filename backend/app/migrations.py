"""
자동 DB 마이그레이션 모듈
백엔드 시작 시 자동으로 실행되어 DB 스키마를 최신 상태로 유지
"""
from sqlalchemy import text
from sqlmodel import create_engine
from app.config import settings

def run_migrations():
    """
    모든 마이그레이션을 순차적으로 실행
    멱등성 보장 - 여러 번 실행해도 안전
    """
    engine = create_engine(str(settings.DATABASE_URL))
    
    print("\n" + "=" * 80)
    print("🔄 DB 마이그레이션 체크 시작...")
    print("=" * 80)
    
    migrations_applied = 0
    
    with engine.connect() as conn:
        # Migration 1: conversation_log 컬럼 추가
        try:
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'simulation_feedbacks' 
                AND column_name = 'conversation_log'
            """))
            
            if not result.fetchone():
                print("\n📊 Migration 1: conversation_log 컬럼 추가 중...")
                conn.execute(text("""
                    ALTER TABLE simulation_feedbacks 
                    ADD COLUMN conversation_log TEXT
                """))
                conn.commit()
                print("   ✅ conversation_log 컬럼 추가 완료")
                migrations_applied += 1
            else:
                print("\n✓ Migration 1: conversation_log 컬럼 이미 존재")
        except Exception as e:
            print(f"\n⚠️ Migration 1 실패: {e}")
        
        # Migration 2: goal_achievement_data 컬럼 추가
        try:
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'simulation_feedbacks' 
                AND column_name = 'goal_achievement_data'
            """))
            
            if not result.fetchone():
                print("\n📊 Migration 2: goal_achievement_data 컬럼 추가 중...")
                conn.execute(text("""
                    ALTER TABLE simulation_feedbacks 
                    ADD COLUMN goal_achievement_data TEXT
                """))
                conn.commit()
                print("   ✅ goal_achievement_data 컬럼 추가 완료")
                migrations_applied += 1
            else:
                print("\n✓ Migration 2: goal_achievement_data 컬럼 이미 존재")
        except Exception as e:
            print(f"\n⚠️ Migration 2 실패: {e}")
        
        # Migration 3: persona_info 컬럼 추가
        try:
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'simulation_feedbacks' 
                AND column_name = 'persona_info'
            """))
            
            if not result.fetchone():
                print("\n📊 Migration 3: persona_info 컬럼 추가 중...")
                conn.execute(text("""
                    ALTER TABLE simulation_feedbacks 
                    ADD COLUMN persona_info VARCHAR(200)
                """))
                conn.commit()
                print("   ✅ persona_info 컬럼 추가 완료")
                migrations_applied += 1
            else:
                print("\n✓ Migration 3: persona_info 컬럼 이미 존재")
        except Exception as e:
            print(f"\n⚠️ Migration 3 실패: {e}")
        
        # Migration 4: situation_info 컬럼 추가
        try:
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'simulation_feedbacks' 
                AND column_name = 'situation_info'
            """))
            
            if not result.fetchone():
                print("\n📊 Migration 4: situation_info 컬럼 추가 중...")
                conn.execute(text("""
                    ALTER TABLE simulation_feedbacks 
                    ADD COLUMN situation_info VARCHAR(100)
                """))
                conn.commit()
                print("   ✅ situation_info 컬럼 추가 완료")
                migrations_applied += 1
            else:
                print("\n✓ Migration 4: situation_info 컬럼 이미 존재")
        except Exception as e:
            print(f"\n⚠️ Migration 4 실패: {e}")
        
        # Migration 5: is_company_schedule 컬럼 추가 (schedules 테이블)
        try:
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'schedules' 
                AND column_name = 'is_company_schedule'
            """))
            
            if not result.fetchone():
                print("\n📊 Migration 5: is_company_schedule 컬럼 추가 중...")
                conn.execute(text("""
                    ALTER TABLE schedules 
                    ADD COLUMN is_company_schedule BOOLEAN DEFAULT FALSE
                """))
                conn.commit()
                print("   ✅ is_company_schedule 컬럼 추가 완료")
                migrations_applied += 1
            else:
                print("\n✓ Migration 5: is_company_schedule 컬럼 이미 존재")
        except Exception as e:
            print(f"\n⚠️ Migration 5 실패: {e}")
        
        # 여기에 추가 마이그레이션을 계속 추가할 수 있습니다
        # Migration 6: ...
    
    print("\n" + "=" * 80)
    if migrations_applied > 0:
        print(f"🎉 {migrations_applied}개의 마이그레이션이 적용되었습니다!")
    else:
        print("✅ DB 스키마가 최신 상태입니다.")
    print("=" * 80 + "\n")

if __name__ == "__main__":
    run_migrations()

