import pandas as pd
import os

# 디렉토리 생성
os.makedirs("docs/standardized", exist_ok=True)

# 1. 요구사항 정의서 (Requirements) - 팀원 원본 + 코드 구현 사항 통합
requirements_data = [
    # [Training Center] 계정 및 데이터 관리
    {"Req_ID": "REQ-TC-001", "Category": "TrainingCenter", "Feature": "외부 DB 동기화", "Description": "관리자가 연수원/통합체계 데이터를 동기화하여 계정을 생성한다. (MBTI, 기본정보 포함)", "API_Endpoint": "POST /training-center/sync", "Priority": "High"},
    {"Req_ID": "REQ-TC-002", "Category": "TrainingCenter", "Feature": "일괄 등록 유효성 검증", "Description": "데이터 동기화 시 중복, 필수값 누락, 형식 오류를 검증하고 실패 건수를 반환한다.", "API_Endpoint": "POST /training-center/sync", "Priority": "High"},
    
    # [Auth] 인증 (회원가입 제거됨)
    {"Req_ID": "REQ-AUTH-001", "Category": "Auth", "Feature": "로그인", "Description": "이메일/사번으로 로그인. 비활성 사용자나 없는 계정일 경우 명확한 에러를 반환한다.", "API_Endpoint": "POST /auth/login", "Priority": "High"},
    {"Req_ID": "REQ-AUTH-002", "Category": "Auth", "Feature": "비밀번호 재설정", "Description": "이메일과 사번 검증 후 비밀번호를 재설정한다.", "API_Endpoint": "POST /auth/reset-password", "Priority": "Medium"},

    # [Chatbot] RAG 및 학습 지원
    {"Req_ID": "REQ-CHAT-001", "Category": "Chatbot", "Feature": "규정/매뉴얼 질의응답", "Description": "은행 내부 규정 문서를 검색(RAG)하여 출처와 함께 답변한다.", "API_Endpoint": "POST /chat/", "Priority": "High"},
    {"Req_ID": "REQ-CHAT-002", "Category": "Chatbot", "Feature": "일정 생성 대화", "Description": "자연어('내일 2시 회의')로 일정을 생성 요청 시 날짜/시간을 추출하여 등록한다.", "API_Endpoint": "POST /chat/", "Priority": "High"},
    {"Req_ID": "REQ-CHAT-003", "Category": "Chatbot", "Feature": "학습 현황 분석", "Description": "나의 약점/강점을 질문하면 시험 및 시뮬레이션 결과를 분석하여 답변한다.", "API_Endpoint": "POST /chat/", "Priority": "Medium"},

    # [Schedule] 일정 관리
    {"Req_ID": "REQ-SCH-001", "Category": "Schedule", "Feature": "멘토링 공통 일정 추천", "Description": "멘토와 멘티의 일정을 비교하여 월~금 11:00~14:00 사이의 빈 시간을 추천한다.", "API_Endpoint": "GET /schedules/common-free-slots", "Priority": "Medium"},
    {"Req_ID": "REQ-SCH-002", "Category": "Schedule", "Feature": "식사 일정 자동 등록", "Description": "멘토가 식사 일정을 잡으면 멘티의 캘린더에도 동시에 등록된다.", "API_Endpoint": "POST /schedules/mentor-mentee-meal", "Priority": "Medium"},

    # [Simulation] RAG 시뮬레이션
    {"Req_ID": "REQ-SIM-001", "Category": "Simulation", "Feature": "음성 대화 처리", "Description": "사용자의 음성을 STT로 변환하고, 페르소나에 맞는 응답을 TTS로 반환한다.", "API_Endpoint": "POST /rag-simulation/process-voice-interaction", "Priority": "High"},
    {"Req_ID": "REQ-SIM-002", "Category": "Simulation", "Feature": "종합 피드백 생성", "Description": "대화 종료 후 6대 역량(지식, 기술, 태도 등) 점수와 개선점을 생성한다.", "API_Endpoint": "POST /rag-simulation/generate-feedback", "Priority": "High"},

    # [Report] 리포트
    {"Req_ID": "REQ-REP-001", "Category": "Report", "Feature": "종합 역량 보고서", "Description": "퀴즈와 시뮬레이션 결과를 시각화(육각 그래프 등) 데이터로 제공한다.", "API_Endpoint": "GET /dashboard/mentee", "Priority": "High"},
]

