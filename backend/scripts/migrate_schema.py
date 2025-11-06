#!/usr/bin/env python3
"""
데이터베이스 스키마 마이그레이션 스크립트
새로운 필드 추가 및 제약조건 변경
"""
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from sqlmodel import Session, text
from app.database import engine


def migrate_user_table():
    """User 테이블 마이그레이션"""
    print("🔄 User 테이블 마이그레이션 시작...")
    
    with Session(engine) as session:
        try:
            # 1. birth 컬럼 추가 (이미 있으면 무시)
            try:
                session.exec(text("""
                    ALTER TABLE users 
                    ADD COLUMN IF NOT EXISTS birth VARCHAR(8);
                """))
                session.commit()
                print("  ✅ birth 컬럼 추가 완료")
            except Exception as e:
                print(f"  ⚠️ birth 컬럼 추가 중 오류 (이미 존재할 수 있음): {e}")
                session.rollback()
            
            # 2. address 컬럼 추가 (이미 있으면 무시)
            try:
                session.exec(text("""
                    ALTER TABLE users 
                    ADD COLUMN IF NOT EXISTS address VARCHAR;
                """))
                session.commit()
                print("  ✅ address 컬럼 추가 완료")
            except Exception as e:
                print(f"  ⚠️ address 컬럼 추가 중 오류 (이미 존재할 수 있음): {e}")
                session.rollback()
            
            # 3. email을 nullable로 변경 (기존 데이터는 유지)
            try:
                session.exec(text("""
                    ALTER TABLE users 
                    ALTER COLUMN email DROP NOT NULL;
                """))
                session.commit()
                print("  ✅ email 컬럼을 nullable로 변경 완료")
            except Exception as e:
                # 이미 nullable이거나 제약조건이 없을 수 있음
                print(f"  ⚠️ email nullable 변경 중 오류 (이미 nullable일 수 있음): {e}")
                session.rollback()
            
            # 4. employee_number에 unique 인덱스 추가 (중복이 없을 경우만)
            try:
                # 먼저 중복 확인
                result = session.exec(text("""
                    SELECT employee_number, COUNT(*) 
                    FROM users 
                    WHERE employee_number IS NOT NULL 
                    GROUP BY employee_number 
                    HAVING COUNT(*) > 1;
                """))
                duplicates = result.fetchall()
                
                if duplicates:
                    print(f"  ⚠️ employee_number 중복 발견: {len(duplicates)}개")
                    print("     중복을 해결한 후 다시 시도해주세요.")
                else:
                    # unique 인덱스 생성 (이미 있으면 무시)
                    session.exec(text("""
                        CREATE UNIQUE INDEX IF NOT EXISTS ix_users_employee_number 
                        ON users(employee_number) 
                        WHERE employee_number IS NOT NULL;
                    """))
                    session.commit()
                    print("  ✅ employee_number unique 인덱스 생성 완료")
            except Exception as e:
                print(f"  ⚠️ employee_number unique 인덱스 생성 중 오류: {e}")
                session.rollback()
            
            print("✅ User 테이블 마이그레이션 완료")
            return True
            
        except Exception as e:
            print(f"❌ 마이그레이션 중 오류 발생: {e}")
            session.rollback()
            return False


def verify_migration():
    """마이그레이션 결과 확인"""
    print("\n🔍 마이그레이션 결과 확인 중...")
    
    with Session(engine) as session:
        try:
            # 컬럼 존재 확인
            result = session.exec(text("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'users'
                AND column_name IN ('birth', 'address', 'email', 'employee_number')
                ORDER BY column_name;
            """))
            
            columns = result.fetchall()
            print("\n📋 User 테이블 컬럼 정보:")
            for col in columns:
                nullable = "NULL 가능" if col[2] == 'YES' else "NOT NULL"
                print(f"  - {col[0]}: {col[1]} ({nullable})")
            
            # 인덱스 확인
            result = session.exec(text("""
                SELECT indexname, indexdef
                FROM pg_indexes
                WHERE tablename = 'users'
                AND indexname LIKE '%employee_number%';
            """))
            
            indexes = result.fetchall()
            if indexes:
                print("\n📋 employee_number 인덱스:")
                for idx in indexes:
                    print(f"  - {idx[0]}")
            
            print("\n✅ 마이그레이션 확인 완료")
            return True
            
        except Exception as e:
            print(f"❌ 확인 중 오류 발생: {e}")
            return False


def main():
    """메인 함수"""
    print("🚀 데이터베이스 스키마 마이그레이션 시작...")
    print("=" * 50)
    
    try:
        # 마이그레이션 실행
        if migrate_user_table():
            # 결과 확인
            verify_migration()
            print("\n🎉 마이그레이션 완료!")
        else:
            print("\n❌ 마이그레이션 실패")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n❌ 마이그레이션 중 오류 발생: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

