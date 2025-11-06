# 🧪 로컬 테스트 가이드

## 빠른 시작

### 1️⃣ 데이터베이스 확인
```bash
# PostgreSQL 컨테이너가 실행 중인지 확인
docker ps --filter "name=mentor-postgres"

# 실행되지 않았다면 시작
docker-compose up postgres -d
```

### 2️⃣ 백엔드 서버 실행
```bash
# 방법 1: 배치 파일 사용 (권장)
.\run-backend.bat

# 방법 2: 수동 실행
cd backend
.\venv\Scripts\activate.bat
python -m app.main
```

백엔드 서버가 실행되면:
- API 서버: http://localhost:8000
- API 문서: http://localhost:8000/docs

### 3️⃣ 프론트엔드 서버 실행
```bash
# 방법 1: 배치 파일 사용 (권장)
.\run-frontend.bat

# 방법 2: 수동 실행
cd frontend
npm install  # 처음 실행 시
npm run dev
```

프론트엔드 서버가 실행되면:
- 웹 애플리케이션: http://localhost:3000

### 4️⃣ 전체 상태 확인
```bash
.\test-local.bat
```

## 📋 테스트 체크리스트

### ✅ 로그인 테스트

#### 1. 사번/생년월일 로그인 (새 기능)
- **사번**: `2023001`
- **비밀번호**: `19970127` (YYYYMMDD 형식)
- ✅ 사번으로 로그인 가능
- ✅ 생년월일이 비밀번호로 작동

#### 2. 기존 이메일 로그인 (하위 호환)
- **이메일**: `mentee@bank.com`
- **비밀번호**: `mentee123`
- ✅ 기존 계정도 정상 작동

#### 3. 관리자 로그인
- **이메일**: `admin@bank.com`
- **비밀번호**: `admin123`

### ✅ 마이페이지 테스트

1. **프로필 정보 수정**
   - 주소(`address`) 수정 가능
   - 직책(`position`) 수정 가능
   - 이메일, 전화번호 수정 가능

2. **QR 코드 제거 확인**
   - ✅ QR 코드 관련 UI가 제거되었는지 확인

### ✅ 비밀번호 재설정 테스트

1. **사번 + 생년월일로 재설정**
   - 사번: `2023001`
   - 생년월일: `19970127`
   - 새 비밀번호 설정 가능

### ✅ 관리자 기능 테스트

1. **Excel 파일 업로드**
   - 관리자 계정으로 로그인
   - `/admin/upload-excel` 엔드포인트에 Excel 파일 업로드
   - 필수 컬럼:
     - `name`, `join_year`, `employee_number`, `position`, `team`, `birth`
   - 선택 컬럼:
     - `email`, `phone`, `address` (빈 값 가능)
   - 시험 데이터:
     - 6개 영역 × 10문제 (0/1 점수)
     - 자동으로 0-10점, 총점 60점, 등급 계산

2. **업로드 결과 확인**
   - 사용자 계정 생성/업데이트 확인
   - 시험 점수 저장 확인
   - 멘티 대시보드에서 점수 표시 확인

## 🐛 문제 해결

### 백엔드가 시작되지 않는 경우

1. **가상환경 확인**
   ```bash
   cd backend
   python -m venv venv
   .\venv\Scripts\activate.bat
   pip install -r requirements.txt
   ```

2. **데이터베이스 연결 확인**
   ```bash
   # PostgreSQL이 실행 중인지 확인
   docker ps --filter "name=mentor-postgres"
   
   # 연결 테스트
   python -c "from app.database import engine; engine.connect()"
   ```

3. **포트 충돌 확인**
   - 8000번 포트가 사용 중인지 확인
   - 다른 애플리케이션 종료 또는 포트 변경

### 프론트엔드가 시작되지 않는 경우

1. **의존성 설치**
   ```bash
   cd frontend
   npm install
   ```

2. **포트 충돌 확인**
   - 3000번 포트가 사용 중인지 확인

### 데이터베이스 스키마 이슈

새로운 필드(`birth`, `address`)가 추가되었으므로, 서버 시작 시 자동으로 테이블이 업데이트됩니다.

만약 문제가 발생하면:
```bash
cd backend
.\venv\Scripts\activate.bat
python -c "from app.database import init_db; init_db()"
```

## 📝 테스트 시나리오

### 시나리오 1: 새 사용자 로그인
1. 관리자가 Excel 파일 업로드
2. 사번 `2023001`, 생년월일 `19970127`로 계정 생성
3. 해당 정보로 로그인 시도
4. ✅ 로그인 성공 확인

### 시나리오 2: 프로필 수정
1. 로그인 후 마이페이지 접속
2. 주소와 직책 수정
3. 저장 후 변경사항 확인
4. ✅ 수정된 정보가 저장되었는지 확인

### 시나리오 3: 시험 점수 확인
1. Excel 파일에 시험 데이터 포함
2. 관리자가 업로드
3. 멘티 대시보드 접속
4. ✅ 6개 영역 점수 및 총점 확인

## 🔗 유용한 링크

- **API 문서**: http://localhost:8000/docs
- **프론트엔드**: http://localhost:3000
- **pgAdmin** (개발 환경): http://localhost:5050

## 💡 참고사항

- 모든 변경사항은 데이터베이스에 자동 반영됩니다
- 기존 테스트 계정은 그대로 사용 가능합니다
- 새로운 사번 기반 계정은 Excel 업로드를 통해 생성됩니다