# 2. 상세 테스트 케이스 (Test Cases) - Positive, Negative, Edge Case 포함
test_cases_data = [
    # --- Training Center ---
    {"TC_ID": "TC-TC-001", "Req_ID": "REQ-TC-001", "Type": "Positive", "Scenario": "정상 데이터 동기화", "Pre_Condition": "관리자 로그인, 유효한 기수 날짜 목록", "Input_Data": "{'selected_cohort_dates': ['2024-01-01']}", "Expected_Result": "200 OK, 생성된 계정 수 반환", "Actual_Result": ""},
    {"TC_ID": "TC-TC-002", "Req_ID": "REQ-TC-002", "Type": "Negative", "Scenario": "잘못된 날짜 형식 동기화 시도", "Pre_Condition": "관리자 로그인", "Input_Data": "{'selected_cohort_dates': ['invalid-date']}", "Expected_Result": "400 Bad Request (Date format error)", "Actual_Result": ""},
    
    # --- Auth ---
    {"TC_ID": "TC-AUTH-001", "Req_ID": "REQ-AUTH-001", "Type": "Positive", "Scenario": "이메일 로그인 성공", "Pre_Condition": "활성 계정 존재", "Input_Data": "Valid Email, Valid Password", "Expected_Result": "200 OK, Access/Refresh Token", "Actual_Result": ""},
    {"TC_ID": "TC-AUTH-002", "Req_ID": "REQ-AUTH-001", "Type": "Positive", "Scenario": "사번 로그인 성공", "Pre_Condition": "활성 계정 존재", "Input_Data": "Valid Employee Num, Valid Password", "Expected_Result": "200 OK, Access/Refresh Token", "Actual_Result": ""},
    {"TC_ID": "TC-AUTH-003", "Req_ID": "REQ-AUTH-001", "Type": "Negative", "Scenario": "비밀번호 불일치", "Pre_Condition": "계정 존재", "Input_Data": "Valid Email, Wrong Password", "Expected_Result": "401 Unauthorized", "Actual_Result": ""},
    {"TC_ID": "TC-AUTH-004", "Req_ID": "REQ-AUTH-001", "Type": "Negative", "Scenario": "비활성 계정 로그인", "Pre_Condition": "is_active=False 계정", "Input_Data": "Valid Email, Valid Password", "Expected_Result": "403 Forbidden (Inactive user)", "Actual_Result": ""},

    # --- Chatbot ---
    {"TC_ID": "TC-CHAT-001", "Req_ID": "REQ-CHAT-001", "Type": "Positive", "Scenario": "일반 규정 질문", "Pre_Condition": "로그인", "Input_Data": "'수신 금리 규정 알려줘'", "Expected_Result": "200 OK, 관련 문서 출처 포함 답변", "Actual_Result": ""},
    {"TC_ID": "TC-CHAT-002", "Req_ID": "REQ-CHAT-002", "Type": "Positive", "Scenario": "일정 생성 명령 (날짜 포함)", "Pre_Condition": "로그인", "Input_Data": "'내일 오후 2시 미팅 잡아줘'", "Expected_Result": "200 OK, 일정 생성 완료 메시지", "Actual_Result": ""},
    {"TC_ID": "TC-CHAT-003", "Req_ID": "REQ-CHAT-002", "Type": "Flow", "Scenario": "일정 생성 명령 (날짜 누락)", "Pre_Condition": "로그인", "Input_Data": "Step 1: '회의 잡아줘'\nStep 2: '내일 2시'", "Expected_Result": "Step 1: 시간 묻는 응답\nStep 2: 일정 생성 완료", "Actual_Result": ""},
    {"TC_ID": "TC-CHAT-004", "Req_ID": "REQ-CHAT-003", "Type": "Positive", "Scenario": "학습 약점 분석 요청", "Pre_Condition": "시험/시뮬레이션 기록 있음", "Input_Data": "'내 약점이 뭐야?'", "Expected_Result": "200 OK, 취약 역량(점수 낮은 순) 및 개선 제안", "Actual_Result": ""},
    {"TC_ID": "TC-CHAT-005", "Req_ID": "REQ-CHAT-003", "Type": "Negative", "Scenario": "기록 없는 상태에서 분석 요청", "Pre_Condition": "기록 없음", "Input_Data": "'내 강점 알려줘'", "Expected_Result": "200 OK, '데이터 부족' 안내 메시지", "Actual_Result": ""},

    # --- Schedule ---
    {"TC_ID": "TC-SCH-001", "Req_ID": "REQ-SCH-001", "Type": "Positive", "Scenario": "공통 빈 시간 조회", "Pre_Condition": "멘토 로그인, 멘티 2명 매칭됨", "Input_Data": "None", "Expected_Result": "200 OK, 멘티별 공통 빈 시간 리스트 (월~금)", "Actual_Result": ""},
    {"TC_ID": "TC-SCH-002", "Req_ID": "REQ-SCH-002", "Type": "Positive", "Scenario": "식사 일정 등록", "Pre_Condition": "멘토 로그인", "Input_Data": "{'mentee_id': 1, 'date': '2024-12-25'}", "Expected_Result": "200 OK, 멘토/멘티 양쪽 캘린더에 일정 생성됨", "Actual_Result": ""},
    {"TC_ID": "TC-SCH-003", "Req_ID": "REQ-SCH-002", "Type": "Negative", "Scenario": "매칭되지 않은 멘티와 식사 등록", "Pre_Condition": "멘토 로그인", "Input_Data": "{'mentee_id': 999, ...}", "Expected_Result": "403 Forbidden or 404 Not Found", "Actual_Result": ""},

    # --- Simulation ---
    {"TC_ID": "TC-SIM-001", "Req_ID": "REQ-SIM-001", "Type": "Positive", "Scenario": "음성 입력 처리", "Pre_Condition": "세션 시작", "Input_Data": "Audio File (WAV/WebM)", "Expected_Result": "200 OK, STT Text, LLM Response, Audio URL", "Actual_Result": ""},
    {"TC_ID": "TC-SIM-002", "Req_ID": "REQ-SIM-001", "Type": "Negative", "Scenario": "지원하지 않는 오디오 포맷", "Pre_Condition": "세션 시작", "Input_Data": "Audio File (EXE/TXT)", "Expected_Result": "400 Bad Request or 500 Internal Server Error (Handled gracefully)", "Actual_Result": ""},
    {"TC_ID": "TC-SIM-003", "Req_ID": "REQ-SIM-002", "Type": "Positive", "Scenario": "피드백 데이터 정합성", "Pre_Condition": "대화 10턴 이상 종료", "Input_Data": "Conversation History", "Expected_Result": "200 OK, Knowledge/Skill 등 6개 항목 점수 존재, 총점 계산 일치", "Actual_Result": ""},

    # --- Report ---
    {"TC_ID": "TC-REP-001", "Req_ID": "REQ-REP-001", "Type": "Positive", "Scenario": "대시보드 데이터 로딩", "Pre_Condition": "멘티 로그인", "Input_Data": "None", "Expected_Result": "200 OK, Exam Scores, Learning Progress, Simulation Results 포함", "Actual_Result": ""},
]

# DataFrame 생성
df_req = pd.DataFrame(requirements_data)
df_tc = pd.DataFrame(test_cases_data)

# 엑셀 파일 저장
file_path = "docs/standardized/Project_Requirements_and_TC_v4_Detailed.xlsx"
with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
    df_req.to_excel(writer, sheet_name='요구사항 정의서', index=False)
    df_tc.to_excel(writer, sheet_name='테스트 케이스', index=False)
    
    # 서식 조정
    workbook = writer.book
    worksheet_tc = writer.sheets['테스트 케이스']
    
    # 열 너비
    for sheet in writer.sheets.values():
        for col in sheet.columns:
            sheet.column_dimensions[col[0].column_letter].width = 25
            
    # TC 시트 조건부 서식 (Type에 따라 색상 변경 - 흉내내기)
    # openpyxl로 상세 스타일링 가능하나, 여기서는 데이터 구조에 집중

print(f"File created at: {file_path}")
