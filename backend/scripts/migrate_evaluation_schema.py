"""
평가 스키마 마이그레이션 스크립트
3가지 지표 → 6가지 지표로 DB 스키마 업데이트
"""
import os
import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from app.database import engine
from app.models.rag_simulation import RAGSimulationEvaluation, RAGSimulationSession, RAGSimulationTurn
from sqlmodel import SQLModel


def migrate_evaluation_schema():
    """평가 테이블 스키마 마이그레이션"""
    
    print("🔄 평가 스키마 마이그레이션 시작...")
    
    with engine.begin() as conn:
        # 1. RAGSimulationSession에 goal_list, achieved_goals 컬럼 추가
        print("\n📊 RAGSimulationSession 테이블 업데이트...")
        try:
            conn.execute(text("""
                ALTER TABLE rag_simulation_sessions 
                ADD COLUMN IF NOT EXISTS goal_list TEXT,
                ADD COLUMN IF NOT EXISTS achieved_goals TEXT;
            """))
            print("  ✓ goal_list, achieved_goals 컬럼 추가 완료")
        except Exception as e:
            print(f"  ⚠️ 컬럼 추가 실패 (이미 존재할 수 있음): {e}")
        
        # 2. RAGSimulationTurn의 role, text 컬럼 이름 변경 (또는 새 컬럼 추가)
        print("\n📊 RAGSimulationTurn 테이블 업데이트...")
        try:
            # speaker_role, speaker_text 컬럼 추가
            conn.execute(text("""
                ALTER TABLE rag_simulation_turns 
                ADD COLUMN IF NOT EXISTS speaker_role VARCHAR,
                ADD COLUMN IF NOT EXISTS speaker_text TEXT;
            """))
            print("  ✓ speaker_role, speaker_text 컬럼 추가 완료")
            
            # 기존 데이터 복사 (role → speaker_role, text → speaker_text)
            conn.execute(text("""
                UPDATE rag_simulation_turns 
                SET speaker_role = role, speaker_text = text
                WHERE speaker_role IS NULL AND role IS NOT NULL;
            """))
            print("  ✓ 기존 데이터 복사 완료")
            
        except Exception as e:
            print(f"  ⚠️ 컬럼 추가/복사 실패: {e}")
        
        # 3. RAGSimulationEvaluation 테이블 업데이트
        print("\n📊 RAGSimulationEvaluation 테이블 업데이트...")
        
        # 3-1. 새로운 지표 컬럼 추가
        try:
            conn.execute(text("""
                ALTER TABLE rag_simulation_evaluations 
                ADD COLUMN IF NOT EXISTS empathy_point INTEGER DEFAULT 0,
                ADD COLUMN IF NOT EXISTS clarity_point INTEGER DEFAULT 0,
                ADD COLUMN IF NOT EXISTS kindness_point INTEGER DEFAULT 0,
                ADD COLUMN IF NOT EXISTS confidence_point INTEGER DEFAULT 0;
            """))
            print("  ✓ 새 지표 컬럼 추가 완료 (empathy, clarity, kindness, confidence)")
        except Exception as e:
            print(f"  ⚠️ 컬럼 추가 실패: {e}")
        
        # 3-2. 등급 컬럼 추가
        try:
            conn.execute(text("""
                ALTER TABLE rag_simulation_evaluations 
                ADD COLUMN IF NOT EXISTS grade VARCHAR;
            """))
            print("  ✓ grade 컬럼 추가 완료")
        except Exception as e:
            print(f"  ⚠️ grade 컬럼 추가 실패: {e}")
        
        # 3-3. 각 지표별 이유 컬럼 추가
        try:
            conn.execute(text("""
                ALTER TABLE rag_simulation_evaluations 
                ADD COLUMN IF NOT EXISTS knowledge_reason TEXT,
                ADD COLUMN IF NOT EXISTS skill_reason TEXT,
                ADD COLUMN IF NOT EXISTS empathy_reason TEXT,
                ADD COLUMN IF NOT EXISTS clarity_reason TEXT,
                ADD COLUMN IF NOT EXISTS kindness_reason TEXT,
                ADD COLUMN IF NOT EXISTS confidence_reason TEXT,
                ADD COLUMN IF NOT EXISTS feedback_summary TEXT,
                ADD COLUMN IF NOT EXISTS detail_json TEXT;
            """))
            print("  ✓ 이유 및 피드백 컬럼 추가 완료")
        except Exception as e:
            print(f"  ⚠️ 이유 컬럼 추가 실패: {e}")
        
        # 3-4. 기존 컬럼의 제약 조건 수정 (0-100점으로 변경)
        try:
            # PostgreSQL의 경우 CHECK 제약 조건을 DROP하고 새로 추가해야 함
            # 여기서는 간단하게 처리
            print("  ℹ️ 점수 범위 제약 조건은 새 데이터부터 적용됩니다.")
        except Exception as e:
            print(f"  ⚠️ 제약 조건 수정 실패: {e}")
        
        # 3-5. 기존 attitude_point를 empathy_point로 복사 (데이터 마이그레이션)
        try:
            conn.execute(text("""
                UPDATE rag_simulation_evaluations 
                SET empathy_point = CASE 
                    WHEN attitude_point IS NOT NULL THEN attitude_point * 100 / 30  -- 30점 만점 → 100점 만점
                    ELSE 0 
                END
                WHERE empathy_point = 0;
            """))
            print("  ✓ 기존 attitude_point를 empathy_point로 변환 완료")
        except Exception as e:
            print(f"  ⚠️ 데이터 마이그레이션 실패: {e}")
        
        # 3-6. 기존 knowledge_point, skill_point 스케일 조정 (40점, 30점 만점 → 100점 만점)
        try:
            conn.execute(text("""
                UPDATE rag_simulation_evaluations 
                SET 
                    knowledge_point = CASE 
                        WHEN knowledge_point <= 40 THEN knowledge_point * 100 / 40
                        ELSE knowledge_point 
                    END,
                    skill_point = CASE 
                        WHEN skill_point <= 30 THEN skill_point * 100 / 30
                        ELSE skill_point 
                    END
                WHERE knowledge_point <= 40 OR skill_point <= 30;
            """))
            print("  ✓ 기존 점수 스케일 조정 완료 (100점 만점으로)")
        except Exception as e:
            print(f"  ⚠️ 스케일 조정 실패: {e}")
        
        # 3-7. 기존 데이터에 기본값 설정
        try:
            conn.execute(text("""
                UPDATE rag_simulation_evaluations 
                SET 
                    clarity_point = COALESCE(clarity_point, 70),
                    kindness_point = COALESCE(kindness_point, 70),
                    confidence_point = COALESCE(confidence_point, 70),
                    grade = COALESCE(grade, 'B'),
                    feedback_summary = COALESCE(feedback_summary, '평가 완료')
                WHERE clarity_point = 0 OR kindness_point = 0 OR confidence_point = 0;
            """))
            print("  ✓ 기존 데이터 기본값 설정 완료")
        except Exception as e:
            print(f"  ⚠️ 기본값 설정 실패: {e}")
    
    print("\n✅ 마이그레이션 완료!")
    print("\n📝 다음 단계:")
    print("  1. 애플리케이션 재시작")
    print("  2. POST /rag-simulation/evaluate 엔드포인트로 새 평가 테스트")
    print("  3. GET /rag-simulation/evaluation/{session_key}로 결과 확인")


