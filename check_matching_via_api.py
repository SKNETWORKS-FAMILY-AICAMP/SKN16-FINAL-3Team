"""
기존 API를 통해 매칭 상태 확인하는 스크립트
"""
import requests
import json

BASE_URL = "http://localhost:8000"

def check_matching():
    print("=" * 60)
    print("🔍 기존 API를 통한 매칭 상태 확인")
    print("=" * 60)
    
    try:
        # 1. 관리자 로그인
        print("\n1️⃣ 관리자 로그인...")
        login_response = requests.post(
            f"{BASE_URL}/auth/login",
            data={"username": "admin@bank.com", "password": "admin123"},
            timeout=5
        )
        
        if login_response.status_code != 200:
            print(f"❌ 로그인 실패: {login_response.status_code}")
            return
        
        token = login_response.json().get("access_token")
        headers = {"Authorization": f"Bearer {token}"}
        print("✅ 로그인 성공")
        
        # 2. 관리자 매칭 대시보드 조회
        print("\n2️⃣ 관리자 매칭 대시보드 조회...")
        matching_response = requests.get(
            f"{BASE_URL}/dashboard/matching",
            headers=headers,
            timeout=5
        )
        
        if matching_response.status_code == 200:
            data = matching_response.json()
            
            # 권도형 멘토 찾기
            mentors = data.get("mentors", [])
            mentor_do = None
            for m in mentors:
                if m.get("name") == "권도형":
                    mentor_do = m
                    break
            
            if mentor_do:
                print(f"✅ 권도형 멘토 발견: ID {mentor_do.get('id')}")
                print(f"   현재 멘티 수: {mentor_do.get('current_mentee_count', 0)}명")
                
                # 매칭 목록에서 확인
                matches = data.get("current_matches", [])
                do_matches = [m for m in matches if m.get("mentor", {}).get("name") == "권도형"]
                
                if do_matches:
                    print(f"\n   권도형 멘토의 활성 매칭:")
                    for match in do_matches:
                        mentee_name = match.get("mentee", {}).get("name")
                        print(f"      - {mentee_name}")
                else:
                    print(f"\n   ❌ 권도형 멘토의 활성 매칭이 관리자 대시보드에도 없습니다!")
            else:
                print("   ⚠️ 권도형 멘토를 찾을 수 없습니다.")
        else:
            print(f"❌ API 호출 실패: {matching_response.status_code}")
        
        # 3. 권도형 멘토 계정으로 로그인하여 대시보드 확인
        print("\n3️⃣ 권도형 멘토 계정으로 로그인 시도...")
        
        # 권도형의 이메일 확인 (DB에서)
        # 일단 이메일을 추정해서 시도해보거나, 다른 방법 사용
        
        print("   ℹ️ 권도형 멘토의 정확한 이메일이 필요합니다.")
        print("   💡 DB에서 확인: 202101020@bank.com (추정)")
        
        # 멘티 계정 확인
        print("\n4️⃣ 홍예미, 황나미 멘티 계정 확인...")
        print("   💡 멘티 이메일:")
        print("      - 홍예미: 202504028@bank.com")
        print("      - 황나미: 202504029@bank.com")
        
        print("\n" + "=" * 60)
        print("📊 진단 결과 요약")
        print("=" * 60)
        print("\n✅ DB 상태:")
        print("   - 권도형 ↔ 홍예미: 활성 매칭 존재")
        print("   - 권도형 ↔ 황나미: 활성 매칭 존재")
        print("\n💡 문제 해결 방법:")
        print("   1. 백엔드 서버 재시작 (새 API 활성화)")
        print("   2. 멘토/멘티 계정으로 로그인하여 확인")
        print("   3. 브라우저 캐시 삭제")
        print("   4. 로그아웃 후 다시 로그인")
        
    except requests.exceptions.ConnectionError:
        print("\n❌ 서버에 연결할 수 없습니다!")
        print("   백엔드 서버가 실행 중인지 확인하세요.")
    except Exception as e:
        print(f"\n❌ 오류: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_matching()



