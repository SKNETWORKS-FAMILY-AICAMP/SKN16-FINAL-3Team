export interface MouthCue {
  start: number;
  end: number;
  value: string;
}

export interface LipsyncData {
  audioUrl: string;
  mouthCues: MouthCue[];
}

