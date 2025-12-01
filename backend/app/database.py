"""
데이터베이스 연결 및 세션 관리
PostgreSQL + pgvector를 사용합니다.
"""
from sqlmodel import SQLModel, create_engine, Session
from pgvector.sqlalchemy import Vector
from sqlalchemy import text
from app.config import settings

# 모든 모델이 메타데이터에 등록되도록 명시적으로 임포트
import app.models  # noqa: F401

# 데이터베이스 엔진 생성
engine = create_engine(
    settings.DATABASE_URL,
    echo=True,  # SQL 쿼리 로깅 (개발 환경에서만 사용)
    pool_pre_ping=True,  # 연결 상태 확인
    pool_size=5,
    max_overflow=10
)


def init_db():
    """
    데이터베이스 초기화
    - 테이블 생성 (데이터 보존)
    - pgvector 확장 활성화
    """
    # pgvector 확장 활성화
    with Session(engine) as session:
        try:
            session.exec(text("CREATE EXTENSION IF NOT EXISTS vector"))
            session.commit()
            print("✅ pgvector extension enabled")
        except Exception as e:
            print(f"❌ Error enabling pgvector: {e}")
            session.rollback()
    
    # 모든 테이블 생성 (기존 테이블이 있으면 건너뜀)
    SQLModel.metadata.create_all(engine)
    print("✅ Database tables created/verified")

    # 게시글 카테고리 컬럼 보장
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "ALTER TABLE IF EXISTS posts ADD COLUMN IF NOT EXISTS category VARCHAR(50) DEFAULT '기타'"
        )
        connection.exec_driver_sql(
            "UPDATE posts SET category = '기타' WHERE category IS NULL"
        )
        connection.exec_driver_sql(
            "ALTER TABLE IF EXISTS posts ADD COLUMN IF NOT EXISTS subcategory VARCHAR(50)"
        )
        connection.exec_driver_sql(
            "UPDATE posts SET subcategory = NULL WHERE subcategory = ''"
        )
        connection.exec_driver_sql(
            "ALTER TABLE IF EXISTS comments ADD COLUMN IF NOT EXISTS join_status VARCHAR(20) DEFAULT 'none'"
        )
        connection.exec_driver_sql(
            "ALTER TABLE IF EXISTS comments ADD COLUMN IF NOT EXISTS join_approved_at TIMESTAMP"
        )
        connection.exec_driver_sql(
            "UPDATE comments SET join_status = 'none' WHERE join_status IS NULL OR join_status = ''"
        )
    print("✅ Post category column verified")
    
    # Training Center Records 테이블 마이그레이션 (누락된 컬럼 추가)
    try:
        with engine.begin() as connection:
            # 테이블 존재 여부 확인
            table_exists = connection.exec_driver_sql(
                """
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'training_center_records'
                );
                """
            ).scalar()
            
            if not table_exists:
                print("⚠️ training_center_records 테이블이 존재하지 않습니다. 테이블 생성은 SQLModel이 처리합니다.")
            else:
                print("🔄 training_center_records 테이블 마이그레이션 시작...")
                
                # gender 컬럼 추가 (가장 중요한 누락 컬럼)
                try:
                    connection.exec_driver_sql(
                        """
                        DO $$ 
                        BEGIN
                            IF NOT EXISTS (
                                SELECT 1 FROM information_schema.columns 
                                WHERE table_name = 'training_center_records' 
                                AND column_name = 'gender'
                            ) THEN
                                ALTER TABLE training_center_records 
                                ADD COLUMN gender VARCHAR(10);
                                RAISE NOTICE 'gender 컬럼 추가됨';
                            END IF;
                        END $$;
                        """
                    )
                    print("  ✅ gender 컬럼 확인/추가 완료")
                except Exception as e:
                    print(f"  ⚠️ gender 컬럼 처리 중 오류 (무시 가능): {e}")
        
                # 다른 필수 컬럼들도 확인 및 추가
                # join_year
                try:
                    connection.exec_driver_sql(
                        """
                        DO $$ 
                        BEGIN
                            IF NOT EXISTS (
                                SELECT 1 FROM information_schema.columns 
                                WHERE table_name = 'training_center_records' 
                                AND column_name = 'join_year'
                            ) THEN
                                ALTER TABLE training_center_records 
                                ADD COLUMN join_year INTEGER;
                            END IF;
                        END $$;
                        """
                    )
                except Exception as e:
                    print(f"  ⚠️ join_year 컬럼 처리 중 오류 (무시 가능): {e}")
        
                # major (Optional이지만 인덱스가 있음)
                try:
                    connection.exec_driver_sql(
                        """
                        DO $$ 
                        BEGIN
                            IF NOT EXISTS (
                                SELECT 1 FROM information_schema.columns 
                                WHERE table_name = 'training_center_records' 
                                AND column_name = 'major'
                            ) THEN
                                ALTER TABLE training_center_records 
                                ADD COLUMN major VARCHAR(100);
                                CREATE INDEX IF NOT EXISTS ix_training_center_records_major 
                                ON training_center_records(major);
                            END IF;
                        END $$;
                        """
                    )
                except Exception as e:
                    print(f"  ⚠️ major 컬럼 처리 중 오류 (무시 가능): {e}")
                
                # career_goal (Optional이지만 인덱스가 있음)
                try:
                    connection.exec_driver_sql(
                        """
                        DO $$ 
                        BEGIN
                            IF NOT EXISTS (
                                SELECT 1 FROM information_schema.columns 
                                WHERE table_name = 'training_center_records' 
                                AND column_name = 'career_goal'
                            ) THEN
                                ALTER TABLE training_center_records 
                                ADD COLUMN career_goal VARCHAR(100);
                                CREATE INDEX IF NOT EXISTS ix_training_center_records_career_goal 
                                ON training_center_records(career_goal);
                            END IF;
                        END $$;
                        """
                    )
                except Exception as e:
                    print(f"  ⚠️ career_goal 컬럼 처리 중 오류 (무시 가능): {e}")
                
                # 나머지 컬럼들 (한 번에 처리)
                remaining_columns = [
                    ("birth", "DATE"),
                    ("email", "VARCHAR(255)"),
                    ("phone", "VARCHAR(20)"),
                    ("address", "VARCHAR(255)"),
                    ("section_scores", "JSONB"),
                    ("question_scores", "JSONB"),
                    ("total_score", "INTEGER"),
                ]
                
                for col_name, col_type in remaining_columns:
                    try:
                        connection.exec_driver_sql(
                            f"""
                            DO $$ 
                            BEGIN
                                IF NOT EXISTS (
                                    SELECT 1 FROM information_schema.columns 
                                    WHERE table_name = 'training_center_records' 
                                    AND column_name = '{col_name}'
                                ) THEN
                                    ALTER TABLE training_center_records 
                                    ADD COLUMN {col_name} {col_type};
                                END IF;
                            END $$;
                            """
                        )
                    except Exception as e:
                        print(f"  ⚠️ {col_name} 컬럼 처리 중 오류 (무시 가능): {e}")
                
                # updated_at
                try:
                    connection.exec_driver_sql(
                        """
                        DO $$ 
                        BEGIN
                            IF NOT EXISTS (
                                SELECT 1 FROM information_schema.columns 
                                WHERE table_name = 'training_center_records' 
                                AND column_name = 'updated_at'
                            ) THEN
                                ALTER TABLE training_center_records 
                                ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
                            END IF;
                        END $$;
                        """
                    )
                except Exception as e:
                    print(f"  ⚠️ updated_at 컬럼 처리 중 오류 (무시 가능): {e}")
                
        print("✅ Training Center Records table migration completed")
    except Exception as e:
        print(f"⚠️ Training Center Records 마이그레이션 중 오류 발생: {e}")
        print("   이는 테이블이 아직 생성되지 않았거나 다른 문제일 수 있습니다.")
        print("   테이블이 생성되면 자동으로 마이그레이션이 실행됩니다.")

    # ExamScore / ExamResult 테이블 마이그레이션 (exam_type 컬럼 추가)
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql(
                """
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name = 'exam_scores'
                        AND column_name = 'exam_type'
                    ) THEN
                        ALTER TABLE exam_scores ADD COLUMN exam_type VARCHAR(50) DEFAULT 'beginning';
                    END IF;
                    UPDATE exam_scores SET exam_type = 'beginning'
                    WHERE exam_type IS NULL OR exam_type = '';
                END $$;
                """
            )
            connection.exec_driver_sql(
                """
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name = 'exam_results'
                        AND column_name = 'exam_type'
                    ) THEN
                        ALTER TABLE exam_results ADD COLUMN exam_type VARCHAR(50) DEFAULT 'beginning';
                    END IF;
                    UPDATE exam_results SET exam_type = 'beginning'
                    WHERE exam_type IS NULL OR exam_type = '';
                END $$;
                """
            )
        print("✅ Exam score tables migration completed")
    except Exception as e:
        print(f"⚠️ Exam score table migration error: {e}")


def get_session():
    """
    데이터베이스 세션 의존성
    FastAPI 엔드포인트에서 사용됩니다.
    """
    with Session(engine) as session:
        yield session


