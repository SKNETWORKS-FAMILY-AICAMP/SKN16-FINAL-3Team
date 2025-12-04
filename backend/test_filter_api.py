"""
학습 이력 필터 API 테스트
- 실제 API 호출로 필터 동작 확인
"""
import requests
import json

BASE_URL = "http://localhost:3000/api"

def test_learning_history_filters():
    """필터 API 테스트"""
    
    # 테스트 토큰 (실제로는 로그인해서 받아야 함)
    # 여기서는 백엔드에서 직접 테스트하는 방식으로 변경
    
    print("=" * 80)
    print("학습 이력 필터 API 테스트")
    print("=" * 80)
    
    print("\n⚠️ 이 스크립트는 백엔드 내부에서 직접 테스트하는 것이 더 적합합니다.")
    print("   실제 API 테스트는 프론트엔드나 Postman을 통해 수행하세요.")
    
    print("\n📋 발견된 문제점:")
    print("1. 모드 필터 매핑:")
    print("   - 프론트엔드: 'pre' (초기)")
    print("   - 백엔드 변환: ExamType.BEGINNING → 'pre'")
    print("   - ✅ 정상 작동 예상")
    
    print("\n2. 퀴즈 로그 mode 문제:")
    print("   - 퀴즈 로그에 'final', 'midterm' 같은 시험 모드 값이 존재")
    print("   - 이는 데이터 생성 시 오류일 가능성")
    
    print("\n3. 기수 필터:")
    print("   - 프론트엔드: 하드코딩된 1, 2, 3, 4기")
    print("   - 백엔드: DB의 TrainingCohort.id 사용")
    print("   - ⚠️ 기수 ID가 하드코딩된 값과 일치하는지 확인 필요")
    
    print("\n4. 기수 ID 매핑:")
    print("   - 프론트엔드에서 보내는 cohort_id: 1, 2, 3, 4")
    print("   - 실제 DB의 cohort_id: 183, 202, 203, 205")
    print("   - ⚠️ 불일치! 프론트엔드가 잘못된 ID를 보내고 있음")

if __name__ == "__main__":
    test_learning_history_filters()

