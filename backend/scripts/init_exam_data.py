#!/usr/bin/env python3
"""
시험 데이터 초기화 스크립트
bank_training_exam.json 파일을 읽어서 데이터베이스에 저장
"""
import json
import sys
import os
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from sqlmodel import Session, select
from app.database import engine
from app.models.mentor import ExamQuestion


def load_exam_data():
    """시험 데이터 JSON 파일 로드"""
    exam_file = project_root / "data" / "bank_training_exam.json"
    
    if not exam_file.exists():
        print(f"❌ 시험 데이터 파일을 찾을 수 없습니다: {exam_file}")
        return None
    
    with open(exam_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def clear_existing_questions(session: Session):
    """기존 시험 문제 데이터 삭제"""
    print("🗑️ 기존 시험 문제 데이터 삭제 중...")
    
    # 모든 시험 문제 삭제
    existing_questions = session.exec(select(ExamQuestion)).all()
    for question in existing_questions:
        session.delete(question)
    
    session.commit()
    print(f"✅ {len(existing_questions)}개의 기존 문제 삭제 완료")


def insert_exam_questions(exam_data: dict, session: Session):
    """시험 문제들을 데이터베이스에 삽입"""
    print("📝 시험 문제 데이터 삽입 중...")
    
    inserted_count = 0
    
    for section in exam_data['sections']:
        section_id = section['section_id']
        section_name = section['section_name']
        
        print(f"  📚 {section_name} 섹션 처리 중...")
        
        for question_data in section['questions']:
            question = ExamQuestion(
                q_id=question_data['q_id'],
                question=question_data['question'],
                question_type=question_data.get('type', 'multiple_choice'),
                options=json.dumps(question_data['options'], ensure_ascii=False),
                correct_answer=question_data['answer'],
                difficulty=question_data.get('difficulty', 'basic'),
                learning_topic=question_data['learning_topic'],
                explanation=question_data['explanation'],
                section_id=section_id,
                section_name=section_name
            )
            
            session.add(question)
            inserted_count += 1
    
    session.commit()
    print(f"✅ 총 {inserted_count}개의 시험 문제 삽입 완료")


def main():
    """메인 함수"""
    print("🚀 시험 데이터 초기화 시작...")
    
    # 시험 데이터 로드
    exam_data = load_exam_data()
    if not exam_data:
        return
    
    print(f"📊 시험 정보:")
    print(f"  - 제목: {exam_data['exam_info']['title']}")
    print(f"  - 총 문제 수: {exam_data['exam_info']['total_questions']}")
    print(f"  - 섹션 수: {exam_data['exam_info']['sections']}")
    
    # 데이터베이스 세션 생성
    with Session(engine) as session:
        try:
            # 기존 데이터 삭제
            clear_existing_questions(session)
            
            # 새 데이터 삽입
            insert_exam_questions(exam_data, session)
            
            print("🎉 시험 데이터 초기화 완료!")
            
            # 삽입된 데이터 확인
            total_questions = session.exec(select(ExamQuestion)).all()
            print(f"📈 데이터베이스에 총 {len(total_questions)}개의 문제가 저장되었습니다.")
            
            # 섹션별 통계
            sections = {}
            for q in total_questions:
                if q.section_name not in sections:
                    sections[q.section_name] = 0
                sections[q.section_name] += 1
            
            print("\n📊 섹션별 문제 수:")
            for section_name, count in sections.items():
                print(f"  - {section_name}: {count}문제")
                
        except Exception as e:
            print(f"❌ 오류 발생: {e}")
            session.rollback()
            raise


if __name__ == "__main__":
    main()

