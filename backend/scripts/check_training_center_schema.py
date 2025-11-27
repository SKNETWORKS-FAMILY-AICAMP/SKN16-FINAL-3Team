#!/usr/bin/env python3
"""
Training Center Records 테이블 스키마 확인 및 마이그레이션 스크립트
각자의 Docker 환경에서 스키마 상태를 확인하고 필요한 컬럼을 추가합니다.
"""
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from sqlalchemy import text, inspect
from app.database import engine, init_db


def check_schema():
    """Training Center Records 테이블 스키마 확인"""
    print("🔍 Training Center Records 테이블 스키마 확인 중...")
    print("=" * 60)
    
    inspector = inspect(engine)
    
    # 테이블 존재 여부 확인
    table_names = inspector.get_table_names()
    if "training_center_records" not in table_names:
        print("❌ training_center_records 테이블이 존재하지 않습니다!")
        print("💡 해결 방법: init_db()를 실행하세요.")
        return False
    
    print("✅ training_center_records 테이블 존재 확인")
    
    # 컬럼 목록 가져오기
    columns = inspector.get_columns("training_center_records")
    column_names = [col["name"] for col in columns]
    
    print(f"\n📋 현재 컬럼 목록 ({len(column_names)}개):")
    for col in sorted(column_names):
        print(f"  - {col}")
    
    # 필수 컬럼 확인
    required_columns = [
        "gender",
        "join_year",
        "major",
        "career_goal",
        "birth",
        "email",
        "phone",
        "address",
        "section_scores",
        "question_scores",
        "total_score",
        "updated_at",
    ]
    
    print(f"\n🔍 필수 컬럼 확인:")
    missing_columns = []
    for col in required_columns:
        if col in column_names:
            print(f"  ✅ {col}")
        else:
            print(f"  ❌ {col} (누락)")
            missing_columns.append(col)
    
    if missing_columns:
        print(f"\n⚠️ 누락된 컬럼: {', '.join(missing_columns)}")
        print("💡 해결 방법: init_db()를 실행하여 마이그레이션을 수행하세요.")
        return False
    else:
        print("\n✅ 모든 필수 컬럼이 존재합니다!")
        return True


def run_migration():
    """마이그레이션 실행"""
    print("\n" + "=" * 60)
    print("🔄 마이그레이션 실행 중...")
    print("=" * 60)
    
    try:
        init_db()
        print("\n✅ 마이그레이션 완료!")
        return True
    except Exception as e:
        print(f"\n❌ 마이그레이션 실패: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """메인 함수"""
    print("🚀 Training Center Records 스키마 진단 도구")
    print("=" * 60)
    
    # 스키마 확인
    is_ok = check_schema()
    
    if not is_ok:
        print("\n" + "=" * 60)
        response = input("마이그레이션을 실행하시겠습니까? (y/n): ").strip().lower()
        if response == 'y':
            run_migration()
            # 다시 확인
            print("\n" + "=" * 60)
            check_schema()
        else:
            print("\n💡 수동으로 마이그레이션을 실행하려면:")
            print("   python -c 'from app.database import init_db; init_db()'")
            print("   또는")
            print("   docker-compose restart backend")
    else:
        print("\n🎉 스키마가 정상입니다!")


if __name__ == "__main__":
    main()

