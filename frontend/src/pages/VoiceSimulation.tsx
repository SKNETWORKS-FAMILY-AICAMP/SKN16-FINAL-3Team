import React, { useState, useRef, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'
import { usePersonaStore } from '../store/usePersonaStore'
import api from '../utils/api'
import { ragSimulationAPI } from '../utils/api'
import { playFromAnyAudioPayload } from '../utils/audio'
import { AudioVisualizer } from '../components/AudioVisualizer'
import CustomerAvatar from '../components/CustomerAvatar'
import { isOnTopic, containsProfanity } from '../utils/offtopicDetector'
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
  ChevronLeftIcon,
  ChevronRightIcon,
  CheckIcon,
  ArrowsPointingOutIcon,
  ArrowsPointingInIcon
} from '@heroicons/react/24/outline'

interface VoiceSimulationProps {
  simulationData: any
  onBack: () => void
}

// 상황 제목에서 "(추가#48)" 같은 내부 관리용 태그 제거
const sanitizeSituationTitle = (title: string): string => {
  if (!title) return ''
  return title.replace(/\s*\(추가\s*#\d+\)\s*$/g, '').trim()
}

// 따옴표("…") 안의 핵심 문구 + 주요 키워드를 하이라이트해서 렌더링
const renderHighlightedText = (text: string) => {
  if (!text) return null

  // 도메인 주요 키워드 (부분 일치)
  const keywordSubstrings = [
    '고객의 배경',
    '문의 의도',
    '현재 금융 상황',
    // 환전/여행 관련
    '여행 경비 환전',
    '환전·환율 우대',
    '환전 우대',
    '환전·환율',
    '환전',
    '환율',

    // 대출/우대금리 관련
    '대출금리·우대금리 구조',
    '대출금리',
    '우대금리',
    '핵심 조건',

    // 리스크·유의사항 관련
    '리스크·불이익',
    '규제·리스크·불이익',
    '규제·리스크',
    '리스크와 유의사항',
    '리스크와 유의 사항',
    '리스크',
    '유의사항',
  
    '커뮤니케이션 방식',

    // 마무리·정리 관련
    '다음에 무엇을 해야 하는지',
    '다음에 무엇을 해야 하는 지',
    '다음 단계',
    '요약',
    '정리해',
    '정리하여 안내',
  ]

  const highlightSegment = (segment: string, baseKey: number) => {
    const elements: JSX.Element[] = []
    let remaining = segment
    let localIndex = 0

    while (remaining.length > 0) {
      // 남은 문자열에서 가장 앞에 등장하는 키워드 찾기
      let earliestIndex = -1
      let matchedKeyword = ''

      for (const kw of keywordSubstrings) {
        if (!kw) continue
        const idx = remaining.indexOf(kw)
        if (idx !== -1 && (earliestIndex === -1 || idx < earliestIndex)) {
          earliestIndex = idx
          matchedKeyword = kw
        }
      }

      if (earliestIndex === -1 || !matchedKeyword) {
        // 더 이상 키워드가 없으면 나머지를 그대로 추가
        elements.push(
          <span key={`${baseKey}-${localIndex++}`}>
            {remaining}
          </span>
        )
        break
      }

      // 키워드 이전의 일반 텍스트
      if (earliestIndex > 0) {
        const before = remaining.slice(0, earliestIndex)
        elements.push(
          <span key={`${baseKey}-${localIndex++}`}>
            {before}
          </span>
        )
      }

      // 키워드 자체 하이라이트
      const keywordText = remaining.slice(earliestIndex, earliestIndex + matchedKeyword.length)
      elements.push(
        <span
          key={`${baseKey}-${localIndex++}`}
          className="text-blue-800 bg-blue-100 px-1 rounded-md"
        >
          {keywordText}
        </span>
      )

      // 나머지 문자열로 계속 처리
      remaining = remaining.slice(earliestIndex + matchedKeyword.length)
    }

    return elements
  }

  // "..." 구간을 기준으로 분리 (따옴표 포함하여 보존)
  const parts = text.split(/(".*?")/g)

  return parts.map((part, index) => {
    if (!part) return null

    // 따옴표로 둘러싸인 구간은 강조
    if (part.startsWith('"') && part.endsWith('"') && part.length > 2) {
      const inner = part.slice(1, -1) // 따옴표 제거
      return (
        <span
          key={index}
          className="text-blue-800 bg-blue-100 px-1 rounded-md"
        >
          {inner}
        </span>
      )
    }

    // 그 외 일반 텍스트는 주요 키워드만 강조
    return <span key={index}>{highlightSegment(part, index)}</span>
  })
}

// 대화 메시지 타입
interface ChatMessage {
  id: string
  role: 'user' | 'customer'
  text: string
  audio?: string
  timestamp: Date
}

// 🧪 테스트 모드 시나리오 타입
// 🧪 이전 하드코딩된 시나리오 제거됨 - 백엔드에서 받은 test_scenario만 사용

interface RagCollectOptions {
  context?: string
  turnIndexHint?: number
  nextTurnRole?: string
}

const VoiceSimulation: React.FC<VoiceSimulationProps> = ({ simulationData, onBack }) => {
  const { user } = useAuthStore()
  const { setPersona, setAudio } = usePersonaStore()
  const navigate = useNavigate()
  const [isRecording, setIsRecording] = useState(false)
  const [isPlaying, setIsPlaying] = useState(false)
  const [userMessage, setUserMessage] = useState('')
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]) // 대화 히스토리
  const chatHistoryRef = useRef<ChatMessage[]>([]) // 🚨 최신 chatHistory 추적용 ref
  
  // 🚨 chatHistory가 변경될 때마다 ref도 업데이트 (최신 상태 보장)
  useEffect(() => {
    chatHistoryRef.current = chatHistory
    console.log(`📊 chatHistory ref 업데이트: ${chatHistory.length}개 메시지`)
  }, [chatHistory])
  
  // 🔧 헬퍼 함수: setChatHistory와 ref를 동시에 업데이트 (비동기 문제 해결)
  const updateChatHistory = (newHistory: ChatMessage[]) => {
    chatHistoryRef.current = newHistory // 🚨 ref 먼저 즉시 업데이트
    setChatHistory(newHistory) // 그 다음 state 업데이트
    console.log(`📊 chatHistory 동시 업데이트: ${newHistory.length}개 메시지`)
  }
  
  const [subtitle, setSubtitle] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [stream, setStream] = useState<MediaStream | null>(null) // 오디오 스트림
  const [videoStream, setVideoStream] = useState<MediaStream | null>(null) // 비디오 스트림
  const [isInitializing, setIsInitializing] = useState(true) // 초기화 상태
  
  // 🧪 테스트 모드: 시뮬레이션 시작 시 conversation_history 초기화
  // ⚠️ 중요: 첫 번째 직원 인사는 사용자가 녹음할 때 추가되므로 여기서는 초기화하지 않음
  // 백엔드에서도 initial_conversation_history를 빈 배열로 반환하므로 여기서도 빈 배열로 시작
  useEffect(() => {
    const isTestMode = simulationData?.is_test_mode || !!simulationData?.test_scenario
    if (isTestMode) {
      // 테스트 모드에서는 chatHistory를 빈 배열로 시작
      // 첫 번째 직원 인사는 사용자가 녹음할 때 추가됨
      if (chatHistory.length === 0) {
        console.log('🧪 테스트 모드: chatHistory를 빈 배열로 초기화 (첫 번째 직원 인사는 사용자 녹음 시 추가됨)')
        setChatHistory([])
        setScenarioStep(0) // 🧪 시나리오 턴도 초기화
      }
    }
  }, [simulationData?.is_test_mode, simulationData?.test_scenario])
  const [isStarted, setIsStarted] = useState(false) // 시뮬레이션 시작 여부
  const [initialInstructionMessage, setInitialInstructionMessage] = useState<string>('') // 초기 안내 메시지
  const [isSimulationInfoOpen, setIsSimulationInfoOpen] = useState(true) // 시뮬레이션 정보 패널 열기/닫기 (기본값: 열림)
  const [activeTab, setActiveTab] = useState<'customer' | 'situation-detail' | 'goals'>('customer') // 활성 탭
  const [checkedGoals, setCheckedGoals] = useState<Set<number>>(new Set()) // 달성된 목표 인덱스
  const [goalAchievementTimes, setGoalAchievementTimes] = useState<Map<number, number>>(new Map()) // 목표별 달성 턴 번호
  const [isChatCollapsed, setIsChatCollapsed] = useState(false) // 대화창 접기/펼치기 상태
  const [isSimulationCompleted, setIsSimulationCompleted] = useState(false) // 시뮬레이션 완료 상태
  const [isGeneratingFeedback, setIsGeneratingFeedback] = useState(false) // 평가서 생성 중 상태
  const [feedbackProgress, setFeedbackProgress] = useState(0) // 평가서 생성 진행률 (0-100)
  const progressIntervalRef = useRef<NodeJS.Timeout | null>(null) // 진행률 시뮬레이션 interval 참조
  const [isPersonaMainView, setIsPersonaMainView] = useState(true) // 페르소나가 큰 화면인지 (기본값: true)
  const [offtopicCount, setOfftopicCount] = useState(0) // 이탈 카운터
  const [isEnding, setIsEnding] = useState(false) // 종료 중 상태 (끝맺음 용어 감지 시)
  const [simulationStartTime, setSimulationStartTime] = useState<number | null>(null) // 시뮬레이션 시작 시간
  const [isFullscreen, setIsFullscreen] = useState(false) // 전체 화면 상태
  const [currentFeedbackId, setCurrentFeedbackId] = useState<number | null>(null) // 현재 피드백 ID (녹화 연결용)
  const [currentRecordingId, setCurrentRecordingId] = useState<string | null>(null) // 현재 녹화 ID (UUID 문자열)
  const [currentTurnIndex, setCurrentTurnIndex] = useState<number>(0) // 테스트 모드 현재 턴 인덱스
  const [currentExpectedText, setCurrentExpectedText] = useState<string>('') // 테스트 모드 현재 기대 텍스트
  const [scenarioStep, setScenarioStep] = useState<number>(0) // 🧪 테스트 모드: 시나리오 턴 인덱스 (0 → Turn 1, 1 → Turn 2 ...)
  const [ragEvaluations, setRagEvaluations] = useState<any[]>([]) // 🧪 테스트 모드: RAG 평가 결과 누적
  const ragEvaluationsRef = useRef<any[]>([])
  const [ragSummary, setRagSummary] = useState<any>(null) // 🧪 테스트 모드: RAG 평가 종합 결과
  const ragSummaryRef = useRef<any>(null)

  const updateRagEvaluationsState = useCallback((evaluations: any[]) => {
    ragEvaluationsRef.current = evaluations
    setRagEvaluations(evaluations)
  }, [])

  const updateRagSummaryState = useCallback((summary: any) => {
    ragSummaryRef.current = summary
    setRagSummary(summary)
  }, [])

  // 테스트 모드 여부 계산 (컴포넌트 레벨에서)
  const isTestMode = simulationData?.is_test_mode || !!simulationData?.test_scenario

  // 🚨 중요: simulationData의 최신 상태를 유지하기 위한 Ref
  // processAudio가 클로저로 인해 이전 simulationData를 참조하는 문제를 방지
  const simulationDataRef = useRef<any>(simulationData)

  useEffect(() => {
    simulationDataRef.current = simulationData
  }, [simulationData])

  const computeRagSummaryFromEvaluations = (evaluations: any[]) => {
    if (!evaluations || evaluations.length === 0) {
      return {
        total_evaluations: 0,
        employee_count: 0,
        customer_count: 0,
        employee_average: 0,
        customer_average: 0,
        average_score: 0
      }
    }

    const employeeEvals = evaluations.filter((e: any) => e.role === 'employee')
    const customerEvals = evaluations.filter((e: any) => e.role === 'customer')
    const allScores = evaluations.map((e: any) => e.evaluation?.score || 0)
    const avgScore = allScores.length > 0 ? allScores.reduce((a: number, b: number) => a + b, 0) / allScores.length : 0
    const empAvg = employeeEvals.length > 0
      ? employeeEvals.reduce((sum: number, e: any) => sum + (e.evaluation?.score || 0), 0) / employeeEvals.length
      : 0
    const custAvg = customerEvals.length > 0
      ? customerEvals.reduce((sum: number, e: any) => sum + (e.evaluation?.score || 0), 0) / customerEvals.length
      : 0

    return {
      total_evaluations: evaluations.length,
      employee_count: employeeEvals.length,
      customer_count: customerEvals.length,
      employee_average: empAvg,
      customer_average: custAvg,
      average_score: avgScore
    }
  }

  const collectRagDataFromResponse = (
    responseData: any,
    options: RagCollectOptions = {}
  ): boolean => {
    // 🧪 테스트 모드 확인 (함수 내부에서도 확인)
    const isTestModeLocal = simulationData?.is_test_mode || !!simulationData?.test_scenario || responseData?.is_test_mode
    
    if (!responseData) {
      return false
    }
    
    // 🧪 테스트 모드이거나 RAG 평가 데이터가 있으면 수집
    if (!isTestModeLocal && !responseData.rag_evaluations && !responseData.rag_evaluation && !responseData.rag_evaluation_customer) {
      return false
    }

    const contextLabel = options.context || 'default'

    if (responseData.rag_evaluations && Array.isArray(responseData.rag_evaluations)) {
      const evaluations = responseData.rag_evaluations
      updateRagEvaluationsState(evaluations)

      if (responseData.rag_summary) {
        updateRagSummaryState(responseData.rag_summary)
      } else if (evaluations.length > 0) {
        updateRagSummaryState(computeRagSummaryFromEvaluations(evaluations))
      }

      console.log(`🧪 ✅ RAG 평가 결과 수집 (${contextLabel} - 전체 배열):`, {
        total: evaluations.length,
        summary: responseData.rag_summary || computeRagSummaryFromEvaluations(evaluations)
      })
      return true
    }

    const singleEval = responseData.rag_evaluation || responseData.rag_evaluation_customer
    if (singleEval) {
      const expectedProductCode = singleEval.expected_product_code ||
        responseData.rag_evaluation?.expected_product_code ||
        responseData.rag_evaluation_customer?.expected_product_code

      const derivedRole = options.nextTurnRole === 'customer'
        ? 'employee'
        : options.nextTurnRole === 'employee'
          ? 'customer'
          : singleEval.role || 'employee'

      const turnIndexFromResponse = typeof responseData.current_turn_index === 'number'
        ? responseData.current_turn_index
        : currentTurnIndex

      const turnIndex = options.turnIndexHint !== undefined
        ? options.turnIndexHint
        : turnIndexFromResponse

      setRagEvaluations(prev => {
        const updated = [
          ...prev,
          {
            turn_index: turnIndex,
            role: derivedRole,
            expected_product_code: expectedProductCode,
            evaluation: singleEval
          }
        ]
        ragEvaluationsRef.current = updated

        if (responseData.rag_summary) {
          updateRagSummaryState(responseData.rag_summary)
        } else {
          updateRagSummaryState(computeRagSummaryFromEvaluations(updated))
        }

        console.log(`🧪 ✅ 개별 RAG 평가 결과 수집 (${contextLabel}):`, {
          turn_index: turnIndex,
          role: derivedRole,
          score: singleEval.score,
          expected_product_code: expectedProductCode,
          total_evaluations: updated.length
        })

        return updated
      })
      return true
    }

    return false
  }

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

      // 🧪 테스트 모드: 첫 번째 턴의 expected_text 설정
      const isTestMode = simulationData?.is_test_mode || !!simulationData?.test_scenario
      console.log('🧪 테스트 모드 체크:', {
        is_test_mode: simulationData?.is_test_mode,
        has_test_scenario: !!simulationData?.test_scenario,
        test_scenario_turns: simulationData?.test_scenario?.turns?.length
      })
      
      if (isTestMode && simulationData?.test_scenario?.turns) {
        const firstTurn = simulationData.test_scenario.turns[0]
        if (firstTurn?.expected_text) {
          setCurrentExpectedText(firstTurn.expected_text)
          setCurrentTurnIndex(0)
          console.log('🧪 테스트 모드: 첫 번째 턴 기대 텍스트 설정:', firstTurn.expected_text)
          console.log('🧪 첫 번째 턴 역할:', firstTurn.role)
          
          // 🧪 첫 번째 턴이 직원 턴이면 대화창에 추가하지 않음 (사용자가 녹음해야 함)
          // 첫 번째 턴이 고객 턴이면 자동으로 고객 응답 생성 (하지만 여기서는 처리하지 않음, 첫 녹음 후 처리)
        } else {
          console.warn('🧪 첫 번째 턴에 expected_text가 없습니다:', firstTurn)
        }
      } else {
        console.warn('🧪 테스트 모드가 아니거나 test_scenario가 없습니다:', {
          isTestMode,
          hasTestScenario: !!simulationData?.test_scenario,
          hasTurns: !!simulationData?.test_scenario?.turns
        })
      }

      // 🔥 변경: 초기 안내 메시지만 저장, 대화창은 표시하지 않음
      const initialMessage = simulationData?.initial_message
      
      // 🧪 테스트 모드: chatHistory를 빈 배열로 시작 (첫 번째 직원 인사는 사용자 녹음 시 추가됨)
      const isTestModeForHistory = simulationData?.is_test_mode || !!simulationData?.test_scenario
      
      // 안내 메시지 저장 (대화창에는 추가하지 않음)
      if (initialMessage?.type === 'instruction' && initialMessage?.content) {
        setInitialInstructionMessage(initialMessage.content)
        // 테스트 모드에서는 chatHistory를 빈 배열로 시작
        setChatHistory([])
        setScenarioStep(0) // 🧪 시나리오 턴 초기화
        setIsInitializing(true) // 사용자가 말을 시작할 때까지 초기화 상태 유지
      } else {
        // 테스트 모드에서는 chatHistory를 빈 배열로 시작
        setChatHistory([])
        setScenarioStep(0) // 🧪 시나리오 턴 초기화
        setIsInitializing(false) // 초기 메시지가 없으면 바로 시작 가능
      }
    }
  }, [simulationData, isStarted])

  // 자동 녹화 시작 제거 - 사용자가 명시적으로 "녹음 시작" 버튼을 눌러야만 시작됨

  // 🔥 새 메시지(사용자 또는 고객)가 추가될 때 대화창 스크롤 (전체 화면은 무조건 고정)
  // 대화창 스크롤 함수 (재사용)
  const scrollToBottom = () => {
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

  useEffect(() => {
    // 새 메시지가 추가되면 대화창 내부만 스크롤
    if (chatHistory.length > 0) {
      scrollToBottom()
    }
  }, [chatHistory])

  // 로딩 상태가 변경될 때도 스크롤 (로딩 메시지 표시를 위해)
  useEffect(() => {
    if (loading) {
      scrollToBottom()
    }
  }, [loading])

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
  const handleEndSimulation = async (finalChatHistory?: ChatMessage[]) => {
    console.log('🔚 시뮬레이션 종료 처리 시작...')
    
    // 🚨 중요: 최신 chatHistory 사용 (우선순위: 파라미터 > ref > state)
    const latestChatHistory = finalChatHistory || chatHistoryRef.current || chatHistory
    console.log(`📊 대화 히스토리 길이: ${latestChatHistory.length}개 (파라미터 전달: ${!!finalChatHistory}, 상태 사용: ${!finalChatHistory})`)
    if (latestChatHistory.length > 0) {
      console.log(`📊 마지막 메시지: role='${latestChatHistory[latestChatHistory.length - 1].role}', text='${latestChatHistory[latestChatHistory.length - 1].text.substring(0, 50)}...'`)
    }
    
    // 🧪 테스트 모드: 현재 ragEvaluations 상태 확인 (중요!)
    const currentIsTestMode = simulationData?.is_test_mode || !!simulationData?.test_scenario
    const ragEvaluationsSnapshot = ragEvaluationsRef.current
    const ragSummarySnapshot = ragSummaryRef.current
    console.log('🧪 시뮬레이션 종료 시 RAG 평가 결과 상태:', {
      ragEvaluationsLength: ragEvaluationsSnapshot.length,
      ragEvaluations: ragEvaluationsSnapshot,
      hasRagSummary: !!ragSummarySnapshot,
      ragSummary: ragSummarySnapshot,
      isTestMode: currentIsTestMode,
      hasTestScenario: !!simulationData?.test_scenario
    })
    
    setIsGeneratingFeedback(true) // 피드백 생성 중 상태 설정
    setFeedbackProgress(0) // 진행률 초기화
    
    // 진행률 시뮬레이션 시작
    progressIntervalRef.current = setInterval(() => {
      setFeedbackProgress(prev => {
        if (prev >= 90) {
          // 90%에서 멈춤 (실제 완료까지 대기)
          return prev
        }
        // 점진적으로 증가 (0% → 90%)
        const increment = Math.random() * 5 + 2 // 2-7%씩 증가
        return Math.min(prev + increment, 90)
      })
    }, 300) // 300ms마다 업데이트
    
    try {
      let recordingId: string | null = null
      let feedbackId: number | null = null
      
      // 1. 먼저 녹화 중지 및 저장 (feedback_id 없이)
      if (videoRecorderRef.current && videoRecorderRef.current.state !== 'inactive') {
        console.log('📹 화면 녹화 중지 및 업로드 중...')
        
        // onstop 핸들러를 여기서 설정 (종료 시에만 실행되도록)
        const recorder = videoRecorderRef.current
        if (recorder) {
          await new Promise<void>((resolve) => {
            recorder.onstop = async () => {
              const videoBlob = new Blob(videoChunksRef.current, { 
                type: recorder.mimeType || 'video/webm' 
              })
              console.log('✅ 녹화 완료, 파일 크기:', videoBlob.size, 'bytes')
              
              // 녹화 파일 업로드 (feedback_id 없이 먼저 저장)
              if (videoBlob.size > 0) {
                const uploadResult = await uploadRecording(videoBlob, null)
                if (uploadResult?.id) {
                  recordingId = uploadResult.id
                  setCurrentRecordingId(recordingId as any) // UUID 문자열
                  console.log('📝 녹화 저장 완료, recording_id:', recordingId)
                } else {
                  console.warn('⚠️ 녹화 업로드 결과에 ID가 없습니다.')
                }
              } else {
                console.warn('⚠️ 녹화 파일 크기가 0입니다.')
              }
              
              // 녹화 데이터 초기화
              videoChunksRef.current = []
              resolve()
            }
            
            // 녹화 중지
            recorder.stop()
          })
        }
      } else {
        console.log('⚠️ 녹화가 시작되지 않았거나 이미 중지되었습니다.')
      }

      // 2. 피드백 생성 및 페이지 이동
      let feedbackData: any = null
      try {
        const startTime = Date.now()
        
        // 대화 기록이 충분한지 확인
        if (latestChatHistory.length >= 2) {
          // 시뮬레이션 경과 시간 계산 (초)
          const durationSeconds = simulationStartTime 
            ? Math.floor((Date.now() - simulationStartTime) / 1000)
            : null

          // 🚨 중요: 최신 chatHistory를 API 형식으로 변환 (모든 대화 포함)
          const conversationHistory = latestChatHistory.map((msg) => ({
            role: msg.role === 'user' ? 'employee' : 'customer',
            text: msg.text,
            timestamp: msg.timestamp.toISOString()
          }))
          
          console.log(`📤 피드백 생성 요청: conversation_history ${conversationHistory.length}개 메시지 전송`)
          if (conversationHistory.length > 0) {
            console.log(`   첫 메시지: role='${conversationHistory[0].role}', text='${conversationHistory[0].text.substring(0, 30)}...'`)
            console.log(`   마지막 메시지: role='${conversationHistory[conversationHistory.length - 1].role}', text='${conversationHistory[conversationHistory.length - 1].text.substring(0, 30)}...'`)
          }

          // 🚨 중요: 피드백 생성 전에 목표 달성 정보를 DB에 저장
          // 달성된 목표가 없어도 저장 (0/10도 유효한 데이터!)
          if (simulationData?.session_id) {
            const goals = simulationData?.situation?.goals || []
            
            // 목표가 있으면 저장 (달성 여부와 무관)
            if (goals.length > 0) {
              try {
                console.log('💾 목표 달성 정보 저장 중...')
                console.log(`   현재 달성: ${checkedGoals.size}/${goals.length}`)
                console.log(`   달성 목표 인덱스:`, Array.from(checkedGoals))
                console.log(`   달성 시점 Map 크기:`, goalAchievementTimes.size)
                
                // 달성 시점 정보를 포함한 목표 데이터 구성
                const achievedGoalsWithTimes = Array.from(checkedGoals).map(index => ({
                  index,
                  turn: goalAchievementTimes.get(index) || 0
                }))
                
                console.log(`   전송할 데이터:`, {
                  session_key: simulationData.session_id,
                  achieved_indices: Array.from(checkedGoals),
                  total_goals: goals.length,
                  achievement_details: achievedGoalsWithTimes
                })
                
                await api.post('/rag-simulation/update-goal-achievement', {
                  session_key: simulationData.session_id,
                  achieved_indices: Array.from(checkedGoals),
                  total_goals: goals.length,
                  achievement_details: achievedGoalsWithTimes  // 달성 시점 정보 포함
                })
                console.log('✅ 목표 달성 정보 저장 완료! (달성 시점 포함)')
              } catch (saveError) {
                console.error('⚠️ 목표 달성 정보 저장 실패:', saveError)
                // 저장 실패해도 평가는 계속 진행
              }
            }
          }

          // 피드백 생성 API 호출
          console.log('📊 피드백 생성 API 호출 중...')
          
          // 🧪 테스트 모드: RAG 평가 결과 포함
          // 여러 방법으로 테스트 모드 감지 (더 확실하게)
          const isTestModeFromData = simulationData?.is_test_mode === true
          const hasTestScenario = !!simulationData?.test_scenario
          const isTestModeFromState = ragEvaluationsSnapshot.length > 0 || ragSummarySnapshot !== null // RAG 평가 결과가 있으면 테스트 모드로 간주
          const isTestMode = isTestModeFromData || hasTestScenario || isTestModeFromState
          
          console.log('🧪 피드백 생성 전 RAG 평가 결과 상태:', {
            isTestModeFromData,
            hasTestScenario,
            isTestModeFromState,
            isTestMode,
            simulationDataKeys: simulationData ? Object.keys(simulationData) : [],
            hasIsTestMode: simulationData?.is_test_mode,
            ragEvaluationsLength: ragEvaluationsSnapshot.length,
            ragEvaluations: ragEvaluationsSnapshot,
            hasRagSummary: !!ragSummarySnapshot,
            ragSummary: ragSummarySnapshot
          })
          
          const requestPayload: any = {
            conversation_history: conversationHistory,
            persona: simulationData?.persona || {},
            situation: simulationData?.situation || {},
            duration_seconds: durationSeconds,
            session_key: simulationData?.session_id || null,  // 🚨 세션 키 전달 (목표 달성 정보 조회용)
            is_test_mode: isTestMode === true ? true : false  // 테스트 모드 여부 전달 (명시적으로 True/False 설정, undefined/null 방지)
          }
          
          // 🧪 테스트 모드이거나 RAG 평가 결과가 있으면 포함
          // 중요: ragEvaluations가 비어있어도 테스트 모드면 빈 배열이라도 전달 (디버깅용)
        if (isTestMode || ragEvaluationsSnapshot.length > 0) {
            console.log('🧪 피드백 요청 전 최종 확인:', {
              isTestMode,
            ragEvaluationsLength: ragEvaluationsSnapshot.length,
            ragEvaluations: ragEvaluationsSnapshot,
            hasRagSummary: !!ragSummarySnapshot
            })
            
          if (ragEvaluationsSnapshot.length > 0) {
            requestPayload.rag_evaluations = ragEvaluationsSnapshot
              // rag_summary가 없으면 자동 생성
            if (ragSummarySnapshot) {
              requestPayload.rag_summary = ragSummarySnapshot
              } else {
                // rag_evaluations에서 자동으로 summary 생성
              const employeeEvals = ragEvaluationsSnapshot.filter((e: any) => e.role === 'employee')
              const customerEvals = ragEvaluationsSnapshot.filter((e: any) => e.role === 'customer')
              const allScores = ragEvaluationsSnapshot.map((e: any) => e.evaluation?.score || 0)
                const avgScore = allScores.length > 0 ? allScores.reduce((a: number, b: number) => a + b, 0) / allScores.length : 0
                const empAvg = employeeEvals.length > 0 
                  ? employeeEvals.reduce((sum: number, e: any) => sum + (e.evaluation?.score || 0), 0) / employeeEvals.length 
                  : 0
                const custAvg = customerEvals.length > 0 
                  ? customerEvals.reduce((sum: number, e: any) => sum + (e.evaluation?.score || 0), 0) / customerEvals.length 
                  : 0
                requestPayload.rag_summary = {
                total_evaluations: ragEvaluationsSnapshot.length,
                  employee_count: employeeEvals.length,
                  customer_count: customerEvals.length,
                  employee_average: empAvg,
                  customer_average: custAvg,
                  average_score: avgScore
                }
              }
              console.log('🧪 ✅ 테스트 모드: RAG 평가 결과를 피드백 요청에 포함', {
              evaluations_count: ragEvaluationsSnapshot.length,
                summary: requestPayload.rag_summary,
              evaluations: ragEvaluationsSnapshot.map((e: any) => ({
                  turn: e.turn_index,
                  role: e.role,
                  score: e.evaluation?.score,
                  expected_product_code: e.expected_product_code
                }))
              })
            } else {
              console.warn('🧪 ⚠️ 테스트 모드로 감지되었지만 RAG 평가 결과가 없음!', {
                isTestMode,
                isTestModeFromData,
                isTestModeFromState,
                ragEvaluationsLength: ragEvaluations.length,
                ragEvaluations: ragEvaluations,
                simulationData: simulationData
              })
            }
          } else {
            console.log('🧪 일반 모드: RAG 평가 결과 포함 안 함', {
              isTestMode,
              ragEvaluationsLength: ragEvaluations.length
            })
          }
          
          console.log('📤 피드백 생성 요청:', {
            is_test_mode: requestPayload.is_test_mode,
            has_persona: !!requestPayload.persona,
            has_situation: !!requestPayload.situation,
            conversation_turns: requestPayload.conversation_history?.length || 0,
            has_rag_evaluations: !!requestPayload.rag_evaluations,
            rag_evaluations_length: requestPayload.rag_evaluations?.length || 0,
            has_rag_summary: !!requestPayload.rag_summary
          })
          
          const response = await api.post('/rag-simulation/generate-feedback', requestPayload)

          feedbackData = response.data.feedback
          feedbackId = feedbackData?.feedback_id || null
          setCurrentFeedbackId(feedbackId)
          
          console.log('✅ 피드백 생성 완료:', {
            feedback_id: feedbackId,
            is_test_mode: feedbackData?.is_test_mode,
            has_feedback_id: !!feedbackId
          })
          
          // 🧪 테스트 모드: RAG 평가 결과를 피드백 데이터에 포함 (백엔드에서 이미 포함되었지만 확인)
          // 테스트 모드이거나 RAG 평가 결과가 있으면 강제로 포함
          console.log('🧪 피드백 데이터 수신 후 RAG 평가 결과 확인:', {
            isTestMode,
          ragEvaluationsLength: ragEvaluationsSnapshot.length,
          hasFeedbackRagEvaluations: !!feedbackData.rag_evaluations,
          feedbackRagEvaluationsLength: feedbackData.rag_evaluations?.length || 0,
            feedbackDataKeys: Object.keys(feedbackData)
          })
          
        if (isTestMode || ragEvaluationsSnapshot.length > 0) {
            // 백엔드에서 이미 포함되었는지 확인
          if (!feedbackData.rag_evaluations && ragEvaluationsSnapshot.length > 0) {
            feedbackData.rag_evaluations = ragEvaluationsSnapshot
              // rag_summary가 없으면 자동 생성
            if (ragSummarySnapshot) {
              feedbackData.rag_summary = ragSummarySnapshot
            } else if (ragEvaluationsSnapshot.length > 0) {
              const employeeEvals = ragEvaluationsSnapshot.filter((e: any) => e.role === 'employee')
              const customerEvals = ragEvaluationsSnapshot.filter((e: any) => e.role === 'customer')
              const allScores = ragEvaluationsSnapshot.map((e: any) => e.evaluation?.score || 0)
                const avgScore = allScores.length > 0 ? allScores.reduce((a: number, b: number) => a + b, 0) / allScores.length : 0
                const empAvg = employeeEvals.length > 0 
                  ? employeeEvals.reduce((sum: number, e: any) => sum + (e.evaluation?.score || 0), 0) / employeeEvals.length 
                  : 0
                const custAvg = customerEvals.length > 0 
                  ? customerEvals.reduce((sum: number, e: any) => sum + (e.evaluation?.score || 0), 0) / customerEvals.length 
                  : 0
                feedbackData.rag_summary = {
                total_evaluations: ragEvaluationsSnapshot.length,
                  employee_count: employeeEvals.length,
                  customer_count: customerEvals.length,
                  employee_average: empAvg,
                  customer_average: custAvg,
                  average_score: avgScore
                }
              }
              console.log('🧪 ✅ RAG 평가 결과를 피드백 데이터에 추가 (프론트엔드에서)', {
              evaluations_count: ragEvaluationsSnapshot.length,
                summary: feedbackData.rag_summary
              })
            } else if (feedbackData.rag_evaluations) {
              console.log('🧪 ✅ RAG 평가 결과가 이미 피드백 데이터에 포함됨 (백엔드에서)', {
                evaluations_count: feedbackData.rag_evaluations.length,
                summary: feedbackData.rag_summary
              })
            } else {
              console.warn('🧪 ⚠️ RAG 평가 결과가 피드백 데이터에 없음', {
                isTestMode,
              hasRagEvaluations: ragEvaluationsSnapshot.length > 0,
              ragEvaluationsLength: ragEvaluationsSnapshot.length,
                feedbackDataKeys: Object.keys(feedbackData)
              })
            }
          }
          
          console.log('✅ 피드백 생성 완료!')
          console.log('   - feedback_id:', feedbackId)
          console.log('   - DB 저장:', feedbackId ? '성공' : '실패 (ID 없음)')
          console.log('   - is_test_mode:', feedbackData?.is_test_mode)
          console.log('   - 대시보드 조회 가능:', feedbackData?.is_test_mode === false ? '예 (일반 모드)' : feedbackData?.is_test_mode === true ? '아니오 (테스트 모드)' : '불명확')
          console.log('   - 목표 달성 정보:', feedbackData?.goalAchievement ? '있음' : '없음')
          
          // 🚨 중요: 저장 성공 및 대시보드 조회 가능 여부 확인
          if (feedbackId) {
            if (feedbackData?.is_test_mode === false) {
              console.log('   ✅ 일반 모드 평가서로 저장됨 - 대시보드에서 조회 가능합니다.')
            } else if (feedbackData?.is_test_mode === true) {
              console.log('   ⚠️ 테스트 모드 평가서로 저장됨 - 대시보드 일반 기록에는 표시되지 않습니다.')
            } else {
              console.warn('   ⚠️ is_test_mode 값이 명확하지 않음:', feedbackData?.is_test_mode)
            }
          } else {
            console.error('   ❌ 피드백 ID가 없습니다! DB 저장이 실패했을 수 있습니다.')
            alert('⚠️ 피드백이 생성되었지만 DB에 저장되지 않았을 수 있습니다.\n\n대시보드에서 기록을 확인할 수 없을 수 있습니다.')
          }
          
          // 3. 녹화의 feedback_id 업데이트 (JSON 파일 수정)
          if (recordingId && feedbackId) {
            try {
              await api.put(`/rag-simulation/recordings/${recordingId}/feedback`, { feedback_id: feedbackId })
              console.log('✅ 녹화와 피드백 연결 완료 (recording_id:', recordingId, ', feedback_id:', feedbackId, ')')
            } catch (error) {
              console.error('⚠️ 녹화 feedback_id 업데이트 실패:', error)
              // 실패해도 계속 진행
            }
          }
        }
      } catch (error: any) {
        console.error('❌ 피드백 생성 실패:', error)
        console.error('   에러 상세:', error?.response?.data || error?.message)
        // 피드백 생성 실패 시 사용자에게 알림
        const errorMessage = error?.response?.data?.detail || error?.message || '알 수 없는 오류'
        console.error('   최종 에러 메시지:', errorMessage)
        alert(`피드백 생성에 실패했습니다: ${errorMessage}\n\n대시보드에 기록이 저장되지 않을 수 있습니다.`)
        // 피드백 생성 실패해도 녹화는 저장됨
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

      // 피드백 페이지로 이동
      if (feedbackData) {
        // 🧪 피드백 데이터 전달 전 최종 확인
        console.log('📤 피드백 페이지로 이동:', {
          hasRagEvaluations: !!feedbackData.rag_evaluations,
          ragEvaluationsCount: feedbackData.rag_evaluations?.length || 0,
          hasRagSummary: !!feedbackData.rag_summary,
          feedbackDataKeys: Object.keys(feedbackData)
        })
        
        // 피드백 데이터가 있으면 바로 페이지로 이동
        setIsGeneratingFeedback(false) // 피드백 생성 완료
        navigate('/simulation-feedback', {
          state: { feedbackData }
        })
      } else {
        // 피드백이 없으면 handleGoToEvaluation 사용 (대화 기록이 부족한 경우)
        await handleGoToEvaluation()
      }

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
    setGoalAchievementTimes(new Map()) // 달성 시점 정보도 초기화
    setScenarioStep(0) // 🧪 시나리오 턴 초기화
    setIsStarted(false)
    setIsInitializing(true)
    setUserMessage('')
    setError('')
    setIsPlaying(false)
    setIsRecording(false)
    setSimulationStartTime(null) // 시작 시간 초기화
    
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

      // 시뮬레이션 경과 시간 계산 (초)
      const durationSeconds = simulationStartTime 
        ? Math.floor((Date.now() - simulationStartTime) / 1000)
        : null

      // 대화 히스토리를 API 형식으로 변환
      const conversationHistory = chatHistory.map((msg) => ({
        role: msg.role === 'user' ? 'employee' : 'customer',
        text: msg.text,
        timestamp: msg.timestamp.toISOString()
      }))

      // 🚨 중요: 피드백 생성 전에 목표 달성 정보를 DB에 저장
      // 달성된 목표가 없어도 저장 (0/10도 유효한 데이터!)
      if (simulationData?.session_id) {
        const goals = simulationData?.situation?.goals || []
        
        // 목표가 있으면 저장 (달성 여부와 무관)
        if (goals.length > 0) {
          try {
            console.log('💾 목표 달성 정보 저장 중...')
            console.log(`   현재 달성: ${checkedGoals.size}/${goals.length}`)
            console.log(`   달성 목표 인덱스:`, Array.from(checkedGoals))
            console.log(`   달성 시점 Map 크기:`, goalAchievementTimes.size)
            
            // 달성 시점 정보를 포함한 목표 데이터 구성
            const achievedGoalsWithTimes = Array.from(checkedGoals).map(index => ({
              index,
              turn: goalAchievementTimes.get(index) || 0
            }))
            
            console.log(`   전송할 데이터:`, {
              session_key: simulationData.session_id,
              achieved_indices: Array.from(checkedGoals),
              total_goals: goals.length,
              achievement_details: achievedGoalsWithTimes
            })
            
            await api.post('/rag-simulation/update-goal-achievement', {
              session_key: simulationData.session_id,
              achieved_indices: Array.from(checkedGoals),
              total_goals: goals.length,
              achievement_details: achievedGoalsWithTimes  // 달성 시점 정보 포함
            })
            console.log('✅ 목표 달성 정보 저장 완료! (달성 시점 포함)')
          } catch (saveError) {
            console.error('⚠️ 목표 달성 정보 저장 실패:', saveError)
            // 저장 실패해도 평가는 계속 진행
          }
        }
      }

      // 피드백 생성 API 호출
      console.log('📊 피드백 생성 API 호출 중...')

      const ragEvaluationsSnapshot = ragEvaluationsRef.current
      const ragSummarySnapshot = ragSummaryRef.current
      // 🧪 테스트 모드 감지: 여러 방법으로 확인
      const isTestModeFromData = simulationData?.is_test_mode === true
      const hasTestScenario = !!simulationData?.test_scenario
      const isTestMode = isTestModeFromData || hasTestScenario
      
      console.log('🧪 테스트 모드 감지 (강제 이동):', {
        isTestModeFromData,
        hasTestScenario,
        isTestMode,
        simulationDataKeys: simulationData ? Object.keys(simulationData) : [],
        simulationDataIsTestMode: simulationData?.is_test_mode
      })

      const requestPayload: any = {
        conversation_history: conversationHistory,
        persona: simulationData?.persona || {},
        situation: simulationData?.situation || {},
        duration_seconds: durationSeconds,
        session_key: simulationData?.session_id || null,  // 🚨 세션 키 전달 (목표 달성 정보 조회용)
        is_test_mode: isTestMode === true ? true : false  // 테스트 모드 여부 전달 (명시적으로 True/False 설정, undefined/null 방지)
      }

      if (isTestMode || ragEvaluationsSnapshot.length > 0) {
        console.log('🧪 평가 강제 이동 전 RAG 평가 상태:', {
          ragEvaluationsLength: ragEvaluationsSnapshot.length,
          hasRagSummary: !!ragSummarySnapshot
        })
        if (ragEvaluationsSnapshot.length > 0) {
          requestPayload.rag_evaluations = ragEvaluationsSnapshot
          requestPayload.rag_summary = ragSummarySnapshot ?? computeRagSummaryFromEvaluations(ragEvaluationsSnapshot)
        }
      }

      console.log('📤 피드백 생성 요청 (강제 이동):', {
        is_test_mode: requestPayload.is_test_mode,
        has_persona: !!requestPayload.persona,
        has_situation: !!requestPayload.situation,
        conversation_turns: requestPayload.conversation_history?.length || 0
      })
      
      const response = await api.post('/rag-simulation/generate-feedback', requestPayload)

      const feedbackData = response.data.feedback
      const feedbackId = feedbackData?.feedback_id || null
      setCurrentFeedbackId(feedbackId)
      const elapsedTime = Date.now() - startTime

      console.log('✅ 피드백 생성 완료!')
      console.log('   - feedback_id:', feedbackId)
      console.log('   - is_test_mode:', feedbackData?.is_test_mode)
      console.log('   - DB 저장:', feedbackId ? '성공' : '실패 (ID 없음)')
      console.log('   - 목표 달성 정보:', feedbackData?.goalAchievement ? '있음' : '없음')

      // 진행률 100%로 설정
      setFeedbackProgress(100)
      
      // 진행률 시뮬레이션 정리
      if (progressIntervalRef.current !== null) {
        clearInterval(progressIntervalRef.current)
        progressIntervalRef.current = null
      }

      // 🔥 평가서 생성이 빠르면(1초 이내) 로딩 화면 건너뛰기
      if (elapsedTime < 1000) {
        // 바로 피드백 페이지로 이동
        navigate('/simulation-feedback', {
          state: { feedbackData }
        })
      } else {
        // 로딩 화면을 잠시 보여준 후 이동
        setTimeout(() => {
          navigate('/simulation-feedback', {
            state: { feedbackData }
          })
        }, 500) // 100% 표시를 잠시 보여주기
      }

    } catch (error: any) {
      console.error('❌ 피드백 생성 실패:', error)
      console.error('   에러 상세:', error?.response?.data || error?.message)
      console.error('   스택 트레이스:', error?.stack)
      // 진행률 시뮬레이션 정리
      if (progressIntervalRef.current !== null) {
        clearInterval(progressIntervalRef.current)
        progressIntervalRef.current = null
      }
      setIsGeneratingFeedback(false)
      setFeedbackProgress(0)
      const errorMessage = error?.response?.data?.detail || error?.message || '알 수 없는 오류'
      console.error('   최종 에러 메시지:', errorMessage)
      setError(`피드백 생성에 실패했습니다: ${errorMessage}\n\n대시보드에 기록이 저장되지 않을 수 있습니다.`)
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
      const newAchievedIndices = new Set<number>(achievedIndicesArray)
      
      // 🚨 중요: 기존에 달성된 목표와 새로 달성된 목표를 병합 (한번 달성되면 계속 유지)
      const mergedAchievedIndices = new Set<number>(checkedGoals)
      for (const goalIndex of newAchievedIndices) {
        mergedAchievedIndices.add(goalIndex)
      }
      
      console.log(`📊 목표 달성 상태: 기존 ${checkedGoals.size}개 + 새로 ${newAchievedIndices.size}개 = 총 ${mergedAchievedIndices.size}개`)
      
      // 🚨 새로 달성된 목표의 달성 시점 기록
      const newAchievementTimes = new Map(goalAchievementTimes)
      const currentTurnNumber = Math.floor(history.length / 2) // 턴 번호 (employee + customer = 1턴)
      
      for (const goalIndex of newAchievedIndices) {
        // 처음 달성된 목표만 시점 기록 (이미 기록된 건 유지)
        if (!newAchievementTimes.has(goalIndex)) {
          newAchievementTimes.set(goalIndex, currentTurnNumber)
          console.log(`🎯 목표 ${goalIndex} 달성! (턴 ${currentTurnNumber})`)
        }
      }
      
      // 병합된 목표 달성 상태로 업데이트 (기존 달성 목표 유지)
      setCheckedGoals(mergedAchievedIndices)
      setGoalAchievementTimes(newAchievementTimes)
      
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

  // 녹화 파일 업로드 (파일 시스템 + JSON 메타데이터 방식)
  const uploadRecording = async (videoBlob: Blob, feedbackId: number | null = null) => {
    try {
      console.log('📤 녹화 파일 업로드 시작...', { 
        feedbackId, 
        blobSize: videoBlob.size,
        blobType: videoBlob.type 
      })
      
      if (videoBlob.size === 0) {
        console.error('❌ 녹화 파일 크기가 0입니다.')
        return null
      }
      
      // 메타데이터 생성
      const meta = {
        title: "시뮬레이션 녹화",
        category: simulationData?.situation?.category || "기타",
        persona_id: simulationData?.persona?.id || null,
        situation_id: simulationData?.situation?.id || null,
        feedback_id: feedbackId,
        started_at: simulationStartTime ? new Date(simulationStartTime).toISOString() : new Date().toISOString(),
        ended_at: new Date().toISOString(),
        user_notes: "",
        simulation_id: simulationData?.session_id || Date.now().toString()
      }
      
      console.log('📋 메타데이터:', meta)
      
      const formData = new FormData()
      const file = new File([videoBlob], `recording_${Date.now()}.webm`, { type: "video/webm" })
      formData.append('file', file)
      formData.append('meta', JSON.stringify(meta))
      
      console.log('📦 FormData 생성 완료, 파일명:', file.name, '크기:', file.size)

      // FormData는 브라우저가 자동으로 Content-Type을 설정하므로 헤더 제거 (boundary 자동 설정)
      const response = await api.post('/rag-simulation/upload-recording', formData, {
        headers: {
          'Content-Type': undefined  // FormData 사용 시 자동 설정되도록
        },
        onUploadProgress: (progressEvent) => {
          if (progressEvent.total) {
            const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total)
            console.log(`📊 업로드 진행률: ${percentCompleted}%`)
          }
        }
      })

      console.log('✅ 녹화 파일 업로드 완료:', response.data)
      
      // 녹화 ID 저장
      if (response.data?.id) {
        setCurrentRecordingId(response.data.id)
        console.log('📝 녹화 ID 저장:', response.data.id)
      } else {
        console.warn('⚠️ 응답에 id가 없습니다:', response.data)
      }
      
      // 사용자에게 알림 (선택사항)
      if (response.data?.video_url) {
        console.log('📹 녹화 파일 URL:', response.data.video_url)
      }
      
      return response.data
    } catch (error: any) {
      console.error('❌ 녹화 파일 업로드 실패:', error)
      console.error('❌ 에러 상세:', error.response?.data || error.message)
      // 업로드 실패해도 시뮬레이션은 계속 진행
      return null
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

        // onstop 핸들러는 handleEndSimulation에서 설정하므로 여기서는 설정하지 않음
        // 녹화는 시작만 하고, 종료 시에만 저장됨

        videoRecorderRef.current.start(1000) // 1초마다 데이터 수집
        console.log('✅ 화면 녹화 시작됨 (녹음 시작 버튼 클릭 시)')
      }

      setIsRecording(true)
      setSubtitle('말씀해주세요...')
    } catch (error) {
      console.error('녹음 시작 실패:', error)
      setError('마이크 접근 권한이 필요합니다.')
    }
  }

  // 음성 녹음 중지 (화면 녹화는 계속 진행 - 최종 종료 시에만 중지)
  const stopRecording = () => {
    // 오디오 녹음만 중지 (STT 처리를 위해)
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop()
      setIsRecording(false)
      setSubtitle('음성을 처리 중입니다...')
      console.log('🎤 오디오 녹음만 중지 (화면 녹화는 계속 진행)')
    }
    
    // 화면 녹화는 중지하지 않음 - 최종 종료 시에만 중지됨
    // if (videoRecorderRef.current && videoRecorderRef.current.state !== 'inactive') {
    //   console.log('🛑 화면 녹화 중지 중...')
    //   videoRecorderRef.current.stop()
    // }
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
      // 🚨 중요: simulationDataRef.current를 사용하여 최신 상태 참조 (클로저 문제 해결)
      const currentSimulationData = simulationDataRef.current || simulationData
      const currentRagEvaluations = ragEvaluationsRef.current || []
      
      const sessionDataWithHistory = {
        ...currentSimulationData,
        conversation_history: chatHistory.map(msg => ({
          role: msg.role === 'user' ? 'employee' : 'customer',
          text: msg.text,
          timestamp: msg.timestamp.toISOString()
        })),
        achieved_goals: Array.from(checkedGoals), // 달성된 목표 포함
        offtopic_count: offtopicCount, // 프론트엔드 이탈 카운터 사용
        current_turn_index: currentTurnIndex, // 🧪 테스트 모드: 현재 턴 인덱스 전달
        stt_evaluations: [], // 🧪 테스트 모드: STT 평가 결과
        rag_evaluations: currentRagEvaluations,
        rag_summary: ragSummaryRef.current || null
      }
      
      // 🧪 테스트 모드 디버깅
      const isTestModeForDebug = currentSimulationData?.is_test_mode || !!currentSimulationData?.test_scenario
      if (isTestModeForDebug) {
        console.log('🧪 테스트 모드 세션 데이터 전송:', {
          is_test_mode: sessionDataWithHistory.is_test_mode,
          test_scenario: !!sessionDataWithHistory.test_scenario,
          current_turn_index: sessionDataWithHistory.current_turn_index,
          rag_evaluations_count: currentRagEvaluations.length,
          rag_evaluations_sample: currentRagEvaluations.slice(0, 1)
        })
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
      let ragCollectedForThisResponse = false
      
      // 🔥 욕설 감지 (이탈 감지보다 우선)
      if (transcribed_text && !isEnding) {
        const hasProfanity = containsProfanity(transcribed_text)
        if (hasProfanity) {
          console.log('⚠️ 욕설 감지:', transcribed_text)
          const newCount = offtopicCount + 1
          setOfftopicCount(newCount)
          
          // 욕설 사용 시 즉시 에러 메시지 표시
          setError('은행 신입사원 온보딩입니다. 관련된 답변만 하십시오.')
          setTimeout(() => setError(''), 3000)
          console.log('⚠️ 욕설 감지:', transcribed_text, `(이탈 횟수: ${newCount}/3)`)
          
          // 욕설이어도 사용자 메시지는 대화에 추가
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
            handleEndSimulation(chatHistoryRef.current) // 🔧 최신 히스토리 전달
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
          if (isTestMode) {
            const collected = collectRagDataFromResponse(response.data, {
              context: 'audio-end-keyword',
              turnIndexHint: currentTurnIndex,
              nextTurnRole: response.data.next_turn_role
            })
            ragCollectedForThisResponse = ragCollectedForThisResponse || collected
            if (!collected) {
              console.warn('🧪 ⚠️ 종료 표현 감지 시 RAG 평가 결과를 수집하지 못했습니다.', {
                responseKeys: Object.keys(response.data || {}),
                currentTurnIndex
              })
            }
          }
          setIsEnding(true) // 종료 중 상태로 설정
          // 사용자 메시지만 추가하고 고객 응답은 받지 않음
          let updatedChatHistory: ChatMessage[] = [...chatHistory]
          updatedChatHistory.push({
            id: Date.now().toString(),
            role: 'user',
            text: transcribed_text,
            timestamp: new Date()
          })
          updateChatHistory(updatedChatHistory) // 🔧 ref와 state 동시 업데이트
          // 바로 평가서 생성 시작
          setIsGeneratingFeedback(true)
          handleEndSimulation(updatedChatHistory) // 🔧 최신 히스토리 전달
          setLoading(false)
          return
        }
      }
      
      // 백엔드의 end_signal 확인
      if (end_signal === true && !isEnding) {
        isEndMessage = true
        console.log('🔚 종료 신호 수신 (백엔드 LLM 판단):', transcribed_text)
        
        // 🧪 테스트 모드: 마지막 응답에서 RAG 평가 결과 수집 (중요!)
        if (isTestMode) {
          console.log('🧪 종료 신호 수신: 마지막 RAG 평가 결과 수집')
          const collected = collectRagDataFromResponse(response.data, {
            context: 'audio-end-signal',
            turnIndexHint: currentTurnIndex,
            nextTurnRole: response.data.next_turn_role
          })
          ragCollectedForThisResponse = ragCollectedForThisResponse || collected
          if (!collected && response.data.test_completed) {
            console.warn('🧪 ⚠️ test_completed이지만 RAG 평가 결과가 없음:', {
              hasRagEvaluations: !!response.data.rag_evaluations,
              hasRagSummary: !!response.data.rag_summary,
              responseKeys: Object.keys(response.data)
            })
          }
        }
        
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
          handleEndSimulation(chatHistoryRef.current) // 🔧 최신 히스토리 전달
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
      
      // 🧪 테스트 모드: 백엔드 응답 전체 확인 (디버깅)
      if (response.data.is_test_mode || simulationData?.is_test_mode || simulationData?.test_scenario) {
        console.log('🧪 ===== 백엔드 응답 전체 확인 (테스트 모드) =====')
        console.log('🧪 response.data.keys:', Object.keys(response.data))
        console.log('🧪 response.data.rag_evaluations:', response.data.rag_evaluations)
        console.log('🧪 response.data.rag_evaluation:', response.data.rag_evaluation)
        console.log('🧪 response.data.rag_evaluation_customer:', response.data.rag_evaluation_customer)
        console.log('🧪 response.data.rag_summary:', response.data.rag_summary)
        console.log('🧪 response.data.current_turn_index:', response.data.current_turn_index)
        console.log('🧪 response.data.is_test_mode:', response.data.is_test_mode)
      }

      // 🧪 테스트 모드: expected_text 표시 및 current_turn_index 업데이트
      const isTestModeForExpectedText = simulationData?.is_test_mode || !!simulationData?.test_scenario
      if (isTestModeForExpectedText) {
        // 백엔드에서 next_turn_expected_text를 제공하면 사용
        if (response.data.next_turn_expected_text) {
          setCurrentExpectedText(response.data.next_turn_expected_text)
          console.log('🧪 테스트 모드: 다음 턴 expected_text 수신:', response.data.next_turn_expected_text)
        } else {
          // 백엔드에서 제공하지 않으면 test_scenario에서 가져오기
          const testScenario = simulationData?.test_scenario
          if (testScenario?.turns) {
            const nextTurnIndex = response.data.current_turn_index !== undefined 
              ? response.data.current_turn_index 
              : currentTurnIndex + 1
            
            if (nextTurnIndex < testScenario.turns.length) {
              const nextTurn = testScenario.turns[nextTurnIndex]
              if (nextTurn?.role === 'employee' && nextTurn?.expected_text) {
                setCurrentExpectedText(nextTurn.expected_text)
                setCurrentTurnIndex(nextTurnIndex)
              } else {
                setCurrentExpectedText('')
              }
            } else {
              setCurrentExpectedText('')
            }
          }
        }
        
        // current_turn_index 업데이트
        if (response.data.current_turn_index !== undefined) {
          setCurrentTurnIndex(response.data.current_turn_index)
        }
      }
      
      // RAG 데이터 수집 (일반 모드와 동일)
      if (!ragCollectedForThisResponse) {
        const collected = collectRagDataFromResponse(response.data, {
          context: 'audio-turn',
          turnIndexHint: currentTurnIndex,
          nextTurnRole: response.data.next_turn_role
        })
        ragCollectedForThisResponse = ragCollectedForThisResponse || collected
      }

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
      
      // 🧪 테스트 모드: 백엔드의 conversation_history를 기반으로 메시지 동기화
      const isTestModeLocal = simulationData?.is_test_mode || !!simulationData?.test_scenario
      
      console.log('🔥 ========== 메시지 추가 로직 진입 ==========')
      console.log('🔥 isTestModeLocal:', isTestModeLocal)
      console.log('🔥 simulationData?.is_test_mode:', simulationData?.is_test_mode)
      console.log('🔥 simulationData?.test_scenario:', !!simulationData?.test_scenario)
      console.log('🔥 response.data.conversation_history 존재:', !!response.data.conversation_history)
      console.log('🔥 response.data.conversation_history 길이:', response.data.conversation_history?.length || 0)
      console.log('🔥 transcribed_text:', transcribed_text)
      console.log('🔥 customer_response:', customer_response)
      
      // 🧪 테스트 모드: 시나리오 기반 대화 처리
      if (isTestModeLocal && response.data.conversation_history) {
        console.log('🔥 ✅ 테스트 모드 분기 진입: conversation_history 사용')
        // 🧪 백엔드의 conversation_history를 프론트엔드 형식으로 변환
        // 백엔드: role='employee' 또는 'customer'
        // 프론트엔드: role='user' (employee) 또는 'customer'
        const backendHistory = response.data.conversation_history || []
        console.log('🧪 ========== 테스트 모드: 백엔드 conversation_history 동기화 시작 ==========')
        console.log('🧪 백엔드 응답 conversation_history 길이:', backendHistory.length, '개 메시지')
        console.log('🧪 백엔드 응답 전체 conversation_history:', JSON.stringify(backendHistory, null, 2))
        
        // 🧪 백엔드 히스토리를 프론트엔드 형식으로 변환하여 완전히 교체
        updatedChatHistory = backendHistory.map((msg: any, index: number) => {
          // 백엔드 role을 프론트엔드 role로 매핑
          // 백엔드: 'employee' 또는 'customer'
          // 프론트엔드: 'user' (신입사원) 또는 'customer' (고객)
          let frontendRole: 'user' | 'customer'
          
          // role 확인 및 매핑 (엄격하게)
          const backendRole = String(msg.role || msg.role_name || '').trim()
          const msgText = String(msg.text || msg.message || '')
          
          console.log(`🧪   [${index}] 원본: role='${backendRole}' (원본 타입: ${typeof msg.role}), text='${msgText.substring(0, 40)}...'`)
          
          // 🧪 role 매핑 (엄격하게 'employee' 또는 'customer'만 허용)
          if (backendRole === 'employee') {
            frontendRole = 'user'  // 신입사원 (파란색, 오른쪽)
            console.log(`🧪   ✅ [${index}] 'employee' → 'user' (🔵 파란색, 오른쪽)`)
          } else if (backendRole === 'customer') {
            frontendRole = 'customer'  // 고객 (초록색, 왼쪽)
            console.log(`🧪   ✅ [${index}] 'customer' → 'customer' (🟢 초록색, 왼쪽)`)
          } else {
            // 🧪 role이 없거나 잘못된 경우 - 인덱스 기반으로 강제 추정
            console.error(`🧪 ❌ [${index}] role이 잘못됨: '${backendRole}', text='${msgText.substring(0, 30)}...'`)
            console.error(`🧪 ❌ 원본 메시지 객체:`, JSON.stringify(msg, null, 2))
            
            // 🧪 인덱스 기반으로 강제 추정 (짝수 인덱스는 직원, 홀수 인덱스는 고객)
            if (index % 2 === 0) {
              frontendRole = 'user'  // 짝수 인덱스는 직원 (Turn 0, 2, 4, 6...)
              console.error(`🧪 ⚠️ [${index}] 인덱스 기반 추정: 짝수 → 'user' (🔵 파란색)`)
            } else {
              frontendRole = 'customer'  // 홀수 인덱스는 고객 (Turn 1, 3, 5, 7...)
              console.error(`🧪 ⚠️ [${index}] 인덱스 기반 추정: 홀수 → 'customer' (🟢 초록색)`)
            }
          }
          
          // 🧪 마지막 고객 메시지에만 customer_audio 할당 (다시 듣기 버튼을 위해 저장)
          const isLastCustomerMessage = frontendRole === 'customer' && 
                                        index === backendHistory.length - 1 && 
                                        response.data.customer_audio
          
          const chatMessage: ChatMessage = {
            id: `test-${index}-${Date.now()}-${Math.random()}`,
            role: frontendRole,  // 🧪 강제로 'user' 또는 'customer' 설정
            text: msgText,
            audio: isLastCustomerMessage ? response.data.customer_audio : undefined,
            timestamp: msg.timestamp ? new Date(msg.timestamp) : new Date()
          }
          
          console.log(`🧪   [${index}] 최종 ChatMessage: role='${chatMessage.role}', text='${chatMessage.text.substring(0, 30)}...', audio=${!!chatMessage.audio}`)
          
          return chatMessage
        })
        
        console.log('🧪 ========== 프론트엔드로 변환된 히스토리 ==========')
        console.log('🧪 총 메시지 수:', updatedChatHistory.length)
        updatedChatHistory.forEach((msg, idx) => {
          const roleLabel = msg.role === 'user' ? '신입사원 (나)' : '고객'
          const colorLabel = msg.role === 'user' ? '🔵 파란색 (오른쪽)' : '🟢 초록색 (왼쪽)'
          const alignLabel = msg.role === 'user' ? '→ 오른쪽' : '← 왼쪽'
          console.log(`🧪   [${idx}] role='${msg.role}' (${roleLabel}, ${colorLabel}, ${alignLabel}): ${msg.text.substring(0, 50)}...`)
        })
        
        // 🧪 검증: role이 올바르게 매핑되었는지 확인
        const userMessages = updatedChatHistory.filter(msg => msg.role === 'user')
        const customerMessages = updatedChatHistory.filter(msg => msg.role === 'customer')
        console.log(`🧪 검증 결과: 신입사원(🔵) ${userMessages.length}개, 고객(🟢) ${customerMessages.length}개`)
        
        if (userMessages.length === 0 && updatedChatHistory.length > 0) {
          console.error('🧪 ❌❌❌ 심각한 오류: 신입사원 메시지가 없습니다! 모든 메시지가 고객으로 표시되고 있습니다.')
          console.error('🧪 ❌ 백엔드 응답을 확인하세요:', JSON.stringify(response.data, null, 2))
        }
        
        // 🧪 추가 검증: role이 정확히 'user' 또는 'customer'인지 확인
        const invalidRoles = updatedChatHistory.filter(msg => msg.role !== 'user' && msg.role !== 'customer')
        if (invalidRoles.length > 0) {
          console.error('🧪 ❌❌❌ 심각한 오류: 잘못된 role이 있습니다:', invalidRoles)
        }
        
        console.log('🧪 ========== conversation_history 동기화 완료 ==========')
      } else {
        console.log('🔥 ⚠️ 일반 모드 분기 진입 (또는 테스트 모드인데 conversation_history 없음)')
        console.log('🔥   isTestModeLocal:', isTestModeLocal)
        console.log('🔥   response.data.conversation_history:', response.data.conversation_history)
        
        // 일반 모드: 기존 로직 유지
        // 사용자 메시지 추가
        if (transcribed_text) {
          console.log('🔥 ✅ 사용자 메시지 추가: role="user", text="' + transcribed_text.substring(0, 30) + '..."')
          const traineeMessage: ChatMessage = {
            id: Date.now().toString(),
            role: 'user',
            text: transcribed_text,
            timestamp: new Date()
          }
          updatedChatHistory.push(traineeMessage)
          
          // 🧪 테스트 모드: 백엔드에서 고객 응답이 자동으로 생성되므로 프론트엔드에서 추가하지 않음
          // 백엔드에서 customer_response와 customer_audio를 받아서 처리함
        } else {
          console.log('🔥 ⚠️ transcribed_text가 없어서 사용자 메시지 추가 안 함')
        }
        
        // 고객 응답 추가
        if (customer_response && !isEnding) {
          // customer_response에서 불필요한 텍스트 제거 (speak, 말하기 등)
          const cleanResponse = customer_response.replace(/\b(speak|말하기|말해|말씀)\b/gi, '').trim()
          
          console.log('🔥 ✅ 고객 응답 추가: role="customer", text="' + cleanResponse.substring(0, 30) + '..."')
          updatedChatHistory.push({
            id: (Date.now() + 1).toString(),
            role: 'customer',
            text: cleanResponse, // 정리된 텍스트 저장
            audio: customer_audio,
            timestamp: new Date()
          })
          
          // 🧪 테스트 모드가 아닐 때만 아바타 설정 (테스트 모드에서는 중복 재생 방지)
          if (customer_audio && !isTestModeLocal) {
            setAudio({
              audioUrl: customer_audio,
              text: cleanResponse,
              mouthCues: [] // TODO: Rhubarb로 생성
            })
          }
        } else {
          console.log('🔥 ⚠️ customer_response가 없거나 isEnding=true여서 고객 응답 추가 안 함')
          console.log('🔥   customer_response:', customer_response)
          console.log('🔥   isEnding:', isEnding)
        }
      }
      
      console.log('🔥 ========== 메시지 추가 로직 완료 ==========')
      console.log('🔥 최종 updatedChatHistory 길이:', updatedChatHistory.length)
      updatedChatHistory.forEach((msg, idx) => {
        console.log(`🔥   [${idx}] role='${msg.role}', text='${msg.text.substring(0, 30)}...'`)
      })

      // 🧪 테스트 모드: setChatHistory 호출 전 최종 검증
      if (isTestModeLocal) {
        console.log('🧪 ========== setChatHistory 호출 전 최종 검증 ==========')
        console.log('🧪 updatedChatHistory 길이:', updatedChatHistory.length)
        updatedChatHistory.forEach((msg, idx) => {
          const roleIcon = msg.role === 'user' ? '🔵' : '🟢'
          console.log(`🧪   [${idx}] ${roleIcon} role='${msg.role}', text='${msg.text.substring(0, 30)}...'`)
        })
        const userCount = updatedChatHistory.filter(m => m.role === 'user').length
        const customerCount = updatedChatHistory.filter(m => m.role === 'customer').length
        console.log(`🧪 최종 검증: user(🔵)=${userCount}개, customer(🟢)=${customerCount}개`)
        if (userCount === 0 && updatedChatHistory.length > 0) {
          console.error('🧪 ❌❌❌ 심각: user 메시지가 0개입니다!')
        }
        console.log('🧪 ================================================')
      }
      
      updateChatHistory(updatedChatHistory) // 🔧 ref와 state 동시 업데이트
      
      // 🧪 테스트 모드: setChatHistory 호출 후 확인
      if (isTestModeLocal) {
        console.log('🧪 ✅ updateChatHistory 호출 완료. ref와 state가 동시에 업데이트됩니다.')
      }

      // 사용자 입력 필드 초기화
      setUserMessage('')

      // 🔥 종료 중이면 고객 음성 재생하지 않음
      if (isEnding) {
        setLoading(false)
        return
      }

      // 🧪 테스트 모드: 고객 응답 TTS 자동 재생 (한 번만 재생)
      // ✅ 메시지에 audio는 이미 저장되어 있으므로, 여기서는 자동 재생만 수행
      // ✅ 다시 듣기 버튼은 메시지의 audio를 사용하여 작동함
      // ✅ setAudio는 호출하지 않음 (중복 재생 방지)
      if (isTestModeLocal && customer_audio) {
        try {
          // customer_response에서 불필요한 텍스트 제거 (speak, 말하기 등)
          const cleanResponse = (customer_response || '').replace(/\b(speak|말하기|말해|말씀)\b/gi, '').trim()
          
          console.log('🧪 ========== 테스트 모드: 고객 응답 TTS 자동 재생 시작 (한 번만) ==========')
          console.log('🧪 customer_response (원본):', customer_response)
          console.log('🧪 customer_response (정리):', cleanResponse)
          console.log('🧪 customer_audio 존재:', !!customer_audio)
          console.log('🧪 ✅ 메시지에 audio가 저장되어 있어 다시 듣기 버튼도 작동합니다')
          
          // 오디오만 재생 (setAudio 호출하지 않음 - 중복 재생 방지)
          console.log('🎵 테스트 모드 오디오 자동 재생 시도 (한 번만)...')
          await playFromAnyAudioPayload(customer_audio, 'audio/mpeg')
          setIsPlaying(true)
          setError('')
          console.log('🧪 ✅ 테스트 모드: 고객 응답 TTS 자동 재생 시작됨 (다시 듣기 버튼도 사용 가능)')
          
          // 종료 플래그가 설정되어 있으면 오디오 재생 후 시뮬레이션 종료
          if (isEndMessage) {
            const responseLength = cleanResponse?.length || customer_response?.length || 0
            const estimatedAudioDuration = Math.max(2000, Math.min(responseLength * 100, 5000))
            setTimeout(() => {
              console.log('🔚 대화 종료: 고객 응답 재생 완료 후 종료')
              setIsGeneratingFeedback(true)
              handleEndSimulation(chatHistoryRef.current)
            }, estimatedAudioDuration)
          }
        } catch (audioError) {
          console.error('🧪 ❌ 테스트 모드: 고객 응답 TTS 재생 실패:', audioError)
          setError('오디오 재생에 실패했습니다.')
          
          // 오디오 재생 실패 시에도 종료 플래그가 설정되어 있으면 종료
          if (isEndMessage) {
            setTimeout(() => {
              console.log('🔚 대화 종료: 오디오 재생 실패로 인한 종료')
              setIsGeneratingFeedback(true)
              handleEndSimulation(chatHistoryRef.current)
            }, 1000)
          }
        }
      } else if (isTestModeLocal) {
        console.log('🧪 ⚠️ 테스트 모드인데 customer_audio가 없습니다:')
        console.log('🧪   customer_audio:', !!customer_audio)
        console.log('🧪   customer_response:', customer_response)
        
        // 오디오가 없을 때도 종료 플래그가 설정되어 있으면 종료
        if (isEndMessage) {
          setTimeout(() => {
            console.log('🔚 대화 종료: 오디오 없음으로 인한 종료')
            setIsGeneratingFeedback(true)
            handleEndSimulation(chatHistoryRef.current)
          }, 1000)
        }
      }
      
      // 일반 모드: 고객 음성 재생
      if (!isTestModeLocal && customer_audio) {
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
              handleEndSimulation(chatHistoryRef.current) // 🔧 최신 히스토리 전달
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
              handleEndSimulation(chatHistoryRef.current) // 🔧 최신 히스토리 전달
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
            handleEndSimulation(chatHistoryRef.current) // 🔧 최신 히스토리 전달
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
      
      // 🔥 욕설 감지 (이탈 감지보다 우선)
      if (userMessage && !isEnding) {
        const hasProfanity = containsProfanity(userMessage)
        if (hasProfanity) {
          console.log('⚠️ 욕설 감지 (전송 전):', userMessage)
          const newCount = offtopicCount + 1
          setOfftopicCount(newCount)
          
          // 욕설 사용 시 즉시 에러 메시지 표시
          setError('은행 신입사원 온보딩입니다. 관련된 답변만 하십시오.')
          setTimeout(() => setError(''), 3000)
          console.log('⚠️ 욕설 감지 (프론트엔드):', userMessage, `(이탈 횟수: ${newCount}/3)`)
          
          // 욕설이어도 사용자 메시지는 대화에 추가
          let updatedChatHistory: ChatMessage[] = [...chatHistory]
          updatedChatHistory.push({
            id: Date.now().toString(),
            role: 'user',
            text: userMessage,
            timestamp: new Date()
          })
          setChatHistory(updatedChatHistory)
          setUserMessage('')
          setLoading(false)
          return // 백엔드로 전송하지 않음
        }
      }

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
            handleEndSimulation(chatHistoryRef.current) // 🔧 최신 히스토리 전달
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
        offtopic_count: offtopicCount, // 프론트엔드 이탈 카운터 사용
        current_turn_index: currentTurnIndex, // 🧪 테스트 모드: 현재 턴 인덱스 전달
        stt_evaluations: [],
        rag_evaluations: ragEvaluationsRef.current || [],
        rag_summary: ragSummaryRef.current || null
      }
      
      // 🧪 테스트 모드 디버깅
      const isTestModeForDebug = simulationData?.is_test_mode || !!simulationData?.test_scenario
      if (isTestModeForDebug) {
        console.log('🧪 테스트 모드 텍스트 입력 - 세션 데이터:', {
          is_test_mode: sessionDataWithHistory.is_test_mode,
          test_scenario: !!sessionDataWithHistory.test_scenario,
          current_turn_index: sessionDataWithHistory.current_turn_index,
          currentExpectedText: currentExpectedText
        })
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
      let ragCollectedForThisResponse = false
      
      // 🔥 프론트엔드에서도 이탈 감지 (백엔드와 이중 체크) - 이미 전송 전에 체크했으므로 여기서는 백엔드 응답만 처리
      
      // 🔥 끝맺음 용어가 먼저 감지되면 바로 종료 (고객 응답 받지 않음)
      let isEndMessage = false
      if (userMessage && !isEnding) {
        isEndMessage = checkConversationEnd(userMessage)
        if (isEndMessage) {
          console.log('🔚 종료 표현 감지 (끝맺음 용어):', userMessage)
          if (isTestMode) {
            const collected = collectRagDataFromResponse(response.data, {
              context: 'text-end-keyword',
              turnIndexHint: currentTurnIndex,
              nextTurnRole: response.data.next_turn_role
            })
            ragCollectedForThisResponse = ragCollectedForThisResponse || collected
            if (!collected) {
              console.warn('🧪 ⚠️ 종료 표현 감지 (텍스트) 시 RAG 평가 결과를 수집하지 못했습니다.', {
                responseKeys: Object.keys(response.data || {}),
                currentTurnIndex
              })
            }
          }
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
          handleEndSimulation(updatedChatHistory) // 🚨 최신 chatHistory 전달
          setLoading(false)
          return
        }
      }
      
      // 백엔드의 end_signal 확인
      if (end_signal === true && !isEnding) {
        isEndMessage = true
        console.log('🔚 종료 신호 수신 (백엔드 LLM 판단):', userMessage)
        
        // 🧪 테스트 모드: 마지막 응답에서 RAG 평가 결과 수집 (중요!)
        if (isTestMode) {
          console.log('🧪 종료 신호 수신 (텍스트): 마지막 RAG 평가 결과 수집')
          const collected = collectRagDataFromResponse(response.data, {
            context: 'text-end-signal',
            turnIndexHint: currentTurnIndex,
            nextTurnRole: response.data.next_turn_role
          })
          ragCollectedForThisResponse = ragCollectedForThisResponse || collected
          if (!collected && response.data.test_completed) {
            console.warn('🧪 ⚠️ test_completed이지만 RAG 평가 결과가 없음 (텍스트):', {
              hasRagEvaluations: !!response.data.rag_evaluations,
              hasRagSummary: !!response.data.rag_summary,
              responseKeys: Object.keys(response.data)
            })
          }
        }
        
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
          handleEndSimulation(chatHistoryRef.current) // 🚨 최신 chatHistory 전달
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

      // 🧪 테스트 모드 처리 (백엔드 응답의 is_test_mode도 확인)
      const isTestModeFromResponse = response.data.is_test_mode === true
      const isTestModeEffective = isTestModeFromResponse || isTestMode
      
      if (isTestModeEffective) {
        console.log('🧪 ===== 테스트 모드 텍스트 입력 응답 처리 =====')
        console.log('🧪 백엔드 is_test_mode:', response.data.is_test_mode)
        console.log('🧪 customer_response:', response.data.customer_response)
        console.log('🧪 customer_audio:', response.data.customer_audio)
        
        // 테스트 모드: current_turn_index 업데이트 및 다음 턴의 expected_text 표시
        const nextTurnIndex = response.data.current_turn_index !== undefined 
          ? response.data.current_turn_index 
          : currentTurnIndex + 1
        
        setCurrentTurnIndex(nextTurnIndex)
        
        // 백엔드에서 next_turn_expected_text를 제공하면 우선 사용, 없으면 test_scenario에서 가져오기
        if (response.data.next_turn_expected_text) {
          setCurrentExpectedText(response.data.next_turn_expected_text)
          console.log('🧪 테스트 모드: 백엔드에서 다음 턴 기대 텍스트 수신:', response.data.next_turn_expected_text)
        } else {
          // 백엔드에서 제공하지 않으면 test_scenario에서 직접 가져오기
          const testScenario = simulationData?.test_scenario
          if (testScenario?.turns && nextTurnIndex < testScenario.turns.length) {
            const nextTurn = testScenario.turns[nextTurnIndex]
            if (nextTurn?.expected_text) {
              setCurrentExpectedText(nextTurn.expected_text)
              console.log('🧪 테스트 모드: 다음 턴 기대 텍스트 설정:', nextTurn.expected_text)
            } else {
              setCurrentExpectedText('')
            }
          } else {
            setCurrentExpectedText('')
          }
        }
        
        if (!ragCollectedForThisResponse) {
          const collected = collectRagDataFromResponse(response.data, {
            context: 'text-turn',
            turnIndexHint: nextTurnIndex - 1,
            nextTurnRole: response.data.next_turn_role
          })
          ragCollectedForThisResponse = ragCollectedForThisResponse || collected
          if (!collected) {
            console.warn('🧪 ⚠️ 테스트 모드 텍스트 응답에서 RAG 평가 결과를 찾지 못했습니다.', {
              responseKeys: Object.keys(response.data || {}),
              currentTurnIndex
            })
          }
        }
      }

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
      
      // 🔥 사용자가 입력한 메시지는 항상 'user' (신입사원)로 추가
      // 테스트 모드든 일반 모드든 상관없이, 사용자가 직접 입력/녹음한 것은 모두 신입사원 발화
      console.log('🔥 ✅ 사용자 메시지 추가: role="user" (신입사원), text="' + userMessage.substring(0, 30) + '..."')
      const traineeMessage: ChatMessage = {
        id: Date.now().toString(),
        role: 'user',  // 🔥 무조건 'user' (신입사원, 파란색, 오른쪽)
        text: userMessage,
        timestamp: new Date()
      }
      updatedChatHistory.push(traineeMessage)
      
      // 🧪 테스트 모드: 백엔드에서 고객 응답이 자동으로 생성되므로 추가
      // 고객 응답 추가 (테스트 모드와 일반 모드 모두)
      if (customer_response && !isEnding) {
        // customer_response에서 불필요한 텍스트 제거 (speak, 말하기 등)
        const cleanResponse = customer_response.replace(/\b(speak|말하기|말해|말씀)\b/gi, '').trim()
        
        console.log('🔥 ✅ 고객 응답 추가: role="customer", text="' + cleanResponse.substring(0, 30) + '..."')
        updatedChatHistory.push({
          id: (Date.now() + 1).toString(),
          role: 'customer',
          text: cleanResponse, // 정리된 텍스트 저장
          audio: customer_audio,
          timestamp: new Date()
        })

        // 🧪 테스트 모드가 아닐 때만 아바타 설정 (테스트 모드에서는 중복 재생 방지)
        if (customer_audio && !isTestModeEffective) {
          setAudio({
            audioUrl: customer_audio,
            text: cleanResponse,
            mouthCues: [] // TODO: Rhubarb로 생성
          })
        }
      } else {
        console.log('🔥 ⚠️ customer_response가 없거나 isEnding=true여서 고객 응답 추가 안 함')
        console.log('🔥   customer_response:', customer_response)
        console.log('🔥   isEnding:', isEnding)
      }
      
      setChatHistory(updatedChatHistory)
      // chatHistoryRef는 useEffect에서 자동 업데이트됨

      // 사용자 입력 필드 초기화
      setUserMessage('')

      // 🔥 종료 중이면 고객 음성 재생하지 않음
      if (isEnding) {
        setLoading(false)
        return
      }

      // 🧪 테스트 모드: 고객 응답 TTS 자동 재생 (한 번만 재생, 텍스트 입력)
      // ✅ 메시지에 audio는 이미 저장되어 있으므로, 여기서는 자동 재생만 수행
      // ✅ 다시 듣기 버튼은 메시지의 audio를 사용하여 작동함
      // ✅ setAudio는 호출하지 않음 (중복 재생 방지)
      if (isTestModeEffective && customer_audio) {
        try {
          // customer_response에서 불필요한 텍스트 제거 (speak, 말하기 등)
          const cleanResponse = (customer_response || '').replace(/\b(speak|말하기|말해|말씀)\b/gi, '').trim()
          
          console.log('🧪 ========== 테스트 모드: 고객 응답 TTS 자동 재생 시작 (텍스트 입력, 한 번만) ==========')
          console.log('🧪 customer_response (원본):', customer_response)
          console.log('🧪 customer_response (정리):', cleanResponse)
          console.log('🧪 customer_audio 존재:', !!customer_audio)
          console.log('🧪 ✅ 메시지에 audio가 저장되어 있어 다시 듣기 버튼도 작동합니다')
          
          // 오디오만 재생 (setAudio 호출하지 않음 - 중복 재생 방지)
          console.log('🎵 테스트 모드 오디오 자동 재생 시도 (텍스트 입력, 한 번만)...')
          await playFromAnyAudioPayload(customer_audio, 'audio/mpeg')
          setIsPlaying(true)
          setError('')
          console.log('🧪 ✅ 테스트 모드: 고객 응답 TTS 자동 재생 시작됨 (텍스트 입력, 다시 듣기 버튼도 사용 가능)')
          
          // 종료 플래그가 설정되어 있으면 오디오 재생 후 시뮬레이션 종료
          if (isEndMessage) {
            const responseLength = cleanResponse?.length || customer_response?.length || 0
            const estimatedAudioDuration = Math.max(2000, Math.min(responseLength * 100, 5000))
            setTimeout(() => {
              console.log('🔚 대화 종료: 고객 응답 재생 완료 후 종료')
              const currentChatHistory = chatHistory
              console.log(`📤 종료 시 chatHistory 길이: ${currentChatHistory.length}개`)
              setIsGeneratingFeedback(true)
              handleEndSimulation(currentChatHistory)
            }, estimatedAudioDuration)
          }
        } catch (audioError) {
          console.error('🧪 ❌ 테스트 모드: 고객 응답 TTS 재생 실패 (텍스트 입력):', audioError)
          setError('오디오 재생에 실패했습니다.')
          
          // 오디오 재생 실패 시에도 종료 플래그가 설정되어 있으면 종료
          if (isEndMessage) {
            setTimeout(() => {
              console.log('🔚 대화 종료: 오디오 재생 실패로 인한 종료')
              setIsGeneratingFeedback(true)
              handleEndSimulation(chatHistoryRef.current)
            }, 1000)
          }
        }
      } else if (isTestModeEffective) {
        console.log('🧪 ⚠️ 테스트 모드인데 customer_audio가 없습니다 (텍스트 입력):')
        console.log('🧪   customer_audio:', !!customer_audio)
        console.log('🧪   customer_response:', customer_response)
        
        // 오디오가 없을 때도 종료 플래그가 설정되어 있으면 종료
        if (isEndMessage) {
          setTimeout(() => {
            console.log('🔚 대화 종료: 오디오 없음으로 인한 종료')
            setIsGeneratingFeedback(true)
            handleEndSimulation(chatHistoryRef.current)
          }, 1000)
        }
      }
      
      // 오디오 재생 - 새로운 유틸 사용 (일반 모드에서만)
      if (customer_audio && !isTestModeEffective) {
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
              // 🚨 중요: 최신 chatHistory를 파라미터로 전달하여 모든 대화 포함
              const currentChatHistory = chatHistory
              console.log(`📤 종료 시 chatHistory 길이: ${currentChatHistory.length}개`)
              // 대화창을 즉시 숨기고 평가서 생성 시작
              setIsGeneratingFeedback(true)
              handleEndSimulation(currentChatHistory)
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
              handleEndSimulation(chatHistoryRef.current) // 🔧 최신 히스토리 전달
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
            handleEndSimulation(chatHistoryRef.current) // 🔧 최신 히스토리 전달
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
        <div className="bg-white rounded-2xl shadow-2xl p-12 max-w-lg w-full text-center">
          <div className="flex justify-center mb-6">
            <div className="w-20 h-20 bg-blue-100 rounded-full flex items-center justify-center">
              <ArrowPathIcon className="w-12 h-12 text-blue-600 animate-spin" />
            </div>
          </div>
          <h2 className="text-3xl font-bold text-gray-900 mb-4">
            평가서 생성 중...
          </h2>
          <div className="text-gray-600 text-base mb-6">
            <p className="whitespace-nowrap">대화 내용을 분석하여 평가서를 작성하고 있습니다.</p>
            <p className="mt-1">잠시만 기다려주세요.</p>
          </div>
          
          {/* 진행률 표시 */}
          <div className="mb-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-gray-700">진행률</span>
              <span className="text-sm font-bold text-blue-600">{Math.round(feedbackProgress)}%</span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-3 overflow-hidden">
              <div 
                className="bg-blue-600 h-3 rounded-full transition-all duration-300 ease-out"
                style={{ width: `${feedbackProgress}%` }}
              />
            </div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-white flex flex-col md:flex-row">
      {/* 왼쪽: 시뮬레이션 정보 패널 - 접기/펼치기 가능 */}
      {isSimulationInfoOpen ? (
        <div className="w-full md:w-80 bg-white border-r border-gray-200 flex flex-col flex-shrink-0 transition-all duration-300 md:h-auto md:min-h-screen overflow-hidden">
          {/* 헤더 */}
          <div className="p-6 border-b border-gray-200">
            <div className="flex items-center justify-between mb-4">
              <button
                onClick={onBack}
                className="flex items-center text-gray-600 hover:text-gray-800 transition-colors"
              >
                <ArrowLeftIcon className="w-5 h-5 mr-2" />
                뒤로가기
              </button>
              <button
                onClick={() => setIsSimulationInfoOpen(false)}
                className="p-1 text-gray-500 hover:text-gray-700 transition-colors"
                title="패널 닫기"
              >
                {/* 작은 화면: 아래쪽 화살표, 큰 화면: 왼쪽 화살표 */}
                <ChevronUpIcon className="w-5 h-5 md:hidden" />
                <ChevronLeftIcon className="w-5 h-5 hidden md:block" />
              </button>
            </div>
            <h2 className="text-xl font-bold text-gray-900">시뮬레이션 정보</h2>
          </div>

          {/* 탭 네비게이션 */}
          <div className="flex border-b border-gray-200 bg-white">
            <button
              onClick={() => setActiveTab('customer')}
              className={`flex-1 px-4 py-3 text-sm font-medium transition-colors ${
                activeTab === 'customer'
                  ? 'text-blue-600 border-b-2 border-blue-600 bg-white'
                  : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
              }`}
            >
              고객 정보
            </button>
            <button
              onClick={() => setActiveTab('situation-detail')}
              className={`flex-1 px-4 py-3 text-sm font-medium transition-colors ${
                activeTab === 'situation-detail'
                  ? 'text-blue-600 border-b-2 border-blue-600 bg-white'
                  : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
              }`}
            >
              상황 정보
            </button>
            <button
              onClick={() => setActiveTab('goals')}
              className={`flex-1 px-4 py-3 text-sm font-medium transition-colors ${
                activeTab === 'goals'
                  ? 'text-blue-600 border-b-2 border-blue-600 bg-white'
                  : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
              }`}
            >
              목표
            </button>
          </div>

          {/* 탭 컨텐츠 */}
          <div className="flex-1 overflow-y-auto p-6">
            {/* 고객 정보 탭 */}
            {activeTab === 'customer' && (
              <div className="bg-white rounded-lg p-4 space-y-3">
                <div className="flex justify-between items-center">
                  <span className="text-gray-600">성별:</span>
                  <span className="font-medium text-gray-900">
                    {simulationData?.persona?.gender || '미설정'}
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-gray-600">연령대:</span>
                  <span className="font-medium text-gray-900">
                    {simulationData?.persona?.age_group || '미설정'}
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-gray-600">직업:</span>
                  <span className="font-medium text-gray-900">
                    {simulationData?.persona?.occupation || '미설정'}
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-gray-600">고객 타입:</span>
                  <span className="font-medium text-gray-900">
                    {simulationData?.persona?.type || '미설정'}
                  </span>
                </div>
              </div>
            )}

            {/* 상황 정보 탭 */}
            {activeTab === 'situation-detail' && (
              <div className="bg-white rounded-lg p-4 space-y-3">
                <div>
                  <div className="text-sm text-gray-600 mb-2">업무 카테고리</div>
                  <div className="text-base font-medium text-gray-900">
                    {simulationData?.situation?.category || '미설정'}
                  </div>
                </div>
                <div>
                  <div className="text-sm text-gray-600 mb-2">상황 제목</div>
                  <div className="text-base font-medium text-gray-900">
                    {sanitizeSituationTitle(simulationData?.situation?.title || '미설정')}
                  </div>
                </div>
                {simulationData?.situation?.description && (
                  <div>
                    <div className="text-sm text-gray-600 mb-2">상황 설명</div>
                    <div className="text-sm text-gray-700">
                      {simulationData.situation.description}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* 목표 탭 */}
            {activeTab === 'goals' && (
              <div className="space-y-3">
                {/* 안내 박스 (UI 과밀로 인해 일단 비표시 처리)
                <div className="bg-blue-50/70 rounded-lg border border-blue-200 p-3 text-xs leading-relaxed">
                  <p>
                    <span className="font-semibold text-blue-700">
                      이 시뮬레이션은 아래에 정의된 목표 달성 여부가 평가 기준으로 들어가며
                    </span>
                  </p>
                  <p className="mt-1 text-gray-700">
                    <span className="font-semibold text-blue-700">
                      대화 중 목표가 달성되면 자동으로 체크됩니다.
                    </span>
                  </p>
                </div>
                */}

                {simulationData?.situation?.goals && simulationData.situation.goals.length > 0 ? (
                  <ul className="space-y-3">
                    {simulationData.situation.goals.map((goal: string, index: number) => {
                      const isChecked = checkedGoals.has(index)
                      return (
                        <li
                          key={index}
                          className={`flex items-start gap-3 rounded-xl p-4 text-sm transition-colors border ${
                            isChecked ? 'bg-blue-50 border-blue-300' : 'bg-gray-50 border-gray-200'
                          }`}
                        >
                          {/* 번호/체크 아이콘 */}
                          <div className="flex-shrink-0 mt-0.5">
                            <div
                              className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold ${
                                isChecked ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-500'
                              }`}
                            >
                              {isChecked ? <CheckIcon className="w-4 h-4" /> : index + 1}
                            </div>
                          </div>

                          {/* 제목 + 설명 */}
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center justify-between mb-1">
                              <span className="text-sm font-semibold text-gray-700">
                                목표 {index + 1}
                              </span>
                              {isChecked && (
                                <span className="text-sm font-semibold text-blue-600">
                                  달성
                                </span>
                              )}
                            </div>
                            <p className={`text-sm leading-relaxed ${isChecked ? 'text-blue-800' : 'text-gray-900'}`}>
                              {renderHighlightedText(goal)}
                            </p>
                          </div>
                        </li>
                      )
                    })}
                  </ul>
                ) : (
                  <div className="text-center text-gray-500 py-8">
                    설정된 목표가 없습니다.
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      ) : (
        /* 패널이 닫혔을 때 - 작은 화면: 패널 위치에 열기 버튼, 큰 화면: 왼쪽에 열기 버튼 */
        <>
          {/* 작은 화면: 패널이 열려있을 때의 헤더 위치에 열기 버튼 */}
          <div className="md:hidden w-full bg-white border-r border-gray-200 flex flex-col">
            <div className="p-6 border-b border-gray-200">
              <div className="flex items-center justify-end">
                <button
                  onClick={() => setIsSimulationInfoOpen(true)}
                  className="p-1 text-gray-500 hover:text-gray-700 transition-colors"
                  title="시뮬레이션 정보 열기"
                >
                  <ChevronDownIcon className="w-5 h-5" />
                </button>
              </div>
            </div>
          </div>
          {/* 큰 화면: 왼쪽에 열기 버튼 */}
          <div className="hidden md:block w-12 bg-white border-r border-gray-200 flex items-start justify-center pt-6">
            <button
              onClick={() => setIsSimulationInfoOpen(true)}
              className="p-2 text-gray-500 hover:text-gray-700 transition-colors"
              title="패널 열기"
            >
              <ChevronRightIcon className="w-5 h-5" />
            </button>
          </div>
        </>
      )}

      {/* 오른쪽: 메인 시뮬레이션 영역 - 16:9 고정 */}
      <div className="flex-1 flex flex-col bg-white overflow-hidden">
        {/* 시작 전 화면 */}
        {!isStarted && (
          <div className="flex-1 flex items-center justify-center bg-white">
            <div className="text-center">
              <h1 className="text-4xl font-bold text-gray-900 mb-4">시뮬레이션 준비</h1>
              <button
                onClick={() => {
                  setIsStarted(true)
                  setIsInitializing(true)
                  setSimulationStartTime(Date.now()) // 시뮬레이션 시작 시간 기록
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
            {/* 비디오 영역 - 16:9 비율 고정, 반응형 조정 */}
            <div 
              ref={videoContainerRef}
              className="relative bg-gray-900 w-full" 
              style={{ aspectRatio: '16/9', minHeight: '200px' }}
            >
              {/* 전체 화면 버튼 */}
              {isStarted && (
                <button
                  onClick={toggleFullscreen}
                  className="absolute top-4 right-4 z-10 p-2 bg-black bg-opacity-50 text-white rounded-lg hover:bg-opacity-70 transition-all"
                  title={isFullscreen ? '전체 화면 해제' : '전체 화면'}
                >
                  {isFullscreen ? (
                    <ArrowsPointingInIcon className="w-6 h-6" />
                  ) : (
                    <ArrowsPointingOutIcon className="w-6 h-6" />
                  )}
                </button>
              )}
              {/* 🔥 초기 알림 오버레이 - 비디오 영역 중앙에 띄우되, 하단 녹음 버튼과 겹치지 않게 여백 확보 */}
              {isInitializing && initialInstructionMessage && (
                <div className="absolute inset-0 bg-black bg-opacity-50 z-10 flex items-center justify-center pt-4 pb-32 md:pt-8 md:pb-28">
                  <div className="bg-white rounded-xl p-2 sm:p-3 md:p-4 max-w-md w-[80%] sm:w-[75%] md:w-[70%] lg:w-[60%] mx-2 sm:mx-4 shadow-2xl max-h-[65vh] sm:max-h-[60vh] md:max-h-[60vh] overflow-y-auto">
                    <div className="text-center">
                      <div className="text-lg sm:text-xl md:text-2xl lg:text-3xl mb-1.5 sm:mb-2 md:mb-3">💬</div>
                      {isTestMode ? (
                        <>
                          <h2 className="text-sm sm:text-base md:text-lg lg:text-xl font-bold text-gray-900 mb-1.5 sm:mb-2 md:mb-3">
                            테스트 모드
                          </h2>
                          <div className="bg-blue-50 border-2 border-blue-300 rounded-lg p-1.5 sm:p-2 md:p-3 mb-1.5 sm:mb-2 md:mb-3">
                            <p className="text-xs font-semibold text-blue-800 mb-0.5 sm:mb-1">다음 대사를 따라 말해주세요:</p>
                            <p className="text-xs sm:text-sm md:text-base font-medium text-gray-900 leading-relaxed break-words">
                              {currentExpectedText || initialInstructionMessage}
                            </p>
                          </div>
                          <p className="text-xs text-gray-600 mb-2 sm:mb-3 md:mb-4">
                            화면에 표시된 대사를 정확히 따라 말해주세요.
                          </p>
                        </>
                      ) : (
                        <>
                      <h2 className="text-sm sm:text-base md:text-lg lg:text-xl font-bold text-gray-900 mb-1.5 sm:mb-2 md:mb-3 break-words px-1 sm:px-2">
                        {initialInstructionMessage || "안녕하세요, 무엇을 도와드릴까요?"}
                      </h2>
                      <p className="text-xs sm:text-sm md:text-base text-gray-700 mb-1 md:mb-2">
                        위 메시지로 시작하세요.
                      </p>
                      <p className="text-xs text-gray-600 mb-2 sm:mb-3 md:mb-4">
                        마이크 버튼을 눌러 말을 시작해주세요.
                      </p>
                        </>
                      )}
                      
                      {/* 🧪 테스트용: 텍스트 입력 옵션 (임시) */}
                      <div className="mb-2 sm:mb-3 md:mb-4 bg-yellow-50 border border-yellow-300 rounded-lg p-1.5 sm:p-2 md:p-3">
                        <input
                          type="text"
                          value={userMessage}
                          onChange={(e) => setUserMessage(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter' && !e.shiftKey && userMessage.trim()) {
                              e.preventDefault()
                              handleTextSubmit()
                            }
                          }}
                          placeholder="텍스트로 시작하기 (Enter)"
                          className="w-full px-2 py-1 sm:px-3 sm:py-1.5 border border-yellow-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-yellow-500 text-xs sm:text-sm"
                        />
                        <button
                          onClick={handleTextSubmit}
                          disabled={!userMessage.trim() || loading}
                          className="mt-1 sm:mt-1.5 w-full px-2 py-1 sm:px-3 sm:py-1.5 bg-yellow-500 text-white rounded-lg hover:bg-yellow-600 disabled:bg-gray-300 disabled:cursor-not-allowed text-xs sm:text-sm font-medium"
                        >
                          텍스트로 시작하기
                        </button>
                      </div>
                      
                      <div className="flex justify-center mb-1">
                        <div className="bg-blue-50 border-2 border-blue-300 rounded-lg px-1.5 sm:px-2 md:px-3 py-1 sm:py-1.5">
                          <p className="text-blue-800 font-semibold text-xs">
                            📍 화면 하단의 빨간 녹음 버튼을 눌러주세요
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
                  !isPersonaMainView ? 'z-20' : 'z-0'
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

              {/* 🧪 테스트 모드: 신입사원 응답 표시 */}
              {isTestMode && currentExpectedText && (
                <div className="absolute top-4 left-1/2 transform -translate-x-1/2 z-50 bg-yellow-100 border-2 border-yellow-400 rounded-lg p-4 max-w-2xl shadow-lg">
                  <div className="flex items-start">
                    <div className="flex-shrink-0 mr-3">
                      <span className="text-2xl">🟨</span>
                    </div>
                    <div className="flex-1">
                      <div className="text-sm font-semibold text-yellow-800 mb-1">신입사원 답변</div>
                      <div className="text-base text-gray-800 leading-relaxed whitespace-pre-wrap">
                        {currentExpectedText}
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* 녹음 버튼 (하단 중앙) - 일반 모드와 테스트 모드 동일하게 처리 */}
              {/* 화면 하단에 살짝 여유를 두어 버튼이 잘리지 않도록 bottom 여백을 크게 설정 */}
              <div className="absolute bottom-6 md:bottom-10 left-1/2 transform -translate-x-1/2 z-10">
                {!isRecording ? (
                  <button
                    onClick={startRecording}
                    disabled={loading}
                    className="flex items-center px-4 py-2 md:px-8 md:py-4 bg-red-600 text-white rounded-full hover:bg-red-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors shadow-2xl text-sm md:text-base"
                  >
                    <MicrophoneIcon className="w-5 h-5 md:w-6 md:h-6 mr-1 md:mr-2" />
                    <span className="hidden sm:inline">녹음 시작</span>
                    <span className="sm:hidden">녹음</span>
                  </button>
                ) : (
                  <button
                    onClick={stopRecording}
                    className="flex items-center px-4 py-2 md:px-8 md:py-4 bg-red-600 text-white rounded-full hover:bg-red-700 transition-colors shadow-2xl animate-pulse text-sm md:text-base"
                  >
                    <StopIcon className="w-5 h-5 md:w-6 md:h-6 mr-1 md:mr-2" />
                    <span className="hidden sm:inline">녹음 중지</span>
                    <span className="sm:hidden">중지</span>
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

            {/* 채팅 히스토리 - 내용에 맞게 자동 조정 */}
            <div className="flex flex-col bg-white border-t border-gray-200 relative z-10">
              <div className="flex items-center justify-between px-4 pt-4 pb-2 flex-shrink-0">
                <h3 className="font-semibold text-gray-900">대화</h3>
                <button
                  onClick={() => setIsChatCollapsed(!isChatCollapsed)}
                  className="p-1 text-gray-500 hover:text-gray-700 transition-colors"
                  title={isChatCollapsed ? '대화창 펼치기' : '대화창 접기'}
                >
                  {isChatCollapsed ? (
                    <ChevronDownIcon className="w-5 h-5" />
                  ) : (
                    <ChevronUpIcon className="w-5 h-5" />
                  )}
                </button>
              </div>
              
              {/* 스크롤 가능한 대화 내용 영역 - 내용에 맞게 자동 조정, 최대 높이 제한 */}
              {!isChatCollapsed && (
              <div 
                className="overflow-y-auto px-4 pb-2" 
                style={{ 
                  scrollBehavior: 'smooth',
                  position: 'relative',
                  maxHeight: '400px', // 최대 높이 제한
                  minHeight: '100px', // 최소 높이
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
                  <>
                    {chatHistory.map((message, mapIndex) => {
                      // 🔥 디버깅: 렌더링 시 role 확인
                      console.log(`🎨 [렌더링 ${mapIndex}] role='${message.role}' (타입: ${typeof message.role}), text='${message.text.substring(0, 30)}...'`)
                      const isUser = message.role === 'user'
                      const isCustomer = message.role === 'customer'
                      console.log(`🎨   → isUser=${isUser}, isCustomer=${isCustomer}`)
                      console.log(`🎨   → justify-end(오른쪽, 파란색)=${isUser}, justify-start(왼쪽, 초록색)=${isCustomer}`)
                      
                      return (
                      <div
                        key={message.id}
                        className={`flex ${
                          isUser ? 'justify-end' : 'justify-start'
                        }`}
                      >
                        <div
                          className={`p-4 rounded-lg max-w-[75%] ${
                            isUser
                              ? 'bg-blue-50' 
                              : 'bg-green-50'
                          }`}
                        >
                          <div className="flex items-center mb-2">
                            <span className={`font-medium text-sm ${
                              isUser ? 'text-blue-800' : 'text-green-800'
                            }`}>
                              {isUser ? '신입사원 (나)' : '고객'}
                            </span>
                            {/* 🔥 디버깅: role 표시 */}
                            <span className="text-xs text-gray-400 ml-2">
                              [role: {message.role}]
                            </span>
                            <span className="text-xs text-gray-500 ml-2">
                              {message.timestamp.toLocaleTimeString()}
                            </span>
                          </div>
                          <p className={`text-sm leading-relaxed ${
                            isUser ? 'text-blue-700' : 'text-green-700'
                          }`}>
                            {message.text}
                          </p>
                          {isCustomer && message.audio && (
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
                      </div>
                      )
                    })}
                    {/* 로딩 중일 때 고객 응답 생성 중 메시지 표시 */}
                    {loading && (
                      <div className="flex justify-start">
                        <div className="bg-green-50 p-4 rounded-lg max-w-[75%]">
                          <div className="flex items-center gap-2">
                            <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-green-600"></div>
                            <span className="text-sm text-green-700 font-medium">
                              고객님의 대화 생성 중입니다...
                            </span>
                          </div>
                        </div>
                      </div>
                    )}
                  </>
                )}
                <div ref={chatEndRef} />
                </div>
              </div>
              )}
              
              {/* 접혔을 때: 고객의 가장 최신 메시지만 표시 */}
              {isChatCollapsed && (() => {
                const latestCustomerMessage = [...chatHistory].reverse().find(msg => msg.role === 'customer')
                return latestCustomerMessage ? (
                  <div className="px-4 pb-2">
                    <div className="bg-green-50 p-3 rounded-lg">
                      <div className="flex items-center mb-1">
                        <span className="font-medium text-sm text-green-800">고객</span>
                        <span className="text-xs text-gray-500 ml-2">
                          {latestCustomerMessage.timestamp.toLocaleTimeString()}
                        </span>
                      </div>
                      <p className="text-sm text-green-700 leading-relaxed line-clamp-2">
                        {latestCustomerMessage.text}
                      </p>
                    </div>
                  </div>
                ) : (
                  <div className="px-4 pb-2">
                    <div className="text-center text-gray-500 text-sm py-2">
                      아직 고객 메시지가 없습니다.
                    </div>
                  </div>
                )
              })()}

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
