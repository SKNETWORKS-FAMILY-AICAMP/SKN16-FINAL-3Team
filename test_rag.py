import requests
import json

# 챗봇 API 테스트
def test_chat(message):
    url = "http://localhost:8000/chat/"
    data = {"message": message}
    
    try:
        response = requests.post(url, json=data)
        if response.status_code == 200:
            result = response.json()
            print(f"질문: {message}")
            print(f"답변: {result.get('answer', '')[:200]}...")
            print(f"소스: {result.get('sources', [])}")
            print("-" * 50)
            return True
        else:
            print(f"오류: {response.status_code}")
            return False
    except Exception as e:
        print(f"연결 오류: {e}")
        return False

# 테스트 실행
if __name__ == "__main__":
    test_messages = [
        "위임장",
        "이의신청서", 
        "대출",
        "예금"
    ]
    
    for msg in test_messages:
        test_chat(msg)
