"""
매칭 문제 자동 해결 스크립트
1. 중복 비활성 관계 정리
2. 활성 관계 확인
3. 문제 해결
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from sqlmodel import Session, select
from app.database import engine
from app.models.user import User
from app.models.mentor import MentorMenteeRelation

def fix_matching():
    print("=" * 60)
    print("🔧 매칭 문제 자동 해결 시작")
    print("=" * 60)
    
    try:
        with Session(engine) as session:
            # 1. 권도형 멘토 찾기
            mentor = session.exec(
                select(User).where(
                    User.name == "권도형",
                    User.role == "mentor"
                )
            ).first()
            
            if not mentor:
                print("❌ 권도형 멘토를 찾을 수 없습니다.")
                return
            
            print(f"✅ 멘토 찾음: {mentor.name} (ID: {mentor.id})")
            
            # 2. 홍예미, 황나미 멘티 찾기
            mentee_names = ["홍예미", "황나미"]
            mentees = {}
            
            for mentee_name in mentee_names:
                mentee = session.exec(
                    select(User).where(
                        User.name == mentee_name,
                        User.role == "mentee"
                    )
                ).first()
                
                if mentee:
                    mentees[mentee_name] = mentee
                    print(f"✅ 멘티 찾음: {mentee.name} (ID: {mentee.id})")
                else:
                    print(f"❌ {mentee_name} 멘티를 찾을 수 없습니다.")
            
            if len(mentees) == 0:
                print("❌ 멘티를 찾을 수 없어 작업을 중단합니다.")
                return
            
            # 3. 각 멘티별로 처리
            for mentee_name, mentee in mentees.items():
                print(f"\n📋 {mentee_name} 처리 중...")
                
                # 해당 멘티의 모든 매칭 관계 조회
                all_relations = session.exec(
                    select(MentorMenteeRelation).where(
                        MentorMenteeRelation.mentee_id == mentee.id,
                        MentorMenteeRelation.mentor_id == mentor.id
                    )
                ).all()
                
                print(f"   발견된 매칭 관계: {len(all_relations)}개")
                
                # 활성 관계 확인
                active_relations = [r for r in all_relations if r.is_active]
                inactive_relations = [r for r in all_relations if not r.is_active]
                
                if len(active_relations) > 0:
                    print(f"   ✅ 활성 매칭 {len(active_relations)}개 존재")
                    
                    # 활성 관계가 2개 이상이면 최신 것만 남기고 나머지 비활성화
                    if len(active_relations) > 1:
                        print(f"   ⚠️ 활성 매칭이 {len(active_relations)}개입니다. 최신 것만 유지합니다.")
                        # matched_at 기준으로 정렬 (최신 것만 활성 유지)
                        active_relations.sort(key=lambda x: x.matched_at, reverse=True)
                        for rel in active_relations[1:]:
                            rel.is_active = False
                            session.add(rel)
                            print(f"      - 관계 ID {rel.id} 비활성화")
                    
                    # 비활성 관계는 모두 정리 (이미 비활성이므로 삭제하지 않고 그대로 둠)
                    if len(inactive_relations) > 0:
                        print(f"   ℹ️ 비활성 매칭 {len(inactive_relations)}개는 그대로 유지됩니다.")
                
                else:
                    # 활성 관계가 없으면, 가장 최근 비활성 관계를 활성화
                    print(f"   ❌ 활성 매칭이 없습니다. 비활성 매칭을 활성화합니다.")
                    
                    if len(inactive_relations) > 0:
                        # 가장 최근 매칭을 활성화
                        inactive_relations.sort(key=lambda x: x.matched_at, reverse=True)
                        latest_relation = inactive_relations[0]
                        latest_relation.is_active = True
                        session.add(latest_relation)
                        print(f"      ✅ 관계 ID {latest_relation.id} 활성화 (매칭일: {latest_relation.matched_at})")
                    else:
                        # 매칭 관계가 전혀 없으면 새로 생성
                        print(f"      📝 새로운 매칭 관계 생성 중...")
                        from datetime import datetime
                        from app.models.training_center import TrainingCenterRecord
                        
                        # 멘티의 기수 정보 찾기
                        cohort_id = None
                        if mentee.employee_number:
                            from sqlmodel import select
                            record = session.exec(
                                select(TrainingCenterRecord).where(
                                    TrainingCenterRecord.employee_number == mentee.employee_number,
                                    TrainingCenterRecord.employee_type == "mentee"
                                )
                            ).first()
                            cohort_id = record.cohort_id if record else None
                        
                        new_relation = MentorMenteeRelation(
                            mentor_id=mentor.id,
                            mentee_id=mentee.id,
                            cohort_id=cohort_id,
                            is_active=True,
                            matched_at=datetime.utcnow(),
                            notes="자동 수정: 매칭 문제 해결"
                        )
                        session.add(new_relation)
                        print(f"      ✅ 새로운 매칭 관계 생성 완료")
            
            # 4. 변경사항 저장
            print("\n💾 변경사항 저장 중...")
            session.commit()
            print("✅ 변경사항 저장 완료")
            
            # 5. 최종 확인
            print("\n" + "=" * 60)
            print("5️⃣ 최종 확인")
            print("=" * 60)
            
            for mentee_name, mentee in mentees.items():
                active_count = session.exec(
                    select(MentorMenteeRelation).where(
                        MentorMenteeRelation.mentee_id == mentee.id,
                        MentorMenteeRelation.mentor_id == mentor.id,
                        MentorMenteeRelation.is_active == True
                    )
                ).all()
                
                print(f"\n{mentee_name}:")
                if len(active_count) == 1:
                    print(f"   ✅ 활성 매칭 1개 존재 (정상)")
                elif len(active_count) > 1:
                    print(f"   ⚠️ 활성 매칭 {len(active_count)}개 존재 (정리 필요)")
                else:
                    print(f"   ❌ 활성 매칭 없음")
            
            print("\n" + "=" * 60)
            print("✅ 매칭 문제 해결 완료!")
            print("=" * 60)
            print("\n💡 다음 단계:")
            print("   1. 백엔드 서버 재시작")
            print("   2. 멘토/멘티 계정으로 로그인하여 매칭 확인")
            print("   3. 문제가 계속되면 브라우저 캐시 삭제")
    
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    fix_matching()



