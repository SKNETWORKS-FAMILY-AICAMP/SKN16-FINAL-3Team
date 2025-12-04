"""
학습 이력 필터 기능 점검 스크립트
- 기수별 필터 동작 확인
- 모드별 필터 동작 확인
- 실제 데이터와의 일치 여부 확인
"""
import os
import sys
from sqlmodel import Session, select, create_engine
from app.models.user import User, UserRole
from app.models.mentor import ExamScore, ExamType
from app.models.quiz import QuizGenerationLog
from app.models.training_center import TrainingCenterRecord, TrainingCohort

# 환경 변수에서 DATABASE_URL 가져오기
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://mentoruser:mentorpass@postgres:5432/mentordb")
engine = create_engine(DATABASE_URL)

def check_cohort_filtering():
    """기수별 필터링 로직 점검"""
    print("=" * 80)
    print("기수별 필터링 로직 점검")
    print("=" * 80)
    
    with Session(engine) as session:
        # 1. 존재하는 모든 기수 확인
        cohorts = session.exec(select(TrainingCohort)).all()
        print(f"\n📋 DB에 존재하는 기수 목록:")
        cohort_map = {}
        for cohort in cohorts:
            print(f"  - ID: {cohort.id}, 라벨: {cohort.label}")
            cohort_map[cohort.id] = cohort.label
        
        # 2. 각 기수별 멘티 수 확인
        print(f"\n📊 각 기수별 멘티 수:")
        for cohort_id, cohort_label in cohort_map.items():
            mentee_records = session.exec(
                select(TrainingCenterRecord).where(
                    TrainingCenterRecord.cohort_id == cohort_id,
                    TrainingCenterRecord.employee_type == "mentee"
                )
            ).all()
            print(f"  - {cohort_label} (ID: {cohort_id}): {len(mentee_records)}명")
        
        # 3. 시험 점수 데이터가 있는 멘티들의 기수 분포 확인
        print(f"\n📝 시험 점수가 있는 멘티들의 기수 분포:")
        exam_scores = session.exec(select(ExamScore)).all()
        mentee_cohort_count = {}
        
        for exam in exam_scores:
            mentee = session.get(User, exam.mentee_id)
            if mentee and mentee.employee_number:
                record = session.exec(
                    select(TrainingCenterRecord).where(
                        TrainingCenterRecord.employee_number == mentee.employee_number
                    )
                ).first()
                
                if record and record.cohort_id:
                    cohort_label = cohort_map.get(record.cohort_id, f"기수 ID {record.cohort_id}")
                    if cohort_label not in mentee_cohort_count:
                        mentee_cohort_count[cohort_label] = {"beginning": 0, "midterm": 0, "final": 0}
                    
                    exam_type_map = {
                        ExamType.BEGINNING: "beginning",
                        ExamType.MIDTERM: "midterm",
                        ExamType.FINAL: "final"
                    }
                    exam_type_key = exam_type_map.get(exam.exam_type, "unknown")
                    if exam_type_key in mentee_cohort_count[cohort_label]:
                        mentee_cohort_count[cohort_label][exam_type_key] += 1
        
        for cohort_label, counts in mentee_cohort_count.items():
            print(f"  - {cohort_label}:")
            print(f"    - 초기: {counts['beginning']}개")
            print(f"    - 중간: {counts['midterm']}개")
            print(f"    - 최종: {counts['final']}개")
        
        # 4. 퀴즈 로그의 기수 분포 확인
        print(f"\n🎯 퀴즈 로그의 기수 분포:")
        quiz_logs = session.exec(select(QuizGenerationLog)).all()
        quiz_cohort_count = {}
        
        for log in quiz_logs:
            user = session.get(User, log.user_id)
            if user and user.employee_number:
                record = session.exec(
                    select(TrainingCenterRecord).where(
                        TrainingCenterRecord.employee_number == user.employee_number
                    )
                ).first()
                
                if record and record.cohort_id:
                    cohort_label = cohort_map.get(record.cohort_id, f"기수 ID {record.cohort_id}")
                    if cohort_label not in quiz_cohort_count:
                        quiz_cohort_count[cohort_label] = {"random": 0, "custom": 0}
                    
                    if log.mode in ["random", "custom"]:
                        quiz_cohort_count[cohort_label][log.mode] += 1
        
        for cohort_label, counts in quiz_cohort_count.items():
            print(f"  - {cohort_label}:")
            print(f"    - 랜덤: {counts['random']}개")
            print(f"    - 맞춤: {counts['custom']}개")

