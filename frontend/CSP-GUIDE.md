# Content Security Policy (CSP) 가이드

## 문제 상황

브라우저 개발자 도구에서 다음과 같은 CSP 경고가 나타날 수 있습니다:

```
Content Security Policy of your site blocks the use of 'eval' in JavaScript
```

## 원인

1. **Vite 개발 서버**는 Hot Module Replacement (HMR)를 위해 `eval()` 사용
2. **브라우저 확장 프로그램** 또는 **브라우저 보안 설정**이 CSP 적용
3. 두 가지가 충돌하여 경고 발생

## 해결 방법

### ✅ 이미 적용된 해결책

`index.html`에 개발 환경용 CSP 메타 태그를 추가했습니다:

```html
<meta http-equiv="Content-Security-Policy" 
      content="... 'unsafe-eval' ...">
```

이것은:
- ✅ 개발 환경에서 Vite HMR이 정상 작동
- ✅ CSP 경고 제거
- ✅ 로컬 환경에서만 사용되므로 안전

### 🔒 프로덕션 배포 시

프로덕션에는 `index.prod.html`을 사용하세요 (unsafe-eval 없음):

```bash
# 프로덕션 빌드
npm run build

# index.prod.html을 사용하도록 설정
cp index.prod.html dist/index.html
```

## 확인 방법

### 1. 브라우저 새로고침
```
Ctrl + Shift + R (하드 리프레시)
```

### 2. 개발자 도구 확인
```
F12 → Console 탭
```

CSP 경고가 사라져야 합니다!

### 3. 네트워크 탭 확인
```
F12 → Network 탭 → localhost:3000 → Headers → Response Headers
```

`content-security-policy` 헤더 확인

## 여전히 경고가 나타난다면?

### A. 브라우저 캐시 제거

```
F12 → Application → Storage → Clear site data
```

### B. 브라우저 확장 프로그램 비활성화

1. `chrome://extensions/` 접속
2. 보안 관련 확장 프로그램 비활성화
3. 페이지 새로고침

### C. 시크릿 모드에서 테스트

```
Ctrl + Shift + N
```

시크릿 모드에서 `http://localhost:3000` 접속

### D. 다른 브라우저에서 테스트

- Chrome 대신 Firefox 사용
- Edge 사용

## 보안 참고사항

### 개발 환경 (현재)
- `unsafe-eval` 사용: **안전함** ✅
  - 로컬 환경에서만 실행
  - 인터넷에 노출되지 않음
  - Vite HMR 필수 기능

### 프로덕션 환경
- `unsafe-eval` 사용: **위험함** ⚠️
  - 반드시 `index.prod.html` 사용
  - 또는 Nginx에서 안전한 CSP 설정

## 참고 문서

- [Vite CSP 관련 이슈](https://github.com/vitejs/vite/issues/2700)
- [Content Security Policy - MDN](https://developer.mozilla.org/en-US/docs/Web/HTTP/CSP)
- 프로젝트의 `SECURITY.md` 참조





