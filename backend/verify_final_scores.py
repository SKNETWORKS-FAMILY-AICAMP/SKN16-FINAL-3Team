"""
최종 평가 점수 검증 스크립트
"""
import os
from sqlmodel import Session, select
from app.database import engine
from app.models.mentor import ExamScore, ExamType

def verify_final_scores():
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://mentoruser:mentorpass@postgres:5432/mentordb")
    
    with Session(engine) as session:
        print("=" * 80)
        print("최종 평가 점수 검증")
        print("=" * 80)
        
        final_exams = session.exec(
            select(ExamScore).where(ExamScore.exam_type == ExamType.FINAL)
        ).all()
        
        print(f"\n총 {len(final_exams)}개의 최종 평가 발견")
        
        # 범위별 분류
        in_range = []  # 48~54점
        too_low = []   # 48점 미만
        too_high = []  # 54점 초과
        
        for exam in final_exams:
            score = exam.total_score
            if 48 <= score <= 54:
                in_range.append((exam.mentee_id, score))
            elif score < 48:
                too_low.append((exam.mentee_id, score))
            else:
                too_high.append((exam.mentee_id, score))
        
        print(f"\n📊 범위별 분류:")
        print(f"  ✅ 올바른 범위 (48~54점): {len(in_range)}개")
        print(f"  ❌ 범위 밖 낮음 (<48점): {len(too_low)}개")
        print(f"  ❌ 범위 밖 높음 (>54점): {len(too_high)}개")
        
        if too_low:
            print(f"\n⚠️ 범위 밖 낮은 점수 (처음 10개):")
            for mentee_id, score in too_low[:10]:
                print(f"    멘티 {mentee_id}: {score}점 ({score/60*100:.1f}%)")
        
        if too_high:
            print(f"\n⚠️ 범위 밖 높은 점수 (처음 10개):")
            for mentee_id, score in too_high[:10]:
                print(f"    멘티 {mentee_id}: {score}점 ({score/60*100:.1f}%)")
        
        # 통계
        if final_exams:
            scores = [exam.total_score for exam in final_exams if exam.total_score]
            avg = sum(scores) / len(scores) if scores else 0
            min_score = min(scores) if scores else 0
            max_score = max(scores) if scores else 0
            
            print(f"\n📈 통계:")
            print(f"  평균: {avg:.1f}점 ({avg/60*100:.1f}%)")
            print(f"  범위: {min_score:.1f}~{max_score:.1f}점 ({min_score/60*100:.1f}%~{max_score/60*100:.1f}%)")
            print(f"  목표 범위: 48~54점 (80~90%)")

if __name__ == "__main__":
    verify_final_scores()

