"""
시뮬레이션 피드백 테이블에 테스트 모드 컬럼 추가 마이그레이션
is_test_mode 컬럼 추가
"""
import os
import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from app.database import engine


def migrate_simulation_feedback_test_mode():
    """simulation_feedbacks 테이블에 is_test_mode 컬럼 추가"""
    
    print("🔄 simulation_feedbacks 테이블 마이그레이션 시작...")
    print("   - is_test_mode 컬럼 추가")
    
    with engine.begin() as conn:
        try:
            # is_test_mode 컬럼 추가 (기본값 False, 인덱스 추가)
            conn.execute(text("""
                ALTER TABLE simulation_feedbacks 
                ADD COLUMN IF NOT EXISTS is_test_mode BOOLEAN DEFAULT FALSE;
            """))
            print("  ✓ is_test_mode 컬럼 추가 완료")
            
            # 인덱스 추가 (조회 성능 향상)
            try:
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_simulation_feedbacks_is_test_mode 
                    ON simulation_feedbacks(is_test_mode);
                """))
                print("  ✓ is_test_mode 인덱스 추가 완료")
            except Exception as e:
                print(f"  ⚠️ 인덱스 추가 실패 (이미 존재할 수 있음): {e}")
            
            # 기존 데이터에 기본값 설정 (NULL이면 False)
            conn.execute(text("""
                UPDATE simulation_feedbacks 
                SET is_test_mode = FALSE
                WHERE is_test_mode IS NULL;
            """))
            print("  ✓ 기존 데이터 기본값 설정 완료")
            
        except Exception as e:
            print(f"  ❌ 마이그레이션 실패: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    print("\n✅ 마이그레이션 완료!")
    print("\n📝 다음 단계:")
    print("  1. 애플리케이션 재시작")
    print("  2. 테스트 모드 시뮬레이션 실행")
    print("  3. 관리자 대시보드에서 테스트 평가서 확인")


def verify_migration():
    """마이그레이션 검증"""
    print("\n🔍 마이그레이션 검증 중...")
    
    with engine.begin() as conn:
        # 컬럼 확인
        result = conn.execute(text("""
            SELECT column_name, data_type, column_default
            FROM information_schema.columns 
            WHERE table_name = 'simulation_feedbacks'
            AND column_name = 'is_test_mode';
        """))
        
        column = result.fetchone()
        if column:
            print(f"\n✅ is_test_mode 컬럼 존재 확인:")
            print(f"   - 컬럼명: {column[0]}")
            print(f"   - 타입: {column[1]}")
            print(f"   - 기본값: {column[2]}")
        else:
            print("\n❌ is_test_mode 컬럼이 존재하지 않습니다!")
            return False
        
        # 인덱스 확인
        result = conn.execute(text("""
            SELECT indexname 
            FROM pg_indexes 
            WHERE tablename = 'simulation_feedbacks'
            AND indexname = 'idx_simulation_feedbacks_is_test_mode';
        """))
        
        index = result.fetchone()
        if index:
            print(f"✅ 인덱스 존재 확인: {index[0]}")
        else:
            print("⚠️ 인덱스가 존재하지 않습니다 (선택사항)")
        
        return True


if __name__ == "__main__":
    print("=" * 60)
    print("시뮬레이션 피드백 테스트 모드 마이그레이션 스크립트")
    print("simulation_feedbacks 테이블에 is_test_mode 컬럼 추가")
    print("=" * 60)
    
    try:
        migrate_simulation_feedback_test_mode()
        if verify_migration():
            print("\n🎉 마이그레이션 성공!")
        else:
            print("\n⚠️ 마이그레이션은 완료되었지만 검증에 실패했습니다.")
    except Exception as e:
        print(f"\n❌ 마이그레이션 실패: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

