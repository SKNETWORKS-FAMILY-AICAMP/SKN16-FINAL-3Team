"""
현재 대시보드에 나오는 '최종' 평가 점수 조회
"""
from sqlmodel import Session, select, create_engine
from app.models.mentor import ExamScore, ExamType
from app.models.user import User
from app.models.training_center import TrainingCenterRecord, TrainingCohort
import json
from datetime import datetime

def check_final_exam_scores():
    import os
    # Docker 컨테이너 내에서는 postgres 서비스 이름 사용
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://mentoruser:mentorpass@postgres:5432/mentordb")
    engine = create_engine(DATABASE_URL)
    
    with Session(engine) as session:
        print("=" * 100)
        print("최종 평가 점수 조회")
        print("=" * 100)
        
        # 최종 평가 점수 조회
        final_exams = session.exec(
            select(ExamScore, User.name, User.email, User.employee_number)
            .join(User, ExamScore.mentee_id == User.id)
            .where(ExamScore.exam_type == ExamType.FINAL)
            .order_by(ExamScore.exam_date.desc())
            .limit(50)
        ).all()
        
        print(f"\n총 {len(final_exams)}개의 최종 평가 점수 발견\n")
        
        # 기수별로 그룹화
        cohort_exams = {}
        
        for exam_score, user_name, user_email, employee_number in final_exams:
            # 기수 정보 조회
            cohort_label = None
            if employee_number:
                training_record = session.exec(
                    select(TrainingCenterRecord).where(
                        TrainingCenterRecord.employee_number == employee_number
                    )
                ).first()
                
                if training_record and training_record.cohort_id:
                    cohort = session.get(TrainingCohort, training_record.cohort_id)
                    if cohort:
                        cohort_label = cohort.label
            
            if not cohort_label:
                cohort_label = "기수 정보 없음"
            
            if cohort_label not in cohort_exams:
                cohort_exams[cohort_label] = []
            
            # score_data 파싱
            score_data = {}
            if exam_score.score_data:
                try:
                    score_data = json.loads(exam_score.score_data) if isinstance(exam_score.score_data, str) else exam_score.score_data
                except:
                    score_data = {}
            
            cohort_exams[cohort_label].append({
                "user_id": exam_score.mentee_id,
                "user_name": user_name,
                "user_email": user_email,
                "total_score": exam_score.total_score,
                "score_data": score_data,
                "exam_date": exam_score.exam_date,
                "score_data_str": exam_score.score_data[:100] if exam_score.score_data else "없음"
            })
        
        # 기수별로 출력
        for cohort_label in sorted(cohort_exams.keys()):
            exams = cohort_exams[cohort_label]
            print(f"\n{'=' * 100}")
            print(f"기수: {cohort_label} ({len(exams)}명)")
            print(f"{'=' * 100}")
            print(f"{'사용자 ID':<12} {'이름':<15} {'총점':<8} {'영역별 점수':<60} {'시험일':<20}")
            print("-" * 100)
            
            for exam in exams:
                score_str = ""
                if exam["score_data"]:
                    score_items = []
                    for key, value in list(exam["score_data"].items())[:3]:  # 처음 3개만
                        score_items.append(f"{key}:{value}")
                    score_str = ", ".join(score_items)
                    if len(exam["score_data"]) > 3:
                        score_str += "..."
                else:
                    score_str = "점수 데이터 없음"
                
                exam_date_str = exam["exam_date"].strftime("%Y-%m-%d %H:%M") if exam["exam_date"] else "N/A"
                
                print(f"{exam['user_id']:<12} {exam['user_name']:<15} {exam['total_score']:<8.1f} {score_str:<60} {exam_date_str:<20}")
        
        # 통계 정보
        print(f"\n{'=' * 100}")
        print("통계 정보")
        print(f"{'=' * 100}")
        
        total_count = sum(len(exams) for exams in cohort_exams.values())
        total_score_sum = 0
        total_with_score_data = 0
        total_without_score_data = 0
        
        for cohort_label, exams in cohort_exams.items():
            cohort_score_sum = 0
            cohort_with_score_data = 0
            cohort_without_score_data = 0
            
            for exam in exams:
                cohort_score_sum += exam["total_score"]
                if exam["score_data"]:
                    cohort_with_score_data += 1
                else:
                    cohort_without_score_data += 1
            
            total_score_sum += cohort_score_sum
            
            avg_score = cohort_score_sum / len(exams) if exams else 0
            print(f"\n{cohort_label}:")
            print(f"  평균 점수: {avg_score:.1f}점")
            print(f"  점수 데이터 있음: {cohort_with_score_data}명")
            print(f"  점수 데이터 없음: {cohort_without_score_data}명")
        
        if total_count > 0:
            overall_avg = total_score_sum / total_count
            print(f"\n전체 평균: {overall_avg:.1f}점")
            print(f"전체 인원: {total_count}명")

if __name__ == "__main__":
    try:
        check_final_exam_scores()
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()

