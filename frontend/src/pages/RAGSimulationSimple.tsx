/**
 * 간단한 RAG 시뮬레이션 페이지 (테스트용)
 */
import { useState, useEffect } from 'react'
import { useAuthStore } from '../store/authStore'
import { api } from '../utils/api'

const RAGSimulationSimple: React.FC = () => {
  const { user } = useAuthStore()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

  useEffect(() => {
    setMessage('RAG 시뮬레이션 페이지가 로드되었습니다!')
  }, [])

  const testAPI = async () => {
    try {
      setLoading(true)
      setError('')
      
      const response = await api.get('/rag-simulation/personas')
      setMessage(`API 테스트 성공: ${response.data.personas.length}개의 페르소나 로드됨`)
      
    } catch (error) {
      console.error('API 테스트 실패:', error)
      setError('API 테스트 실패: ' + error)
    } finally {
      setLoading(false)
    }
  }

  const startSimulation = async () => {
    try {
      setLoading(true)
      setError('')
      
      // 간단한 시뮬레이션 시작
      const response = await api.post('/rag-simulation/start-simulation', {
        persona_id: 'p_20s_student_lowlit_practical',
        scenario_id: 'sc_easy_0001_p_30s_foreigner_lowlit_conservative_s_deposit_installment_open'
      })
      
      setMessage(`시뮬레이션 시작 성공! 세션 ID: ${response.data.session_id}`)
      
    } catch (error) {
      console.error('시뮬레이션 시작 실패:', error)
      setError('시뮬레이션 시작 실패: ' + (error.response?.data?.detail || error.message))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-purple-50 to-blue-100 p-6">
      <div className="max-w-4xl mx-auto">
        {/* 헤더 */}
        <div className="bg-white rounded-lg shadow-lg p-6 mb-6">
          <h1 className="text-3xl font-bold text-gray-900 mb-4">
            🎯 RAG 기반 음성 시뮬레이션 (테스트)
          </h1>
          <p className="text-gray-600">
            현재 사용자: {user?.username} ({user?.role})
          </p>
        </div>

        {/* 메시지 */}
        <div className="bg-white rounded-lg shadow-lg p-6 mb-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">상태</h2>
          <p className="text-gray-700">{message}</p>
        </div>

        {/* API 테스트 */}
        <div className="bg-white rounded-lg shadow-lg p-6 mb-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">API 테스트</h2>
          <div className="space-x-4">
            <button
              onClick={testAPI}
              disabled={loading}
              className="bg-blue-600 text-white px-6 py-3 rounded-lg hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
            >
              {loading ? '테스트 중...' : '페르소나 API 테스트'}
            </button>
            <button
              onClick={startSimulation}
              disabled={loading}
              className="bg-green-600 text-white px-6 py-3 rounded-lg hover:bg-green-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
            >
              {loading ? '시작 중...' : '시뮬레이션 시작'}
            </button>
          </div>
        </div>

        {/* 오류 메시지 */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4">
            <p className="text-red-600">{error}</p>
          </div>
        )}
      </div>
    </div>
  )
}

export default RAGSimulationSimple
