import { create } from 'zustand';

type Persona = {
  persona_id: string;
  avatarUrl: string;  // RPM GLB URL
  voicePreset: string; // "ko_female_50s_1" ...
  gender: 'male' | 'female';
  age_group: string;
  type: string; // "보수형", "실용형" 등
};

type AudioBundle = {
  audioUrl: string;     // TTS mp3/wav URL
  text: string;         // 대화 텍스트
  mouthCues?: Array<{ start: number; end: number; value: string }>;
};

type State = {
  persona: Persona | null;
  currentAudio: AudioBundle | null;
  setPersona: (p: Persona) => void;
  setAudio: (a: AudioBundle | null) => void;
  clearSession: () => void;
};

export const usePersonaStore = create<State>((set) => ({
  persona: null,
  currentAudio: null,
  
  setPersona: (persona) => set({ persona }),
  
  setAudio: (audio) => set({ currentAudio: audio }),
  
  clearSession: () => set({ persona: null, currentAudio: null })
}));

