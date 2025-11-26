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

        # Migration 14: training_center_records.hobbies → hobby1, hobby2 변경
        try:
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'training_center_records' 
                AND column_name = 'hobby1'
            """))

            if not result.fetchone():
                print("\n📊 Migration 14: training_center_records.hobby1, hobby2 추가 중...")
                # hobby1, hobby2 컬럼 추가
                conn.execute(text("""
                    ALTER TABLE training_center_records 
                    ADD COLUMN hobby1 VARCHAR(50)
                """))
                conn.execute(text("""
                    ALTER TABLE training_center_records 
                    ADD COLUMN hobby2 VARCHAR(50)
                """))
                # 기존 hobbies 데이터를 hobby1, hobby2로 마이그레이션
                conn.execute(text("""
                    UPDATE training_center_records 
                    SET hobby1 = (hobbies->>0)::VARCHAR(50),
                        hobby2 = (hobbies->>1)::VARCHAR(50)
                    WHERE hobbies IS NOT NULL AND jsonb_array_length(hobbies) > 0
                """))
                # hobbies 컬럼 삭제 (선택사항 - 필요시 주석 처리)
                # conn.execute(text("""
                #     ALTER TABLE training_center_records 
                #     DROP COLUMN hobbies
                # """))
                conn.commit()
                print("   ✅ hobby1, hobby2 컬럼 추가 및 데이터 마이그레이션 완료")
                migrations_applied += 1
            else:
                print("\n✓ Migration 14: hobby1, hobby2 컬럼 이미 존재")
        except Exception as e:
            print(f"\n⚠️ Migration 14 실패: {e}")

        # Migration 15: simulation_feedbacks에 persona_fit_score 컬럼 추가
        try:
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'simulation_feedbacks' 
                AND column_name = 'persona_fit_score'
            """))

            if not result.fetchone():
                print("\n📊 Migration 15: simulation_feedbacks에 persona_fit_score 컬럼 추가 중...")
                conn.execute(text("""
                    ALTER TABLE simulation_feedbacks 
                    ADD COLUMN persona_fit_score INTEGER DEFAULT 0 CHECK (persona_fit_score >= 0 AND persona_fit_score <= 100)
                """))
                conn.commit()
                print("   ✅ persona_fit_score 컬럼 추가 완료")
                migrations_applied += 1
            else:
                print("\n✓ Migration 15: persona_fit_score 컬럼 이미 존재")
        except Exception as e:
            print(f"\n⚠️ Migration 15 실패: {e}")

        # Migration 16: simulation_feedbacks에 persona_fit_feedback 컬럼 추가
        try:
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'simulation_feedbacks' 
                AND column_name = 'persona_fit_feedback'
            """))

            if not result.fetchone():
                print("\n📊 Migration 16: simulation_feedbacks에 persona_fit_feedback 컬럼 추가 중...")
                conn.execute(text("""
                    ALTER TABLE simulation_feedbacks 
                    ADD COLUMN persona_fit_feedback TEXT
                """))
                conn.commit()
                print("   ✅ persona_fit_feedback 컬럼 추가 완료")
                migrations_applied += 1
            else:
                print("\n✓ Migration 16: persona_fit_feedback 컬럼 이미 존재")
        except Exception as e:
            print(f"\n⚠️ Migration 16 실패: {e}")

        # Migration 17: matching_results, matching_reports 테이블은 SQLModel이 자동 생성
        # 별도 마이그레이션 불필요 (init_db에서 자동 생성됨)
        
        # Migration 18: training_center_records에 major, career_goal 컬럼 추가
        try:
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'training_center_records' 
                AND column_name = 'major'
            """))

            if not result.fetchone():
                print("\n📊 Migration 18: training_center_records에 major, career_goal 추가 중...")
                conn.execute(text("""
                    ALTER TABLE training_center_records 
                    ADD COLUMN major VARCHAR(50)
                """))
                conn.execute(text("""
                    ALTER TABLE training_center_records 
                    ADD COLUMN career_goal VARCHAR(100)
                """))
                conn.commit()
                print("   ✅ major, career_goal 컬럼 추가 완료")
                migrations_applied += 1
            else:
                print("\n✓ Migration 18: major, career_goal 컬럼 이미 존재")
        except Exception as e:
            print(f"\n⚠️ Migration 18 실패: {e}")

        # Migration 19: matching_results에 새로운 점수 컬럼 추가
        try:
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'matching_results' 
                AND column_name = 'weakness_strength_score'
            """))

            if not result.fetchone():
                print("\n📊 Migration 19: matching_results에 새로운 점수 컬럼 추가 중...")
                conn.execute(text("""
                    ALTER TABLE matching_results 
                    ADD COLUMN weakness_strength_score FLOAT DEFAULT 0.0
                """))
                conn.execute(text("""
                    ALTER TABLE matching_results 
                    ADD COLUMN career_score FLOAT DEFAULT 0.0
                """))
                conn.execute(text("""
                    ALTER TABLE matching_results 
                    ADD COLUMN major_score FLOAT DEFAULT 0.0
                """))
                conn.commit()
                print("   ✅ weakness_strength_score, career_score, major_score 컬럼 추가 완료")
                migrations_applied += 1
            else:
                print("\n✓ Migration 19: 새로운 점수 컬럼 이미 존재")
        except Exception as e:
            print(f"\n⚠️ Migration 19 실패: {e}")

        # Migration 20: training_center_records에 gender 컬럼 추가
        try:
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'training_center_records' 
                AND column_name = 'gender'
            """))

            if not result.fetchone():
                print("\n📊 Migration 20: training_center_records에 gender 컬럼 추가 중...")
                conn.execute(text("""
                    ALTER TABLE training_center_records 
                    ADD COLUMN gender VARCHAR(10)
                """))
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS ix_training_center_records_gender 
                    ON training_center_records(gender)
                """))
                conn.commit()
                print("   ✅ gender 컬럼 추가 완료")
                migrations_applied += 1
            else:
                print("\n✓ Migration 20: gender 컬럼 이미 존재")
        except Exception as e:
            print(f"\n⚠️ Migration 20 실패: {e}")

        # Migration 21: simulation_feedbacks에 is_test_mode 컬럼 추가
        try:
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'simulation_feedbacks' 
                AND column_name = 'is_test_mode'
            """))
            
            if not result.fetchone():
                print("\n📊 Migration 21: simulation_feedbacks에 is_test_mode 컬럼 추가 중...")
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
                print("\n✓ Migration 21: is_test_mode 컬럼 이미 존재")
        except Exception as e:
            print(f"\n⚠️ Migration 21 실패: {e}")
        
        # Migration 22: simulation_feedbacks에 empathy_score 컬럼 추가
        try:
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'simulation_feedbacks' 
                AND column_name = 'empathy_score'
            """))
            
            if not result.fetchone():
                print("\n📊 Migration 22: simulation_feedbacks에 empathy_score 컬럼 추가 중...")
                conn.execute(text("""
                    ALTER TABLE simulation_feedbacks 
                    ADD COLUMN empathy_score INTEGER DEFAULT 0 CHECK (empathy_score >= 0 AND empathy_score <= 100)
                """))
                conn.commit()
                print("   ✅ empathy_score 컬럼 추가 완료")
                migrations_applied += 1
            else:
                print("\n✓ Migration 22: empathy_score 컬럼 이미 존재")
        except Exception as e:
            print(f"\n⚠️ Migration 22 실패: {e}")
        
        # Migration 23: simulation_feedbacks에 empathy_feedback 컬럼 추가
        try:
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'simulation_feedbacks' 
                AND column_name = 'empathy_feedback'
            """))
            
            if not result.fetchone():
                print("\n📊 Migration 23: simulation_feedbacks에 empathy_feedback 컬럼 추가 중...")
                conn.execute(text("""
                    ALTER TABLE simulation_feedbacks 
                    ADD COLUMN empathy_feedback TEXT
                """))
                conn.commit()
                print("   ✅ empathy_feedback 컬럼 추가 완료")
                migrations_applied += 1
            else:
                print("\n✓ Migration 23: empathy_feedback 컬럼 이미 존재")
        except Exception as e:
            print(f"\n⚠️ Migration 23 실패: {e}")
        
        # Migration 24: simulation_feedbacks에 persona_age_group 컬럼 추가
        try:
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'simulation_feedbacks' 
                AND column_name = 'persona_age_group'
            """))
            
            if not result.fetchone():
                print("\n📊 Migration 24: simulation_feedbacks에 persona_age_group 컬럼 추가 중...")
                conn.execute(text("""
                    ALTER TABLE simulation_feedbacks 
                    ADD COLUMN persona_age_group VARCHAR(50)
                """))
                conn.commit()
                print("   ✅ persona_age_group 컬럼 추가 완료")
                migrations_applied += 1
            else:
                print("\n✓ Migration 24: persona_age_group 컬럼 이미 존재")
        except Exception as e:
            print(f"\n⚠️ Migration 24 실패: {e}")
        
        # Migration 25: simulation_feedbacks에 persona_gender 컬럼 추가
        try:
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'simulation_feedbacks' 
                AND column_name = 'persona_gender'
            """))
            
            if not result.fetchone():
                print("\n📊 Migration 25: simulation_feedbacks에 persona_gender 컬럼 추가 중...")
                conn.execute(text("""
                    ALTER TABLE simulation_feedbacks 
                    ADD COLUMN persona_gender VARCHAR(20)
                """))
                conn.commit()
                print("   ✅ persona_gender 컬럼 추가 완료")
                migrations_applied += 1
            else:
                print("\n✓ Migration 25: persona_gender 컬럼 이미 존재")
        except Exception as e:
            print(f"\n⚠️ Migration 25 실패: {e}")
        
        # Migration 26: simulation_feedbacks에 persona_occupation 컬럼 추가
        try:
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'simulation_feedbacks' 
                AND column_name = 'persona_occupation'
            """))
            
            if not result.fetchone():
                print("\n📊 Migration 26: simulation_feedbacks에 persona_occupation 컬럼 추가 중...")
                conn.execute(text("""
                    ALTER TABLE simulation_feedbacks 
                    ADD COLUMN persona_occupation VARCHAR(50)
                """))
                conn.commit()
                print("   ✅ persona_occupation 컬럼 추가 완료")
                migrations_applied += 1
            else:
                print("\n✓ Migration 26: persona_occupation 컬럼 이미 존재")
        except Exception as e:
            print(f"\n⚠️ Migration 26 실패: {e}")
        
        # Migration 27: simulation_feedbacks에 persona_customer_style 컬럼 추가
        try:
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'simulation_feedbacks' 
                AND column_name = 'persona_customer_style'
            """))
            
            if not result.fetchone():
                print("\n📊 Migration 27: simulation_feedbacks에 persona_customer_style 컬럼 추가 중...")
                conn.execute(text("""
                    ALTER TABLE simulation_feedbacks 
                    ADD COLUMN persona_customer_style VARCHAR(50)
                """))
                conn.commit()
                print("   ✅ persona_customer_style 컬럼 추가 완료")
                migrations_applied += 1
            else:
                print("\n✓ Migration 27: persona_customer_style 컬럼 이미 존재")
        except Exception as e:
            print(f"\n⚠️ Migration 27 실패: {e}")
        
        # Migration 28: personas 테이블 생성
        try:
            result = conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'personas'
            """))
            
            if not result.fetchone():
                print("\n📊 Migration 28: personas 테이블 생성 중...")
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS public.personas (
                        id VARCHAR(50) PRIMARY KEY,
                        gender VARCHAR(10) NOT NULL,
                        age_group VARCHAR(20) NOT NULL,
                        occupation VARCHAR(50) NOT NULL,
                        customer_style VARCHAR(20) NOT NULL,
                        speech_tone VARCHAR(100),
                        speech_speed VARCHAR(20),
                        tts_temperature FLOAT,
                        utterance_hints TEXT[],
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                conn.commit()
                print("   ✅ personas 테이블 생성 완료")
                migrations_applied += 1
            else:
                # 테이블이 이미 있으면 updated_at 컬럼 확인 및 추가
                result = conn.execute(text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'personas' 
                    AND column_name = 'updated_at'
                """))
                
                if not result.fetchone():
                    print("\n📊 Migration 28: personas 테이블에 updated_at 컬럼 추가 중...")
                    conn.execute(text("""
                        ALTER TABLE public.personas 
                        ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    """))
                    conn.commit()
                    print("   ✅ updated_at 컬럼 추가 완료")
                    migrations_applied += 1
                else:
                    print("\n✓ Migration 28: personas 테이블 이미 존재")
        except Exception as e:
            print(f"\n⚠️ Migration 28 실패: {e}")
        
        # Migration 29: personas_expanded_minified2.json 데이터를 personas 테이블에 삽입
        try:
            import os
            import json as json_module
            from pathlib import Path
            
            # JSON 파일 경로
            json_path = Path(__file__).parent.parent / "data" / "personas_expanded_minified2.json"
            
            if json_path.exists():
                # 기존 데이터 확인
                result = conn.execute(text("""
                    SELECT COUNT(*) FROM personas
                """))
                existing_count = result.fetchone()[0]
                
                if existing_count == 0:
                    print("\n📊 Migration 29: personas_expanded_minified2.json 데이터 삽입 중...")
                    
                    # JSON 파일 읽기
                    with open(json_path, 'r', encoding='utf-8') as f:
                        data = json_module.load(f)
                    
                    personas_list = data.get("personas", [])
                    inserted_count = 0
                    
                    for persona_data in personas_list:
                        try:
                            # utterance_hints 배열을 PostgreSQL 배열 형식으로 변환
                            utterance_hints = persona_data.get("utterance_hints", [])
                            # PostgreSQL 배열 리터럴 형식: ARRAY['item1', 'item2']
                            if utterance_hints:
                                # 각 항목을 이스케이프 처리
                                escaped_hints = [hint.replace("'", "''") for hint in utterance_hints]
                                utterance_hints_sql = "ARRAY[" + ",".join([f"'{hint}'" for hint in escaped_hints]) + "]"
                            else:
                                utterance_hints_sql = "ARRAY[]::TEXT[]"
                            
                            # speech 객체에서 데이터 추출
                            speech = persona_data.get("speech", {})
                            speech_tone = speech.get("tone", "").replace("'", "''") if speech.get("tone") else ""
                            speech_speed = speech.get("speed", "").replace("'", "''") if speech.get("speed") else ""
                            tts_temperature = speech.get("tts_temperature", 0.5)
                            
                            # 데이터 삽입 (SQL 문자열 직접 구성 - 파라미터 바인딩 대신)
                            id_val = persona_data.get("id", "").replace("'", "''")
                            gender_val = persona_data.get("gender", "").replace("'", "''")
                            age_group_val = persona_data.get("age_group", "").replace("'", "''")
                            occupation_val = persona_data.get("occupation", "").replace("'", "''")
                            customer_style_val = persona_data.get("customer_style", "").replace("'", "''")
                            
                            sql = f"""
                                INSERT INTO personas (
                                    id, gender, age_group, occupation, customer_style,
                                    speech_tone, speech_speed, tts_temperature, utterance_hints
                                ) VALUES (
                                    '{id_val}', '{gender_val}', '{age_group_val}', '{occupation_val}', '{customer_style_val}',
                                    '{speech_tone}', '{speech_speed}', {tts_temperature}, {utterance_hints_sql}
                                )
                                ON CONFLICT (id) DO NOTHING
                            """
                            conn.execute(text(sql))
                            inserted_count += 1
                        except Exception as e:
                            print(f"   ⚠️ 페르소나 {persona_data.get('id', 'unknown')} 삽입 실패: {e}")
                            continue
                    
                    conn.commit()
                    print(f"   ✅ {inserted_count}개의 페르소나 데이터 삽입 완료")
                    migrations_applied += 1
                else:
                    print(f"\n✓ Migration 29: personas 테이블에 이미 {existing_count}개의 데이터가 존재합니다")
            else:
                print(f"\n⚠️ Migration 29: JSON 파일을 찾을 수 없습니다: {json_path}")
        except Exception as e:
            print(f"\n⚠️ Migration 29 실패: {e}")
            import traceback
            traceback.print_exc()
        
        # 여기에 추가 마이그레이션을 계속 추가할 수 있습니다
    
    print("\n" + "=" * 80)
    if migrations_applied > 0:
        print(f"🎉 {migrations_applied}개의 마이그레이션이 적용되었습니다!")
    else:
        print("✅ DB 스키마가 최신 상태입니다.")
    print("=" * 80 + "\n")

if __name__ == "__main__":
    run_migrations()