def check_mode_filtering():
    """모드별 필터링 로직 점검"""
    print("\n" + "=" * 80)
    print("모드별 필터링 로직 점검")
    print("=" * 80)
    
    with Session(engine) as session:
        # 1. 시험 점수의 exam_type 분포 확인
        print(f"\n📝 시험 점수의 exam_type 분포:")
        exam_scores = session.exec(select(ExamScore)).all()
        exam_type_count = {"beginning": 0, "midterm": 0, "final": 0}
        
        exam_type_map = {
            ExamType.BEGINNING: "beginning",
            ExamType.MIDTERM: "midterm",
            ExamType.FINAL: "final"
        }
        
        for exam in exam_scores:
            exam_type_key = exam_type_map.get(exam.exam_type, "unknown")
            if exam_type_key in exam_type_count:
                exam_type_count[exam_type_key] += 1
        
        print(f"  - 초기 (beginning): {exam_type_count['beginning']}개")
        print(f"  - 중간 (midterm): {exam_type_count['midterm']}개")
        print(f"  - 최종 (final): {exam_type_count['final']}개")
        
        # 2. 퀴즈 로그의 mode 분포 확인
        print(f"\n🎯 퀴즈 로그의 mode 분포:")
        quiz_logs = session.exec(select(QuizGenerationLog)).all()
        quiz_mode_count = {}
        
        for log in quiz_logs:
            if log.mode not in quiz_mode_count:
                quiz_mode_count[log.mode] = 0
            quiz_mode_count[log.mode] += 1
        
        for mode, count in sorted(quiz_mode_count.items()):
            print(f"  - {mode}: {count}개")
        
        # 3. API 필터 로직 검증
        print(f"\n🔍 API 필터 로직 검증:")
        print(f"  - 시험 모드 필터:")
        print(f"    - 'pre' → ExamType.BEGINNING 매핑 필요 (현재는 'beginning' 사용)")
        print(f"    - 'midterm' → ExamType.MIDTERM")
        print(f"    - 'final' → ExamType.FINAL")
        print(f"  - 퀴즈 모드 필터:")
        print(f"    - 'random' → QuizGenerationLog.mode == 'random'")
        print(f"    - 'custom' → QuizGenerationLog.mode == 'custom'")

def check_filter_issues():
    """필터 관련 잠재적 문제점 확인"""
    print("\n" + "=" * 80)
    print("필터 관련 잠재적 문제점 확인")
    print("=" * 80)
    
    with Session(engine) as session:
        issues = []
        
        # 1. cohort_id가 None인 TrainingCenterRecord 확인
        null_cohort_records = session.exec(
            select(TrainingCenterRecord).where(
                TrainingCenterRecord.cohort_id == None
            )
        ).all()
        
        if null_cohort_records:
            issues.append(f"⚠️ cohort_id가 None인 TrainingCenterRecord: {len(null_cohort_records)}개")
            print(f"\n⚠️ cohort_id가 None인 TrainingCenterRecord: {len(null_cohort_records)}개")
            for record in null_cohort_records[:5]:  # 처음 5개만 출력
                print(f"  - 사번: {record.employee_number}, 역할: {record.role}")
        
        # 2. employee_number가 없는 User 확인
        users_without_employee = session.exec(
            select(User).where(
                User.employee_number == None,
                User.role == UserRole.MENTEE
            )
        ).all()
        
        if users_without_employee:
            issues.append(f"⚠️ employee_number가 None인 멘티: {len(users_without_employee)}명")
            print(f"\n⚠️ employee_number가 None인 멘티: {len(users_without_employee)}명")
            for user in users_without_employee[:5]:  # 처음 5개만 출력
                print(f"  - ID: {user.id}, 이름: {user.name}, 이메일: {user.email}")
        
        # 3. TrainingCenterRecord와 User의 employee_number 불일치 확인
        print(f"\n🔍 TrainingCenterRecord와 User의 employee_number 일치 여부 확인 중...")
        exam_scores = session.exec(select(ExamScore)).all()
        mismatch_count = 0
        
        for exam in exam_scores[:100]:  # 처음 100개만 확인
            mentee = session.get(User, exam.mentee_id)
            if mentee and mentee.employee_number:
                record = session.exec(
                    select(TrainingCenterRecord).where(
                        TrainingCenterRecord.employee_number == mentee.employee_number
                    )
                ).first()
                
                if not record:
                    mismatch_count += 1
                    if mismatch_count <= 5:
                        print(f"  - 멘티 ID {mentee.id} (사번: {mentee.employee_number})의 TrainingCenterRecord를 찾을 수 없음")
        
        if mismatch_count > 5:
            print(f"  ... 외 {mismatch_count - 5}개 더 있음")
        
        if mismatch_count == 0:
            print("  ✅ 모든 시험 점수의 멘티가 TrainingCenterRecord와 연결되어 있습니다.")
        else:
            issues.append(f"⚠️ TrainingCenterRecord를 찾을 수 없는 멘티: {mismatch_count}명")
        
        # 4. 모드 필터 매핑 확인
        print(f"\n🔍 모드 필터 매핑 확인:")
        print(f"  - 프론트엔드에서 사용하는 모드:")
        print(f"    - 'pre' (초기)")
        print(f"    - 'midterm' (중간)")
        print(f"    - 'final' (최종)")
        print(f"    - 'random' (랜덤)")
        print(f"    - 'custom' (맞춤)")
        print(f"  - 백엔드에서 실제 사용하는 값:")
        print(f"    - ExamType.BEGINNING (초기)")
        print(f"    - ExamType.MIDTERM (중간)")
        print(f"    - ExamType.FINAL (최종)")
        print(f"    - QuizGenerationLog.mode == 'random' (랜덤)")
        print(f"    - QuizGenerationLog.mode == 'custom' (맞춤)")
        print(f"  ⚠️ 주의: 'pre'는 ExamType.BEGINNING으로 변환되어야 함")
        
        if not issues:
            print("\n✅ 발견된 문제점이 없습니다.")
        else:
            print(f"\n⚠️ 총 {len(issues)}개의 잠재적 문제점이 발견되었습니다.")

def main():
    print("=" * 80)
    print("학습 이력 필터 기능 종합 점검")
    print("=" * 80)
    
    try:
        check_cohort_filtering()
        check_mode_filtering()
        check_filter_issues()
        
        print("\n" + "=" * 80)
        print("✅ 점검 완료")
        print("=" * 80)
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

