"""
멘토-멘티 매칭 진단 스크립트
간단히 실행하여 매칭 상태를 확인할 수 있습니다.
"""
import requests
import json
import sys

BASE_URL = "http://localhost:8000"

def main():
    print("=" * 60)
    print("🔍 멘토-멘티 매칭 진단 시작")
    print("=" * 60)
    
    try:
        # 1. 로그인
        print("\n1️⃣ 관리자 계정으로 로그인 중...")
        login_response = requests.post(
            f"{BASE_URL}/auth/login",
            data={"username": "admin@bank.com", "password": "admin123"},
            timeout=5
        )
        
        if login_response.status_code != 200:
            print(f"❌ 로그인 실패: {login_response.status_code}")
            print(f"응답: {login_response.text}")
            return
        
        token = login_response.json().get("access_token")
        if not token:
            print("❌ 토큰을 받을 수 없습니다.")
            return
        
        print("✅ 로그인 성공!")
        
        # 진단할 사용자 목록
        mentors_to_check = ["권도형"]
        mentees_to_check = ["홍예미", "황나미"]
        
        headers = {"Authorization": f"Bearer {token}"}
        
        # 2. 멘토 진단
        print("\n" + "=" * 60)
        print("2️⃣ 멘토 매칭 상태 진단")
        print("=" * 60)
        
        for mentor_name in mentors_to_check:
            print(f"\n📋 {mentor_name} 멘토 진단 중...")
            try:
                response = requests.get(
                    f"{BASE_URL}/dashboard/admin/diagnose-matching/{mentor_name}",
                    headers=headers,
                    timeout=5
                )
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if "error" in data:
                        print(f"   ⚠️ {data['error']}")
                        continue
                    
                    mentor_info = data.get("mentor", {})
                    active_count = data.get("active_count", 0)
                    total_count = data.get("total_count", 0)
                    
                    print(f"   👤 멘토 ID: {mentor_info.get('id')}")
                    print(f"   📧 이메일: {mentor_info.get('email')}")
                    print(f"   📊 총 매칭 관계: {total_count}개")
                    print(f"   ✅ 활성 매칭: {active_count}개")
                    
                    if active_count == 0:
                        print(f"   ❌ 문제 발견: 활성 매칭이 없습니다!")
                        if total_count > 0:
                            print(f"   💡 해결 방법: 비활성 관계를 활성화하거나 재매칭이 필요합니다.")
                    else:
                        print(f"   ✅ 정상: {active_count}개의 활성 매칭이 있습니다.")
                        
                        # 활성 관계 상세 정보
                        active_relations = data.get("active_relations", [])
                        for i, rel in enumerate(active_relations, 1):
                            print(f"\n   📝 활성 관계 #{i}:")
                            print(f"      - 멘티: {rel.get('mentee_name')} (ID: {rel.get('mentee_id')})")
                            print(f"      - 매칭일: {rel.get('matched_at')}")
                    
                    # 비활성 관계도 표시
                    all_relations = data.get("all_relations", [])
                    inactive_relations = [r for r in all_relations if not r.get("is_active")]
                    if inactive_relations:
                        print(f"\n   ⚠️ 비활성 매칭 관계 ({len(inactive_relations)}개):")
                        for rel in inactive_relations:
                            print(f"      - {rel.get('mentee_name')} (비활성)")
                
                else:
                    print(f"   ❌ API 호출 실패: {response.status_code}")
                    print(f"   응답: {response.text}")
            
            except requests.exceptions.RequestException as e:
                print(f"   ❌ 오류 발생: {e}")
        
        # 3. 멘티 진단
        print("\n" + "=" * 60)
        print("3️⃣ 멘티 매칭 상태 진단")
        print("=" * 60)
        
        for mentee_name in mentees_to_check:
            print(f"\n📋 {mentee_name} 멘티 진단 중...")
            try:
                response = requests.get(
                    f"{BASE_URL}/dashboard/admin/diagnose-mentee-matching/{mentee_name}",
                    headers=headers,
                    timeout=5
                )
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if "error" in data:
                        print(f"   ⚠️ {data['error']}")
                        continue
                    
                    mentee_info = data.get("mentee", {})
                    active_count = data.get("active_count", 0)
                    total_count = data.get("total_count", 0)
                    
                    print(f"   👤 멘티 ID: {mentee_info.get('id')}")
                    print(f"   📧 이메일: {mentee_info.get('email')}")
                    print(f"   📊 총 매칭 관계: {total_count}개")
                    print(f"   ✅ 활성 매칭: {active_count}개")
                    
                    if active_count == 0:
                        print(f"   ❌ 문제 발견: 담당 멘토가 없습니다!")
                        if total_count > 0:
                            print(f"   💡 해결 방법: 비활성 관계를 활성화하거나 재매칭이 필요합니다.")
                    else:
                        active_relations = data.get("active_relations", [])
                        for rel in active_relations:
                            print(f"   ✅ 담당 멘토: {rel.get('mentor_name')} (ID: {rel.get('mentor_id')})")
                    
                    # 비활성 관계 확인
                    all_relations = data.get("all_relations", [])
                    inactive_relations = [r for r in all_relations if not r.get("is_active")]
                    if inactive_relations:
                        print(f"\n   ⚠️ 비활성 매칭 관계 ({len(inactive_relations)}개):")
                        for rel in inactive_relations:
                            print(f"      - {rel.get('mentor_name')} (비활성)")
                
                else:
                    print(f"   ❌ API 호출 실패: {response.status_code}")
                    print(f"   응답: {response.text}")
            
            except requests.exceptions.RequestException as e:
                print(f"   ❌ 오류 발생: {e}")
        
        # 4. 종합 진단 결과
        print("\n" + "=" * 60)
        print("4️⃣ 진단 완료")
        print("=" * 60)
        print("\n💡 다음 단계:")
        print("   1. 문제가 발견된 경우: backend/매칭_문제_해결_가이드.md 참고")
        print("   2. 관리자 대시보드에서 재매칭 수행")
        print("   3. 또는 DB에서 직접 수정")
        
    except requests.exceptions.ConnectionError:
        print("\n❌ 서버에 연결할 수 없습니다!")
        print("   확인 사항:")
        print("   1. 백엔드 서버가 실행 중인지 확인 (http://localhost:8000)")
        print("   2. docker-compose up으로 서버 시작")
        sys.exit(1)
    
    except Exception as e:
        print(f"\n❌ 예상치 못한 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()



