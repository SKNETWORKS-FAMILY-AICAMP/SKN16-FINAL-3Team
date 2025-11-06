/**
 * Rhubarb mouth cue value(A,B,C,...) -> morph target 이름과 가중치 매핑
 * RPM 아바타마다 morph target 이름이 다를 수 있으므로 확인 필요
 */
export const VISEME_TO_MORPH: Record<string, { key: string; weight: number }> = {
  "A": { key: "viseme_AA", weight: 1.0 },
  "B": { key: "viseme_CH", weight: 1.0 },
  "C": { key: "viseme_DD", weight: 1.0 },
  "D": { key: "viseme_E", weight: 0.8 },
  "E": { key: "viseme_FF", weight: 1.0 },
  "F": { key: "viseme_I", weight: 0.6 },
  "G": { key: "viseme_k", weight: 0.6 },
  "H": { key: "viseme_nn", weight: 0.5 },
  "X": { key: "jawOpen", weight: 0.0 }, // 무음/닫음
};

/**
 * 페르소나별 표정 (감정) 매핑
 * type에 따라 블렌드셰이프 가중치 조정
 */
export const PERSONA_EXPRESSIONS: Record<string, Record<string, number>> = {
  "실용형": {
    "browUp": 0.1,
    "smile": 0.2,
    "eyeSquint": 0.1
  },
  "보수형": {
    "browDown": 0.1,
    "snarl": 0.05,
    "smile": 0.1
  },
  "불만형": {
    "browDown": 0.5,
    "snarl": 0.4,
    "jawOpen": 0.2
  },
  "긍정형": {
    "browUp": 0.3,
    "smile": 0.6,
    "eyeSquint": 0.3
  },
  "급함형": {
    "browUp": 0.4,
    "snarl": 0.2,
    "jawOpen": 0.3
  }
};

