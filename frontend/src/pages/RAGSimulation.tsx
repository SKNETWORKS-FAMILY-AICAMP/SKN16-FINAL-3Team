/**
 * RAG 기반 시뮬레이션 페이지
 * 제공된 데이터를 활용한 STT/LLM/TTS 기반 음성 시뮬레이션
 */
import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'
import { api } from '../utils/api'
import {
  PlayIcon,
  StopIcon,
  MicrophoneIcon,
  SpeakerWaveIcon,
  ClockIcon,
  TrophyIcon,
  ChartBarIcon,
  AcademicCapIcon,
  CheckCircleIcon,
  XCircleIcon,
  ArrowRightIcon,
  ArrowLeftIcon,
  UserIcon,
  StarIcon
} from '@heroicons/react/24/outline'
// import { motion } from 'framer-motion'

interface Persona {
  persona_id: string
  age_group: string
  occupation: string
  financial_literacy: string
  type: string
  tone: string
  style: any
  sample_utterances: string[]
  notes: string
}

interface Scenario {
  scenario_id: string
  title: string
  persona: string
  difficulty: string
  storyline: any
  turn_blueprint: any[]
  evaluation_rubric: any[]
}

interface SimulationState {
  currentPersona: Persona | null
  currentScenario: Scenario | null
  sessionData: any | null
  isRecording: boolean
  isPlaying: boolean
  conversationHistory: any[]
  currentScore: number
  isCompleted: boolean
}

