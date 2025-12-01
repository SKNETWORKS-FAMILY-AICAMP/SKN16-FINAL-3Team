import pandas as pd
import os
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side

os.makedirs("docs/standardized", exist_ok=True)

# ============================================================
# 1. 요구사항 정의서 (코드화 적용)
# 컬럼: 요구사항ID, 요구사항명, 기능ID, 기능명, 상세 설명, API Endpoint
# ============================================================
requirements_data = [
    # ==================== [TC] 연수원 관리 ====================
    ["TC01", "연수원 데이터 동기화", "TC01-01", "외부 API 연동", "관리자가 연수원 및 통합체계 외부 API 데이터를 동기화한다.", "POST /training-center/sync"],
    ["TC01", "연수원 데이터 동기화", "TC01-02", "기수 날짜 필터링", "동기화 시 선택된 기수 날짜(cohort_dates)를 기준으로 데이터를 필터링한다.", "POST /training-center/sync"],
    ["TC01", "연수원 데이터 동기화", "TC01-03", "동기화 결과 리포트", "동기화 결과로 생성된 멘티/멘토 수와 총 레코드 수를 반환한다.", "POST /training-center/sync"],
    ["TC02", "계정 자동 생성", "TC02-01", "User 계정 Insert", "create_accounts=true 옵션 시 동기화된 데이터를 기반으로 User 계정을 자동 생성한다.", "POST /training-center/sync"],
    ["TC02", "계정 자동 생성", "TC02-02", "초기 비밀번호 설정", "신규 계정 생성 시 초기 비밀번호를 설정하고 멘티 역할을 부여한다.", "-"],
    ["TC03", "데이터 유효성 검증", "TC03-01", "중복 검사", "동기화 시 중복된 사번이나 이메일이 있을 경우 기존 데이터를 갱신(Upsert)한다.", "-"],
    ["TC03", "데이터 유효성 검증", "TC03-02", "날짜 형식 검증", "잘못된 날짜 형식 입력 시 400 Bad Request 에러를 반환한다.", "POST /training-center/sync"],
    ["TC04", "목록 조회", "TC04-01", "필터링 조회", "관리자는 기수별, 역할별(멘토/멘티)로 동기화된 사용자 목록을 조회할 수 있다.", "GET /training-center/records"],
    ["TC04", "목록 조회", "TC04-02", "검색 기능", "이름 또는 사번 키워드로 검색할 수 있다.", "GET /training-center/mentees"],
    ["TC04", "목록 조회", "TC04-03", "레코드 삭제", "관리자는 선택한 레코드를 일괄 삭제할 수 있다.", "DELETE /training-center/records"],

    # ==================== [AUTH] 인증 ====================
    ["AUTH01", "로그인", "AUTH01-01", "이메일/사번 식별", "사용자는 이메일 또는 사번을 아이디로 사용하여 로그인할 수 있다.", "POST /auth/login"],
    ["AUTH01", "로그인", "AUTH01-02", "JWT 토큰 생성", "로그인 성공 시 JWT Access Token과 Refresh Token을 발급한다.", "POST /auth/login"],
    ["AUTH01", "로그인", "AUTH01-03", "비활성 계정 차단", "비활성화된 계정(is_active=False) 로그인 시도 시 403 Forbidden을 반환한다.", "POST /auth/login"],
    ["AUTH01", "로그인", "AUTH01-04", "인증 실패 처리", "존재하지 않는 계정이나 비밀번호 불일치 시 401 Unauthorized를 반환한다.", "POST /auth/login"],
    ["AUTH02", "내 정보 관리", "AUTH02-01", "프로필 조회", "로그인한 사용자는 자신의 프로필 정보(이름, 부서, 사진 등)를 조회할 수 있다.", "GET /auth/me"],
    ["AUTH02", "내 정보 관리", "AUTH02-02", "비밀번호 변경", "사용자는 자신의 비밀번호를 변경할 수 있다.", "PUT /auth/me"],
    ["AUTH02", "내 정보 관리", "AUTH02-03", "기존 비밀번호 검증", "비밀번호 변경 시 기존 비밀번호 확인이 필요하다.", "PUT /auth/me"],
    ["AUTH02", "내 정보 관리", "AUTH02-04", "프로필 사진 업로드", "사용자는 프로필 사진을 업로드하거나 삭제할 수 있다.", "POST /auth/profile-photo"],
    ["AUTH03", "계정 복구", "AUTH03-01", "비밀번호 재설정", "비밀번호 분실 시 이메일과 사번을 통해 본인 인증 후 재설정할 수 있다.", "POST /auth/reset-password"],
    ["AUTH03", "계정 복구", "AUTH03-02", "아이디 찾기", "이름과 사번을 입력하여 등록된 이메일(아이디)을 확인할 수 있다.", "POST /auth/find-id"],

    # ==================== [CHAT] AI 챗봇 ====================
    ["CHAT01", "RAG 질의응답", "CHAT01-01", "질문 의도 분석", "사용자가 은행 규정이나 업무 매뉴얼에 대해 질문하면 RAG 기술을 활용하여 답변한다.", "POST /chat/"],
    ["CHAT01", "RAG 질의응답", "CHAT01-02", "출처 표기", "답변 생성 시 참조한 문서의 출처(법령명, 조항 등)를 sources 필드에 포함한다.", "POST /chat/"],
    ["CHAT01", "RAG 질의응답", "CHAT01-03", "메타데이터 반환", "응답에 걸린 시간(response_time)과 사용된 모델(model, provider) 정보를 반환한다.", "POST /chat/"],
    ["CHAT02", "일정 생성 대화", "CHAT02-01", "날짜/시간 엔티티 추출", "자연어 대화를 통해 일정을 생성할 수 있다. (예: '내일 2시 회의 잡아줘')", "POST /chat/"],
    ["CHAT02", "일정 생성 대화", "CHAT02-02", "슬롯 필링", "일정 생성 시 시간 정보가 누락되면 '몇 시인가요?'와 같이 되물어 정보를 보완한다.", "POST /chat/"],
    ["CHAT02", "일정 생성 대화", "CHAT02-03", "상태 관리", "pending_actions 상태를 활용하여 대화 컨텍스트를 유지한다.", "-"],
    ["CHAT03", "학습 현황 분석", "CHAT03-01", "성적 데이터 조회", "사용자가 자신의 강점/약점을 물어보면 시험 및 시뮬레이션 결과를 분석하여 답변한다.", "POST /chat/"],
    ["CHAT03", "학습 현황 분석", "CHAT03-02", "취약점 분석", "LearningProgressChatService를 통해 취약 역량을 자동 추출하고 개선 제안을 생성한다.", "-"],
    ["CHAT04", "대화 기록", "CHAT04-01", "기록 저장/조회", "사용자와의 대화 내역을 저장하고 조회할 수 있다.", "GET /chat/history"],

    # ==================== [SCH] 일정 관리 ====================
    ["SCH01", "일정 등록", "SCH01-01", "일정 생성 API", "사용자는 날짜, 시간, 제목, 설명, 장소, 색상을 지정하여 개인 일정을 등록할 수 있다.", "POST /schedules/"],
    ["SCH01", "일정 등록", "SCH01-02", "회사 일정 구분", "관리자가 생성한 일정은 is_company_schedule=true로 설정되어 모든 사용자에게 표시된다.", "POST /schedules/"],
    ["SCH01", "일정 등록", "SCH01-03", "필수값 검증", "start_time이 누락된 경우 400 Bad Request 에러를 반환한다.", "POST /schedules/"],
    ["SCH02", "일정 조회", "SCH02-01", "날짜 범위 필터링", "사용자는 월간/주간/일간 단위로 자신의 일정 + 회사 일정을 조회할 수 있다.", "GET /schedules/"],
    ["SCH02", "일정 조회", "SCH02-02", "기간 필터", "start_date와 end_date 파라미터로 기간을 지정할 수 있다.", "GET /schedules/"],
    ["SCH02", "일정 조회", "SCH02-03", "일정 CRUD", "사용자는 자신이 생성한 일정을 수정하거나 삭제할 수 있다.", "PUT/DELETE /schedules/{id}"],
    ["SCH03", "공휴일 조회", "SCH03-01", "공휴일 API 연동", "연도와 월을 지정하여 공휴일 목록을 조회할 수 있다.", "GET /schedules/holidays"],
    ["SCH03", "공휴일 조회", "SCH03-02", "강제 동기화", "force_refresh=true 옵션으로 공휴일 데이터를 강제 동기화할 수 있다.", "GET /schedules/holidays"],
    ["SCH04", "멘토링 일정", "SCH04-01", "공통 빈 시간 추천", "멘토는 매칭된 멘티들과의 공통된 빈 시간을 자동으로 추천받을 수 있다.", "GET /schedules/common-free-slots"],
    ["SCH04", "멘토링 일정", "SCH04-02", "시간 슬롯 추출", "월~금 11:00~14:00 사이의 가용 시간 슬롯을 추출한다.", "-"],
    ["SCH04", "멘토링 일정", "SCH04-03", "식사 일정 연동", "멘토가 식사 일정을 등록하면 해당 멘티의 캘린더에도 자동으로 일정이 공유된다.", "POST /schedules/mentor-mentee-meal"],

    # ==================== [SIM] RAG 시뮬레이션 ====================
    ["SIM01", "시나리오 선택", "SIM01-01", "페르소나 조회", "시뮬레이션에 사용할 고객 페르소나 목록을 조회할 수 있다.", "GET /rag-simulation/personas"],
    ["SIM01", "시나리오 선택", "SIM01-02", "상황 조회", "시뮬레이션 시나리오(수신, 여신, 카드 등) 목록을 조회할 수 있다.", "GET /rag-simulation/situations"],
    ["SIM01", "시나리오 선택", "SIM01-03", "랜덤 선택", "random=true 옵션으로 카테고리별 1개씩 랜덤 선택된 상황을 조회할 수 있다.", "GET /rag-simulation/situations"],
    ["SIM02", "시뮬레이션 시작", "SIM02-01", "세션 초기화", "페르소나와 상황을 선택하여 시뮬레이션 세션을 시작한다.", "POST /rag-simulation/start-simulation"],
    ["SIM02", "시뮬레이션 시작", "SIM02-02", "초기 데이터 로딩", "시작 시 고객의 초기 인사말(initial_message)과 대화 목표(goals)를 제공한다.", "-"],
    ["SIM03", "음성 대화 처리", "SIM03-01", "STT 변환", "사용자의 음성을 STT로 변환하고, 페르소나에 맞는 응답을 생성한다.", "POST /rag-simulation/process-voice-interaction"],
    ["SIM03", "음성 대화 처리", "SIM03-02", "TTS 변환", "생성된 응답을 TTS로 변환하여 오디오 URL을 반환한다.", "-"],
    ["SIM03", "음성 대화 처리", "SIM03-03", "실시간 점수 계산", "각 턴마다 대화 단계(conversation_phase)와 세션 점수(session_score)를 업데이트한다.", "-"],
    ["SIM03", "음성 대화 처리", "SIM03-04", "RAG 평가", "직원 발화에 대해 RAG 기반 정확성 평가(rag_evaluation)를 수행한다.", "-"],
    ["SIM04", "종합 피드백", "SIM04-01", "역량별 점수 산출", "대화 종료 후 6가지 핵심 역량(지식, 기술, 태도 등)에 대한 점수와 피드백을 생성한다.", "POST /rag-simulation/generate-feedback"],
    ["SIM04", "종합 피드백", "SIM04-02", "강점/약점 분석", "피드백에는 강점, 약점, 개선 제안이 포함된다.", "-"],
    ["SIM04", "종합 피드백", "SIM04-03", "피드백 저장", "생성된 피드백을 DB에 저장하고 이력을 조회할 수 있다.", "GET /rag-simulation/feedback-history"],
    ["SIM05", "녹음 관리", "SIM05-01", "파일 업로드", "시뮬레이션 녹음 파일을 업로드하고 관리할 수 있다.", "POST /rag-simulation/upload-recording"],
    ["SIM06", "테스트 모드", "SIM06-01", "테스트 시나리오", "STT 성능 및 RAG 연동 테스트를 위한 테스트 모드 시뮬레이션을 제공한다.", "POST /rag-simulation/start-test-simulation"],

    # ==================== [QUIZ] 퀴즈 ====================
    ["QUIZ01", "퀴즈 생성", "QUIZ01-01", "랜덤 출제", "랜덤 모드로 지정된 문항 수의 퀴즈 세트를 생성할 수 있다.", "POST /quiz/generate"],
    ["QUIZ01", "퀴즈 생성", "QUIZ01-02", "맞춤 출제", "맞춤 모드로 사용자의 취약 영역 기반 퀴즈 세트를 생성할 수 있다.", "POST /quiz/generate"],
    ["QUIZ01", "퀴즈 생성", "QUIZ01-03", "프로필 필수 검증", "맞춤 모드 사용 시 profile(오답 문제 ID, 카테고리별 점수) 정보가 필수이다.", "POST /quiz/generate"],
    ["QUIZ02", "응시 횟수 제한", "QUIZ02-01", "횟수 제한 관리", "모드별(random, custom, midterm, final)로 일일 응시 횟수가 제한된다.", "-"],
    ["QUIZ02", "응시 횟수 제한", "QUIZ02-02", "제한 초과 에러", "제한 초과 시 403 Forbidden과 함께 안내 메시지를 반환한다.", "POST /quiz/generate"],
    ["QUIZ03", "퀴즈 제출", "QUIZ03-01", "즉시 채점", "답안을 제출하면 즉시 채점 결과(score, correct_count, details)를 반환한다.", "POST /quiz/submit"],
    ["QUIZ03", "퀴즈 제출", "QUIZ03-02", "권한 검증", "제출 시 해당 generation_id가 존재하지 않거나 본인 것이 아니면 404 에러를 반환한다.", "POST /quiz/submit"],
    ["QUIZ04", "퀴즈 기록", "QUIZ04-01", "이력 조회", "사용자의 퀴즈 응시 이력(모드, 점수, 날짜, 카테고리별 통계)을 조회할 수 있다.", "GET /quiz/my-history"],
    ["QUIZ04", "퀴즈 기록", "QUIZ04-02", "잔여 횟수 조회", "사용자의 모드별 남은 응시 횟수를 조회할 수 있다.", "GET /quiz/remaining-attempts"],

    # ==================== [REP] 리포트/대시보드 ====================
    ["REP01", "멘티 대시보드", "REP01-01", "통합 대시보드", "멘티는 자신의 학습 현황, 최근 점수, 멘토 정보를 한눈에 확인할 수 있다.", "GET /dashboard/mentee"],
    ["REP01", "멘티 대시보드", "REP01-02", "데이터 집계", "시험 점수(ExamScore), 시뮬레이션 결과, 퀴즈 통계를 종합하여 표시한다.", "-"],
    ["REP01", "멘티 대시보드", "REP01-03", "차트 데이터 생성", "6대 역량(은행업무, 상품지식, 고객응대 등)을 레이더 차트 데이터로 제공한다.", "-"],
    ["REP01", "멘티 대시보드", "REP01-04", "추세 분석", "시간에 따른 역량 성장 추이를 그래프로 시각화할 수 있는 데이터를 제공한다.", "-"],
    ["REP02", "멘토 대시보드", "REP02-01", "멘티 현황 조회", "멘토는 담당 멘티들의 학습 현황과 성과를 모니터링할 수 있다.", "GET /dashboard/mentor"],
    ["REP02", "멘토 대시보드", "REP02-02", "피드백 전송", "멘토는 멘티에게 텍스트 피드백을 전송할 수 있다.", "POST /dashboard/feedback"],
    ["REP03", "관리자 대시보드", "REP03-01", "매칭 관리", "관리자 또는 멘토가 멘토-멘티 매칭을 설정하거나 해제할 수 있다.", "POST /dashboard/assign-mentor"],
    ["REP03", "관리자 대시보드", "REP03-02", "매칭 현황 조회", "관리자는 전체 멘토-멘티 매칭 현황을 조회할 수 있다.", "GET /dashboard/admin/matching-dashboard"],

    # ==================== [CLUB] 동아리 라운지 ====================
    ["CLUB01", "게시글 관리", "CLUB01-01", "게시글 작성", "사용자는 취미나 관심사를 공유하는 게시글을 작성할 수 있다.", "POST /posts/"],
    ["CLUB01", "게시글 관리", "CLUB01-02", "필드 정의", "게시글에는 제목, 내용, 카테고리를 지정할 수 있다.", "-"],
    ["CLUB01", "게시글 관리", "CLUB01-03", "목록 조회", "최신순 또는 인기순으로 게시글 목록을 조회할 수 있다.", "GET /posts/"],
    ["CLUB01", "게시글 관리", "CLUB01-04", "상세 조회", "게시글 상세 조회 시 해당 게시글의 댓글 목록도 함께 반환된다.", "GET /posts/{post_id}"],
    ["CLUB01", "게시글 관리", "CLUB01-05", "권한 검증", "작성자 본인만 게시글을 수정하거나 삭제할 수 있다.", "PUT/DELETE /posts/{post_id}"],
    ["CLUB02", "댓글 및 모임", "CLUB02-01", "댓글 작성", "게시글에 댓글을 작성할 수 있다.", "POST /posts/comments"],
    ["CLUB02", "댓글 및 모임", "CLUB02-02", "같이하기 신청", "댓글에 '같이하기' 기능을 통해 모임 참여를 신청할 수 있다.", "POST /posts/comments"],
    ["CLUB02", "댓글 및 모임", "CLUB02-03", "같이하기 승인", "게시글 작성자는 '같이하기' 신청을 승인할 수 있다.", "POST /posts/comments/{comment_id}/join"],
]

