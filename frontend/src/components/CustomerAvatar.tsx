import { usePersonaStore } from '../store/usePersonaStore'
import { getPersonaAvatarUrl } from '../lib/rpm/rpmHelper'
// import Avatar3D from './Avatar3D' // 임시로 비활성화 (패키지 충돌)

interface CustomerAvatarProps {
  className?: string
}

/**
 * 고객 아바타 표시 컴포넌트
 * 페르소나에 맞는 RPM 아바타를 로드하고 표시
 */
export default function CustomerAvatar({ className = '' }: CustomerAvatarProps) {
  // ✅ 훅들을 항상 최상단에서 동일한 순서로 호출
  const { persona, currentAudio } = usePersonaStore()

  // ✅ 오디오 자동 재생 제거 - VoiceSimulation에서 재생하므로 중복 방지

  // ✅ 페르소나가 없으면 표시하지 않음 - 훅 호출 이후에 조건부 렌더링
  if (!persona) {
    return (
      <div className={`flex items-center justify-center bg-gray-100 rounded-lg ${className}`}>
        <p className="text-gray-500">고객 아바타가 준비되지 않았습니다.</p>
      </div>
    )
  }

  const avatarUrl = getPersonaAvatarUrl(persona.persona_id)

  // 수동 재생 함수 제거 - 대화 히스토리에서만 재생

  return (
    <div className={`relative bg-white rounded-lg shadow-lg overflow-hidden ${className}`}>
      {/* 아바타 3D 렌더링 영역 */}
      <div className="aspect-square bg-gradient-to-br from-blue-50 to-purple-50 flex items-center justify-center relative rounded-lg overflow-hidden">
        {avatarUrl ? (
          // 3D 아바타 렌더링 (임시로 비활성화)
          // <Avatar3D 
          //   avatarUrl={avatarUrl} 
          //   className="w-full h-full"
          // />
          <div className="text-center p-8 w-full h-full flex flex-col items-center justify-center">
            <div className="text-9xl mb-8 animate-pulse">
              {(persona.gender === '여성' || persona.gender === 'female') ? '👩' : '👨'}
            </div>
            <div className="bg-white/90 backdrop-blur-sm rounded-xl p-6 shadow-lg">
              <p className="text-2xl font-bold text-gray-800 mb-2">{persona.type}</p>
              <p className="text-sm text-gray-600">{persona.age_group} • {persona.gender}</p>
              <p className="text-xs text-gray-500 mt-2">3D 아바타 준비 중...</p>
            </div>
          </div>
        ) : (
          // 폴백: 이모지 아바타
          <div className="text-center p-8 w-full h-full flex flex-col items-center justify-center">
            <div className="text-9xl mb-8 animate-pulse">
              {(persona.gender === '여성' || persona.gender === 'female') ? '👩' : '👨'}
            </div>
            <div className="bg-white/90 backdrop-blur-sm rounded-xl p-6 shadow-lg">
              <p className="text-2xl font-bold text-gray-800 mb-2">{persona.type}</p>
              <p className="text-sm text-gray-600">{persona.age_group} • {persona.gender}</p>
              <p className="text-xs text-gray-500 mt-2">3D 모델 준비 중...</p>
            </div>
          </div>
        )}
        
        {/* 페르소나 정보 오버레이 */}
        <div className="absolute top-4 left-4 bg-black/70 text-white px-3 py-2 rounded-lg text-sm">
          <p className="font-semibold">{persona.type}</p>
          <p className="text-xs opacity-80">{persona.age_group} • {persona.gender}</p>
        </div>
      </div>

      {/* 고객 메시지 하단 오버레이 제거 (대화 영역에서만 다시 듣기 제공) */}
    </div>
  )
}
