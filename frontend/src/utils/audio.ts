// 안전한 오디오 재생 유틸 (atob + fetch(data:) 없이 동작)

/**
 * 안전한 base64 → Blob 변환 (로컬 디코딩)
 */
function base64ToBlobSafe(input: string, mime: string): Blob {
  // data: 접두 제거
  const comma = input.indexOf(',');
  let b64 = input.startsWith('data:') && comma !== -1 ? input.slice(comma + 1) : input;

  // URL-safe → 표준, 공백 제거, 패딩
  b64 = b64.replace(/-/g, '+').replace(/_/g, '/').replace(/\s+/g, '');
  const pad = b64.length % 4;
  if (pad) b64 += '='.repeat(4 - pad);

  // atob로 디코드
  const bin = atob(b64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);

  return new Blob([bytes], { type: mime });
}

/**
 * 다양한 형태의 오디오 페이로드를 재생 (fetch(data:) 금지!)
 */
export async function playFromAnyAudioPayload(payload: any, mimeHint = 'audio/wav'): Promise<void> {
  console.groupCollapsed('🎧 오디오 재생 디버그');
  console.log('payload:', payload);
  console.log('payload 타입:', typeof payload);

  const audio = new Audio();

  try {
    // 1) HTTP(S) URL
    if (typeof payload === 'string' && /^https?:\/\//.test(payload)) {
      audio.src = payload;
      await audio.play();
      console.log('🎵 오디오 재생 성공 (URL)');
      console.groupEnd();
      return;
    }

    // 2) data URL (fetch 금지! 직접 재생)
    if (typeof payload === 'string' && payload.startsWith('data:')) {
      audio.src = payload;
      await audio.play();
      console.log('🎵 오디오 재생 성공 (data URL 직결)');
      console.groupEnd();
      return;
    }

    // 3) { base64, mime } or pure base64 string → 로컬 디코딩 후 blob:
    const { base64, mime } =
      typeof payload === 'string'
        ? { base64: payload, mime: mimeHint }
        : { base64: payload?.base64, mime: payload?.mime ?? mimeHint };

    if (base64) {
      const blob = base64ToBlobSafe(base64, mime);
      const url = URL.createObjectURL(blob);
      audio.src = url;
      await audio.play();
      console.log('🎵 오디오 재생 성공 (base64→blob)');
      audio.onended = () => URL.revokeObjectURL(url);
      console.groupEnd();
      return;
    }

    // 4) { dataUrl } 객체
    if (payload?.dataUrl) {
      const mime = payload?.mime ?? mimeHint;
      if (payload.dataUrl.startsWith('data:')) {
        // data URL은 직접 재생
        audio.src = payload.dataUrl;
      } else {
        // blob URL
        audio.src = payload.dataUrl;
      }
      await audio.play();
      console.log('🎵 오디오 재생 성공 (dataUrl 객체)');
      console.groupEnd();
      return;
    }

    // 5) ArrayBuffer/TypedArray
    if (payload instanceof ArrayBuffer || ArrayBuffer.isView(payload)) {
      const blob = new Blob([payload as any], { type: mimeHint });
      const url = URL.createObjectURL(blob);
      audio.src = url;
      await audio.play();
      console.log('🎵 오디오 재생 성공 (ArrayBuffer→blob)');
      audio.onended = () => URL.revokeObjectURL(url);
      console.groupEnd();
      return;
    }

    // 6) { audioUrl } 객체
    if (payload?.audioUrl) {
      audio.src = payload.audioUrl;
      await audio.play();
      console.log('🎵 오디오 재생 성공 (audioUrl 객체)');
      console.groupEnd();
      return;
    }

    console.error('❌ 알 수 없는 페이로드 형식');
    throw new Error('알 수 없는 오디오 페이로드 형식');

  } catch (error) {
    console.error('❌ 오디오 재생 실패:', error);
    throw error;
  }
}
