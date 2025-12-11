"""
DB에 직접 접속하여 매칭 진단하는 스크립트
서버 재시작 없이도 문제를 진단할 수 있습니다.
"""
import sys
import os

# 프로젝트 루트를 경로에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from sqlmodel import Session, select
from app.database import engine
from app.models.user import User
from app.models.mentor import MentorMenteeRelation

def diagnose_matching():
    print("=" * 60)
    print("🔍 DB 직접 접속 매칭 진단 시작")
    print("=" * 60)
    
    try:
        with Session(engine) as session:
            # 1. 권도형 멘토 찾기
            print("\n1️⃣ 권도형 멘토 찾기...")
            mentor = session.exec(
                select(User).where(
                    User.name == "권도형",
                    User.role == "mentor"
                )
            ).first()
            
            if not mentor:
                print("   ❌ 권도형 멘토를 찾을 수 없습니다.")
                print("   💡 DB에 있는 멘토 이름 확인 중...")
                
                # 모든 멘토 목록 출력
                all_mentors = session.exec(
                    select(User).where(User.role == "mentor")
                ).all()
                
                if all_mentors:
                    print(f"   📋 DB에 있는 멘토 목록 ({len(all_mentors)}명):")
                    for m in all_mentors[:10]:  # 최대 10명만
                        print(f"      - {m.name} (ID: {m.id}, Email: {m.email})")
                else:
                    print("   ⚠️ DB에 멘토가 없습니다.")
                return
            
            print(f"   ✅ 멘토 찾음: {mentor.name} (ID: {mentor.id})")
            
            # 2. 권도형 멘토의 매칭 관계 확인
            print("\n2️⃣ 매칭 관계 확인...")
            all_relations = session.exec(
                select(MentorMenteeRelation).where(
                    MentorMenteeRelation.mentor_id == mentor.id
                )
            ).all()
            
            print(f"   📊 총 매칭 관계: {len(all_relations)}개")
            
            if len(all_relations) == 0:
                print("   ❌ 문제 발견: 매칭 관계가 전혀 없습니다!")
                print("   💡 해결 방법: 관리자 대시보드에서 새로 매칭해야 합니다.")
                return
            
            # 활성/비활성 분류
            active_relations = [r for r in all_relations if r.is_active]
            inactive_relations = [r for r in all_relations if not r.is_active]
            
            print(f"   ✅ 활성 매칭: {len(active_relations)}개")
            print(f"   ⚠️ 비활성 매칭: {len(inactive_relations)}개")
            
            if len(active_relations) == 0:
                print("\n   ❌ 문제 발견: 활성 매칭이 없습니다!")
                print("   💡 해결 방법:")
                print("      1. 관리자 대시보드에서 재매칭")
                print("      2. 또는 DB에서 is_active를 True로 변경")
                
                if len(inactive_relations) > 0:
                    print("\n   📝 비활성 매칭 관계:")
                    for rel in inactive_relations:
                        mentee = session.get(User, rel.mentee_id)
                        if mentee:
                            print(f"      - {mentee.name} (ID: {rel.mentee_id}) - 비활성")
            
            # 3. 활성 매칭 상세 정보
            if len(active_relations) > 0:
                print("\n3️⃣ 활성 매칭 상세 정보:")
                for i, rel in enumerate(active_relations, 1):
                    mentee = session.get(User, rel.mentee_id)
                    if mentee:
                        print(f"\n   📝 매칭 #{i}:")
                        print(f"      - 멘티: {mentee.name} (ID: {rel.mentee_id})")
                        print(f"      - 이메일: {mentee.email}")
                        print(f"      - 매칭일: {rel.matched_at}")
                        print(f"      - 활성 상태: {'✅ 활성' if rel.is_active else '❌ 비활성'}")
                        print(f"      - 기수 ID: {rel.cohort_id}")
            
            # 4. 홍예미, 황나미 멘티 확인
            print("\n4️⃣ 멘티 확인...")
            mentee_names = ["홍예미", "황나미"]
            
            for mentee_name in mentee_names:
                print(f"\n   📋 {mentee_name} 멘티 찾기...")
                mentee = session.exec(
                    select(User).where(
                        User.name == mentee_name,
                        User.role == "mentee"
                    )
                ).first()
                
                if not mentee:
                    print(f"      ❌ {mentee_name} 멘티를 찾을 수 없습니다.")
                    continue
                
                print(f"      ✅ 멘티 찾음: {mentee.name} (ID: {mentee.id})")
                
                # 멘티의 매칭 관계 확인
                mentee_relations = session.exec(
                    select(MentorMenteeRelation).where(
                        MentorMenteeRelation.mentee_id == mentee.id
                    )
                ).all()
                
                active_mentee_relations = [r for r in mentee_relations if r.is_active]
                
                if len(active_mentee_relations) == 0:
                    print(f"      ❌ 문제: 담당 멘토가 없습니다!")
                    
                    if len(mentee_relations) > 0:
                        print(f"      ⚠️ 비활성 매칭 관계 {len(mentee_relations)}개 발견:")
                        for rel in mentee_relations:
                            mentor_user = session.get(User, rel.mentor_id)
                            if mentor_user:
                                print(f"         - {mentor_user.name} (비활성)")
                else:
                    for rel in active_mentee_relations:
                        mentor_user = session.get(User, rel.mentor_id)
                        if mentor_user:
                            print(f"      ✅ 담당 멘토: {mentor_user.name} (ID: {rel.mentor_id})")
            
            # 5. 종합 진단 결과
            print("\n" + "=" * 60)
            print("5️⃣ 종합 진단 결과")
            print("=" * 60)
            
            if len(active_relations) == 0:
                print("\n❌ 문제 확인:")
                print("   - 권도형 멘토에게 활성 매칭이 없습니다.")
                print("\n💡 해결 방법:")
                print("   1. 관리자 대시보드 접속")
                print("   2. 매칭 관리 페이지 이동")
                print("   3. 권도형 ↔ 홍예미, 황나미 재매칭")
                print("   4. 또는 DB에서 직접 수정:")
                print("      UPDATE mentor_mentee_relations")
                print("      SET is_active = TRUE")
                print("      WHERE mentor_id = (SELECT id FROM users WHERE name = '권도형')")
                print("        AND mentee_id IN (")
                print("          SELECT id FROM users WHERE name IN ('홍예미', '황나미')")
                print("        );")
            else:
                print("\n✅ 정상:")
                print(f"   - 권도형 멘토에게 {len(active_relations)}개의 활성 매칭이 있습니다.")
                print("\n⚠️ 확인 필요:")
                print("   - 개인 계정에서 매칭이 안 보인다면:")
                print("     1. 서버를 재시작해보세요")
                print("     2. 브라우저 캐시를 삭제해보세요")
                print("     3. 로그아웃 후 다시 로그인해보세요")
    
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    diagnose_matching()



