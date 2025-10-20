#!/usr/bin/env python3
"""
데이터베이스 테이블 초기화 스크립트
새로운 시험 관련 테이블들을 생성
"""
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from sqlmodel import SQLModel
from app.database import engine
from app.models import *  # 모든 모델 import


def create_tables():
    """새로운 테이블들 생성"""
    print("🏗️ 데이터베이스 테이블 생성 중...")
    
    try:
        # 모든 테이블 생성
        SQLModel.metadata.create_all(engine)
        print("✅ 모든 테이블이 성공적으로 생성되었습니다.")
        
        # 생성된 테이블 목록 출력
        print("\n📋 생성된 테이블 목록:")
        for table_name in SQLModel.metadata.tables.keys():
            print(f"  - {table_name}")
        
    except Exception as e:
        print(f"❌ 테이블 생성 중 오류 발생: {e}")
        raise


def main():
    """메인 함수"""
    print("🚀 데이터베이스 테이블 초기화 시작...")
    
    try:
        create_tables()
        print("🎉 데이터베이스 테이블 초기화 완료!")
        
    except Exception as e:
        print(f"❌ 초기화 실패: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