# ============================================================
# 2. 테스트 케이스 (기능ID 연결)
# 컬럼: TC_ID, 기능ID, Type, 시나리오, 사전조건, 입력 데이터, 기대 결과, 실제 결과
# ============================================================
test_cases_data = [
    # --- [TC] 연수원 관리 ---
    ["TC-TC01-01", "TC01-01", "Positive", "정상 데이터 동기화", "관리자 로그인", "selected_cohort_dates: ['2024-01-01']", "200 OK, 생성된 멘티/멘토 수 반환", ""],
    ["TC-TC02-01", "TC02-01", "Positive", "계정 자동 생성 옵션", "관리자 로그인", "create_accounts: true", "200 OK, created_accounts > 0", ""],
    ["TC-TC03-02", "TC03-02", "Negative", "잘못된 날짜 형식", "관리자 로그인", "selected_cohort_dates: ['invalid-date']", "400 Bad Request", ""],
    ["TC-TC01-02", "TC01-01", "Negative", "비관리자 접근", "일반 사용자 로그인", "동기화 요청", "403 Forbidden", ""],
    ["TC-TC04-02", "TC04-02", "Positive", "멘티 목록 검색", "관리자 로그인", "search: '홍길동'", "200 OK, 검색 결과 반환", ""],

    # --- [AUTH] 인증 ---
    ["TC-AUTH01-01", "AUTH01-01", "Positive", "이메일 로그인 성공", "활성 계정 존재", "Valid Email, Valid Password", "200 OK, Access/Refresh Token 발급", ""],
    ["TC-AUTH01-02", "AUTH01-01", "Positive", "사번 로그인 성공", "활성 계정 존재", "Valid Employee Number, Valid Password", "200 OK, Token 발급", ""],
    ["TC-AUTH01-03", "AUTH01-04", "Negative", "비밀번호 불일치", "계정 존재", "Valid Email, Wrong Password", "401 Unauthorized", ""],
    ["TC-AUTH01-04", "AUTH01-03", "Negative", "비활성 계정 로그인", "is_active=False 계정", "Valid Email, Valid Password", "403 Forbidden", ""],
    ["TC-AUTH01-05", "AUTH01-04", "Negative", "존재하지 않는 계정", "-", "Unknown Email", "401 Unauthorized", ""],
    ["TC-AUTH02-01", "AUTH02-01", "Positive", "내 정보 조회", "로그인 상태", "GET /auth/me", "200 OK, 프로필 정보 반환", ""],
    ["TC-AUTH02-02", "AUTH02-02", "Positive", "비밀번호 변경", "로그인 상태", "기존 PW + 새 PW", "200 OK", ""],
    ["TC-AUTH02-03", "AUTH02-03", "Negative", "기존 비밀번호 틀림", "로그인 상태", "틀린 기존 PW + 새 PW", "400 Bad Request", ""],

    # --- [CHAT] 챗봇 ---
    ["TC-CHAT01-01", "CHAT01-01", "Positive", "규정 질문 답변", "로그인 상태", "'수신 금리 규정 알려줘'", "200 OK, 답변 + sources 포함", ""],
    ["TC-CHAT02-01", "CHAT02-01", "Positive", "일정 생성 (완전한 정보)", "로그인 상태", "'내일 오후 2시 팀 미팅'", "200 OK, 일정 생성 완료 메시지", ""],
    ["TC-CHAT02-02", "CHAT02-02", "Flow", "일정 생성 (시간 누락)", "로그인 상태", "Step1: '회의 잡아줘'\nStep2: '오후 3시'", "Step1: '몇 시인가요?' 응답\nStep2: 일정 생성 완료", ""],
    ["TC-CHAT03-01", "CHAT03-01", "Positive", "학습 약점 분석", "시험/시뮬레이션 기록 있음", "'내 약점이 뭐야?'", "200 OK, 취약 역량 분석 결과", ""],
    ["TC-CHAT03-02", "CHAT03-01", "Edge", "기록 없는 상태에서 분석 요청", "신규 가입 직후", "'내 강점 알려줘'", "200 OK, '데이터 부족' 안내 메시지", ""],

    # --- [SCH] 일정 관리 ---
    ["TC-SCH01-01", "SCH01-01", "Positive", "일정 직접 등록", "로그인 상태", "title, start_time, end_time", "201 Created, 일정 ID 반환", ""],
    ["TC-SCH01-02", "SCH01-03", "Negative", "필수값 누락", "로그인 상태", "title만 입력 (start_time 없음)", "400 Bad Request", ""],
    ["TC-SCH02-01", "SCH02-01", "Positive", "일정 목록 조회", "로그인 상태", "start_date, end_date", "200 OK, 일정 리스트 반환", ""],
    ["TC-SCH03-01", "SCH03-01", "Positive", "공휴일 조회", "로그인 상태", "year: 2024, month: 12", "200 OK, 공휴일 리스트", ""],
    ["TC-SCH04-01", "SCH04-01", "Positive", "공통 빈 시간 조회", "멘토 로그인, 멘티 매칭됨", "-", "200 OK, 시간 슬롯 리스트", ""],
    ["TC-SCH04-02", "SCH04-03", "Negative", "매칭 안 된 멘티와 식사 등록", "멘토 로그인", "mentee_id: 999", "403 or 404 에러", ""],

    # --- [SIM] 시뮬레이션 ---
    ["TC-SIM01-01", "SIM01-01", "Positive", "페르소나 목록 조회", "로그인 상태", "-", "200 OK, 페르소나 리스트", ""],
    ["TC-SIM01-02", "SIM01-03", "Positive", "상황 목록 조회 (랜덤)", "로그인 상태", "random=true", "200 OK, 카테고리별 1개씩", ""],
    ["TC-SIM02-01", "SIM02-01", "Positive", "시뮬레이션 세션 시작", "로그인 상태", "persona_id, situation_id", "200 OK, session_id, initial_message", ""],
    ["TC-SIM03-01", "SIM03-01", "Positive", "음성 입력 처리", "세션 시작됨", "Audio File (WAV/WebM)", "200 OK, transcribed_text, customer_response, audio_url", ""],
    ["TC-SIM03-02", "SIM03-01", "Negative", "지원하지 않는 오디오 포맷", "세션 시작됨", "Audio File (EXE)", "400 or 500 에러 (Graceful)", ""],
    ["TC-SIM04-01", "SIM04-01", "Positive", "피드백 생성", "대화 10턴 이상 완료", "conversation_history", "200 OK, 6개 역량 점수, 강점/약점/개선점", ""],
    ["TC-SIM04-02", "SIM04-03", "Positive", "피드백 이력 조회", "피드백 1건 이상 존재", "-", "200 OK, 피드백 리스트", ""],

    # --- [QUIZ] 퀴즈 ---
    ["TC-QUIZ01-01", "QUIZ01-01", "Positive", "랜덤 퀴즈 생성", "로그인 상태", "mode: random, total_questions: 10", "200 OK, 문제 리스트, generation_id", ""],
    ["TC-QUIZ01-02", "QUIZ01-02", "Positive", "맞춤 퀴즈 생성", "로그인 상태", "mode: custom, profile 포함", "200 OK, 취약 영역 중심 문제", ""],
    ["TC-QUIZ01-03", "QUIZ01-03", "Negative", "맞춤 모드 profile 누락", "로그인 상태", "mode: custom, profile 없음", "400 Bad Request", ""],
    ["TC-QUIZ02-01", "QUIZ02-02", "Negative", "응시 횟수 초과", "오늘 이미 최대 응시", "퀴즈 생성 요청", "403 Forbidden, 안내 메시지", ""],
    ["TC-QUIZ03-01", "QUIZ03-01", "Positive", "퀴즈 제출 및 채점", "퀴즈 생성됨", "generation_id, answers", "200 OK, score, correct_count, details", ""],
    ["TC-QUIZ03-02", "QUIZ03-02", "Negative", "타인의 퀴즈 제출 시도", "로그인 상태", "다른 사용자의 generation_id", "404 Not Found", ""],
    ["TC-QUIZ04-01", "QUIZ04-01", "Positive", "퀴즈 이력 조회", "퀴즈 1회 이상 응시", "-", "200 OK, 이력 리스트", ""],

    # --- [REP] 리포트/대시보드 ---
    ["TC-REP01-01", "REP01-01", "Positive", "멘티 대시보드 로딩", "멘티 로그인", "-", "200 OK, exam_scores, simulation_results 포함", ""],
    ["TC-REP02-01", "REP02-01", "Positive", "멘토 대시보드 로딩", "멘토 로그인", "-", "200 OK, 담당 멘티 리스트 및 현황", ""],
    ["TC-REP02-02", "REP02-02", "Positive", "멘토 피드백 전송", "멘토 로그인", "mentee_id, feedback_text", "200 OK", ""],
    ["TC-REP03-01", "REP03-01", "Positive", "멘토 배정", "관리자 로그인", "mentor_id, mentee_id", "200 OK, 매칭 완료", ""],

    # --- [CLUB] 동아리 라운지 ---
    ["TC-CLUB01-01", "CLUB01-01", "Positive", "게시글 작성", "로그인 상태", "title, content, category", "200 OK, 게시글 ID", ""],
    ["TC-CLUB01-02", "CLUB01-03", "Positive", "게시글 목록 조회", "로그인 상태", "-", "200 OK, 게시글 리스트", ""],
    ["TC-CLUB01-03", "CLUB01-04", "Positive", "게시글 상세 조회", "게시글 존재", "post_id", "200 OK, 게시글 + 댓글 리스트", ""],
    ["TC-CLUB01-04", "CLUB01-05", "Negative", "타인 게시글 삭제 시도", "로그인 상태", "타인의 post_id", "403 Forbidden", ""],
    ["TC-CLUB02-01", "CLUB02-02", "Positive", "같이하기 신청", "로그인 상태", "comment with join request", "200 OK, join_status: pending", ""],
    ["TC-CLUB02-02", "CLUB02-03", "Positive", "같이하기 승인", "게시글 작성자 로그인", "comment_id", "200 OK, join_status: approved", ""],
]

