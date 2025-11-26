# Git Pull 후 작업 가이드 (Cursor 사용자용)

## 🚀 빠른 시작 (3단계)

### 1. Git Pull
```
git pull origin main
```

### 2. Docker 재빌드 및 시작
```
docker-compose down
docker-compose build --no-cache backend
docker-compose up -d
```

### 3. 마이그레이션 확인 (선택사항)
백엔드가 시작되면 자동으로 마이그레이션이 실행되지만, 확실하게 하려면:
```
docker-compose exec backend python -c "from app.database import init_db; init_db()"
```

---

## 📋 상세 설명

### 왜 이렇게 해야 하나요?

1. **Git Pull**: 최신 코드 받기
2. **Docker 재빌드**: 변경된 코드 반영
3. **마이그레이션**: 데이터베이스 스키마 업데이트 (새로운 컬럼 추가 등)

### 마이그레이션은 필수인가요?

**아니요!** 백엔드 서버가 시작될 때 자동으로 `init_db()`가 실행되어 마이그레이션이 자동으로 수행됩니다.

하지만 **오류가 발생하는 경우**에만 수동으로 실행하세요:
```
docker-compose exec backend python -c "from app.database import init_db; init_db()"
```

---

## 🔍 문제 발생 시

### 연수원 DB 500 오류가 발생하면?

1. **스키마 확인**:
   ```
   check_training_schema.bat
   ```
   또는
   ```
   docker-compose exec backend python backend/scripts/check_training_center_schema.py
   ```

2. **수동 마이그레이션 실행**:
   ```
   docker-compose exec backend python -c "from app.database import init_db; init_db()"
   ```

3. **백엔드 재시작**:
   ```
   docker-compose restart backend
   ```

---

## 💡 Cursor에게 명령하기 (복사해서 사용하세요!)

### 방법 1: 간단한 버전 (권장) ⭐
```
git pull origin main 하고 docker-compose down 후 docker-compose build --no-cache backend 하고 docker-compose up -d 해줘
```

### 방법 2: 마이그레이션까지 확실하게 (오류 발생 시)
```
git pull origin main 하고 docker-compose down 후 docker-compose build --no-cache backend 하고 docker-compose up -d 한 다음, docker-compose exec backend python -c "from app.database import init_db; init_db()" 실행해줘
```

### 방법 3: 문제 발생 시 진단
```
연수원 DB 500 오류가 발생했어. check_training_schema.bat 실행해서 스키마 확인하고, 필요하면 마이그레이션 실행해줘
```

### 방법 4: 한 줄로 간단하게
```
git pull origin main 하고 docker 재빌드 후 compose up 해줘
```

---

## ⚠️ 주의사항

- **데이터 손실 주의**: `docker-compose down -v`는 **절대 사용하지 마세요!** (모든 데이터가 삭제됩니다)
- **백엔드만 재빌드**: 프론트엔드는 보통 재빌드할 필요 없습니다
- **마이그레이션은 자동**: 백엔드 시작 시 자동 실행되므로 수동 실행은 선택사항입니다

---

## ✅ 체크리스트

Git pull 후:
- [ ] `git pull origin main` 완료
- [ ] `docker-compose down` 완료
- [ ] `docker-compose build --no-cache backend` 완료
- [ ] `docker-compose up -d` 완료
- [ ] (선택) 마이그레이션 확인
- [ ] 브라우저에서 http://localhost:3000 접속 확인

---

## 🆘 여전히 오류가 발생하면?

1. 백엔드 로그 확인:
   ```
   docker-compose logs backend
   ```

2. 데이터베이스 로그 확인:
   ```
   docker-compose logs postgres
   ```

3. 스키마 진단 도구 실행:
   ```
   check_training_schema.bat
   ```

4. `TRAINING_CENTER_TROUBLESHOOTING.md` 파일 참고

