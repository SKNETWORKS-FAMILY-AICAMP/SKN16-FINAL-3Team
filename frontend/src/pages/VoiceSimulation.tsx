import React, { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'
import { usePersonaStore } from '../store/usePersonaStore'
import api from '../utils/api'
import { ragSimulationAPI } from '../utils/api'
import { playFromAnyAudioPayload } from '../utils/audio'
import { AudioVisualizer } from '../components/AudioVisualizer'
import CustomerAvatar from '../components/CustomerAvatar'
import { isOnTopic } from '../utils/offtopicDetector'
import {
  MicrophoneIcon,
  StopIcon,
  PlayIcon,
  SpeakerWaveIcon,
  ArrowPathIcon,
  ArrowLeftIcon,
  VideoCameraIcon,
  ChevronUpIcon,
  ChevronDownIcon,
  CheckIcon,
  ArrowsPointingOutIcon,
  ArrowsPointingInIcon
} from '@heroicons/react/24/outline'

interface VoiceSimulationProps {
  simulationData: any
  onBack: () => void
}

// 대화 메시지 타입
interface ChatMessage {
  id: string
  role: 'user' | 'customer'
  text: string
  audio?: string
  timestamp: Date
}

const VoiceSimulation: React.FC<VoiceSimulationProps> = ({ simulationData, onBack }) => {
  const { user } = useAuthStore()
  const { setPersona, setAudio } = usePersonaStore()
  const navigate = useNavigate()
  const [isRecording, setIsRecording] = useState(false)
  const [isPlaying, setIsPlaying] = useState(false)
  const [userMessage, setUserMessage] = useState('')
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]) // 대화 히스토리
  const [subtitle, setSubtitle] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [stream, setStream] = useState<MediaStream | null>(null) // 오디오 스트림
  const [videoStream, setVideoStream] = useState<MediaStream | null>(null) // 비디오 스트림
  const [isInitializing, setIsInitializing] = useState(true) // 초기화 상태
  const [isStarted, setIsStarted] = useState(false) // 시뮬레이션 시작 여부
  const [initialInstructionMessage, setInitialInstructionMessage] = useState<string>('') // 초기 안내 메시지
  const [isCustomerInfoOpen, setIsCustomerInfoOpen] = useState(false) // 고객 정보 접기/펼치기 (기본값: 접힘)
  const [isSituationInfoOpen, setIsSituationInfoOpen] = useState(false) // 상황 정보 접기/펼치기 (기본값: 접힘)
  const [checkedGoals, setCheckedGoals] = useState<Set<number>>(new Set()) // 달성된 목표 인덱스
  const [isSimulationCompleted, setIsSimulationCompleted] = useState(false) // 시뮬레이션 완료 상태
  const [isGeneratingFeedback, setIsGeneratingFeedback] = useState(false) // 평가서 생성 중 상태
  const [isPersonaMainView, setIsPersonaMainView] = useState(true) // 페르소나가 큰 화면인지 (기본값: true)
  const [offtopicCount, setOfftopicCount] = useState(0) // 이탈 카운터
  const [isEnding, setIsEnding] = useState(false) // 종료 중 상태 (끝맺음 용어 감지 시)
  const [isFullscreen, setIsFullscreen] = useState(false) // 전체 화면 상태

  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const videoContainerRef = useRef<HTMLDivElement | null>(null) // 전체 화면용 컨테이너
  const audioChunksRef = useRef<Blob[]>([])
  const videoRecorderRef = useRef<MediaRecorder | null>(null) // 화면 녹화용
  const videoChunksRef = useRef<Blob[]>([]) // 화면 녹화 데이터
  const audioRef = useRef<HTMLAudioElement>(null)
  const chatEndRef = useRef<HTMLDivElement>(null) // 스크롤 자동 이동용
  const videoRef = useRef<HTMLVideoElement>(null) // 비디오 엘리먼트 참조 (큰 화면)
  const smallVideoRef = useRef<HTMLVideoElement>(null) // 비디오 엘리먼트 참조 (작은 화면)

  // 페르소나 이미지 URL 가져오기 함수
  const getPersonaImageUrl = (gender: string, ageGroup: string): string => {
    // 성별 한글 변환
    const genderKor = (gender === '여성' || gender === 'female' || gender === 'Female') ? '여자' : '남자'
    
    // 연령대 한글 변환 (60대 이상을 먼저 체크해야 함)
    let ageKey = '30대' // 기본값
    if (ageGroup.includes('60대 이상') || ageGroup.includes('60대이상') || ageGroup === '60대 이상') {
      ageKey = '60대이상'
    } else if (ageGroup.includes('50') || ageGroup.includes('50대')) {
      ageKey = '50대'
    } else if (ageGroup.includes('40') || ageGroup.includes('40대')) {
      ageKey = '40대'
    } else if (ageGroup.includes('30') || ageGroup.includes('30대')) {
      ageKey = '30대'
    } else if (ageGroup.includes('20') || ageGroup.includes('20대')) {
      ageKey = '20대'
    } else if (ageGroup.includes('10') || ageGroup.includes('10대')) {
      ageKey = '10대'
    }
    
    // 파일명: "10대여자.png", "20대남자.png", "60대이상여자.png" 형식 (PNG 지원)
    // 캐시 무효화를 위해 timestamp 추가
    const timestamp = Date.now()
    const imageUrl = `/assets/personas/${ageKey}${genderKor}.png?v=${timestamp}`
    console.log('🖼️ 페르소나 이미지 URL 생성:', { gender, ageGroup, genderKor, ageKey, imageUrl })
    return imageUrl
  }

  // 이미지 로드 실패 시 여러 확장자 시도하는 함수
  const handleImageError = (e: React.SyntheticEvent<HTMLImageElement, Event>, attempts: number = 0, originalUrl?: string) => {
    const target = e.target as HTMLImageElement
    const currentSrc = target.src
    const baseUrl = originalUrl || currentSrc.replace(/\.(png|jpg|jpeg)$/i, '')
    
    console.error(`❌ 이미지 로드 실패 (시도 ${attempts + 1}):`, currentSrc)
    console.error(`📍 기본 URL: ${baseUrl}`)
    
    // 여러 확장자 시도
    const extensions = ['.png', '.jpg', '.jpeg', '.PNG', '.JPG', '.JPEG']
    if (attempts < extensions.length) {
      const nextUrl = baseUrl.replace(/\.(png|jpg|jpeg|PNG|JPG|JPEG)$/i, '') + extensions[attempts]
      console.log(`🔄 확장자 변경 시도 (${attempts + 1}/${extensions.length}): ${nextUrl}`)
      target.src = nextUrl
      // 다음 시도를 위해 이벤트 핸들러 재등록
      const nextAttempts = attempts + 1
      target.onerror = (event) => handleImageError(event as any, nextAttempts, originalUrl || baseUrl)
      return
    }
    
    // 모든 확장자 실패 시 기본 아바타 사용
    console.warn('⚠️ 모든 확장자 실패, 기본 아바타 사용')
    console.warn(`📁 예상 파일 위치: frontend/public/assets/personas/`)
    console.warn(`📝 예상 파일명: ${baseUrl.replace(/^.*\//, '')}.png 또는 .jpg`)
    target.src = '/assets/default-avatar.svg'
    target.onerror = null // 무한 루프 방지
  }

  // 카메라 스트림 초기화
  useEffect(() => {
    if (isStarted) {
      const initCamera = async () => {
        try {
          console.log('🎥 카메라 초기화 시작...')
          const stream = await navigator.mediaDevices.getUserMedia({ 
            video: {
              width: { ideal: 1280 },
              height: { ideal: 720 },
              facingMode: 'user'
            },
            audio: false // 비디오만 가져오기 (오디오는 별도로)
          })
          console.log('✅ 카메라 스트림 획득 성공:', stream)
          setVideoStream(stream)
          
          // 초기 상태에서는 페르소나가 큰 화면이므로 작은 화면에만 스트림 할당
          // 큰 화면 비디오는 나중에 화면 전환 시 할당됨
          if (smallVideoRef.current) {
            smallVideoRef.current.srcObject = stream
            smallVideoRef.current.play().catch(err => {
              console.error('작은 화면 비디오 초기 재생 실패:', err)
            })
            console.log('✅ 작은 화면 비디오 엘리먼트에 스트림 할당 완료')
          } else {
            console.warn('⚠️ smallVideoRef.current가 null입니다')
          }
          
          // 큰 화면 비디오도 초기화 (나중에 필요할 때 사용)
          if (videoRef.current) {
            videoRef.current.srcObject = stream
            videoRef.current.pause() // 초기에는 재생하지 않음 (페르소나가 큰 화면이므로)
            console.log('✅ 큰 화면 비디오 엘리먼트 초기화 완료')
          }
        } catch (error: any) {
          console.error('❌ 카메라 접근 실패:', error)
          setError(`카메라 접근 권한이 필요합니다: ${error.message}`)
        }
      }
      initCamera()
    }

    // 컴포넌트 언마운트 시 정리
    return () => {
      if (videoStream) {
        console.log('🧹 카메라 스트림 정리 중...')
        videoStream.getTracks().forEach(track => {
          track.stop()
          console.log('✅ 트랙 정리 완료:', track.kind)
        })
        setVideoStream(null)
      }
    }
  }, [isStarted])

  // videoStream이 변경될 때 비디오 엘리먼트 업데이트
  useEffect(() => {
    if (videoStream) {
      console.log('🔄 비디오 스트림 업데이트 중...', { isPersonaMainView })
      
      // 화면 상태에 따라 적절한 비디오 엘리먼트에만 재생
      if (isPersonaMainView) {
        // 페르소나가 큰 화면: 작은 화면에 카메라 표시
        if (smallVideoRef.current) {
          smallVideoRef.current.srcObject = videoStream
          smallVideoRef.current.play().catch(err => {
            console.error('작은 화면 비디오 재생 실패:', err)
          })
          console.log('✅ 작은 화면 비디오 업데이트 완료')
        }
        // 큰 화면 비디오는 스트림만 할당하고 재생하지 않음
        if (videoRef.current) {
          videoRef.current.srcObject = videoStream
          videoRef.current.pause()
        }
      } else {
        // 카메라가 큰 화면: 큰 화면에 카메라 표시
        if (videoRef.current) {
          videoRef.current.srcObject = videoStream
          videoRef.current.play().catch(err => {
            console.error('큰 화면 비디오 재생 실패:', err)
          })
          console.log('✅ 큰 화면 비디오 업데이트 완료')
        }
        // 작은 화면 비디오는 스트림만 할당하고 재생하지 않음
        if (smallVideoRef.current) {
          smallVideoRef.current.srcObject = videoStream
          smallVideoRef.current.pause()
        }
      }
    } else {
      // 스트림이 없으면 비디오 엘리먼트 정리
      if (videoRef.current) {
        videoRef.current.srcObject = null
      }
      if (smallVideoRef.current) {
        smallVideoRef.current.srcObject = null
      }
    }
  }, [videoStream, isPersonaMainView])

  // 화면 전환 시 비디오 재생 강제 확인 (추가 보안)
  useEffect(() => {
    if (videoStream) {
      console.log('🔄 화면 전환 감지:', { isPersonaMainView, videoStream: !!videoStream })
      
      // 화면 전환 후 잠시 기다린 후 재생 상태 확인
      const timer = setTimeout(() => {
        if (!isPersonaMainView && videoRef.current) {
          // 카메라가 큰 화면일 때
          console.log('📹 큰 화면에 카메라 표시 확인')
          if (videoRef.current.paused || !videoRef.current.srcObject) {
            console.log('⚠️ 큰 화면 비디오 재생되지 않음 - 강제 재할당')
            videoRef.current.srcObject = videoStream
            videoRef.current.play().catch(err => {
              console.error('큰 화면 비디오 재생 실패:', err)
            })
          }
        } else if (isPersonaMainView && smallVideoRef.current) {
          // 카메라가 작은 화면일 때
          console.log('📹 작은 화면에 카메라 표시 확인')
          if (smallVideoRef.current.paused || !smallVideoRef.current.srcObject) {
            console.log('⚠️ 작은 화면 비디오 재생되지 않음 - 강제 재할당')
            smallVideoRef.current.srcObject = videoStream
            smallVideoRef.current.play().catch(err => {
              console.error('작은 화면 비디오 재생 실패:', err)
            })
          }
        }
      }, 100)
      
      return () => clearTimeout(timer)
    }
  }, [isPersonaMainView, videoStream])

  // 페르소나 설정 및 (시작 버튼 이후) 초기 멘트 처리
  useEffect(() => {
    if (!isStarted) return
    if (simulationData?.persona) {
      console.log('👤 페르소나 데이터:', simulationData.persona)
      console.log('👤 페르소나 성별:', simulationData.persona.gender)
      console.log('👤 페르소나 연령대:', simulationData.persona.age_group)
      
      setPersona({
        persona_id: simulationData.persona.id || '',
        avatarUrl: '', // TODO: RPM URL
        voicePreset: simulationData.persona.type || '',
        gender: simulationData.persona.gender || 'male',
        age_group: simulationData.persona.age_group || '',
        type: simulationData.persona.type || ''
      })

      // 🔥 변경: 초기 안내 메시지만 저장, 대화창은 표시하지 않음
      const initialMessage = simulationData?.initial_message
      
      // 안내 메시지 저장 (대화창에는 추가하지 않음)
      if (initialMessage?.type === 'instruction' && initialMessage?.content) {
        setInitialInstructionMessage(initialMessage.content)
        // chatHistory는 비워둠 (대화창이 보이지 않음)
        setChatHistory([])
        setIsInitializing(true) // 사용자가 말을 시작할 때까지 초기화 상태 유지
      } else {
        setChatHistory([])
        setIsInitializing(false) // 초기 메시지가 없으면 바로 시작 가능
      }
    }
  }, [simulationData, isStarted])

  // 🔥 새 메시지(사용자 또는 고객)가 추가될 때 대화창 스크롤 (전체 화면은 무조건 고정)
  useEffect(() => {
    // 새 메시지가 추가되면 대화창 내부만 스크롤
    if (chatHistory.length > 0) {
      // 약간의 지연을 두어 DOM 업데이트 후 대화창 내부만 스크롤
      setTimeout(() => {
        if (chatEndRef.current) {
          // 대화창 내부 스크롤 컨테이너 찾기
          const chatContainer = chatEndRef.current.closest('.overflow-y-auto') as HTMLElement
          if (chatContainer) {
            // 대화창 내부 컨테이너만 스크롤 (전체 화면은 영향 없음)
            // scrollIntoView 대신 직접 스크롤 위치 조정
            chatContainer.scrollTo({
              top: chatContainer.scrollHeight,
              behavior: 'smooth'
            })
          } else {
            // 대화창 컨테이너를 찾지 못한 경우에도 안전하게 스크롤
            chatEndRef.current.scrollIntoView({ 
              behavior: 'smooth',
              block: 'nearest', // 최소한의 스크롤만 수행
              inline: 'nearest'
            })
          }
        }
      }, 150)
    }
  }, [chatHistory])

  // 전체 화면 상태 감지
  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(!!document.fullscreenElement)
    }

    document.addEventListener('fullscreenchange', handleFullscreenChange)
    document.addEventListener('webkitfullscreenchange', handleFullscreenChange)
    document.addEventListener('mozfullscreenchange', handleFullscreenChange)
    document.addEventListener('MSFullscreenChange', handleFullscreenChange)

    return () => {
      document.removeEventListener('fullscreenchange', handleFullscreenChange)
      document.removeEventListener('webkitfullscreenchange', handleFullscreenChange)
      document.removeEventListener('mozfullscreenchange', handleFullscreenChange)
      document.removeEventListener('MSFullscreenChange', handleFullscreenChange)
    }
  }, [])

  // 전체 화면 진입/해제 함수
  const toggleFullscreen = async () => {
    if (!videoContainerRef.current) return

    try {
      if (!isFullscreen) {
        // 전체 화면 진입
        if (videoContainerRef.current.requestFullscreen) {
          await videoContainerRef.current.requestFullscreen()
        } else if ((videoContainerRef.current as any).webkitRequestFullscreen) {
          await (videoContainerRef.current as any).webkitRequestFullscreen()
        } else if ((videoContainerRef.current as any).mozRequestFullScreen) {
          await (videoContainerRef.current as any).mozRequestFullScreen()
        } else if ((videoContainerRef.current as any).msRequestFullscreen) {
          await (videoContainerRef.current as any).msRequestFullscreen()
        }
      } else {
        // 전체 화면 해제
        if (document.exitFullscreen) {
          await document.exitFullscreen()
        } else if ((document as any).webkitExitFullscreen) {
          await (document as any).webkitExitFullscreen()
        } else if ((document as any).mozCancelFullScreen) {
          await (document as any).mozCancelFullScreen()
        } else if ((document as any).msExitFullscreen) {
          await (document as any).msExitFullscreen()
        }
      }
    } catch (error) {
      console.error('전체 화면 전환 실패:', error)
    }
  }

  // 대화 종료 표현 감지 (문장 끝부분에 종료 표현이 있는지 확인)
  const checkConversationEnd = (message: string): boolean => {
    // 백엔드의 end_signal을 우선 사용하므로, 이 함수는 보조 역할만 수행
    // 문장 끝부분에 종료 표현이 있는 경우만 감지
    const endKeywords = [
      '감사합니다',
      '수고하셨습니다',
      '감사해요',
      '고마워요',
      '고맙습니다',
      '끝',
      '종료',
      '마무리',
      '그럼 이만',
      '안녕히가세요',
      '수고하세요',
      '그럼 이만',
      '안녕히 계세요'
    ]
    
    const trimmedMessage = message.trim()
    if (!trimmedMessage) return false
    
    // 문장 끝부분(마지막 10글자)에 종료 키워드가 있는지 확인
    const lastChars = trimmedMessage.slice(-10).toLowerCase()
    const hasEndKeyword = endKeywords.some(keyword => lastChars.includes(keyword.toLowerCase()))
    
    // 문장이 매우 짧고(10글자 이하) 종료 키워드로 시작하거나 끝나는 경우만 종료로 판단
    if (trimmedMessage.length <= 10) {
      const lowerMessage = trimmedMessage.toLowerCase()
      return endKeywords.some(keyword => {
        const lowerKeyword = keyword.toLowerCase()
        return lowerMessage === lowerKeyword || 
               lowerMessage.startsWith(lowerKeyword) || 
               lowerMessage.endsWith(lowerKeyword)
      })
    }
    
    // 긴 문장의 경우 끝부분에만 종료 표현이 있어야 종료로 판단
    return hasEndKeyword
  }

  // 시뮬레이션 종료 처리
  const handleEndSimulation = async () => {
    console.log('🔚 시뮬레이션 종료 처리 시작...')
    
    try {
      // 화면 녹화 중지 및 업로드
      if (videoRecorderRef.current && videoRecorderRef.current.state !== 'inactive') {
        console.log('📹 화면 녹화 중지 및 업로드 중...')
        videoRecorderRef.current.stop()
        
        videoRecorderRef.current.onstop = async () => {
          // 녹화 데이터를 Blob으로 변환
          const videoBlob = new Blob(videoChunksRef.current, { type: 'video/webm' })
          console.log('✅ 녹화 완료, 파일 크기:', videoBlob.size, 'bytes')
          
          // 녹화 파일 업로드
          if (videoBlob.size > 0) {
            await uploadRecording(videoBlob)
          }
          
          // 녹화 데이터 초기화
          videoChunksRef.current = []
        }
      }

      // 오디오 녹화 중지
      if (isRecording && mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
        console.log('🎤 오디오 녹화 중지 중...')
        mediaRecorderRef.current.stop()
        setIsRecording(false)
      }

      // 카메라 스트림 정리
      if (videoStream) {
        videoStream.getTracks().forEach(track => track.stop())
        setVideoStream(null)
      }

      // 오디오 스트림 정리
      if (stream) {
        stream.getTracks().forEach(track => track.stop())
        setStream(null)
      }

      // 🔥 변경: 바로 평가서 생성 시작 (완료 페이지를 거치지 않음)
      await handleGoToEvaluation()

      console.log('✅ 시뮬레이션 종료 처리 완료')
    } catch (error) {
      console.error('❌ 시뮬레이션 종료 처리 실패:', error)
      // 오류가 발생하면 로딩 상태 해제
      setIsGeneratingFeedback(false)
      setError('평가서 생성에 실패했습니다. 다시 시도해주세요.')
    }
  }
  
  // 다시 시뮬레이션 시작
  const handleRestartSimulation = () => {
    // 모든 상태 초기화
    setOfftopicCount(0)
    setIsEnding(false)
    setIsSimulationCompleted(false)
    setChatHistory([])
    setCheckedGoals(new Set())
    setIsStarted(false)
    setIsInitializing(true)
    setUserMessage('')
    setError('')
    setIsPlaying(false)
    setIsRecording(false)
    
    // 녹화 관련 초기화
    videoChunksRef.current = []
    audioChunksRef.current = []
    mediaRecorderRef.current = null
    videoRecorderRef.current = null
    
    // 스트림 정리
    if (videoStream) {
      videoStream.getTracks().forEach(track => track.stop())
      setVideoStream(null)
    }
    if (stream) {
      stream.getTracks().forEach(track => track.stop())
      setStream(null)
    }
    
    console.log('🔄 시뮬레이션 재시작 준비 완료')
  }
  
  // 평가 페이지로 이동
  const handleGoToEvaluation = async () => {
    try {
      const startTime = Date.now()
      
      // 대화 기록이 충분한지 확인
      if (chatHistory.length < 2) {
        alert('시뮬레이션을 더 진행해주세요. (최소 2턴 이상 대화 필요)')
        setIsGeneratingFeedback(false)
        return
      }

      // 대화 히스토리를 API 형식으로 변환
      const conversationHistory = chatHistory.map((msg) => ({
        role: msg.role === 'user' ? 'employee' : 'customer',
        text: msg.text,
        timestamp: msg.timestamp.toISOString()
      }))

      // 피드백 생성 API 호출
      const response = await api.post('/rag-simulation/generate-feedback', {
        conversation_history: conversationHistory,
        persona: simulationData?.persona || {},
        situation: simulationData?.situation || {}
      })

      const feedbackData = response.data.feedback
      const elapsedTime = Date.now() - startTime

      // 🔥 평가서 생성이 빠르면(1초 이내) 로딩 화면 건너뛰기
      if (elapsedTime < 1000) {
        // 바로 피드백 페이지로 이동
        navigate('/simulation-feedback', {
          state: { feedbackData }
        })
      } else {
        // 로딩 화면을 잠시 보여준 후 이동
        navigate('/simulation-feedback', {
          state: { feedbackData }
        })
      }

    } catch (error) {
      console.error('피드백 생성 실패:', error)
      setIsGeneratingFeedback(false)
      setError('피드백 생성에 실패했습니다. 다시 시도해주세요.')
    }
  }

  // 목표 달성 분석 함수
  const analyzeGoalAchievement = async (history: ChatMessage[]) => {
    const goals = simulationData?.situation?.goals
    if (!goals || goals.length === 0) {
      return
    }

    // 사용자 메시지가 있는지 확인
    const hasUserMessages = history.some(msg => msg.role === 'user')
    if (!hasUserMessages) {
      return
    }

    try {
      console.log('🎯 목표 달성 분석 시작...')
      
      // 대화 히스토리를 API 형식으로 변환
      const conversationHistory = history.map(msg => ({
        role: msg.role === 'user' ? 'user' : 'customer',
        text: msg.text
      }))

      const result = await ragSimulationAPI.analyzeGoalAchievement(conversationHistory, goals)
      
      console.log('✅ 목표 달성 분석 결과:', result)
      
      // 달성된 목표 인덱스를 Set으로 변환
      const achievedIndicesArray = (result.achieved_goal_indices || []) as number[]
      const achievedIndices = new Set<number>(achievedIndicesArray)
      setCheckedGoals(achievedIndices)
      
    } catch (error) {
      console.error('❌ 목표 달성 분석 실패:', error)
    }
  }

  // 대화 히스토리가 변경될 때마다 목표 달성 분석 (고객 응답 후 분석)
  useEffect(() => {
    if (!isStarted || isInitializing) {
      return
    }

    const userMessages = chatHistory.filter(msg => msg.role === 'user')
    if (userMessages.length === 0) {
      return
    }

    // 마지막 메시지 확인
    const lastMessage = chatHistory[chatHistory.length - 1]
    if (lastMessage) {
      // 고객 응답이 온 후 약간의 지연을 두고 분석
      const delay = lastMessage.role === 'customer' ? 1000 : 3000
      const timer = setTimeout(() => {
        analyzeGoalAchievement(chatHistory)
      }, delay)

      return () => clearTimeout(timer)
    }
  }, [chatHistory, isStarted, isInitializing, simulationData])

  // 녹화 파일 업로드
  const uploadRecording = async (videoBlob: Blob) => {
    try {
      console.log('📤 녹화 파일 업로드 시작...')
      
      const formData = new FormData()
      formData.append('video', videoBlob, `simulation_${Date.now()}.webm`)
      formData.append('session_data', JSON.stringify({
        simulation_id: simulationData?.session_id || Date.now(),
        persona_id: simulationData?.persona?.id,
        situation_id: simulationData?.situation?.id,
        user_id: user?.id,
        timestamp: new Date().toISOString()
      }))

      // FormData는 브라우저가 자동으로 Content-Type을 설정하므로 헤더 제거
      const response = await api.post('/rag-simulation/upload-recording', formData, {
        onUploadProgress: (progressEvent) => {
          if (progressEvent.total) {
            const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total)
            console.log(`업로드 진행률: ${percentCompleted}%`)
          }
        }
      })

      console.log('✅ 녹화 파일 업로드 완료:', response.data)
      
      // 사용자에게 알림 (선택사항)
      if (response.data?.video_url) {
        console.log('📹 녹화 파일 URL:', response.data.video_url)
        // 필요시 상태 업데이트 또는 토스트 메시지 표시
      }
    } catch (error) {
      console.error('❌ 녹화 파일 업로드 실패:', error)
      // 업로드 실패해도 시뮬레이션은 계속 진행
    }
  }

  // 음성 녹음 시작 (화면 녹화 포함)
  const startRecording = async () => {
    try {
      // 오디오 스트림 가져오기
      const audioStream = await navigator.mediaDevices.getUserMedia({ 
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          sampleRate: 44100
        }
      })
      
      // 스트림을 state에 저장 (시각화용)
      setStream(audioStream)
      
      // 오디오 녹음용 MediaRecorder (STT용)
      mediaRecorderRef.current = new MediaRecorder(audioStream, {
        mimeType: 'audio/webm;codecs=opus'
      })
      audioChunksRef.current = []

      mediaRecorderRef.current.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data)
        }
      }

      mediaRecorderRef.current.onstop = () => {
        const audioBlob = new Blob(audioChunksRef.current, { 
          type: mediaRecorderRef.current?.mimeType || 'audio/webm'
        })
        console.log('녹음된 오디오 Blob:', audioBlob)
        console.log('Blob 크기:', audioBlob.size)
        
        // 오디오 스트림 정리
        audioStream.getTracks().forEach(track => track.stop())
        setStream(null)
        
        processAudio(audioBlob)
      }

      mediaRecorderRef.current.start()
      
      // 화면 녹화 시작 (비디오 + 오디오 함께)
      if (videoStream && audioStream) {
        console.log('🎬 화면 녹화 시작...')
        
        // 비디오 트랙과 오디오 트랙 합치기
        const combinedStream = new MediaStream()
        videoStream.getVideoTracks().forEach(track => {
          combinedStream.addTrack(track)
          console.log('✅ 비디오 트랙 추가:', track.label)
        })
        audioStream.getAudioTracks().forEach(track => {
          combinedStream.addTrack(track)
          console.log('✅ 오디오 트랙 추가:', track.label)
        })

        // 화면 녹화용 MediaRecorder
        const videoMimeType = MediaRecorder.isTypeSupported('video/webm;codecs=vp9,opus') 
          ? 'video/webm;codecs=vp9,opus'
          : MediaRecorder.isTypeSupported('video/webm;codecs=vp8,opus')
          ? 'video/webm;codecs=vp8,opus'
          : 'video/webm'
        
        videoRecorderRef.current = new MediaRecorder(combinedStream, {
          mimeType: videoMimeType,
          videoBitsPerSecond: 2500000 // 2.5 Mbps
        })
        videoChunksRef.current = []

        videoRecorderRef.current.ondataavailable = (event) => {
          if (event.data.size > 0) {
            videoChunksRef.current.push(event.data)
            console.log('📹 화면 녹화 데이터 수신:', event.data.size, 'bytes')
          }
        }

        videoRecorderRef.current.onstop = async () => {
          const videoBlob = new Blob(videoChunksRef.current, { 
            type: videoRecorderRef.current?.mimeType || 'video/webm'
          })
          console.log('✅ 화면 녹화 완료:', videoBlob.size, 'bytes')
          
          // 백엔드로 업로드
          await uploadRecording(videoBlob)
        }

        videoRecorderRef.current.start(1000) // 1초마다 데이터 수집
        console.log('✅ 화면 녹화 시작됨')
      }

      setIsRecording(true)
      setSubtitle('말씀해주세요...')
    } catch (error) {
      console.error('녹음 시작 실패:', error)
      setError('마이크 접근 권한이 필요합니다.')
    }
  }

  // 음성 녹음 중지 (화면 녹화도 함께 중지)
  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop()
      setIsRecording(false)
      setSubtitle('음성을 처리 중입니다...')
    }
    
    // 화면 녹화도 중지
    if (videoRecorderRef.current && videoRecorderRef.current.state !== 'inactive') {
      console.log('🛑 화면 녹화 중지 중...')
      videoRecorderRef.current.stop()
    }
  }

  // 음성 처리 및 STT - 상세 로그 + 방탄 분기
  const processAudio = async (audioBlob: Blob) => {
    console.groupCollapsed('🚀 음성 인터랙션 요청');
    console.log('보내는 파일:', audioBlob?.type, audioBlob?.size, 'bytes');
    
    try {
      setLoading(true)
      setError('')

      // 🔥 프론트엔드에서 이탈 감지 (백엔드 전송 전)
      // STT 결과를 기다려야 하므로, 여기서는 일단 전송하고 백엔드 응답에서 처리
      
      // 세션 데이터에 대화 히스토리 포함
      const sessionDataWithHistory = {
        ...simulationData,
        conversation_history: chatHistory.map(msg => ({
          role: msg.role === 'user' ? 'employee' : 'customer',
          text: msg.text,
          timestamp: msg.timestamp.toISOString()
        })),
        achieved_goals: Array.from(checkedGoals), // 달성된 목표 포함
        offtopic_count: offtopicCount // 프론트엔드 이탈 카운터 사용
      }

      const formData = new FormData()
      formData.append('audio_file', audioBlob, 'recording.webm')  // 서버가 audio_file을 기대
      formData.append('session_data', JSON.stringify(sessionDataWithHistory))

      console.log('FormData 준비 완료, 전송 시작...');

      const response = await api.post('/rag-simulation/process-voice-interaction', formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      })

      console.log('✅ 응답 원본:', response.data);
      const { transcribed_text, customer_response, customer_audio, end_signal, error } = response.data
      
      // 🔥 프론트엔드에서도 이탈 감지 (백엔드와 이중 체크)
      if (transcribed_text && !isEnding) {
        const isOfftopic = !isOnTopic(transcribed_text)
        if (isOfftopic) {
          console.log('⚠️ 프론트엔드 이탈 감지:', transcribed_text)
          const newCount = offtopicCount + 1
          setOfftopicCount(newCount)
          
          // 이탈 4번째부터 강제 종료 (3번까지는 허용)
          if (newCount >= 4) {
            console.log('🔚 이탈 4회 - 강제 종료')
            setIsEnding(true)
            setIsGeneratingFeedback(true)
            handleEndSimulation()
            setLoading(false)
            return
          }
          
          // 이탈 알림 표시 (3초 후 자동 제거)
          setError('은행 신입사원 온보딩입니다. 관련된 답변만 하십시오.')
          setTimeout(() => setError(''), 3000)
          console.log('⚠️ 이탈 감지 (프론트엔드):', transcribed_text, `(횟수: ${newCount}/3)`)
          
          // 🔥 이탈이어도 사용자 메시지는 대화에 추가
          let updatedChatHistory: ChatMessage[] = [...chatHistory]
          updatedChatHistory.push({
            id: Date.now().toString(),
            role: 'user',
            text: transcribed_text,
            timestamp: new Date()
          })
          setChatHistory(updatedChatHistory)
          setLoading(false)
          return // 고객 응답은 받지 않음
        }
      }
      
      // 🔥 끝맺음 용어가 먼저 감지되면 바로 종료 (고객 응답 받지 않음)
      let isEndMessage = false
      if (transcribed_text && !isEnding) {
        isEndMessage = checkConversationEnd(transcribed_text)
        if (isEndMessage) {
          console.log('🔚 종료 표현 감지 (끝맺음 용어):', transcribed_text)
          setIsEnding(true) // 종료 중 상태로 설정
          // 사용자 메시지만 추가하고 고객 응답은 받지 않음
          let updatedChatHistory: ChatMessage[] = [...chatHistory]
          updatedChatHistory.push({
            id: Date.now().toString(),
            role: 'user',
            text: transcribed_text,
            timestamp: new Date()
          })
          setChatHistory(updatedChatHistory)
          // 바로 평가서 생성 시작
          setIsGeneratingFeedback(true)
          handleEndSimulation()
          setLoading(false)
          return
        }
      }
      
      // 백엔드의 end_signal 확인
      if (end_signal === true && !isEnding) {
        isEndMessage = true
        console.log('🔚 종료 신호 수신 (백엔드 LLM 판단):', transcribed_text)
        setIsEnding(true)
      }
      
      // 백엔드에서 이탈 감지 시 에러 메시지만 표시하고 대화에는 추가하지 않음
      if (error) {
        // 백엔드에서 반환한 이탈 카운터 사용 (없으면 프론트엔드 카운터 증가)
        const backendCount = response.data.offtopic_count
        const newCount = backendCount !== undefined ? backendCount : offtopicCount + 1
        setOfftopicCount(newCount)
        
        // 이탈 3번이면 강제 종료
        if (newCount >= 3) {
          console.log('🔚 이탈 3회 - 강제 종료')
          setIsEnding(true)
          setIsGeneratingFeedback(true)
          handleEndSimulation()
          setLoading(false)
          return
        }
        
        setError(error)
        setLoading(false)
        console.log('⚠️ 이탈 감지 (백엔드):', error, `(횟수: ${newCount}/3)`)
        // 3초 후 에러 메시지 자동 제거
        setTimeout(() => setError(''), 3000)
        return
      }
      
      // 정상 응답 시 이탈 카운터 리셋 (온토픽으로 돌아옴)
      if (response.data.offtopic_count !== undefined && response.data.offtopic_count === 0) {
        setOfftopicCount(0)
      }
      
      // 오디오 페이로드 디버깅
      console.log('오디오 페이로드 타입:', typeof customer_audio);
      console.log('오디오 페이로드 미리보기:', typeof customer_audio === 'string' ? customer_audio.substring(0, 100) : customer_audio);

      console.log('API 응답 데이터:', { transcribed_text, customer_response, customer_audio: customer_audio ? customer_audio.substring(0, 100) + '...' : null })

      // 🔥 종료 중이면 고객 응답을 받지 않음
      if (isEnding) {
        setLoading(false)
        return
      }
      
      // 🔥 첫 메시지 처리: 초기화 상태 해제 및 대화창 표시 시작
      let updatedChatHistory: ChatMessage[] = [...chatHistory]
      
      if (isInitializing) {
        setIsInitializing(false) // 대화 시작 (알림 모달 숨김)
      }
      
      // 대화 히스토리에 사용자 메시지 추가 (사용자가 실제로 말한 것만)
      if (transcribed_text) {
        updatedChatHistory.push({
          id: Date.now().toString(),
          role: 'user',
          text: transcribed_text,
          timestamp: new Date()
        })
      }
      
      // 대화 히스토리에 고객 메시지 추가
      if (customer_response && !isEnding) {
        updatedChatHistory.push({
          id: (Date.now() + 1).toString(),
          role: 'customer',
          text: customer_response,
          audio: customer_audio,
          timestamp: new Date()
        })
        
        // 🔥 아바타가 말하도록 설정
        if (customer_audio) {
          setAudio({
            audioUrl: customer_audio,
            text: customer_response,
            mouthCues: [] // TODO: Rhubarb로 생성
          })
        }
      }
      
      setChatHistory(updatedChatHistory)

      // 사용자 입력 필드 초기화
      setUserMessage('')

      // 🔥 종료 중이면 고객 음성 재생하지 않음
      if (isEnding) {
        setLoading(false)
        return
      }

      // 고객 음성 재생 - 새로운 유틸 사용
      if (customer_audio) {
        try {
          console.log('🎵 오디오 재생 시도...');
          await playFromAnyAudioPayload(customer_audio, 'audio/mpeg');
          setIsPlaying(true);
          setError('');
          
          // 종료 플래그가 설정되어 있으면 오디오 재생 후 시뮬레이션 종료
          if (isEndMessage) {
            const responseLength = customer_response?.length || 0
            const estimatedAudioDuration = Math.max(2000, Math.min(responseLength * 100, 5000)) // 재생 시간 단축
            setTimeout(() => {
              console.log('🔚 대화 종료: 고객 응답 재생 완료 후 종료')
              // 대화창을 즉시 숨기고 평가서 생성 시작
              setIsGeneratingFeedback(true)
              handleEndSimulation()
            }, estimatedAudioDuration)
          }
        } catch (audioError) {
          console.error('오디오 재생 실패:', audioError);
          setError('오디오 재생에 실패했습니다.');
          
          // 오디오 재생 실패 시에도 종료 플래그가 설정되어 있으면 종료
          if (isEndMessage) {
            setTimeout(() => {
              console.log('🔚 대화 종료: 오디오 재생 실패로 인한 종료')
              // 대화창을 즉시 숨기고 평가서 생성 시작
              setIsGeneratingFeedback(true)
              handleEndSimulation()
            }, 1000)
          }
        }
      } else {
        console.log('오디오 데이터가 없습니다. 텍스트만 표시됩니다.')
        
        // 오디오가 없을 때도 종료 플래그가 설정되어 있으면 종료
        if (isEndMessage) {
          setTimeout(() => {
            console.log('🔚 대화 종료: 오디오 없음으로 인한 종료')
            // 대화창을 즉시 숨기고 평가서 생성 시작
            setIsGeneratingFeedback(true)
            handleEndSimulation()
          }, 1000)
        }
      }

      setSubtitle('')

    } catch (error: any) {
      console.error('❌ 음성 처리 실패:', error)
      setError('음성 처리를 실패했습니다. 다시 시도해주세요.')
    } finally {
      setLoading(false)
      console.groupEnd();
    }
  }

  // 텍스트 입력으로도 시뮬레이션 가능
  const handleTextSubmit = async () => {
    if (!userMessage.trim()) return

    console.groupCollapsed('💬 텍스트 인터랙션 요청');

    try {
      setLoading(true)
      setError('')

      // 🔥 프론트엔드에서 이탈 감지 (백엔드 전송 전)
      if (userMessage && !isEnding) {
        const isOfftopic = !isOnTopic(userMessage)
        if (isOfftopic) {
          console.log('⚠️ 프론트엔드 이탈 감지 (전송 전):', userMessage)
          const newCount = offtopicCount + 1
          setOfftopicCount(newCount)
          
          // 이탈 4번째부터 강제 종료 (3번까지는 허용)
          if (newCount >= 4) {
            console.log('🔚 이탈 4회 - 강제 종료')
            setIsEnding(true)
            setIsGeneratingFeedback(true)
            handleEndSimulation()
            setLoading(false)
            return
          }
          
          // 🔥 이탈이어도 사용자 메시지는 대화에 추가
          let updatedChatHistory: ChatMessage[] = [...chatHistory]
          updatedChatHistory.push({
            id: Date.now().toString(),
            role: 'user',
            text: userMessage,
            timestamp: new Date()
          })
          setChatHistory(updatedChatHistory)
          setUserMessage('')
          
          // 이탈 알림 표시 (3초 후 자동 제거)
          setError('은행 신입사원 온보딩입니다. 관련된 답변만 하십시오.')
          setLoading(false)
          console.log('⚠️ 이탈 감지 (프론트엔드):', userMessage, `(횟수: ${newCount}/3)`)
          setTimeout(() => setError(''), 3000)
          return // 백엔드로 전송하지 않음
        }
      }

      console.log('전송할 메시지:', userMessage);
      console.log('세션 데이터:', simulationData);
      console.log('세션 데이터 키:', Object.keys(simulationData || {}));

      // 세션 데이터에 대화 히스토리 및 달성된 목표 포함
      const sessionDataWithHistory = {
        ...simulationData,
        conversation_history: chatHistory.map(msg => ({
          role: msg.role === 'user' ? 'employee' : 'customer',
          text: msg.text,
          timestamp: msg.timestamp.toISOString()
        })),
        achieved_goals: Array.from(checkedGoals), // 달성된 목표 포함
        offtopic_count: offtopicCount // 프론트엔드 이탈 카운터 사용
      }

      // JSON으로 전송
      const requestData = {
        session_data: sessionDataWithHistory,
        user_message: userMessage
      };

      console.log('요청 데이터 구조:', {
        session_data_keys: Object.keys(requestData.session_data || {}),
        user_message: requestData.user_message
      });

      // JSON으로 직접 전송 (Axios가 자동으로 Content-Type 설정)
      const response = await api.post('/rag-simulation/process-voice-interaction', requestData)

      console.log('✅ 응답 원본:', response.data);
      
      if (!response.data) {
        console.error('응답 데이터가 없습니다');
        setError('서버 응답이 비어있습니다.');
        return;
      }

      const { customer_response, customer_audio, end_signal, error } = response.data
      
      // 🔥 프론트엔드에서도 이탈 감지 (백엔드와 이중 체크) - 이미 전송 전에 체크했으므로 여기서는 백엔드 응답만 처리
      
      // 🔥 끝맺음 용어가 먼저 감지되면 바로 종료 (고객 응답 받지 않음)
      let isEndMessage = false
      if (userMessage && !isEnding) {
        isEndMessage = checkConversationEnd(userMessage)
        if (isEndMessage) {
          console.log('🔚 종료 표현 감지 (끝맺음 용어):', userMessage)
          setIsEnding(true) // 종료 중 상태로 설정
          // 사용자 메시지만 추가하고 고객 응답은 받지 않음
          let updatedChatHistory: ChatMessage[] = [...chatHistory]
          updatedChatHistory.push({
            id: Date.now().toString(),
            role: 'user',
            text: userMessage,
            timestamp: new Date()
          })
          setChatHistory(updatedChatHistory)
          setUserMessage('')
          // 바로 평가서 생성 시작
          setIsGeneratingFeedback(true)
          handleEndSimulation()
          setLoading(false)
          return
        }
      }
      
      // 백엔드의 end_signal 확인
      if (end_signal === true && !isEnding) {
        isEndMessage = true
        console.log('🔚 종료 신호 수신 (백엔드 LLM 판단):', userMessage)
        setIsEnding(true)
      }
      
      // 백엔드에서 이탈 감지 시 에러 메시지만 표시하고 대화에는 추가하지 않음
      if (error) {
        // 백엔드에서 반환한 이탈 카운터 사용 (없으면 프론트엔드 카운터 증가)
        const backendCount = response.data.offtopic_count
        const newCount = backendCount !== undefined ? backendCount : offtopicCount + 1
        setOfftopicCount(newCount)
        
        // 이탈 4번째부터 강제 종료 (3번까지는 허용)
        if (newCount >= 4) {
          console.log('🔚 이탈 4회 - 강제 종료')
          setIsEnding(true)
          setIsGeneratingFeedback(true)
          handleEndSimulation()
          setLoading(false)
          return
        }
        
        // 🔥 이탈이어도 사용자 메시지는 대화에 추가
        let updatedChatHistory: ChatMessage[] = [...chatHistory]
        updatedChatHistory.push({
          id: Date.now().toString(),
          role: 'user',
          text: userMessage,
          timestamp: new Date()
        })
        setChatHistory(updatedChatHistory)
        setUserMessage('')
        
        setError(error)
        setLoading(false)
        console.log('⚠️ 이탈 감지 (백엔드):', error, `(횟수: ${newCount}/3)`)
        // 3초 후 에러 메시지 자동 제거
        setTimeout(() => setError(''), 3000)
        return // 고객 응답은 받지 않음
      }
      
      // 정상 응답 시 이탈 카운터 리셋 (온토픽으로 돌아옴)
      if (response.data.offtopic_count !== undefined && response.data.offtopic_count === 0) {
        setOfftopicCount(0)
      }

      console.log('고객 응답:', customer_response);
      console.log('고객 오디오 있음:', !!customer_audio);
      console.log('종료 신호:', end_signal);

      // 🔥 종료 중이면 고객 응답을 받지 않음
      if (isEnding) {
        setLoading(false)
        return
      }

      // 🔥 첫 메시지 처리: 초기화 상태 해제 및 대화창 표시 시작
      let updatedChatHistory: ChatMessage[] = [...chatHistory]
      
      if (isInitializing) {
        setIsInitializing(false) // 대화 시작 (알림 모달 숨김)
      }
      
      // 대화 히스토리에 사용자 메시지 추가 (사용자가 실제로 입력한 것만)
      updatedChatHistory.push({
        id: Date.now().toString(),
        role: 'user',
        text: userMessage,
        timestamp: new Date()
      })
      
      // 대화 히스토리에 고객 메시지 추가
      if (customer_response && !isEnding) {
        updatedChatHistory.push({
          id: (Date.now() + 1).toString(),
          role: 'customer',
          text: customer_response,
          audio: customer_audio,
          timestamp: new Date()
        })
        
        // 🔥 아바타가 말하도록 설정
        if (customer_audio) {
          setAudio({
            audioUrl: customer_audio,
            text: customer_response,
            mouthCues: [] // TODO: Rhubarb로 생성
          })
        }
      }
      
      setChatHistory(updatedChatHistory)

      // 사용자 입력 필드 초기화
      setUserMessage('')

      // 🔥 종료 중이면 고객 음성 재생하지 않음
      if (isEnding) {
        setLoading(false)
        return
      }

      // 오디오 재생 - 새로운 유틸 사용
      if (customer_audio) {
        try {
          console.log('🎵 오디오 재생 시도...');
          await playFromAnyAudioPayload(customer_audio, 'audio/mpeg');
          setIsPlaying(true);
          setError('');
          
          // 종료 플래그가 설정되어 있으면 오디오 재생 후 시뮬레이션 종료 (고객 응답을 듣는 시간 제공)
          if (isEndMessage) {
            // 고객 응답 길이를 고려하여 대기 시간 설정 (평균적으로 2-5초 정도)
            const responseLength = customer_response?.length || 0
            const estimatedAudioDuration = Math.max(2000, Math.min(responseLength * 100, 5000)) // 최소 2초, 최대 5초
            setTimeout(() => {
              console.log('🔚 대화 종료: 고객 응답 재생 완료 후 종료')
              // 대화창을 즉시 숨기고 평가서 생성 시작
              setIsGeneratingFeedback(true)
              handleEndSimulation()
            }, estimatedAudioDuration)
          }
        } catch (audioError) {
          console.error('오디오 재생 실패:', audioError);
          setError('오디오 재생에 실패했습니다.');
          
          // 오디오 재생 실패 시에도 종료 플래그가 설정되어 있으면 종료
          if (isEndMessage) {
            setTimeout(() => {
              console.log('🔚 대화 종료: 오디오 재생 실패로 인한 종료')
              // 대화창을 즉시 숨기고 평가서 생성 시작
              setIsGeneratingFeedback(true)
              handleEndSimulation()
            }, 1000)
          }
        }
      } else {
        console.log('오디오 데이터가 없습니다. 텍스트만 표시됩니다.');
        
        // 오디오가 없을 때도 종료 플래그가 설정되어 있으면 종료
        if (isEndMessage) {
          setTimeout(() => {
            console.log('🔚 대화 종료: 오디오 없음으로 인한 종료')
            // 대화창을 즉시 숨기고 평가서 생성 시작
            setIsGeneratingFeedback(true)
            handleEndSimulation()
          }, 1000)
        }
      }

    } catch (error: any) {
      console.error('❌ 텍스트 처리 실패:', error)
      console.error('에러 상세:', error?.response?.data || error?.message)
      setError(`메시지 처리를 실패했습니다: ${error?.response?.data?.detail || error?.message || '알 수 없는 오류'}`)
    } finally {
      setLoading(false)
      console.groupEnd();
    }
  }

  // 오디오 재생 완료 처리 및 자동 재생 준비
  useEffect(() => {
    if (audioRef.current) {
      audioRef.current.onended = () => {
        setIsPlaying(false)
        // URL 객체 정리
        if (audioRef.current?.src && audioRef.current.src.startsWith('blob:')) {
          URL.revokeObjectURL(audioRef.current.src)
        }
      }
      
      audioRef.current.onerror = () => {
        setIsPlaying(false)
        setError('오디오 재생 중 오류가 발생했습니다.')
      }
    }
  }, [])

  // 시뮬레이션 완료 페이지
  if (isSimulationCompleted) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-purple-50 flex items-center justify-center p-6 relative">
        {/* 배경 블러 오버레이 */}
        <div className="absolute inset-0 bg-black bg-opacity-10 backdrop-blur-sm"></div>
        
        {/* 완료 카드 */}
        <div className="relative bg-white rounded-2xl shadow-2xl p-8 max-w-md w-full animate-fade-in z-10">
          <style>{`
            @keyframes fade-in {
              from {
                opacity: 0;
                transform: translateY(-20px);
              }
              to {
                opacity: 1;
                transform: translateY(0);
              }
            }
            .animate-fade-in {
              animation: fade-in 0.3s ease-out;
            }
          `}</style>
          
          {/* 체크 아이콘 */}
          <div className="flex justify-center mb-6">
            <div className="w-20 h-20 bg-green-100 rounded-full flex items-center justify-center">
              <CheckIcon className="w-12 h-12 text-green-600" />
            </div>
          </div>
          
          {/* 완료 메시지 */}
          <div className="text-center mb-8">
            <h2 className="text-3xl font-bold text-gray-900 mb-3">
              시뮬레이션이 완료되었습니다
            </h2>
            <p className="text-gray-600 text-lg">
              고객과의 대화가 종료되었습니다.
            </p>
            <p className="text-gray-600 text-lg mt-2">
              이제 신입사원 응대에 대한 평가를 진행해 주세요.
            </p>
          </div>
          
          {/* 통계 (선택사항) */}
          <div className="mb-8 grid grid-cols-2 gap-4">
            <div className="bg-gray-50 rounded-lg p-4 text-center">
              <div className="text-2xl font-bold text-blue-600">{chatHistory.length}</div>
              <div className="text-sm text-gray-600 mt-1">대화 턴</div>
            </div>
            <div className="bg-gray-50 rounded-lg p-4 text-center">
              <div className="text-2xl font-bold text-green-600">{checkedGoals.size}</div>
              <div className="text-sm text-gray-600 mt-1">달성 목표</div>
            </div>
          </div>
          
          {/* 버튼 그룹 */}
          <div className="space-y-4">
            <button
              onClick={handleGoToEvaluation}
              className="w-full bg-gradient-to-r from-blue-500 to-purple-600 text-white font-semibold py-4 px-6 rounded-lg hover:from-blue-600 hover:to-purple-700 transition-all duration-200 shadow-lg hover:shadow-xl transform hover:scale-[1.02]"
            >
              📝 평가 페이지로 이동
            </button>
            
            <button
              onClick={handleRestartSimulation}
              className="w-full bg-gray-100 text-gray-700 font-semibold py-4 px-6 rounded-lg hover:bg-gray-200 transition-all duration-200 border border-gray-300"
            >
              🔁 다시 시뮬레이션하기
            </button>
            
            <button
              onClick={onBack}
              className="w-full text-gray-500 hover:text-gray-700 font-medium py-2 px-4 transition-colors"
            >
              뒤로가기
            </button>
          </div>
        </div>
      </div>
    )
  }

  // 평가서 생성 중 로딩 화면
  if (isGeneratingFeedback) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-purple-50 flex items-center justify-center p-6">
        <div className="bg-white rounded-2xl shadow-2xl p-12 max-w-md w-full text-center">
          <div className="flex justify-center mb-6">
            <div className="w-20 h-20 bg-blue-100 rounded-full flex items-center justify-center">
              <ArrowPathIcon className="w-12 h-12 text-blue-600 animate-spin" />
            </div>
          </div>
          <h2 className="text-3xl font-bold text-gray-900 mb-4">
            평가서 생성 중...
          </h2>
          <p className="text-gray-600 text-lg">
            대화 내용을 분석하여 평가서를 작성하고 있습니다.
          </p>
          <p className="text-gray-500 text-sm mt-2">
            잠시만 기다려주세요.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-100 flex">
      {/* 왼쪽: 시뮬레이션 정보 패널 - 고정 너비 */}
      <div className="w-80 bg-white border-r border-gray-200 p-6 overflow-y-auto flex-shrink-0">
        <div className="mb-6">
          <button
            onClick={onBack}
            className="flex items-center text-gray-600 hover:text-gray-800 transition-colors mb-4"
          >
            <ArrowLeftIcon className="w-5 h-5 mr-2" />
            뒤로가기
          </button>
          <h2 className="text-xl font-bold text-gray-900">시뮬레이션 정보</h2>
        </div>

        {/* 고객 정보 */}
        <div className="mb-6">
          <button
            onClick={() => setIsCustomerInfoOpen(!isCustomerInfoOpen)}
            className="w-full flex items-center justify-between font-semibold text-gray-700 mb-3 hover:text-gray-900 transition-colors"
          >
            <span>고객 정보</span>
            {isCustomerInfoOpen ? (
              <ChevronUpIcon className="w-5 h-5" />
            ) : (
              <ChevronDownIcon className="w-5 h-5" />
            )}
          </button>
          {isCustomerInfoOpen && (
            <div className="bg-gray-50 rounded-lg p-4 space-y-2">
              <div className="flex justify-between">
                <span className="text-gray-600">성별:</span>
                <span className="font-medium text-gray-900">
                  {simulationData?.persona?.gender || '미설정'}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">연령대:</span>
                <span className="font-medium text-gray-900">
                  {simulationData?.persona?.age_group || '미설정'}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">직업:</span>
                <span className="font-medium text-gray-900">
                  {simulationData?.persona?.occupation || '미설정'}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">고객 타입:</span>
                <span className="font-medium text-gray-900">
                  {simulationData?.persona?.type || '미설정'}
                </span>
              </div>
            </div>
          )}
        </div>

        {/* 상황 정보 */}
        <div>
          <button
            onClick={() => setIsSituationInfoOpen(!isSituationInfoOpen)}
            className="w-full flex items-center justify-between font-semibold text-gray-700 mb-3 hover:text-gray-900 transition-colors"
          >
            <span>상황 정보</span>
            {isSituationInfoOpen ? (
              <ChevronUpIcon className="w-5 h-5" />
            ) : (
              <ChevronDownIcon className="w-5 h-5" />
            )}
          </button>
          {isSituationInfoOpen && (
            <div className="bg-gray-50 rounded-lg p-4 space-y-2">
              <div className="flex justify-between">
                <span className="text-gray-600">업무 카테고리:</span>
                <span className="font-medium text-gray-900">
                  {simulationData?.situation?.category || '미설정'}
                </span>
              </div>
              <div>
                <span className="text-gray-600">상황 제목:</span>
                <div className="font-medium text-gray-900 mt-1">
                  {simulationData?.situation?.title || '미설정'}
                </div>
              </div>
              {simulationData?.situation?.goals && simulationData.situation.goals.length > 0 && (
                <div className="mt-3">
                  <span className="text-gray-600 text-sm block mb-1">목표:</span>
                  <ul className="space-y-2">
                    {simulationData.situation.goals.map((goal: string, index: number) => {
                      const isChecked = checkedGoals.has(index)
                      return (
                        <li
                          key={index}
                          className={`flex items-start gap-2 text-sm text-gray-700 rounded p-2 -ml-2 transition-colors ${
                            isChecked ? 'bg-green-50' : ''
                          }`}
                        >
                          <div className={`flex-shrink-0 mt-0.5 ${
                            isChecked ? 'text-green-600' : 'text-gray-400'
                          }`}>
                            {isChecked ? (
                              <CheckIcon className="w-5 h-5" />
                            ) : (
                              <div className="w-5 h-5 border-2 border-gray-300 rounded" />
                            )}
                          </div>
                          <span className={isChecked ? 'text-green-700 line-through' : ''}>
                            {goal}
                          </span>
                        </li>
                      )
                    })}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* 오른쪽: 메인 시뮬레이션 영역 - 16:9 고정 */}
      <div className="flex-1 flex flex-col bg-white overflow-hidden">
        {/* 시작 전 화면 */}
        {!isStarted && (
          <div className="flex-1 flex items-center justify-center bg-gray-50">
            <div className="text-center">
              <h1 className="text-4xl font-bold text-gray-900 mb-4">시뮬레이션 준비</h1>
              <p className="text-gray-600 mb-8">시뮬레이션을 시작하려면 아래 버튼을 눌러주세요.</p>
              <button
                onClick={() => {
                  setIsStarted(true)
                  setIsInitializing(true)
                }}
                className="px-12 py-4 bg-blue-600 text-white text-xl font-semibold rounded-lg hover:bg-blue-700 transition-colors shadow-lg"
              >
                시뮬레이션 시작하기
              </button>
            </div>
          </div>
        )}

        {/* 시작 후 화면 */}
        {isStarted && (
          <>
            {/* 비디오 영역 - 16:9 비율 고정 */}
            <div 
              ref={videoContainerRef}
              className="relative bg-gray-900" 
              style={{ aspectRatio: '16/9', width: '100%' }}
            >
              {/* 전체 화면 버튼 */}
              {isStarted && (
                <button
                  onClick={toggleFullscreen}
                  className="absolute top-4 right-4 z-50 p-2 bg-black bg-opacity-50 text-white rounded-lg hover:bg-opacity-70 transition-all"
                  title={isFullscreen ? '전체 화면 해제' : '전체 화면'}
                >
                  {isFullscreen ? (
                    <ArrowsPointingInIcon className="w-6 h-6" />
                  ) : (
                    <ArrowsPointingOutIcon className="w-6 h-6" />
                  )}
                </button>
              )}
              {/* 🔥 초기 알림 오버레이 - 비디오 영역에 맞춰 표시 */}
              {isInitializing && initialInstructionMessage && (
                <div className="absolute inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center">
                  <div className="bg-white rounded-2xl p-8 max-w-lg w-full mx-4 shadow-2xl">
                    <div className="text-center">
                      <div className="text-5xl mb-4">💬</div>
                      <h2 className="text-2xl font-bold text-gray-900 mb-4">
                        {initialInstructionMessage || "안녕하세요, 무엇을 도와드릴까요?"}
                      </h2>
                      <p className="text-lg text-gray-700 mb-3">
                        위 메시지로 시작하세요.
                      </p>
                      <p className="text-base text-gray-600 mb-6">
                        마이크 버튼을 눌러 말을 시작해주세요.
                      </p>
                      <div className="flex justify-center">
                        <div className="bg-blue-50 border-2 border-blue-300 rounded-lg px-4 py-2">
                          <p className="text-blue-800 font-semibold text-sm">
                            📍 아래 빨간 녹음 버튼을 눌러주세요
                          </p>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              )}
              
              {/* 큰 화면: 페르소나 이미지 또는 사용자 카메라 */}
              {isPersonaMainView ? (
                // 페르소나 이미지가 큰 화면
                <div 
                  className="absolute inset-0 w-full h-full flex items-center justify-center cursor-pointer overflow-hidden"
                  onClick={(e) => {
                    e.stopPropagation()
                    console.log('🖱️ 큰 화면 페르소나 클릭 -> 카메라로 전환')
                    setIsPersonaMainView(false)
                  }}
                >
                  {simulationData?.persona ? (
                    <>
                      <img
                        src={getPersonaImageUrl(
                          simulationData.persona.gender || '여성',
                          simulationData.persona.age_group || '30대'
                        )}
                        alt="고객 페르소나"
                        className="w-full h-full object-cover"
                        onLoad={(e) => {
                          console.log('✅ 페르소나 이미지 로드 성공:', (e.target as HTMLImageElement).src)
                        }}
                        onError={(e) => {
                          const originalUrl = getPersonaImageUrl(
                            simulationData.persona.gender || '여성',
                            simulationData.persona.age_group || '30대'
                          )
                          handleImageError(e, 0, originalUrl)
                        }}
                      />
                    </>
                  ) : (
                    <div className="text-white text-center">
                      <VideoCameraIcon className="w-16 h-16 mx-auto mb-4 text-gray-400" />
                      <p className="text-gray-400">페르소나 정보를 불러오는 중...</p>
                      {process.env.NODE_ENV === 'development' && (
                        <p className="text-red-400 mt-2 text-sm">
                          simulationData: {JSON.stringify(simulationData?.persona || '없음')}
                        </p>
                      )}
                    </div>
                  )}
                </div>
              ) : (
                // 사용자 카메라가 큰 화면
                <div 
                  className="absolute inset-0 w-full h-full flex items-center justify-center cursor-pointer overflow-hidden"
                  onClick={(e) => {
                    e.stopPropagation()
                    console.log('🖱️ 큰 화면 카메라 클릭 -> 페르소나로 전환')
                    setIsPersonaMainView(true)
                  }}
                >
                  {videoStream ? (
                    <video
                      ref={videoRef}
                      autoPlay
                      playsInline
                      muted
                      className="w-full h-full object-cover"
                      style={{ transform: 'scaleX(-1)' }}
                      onLoadedMetadata={() => {
                        console.log('✅ 큰 화면 비디오 메타데이터 로드 완료')
                        if (videoRef.current && videoRef.current.paused) {
                          videoRef.current.play().catch(err => {
                            console.error('큰 화면 비디오 자동 재생 실패:', err)
                          })
                        }
                      }}
                      onCanPlay={() => {
                        console.log('✅ 큰 화면 비디오 재생 준비 완료')
                        if (videoRef.current && videoRef.current.paused) {
                          videoRef.current.play().catch(err => {
                            console.error('큰 화면 비디오 canPlay 재생 실패:', err)
                          })
                        }
                      }}
                      onError={(e) => {
                        console.error('❌ 큰 화면 비디오 에러:', e)
                      }}
                    />
                  ) : (
                    <div className="text-white text-center z-10">
                      <VideoCameraIcon className="w-16 h-16 mx-auto mb-4 text-gray-400" />
                      <p className="text-gray-400">카메라를 불러오는 중...</p>
                      {error && (
                        <p className="text-red-400 mt-2 text-sm">{error}</p>
                      )}
                    </div>
                  )}
                </div>
              )}
              
              {/* 작은 화면: 사용자 카메라 또는 페르소나 이미지 */}
              <div 
                className={`absolute bottom-4 right-4 w-48 h-48 rounded-lg overflow-hidden shadow-2xl border-4 border-white cursor-pointer transition-all duration-300 hover:scale-105 ${
                  !isPersonaMainView ? 'z-20' : 'z-10'
                }`}
                onClick={(e) => {
                  e.stopPropagation()
                  console.log('🖱️ 작은 화면 클릭 -> 화면 전환', { 현재상태: isPersonaMainView, 변경될상태: !isPersonaMainView })
                  setIsPersonaMainView(!isPersonaMainView)
                }}
              >
                {isPersonaMainView ? (
                  // 사용자 카메라가 작은 화면
                  videoStream ? (
                    <video
                      ref={smallVideoRef}
                      autoPlay
                      playsInline
                      muted
                      className="w-full h-full object-cover"
                      style={{ transform: 'scaleX(-1)' }}
                      onLoadedMetadata={() => {
                        console.log('✅ 작은 화면 비디오 메타데이터 로드 완료')
                        if (smallVideoRef.current && smallVideoRef.current.paused) {
                          smallVideoRef.current.play().catch(err => {
                            console.error('작은 화면 비디오 자동 재생 실패:', err)
                          })
                        }
                      }}
                      onCanPlay={() => {
                        console.log('✅ 작은 화면 비디오 재생 준비 완료')
                        if (smallVideoRef.current && smallVideoRef.current.paused) {
                          smallVideoRef.current.play().catch(err => {
                            console.error('작은 화면 비디오 canPlay 재생 실패:', err)
                          })
                        }
                      }}
                      onError={(e) => {
                        console.error('❌ 작은 화면 비디오 에러:', e)
                      }}
                    />
                  ) : (
                    <div className="w-full h-full bg-gray-800 flex items-center justify-center">
                      <VideoCameraIcon className="w-12 h-12 text-gray-400" />
                    </div>
                  )
                ) : (
                  // 페르소나 이미지가 작은 화면
                  simulationData?.persona ? (
                    <img
                      src={getPersonaImageUrl(
                        simulationData.persona.gender || '여성',
                        simulationData.persona.age_group || '30대'
                      )}
                      alt="고객 페르소나"
                      className="w-full h-full object-cover"
                      onLoad={(e) => {
                        console.log('✅ 작은 화면 페르소나 이미지 로드 성공:', (e.target as HTMLImageElement).src)
                      }}
                      onError={(e) => {
                        const originalUrl = getPersonaImageUrl(
                          simulationData.persona.gender || '여성',
                          simulationData.persona.age_group || '30대'
                        )
                        handleImageError(e, 0, originalUrl)
                      }}
                    />
                  ) : (
                    <div className="w-full h-full bg-gray-800 flex items-center justify-center">
                      <VideoCameraIcon className="w-12 h-12 text-gray-400" />
                    </div>
                  )
                )}
              </div>

              {/* 녹음 버튼 (하단 중앙) - 항상 활성화 (오버레이보다 위에 표시) */}
              <div className="absolute bottom-8 left-1/2 transform -translate-x-1/2 z-[60]">
                {!isRecording ? (
                  <button
                    onClick={startRecording}
                    disabled={loading}
                    className="flex items-center px-8 py-4 bg-red-600 text-white rounded-full hover:bg-red-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors shadow-2xl"
                  >
                    <MicrophoneIcon className="w-6 h-6 mr-2" />
                    녹음 시작
                  </button>
                ) : (
                  <button
                    onClick={stopRecording}
                    className="flex items-center px-8 py-4 bg-red-600 text-white rounded-full hover:bg-red-700 transition-colors shadow-2xl animate-pulse"
                  >
                    <StopIcon className="w-6 h-6 mr-2" />
                    녹음 중지
                  </button>
                )}
              </div>

              {/* 실시간 자막 */}
              {subtitle && (
                <div className="absolute top-8 left-1/2 transform -translate-x-1/2 bg-black bg-opacity-75 text-white px-6 py-3 rounded-lg z-30">
                  {subtitle}
                </div>
              )}
            </div>

            {/* 채팅 히스토리 - 입력 필드 고정, 대화 내용만 스크롤 */}
            <div className="flex flex-col bg-white border-t border-gray-200" style={{ height: '320px' }}>
              <h3 className="font-semibold text-gray-900 px-4 pt-4 pb-2 flex-shrink-0">대화</h3>
              
              {/* 스크롤 가능한 대화 내용 영역 - 대화창만 스크롤, 전체 화면은 고정 */}
              <div 
                className="flex-1 overflow-y-auto px-4 pb-2" 
                style={{ 
                  scrollBehavior: 'smooth',
                  position: 'relative',
                  // 전체 화면 상태에서도 대화창만 스크롤되도록 보장
                  overflowAnchor: 'none' // 자동 스크롤 방지 (우리가 직접 제어)
                }}
              >
                <div className="space-y-3">
                {chatHistory.length === 0 ? (
                  <div className="text-center text-gray-500 py-8">
                    대화를 시작하세요. 녹음 버튼을 눌러거나 텍스트를 입력하세요.
                  </div>
                ) : (
                  chatHistory.map((message) => (
                    <div
                      key={message.id}
                      className={`p-4 rounded-lg ${
                        message.role === 'user' ? 'bg-blue-50 ml-8' : 'bg-green-50 mr-8'
                      }`}
                    >
                      <div className="flex items-center mb-2">
                        <span className={`font-medium ${
                          message.role === 'user' ? 'text-blue-800' : 'text-green-800'
                        }`}>
                          {message.role === 'user' ? '신입사원 (나)' : '고객'}
                        </span>
                        <span className="text-xs text-gray-500 ml-2">
                          {message.timestamp.toLocaleTimeString()}
                        </span>
                      </div>
                      <p className={message.role === 'user' ? 'text-blue-700' : 'text-green-700'}>
                        {message.text}
                      </p>
                      {message.role === 'customer' && message.audio && (
                        <button
                          onClick={() => {
                            if (message.audio) {
                              playFromAnyAudioPayload(message.audio, 'audio/mpeg')
                            }
                          }}
                          className="mt-2 flex items-center px-3 py-1 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors text-sm"
                        >
                          <SpeakerWaveIcon className="w-3 h-3 mr-1" />
                          다시 듣기
                        </button>
                      )}
                    </div>
                  ))
                )}
                <div ref={chatEndRef} />
                </div>
              </div>

              {/* 텍스트 입력 (하단) - 고정 */}
              {!isInitializing && (
                <div className="px-4 pb-4 pt-2 border-t border-gray-200 flex-shrink-0">
                  <div className="flex space-x-2">
                    <input
                      type="text"
                      value={userMessage}
                      onChange={(e) => setUserMessage(e.target.value)}
                      onKeyPress={(e) => e.key === 'Enter' && handleTextSubmit()}
                      placeholder="메시지를 입력하세요..."
                      className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                    <button
                      onClick={handleTextSubmit}
                      disabled={loading || !userMessage.trim()}
                      className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
                    >
                      전송
                    </button>
                  </div>
                </div>
              )}
            </div>
          </>
        )}

        {/* 오류 메시지 */}
        {error && (
          <div className="fixed bottom-4 right-4 bg-red-50 border border-red-200 rounded-lg p-4 shadow-lg">
            <p className="text-red-600">{error}</p>
          </div>
        )}

        {/* 오디오 엘리먼트 */}
        <audio ref={audioRef} />
      </div>
    </div>
  )
}

export default VoiceSimulation
