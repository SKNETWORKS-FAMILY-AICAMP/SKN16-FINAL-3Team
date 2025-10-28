/**
 * IQ 테스트 스타일의 단계별 시뮬레이션 페이지
 * 단계별로 진행되는 큰 화면 시뮬레이션
 */
import { useState, useEffect } from 'react'
import { useAuthStore } from '../store/authStore'
import { api } from '../utils/api'
import VoiceSimulation from './VoiceSimulation'
import {
  ChevronRightIcon,
  ChevronLeftIcon,
  UserIcon,
  BriefcaseIcon,
  AcademicCapIcon,
  StarIcon,
  PlayIcon,
  CheckCircleIcon
} from '@heroicons/react/24/outline'

interface SimulationStep {
  id: string
  title: string
  description: string
  type: 'question' | 'selection' | 'result'
  options?: any[]
  required?: boolean
}

const IQStyleSimulation: React.FC = () => {
  const { user } = useAuthStore()
  const [currentStep, setCurrentStep] = useState(0)
  const [answers, setAnswers] = useState<Record<string, any>>({})
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [simulationResult, setSimulationResult] = useState<any>(null)
  const [showResult, setShowResult] = useState(false)
  const [showVoiceSimulation, setShowVoiceSimulation] = useState(false)

  const steps: SimulationStep[] = [
    {
      id: 'gender',
      title: '성별을 선택해주세요',
      description: '고객의 성별을 선택하면 해당 성별에 맞는 음성으로 대화를 진행합니다.',
      type: 'selection',
      options: [
        { id: 'male', label: '남성', icon: '👨', description: '남성 고객의 음성' },
        { id: 'female', label: '여성', icon: '👩', description: '여성 고객의 음성' }
      ],
      required: true
    },
    {
      id: 'age_group',
      title: '연령대를 선택해주세요',
      description: '고객의 연령대를 선택하면 해당 연령대에 맞는 시나리오가 제공됩니다.',
      type: 'selection',
      options: [
        { id: '20s', label: '20대', icon: '🎓', description: '대학생, 신입사원' },
        { id: '30s', label: '30대', icon: '💼', description: '직장인, 신혼부부' },
        { id: '40s', label: '40대', icon: '👨‍👩‍👧‍👦', description: '경력직, 자녀 양육기' },
        { id: '50s', label: '50대', icon: '🏠', description: '중간 관리직, 자녀 독립기' },
        { id: 'senior', label: '60대 이상', icon: '🌅', description: '은퇴자, 노후 준비기' }
      ],
      required: true
    },
    {
      id: 'occupation',
      title: '직업을 선택해주세요',
      description: '고객의 직업에 따라 다른 상담 스타일이 적용됩니다.',
      type: 'selection',
      options: [
        { id: 'student', label: '학생', icon: '🎓', description: '대학생, 대학원생' },
        { id: 'employee', label: '직장인', icon: '💼', description: '회사원, 공무원' },
        { id: 'self_employed', label: '자영업자', icon: '🏪', description: '사업자, 프리랜서' },
        { id: 'retired', label: '은퇴자', icon: '🌅', description: '퇴직자, 노후자' },
        { id: 'foreigner', label: '외국인', icon: '🌍', description: '외국인 고객' }
      ],
      required: true
    },
    {
      id: 'financial_literacy',
      title: '금융 이해도를 선택해주세요',
      description: '고객의 금융 지식 수준에 따라 설명 방식을 조정합니다.',
      type: 'selection',
      options: [
        { id: 'low', label: '낮음', icon: '📚', description: '기초적인 설명이 필요' },
        { id: 'medium', label: '중간', icon: '📖', description: '일반적인 수준의 설명' },
        { id: 'high', label: '높음', icon: '🎯', description: '전문적인 설명 가능' }
      ],
      required: true
    },
    {
      id: 'customer_type',
      title: '고객 타입을 선택해주세요',
      description: '고객의 성격과 선호하는 소통 방식을 선택해주세요.',
      type: 'selection',
      options: [
        { id: 'practical', label: '실용형', icon: '⚡', description: '빠르고 간결한 설명 선호' },
        { id: 'conservative', label: '보수형', icon: '🛡️', description: '안정성 중시' },
        { id: 'angry', label: '불만형', icon: '😤', description: '감정적 대응 필요' },
        { id: 'positive', label: '긍정형', icon: '😊', description: '친근한 톤 선호' },
        { id: 'impatient', label: '급함형', icon: '⏰', description: '시간 압박 강조' }
      ],
      required: true
    },
    {
      id: 'business_category',
      title: '업무 카테고리를 선택해주세요',
      description: '어떤 업무에 대한 시뮬레이션을 진행할지 선택해주세요.',
      type: 'selection',
      options: [
        { id: '수신', label: '수신', icon: '💰', description: '예금, 적금 상품' },
        { id: '여신', label: '여신', icon: '🏦', description: '대출, 신용 상품' },
        { id: '카드', label: '카드', icon: '💳', description: '신용카드, 체크카드' },
        { id: '외환/송금', label: '외환/송금', icon: '🌍', description: '해외송금, 외환거래' },
        { id: '디지털 뱅킹', label: '디지털 뱅킹', icon: '📱', description: '인터넷/모바일 뱅킹' },
        { id: '민원/불만 처리', label: '민원/불만 처리', icon: '📞', description: '고객 민원 해결' }
      ],
      required: true
    },
    {
      id: 'difficulty',
      title: '난이도를 선택해주세요',
      description: '시뮬레이션의 난이도를 선택해주세요.',
      type: 'selection',
      options: [
        { id: 'easy', label: '쉬움', icon: '🟢', description: '단순 질문, 고객 반응 온화' },
        { id: 'normal', label: '보통', icon: '🟡', description: '중간 수준의 정책/규정 포함' },
        { id: 'hard', label: '어려움', icon: '🔴', description: '복합 질문 + 예외상황 발생' }
      ],
      required: true
    }
  ]

  const handleAnswer = (stepId: string, answer: any) => {
    setAnswers(prev => ({
      ...prev,
      [stepId]: answer.id || answer
    }))
  }

  const nextStep = () => {
    if (currentStep < steps.length - 1) {
      setCurrentStep(currentStep + 1)
    }
  }

  const prevStep = () => {
    if (currentStep > 0) {
      setCurrentStep(currentStep - 1)
    }
  }

  const startSimulation = async () => {
    try {
      setLoading(true)
      setError('')
      
      // 선택한 성별, 나이, 직업 등 정보
      const gender = answers.gender || 'male'
      const ageGroup = answers.age_group || '20s'
      const occupation = answers.occupation || 'student'
      const financialLiteracy = answers.financial_literacy || 'low'
      const customerType = answers.customer_type || 'practical'
      const businessCategory = answers.business_category || 'deposit'
      const difficulty = answers.difficulty || 'easy'
      
      console.log('시뮬레이션 시작 요청:', { gender, ageGroup, occupation, financialLiteracy, customerType, businessCategory, difficulty })
      
      // API를 통해 페르소나와 시나리오 ID를 조회
      // 1. 페르소나 조회
      const personaResponse = await api.get('/rag-simulation/personas', {
        params: {
          age_group: ageGroup,
          occupation: occupation,
          customer_type: customerType,
          gender: gender  // 성별 필터 추가
        }
      })
      
      const personas = personaResponse.data.personas || []
      if (personas.length === 0) {
        setError('조건에 맞는 페르소나를 찾을 수 없습니다.')
        return
      }
      
      // 첫 번째 페르소나 사용 (조건에 가장 잘 맞는 것)
      const selectedPersona = personas[0]
      const personaId = selectedPersona.persona_id
      
      console.log('선택된 페르소나:', selectedPersona)
      
      // 2. 시나리오 조회 - 카테고리 기반으로 랜덤 선택
      const scenarioResponse = await api.get('/rag-simulation/scenarios', {
        params: {
          category: businessCategory  // 카테고리만 필터링 (난이도 제외)
        }
      })
      
      let scenarios = scenarioResponse.data.scenarios || []
      
      // 카테고리에 맞는 시나리오가 없으면 전체 시나리오 조회
      if (scenarios.length === 0) {
        const allScenariosResponse = await api.get('/rag-simulation/scenarios')
        scenarios = allScenariosResponse.data.scenarios || []
      }
      
      if (scenarios.length === 0) {
        setError('조건에 맞는 시나리오를 찾을 수 없습니다.')
        return
      }
      
      // 랜덤으로 시나리오 선택
      const randomIndex = Math.floor(Math.random() * scenarios.length)
      const selectedScenario = scenarios[randomIndex]
      const scenarioId = selectedScenario.scenario_id
      
      console.log('선택된 시나리오:', selectedScenario)
      
      // RAG 시뮬레이션 시작 - 성별 정보 포함
      const response = await api.post('/rag-simulation/start-simulation', {
        persona_id: personaId,
        scenario_id: scenarioId,
        gender: gender
      })
      
      setSimulationResult(response.data)
      setShowVoiceSimulation(true) // 음성 시뮬레이션으로 이동
      
    } catch (error: any) {
      console.error('시뮬레이션 시작 실패:', error)
      
      // 인증 오류인 경우 로그인 페이지로 리다이렉트하지 않도록 처리
      if (error.response?.status === 401) {
        setError('로그인이 필요합니다. 다시 로그인해주세요.')
      } else if (error.response?.status === 400) {
        setError('요청 데이터가 올바르지 않습니다. 다시 시도해주세요.')
      } else {
        setError('시뮬레이션을 시작할 수 없습니다. 다시 시도해주세요.')
      }
    } finally {
      setLoading(false)
    }
  }

  const resetSimulation = () => {
    setCurrentStep(0)
    setAnswers({})
    setSimulationResult(null)
    setShowResult(false)
    setShowVoiceSimulation(false)
    setError('')
  }

  const handleBackFromVoice = () => {
    setShowVoiceSimulation(false)
  }

  // currentStep이 유효한 범위인지 확인
  if (currentStep < 0 || currentStep >= steps.length) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-red-50 to-pink-100 flex items-center justify-center p-6">
        <div className="bg-white rounded-lg shadow-lg p-8 text-center">
          <h1 className="text-2xl font-bold text-red-600 mb-4">오류가 발생했습니다</h1>
          <p className="text-gray-600 mb-4">시뮬레이션 단계를 찾을 수 없습니다.</p>
          <button
            onClick={resetSimulation}
            className="bg-blue-600 text-white px-6 py-3 rounded-lg hover:bg-blue-700 transition-colors"
          >
            처음부터 다시 시작
          </button>
        </div>
      </div>
    )
  }

  const currentStepData = steps[currentStep]
  const isLastStep = currentStep === steps.length - 1
  const canProceed = currentStepData && currentStepData.required ? !!answers[currentStepData.id] : true

  if (showVoiceSimulation && simulationResult) {
    // 음성 시뮬레이션 화면
    return (
      <VoiceSimulation 
        simulationData={simulationResult}
        onBack={handleBackFromVoice}
      />
    )
  }

  if (showResult) {
    // 결과 화면
    return (
      <div className="min-h-screen bg-gradient-to-br from-green-50 to-blue-100 flex items-center justify-center p-6">
        <div className="max-w-2xl w-full">
          <div className="bg-white rounded-2xl shadow-2xl p-8 text-center">
            <div className="mb-6">
              <CheckCircleIcon className="h-20 w-20 text-green-500 mx-auto mb-4" />
              <h1 className="text-3xl font-bold text-gray-900 mb-2">시뮬레이션 준비 완료!</h1>
              <p className="text-gray-600">선택하신 조건에 맞는 시뮬레이션이 준비되었습니다.</p>
            </div>
            
            <div className="bg-gray-50 rounded-lg p-6 mb-6">
              <h2 className="text-xl font-semibold text-gray-900 mb-4">선택된 조건</h2>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div><span className="font-medium">연령대:</span> {answers.age_group}</div>
                <div><span className="font-medium">직업:</span> {answers.occupation}</div>
                <div><span className="font-medium">금융 이해도:</span> {answers.financial_literacy}</div>
                <div><span className="font-medium">고객 타입:</span> {answers.customer_type}</div>
                <div><span className="font-medium">업무 카테고리:</span> {answers.business_category}</div>
                <div><span className="font-medium">난이도:</span> {answers.difficulty}</div>
              </div>
            </div>
            
            <div className="space-y-4">
              <button
                onClick={() => window.location.href = '/rag-simulation'}
                className="w-full bg-blue-600 text-white py-4 px-6 rounded-lg hover:bg-blue-700 transition-colors text-lg font-medium"
              >
                시뮬레이션 시작하기
              </button>
              
              <button
                onClick={resetSimulation}
                className="w-full bg-gray-500 text-white py-3 px-6 rounded-lg hover:bg-gray-600 transition-colors"
              >
                다시 선택하기
              </button>
            </div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-purple-50 to-blue-100 flex items-center justify-center p-6">
      <div className="max-w-4xl w-full">
        {/* 진행률 표시 */}
        <div className="mb-8">
          <div className="flex justify-between items-center mb-2">
            <span className="text-sm font-medium text-gray-600">
              {currentStep + 1} / {steps.length}
            </span>
            <span className="text-sm font-medium text-gray-600">
              {Math.round(((currentStep + 1) / steps.length) * 100)}%
            </span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div 
              className="bg-blue-600 h-2 rounded-full transition-all duration-300"
              style={{ width: `${((currentStep + 1) / steps.length) * 100}%` }}
            ></div>
          </div>
        </div>

        {/* 메인 콘텐츠 */}
        <div className="bg-white rounded-2xl shadow-2xl p-8">
          <div className="text-center mb-8">
            <h1 className="text-3xl font-bold text-gray-900 mb-2">
              {currentStepData.title}
            </h1>
            <p className="text-gray-600 text-lg">
              {currentStepData.description}
            </p>
          </div>

          {/* 선택 옵션들 */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
            {currentStepData.options?.map((option) => (
              <button
                key={option.id}
                onClick={() => handleAnswer(currentStepData.id, option)}
                className={`p-6 rounded-lg border-2 transition-all duration-200 text-left hover:shadow-lg ${
                  answers[currentStepData.id] === option.id
                    ? 'border-blue-500 bg-blue-50'
                    : 'border-gray-200 hover:border-gray-300'
                }`}
              >
                <div className="flex items-center mb-3">
                  <span className="text-2xl mr-3">{option.icon}</span>
                  <h3 className="text-lg font-semibold text-gray-900">{option.label}</h3>
                </div>
                <p className="text-gray-600 text-sm">{option.description}</p>
              </button>
            ))}
          </div>

          {/* 네비게이션 버튼 */}
          <div className="flex justify-between">
            <button
              onClick={prevStep}
              disabled={currentStep === 0}
              className="flex items-center px-6 py-3 bg-gray-500 text-white rounded-lg hover:bg-gray-600 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
            >
              <ChevronLeftIcon className="h-5 w-5 mr-2" />
              이전
            </button>

            {isLastStep ? (
              <button
                onClick={startSimulation}
                disabled={!canProceed || loading}
                className="flex items-center px-8 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
              >
                {loading ? (
                  <>
                    <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white mr-2" />
                    시뮬레이션 준비 중...
                  </>
                ) : (
                  <>
                    시뮬레이션 시작
                    <PlayIcon className="h-5 w-5 ml-2" />
                  </>
                )}
              </button>
            ) : (
              <button
                onClick={nextStep}
                disabled={!canProceed}
                className="flex items-center px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
              >
                다음
                <ChevronRightIcon className="h-5 w-5 ml-2" />
              </button>
            )}
          </div>

          {error && (
            <div className="mt-6 p-4 bg-red-50 border border-red-200 rounded-lg">
              <p className="text-red-600">{error}</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default IQStyleSimulation
