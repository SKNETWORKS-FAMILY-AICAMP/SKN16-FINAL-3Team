"""
개인 계정 대시보드 API 테스트
"""
import requests
import json

BASE_URL = "http://localhost:8000"

def test_personal_dashboards():
    print("=" * 60)
    print("🔍 개인 계정 대시보드 API 테스트")
    print("=" * 60)
    
    # 사용자 정보 (DB에서 확인한 정보)
    users = {
        "권도형": {"email": "202101020@bank.com", "role": "mentor"},
        "홍예미": {"email": "202504028@bank.com", "role": "mentee"},
        "황나미": {"email": "202504029@bank.com", "role": "mentee"}
    }
    
    for name, user_info in users.items():
        print(f"\n{'='*60}")
        print(f"👤 {name} ({user_info['role']}) 계정 테스트")
        print(f"{'='*60}")
        
        try:
            # 로그인 (이메일 형식이 맞는지 확인 필요)
            # 일단 사원번호로 로그인 시도
            print(f"\n1️⃣ 로그인 시도...")
            
            # 이메일 형식이 아니라면 사원번호 추출
            email = user_info["email"]
            employee_number = email.split("@")[0] if "@" in email else email
            
            print(f"   이메일/사원번호: {email}")
            
            # 로그인 시도 (사원번호 또는 이메일로)
            login_response = requests.post(
                f"{BASE_URL}/auth/login",
                data={"username": email, "password": "1234"},  # 기본 비밀번호
                timeout=5
            )
            
            if login_response.status_code != 200:
                print(f"   ❌ 로그인 실패: {login_response.status_code}")
                print(f"   응답: {login_response.text}")
                continue
            
            token = login_response.json().get("access_token")
            if not token:
                print(f"   ❌ 토큰을 받을 수 없습니다.")
                continue
            
            headers = {"Authorization": f"Bearer {token}"}
            print(f"   ✅ 로그인 성공!")
            
            # 2. 대시보드 조회
            if user_info["role"] == "mentor":
                print(f"\n2️⃣ 멘토 대시보드 조회...")
                dashboard_response = requests.get(
                    f"{BASE_URL}/dashboard/mentor",
                    headers=headers,
                    timeout=5
                )
                
                if dashboard_response.status_code == 200:
                    data = dashboard_response.json()
                    mentees = data.get("mentees", [])
                    print(f"   ✅ 멘토 대시보드 조회 성공!")
                    print(f"   📊 담당 멘티 수: {len(mentees)}명")
                    
                    if len(mentees) == 0:
                        print(f"   ❌ 문제 발견: 멘티가 0명입니다!")
                    else:
                        print(f"   📝 담당 멘티 목록:")
                        for mentee in mentees:
                            print(f"      - {mentee.get('name')} (ID: {mentee.get('id')})")
                else:
                    print(f"   ❌ API 호출 실패: {dashboard_response.status_code}")
                    print(f"   응답: {dashboard_response.text}")
            
            elif user_info["role"] == "mentee":
                print(f"\n2️⃣ 멘티 대시보드 조회...")
                dashboard_response = requests.get(
                    f"{BASE_URL}/dashboard/mentee",
                    headers=headers,
                    timeout=5
                )
                
                if dashboard_response.status_code == 200:
                    data = dashboard_response.json()
                    mentor_info = data.get("mentor_info")
                    print(f"   ✅ 멘티 대시보드 조회 성공!")
                    
                    if mentor_info is None:
                        print(f"   ❌ 문제 발견: 담당 멘토가 없습니다!")
                    else:
                        print(f"   ✅ 담당 멘토: {mentor_info.get('name')} (ID: {mentor_info.get('id')})")
                else:
                    print(f"   ❌ API 호출 실패: {dashboard_response.status_code}")
                    print(f"   응답: {dashboard_response.text}")
        
        except requests.exceptions.RequestException as e:
            print(f"   ❌ 요청 오류: {e}")
        except Exception as e:
            print(f"   ❌ 오류: {e}")

if __name__ == "__main__":
    test_personal_dashboards()



