"""
페르소나 데이터를 PostgreSQL DB에 저장하는 스크립트
personas_expanded_minified2.json 파일을 읽어서 DB에 저장합니다.
"""
import json
import sys
from pathlib import Path
from urllib.parse import urlparse

import psycopg2
from psycopg2.extras import execute_values

# 프로젝트 루트 경로 추가 (app.config 임포트를 위해)
script_dir = Path(__file__).parent  # backend/scripts
backend_dir = script_dir.parent  # backend
sys.path.insert(0, str(backend_dir))

from app.config import settings


def parse_database_url(database_url: str) -> dict:
    """DATABASE_URL을 파싱하여 연결 정보 추출"""
    parsed = urlparse(database_url)
    return {
        "host": parsed.hostname or "localhost",
        "port": parsed.port or 5432,
        "dbname": parsed.path.lstrip("/") if parsed.path else "mentordb",
        "user": parsed.username or "mentoruser",
        "password": parsed.password or "mentorpass"
    }


def create_personas_table_if_not_exists(cur):
    """personas 테이블이 없으면 생성"""
    cur.execute("""
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
        );
    """)
    
    # updated_at 컬럼이 없으면 추가 (기존 테이블 대응)
    try:
        cur.execute("""
            ALTER TABLE public.personas 
            ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
        """)
    except Exception:
        pass  # 컬럼이 이미 있으면 무시
    
    print("✅ personas 테이블 확인/생성 완료")


def load_and_insert_personas():
    """페르소나 데이터 로드 및 DB 저장"""
    # 1) 파일 경로 설정
    data_dir = script_dir.parent / "data"  # backend/data
    personas_file = data_dir / "personas_expanded_minified2.json"
    
    if not personas_file.exists():
        print(f"❌ 파일을 찾을 수 없습니다: {personas_file}")
        return False
    
    print(f"📄 파일 경로: {personas_file}")
    
    # 2) JSON 파일 읽기
    try:
        with open(personas_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # personas 배열 추출
        if isinstance(data, dict) and "personas" in data:
            personas = data["personas"]
        elif isinstance(data, list):
            personas = data
        else:
            print("❌ JSON 구조가 올바르지 않습니다.")
            return False
        
        print(f"✅ {len(personas)}개의 페르소나 데이터 로드 완료")
    except json.JSONDecodeError as e:
        print(f"❌ JSON 파싱 실패: {e}")
        return False
    except Exception as e:
        print(f"❌ 파일 읽기 실패: {e}")
        return False
    
    # 3) DB 연결 정보 파싱
    db_config = parse_database_url(settings.DATABASE_URL)
    print(f"🔌 DB 연결 정보: {db_config['user']}@{db_config['host']}:{db_config['port']}/{db_config['dbname']}")
    
    # 4) PostgreSQL 연결
    try:
        conn = psycopg2.connect(
            host=db_config["host"],
            port=db_config["port"],
            dbname=db_config["dbname"],
            user=db_config["user"],
            password=db_config["password"]
        )
        cur = conn.cursor()
        print("✅ DB 연결 성공")
    except Exception as e:
        print(f"❌ DB 연결 실패: {e}")
        return False
    
    try:
        # 5) 테이블 생성 (없으면)
        create_personas_table_if_not_exists(cur)
        conn.commit()
        
        # 6) INSERT 반복
        inserted_count = 0
        updated_count = 0
        
        for p in personas:
            try:
                # speech 객체에서 정보 추출
                speech = p.get("speech", {})
                speech_tone = speech.get("tone", "")
                speech_speed = speech.get("speed", "")
                tts_temperature = speech.get("tts_temperature", None)
                
                # utterance_hints는 배열이므로 그대로 사용
                utterance_hints = p.get("utterance_hints", [])
                
                # updated_at 컬럼 존재 여부 확인
                cur.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'personas' AND column_name = 'updated_at';
                """)
                has_updated_at = cur.fetchone() is not None
                
                if has_updated_at:
                    update_clause = ", updated_at = CURRENT_TIMESTAMP"
                else:
                    update_clause = ""
                
                cur.execute(
                    f"""
                    INSERT INTO public.personas (
                        id, gender, age_group, occupation, customer_style,
                        speech_tone, speech_speed, tts_temperature, utterance_hints
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE
                    SET gender = EXCLUDED.gender,
                        age_group = EXCLUDED.age_group,
                        occupation = EXCLUDED.occupation,
                        customer_style = EXCLUDED.customer_style,
                        speech_tone = EXCLUDED.speech_tone,
                        speech_speed = EXCLUDED.speech_speed,
                        tts_temperature = EXCLUDED.tts_temperature,
                        utterance_hints = EXCLUDED.utterance_hints
                        {update_clause};
                    """,
                    (
                        p["id"],
                        p["gender"],
                        p["age_group"],
                        p["occupation"],
                        p["customer_style"],
                        speech_tone,
                        speech_speed,
                        tts_temperature,
                        utterance_hints,
                    )
                )
                
                # ON CONFLICT로 인해 업데이트된 경우와 새로 삽입된 경우 구분
                if cur.rowcount > 0:
                    # rowcount가 1이면 INSERT, 2면 UPDATE (PostgreSQL의 ON CONFLICT 동작)
                    if cur.rowcount == 1:
                        inserted_count += 1
                    else:
                        updated_count += 1
                
            except Exception as e:
                print(f"⚠️ 페르소나 {p.get('id', 'UNKNOWN')} 저장 실패: {e}")
                continue
        
        # 7) 커밋
        conn.commit()
        print(f"✅ 저장 완료: 신규 {inserted_count}개, 업데이트 {updated_count}개")
        
        return True
        
    except Exception as e:
        print(f"❌ 저장 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        return False
        
    finally:
        cur.close()
        conn.close()
        print("✅ DB 연결 종료")


if __name__ == "__main__":
    print("=" * 60)
    print("페르소나 데이터 DB 저장 스크립트")
    print("=" * 60)
    
    success = load_and_insert_personas()
    
    if success:
        print("\n✅ 스크립트 실행 완료!")
        sys.exit(0)
    else:
        print("\n❌ 스크립트 실행 실패!")
        sys.exit(1)