const RAGSimulation: React.FC = () => {
  const { user } = useAuthStore()
  const navigate = useNavigate()
  const [personas, setPersonas] = useState<Persona[]>([])
  const [scenarios, setScenarios] = useState<Scenario[]>([])
  const [selectedPersona, setSelectedPersona] = useState<string>('')
  const [selectedScenario, setSelectedScenario] = useState<string>('')
  const [simulationState, setSimulationState] = useState<SimulationState>({
    currentPersona: null,
    currentScenario: null,
    sessionData: null,
    isRecording: false,
    isPlaying: false,
    conversationHistory: [],
    currentScore: 0,
    isCompleted: false
  })
  const [userMessage, setUserMessage] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [simulationStartTime, setSimulationStartTime] = useState<number | null>(null)
  const [showEndGuide, setShowEndGuide] = useState(true) // 종료 방법 안내 표시 여부
  const [autoEndDetected, setAutoEndDetected] = useState(false) // 자동 종료 감지 여부

  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const audioChunksRef = useRef<Blob[]>([])
  const audioRef = useRef<HTMLAudioElement | null>(null)

  useEffect(() => {
    loadRAGData()
    
    return () => {
      if (mediaRecorderRef.current) {
        mediaRecorderRef.current.stop()
      }
    }
  }, [])

  const loadRAGData = async () => {
    try {
      setLoading(true)
      setError('')
      
      // 페르소나 목록 로드
      const personasResponse = await api.get('/rag-simulation/personas')
      setPersonas(personasResponse.data.personas || [])
      
      // 시나리오 목록 로드
      const scenariosResponse = await api.get('/rag-simulation/scenarios')
      setScenarios(scenariosResponse.data.scenarios || [])
      
    } catch (error) {
      console.error('RAG 데이터 로드 실패:', error)
      setError('데이터를 불러올 수 없습니다. 서버를 확인해주세요.')
      
      // 기본 데이터로 폴백
      setPersonas([
        {
          persona_id: 'p_30s_employee_mediumlit_practical',
          age_group: '30대',
          occupation: '직장인',
          financial_literacy: '중간',
          type: '실용형',
          tone: 'neutral',
          style: { utterance_length: 'medium', politeness: 'normal' },
          sample_utterances: ['핵심만 간단히 알려주세요.', '비교표 있나요?'],
          notes: '결론 중심, 간결한 설명 선호'
        }
      ])
      
      setScenarios([
        {
          scenario_id: 'sc_easy_0001_p_30s_employee_mediumlit_practical_s_deposit_info',
          title: '예금 상품 상담',
          persona: 'p_30s_employee_mediumlit_practical',
          difficulty: 'easy',
          storyline: {
            initial_state: '고객이 예금 상품에 대해 문의하고 있습니다.',
            conflict: '권유성 멘트 없이 사실 중심 비교가 필요합니다.',
            resolution: '핵심 조건과 주의사항을 요약하고 안내 문서를 제공합니다.'
          },
          turn_blueprint: [],
          evaluation_rubric: []
        }
      ])
    } finally {
      setLoading(false)
    }
  }

  const startSimulation = async () => {
    if (!selectedPersona || !selectedScenario) {
      setError('페르소나와 시나리오를 선택해주세요.')
      return
    }

    try {
      setLoading(true)
      setError('')
      
      const response = await api.post('/rag-simulation/start-simulation', {
        persona_id: selectedPersona,
        scenario_id: selectedScenario
      })
      
      const result = response.data
      
      setSimulationState({
        currentPersona: personas.find(p => p.persona_id === selectedPersona) || null,
        currentScenario: scenarios.find(s => s.scenario_id === selectedScenario) || null,
        sessionData: result,
        isRecording: false,
        isPlaying: false,
        conversationHistory: [result.initial_message],
        currentScore: 0,
        isCompleted: false
      })
      
      // 시뮬레이션 시작 시간 기록
      setSimulationStartTime(Date.now())
      
    } catch (error) {
      console.error('시뮬레이션 시작 실패:', error)
      setError('시뮬레이션을 시작할 수 없습니다.')
    } finally {
      setLoading(false)
    }
  }

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const mediaRecorder = new MediaRecorder(stream)
      mediaRecorderRef.current = mediaRecorder
      audioChunksRef.current = []

      mediaRecorder.ondataavailable = (event) => {
        audioChunksRef.current.push(event.data)
      }

      mediaRecorder.onstop = async () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/wav' })
        await processAudioInput(audioBlob)
      }

      mediaRecorder.start()
      setSimulationState(prev => ({ ...prev, isRecording: true }))
      
    } catch (error) {
      console.error('녹음 시작 실패:', error)
      setError('마이크 접근 권한이 필요합니다.')
    }
  }

  const stopRecording = () => {
    if (mediaRecorderRef.current && simulationState.isRecording) {
      mediaRecorderRef.current.stop()
      setSimulationState(prev => ({ ...prev, isRecording: false }))
    }
  }

  const processAudioInput = async (audioBlob: Blob) => {
    try {
      setLoading(true)
      
      const formData = new FormData()
      formData.append('audio_file', audioBlob)
      
      const response = await api.post('/rag-simulation/process-voice-interaction', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        params: {
          session_data: JSON.stringify(simulationState.sessionData)
        }
      })
      
      const result = response.data
      
      // 자동 종료 신호 감지
      if (result.end_signal) {
        setAutoEndDetected(true)
        // 3초 후 자동으로 종료 안내 (백엔드 메시지 사용)
        const endMessage = result.end_message || '대화가 자연스럽게 마무리되었습니다. 피드백을 확인하시겠습니까?'
        setTimeout(() => {
          if (window.confirm(endMessage)) {
            endSimulation()
          }
        }, 3000)
      }
      
      // 대화 기록 업데이트
      setSimulationState(prev => ({
        ...prev,
        conversationHistory: [...prev.conversationHistory, result],
        currentScore: result.session_score
      }))
      
      // 고객 음성 재생
      if (result.customer_audio) {
        await playAudio(result.customer_audio)
      }
      
    } catch (error) {
      console.error('음성 처리 실패:', error)
      setError('음성 처리를 실패했습니다.')
    } finally {
      setLoading(false)
    }
  }

  const processTextInput = async () => {
    if (!userMessage.trim()) {
      setError('메시지를 입력해주세요.')
      return
    }

    try {
      setLoading(true)
      
      const response = await api.post('/rag-simulation/process-voice-interaction', {
        session_data: simulationState.sessionData,
        user_message: userMessage
      })
      
      const result = response.data
      
      // 자동 종료 신호 감지
      if (result.end_signal) {
        setAutoEndDetected(true)
        // 3초 후 자동으로 종료 안내 (백엔드 메시지 사용)
        const endMessage = result.end_message || '대화가 자연스럽게 마무리되었습니다. 피드백을 확인하시겠습니까?'
        setTimeout(() => {
          if (window.confirm(endMessage)) {
            endSimulation()
          }
        }, 3000)
      }
      
      // 대화 기록 업데이트
      setSimulationState(prev => ({
        ...prev,
        conversationHistory: [...prev.conversationHistory, result],
        currentScore: result.session_score
      }))
      
      setUserMessage('')
      
      // 고객 음성 재생
      if (result.customer_audio) {
        await playAudio(result.customer_audio)
      }
      
    } catch (error) {
      console.error('텍스트 처리 실패:', error)
      setError('텍스트 처리를 실패했습니다.')
    } finally {
      setLoading(false)
    }
  }

  const playAudio = async (audioData: string) => {
    try {
      setSimulationState(prev => ({ ...prev, isPlaying: true }))
      
      const audio = new Audio(audioData)
      audioRef.current = audio
      
      audio.onended = () => {
        setSimulationState(prev => ({ ...prev, isPlaying: false }))
      }
      
      audio.onerror = () => {
        setSimulationState(prev => ({ ...prev, isPlaying: false }))
        setError('음성 재생에 실패했습니다.')
      }
      
      await audio.play()
      
    } catch (error) {
      console.error('음성 재생 실패:', error)
      setSimulationState(prev => ({ ...prev, isPlaying: false }))
      setError('음성 재생에 실패했습니다.')
    }
  }

  const resetSimulation = () => {
    setSimulationState({
      currentPersona: null,
      currentScenario: null,
      sessionData: null,
      isRecording: false,
      isPlaying: false,
      conversationHistory: [],
      currentScore: 0,
      isCompleted: false
    })
    setUserMessage('')
    setError('')
    
    if (mediaRecorderRef.current) {
      mediaRecorderRef.current.stop()
    }
    if (audioRef.current) {
      audioRef.current.pause()
    }
  }

  const endSimulation = async () => {
    try {
      setLoading(true)
      setError('')

      // 대화 기록이 충분한지 확인
      if (simulationState.conversationHistory.length < 2) {
        setError('시뮬레이션을 더 진행해주세요. (최소 2턴 이상 대화 필요)')
        setLoading(false)
        return
      }

      // 확인 대화상자
      const confirmed = window.confirm('시뮬레이션을 종료하고 피드백을 확인하시겠습니까?')
      if (!confirmed) {
        setLoading(false)
        return
      }

      // 시뮬레이션 경과 시간 계산 (초)
      const durationSeconds = simulationStartTime 
        ? Math.floor((Date.now() - simulationStartTime) / 1000)
        : null

      // 대화 히스토리를 세션 데이터에서 가져오거나 로컬 상태에서 가져오기
      const conversationHistory = simulationState.sessionData?.conversation_history || 
                                  simulationState.conversationHistory.map((msg, index) => ({
                                    role: index === 0 || index % 2 === 0 ? 'customer' : 'employee',
                                    text: msg.content || msg.text || msg.customer_response || '',
                                    timestamp: new Date().toISOString()
                                  }))

      // 피드백 생성 API 호출
      const response = await api.post('/rag-simulation/generate-feedback', {
        conversation_history: conversationHistory,
        persona: simulationState.sessionData?.persona || simulationState.currentPersona,
        situation: simulationState.sessionData?.situation || simulationState.currentScenario,
        duration_seconds: durationSeconds
      })

      const feedbackData = response.data.feedback

      // 피드백 페이지로 이동 (state를 통해 데이터 전달)
      navigate('/simulation-feedback', {
        state: { feedbackData }
      })

    } catch (error) {
      console.error('시뮬레이션 종료 및 피드백 생성 실패:', error)
      setError('피드백 생성에 실패했습니다. 다시 시도해주세요.')
    } finally {
      setLoading(false)
    }
  }

  const getDifficultyColor = (difficulty: string) => {
    switch (difficulty) {
      case 'easy': return 'bg-green-100 text-green-800'
      case 'normal': return 'bg-yellow-100 text-yellow-800'
      case 'hard': return 'bg-red-100 text-red-800'
      default: return 'bg-gray-100 text-gray-800'
    }
  }

  const getToneColor = (tone: string) => {
    switch (tone) {
      case 'neutral': return 'bg-blue-100 text-blue-800'
      case 'calm': return 'bg-green-100 text-green-800'
      case 'friendly': return 'bg-yellow-100 text-yellow-800'
      case 'angry': return 'bg-red-100 text-red-800'
      case 'impatient': return 'bg-orange-100 text-orange-800'
      default: return 'bg-gray-100 text-gray-800'
    }
  }

  if (simulationState.sessionData) {
    // 시뮬레이션 진행 화면
    return (
      <div className="min-h-screen bg-gradient-to-br from-purple-50 to-blue-100 p-6">
        <div className="max-w-6xl mx-auto">
          {/* 헤더 */}
          <div className="bg-white rounded-lg shadow-lg p-6 mb-6">
            <div className="flex items-center justify-between">
              <div>
                <h1 className="text-2xl font-bold text-gray-900">RAG 기반 음성 시뮬레이션</h1>
                <p className="text-gray-600 mt-2">
                  {simulationState.currentPersona?.persona_id} - {simulationState.currentScenario?.title}
                </p>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={endSimulation}
                  disabled={loading || simulationState.conversationHistory.length < 2}
                  className={`px-4 py-2 rounded-lg transition-colors flex items-center ${
                    autoEndDetected 
                      ? 'bg-green-600 text-white hover:bg-green-700 animate-pulse' 
                      : simulationState.conversationHistory.length >= 2
                      ? 'bg-blue-600 text-white hover:bg-blue-700'
                      : 'bg-gray-400 text-white cursor-not-allowed'
                  }`}
                  title={simulationState.conversationHistory.length < 2 ? '최소 2턴 이상 대화 후 종료 가능' : '시뮬레이션 종료 및 피드백 확인'}
                >
                  <ChartBarIcon className="h-5 w-5 mr-2" />
                  {autoEndDetected ? '피드백 확인하기' : '피드백 보기'}
                </button>
                <button
                  onClick={resetSimulation}
                  className="px-4 py-2 bg-gray-500 text-white rounded-lg hover:bg-gray-600 transition-colors"
                >
                  취소
                </button>
              </div>
            </div>
            
            {/* 종료 방법 안내 */}
            {showEndGuide && (
              <div className="mt-4 p-4 bg-blue-50 border border-blue-200 rounded-lg">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <h3 className="text-sm font-semibold text-blue-900 mb-1">💡 시뮬레이션 종료 방법</h3>
                    <ul className="text-xs text-blue-800 space-y-1 list-disc list-inside">
                      <li>대화가 자연스럽게 마무리되면 자동으로 종료 안내가 표시됩니다</li>
                      <li>또는 상단의 <strong>"피드백 보기"</strong> 버튼을 클릭하여 언제든지 종료할 수 있습니다 (최소 2턴 이상 대화 필요)</li>
                      <li>고객이 "감사합니다", "이만", "괜찮습니다" 등의 말을 하면 종료 시점으로 판단됩니다</li>
                    </ul>
                  </div>
                  <button
                    onClick={() => setShowEndGuide(false)}
                    className="ml-4 text-blue-600 hover:text-blue-800 text-sm font-medium"
                  >
                    닫기
                  </button>
                </div>
              </div>
            )}
            
            {/* 자동 종료 감지 알림 */}
            {autoEndDetected && (
              <div className="mt-4 p-4 bg-green-50 border border-green-300 rounded-lg">
                <div className="flex items-center gap-2">
                  <CheckCircleIcon className="h-5 w-5 text-green-600 flex-shrink-0" />
                  <div className="flex-1">
                    <p className="text-sm font-semibold text-green-800 mb-1">
                      대화가 자연스럽게 마무리되었습니다
                    </p>
                    <p className="text-xs text-green-700">
                      잠시 후 피드백 확인 안내가 표시됩니다. 또는 상단의 "피드백 확인하기" 버튼을 클릭하세요.
                    </p>
                  </div>
                </div>
              </div>
            )}
            
            {/* 현재 점수 및 턴 수 */}
            <div className="mt-4 grid grid-cols-2 gap-4">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-gray-700">대화 턴</span>
                <span className="text-lg font-bold text-purple-600">
                  {Math.floor(simulationState.conversationHistory.length / 2)}턴
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-gray-700">현재 점수</span>
                <span className="text-lg font-bold text-blue-600">
                  {simulationState.currentScore.toFixed(1)}점
                </span>
              </div>
            </div>
          </div>

          {/* 대화 영역 */}
          <div className="bg-white rounded-lg shadow-lg p-6 mb-6">
            <h2 className="text-xl font-semibold text-gray-900 mb-4">대화</h2>
            <div className="space-y-4 max-h-96 overflow-y-auto">
              {simulationState.conversationHistory.map((message, index) => (
                <div key={index} className="flex items-start space-x-3">
                  <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
                    index === 0 ? 'bg-blue-500' : 'bg-gray-500'
                  }`}>
                    {index === 0 ? (
                      <UserIcon className="w-5 h-5 text-white" />
                    ) : (
                      <SpeakerWaveIcon className="w-5 h-5 text-white" />
                    )}
                  </div>
                  <div className="flex-1">
                    <p className="text-gray-900">{message.text}</p>
                    {message.feedback && (
                      <p className="text-sm text-gray-600 mt-1">{message.feedback}</p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* 입력 영역 */}
          <div className="bg-white rounded-lg shadow-lg p-6">
            <h2 className="text-xl font-semibold text-gray-900 mb-4">응답 입력</h2>
            
            {/* 음성 입력 */}
            <div className="mb-4">
              <div className="flex items-center space-x-4">
                <button
                  onClick={simulationState.isRecording ? stopRecording : startRecording}
                  disabled={loading || simulationState.isPlaying}
                  className={`px-6 py-3 rounded-lg text-white font-medium transition-colors ${
                    simulationState.isRecording
                      ? 'bg-red-600 hover:bg-red-700'
                      : 'bg-blue-600 hover:bg-blue-700'
                  } disabled:bg-gray-400 disabled:cursor-not-allowed`}
                >
                  {simulationState.isRecording ? (
                    <>
                      <StopIcon className="h-5 w-5 inline mr-2" />
                      녹음 중지
                    </>
                  ) : (
                    <>
                      <MicrophoneIcon className="h-5 w-5 inline mr-2" />
                      음성 입력
                    </>
                  )}
                </button>
                
                {simulationState.isPlaying && (
                  <div className="flex items-center text-blue-600">
                    <SpeakerWaveIcon className="h-5 w-5 mr-2" />
                    <span>음성 재생 중...</span>
                  </div>
                )}
              </div>
            </div>

            {/* 텍스트 입력 */}
            <div className="mb-4">
              <textarea
                value={userMessage}
                onChange={(e) => setUserMessage(e.target.value)}
                placeholder="텍스트로 응답을 입력하세요..."
                className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                rows={3}
              />
            </div>

            <button
              onClick={processTextInput}
              disabled={loading || !userMessage.trim()}
              className="w-full bg-green-600 text-white py-3 px-4 rounded-lg hover:bg-green-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors flex items-center justify-center"
            >
              {loading ? (
                <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white" />
              ) : (
                <>
                  텍스트 전송
                  <ArrowRightIcon className="h-5 w-5 ml-2" />
                </>
              )}
            </button>
          </div>

          {error && (
            <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg">
              <p className="text-red-600">{error}</p>
            </div>
          )}
        </div>
      </div>
    )
  }

  // 메인 화면 - 시뮬레이션 선택
  return (
    <div className="min-h-screen bg-gradient-to-br from-purple-50 to-blue-100 p-6">
      <div className="max-w-6xl mx-auto">
        {/* 헤더 */}
        <div className="text-center mb-8">
          <div>
            <h1 className="text-4xl font-bold text-gray-900 mb-4">
              🎯 RAG 기반 음성 시뮬레이션
            </h1>
            <p className="text-xl text-gray-600 mb-6">
              STT/LLM/TTS를 활용한 실제 고객과의 음성 대화 시뮬레이션
            </p>
          </div>
        </div>

        {loading && (
          <div className="text-center py-12">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
            <p className="text-gray-600 mt-4">데이터 로딩 중...</p>
          </div>
        )}

        {!loading && (
          <>
            {/* 선택 영역 */}
            <div className="bg-white rounded-lg shadow-lg p-6 mb-8">
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* 페르소나 선택 */}
                <div>
                  <h2 className="text-xl font-semibold text-gray-900 mb-4">고객 페르소나 선택</h2>
                  <div className="space-y-3 max-h-96 overflow-y-auto">
                    {personas.map((persona) => (
                      <div
                        key={persona.persona_id}
                        className={`p-4 border rounded-lg cursor-pointer transition-colors ${
                          selectedPersona === persona.persona_id
                            ? 'border-blue-500 bg-blue-50'
                            : 'border-gray-200 hover:border-gray-300'
                        }`}
                        onClick={() => setSelectedPersona(persona.persona_id)}
                      >
                        <div className="flex items-center justify-between mb-2">
                          <h3 className="font-medium text-gray-900">{persona.persona_id}</h3>
                          <span className={`px-2 py-1 rounded-full text-xs font-medium ${getToneColor(persona.tone)}`}>
                            {persona.tone}
                          </span>
                        </div>
                        <p className="text-sm text-gray-600">
                          {persona.age_group} • {persona.occupation} • {persona.type}
                        </p>
                        <p className="text-sm text-gray-500 mt-1">{persona.notes}</p>
                      </div>
                    ))}
                  </div>
                </div>

                {/* 시나리오 선택 */}
                <div>
                  <h2 className="text-xl font-semibold text-gray-900 mb-4">시나리오 선택</h2>
                  <div className="space-y-3 max-h-96 overflow-y-auto">
                    {scenarios.map((scenario) => (
                      <div
                        key={scenario.scenario_id}
                        className={`p-4 border rounded-lg cursor-pointer transition-colors ${
                          selectedScenario === scenario.scenario_id
                            ? 'border-blue-500 bg-blue-50'
                            : 'border-gray-200 hover:border-gray-300'
                        }`}
                        onClick={() => setSelectedScenario(scenario.scenario_id)}
                      >
                        <div className="flex items-center justify-between mb-2">
                          <h3 className="font-medium text-gray-900">{scenario.title}</h3>
                          <span className={`px-2 py-1 rounded-full text-xs font-medium ${getDifficultyColor(scenario.difficulty)}`}>
                            {scenario.difficulty}
                          </span>
                        </div>
                        <p className="text-sm text-gray-600">
                          페르소나: {scenario.persona}
                        </p>
                        <p className="text-sm text-gray-500 mt-1">
                          {scenario.storyline?.initial_state}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            {/* 시작 버튼 */}
            <div className="text-center">
              <button
                onClick={startSimulation}
                disabled={!selectedPersona || !selectedScenario || loading}
                className="bg-blue-600 text-white px-8 py-4 rounded-lg hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors flex items-center mx-auto"
              >
                <PlayIcon className="h-6 w-6 mr-2" />
                시뮬레이션 시작
              </button>
            </div>

            {error && (
              <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg">
                <p className="text-red-600">{error}</p>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

export default RAGSimulation
