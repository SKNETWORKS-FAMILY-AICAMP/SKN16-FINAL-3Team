"""초기화 최종 테스트 - 전후 상태 비교"""
from sqlmodel import Session, select
from app.database import engine
from app.models.training_center import TrainingCenterRecord, TrainingCohort
from app.models.user import User
from app.models.mentor import MentorMenteeRelation
from app.services.demo_seed_service import DemoSeedService
import json

session = Session(engine)

print("=" * 70)
print("초기화 최종 테스트")
print("=" * 70)

# 초기화 전 상태 확인
print("\n[1단계: 초기화 전 상태 확인]")
print("-" * 70)

cohorts = session.exec(
    select(TrainingCohort).where(
        TrainingCohort.cohort_index.in_([1, 2, 3, 4])
    ).order_by(TrainingCohort.cohort_index)
).all()

before_state = {}
for cohort in cohorts:
    mentors = session.exec(
        select(TrainingCenterRecord).where(
            TrainingCenterRecord.cohort_id == cohort.id,
            TrainingCenterRecord.employee_type == "mentor"
        )
    ).all()
    mentees = session.exec(
        select(TrainingCenterRecord).where(
            TrainingCenterRecord.cohort_id == cohort.id,
            TrainingCenterRecord.employee_type == "mentee"
        )
    ).all()
    
    relations = session.exec(
        select(MentorMenteeRelation).where(
            MentorMenteeRelation.cohort_id == cohort.id,
            MentorMenteeRelation.is_active == True
        )
    ).all()
    
    before_state[cohort.cohort_index] = {
        "label": cohort.label,
        "mentors": len(mentors),
        "mentees": len(mentees),
        "relations": len(relations),
    }
    
    print(f"\n{cohort.label}:")
    print(f"  멘토: {len(mentors)}명")
    print(f"  멘티: {len(mentees)}명")
    print(f"  관계: {len(relations)}개")

# 초기화 실행
print("\n[2단계: 초기화 실행]")
print("-" * 70)
print("초기화 중... (시간이 걸릴 수 있습니다)")

try:
    service = DemoSeedService(session)
    result = service.initialize_demo_data()
    
    print("\n✅ 초기화 완료!")
    
except Exception as e:
    print(f"\n❌ 오류 발생: {e}")
    import traceback
    traceback.print_exc()
    session.rollback()
    session.close()
    exit(1)

# 초기화 후 상태 확인
print("\n[3단계: 초기화 후 상태 확인]")
print("-" * 70)

cohorts_after = session.exec(
    select(TrainingCohort).where(
        TrainingCohort.cohort_index.in_([1, 2, 3, 4])
    ).order_by(TrainingCohort.cohort_index)
).all()

after_state = {}
for cohort in cohorts_after:
    mentors = session.exec(
        select(TrainingCenterRecord).where(
            TrainingCenterRecord.cohort_id == cohort.id,
            TrainingCenterRecord.employee_type == "mentor"
        )
    ).all()
    mentees = session.exec(
        select(TrainingCenterRecord).where(
            TrainingCenterRecord.cohort_id == cohort.id,
            TrainingCenterRecord.employee_type == "mentee"
        )
    ).all()
    
    relations = session.exec(
        select(MentorMenteeRelation).where(
            MentorMenteeRelation.cohort_id == cohort.id,
            MentorMenteeRelation.is_active == True
        )
    ).all()
    
    after_state[cohort.cohort_index] = {
        "label": cohort.label,
        "mentors": len(mentors),
        "mentees": len(mentees),
        "relations": len(relations),
    }
    
    print(f"\n{cohort.label}:")
    print(f"  멘토: {len(mentors)}명 {'✅' if len(mentors) == 15 else '❌'}")
    print(f"  멘티: {len(mentees)}명 {'✅' if len(mentees) == 30 else '❌'}")
    print(f"  관계: {len(relations)}개 {'✅' if len(relations) == 30 else '❌'}")

# 비교 결과
print("\n[4단계: 비교 결과]")
print("-" * 70)
print(f"{'기수':<10} {'멘토 (전)':<12} {'멘토 (후)':<12} {'멘티 (전)':<12} {'멘티 (후)':<12} {'관계 (후)':<12} {'상태'}")
print("-" * 70)

for idx in [1, 2, 3, 4]:
    before = before_state.get(idx, {})
    after = after_state.get(idx, {})
    
    mentor_before = before.get("mentors", 0)
    mentor_after = after.get("mentors", 0)
    mentee_before = before.get("mentees", 0)
    mentee_after = after.get("mentees", 0)
    relations_after = after.get("relations", 0)
    
    status = "✅ 통과" if mentor_after == 15 and mentee_after == 30 and relations_after == 30 else "❌ 실패"
    
    print(f"{idx}기        {mentor_before:<12} {mentor_after:<12} {mentee_before:<12} {mentee_after:<12} {relations_after:<12} {status}")

# 멘토 중복 확인
print("\n[5단계: 멘토 중복 확인]")
print("-" * 70)

all_mentors = {}
for cohort in cohorts_after:
    relations = session.exec(
        select(MentorMenteeRelation).where(
            MentorMenteeRelation.cohort_id == cohort.id,
            MentorMenteeRelation.is_active == True
        )
    ).all()
    
    for rel in relations:
        mentor_user = session.get(User, rel.mentor_id)
        if mentor_user:
            mentor_key = f"{mentor_user.name} ({mentor_user.employee_number})"
            if mentor_key not in all_mentors:
                all_mentors[mentor_key] = []
            all_mentors[mentor_key].append(cohort.label)

duplicate_mentors = {k: v for k, v in all_mentors.items() if len(v) > 1}

if duplicate_mentors:
    print(f"❌ {len(duplicate_mentors)}명의 멘토가 여러 기수에 할당됨:")
    for mentor, cohorts_list in list(duplicate_mentors.items())[:5]:  # 최대 5명만 표시
        print(f"  - {mentor}: {', '.join(set(cohorts_list))}")
    if len(duplicate_mentors) > 5:
        print(f"  ... 외 {len(duplicate_mentors) - 5}명")
else:
    print("✅ 모든 멘토가 한 기수만 담당하고 있습니다.")

session.close()

print("\n" + "=" * 70)
print("테스트 완료!")
print("=" * 70)

