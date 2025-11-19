/**
 * 시뮬레이션 페이지
 * 신입사원을 위한 시뮬레이션 연습 공간
 */
import { useState, useEffect } from 'react'
import { useAuthStore } from '../store/authStore'
import { api } from '../utils/api'
import {
  PlayIcon,
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
import { motion } from 'framer-motion'

interface Scenario {
  id: number
  title: string
  description: string
  category: string
  difficulty: string
  estimated_duration: number
}

interface SimulationState {
  currentScenario: Scenario | null
  currentAttempt: any | null
  currentStep: number
  totalSteps: number
  currentScore: number
  isCompleted: boolean
}

interface Category {
  id: string
  name: string
  description: string
  icon: string
  difficulty_levels: string[]
}

const Simulation: React.FC = () => {
  const { user } = useAuthStore()
  const [scenarios, setScenarios] = useState<Scenario[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [selectedCategory, setSelectedCategory] = useState<string>('')
  const [selectedDifficulty, setSelectedDifficulty] = useState<string>('')
  const [simulationState, setSimulationState] = useState<SimulationState>({
    currentScenario: null,
    currentAttempt: null,
    currentStep: 0,
    totalSteps: 0,
    currentScore: 0,
    isCompleted: false
  })
  const [userResponse, setUserResponse] = useState('')
  const [userAction, setUserAction] = useState('')
  const [showResults, setShowResults] = useState(false)
  const [stepResults, setStepResults] = useState<any[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    loadSimulationData()
  }, [])

  const loadSimulationData = async () => {
    try {
      setLoading(true)
      
      // 시나리오 목록 로드
      const scenariosResponse = await api.get('/simulation/scenarios')
      setScenarios(scenariosResponse.data.scenarios || [])
      
      // 카테고리 목록 로드
      const categoriesResponse = await api.get('/simulation/categories')
      setCategories(categoriesResponse.data.categories || [])
      
    } catch (error) {
      console.error('시뮬레이션 데이터 로드 실패:', error)
    } finally {
      setLoading(false)
    }
  }

  const startSimulation = async (scenarioId: number) => {
    try {
      setLoading(true)
      const response = await api.post('/simulation/start', { scenario_id: scenarioId })
      const result = response.data
      
      setSimulationState({
        currentScenario: result.scenario,
        currentAttempt: result,
        currentStep: 0,
        totalSteps: result.total_steps,
        currentScore: 0,
        isCompleted: false
      })
      setShowResults(false)
      setStepResults([])
      
    } catch (error) {
      console.error('시뮬레이션 시작 실패:', error)
      alert('시뮬레이션을 시작할 수 없습니다.')
    } finally {
      setLoading(false)
    }
  }

  const submitStepResponse = async () => {
    if (!userResponse.trim()) {
      alert('응답을 입력해주세요.')
      return
    }

    try {
      setLoading(true)
      const response = await api.post('/simulation/submit-step', {
        attempt_id: simulationState.currentAttempt.attempt_id,
        step_number: simulationState.currentStep,
        user_response: userResponse,
        user_action: userAction
      })
      
      const result = response.data
      setStepResults([...stepResults, result.step_result])
      setSimulationState(prev => ({
        ...prev,
        currentStep: prev.currentStep + 1,
        currentScore: result.current_score,
        isCompleted: result.is_completed
      }))
      
      if (result.is_completed) {
        setShowResults(true)
      } else {
        setUserResponse('')
        setUserAction('')
      }
      
    } catch (error) {
      console.error('단계 응답 제출 실패:', error)
    } finally {
      setLoading(false)
    }
  }

  const resetSimulation = () => {
    setSimulationState({
      currentScenario: null,
      currentAttempt: null,
      currentStep: 0,
      totalSteps: 0,
      currentScore: 0,
      isCompleted: false
    })
    setUserResponse('')
    setUserAction('')
    setShowResults(false)
    setStepResults([])
  }

  const getDifficultyColor = (difficulty: string) => {
    switch (difficulty) {
      case '초급': return 'bg-green-100 text-green-800'
      case '중급': return 'bg-yellow-100 text-yellow-800'
      case '고급': return 'bg-red-100 text-red-800'
      default: return 'bg-gray-100 text-gray-800'
    }
  }

  const getScoreColor = (score: number) => {
    if (score >= 80) return 'text-green-600'
    if (score >= 60) return 'text-yellow-600'
    return 'text-red-600'
  }

  const filteredScenarios = scenarios.filter(scenario => {
    if (selectedCategory && scenario.category !== selectedCategory) return false
    if (selectedDifficulty && scenario.difficulty !== selectedDifficulty) return false
    return true
  })

  if (simulationState.currentScenario && !showResults) {
    // 시뮬레이션 진행 화면
    const scenario = simulationState.currentScenario
    const currentStepData = simulationState.currentAttempt?.current_step
    
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 p-6">
        <div className="max-w-4xl mx-auto">
          {/* 헤더 */}
          <div className="bg-white rounded-lg shadow-lg p-6 mb-6">
            <div className="flex items-center justify-between">
              <div>
                <h1 className="text-2xl font-bold text-gray-900">{scenario.title}</h1>
                <p className="text-gray-600 mt-2">{scenario.description}</p>
              </div>
              <button
                onClick={resetSimulation}
                className="px-4 py-2 bg-gray-500 text-white rounded-lg hover:bg-gray-600 transition-colors"
              >
                종료
              </button>
            </div>
            
            {/* 진행 상황 */}
            <div className="mt-6">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium text-gray-700">
                  진행 상황: {simulationState.currentStep + 1} / {simulationState.totalSteps}
                </span>
                <span className="text-sm font-medium text-gray-700">
                  현재 점수: <span className={getScoreColor(simulationState.currentScore)}>
                    {simulationState.currentScore.toFixed(1)}점
                  </span>
                </span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div 
                  className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                  style={{ width: `${((simulationState.currentStep + 1) / simulationState.totalSteps) * 100}%` }}
                />
              </div>
            </div>
          </div>

          {/* 현재 단계 */}
          {currentStepData && (
            <div className="bg-white rounded-lg shadow-lg p-6 mb-6">
              <div className="flex items-center mb-4">
                <AcademicCapIcon className="h-6 w-6 text-blue-600 mr-2" />
                <h2 className="text-xl font-semibold text-gray-900">
                  단계 {simulationState.currentStep + 1}
                </h2>
              </div>
              
              <div className="bg-gray-50 rounded-lg p-4 mb-6">
                <h3 className="font-medium text-gray-900 mb-2">상황 설명</h3>
                <p className="text-gray-700">{currentStepData.situation || currentStepData.question}</p>
              </div>

              {/* 고객 프로필 */}
              {currentStepData.customer_profile && (
                <div className="bg-blue-50 rounded-lg p-4 mb-6">
                  <h3 className="font-medium text-gray-900 mb-2">고객 정보</h3>
                  <div className="grid grid-cols-2 gap-4">
                    {Object.entries(currentStepData.customer_profile).map(([key, value]) => (
                      <div key={key} className="text-sm">
                        <span className="font-medium text-gray-600">{key}:</span>
                        <span className="ml-2 text-gray-900">{value as string}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* 응답 입력 */}
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    {currentStepData.type === 'action' ? '행동 선택' : '응답 입력'}
                  </label>
                  {currentStepData.type === 'action' ? (
                    <select
                      value={userAction}
                      onChange={(e) => setUserAction(e.target.value)}
                      className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    >
                      <option value="">행동을 선택하세요</option>
                      <option value="정기예금">정기예금 추천</option>
                      <option value="적금">적금 추천</option>
                      <option value="공감하고 차분하게 대응">공감하고 차분하게 대응</option>
                      <option value="시스템 확인">시스템 확인</option>
                    </select>
                  ) : (
                    <textarea
                      value={userResponse}
                      onChange={(e) => setUserResponse(e.target.value)}
                      placeholder="응답을 입력하세요..."
                      className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                      rows={4}
                    />
                  )}
                </div>

                <button
                  onClick={submitStepResponse}
                  disabled={loading || (!userResponse.trim() && !userAction)}
                  className="w-full bg-blue-600 text-white py-3 px-4 rounded-lg hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors flex items-center justify-center"
                >
                  {loading ? (
                    <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white" />
                  ) : (
                    <>
                      다음 단계
                      <ArrowRightIcon className="h-5 w-5 ml-2" />
                    </>
                  )}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    )
  }

  if (showResults && simulationState.isCompleted) {
    // 결과 화면
    const finalResult = stepResults[stepResults.length - 1]?.final_result
    
    return (
      <div className="min-h-screen bg-gradient-to-br from-green-50 to-blue-100 p-6">
        <div className="max-w-4xl mx-auto">
          <div className="bg-white rounded-lg shadow-lg p-8">
            <div className="text-center mb-8">
              <TrophyIcon className="h-16 w-16 text-yellow-500 mx-auto mb-4" />
              <h1 className="text-3xl font-bold text-gray-900 mb-2">시뮬레이션 완료!</h1>
              <p className="text-gray-600">수고하셨습니다. 결과를 확인해보세요.</p>
            </div>

            {/* 최종 점수 */}
            <div className="bg-gradient-to-r from-blue-500 to-purple-600 rounded-lg p-6 text-white mb-8">
              <div className="flex items-center justify-center space-x-8">
                <div className="text-center">
                  <div className="text-4xl font-bold">{simulationState.currentScore.toFixed(1)}</div>
                  <div className="text-sm opacity-90">최종 점수</div>
                </div>
                <div className="text-center">
                  <div className="text-4xl font-bold">{finalResult?.grade || 'A'}</div>
                  <div className="text-sm opacity-90">등급</div>
                </div>
                <div className="text-center">
                  <div className="text-4xl font-bold">{simulationState.totalSteps}</div>
                  <div className="text-sm opacity-90">총 단계</div>
                </div>
              </div>
            </div>

            {/* 단계별 결과 */}
            <div className="mb-8">
              <h2 className="text-xl font-semibold text-gray-900 mb-4">단계별 결과</h2>
              <div className="space-y-4">
                {stepResults.map((result, index) => (
                  <div key={index} className="border border-gray-200 rounded-lg p-4">
                    <div className="flex items-center justify-between mb-2">
                      <span className="font-medium text-gray-900">단계 {index + 1}</span>
                      <div className="flex items-center space-x-2">
                        {result.is_correct ? (
                          <CheckCircleIcon className="h-5 w-5 text-green-500" />
                        ) : (
                          <XCircleIcon className="h-5 w-5 text-red-500" />
                        )}
                        <span className={`font-medium ${getScoreColor(result.score)}`}>
                          {result.score}/{result.max_score}점
                        </span>
                      </div>
                    </div>
                    <p className="text-sm text-gray-600">{result.feedback}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* 피드백 */}
            {finalResult?.feedback && (
              <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 mb-8">
                <h3 className="font-medium text-gray-900 mb-2">종합 피드백</h3>
                <p className="text-gray-700">{finalResult.feedback}</p>
              </div>
            )}

            <div className="flex space-x-4">
              <button
                onClick={resetSimulation}
                className="flex-1 bg-blue-600 text-white py-3 px-4 rounded-lg hover:bg-blue-700 transition-colors"
              >
                다른 시뮬레이션 시작
              </button>
              <button
                onClick={() => window.location.href = '/dashboard'}
                className="flex-1 bg-gray-600 text-white py-3 px-4 rounded-lg hover:bg-gray-700 transition-colors"
              >
                대시보드로 이동
              </button>
            </div>
          </div>
        </div>
      </div>
    )
  }

  // 메인 화면 - 시나리오 목록
  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 p-6">
      <div className="max-w-6xl mx-auto">
        {/* 헤더 */}
        <div className="text-center mb-8">
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
          >
            <h1 className="text-4xl font-bold text-gray-900 mb-4">
              🎯 시뮬레이션 연습
            </h1>
            <p className="text-xl text-gray-600 mb-6">
              실제 업무 상황을 시뮬레이션하며 실무 능력을 향상시켜보세요
            </p>
          </motion.div>
        </div>

        {/* 필터 */}
        <div className="bg-white rounded-lg shadow-lg p-6 mb-8">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">카테고리</label>
              <select
                value={selectedCategory}
                onChange={(e) => setSelectedCategory(e.target.value)}
                className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              >
                <option value="">전체</option>
                {categories.map(category => (
                  <option key={category.id} value={category.name}>
                    {category.icon} {category.name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">난이도</label>
              <select
                value={selectedDifficulty}
                onChange={(e) => setSelectedDifficulty(e.target.value)}
                className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              >
                <option value="">전체</option>
                <option value="초급">초급</option>
                <option value="중급">중급</option>
                <option value="고급">고급</option>
              </select>
            </div>
            <div className="flex items-end">
              <button
                onClick={() => {
                  setSelectedCategory('')
                  setSelectedDifficulty('')
                }}
                className="w-full bg-gray-500 text-white py-3 px-4 rounded-lg hover:bg-gray-600 transition-colors"
              >
                필터 초기화
              </button>
            </div>
          </div>
        </div>

        {/* 시나리오 목록 */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredScenarios.map((scenario, index) => (
            <motion.div
              key={scenario.id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: index * 0.1 }}
              className="bg-white rounded-lg shadow-lg overflow-hidden hover:shadow-xl transition-shadow"
            >
              <div className="p-6">
                <div className="flex items-center justify-between mb-4">
                  <span className={`px-3 py-1 rounded-full text-sm font-medium ${getDifficultyColor(scenario.difficulty)}`}>
                    {scenario.difficulty}
                  </span>
                  <div className="flex items-center text-sm text-gray-500">
                    <ClockIcon className="h-4 w-4 mr-1" />
                    {scenario.estimated_duration}분
                  </div>
                </div>
                
                <h3 className="text-xl font-semibold text-gray-900 mb-3">
                  {scenario.title}
                </h3>
                
                <p className="text-gray-600 mb-4 line-clamp-3">
                  {scenario.description}
                </p>
                
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-500">
                    {scenario.category}
                  </span>
                  <button
                    onClick={() => startSimulation(scenario.id)}
                    disabled={loading}
                    className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 disabled:bg-gray-400 transition-colors flex items-center"
                  >
                    <PlayIcon className="h-4 w-4 mr-2" />
                    시작하기
                  </button>
                </div>
              </div>
            </motion.div>
          ))}
        </div>

        {filteredScenarios.length === 0 && !loading && (
          <div className="text-center py-12">
            <AcademicCapIcon className="h-16 w-16 text-gray-400 mx-auto mb-4" />
            <h3 className="text-xl font-medium text-gray-900 mb-2">시나리오가 없습니다</h3>
            <p className="text-gray-600">다른 필터 조건을 시도해보세요.</p>
          </div>
        )}

        {loading && (
          <div className="text-center py-12">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
            <p className="text-gray-600 mt-4">로딩 중...</p>
          </div>
        )}
      </div>
    </div>
  )
}

export default Simulation
