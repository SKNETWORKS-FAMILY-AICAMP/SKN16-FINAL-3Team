"""
데이터베이스에 저장된 시험 점수를 점진적 상승 패턴에 맞게 수정
- 초기: 30~40% (18~24점)
- 중간: 50~70% (30~42점)
- 최종: 80~90% (48~54점)
"""
import random
import json
import os
from sqlmodel import Session, select
from app.database import engine
from app.models.mentor import ExamScore, ExamType
from app.models.user import User
from app.models.training_center import TrainingCenterRecord
from app.services.exam_initializer import generate_progressive_exam_score

EXAM_SECTION_KEYS = [
    "은행업무",
    "상품개발 및 운용",
    "신용분석 및 리스크관리",
    "외환",
    "은행지식 및 관련법률",
    "하경은행",
]

def fix_exam_scores_in_database():
    """데이터베이스에 저장된 시험 점수를 점진적 상승 패턴에 맞게 수정"""
    print("=" * 80)
    print("데이터베이스 시험 점수 수정")
    print("=" * 80)
    
    with Session(engine) as session:
        # 모든 멘티 조회
        mentees = session.exec(
            select(User).where(User.role == "mentee")
        ).all()
        
        print(f"\n총 {len(mentees)}명의 멘티 확인")
        
        updated_count = 0
        
        for mentee in mentees:
            # 멘티별 시험 점수 조회 (타입별)
            beginning_exam = session.exec(
                select(ExamScore).where(
                    ExamScore.mentee_id == mentee.id,
                    ExamScore.exam_type == ExamType.BEGINNING
                )
            ).first()
            
            midterm_exam = session.exec(
                select(ExamScore).where(
                    ExamScore.mentee_id == mentee.id,
                    ExamScore.exam_type == ExamType.MIDTERM
                )
            ).first()
            
            final_exam = session.exec(
                select(ExamScore).where(
                    ExamScore.mentee_id == mentee.id,
                    ExamScore.exam_type == ExamType.FINAL
                )
            ).first()
            
            # 사용자별 일관성을 위한 시드 (mentee.id 기반)
            user_seed = mentee.id % 10000
            
            # 초기 평가 점수 생성
            if beginning_exam:
                beginning_total = beginning_exam.total_score
                # 이미 올바른 범위(18~24점)에 있는지 확인
                if beginning_total < 18 or beginning_total > 24:
                    # 점진적 상승 패턴 적용
                    section_scores = generate_progressive_exam_score(
                        exam_type=ExamType.BEGINNING,
                        previous_total=None,
                        user_seed=user_seed
                    )
                    total_score = float(sum(section_scores.values()))
                    
                    beginning_exam.score_data = json.dumps(section_scores, ensure_ascii=False)
                    beginning_exam.total_score = round(total_score, 1)
                    session.add(beginning_exam)
                    updated_count += 1
                    beginning_total = total_score
                else:
                    beginning_total = beginning_exam.total_score
            else:
                beginning_total = None
            
            # 중간 평가 점수 생성
            if midterm_exam:
                midterm_total = midterm_exam.total_score
                # 이미 올바른 범위(30~42점)에 있는지 확인
                if midterm_total < 30 or midterm_total > 42:
                    # 점진적 상승 패턴 적용
                    section_scores = generate_progressive_exam_score(
                        exam_type=ExamType.MIDTERM,
                        previous_total=beginning_total,
                        user_seed=user_seed
                    )
                    total_score = float(sum(section_scores.values()))
                    
                    midterm_exam.score_data = json.dumps(section_scores, ensure_ascii=False)
                    midterm_exam.total_score = round(total_score, 1)
                    session.add(midterm_exam)
                    updated_count += 1
                    midterm_total = total_score
                else:
                    midterm_total = midterm_exam.total_score
            else:
                midterm_total = beginning_total
            
            # 최종 평가 점수 생성
            if final_exam:
                final_total = final_exam.total_score
                # 반드시 올바른 범위(48~54점)에 있어야 함
                # 범위 밖이면 무조건 수정
                if final_total < 48 or final_total > 54:
                    # 점진적 상승 패턴 적용
                    section_scores = generate_progressive_exam_score(
                        exam_type=ExamType.FINAL,
                        previous_total=midterm_total,
                        user_seed=user_seed
                    )
                    total_score = float(sum(section_scores.values()))
                    # 최종 평가는 반드시 48~54점 범위여야 함
                    if total_score < 48:
                        # 범위 밖이면 다시 생성 (더 높은 점수로)
                        section_scores = generate_progressive_exam_score(
                            exam_type=ExamType.FINAL,
                            previous_total=max(midterm_total or 30, 30),  # 최소 30점부터 시작
                            user_seed=user_seed + 1  # 시드 변경하여 다른 점수 생성
                        )
                        total_score = float(sum(section_scores.values()))
                        # 여전히 낮으면 강제로 48점 이상으로 조정
                        if total_score < 48:
                            # 모든 섹션 점수를 균등하게 올려서 총점 48점 이상으로 만들기
                            base_score = 8  # 섹션당 8점 (총 48점)
                            section_scores = {key: base_score for key in EXAM_SECTION_KEYS}
                            total_score = 48.0
                    
                    final_exam.score_data = json.dumps(section_scores, ensure_ascii=False)
                    final_exam.total_score = round(total_score, 1)
                    session.add(final_exam)
                    updated_count += 1
        
        # 변경사항 커밋
        session.commit()
        print(f"\n✅ {updated_count}개의 시험 점수 수정 완료")
        
        # 수정 후 검증
        print(f"\n검증 중...")
        
        final_exams = session.exec(
            select(ExamScore).where(ExamScore.exam_type == ExamType.FINAL)
        ).all()
        
        if final_exams:
            final_scores = [exam.total_score for exam in final_exams if exam.total_score]
            avg_final = sum(final_scores) / len(final_scores) if final_scores else 0
            min_final = min(final_scores) if final_scores else 0
            max_final = max(final_scores) if final_scores else 0
            
            print(f"\n최종 평가 점수 통계:")
            print(f"  평균: {avg_final:.1f}점 ({avg_final/60*100:.1f}%)")
            print(f"  범위: {min_final:.1f}~{max_final:.1f}점 ({min_final/60*100:.1f}%~{max_final/60*100:.1f}%)")
            print(f"  목표 범위: 48~54점 (80~90%)")
            
            if 48 <= min_final and max_final <= 54:
                print(f"  ✅ 모든 최종 평가 점수가 목표 범위 내에 있습니다!")
            else:
                print(f"  ⚠️ 일부 최종 평가 점수가 목표 범위를 벗어났습니다.")

if __name__ == "__main__":
    try:
        fix_exam_scores_in_database()
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()

