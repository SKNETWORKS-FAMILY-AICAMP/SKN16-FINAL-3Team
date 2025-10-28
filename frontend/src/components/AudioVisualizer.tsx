import React, { useEffect, useRef } from 'react';

interface AudioVisualizerProps {
  isRecording: boolean;
  stream: MediaStream | null;
}

/**
 * 실시간 오디오 파형 시각화 컴포넌트
 */
export const AudioVisualizer: React.FC<AudioVisualizerProps> = ({ isRecording, stream }) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animationFrameRef = useRef<number>();
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const dataArrayRef = useRef<Uint8Array | null>(null);

  useEffect(() => {
    if (!isRecording || !stream) {
      // 녹음 중지 시 파형도 정지
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
      if (audioContextRef.current) {
        audioContextRef.current.close();
      }
      return;
    }

    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    try {
      // AudioContext 초기화
      const audioContext = new (window.AudioContext || (window as any).webkitAudioContext)();
      const analyser = audioContext.createAnalyser();
      const source = audioContext.createMediaStreamSource(stream);

      analyser.fftSize = 256;
      analyser.smoothingTimeConstant = 0.8;
      source.connect(analyser);

      audioContextRef.current = audioContext;
      analyserRef.current = analyser;
      dataArrayRef.current = new Uint8Array(analyser.frequencyBinCount);

      // 파형 그리기
      const draw = () => {
        if (!isRecording) return;

        animationFrameRef.current = requestAnimationFrame(draw);

        const bufferLength = analyser.frequencyBinCount;
        const dataArray = dataArrayRef.current;

        if (!dataArray) return;

        analyser.getByteFrequencyData(dataArray);

        // 캔버스 초기화
        ctx.fillStyle = '#1e293b';
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        // 파형 그리기
        const barWidth = (canvas.width / bufferLength) * 2.5;
        let barHeight;
        let x = 0;

        for (let i = 0; i < bufferLength; i++) {
          barHeight = dataArray[i] / 2;

          // 그라데이션 (녹색 → 노란색 → 빨간색)
          const gradient = ctx.createLinearGradient(0, 0, 0, canvas.height);
          gradient.addColorStop(0, '#10b981'); // 초록
          gradient.addColorStop(0.5, '#fbbf24'); // 노랑
          gradient.addColorStop(1, '#ef4444'); // 빨강

          ctx.fillStyle = gradient;
          ctx.fillRect(x, canvas.height - barHeight, barWidth, barHeight);

          x += barWidth + 1;
        }

        // 실시간 볼륨 표시
        const average = dataArray.reduce((a, b) => a + b) / bufferLength;
        const volume = Math.round((average / 255) * 100);
        
        ctx.fillStyle = '#ffffff';
        ctx.font = '16px Arial';
        ctx.fillText(`볼륨: ${volume}%`, 10, 25);
      };

      draw();
    } catch (error) {
      console.error('오디오 분석 실패:', error);
    }

    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
      if (audioContextRef.current) {
        audioContextRef.current.close();
      }
    };
  }, [isRecording, stream]);

  return (
    <div className="w-full bg-slate-800 rounded-lg p-4">
      <canvas
        ref={canvasRef}
        width={600}
        height={150}
        className="w-full h-full rounded"
      />
      {isRecording && (
        <div className="mt-2 flex items-center justify-center">
          <div className="flex items-center space-x-2 text-green-400">
            <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse" />
            <span className="text-sm font-medium">녹음 중...</span>
          </div>
        </div>
      )}
    </div>
  );
};
