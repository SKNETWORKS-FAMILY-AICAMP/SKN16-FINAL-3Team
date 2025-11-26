"""
DB 마이그레이션 스크립트
1. simulation_feedbacks 테이블에 새로운 필드 추가
   - empathy_score, empathy_feedback
   - persona_age_group, persona_gender, persona_occupation, persona_customer_style
2. personas 테이블 생성 (없는 경우)

다른 개발자들이 git pull 후 이 스크립트를 실행해야 합니다.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlmodel import create_engine
from sqlalchemy import text
from app.config import settings

def migrate():
    """simulation_feedbacks 테이블에 새로운 필드 추가"""
    engine = create_engine(str(settings.DATABASE_URL))
    
    print("=" * 80)
    print("🔄 DB 마이그레이션: simulation_feedbacks 테이블 필드 추가")
    print("=" * 80)
    
    migrations_applied = 0
    
    with engine.connect() as conn:
        # 1. empathy_score 컬럼 추가
        try:
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'simulation_feedbacks' 
                AND column_name = 'empathy_score'
            """))
            
            if not result.fetchone():
                print("\n📊 empathy_score 컬럼 추가 중...")
                conn.execute(text("""
                    ALTER TABLE simulation_feedbacks 
                    ADD COLUMN empathy_score INTEGER DEFAULT 0 CHECK (empathy_score >= 0 AND empathy_score <= 100)
                """))
                conn.commit()
                print("✅ empathy_score 컬럼 추가 완료")
                migrations_applied += 1
            else:
                print("\n✓ empathy_score 컬럼 이미 존재")
        except Exception as e:
            print(f"\n⚠️ empathy_score 추가 실패: {e}")
        
        # 2. empathy_feedback 컬럼 추가
        try:
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'simulation_feedbacks' 
                AND column_name = 'empathy_feedback'
            """))
            
            if not result.fetchone():
                print("\n📊 empathy_feedback 컬럼 추가 중...")
                conn.execute(text("""
                    ALTER TABLE simulation_feedbacks 
                    ADD COLUMN empathy_feedback TEXT
                """))
                conn.commit()
                print("✅ empathy_feedback 컬럼 추가 완료")
                migrations_applied += 1
            else:
                print("\n✓ empathy_feedback 컬럼 이미 존재")
        except Exception as e:
            print(f"\n⚠️ empathy_feedback 추가 실패: {e}")
        
        # 3. persona_age_group 컬럼 추가
        try:
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'simulation_feedbacks' 
                AND column_name = 'persona_age_group'
            """))
            
            if not result.fetchone():
                print("\n📊 persona_age_group 컬럼 추가 중...")
                conn.execute(text("""
                    ALTER TABLE simulation_feedbacks 
                    ADD COLUMN persona_age_group VARCHAR(50)
                """))
                conn.commit()
                print("✅ persona_age_group 컬럼 추가 완료")
                migrations_applied += 1
            else:
                print("\n✓ persona_age_group 컬럼 이미 존재")
        except Exception as e:
            print(f"\n⚠️ persona_age_group 추가 실패: {e}")
        
        # 4. persona_gender 컬럼 추가
        try:
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'simulation_feedbacks' 
                AND column_name = 'persona_gender'
            """))
            
            if not result.fetchone():
                print("\n📊 persona_gender 컬럼 추가 중...")
                conn.execute(text("""
                    ALTER TABLE simulation_feedbacks 
                    ADD COLUMN persona_gender VARCHAR(20)
                """))
                conn.commit()
                print("✅ persona_gender 컬럼 추가 완료")
                migrations_applied += 1
            else:
                print("\n✓ persona_gender 컬럼 이미 존재")
        except Exception as e:
            print(f"\n⚠️ persona_gender 추가 실패: {e}")
        
        # 5. persona_occupation 컬럼 추가
        try:
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'simulation_feedbacks' 
                AND column_name = 'persona_occupation'
            """))
            
            if not result.fetchone():
                print("\n📊 persona_occupation 컬럼 추가 중...")
                conn.execute(text("""
                    ALTER TABLE simulation_feedbacks 
                    ADD COLUMN persona_occupation VARCHAR(50)
                """))
                conn.commit()
                print("✅ persona_occupation 컬럼 추가 완료")
                migrations_applied += 1
            else:
                print("\n✓ persona_occupation 컬럼 이미 존재")
        except Exception as e:
            print(f"\n⚠️ persona_occupation 추가 실패: {e}")
        
        # 6. persona_customer_style 컬럼 추가
        try:
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'simulation_feedbacks' 
                AND column_name = 'persona_customer_style'
            """))
            
            if not result.fetchone():
                print("\n📊 persona_customer_style 컬럼 추가 중...")
                conn.execute(text("""
                    ALTER TABLE simulation_feedbacks 
                    ADD COLUMN persona_customer_style VARCHAR(50)
                """))
                conn.commit()
                print("✅ persona_customer_style 컬럼 추가 완료")
                migrations_applied += 1
            else:
                print("\n✓ persona_customer_style 컬럼 이미 존재")
        except Exception as e:
            print(f"\n⚠️ persona_customer_style 추가 실패: {e}")
        
        # 7. personas 테이블 생성
        try:
            result = conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'personas'
            """))
            
            if not result.fetchone():
                print("\n📊 personas 테이블 생성 중...")
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
                print("✅ personas 테이블 생성 완료")
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
                    print("\n📊 personas 테이블에 updated_at 컬럼 추가 중...")
                    conn.execute(text("""
                        ALTER TABLE public.personas 
                        ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    """))
                    conn.commit()
                    print("✅ updated_at 컬럼 추가 완료")
                    migrations_applied += 1
                else:
                    print("\n✓ personas 테이블 이미 존재")
        except Exception as e:
            print(f"\n⚠️ personas 테이블 생성 실패: {e}")
    
    print("\n" + "=" * 80)
    if migrations_applied > 0:
        print(f"🎉 {migrations_applied}개의 마이그레이션이 적용되었습니다!")
    else:
        print("✅ 모든 컬럼이 이미 존재합니다. 마이그레이션이 필요하지 않습니다.")
    print("=" * 80)
    print("\n📝 참고:")
    print("   - 이 마이그레이션은 멱등성(idempotent)이므로 여러 번 실행해도 안전합니다.")
    print("   - 기존 데이터는 NULL 값으로 유지됩니다.")
    print("   - 새로운 시뮬레이션부터 해당 필드가 자동으로 저장됩니다.")

if __name__ == "__main__":
    migrate()

