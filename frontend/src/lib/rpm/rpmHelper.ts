/**
 * Ready Player Me 아바타 URL 생성 및 매핑 헬퍼 함수들
 */

// 성별과 나이대별 기본 RPM 아바타 URL 매핑
const AVATAR_URLS = {
  // 여성 아바타들 (실제 RPM GLB URL로 교체 필요)
  female: {
    '20대': 'https://models.readyplayer.me/65e7a1234567890abcdef001.glb', // 20대 여성
    '30대': 'https://models.readyplayer.me/65e7a1234567890abcdef002.glb', // 30대 여성  
    '40대': 'https://models.readyplayer.me/65e7a1234567890abcdef003.glb', // 40대 여성
    '50대': 'https://models.readyplayer.me/65e7a1234567890abcdef004.glb', // 50대 여성
    '60대 이상': 'https://models.readyplayer.me/65e7a1234567890abcdef005.glb', // 60대+ 여성
  },
  // 남성 아바타들  
  male: {
    '20대': 'https://models.readyplayer.me/65e7a1234567890abcdef101.glb', // 20대 남성
    '30대': 'https://models.readyplayer.me/65e7a1234567890abcdef102.glb', // 30대 남성
    '40대': 'https://models.readyplayer.me/65e7a1234567890abcdef103.glb', // 40대 남성
    '50대': 'https://models.readyplayer.me/65e7a1234567890abcdef104.glb', // 50대 남성
    '60대 이상': 'https://models.readyplayer.me/65e7a1234567890abcdef105.glb', // 60대+ 남성
  }
}

/**
 * 페르소나 정보에 기반하여 Ready Player Me 아바타 URL을 생성합니다.
 */
export function getRpmAvatarUrl(gender: string, ageGroup: string): string {
  const genderKey = gender === '여성' ? 'female' : 'male'
  const genderUrls = AVATAR_URLS[genderKey]
  const avatarUrl = genderUrls[ageGroup as keyof typeof genderUrls]
  
  if (avatarUrl) {
    return avatarUrl
  }
  
  // 폴백: 기본 아바타
  return gender === '여성' 
    ? AVATAR_URLS.female['30대'] 
    : AVATAR_URLS.male['30대']
}

/**
 * 페르소나 ID에 기반하여 아바타 URL을 반환합니다.
 */
export function getPersonaAvatarUrl(personaId: string): string | null {
  // 페르소나 ID에서 성별과 나이대 추출
  // 예: "p_20s_student_lowlit_practical_f" -> 20대, 여성
  
  const parts = personaId.split('_')
  if (parts.length < 2) return null
  
  const ageGroup = parts[1] // "20s", "30s", etc.
  const gender = parts[parts.length - 1] // "f" or "m"
  
  // 나이대 매핑
  const ageMapping: { [key: string]: string } = {
    '20s': '20대',
    '30s': '30대', 
    '40s': '40대',
    '50s': '50대',
    '60s': '60대 이상'
  }
  
  // 성별 매핑
  const genderMapping: { [key: string]: string } = {
    'f': '여성',
    'm': '남성'
  }
  
  const mappedAge = ageMapping[ageGroup]
  const mappedGender = genderMapping[gender]
  
  if (mappedAge && mappedGender) {
    return getRpmAvatarUrl(mappedGender, mappedAge)
  }
  
  return null
}

/**
 * 페르소나별 TTS 음성 프리셋 매핑
 */
export function getPersonaVoicePreset(gender: string, ageGroup: string, customerType: string): string {
  const baseVoice = gender === '여성' ? 'ko_female' : 'ko_male'
  
  // 나이대별 음성 톤 조정
  const ageTone = ageGroup.includes('20') ? 'young' : 
                  ageGroup.includes('60') ? 'senior' : 'adult'
  
  // 고객 타입별 음성 스타일 조정
  const styleMap: { [key: string]: string } = {
    '실용형': 'direct',
    '보수형': 'calm', 
    '불만형': 'tense',
    '긍정형': 'cheerful',
    '급함형': 'urgent'
  }
  
  const style = styleMap[customerType] || 'neutral'
  
  return `${baseVoice}_${ageTone}_${style}`
}

