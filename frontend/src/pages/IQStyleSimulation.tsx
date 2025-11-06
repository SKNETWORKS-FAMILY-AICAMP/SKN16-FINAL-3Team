/**
 * IQ 테스트 스타일의 단계별 시뮬레이션 페이지
 * 랜덤/선택 모드를 지원하는 새로운 시뮬레이션 시스템
 */
import { useState } from 'react'
import { api } from '../utils/api'
import VoiceSimulation from './VoiceSimulation'

interface StepOption {
  id: string
  label: string
  icon: string
  description: string
}

interface SimulationStep {
  id: string
  title: string
  question: string
  options: StepOption[]
  required: boolean
  showIf?: (answers: Record<string, string>) => boolean
}

const IQStyleSimulation: React.FC = () => {
  const [currentStep, setCurrentStep] = useState(0)
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const [isLoading, setIsLoading] = useState(false)
  const [simulationData, setSimulationData] = useState<any>(null)
  const [showVoiceSimulation, setShowVoiceSimulation] = useState(false)

  const steps: SimulationStep[] = [
    {
      id: 'mode',
      title: '시뮬레이션 모드',
      question: '시뮬레이션 모드를 선택해주세요.',
      options: [
        { id: 'select', label: '선택 모드', icon: '🎯', description: '원하는 조건을 직접 선택' },
        { id: 'random', label: '랜덤 모드', icon: '🎲', description: '랜덤으로 조건 설정' }
      ],
      required: true
    },
    {
      id: 'gender',
      title: '고객 성별',
      question: '시뮬레이션할 고객의 성별을 선택해주세요.',
      options: [
        { id: '남성', label: '남성', icon: '👨', description: '남성 고객으로 시뮬레이션' },
        { id: '여성', label: '여성', icon: '👩', description: '여성 고객으로 시뮬레이션' },
        { id: 'random', label: '랜덤', icon: '🎲', description: '랜덤으로 선택' }
      ],
      required: true,
      showIf: (answers) => answers.mode === 'select'
    },
    {
      id: 'ageGroup',
      title: '연령대',
      question: '고객의 연령대를 선택해주세요.',
      options: [
        { id: '10대', label: '10대', icon: '🧒', description: '청소년 연령대' },
        { id: '20대', label: '20대', icon: '😊', description: '젊고 활기찬 연령대' },
        { id: '30대', label: '30대', icon: '😎', description: '안정적이고 성숙한 연령대' },
        { id: '40대', label: '40대', icon: '🧐', description: '경험이 풍부한 연령대' },
        { id: '50대', label: '50대', icon: '👨‍🦳', description: '안정적이고 신중한 연령대' },
        { id: '60대 이상', label: '60대 이상', icon: '👴', description: '인생 경험이 풍부한 연령대' },
        { id: 'random', label: '랜덤', icon: '🎲', description: '랜덤으로 선택' }
      ],
      required: true,
      showIf: (answers) => answers.mode === 'select'
    },
    {
      id: 'occupation',
      title: '직업',
      question: '고객의 직업을 선택해주세요.',
      options: [
        { id: '학생', label: '학생', icon: '🎓', description: '대학생 또는 대학원생' },
        { id: '무직', label: '무직', icon: '😴', description: '무직자' },
        { id: '직장인', label: '직장인', icon: '💼', description: '일반 회사원' },
        { id: '자영업자', label: '자영업자', icon: '💪', description: '개인사업자 또는 소상공인' },
        { id: '은퇴자', label: '은퇴자', icon: '🌴', description: '은퇴한 고객' },
        { id: 'random', label: '랜덤', icon: '🎲', description: '랜덤으로 선택' }
      ],
      required: true,
      showIf: (answers) => answers.mode === 'select'
    },
    {
      id: 'customerType',
      title: '고객 성향',
      question: '고객의 성향을 선택해주세요.',
      options: [
        { id: '불만형', label: '불만형', icon: '😠', description: '불만이 많고 까다로운 성향' },
        { id: '긍정형', label: '긍정형', icon: '😊', description: '밝고 긍정적인 성향' },
        { id: '급함형', label: '급함형', icon: '⏰', description: '시간에 쪽박하고 급한 성향' },
        { id: 'random', label: '랜덤', icon: '🎲', description: '랜덤으로 선택' }
      ],
      required: true,
      showIf: (answers) => answers.mode === 'select'
    },
    {
      id: 'businessCategory',
      title: '업무 카테고리',
      question: '시뮬레이션할 업무 카테고리를 선택해주세요.',
      options: [
        { id: 'deposit', label: '수신', icon: '💰', description: '예금, 적금, 자동이체 등' },
        { id: 'loan', label: '여신', icon: '💳', description: '대출, 신용대출, 담보대출 등' },
        { id: 'card', label: '카드', icon: '💳', description: '발급, 분실, 재발급, 결제 등' },
        { id: 'fx', label: '외환/송금', icon: '🌍', description: '환전, 해외송금 등' },
        { id: 'complaint', label: '민원/불만 처리', icon: '📢', description: '고객 민원 및 불만 처리' },
        { id: 'random', label: '랜덤', icon: '🎲', description: '랜덤으로 선택' }
      ],
      required: true,
      showIf: (answers) => answers.mode === 'select'
    }
  ]

  // 현재 단계 데이터 가져오기
  const currentStepData = steps[currentStep]

  // 진행 가능 여부 확인
  const canProceed = currentStepData && 
    (currentStepData.required ? !!answers[currentStepData.id] : true) &&
    (!currentStepData.showIf || currentStepData.showIf(answers))

  // 답변 처리
  const handleAnswer = (optionId: string) => {
    if (currentStepData) {
      const newAnswers = {
        ...answers,
        [currentStepData.id]: optionId
      }
      setAnswers(newAnswers)
      
      console.log(`Selected ${currentStepData.id}:`, optionId)
      console.log('Current answers:', newAnswers)
      console.log('Current step:', currentStep, 'Total steps:', steps.length)
    }
  }

  // 랜덤 값 선택 헬퍼
  const getRandomValue = (options: StepOption[]) => {
    const nonRandomOptions = options.filter(opt => opt.id !== 'random')
    return nonRandomOptions[Math.floor(Math.random() * nonRandomOptions.length)].id
  }

  // 랜덤 선택 처리
  const handleRandomSelection = () => {
    if (currentStepData) {
      const randomValue = getRandomValue(currentStepData.options)
      handleAnswer(randomValue)
    }
  }

  // 다음 단계로
  const handleNext = () => {
    if (currentStep < steps.length - 1) {
      let nextStep = currentStep + 1
      
      // showIf 조건을 만족하지 않는 단계는 건너뛰기
      while (nextStep < steps.length && steps[nextStep].showIf && !steps[nextStep].showIf!(answers)) {
        nextStep++
      }
      
      setCurrentStep(nextStep)
    }
  }

  // 이전 단계로
  const handlePrevious = () => {
    if (currentStep > 0) {
      let prevStep = currentStep - 1
      
      // showIf 조건을 만족하지 않는 단계는 건너뛰기
      while (prevStep >= 0 && steps[prevStep].showIf && !steps[prevStep].showIf!(answers)) {
        prevStep--
      }
      
      setCurrentStep(Math.max(0, prevStep))
    }
  }

  // 시뮬레이션 시작
  const startSimulation = async () => {
    try {
      setIsLoading(true)
      
      let finalAnswers = { ...answers }
      
      // 랜덤 모드인 경우 모든 값을 랜덤으로 설정
      if (answers.mode === 'random') {
        const genderOptions = steps.find(s => s.id === 'gender')?.options || []
        const ageOptions = steps.find(s => s.id === 'ageGroup')?.options || []
        const occupationOptions = steps.find(s => s.id === 'occupation')?.options || []
        const typeOptions = steps.find(s => s.id === 'customerType')?.options || []
        const categoryOptions = steps.find(s => s.id === 'businessCategory')?.options || []
        
        finalAnswers = {
          ...finalAnswers,
          gender: getRandomValue(genderOptions),
          ageGroup: getRandomValue(ageOptions),
          occupation: getRandomValue(occupationOptions),
          customerType: getRandomValue(typeOptions),
          businessCategory: getRandomValue(categoryOptions)
        }
      } else {
        // 선택 모드에서 랜덤 옵션이 선택된 경우 처리
        Object.keys(finalAnswers).forEach(key => {
          if (finalAnswers[key] === 'random') {
            const step = steps.find(s => s.id === key)
            if (step) {
              finalAnswers[key] = getRandomValue(step.options)
            }
          }
        })
      }
      
      console.log('Final answers after random processing:', finalAnswers)
      
      // API 호출로 persona와 situation ID 가져오기
      const personasResponse = await api.get('/rag-simulation/personas', {
        params: {
          age_group: finalAnswers.ageGroup,
          occupation: finalAnswers.occupation,
          customer_type: finalAnswers.customerType,
          gender: finalAnswers.gender
        }
      })
      
      console.log('Personas response:', personasResponse.data)
      
      if (!personasResponse.data.personas || personasResponse.data.personas.length === 0) {
        throw new Error('조건에 맞는 페르소나를 찾을 수 없습니다.')
      }
      
      // 랜덤으로 persona 선택
      const randomPersona = personasResponse.data.personas[Math.floor(Math.random() * personasResponse.data.personas.length)]
      const personaId = randomPersona.persona_id
      
      console.log('Selected persona:', randomPersona)
      
      // 비즈니스 카테고리에 따른 situation 가져오기
      const situationsResponse = await api.get('/rag-simulation/situations', {
        params: {
          category: finalAnswers.businessCategory
        }
      })
      
      console.log('Situations response:', situationsResponse.data)
      
      // 백엔드에서 { situations: [...], total_count: ... } 구조로 반환
      const situations = situationsResponse.data.situations || []
      console.log('Extracted situations:', situations)
      console.log('Situations length:', situations.length)
      
      if (!situations || situations.length === 0) {
        throw new Error('선택한 카테고리에 맞는 상황을 찾을 수 없습니다.')
      }
      
      // 랜덤으로 situation 선택
      const randomIndex = Math.floor(Math.random() * situations.length)
      console.log('Random index:', randomIndex, 'Array length:', situations.length)
      const randomSituation = situations[randomIndex]
      console.log('Random situation:', randomSituation)
      console.log('Random situation type:', typeof randomSituation)
      
      if (!randomSituation) {
        throw new Error('선택된 상황이 존재하지 않습니다.')
      }
      
      if (!randomSituation.id) {
        console.log('Situation keys:', Object.keys(randomSituation))
        throw new Error('선택된 상황에 ID가 없습니다.')
      }
      
      const situationId = randomSituation.id
      
      console.log('Selected situation:', randomSituation)
      
      // 시뮬레이션 시작
      const response = await api.post('/rag-simulation/start-simulation', {
        persona_id: personaId,
        situation_id: situationId,
        gender: finalAnswers.gender
      })
      
      console.log('Start simulation response:', response.data)
      
      // 시뮬레이션 데이터 저장
      setSimulationData(response.data)
      console.log('Setting showVoiceSimulation to true')
      setShowVoiceSimulation(true)
      console.log('showVoiceSimulation state should be true now')
      
    } catch (error) {
      console.error('시뮬레이션 시작 실패:', error)
      alert('시뮬레이션을 시작할 수 없습니다. 다시 시도해주세요.')
    } finally {
      setIsLoading(false)
    }
  }

  // VoiceSimulation 표시
  console.log('Render check - showVoiceSimulation:', showVoiceSimulation, 'simulationData:', !!simulationData)
  if (showVoiceSimulation && simulationData) {
    console.log('Rendering VoiceSimulation component')
    return <VoiceSimulation simulationData={simulationData} onBack={() => setShowVoiceSimulation(false)} />
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-purple-50">
      <div className="container mx-auto px-4 py-8">
        {/* 헤더 */}
        <div className="text-center mb-12">
          <h1 className="text-5xl font-bold text-gray-800 mb-4">
            🎯 은행 고객 시뮬레이션
          </h1>
          <p className="text-xl text-gray-600">
            단계별로 조건을 설정하여 맞춤형 시뮬레이션을 시작하세요
          </p>
        </div>

        {/* 진행 상황 표시 */}
        <div className="max-w-4xl mx-auto mb-12">
          <div className="flex items-center justify-between">
            {steps.map((step, index) => {
              const isActive = index === currentStep
              const isCompleted = index < currentStep || !!answers[step.id]
              const shouldShow = !step.showIf || step.showIf(answers)
              
              if (!shouldShow && answers.mode === 'select') return null
              
              return (
                <div key={step.id} className="flex items-center">
                  <div className={`w-12 h-12 rounded-full flex items-center justify-center text-white font-bold ${
                    isCompleted ? 'bg-green-500' : isActive ? 'bg-blue-500' : 'bg-gray-300'
                  }`}>
                    {isCompleted ? '✓' : index + 1}
                  </div>
                  {index < steps.length - 1 && (
                    <div className={`w-16 h-1 mx-2 ${
                      isCompleted ? 'bg-green-500' : 'bg-gray-300'
                    }`} />
                  )}
                </div>
              )
            })}
          </div>
        </div>

        {/* 현재 단계 내용 */}
        {currentStepData && (!currentStepData.showIf || currentStepData.showIf(answers)) && (
          <div className="max-w-4xl mx-auto">
            <div className="text-center mb-12">
              <h2 className="text-4xl font-bold text-gray-800 mb-4">
                {currentStepData.title}
              </h2>
              <p className="text-xl text-gray-600">
                {currentStepData.question}
              </p>
            </div>
            
            {(() => {
              const optionCount = currentStepData.options.length
              const isAgeGroup = currentStepData.id === 'ageGroup'
              
              // 연령대 특별 레이아웃: 3개-3개-1개
              if (isAgeGroup && optionCount === 7) {
                const firstThree = currentStepData.options.slice(0, 3)  // 10대, 20대, 30대
                const secondThree = currentStepData.options.slice(3, 6)  // 40대, 50대, 60대 이상
                const lastOne = currentStepData.options.slice(6)  // 랜덤
                
                return (
                  <div className="mb-12 space-y-6">
                    {/* 첫 번째 줄: 3개 */}
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-5xl mx-auto">
                      {firstThree.map((option) => {
                        const isRandomOption = option.id === 'random'
                        return (
                          <button
                            key={option.id}
                            onClick={() => handleAnswer(option.id)}
                            className={`p-8 rounded-2xl border-2 transition-all duration-300 hover:scale-105 ${
                              answers[currentStepData.id] === option.id
                                ? isRandomOption 
                                  ? 'border-purple-500 bg-purple-50 shadow-lg'
                                  : 'border-blue-500 bg-blue-50 shadow-lg'
                                : isRandomOption
                                  ? 'border-purple-200 bg-gradient-to-br from-purple-50 to-pink-50 hover:border-purple-300 hover:shadow-md'
                                  : 'border-gray-200 bg-white hover:border-blue-300 hover:shadow-md'
                            }`}
                          >
                            <div className="text-6xl mb-4">{option.icon}</div>
                            <h3 className={`text-2xl font-semibold mb-2 ${
                              isRandomOption ? 'text-purple-800' : 'text-gray-800'
                            }`}>
                              {option.label}
                            </h3>
                            <p className={`${
                              isRandomOption ? 'text-purple-600' : 'text-gray-600'
                            }`}>
                              {option.description}
                            </p>
                          </button>
                        )
                      })}
                    </div>
                    
                    {/* 두 번째 줄: 3개 (가운데 정렬) */}
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-5xl mx-auto">
                      {secondThree.map((option) => {
                        const isRandomOption = option.id === 'random'
                        return (
                          <button
                            key={option.id}
                            onClick={() => handleAnswer(option.id)}
                            className={`p-8 rounded-2xl border-2 transition-all duration-300 hover:scale-105 ${
                              answers[currentStepData.id] === option.id
                                ? isRandomOption 
                                  ? 'border-purple-500 bg-purple-50 shadow-lg'
                                  : 'border-blue-500 bg-blue-50 shadow-lg'
                                : isRandomOption
                                  ? 'border-purple-200 bg-gradient-to-br from-purple-50 to-pink-50 hover:border-purple-300 hover:shadow-md'
                                  : 'border-gray-200 bg-white hover:border-blue-300 hover:shadow-md'
                            }`}
                          >
                            <div className="text-6xl mb-4">{option.icon}</div>
                            <h3 className={`text-2xl font-semibold mb-2 ${
                              isRandomOption ? 'text-purple-800' : 'text-gray-800'
                            }`}>
                              {option.label}
                            </h3>
                            <p className={`${
                              isRandomOption ? 'text-purple-600' : 'text-gray-600'
                            }`}>
                              {option.description}
                            </p>
                          </button>
                        )
                      })}
                    </div>
                    
                    {/* 세 번째 줄: 1개 (가운데 정렬) */}
                    <div className="flex justify-center">
                      {lastOne.map((option) => {
                        const isRandomOption = option.id === 'random'
                        return (
                          <button
                            key={option.id}
                            onClick={() => handleAnswer(option.id)}
                            className={`w-full md:w-[300px] p-8 rounded-2xl border-2 transition-all duration-300 hover:scale-105 ${
                              answers[currentStepData.id] === option.id
                                ? isRandomOption 
                                  ? 'border-purple-500 bg-purple-50 shadow-lg'
                                  : 'border-blue-500 bg-blue-50 shadow-lg'
                                : isRandomOption
                                  ? 'border-purple-200 bg-gradient-to-br from-purple-50 to-pink-50 hover:border-purple-300 hover:shadow-md'
                                  : 'border-gray-200 bg-white hover:border-blue-300 hover:shadow-md'
                            }`}
                          >
                            <div className="text-6xl mb-4">{option.icon}</div>
                            <h3 className={`text-2xl font-semibold mb-2 ${
                              isRandomOption ? 'text-purple-800' : 'text-gray-800'
                            }`}>
                              {option.label}
                            </h3>
                            <p className={`${
                              isRandomOption ? 'text-purple-600' : 'text-gray-600'
                            }`}>
                              {option.description}
                            </p>
                          </button>
                        )
                      })}
                    </div>
                  </div>
                )
              }
              
              // 일반 레이아웃: 옵션 개수에 따라 조정
              let gridClass = ''
              let itemClass = ''
              
              if (optionCount === 2) {
                // 2개: flex로 가운데 정렬, 각 옵션은 고정 너비
                gridClass = 'flex flex-wrap justify-center gap-6 mb-12'
                itemClass = 'w-full md:w-[400px]'
              } else if (optionCount === 4) {
                // 4개: 2x2 그리드 (고객 성향)
                gridClass = 'grid grid-cols-1 md:grid-cols-2 gap-6 mb-12 max-w-3xl mx-auto'
              } else if (optionCount === 6) {
                // 6개: 2x3 그리드 (업무 카테고리)
                gridClass = 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-12 max-w-5xl mx-auto'
              } else {
                // 기본: 3열 그리드
                gridClass = 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-12'
              }
              
              return (
                <div className={gridClass}>
                  {currentStepData.options.map((option) => {
                    const isRandomOption = option.id === 'random'
                    
                    return (
                      <button
                        key={option.id}
                        onClick={() => handleAnswer(option.id)}
                        className={`${itemClass} p-8 rounded-2xl border-2 transition-all duration-300 hover:scale-105 ${
                          answers[currentStepData.id] === option.id
                            ? isRandomOption 
                              ? 'border-purple-500 bg-purple-50 shadow-lg'
                              : 'border-blue-500 bg-blue-50 shadow-lg'
                            : isRandomOption
                              ? 'border-purple-200 bg-gradient-to-br from-purple-50 to-pink-50 hover:border-purple-300 hover:shadow-md'
                              : 'border-gray-200 bg-white hover:border-blue-300 hover:shadow-md'
                        }`}
                      >
                        <div className="text-6xl mb-4">{option.icon}</div>
                        <h3 className={`text-2xl font-semibold mb-2 ${
                          isRandomOption ? 'text-purple-800' : 'text-gray-800'
                        }`}>
                          {option.label}
                        </h3>
                        <p className={`${
                          isRandomOption ? 'text-purple-600' : 'text-gray-600'
                        }`}>
                          {option.description}
                        </p>
                      </button>
                    )
                  })}
                </div>
              )
            })()}
          </div>
        )}

        {/* 네비게이션 버튼 */}
        <div className="flex justify-center space-x-6">
          {currentStep > 0 && (
            <button
              onClick={handlePrevious}
              className="px-8 py-4 bg-gray-600 text-white text-xl font-semibold rounded-xl hover:bg-gray-700 transition-colors duration-300 shadow-lg hover:shadow-xl"
            >
              이전 단계
            </button>
          )}
          
          {/* 다음 단계 버튼 조건 개선 */}
          {(() => {
            // 기본 조건: 현재 단계가 마지막이 아니고, 진행 가능하고, showIf 조건 만족
            const basicCondition = currentStep < steps.length - 1 && canProceed && (!currentStepData?.showIf || currentStepData.showIf(answers))
            
            // 선택 모드에서 마지막 단계가 아닌 경우
            if (answers.mode === 'select') {
              return basicCondition
            }
            
            // 랜덤 모드에서는 mode 선택 후 바로 시뮬레이션 시작 가능하므로 다음 단계 버튼 숨김
            if (answers.mode === 'random' && currentStep >= 1) {
              return false
            }
            
            return basicCondition
          })() && (
            <button
              onClick={handleNext}
              className="px-8 py-4 bg-blue-600 text-white text-xl font-semibold rounded-xl hover:bg-blue-700 transition-colors duration-300 shadow-lg hover:shadow-xl"
            >
              다음 단계
            </button>
          )}
          
          {/* 시뮬레이션 시작 버튼 조건 개선 */}
          {(() => {
            // 랜덤 모드: mode만 선택하면 시작 가능
            if (answers.mode === 'random' && currentStep >= 1) {
              console.log('랜덤 모드 - 시뮬레이션 시작 버튼 표시')
              return true
            }
            
            // 선택 모드: 모든 필수 단계 완료 확인
            if (answers.mode === 'select') {
              const requiredSteps = ['mode', 'gender', 'ageGroup', 'occupation', 'customerType', 'businessCategory']
              const completedSteps = requiredSteps.filter(stepId => answers[stepId])
              console.log('선택 모드 - 완료된 단계:', completedSteps.length, '/', requiredSteps.length)
              console.log('완료된 단계들:', completedSteps)
              return completedSteps.length === requiredSteps.length
            }
            
            console.log('시뮬레이션 시작 버튼 숨김 - mode:', answers.mode, 'currentStep:', currentStep)
            return false
          })() && (
            <button
              onClick={startSimulation}
              disabled={isLoading}
              className="px-12 py-6 bg-green-600 text-white text-2xl font-bold rounded-xl hover:bg-green-700 transition-colors duration-300 shadow-lg hover:shadow-xl disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isLoading ? '시뮬레이션 준비 중...' : '🚀 시뮬레이션 시작'}
            </button>
          )}
        </div>

        {/* 선택된 답변 요약 (랜덤 모드가 아닐 때만) */}
        {answers.mode === 'select' && Object.keys(answers).length > 1 && (
          <div className="max-w-2xl mx-auto mt-12 p-6 bg-white rounded-2xl shadow-lg">
            <h3 className="text-2xl font-bold text-gray-800 mb-4 text-center">선택한 조건</h3>
            <div className="space-y-2">
              {Object.entries(answers).map(([key, value]) => {
                const step = steps.find(s => s.id === key)
                const option = step?.options.find(o => o.id === value)
                if (!step || !option || key === 'mode') return null
                
                return (
                  <div key={key} className="flex justify-between items-center">
                    <span className="text-gray-600">{step.title}:</span>
                    <span className="font-semibold text-gray-800">{option.label}</span>
                  </div>
                )
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default IQStyleSimulation