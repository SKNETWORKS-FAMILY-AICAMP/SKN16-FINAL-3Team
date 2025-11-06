# 고객 아바타 + 립싱크 시뮬레이션 시스템

## 📋 개요

신입사원 온보딩 시뮬레이션에 **Ready Player Me(RPM) 아바타 + Rhubarb LipSync**를 통합하여 고객이 음성과 표정으로 응답하도록 구현합니다.

## 🎯 주요 기능

1. **페르소나별 아바타**: 고객 타입(실용형/보수형/불만형 등)에 맞는 RPM 아바타
2. **LipSync**: Rhubarb로 오디오 → viseme 타임라인 생성
3. **표정**: 페르소나별로 다른 블렌드셰이프 가중치
4. **TTS 통합**: OpenAI TTS로 생성된 음성을 아바타가 말하도록 동기화

## 📦 설치

### 프론트엔드

```bash
cd frontend
npm install three @react-three/fiber @react-three/drei zustand --legacy-peer-deps
```

> 참고: React 18과 호환되는 버전 사용

### 백엔드 (선택)

Rhubarb LipSync를 Docker에 설치하려면:

```dockerfile
# Dockerfile에 추가
RUN apt-get update && apt-get install -y \
    rhubarb \
    && rm -rf /var/lib/apt/lists/*
```

또는 pip로 설치:
```bash
pip install rhubarb-lip-sync
```

## 🏗️ 아키텍처

```
┌─────────────────────┐
│ VoiceSimulation.tsx │ ← 사용자가 음성/텍스트 입력
└──────────┬──────────┘
           │
           ├─→ API → TTS (OpenAI) → audio.mp3
           │                            │
           │                            ↓
           └───────→ CustomerAvatar ────┼──→ Rhubarb → mouthCues
                                         │
                                         ↓
                                    아바타 립싱크 재생
```

## 🔧 파일 구조

```
frontend/src/
├── components/
│   ├── CustomerAvatar.tsx         # RPM 아바타 표시
│   └── AudioVisualizer.tsx       # (기존)
├── pages/
│   └── VoiceSimulation.tsx       # (수정됨 - 아바타 통합)
├── store/
│   └── usePersonaStore.ts        # 전역 상태 (페르소나 + 오디오)
└── lib/
    ├── rpm/
    │   └── rpmHelper.ts           # RPM URL 생성
    └── lipsync/
        ├── types.ts               # MouthCue 타입
        └── visemeMap.ts           # viseme → morph 매핑

backend/app/routers/
└── lipsync.py                     # Rhubarb API 엔드포인트
```

## 🚀 사용 방법

### 1. RPM 아바타 URL 준비

```typescript
// frontend/src/lib/rpm/rpmHelper.ts
export const PERSONA_AVATARS: Record<string, string> = {
  'p_20s_student_lowlit_practical_f': 'https://models.readyplayer.me/avatar1.glb',
  'p_30s_officeworker_lowlit_conservative_m': 'https://models.readyplayer.me/avatar2.glb',
  // ...
}
```

### 2. 시뮬레이션 실행

1. IQ Style Simulation에서 페르소나 선택 (성별/나이/타입)
2. VoiceSimulation에서 아바타가 표시됨
3. 사용자가 음성/텍스트 입력
4. **고객이 음성+표정으로 응답**

### 3. LipSync 적용 (선택)

```typescript
// TTS 오디오 + Rhubarb JSON 연동
const audioUrl = "/api/tts/output.mp3"
const form = new FormData()
form.append('file', audioBlob)

const rs = await fetch('/lipsync/generate', {
  method: 'POST',
  body: form
})

const { mouthCues } = await rs.json()

// 아바타 상태 업데이트
setAudio({ audioUrl, mouthCues })
```

## 🎨 페르소나별 표정 매핑

```typescript
// frontend/src/lib/lipsync/visemeMap.ts
export const PERSONA_EXPRESSIONS = {
  "실용형": { browUp: 0.1, smile: 0.2 },
  "보수형": { browDown: 0.1, snarl: 0.05 },
  "불만형": { browDown: 0.5, snarl: 0.4 },
  // ...
}
```

## ⚠️ 주의사항

1. **morphTarget 이름**: RPM 아바타마다 morph target 이름이 다를 수 있으므로 콘솔로 확인 필요
2. **Rhubarb 설치**: Docker 컨테이너에 Rhubarb CLI가 설치되어 있어야 함
3. **GLB 파일**: 실제 배포 시 RPM GLB 파일을 CDN이나 로컬에 저장

## 🔍 다음 단계

- [ ] Three.js 렌더링 구현 (`@react-three/fiber`)
- [ ] morphTarget 자동 탐색 유틸
- [ ] viseme 전환 lerp 보간
- [ ] 웹오디오 분석 기반 간이 립싱크 (fallback)

## 📝 참고

- [Ready Player Me](https://readyplayer.me)
- [Rhubarb LipSync](https://github.com/DanielSWolf/rhubarb-lip-sync)
- [React Three Fiber](https://docs.pmnd.rs/react-three-fiber/)

