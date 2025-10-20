#!/usr/bin/env python3
"""
전체 시스템 설정 스크립트
데이터베이스 초기화, 시험 데이터 로드, 학습 자료 인덱싱을 순차적으로 실행
"""
import sys
import asyncio
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

def run_script(script_name: str, description: str):
    """스크립트 실행"""
    print(f"\n{'='*60}")
    print(f"🔄 {description}")
    print(f"{'='*60}")
    
    try:
        # 스크립트 경로
        script_path = project_root / "scripts" / script_name
        
        if not script_path.exists():
            print(f"❌ 스크립트 파일을 찾을 수 없습니다: {script_path}")
            return False
        
        # 스크립트 실행
        import subprocess
        result = subprocess.run([sys.executable, str(script_path)], 
                              capture_output=True, text=True)
        
        if result.returncode == 0:
            print(result.stdout)
            print(f"✅ {description} 완료!")
            return True
        else:
            print(f"❌ {description} 실패!")
            print(f"오류: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ {description} 중 오류 발생: {e}")
        return False


def main():
    """메인 함수"""
    print("🚀 은행 신입사원 AI 온보딩 시스템 설정 시작...")
    print("📋 설정 단계:")
    print("  1. 데이터베이스 테이블 생성")
    print("  2. 시험 데이터 초기화")
    print("  3. 학습 자료 RAG 인덱싱")
    
    # 단계별 실행
    steps = [
        ("init_database_tables.py", "데이터베이스 테이블 생성"),
        ("init_exam_data.py", "시험 데이터 초기화"),
        ("init_learning_materials.py", "학습 자료 RAG 인덱싱")
    ]
    
    success_count = 0
    
    for script_name, description in steps:
        if run_script(script_name, description):
            success_count += 1
        else:
            print(f"\n❌ {description} 단계에서 실패했습니다.")
            print("시스템 설정을 중단합니다.")
            sys.exit(1)
    
    # 완료 메시지
    print(f"\n{'='*60}")
    print("🎉 전체 시스템 설정 완료!")
    print(f"{'='*60}")
    print(f"✅ {success_count}/{len(steps)} 단계 완료")
    print("\n📚 사용 가능한 API 엔드포인트:")
    print("  - POST /exam/submit - 시험 답안 제출 및 채점")
    print("  - GET /exam/questions - 시험 문제 조회")
    print("  - GET /exam/recommendations - 학습 추천 조회")
    print("  - GET /exam/sections - 시험 섹션 정보")
    print("  - POST /chat - AI 멘토 챗봇")
    print("\n🚀 서버 실행: uvicorn app.main:app --reload --port 8000")
    print("📖 API 문서: http://localhost:8000/docs")


if __name__ == "__main__":
    main()

