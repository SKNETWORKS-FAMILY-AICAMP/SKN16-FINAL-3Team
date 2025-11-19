# 🔄 DB 마이그레이션 가이드

## 📌 언제 실행해야 하나요?

다음과 같은 경우 마이그레이션 스크립트를 실행해야 합니다:

1. **git pull 후 시뮬레이션 기능이 작동하지 않을 때**
2. **"column does not exist" 같은 DB 오류가 발생할 때**
3. **팀원이 DB 스키마를 변경했다고 알려줄 때**

---

## 🚀 실행 방법

### **Windows (PowerShell)**:
```bash
cd backend
python scripts/migrate_conversation_log.py
```

### **Mac/Linux**:
```bash
cd backend
python scripts/migrate_conversation_log.py
```

---

## 📊 이 마이그레이션이 하는 일

### **추가되는 컬럼**:
- `conversation_log` (TEXT) - 시뮬레이션 대화 로그 저장

### **영향**:
- ✅ 기존 데이터는 그대로 유지됩니다
- ✅ 새로운 시뮬레이션부터 대화 로그가 저장됩니다
- ✅ 피드백 상세보기에서 대화 내용을 확인할 수 있습니다

---

## ✅ 확인 방법

마이그레이션 후 다음과 같이 확인하세요:

1. **성공 메시지 확인**:
   ```
   ✅ conversation_log 컬럼 추가 완료!
   ```

2. **또는 이미 있는 경우**:
   ```
   ✅ conversation_log 컬럼이 이미 존재합니다.
   ```

---

## 🔧 문제 해결

### **Q: "permission denied" 오류가 발생합니다**
**A**: PostgreSQL이 실행 중인지 확인하세요.
```bash
docker ps | findstr postgres
```

### **Q: "connection refused" 오류가 발생합니다**
**A**: DB가 실행 중이 아닙니다. Docker Compose로 시작하세요.
```bash
docker-compose up -d postgres
```

### **Q: 마이그레이션을 다시 실행해도 되나요?**
**A**: 네! 스크립트는 멱등성(idempotent)이므로 여러 번 실행해도 안전합니다.

---

## 📝 개발자를 위한 노트

새로운 DB 스키마 변경 시:
1. `backend/app/models/` 에서 모델 수정
2. `backend/scripts/` 에 마이그레이션 스크립트 추가
3. 이 README에 실행 방법 문서화
4. 팀원들에게 공지

---

**마지막 업데이트**: 2025-11-07
**관련 기능**: 시뮬레이션 피드백, 대화 로그 저장

