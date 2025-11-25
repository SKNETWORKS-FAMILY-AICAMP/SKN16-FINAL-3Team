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
        
        # Migration 6: rag_simulation_sessions에 persona_info 컬럼 추가
        try:
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'rag_simulation_sessions' 
                AND column_name = 'persona_info'
            """))
            
            if not result.fetchone():
                print("\n📊 Migration 6: rag_simulation_sessions에 persona_info 컬럼 추가 중...")
                conn.execute(text("""
                    ALTER TABLE rag_simulation_sessions 
                    ADD COLUMN persona_info TEXT
                """))
                conn.commit()
                print("   ✅ persona_info 컬럼 추가 완료")
                migrations_applied += 1
            else:
                print("\n✓ Migration 6: persona_info 컬럼 이미 존재 (rag_simulation_sessions)")
        except Exception as e:
            print(f"\n⚠️ Migration 6 실패: {e}")
        
        # Migration 7: rag_simulation_sessions에 situation_info 컬럼 추가
        try:
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'rag_simulation_sessions' 
                AND column_name = 'situation_info'
            """))
            
            if not result.fetchone():
                print("\n📊 Migration 7: rag_simulation_sessions에 situation_info 컬럼 추가 중...")
                conn.execute(text("""
                    ALTER TABLE rag_simulation_sessions 
                    ADD COLUMN situation_info TEXT
                """))
                conn.commit()
                print("   ✅ situation_info 컬럼 추가 완료")
                migrations_applied += 1
            else:
                print("\n✓ Migration 7: situation_info 컬럼 이미 존재 (rag_simulation_sessions)")
        except Exception as e:
            print(f"\n⚠️ Migration 7 실패: {e}")
        
        # Migration 8: rag_simulation_sessions에 goal_achievement_data 컬럼 추가
        try:
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'rag_simulation_sessions' 
                AND column_name = 'goal_achievement_data'
            """))
            
            if not result.fetchone():
                print("\n📊 Migration 8: rag_simulation_sessions에 goal_achievement_data 컬럼 추가 중...")
                conn.execute(text("""
                    ALTER TABLE rag_simulation_sessions 
                    ADD COLUMN goal_achievement_data TEXT
                """))
                conn.commit()
                print("   ✅ goal_achievement_data 컬럼 추가 완료")
                migrations_applied += 1
            else:
                print("\n✓ Migration 8: goal_achievement_data 컬럼 이미 존재 (rag_simulation_sessions)")
        except Exception as e:
            print(f"\n⚠️ Migration 8 실패: {e}")
        
        # Migration 9: simulation_feedbacks에 rag_evaluations 컬럼 추가
        try:
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'simulation_feedbacks' 
                AND column_name = 'rag_evaluations'
            """))
            
            if not result.fetchone():
                print("\n📊 Migration 9: simulation_feedbacks에 rag_evaluations 컬럼 추가 중...")
                conn.execute(text("""
                    ALTER TABLE simulation_feedbacks 
                    ADD COLUMN rag_evaluations TEXT
                """))
                conn.commit()
                print("   ✅ rag_evaluations 컬럼 추가 완료")
                migrations_applied += 1
            else:
                print("\n✓ Migration 9: rag_evaluations 컬럼 이미 존재")
        except Exception as e:
            print(f"\n⚠️ Migration 9 실패: {e}")
        
        # Migration 10: simulation_feedbacks에 rag_summary 컬럼 추가
        try:
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'simulation_feedbacks' 
                AND column_name = 'rag_summary'
            """))
            
            if not result.fetchone():
                print("\n📊 Migration 10: simulation_feedbacks에 rag_summary 컬럼 추가 중...")
                conn.execute(text("""
                    ALTER TABLE simulation_feedbacks 
                    ADD COLUMN rag_summary TEXT
                """))
                conn.commit()
                print("   ✅ rag_summary 컬럼 추가 완료")
                migrations_applied += 1
            else:
                print("\n✓ Migration 10: rag_summary 컬럼 이미 존재")
        except Exception as e:
            print(f"\n⚠️ Migration 10 실패: {e}")

        # Migration 11: training_center_records.employee_type 추가
        try:
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'training_center_records' 
                AND column_name = 'employee_type'
            """))

            if not result.fetchone():
                print("\n📊 Migration 11: training_center_records.employee_type 추가 중...")
                conn.execute(text("""
                    ALTER TABLE training_center_records 
                    ADD COLUMN employee_type VARCHAR(20) DEFAULT 'mentee'
                """))
                conn.execute(text("""
                    UPDATE training_center_records SET employee_type = 'mentee' WHERE employee_type IS NULL
                """))
                conn.commit()
                print("   ✅ employee_type 컬럼 추가 완료")
                migrations_applied += 1
            else:
                print("\n✓ Migration 11: employee_type 컬럼 이미 존재")
        except Exception as e:
            print(f"\n⚠️ Migration 11 실패: {e}")

        # Migration 12: training_center_records.city 추가
        try:
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'training_center_records' 
                AND column_name = 'city'
            """))

            if not result.fetchone():
                print("\n📊 Migration 12: training_center_records.city 추가 중...")
                conn.execute(text("""
                    ALTER TABLE training_center_records 
                    ADD COLUMN city VARCHAR(50)
                """))
                conn.commit()
                print("   ✅ city 컬럼 추가 완료")
                migrations_applied += 1
            else:
                print("\n✓ Migration 12: city 컬럼 이미 존재")
        except Exception as e:
            print(f"\n⚠️ Migration 12 실패: {e}")

        # Migration 13: training_center_records.hobbies 추가
        try:
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'training_center_records' 
                AND column_name = 'hobbies'
            """))

            if not result.fetchone():
                print("\n📊 Migration 13: training_center_records.hobbies 추가 중...")
                conn.execute(text("""
                    ALTER TABLE training_center_records 
                    ADD COLUMN hobbies JSONB DEFAULT '[]'::jsonb
                """))
                conn.commit()
                print("   ✅ hobbies 컬럼 추가 완료")
                migrations_applied += 1
            else:
                print("\n✓ Migration 13: hobbies 컬럼 이미 존재")
        except Exception as e:
            print(f"\n⚠️ Migration 13 실패: {e}")

        # Migration 14: simulation_feedbacks에 persona_fit_score 컬럼 추가
        try:
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'simulation_feedbacks' 
                AND column_name = 'persona_fit_score'
            """))

            if not result.fetchone():
                print("\n📊 Migration 14: simulation_feedbacks에 persona_fit_score 컬럼 추가 중...")
                conn.execute(text("""
                    ALTER TABLE simulation_feedbacks 
                    ADD COLUMN persona_fit_score INTEGER DEFAULT 0 CHECK (persona_fit_score >= 0 AND persona_fit_score <= 100)
                """))
                conn.commit()
                print("   ✅ persona_fit_score 컬럼 추가 완료")
                migrations_applied += 1
            else:
                print("\n✓ Migration 14: persona_fit_score 컬럼 이미 존재")
        except Exception as e:
            print(f"\n⚠️ Migration 14 실패: {e}")

        # Migration 15: simulation_feedbacks에 persona_fit_feedback 컬럼 추가
        try:
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'simulation_feedbacks' 
                AND column_name = 'persona_fit_feedback'
            """))

            if not result.fetchone():
                print("\n📊 Migration 15: simulation_feedbacks에 persona_fit_feedback 컬럼 추가 중...")
                conn.execute(text("""
                    ALTER TABLE simulation_feedbacks 
                    ADD COLUMN persona_fit_feedback TEXT
                """))
                conn.commit()
                print("   ✅ persona_fit_feedback 컬럼 추가 완료")
                migrations_applied += 1
            else:
                print("\n✓ Migration 15: persona_fit_feedback 컬럼 이미 존재")
        except Exception as e:
            print(f"\n⚠️ Migration 15 실패: {e}")
        
        # Migration 14: simulation_feedbacks에 is_test_mode 컬럼 추가
        try:
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'simulation_feedbacks' 
                AND column_name = 'is_test_mode'
            """))
            
            if not result.fetchone():
                print("\n📊 Migration 14: simulation_feedbacks에 is_test_mode 컬럼 추가 중...")
                conn.execute(text("""
                    ALTER TABLE simulation_feedbacks 
                    ADD COLUMN is_test_mode BOOLEAN DEFAULT FALSE
                """))
                conn.execute(text("""
                    UPDATE simulation_feedbacks 
                    SET is_test_mode = FALSE 
                    WHERE is_test_mode IS NULL
                """))
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_simulation_feedbacks_is_test_mode 
                    ON simulation_feedbacks(is_test_mode)
                """))
                conn.commit()
                print("   ✅ is_test_mode 컬럼 및 인덱스 추가 완료")
                migrations_applied += 1
            else:
                print("\n✓ Migration 14: is_test_mode 컬럼 이미 존재")
        except Exception as e:
            print(f"\n⚠️ Migration 14 실패: {e}")
        
        # 여기에 추가 마이그레이션을 계속 추가할 수 있습니다
    
    print("\n" + "=" * 80)
    if migrations_applied > 0:
        print(f"🎉 {migrations_applied}개의 마이그레이션이 적용되었습니다!")
    else:
        print("✅ DB 스키마가 최신 상태입니다.")
    print("=" * 80 + "\n")

if __name__ == "__main__":
    run_migrations()