# DataFrame 생성
df_req = pd.DataFrame(requirements_data, columns=['요구사항ID', '요구사항명', '기능ID', '기능명', '상세 설명', 'API Endpoint'])
df_tc = pd.DataFrame(test_cases_data, columns=['TC_ID', '기능ID', 'Type', '시나리오', '사전조건', '입력 데이터', '기대 결과', '실제 결과'])

# 엑셀 파일 저장
file_path = "docs/standardized/CANT_Requirements_and_TC_Coded.xlsx"
with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
    df_req.to_excel(writer, index=False, sheet_name='요구사항정의서')
    df_tc.to_excel(writer, index=False, sheet_name='테스트케이스')
    
    # 서식 조정
    workbook = writer.book
    
    # 요구사항정의서 시트 서식
    ws_req = writer.sheets['요구사항정의서']
    ws_req.column_dimensions['A'].width = 12  # 요구사항ID
    ws_req.column_dimensions['B'].width = 20  # 요구사항명
    ws_req.column_dimensions['C'].width = 12  # 기능ID
    ws_req.column_dimensions['D'].width = 22  # 기능명
    ws_req.column_dimensions['E'].width = 55  # 상세 설명
    ws_req.column_dimensions['F'].width = 40  # API Endpoint
    
    # 테스트케이스 시트 서식
    ws_tc = writer.sheets['테스트케이스']
    ws_tc.column_dimensions['A'].width = 15  # TC_ID
    ws_tc.column_dimensions['B'].width = 12  # 기능ID
    ws_tc.column_dimensions['C'].width = 10  # Type
    ws_tc.column_dimensions['D'].width = 28  # 시나리오
    ws_tc.column_dimensions['E'].width = 22  # 사전조건
    ws_tc.column_dimensions['F'].width = 35  # 입력 데이터
    ws_tc.column_dimensions['G'].width = 45  # 기대 결과
    ws_tc.column_dimensions['H'].width = 15  # 실제 결과

    # 헤더 스타일 적용
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True)
    
    for sheet in [ws_req, ws_tc]:
        for cell in sheet[1]:
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal='center', vertical='center')

print(f"✅ 코드화된 최종 파일 생성 완료: {file_path}")
print(f"   - 요구사항정의서: {len(df_req)}건")
print(f"   - 테스트케이스: {len(df_tc)}건")