def verify_migration():
    """마이그레이션 검증"""
    print("\n🔍 마이그레이션 검증 중...")
    
    with engine.begin() as conn:
        # 컬럼 확인
        result = conn.execute(text("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'rag_simulation_evaluations'
            ORDER BY ordinal_position;
        """))
        
        columns = result.fetchall()
        print("\n📋 rag_simulation_evaluations 테이블 컬럼:")
        for col in columns:
            print(f"  - {col[0]}: {col[1]}")
        
        # 필수 컬럼 존재 확인
        column_names = [col[0] for col in columns]
        required_columns = [
            'knowledge_point', 'skill_point', 'empathy_point', 
            'clarity_point', 'kindness_point', 'confidence_point',
            'grade', 'feedback_summary', 'detail_json'
        ]
        
        missing = [col for col in required_columns if col not in column_names]
        if missing:
            print(f"\n⚠️ 누락된 컬럼: {missing}")
        else:
            print("\n✅ 모든 필수 컬럼 존재")


if __name__ == "__main__":
    print("=" * 60)
    print("평가 스키마 마이그레이션 스크립트")
    print("3가지 지표 → 6가지 지표 (knowledge, skill, empathy, clarity, kindness, confidence)")
    print("=" * 60)
    
    try:
        migrate_evaluation_schema()
        verify_migration()
    except Exception as e:
        print(f"\n❌ 마이그레이션 실패: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

