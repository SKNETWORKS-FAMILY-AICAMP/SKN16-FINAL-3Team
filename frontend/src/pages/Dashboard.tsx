/**
 * 대시보드 페이지
 * 멘티/멘토별 맞춤 대시보드
 */
import { useState, useEffect, useRef } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'
import { dashboardAPI, adminAPI } from '../utils/api'
import { 
  UserIcon,
  AcademicCapIcon,
  ChatBubbleLeftRightIcon,
  PaperAirplaneIcon,
  TrashIcon,
  ChatBubbleBottomCenterTextIcon,
  TrophyIcon,
  EyeIcon,
  PencilIcon,
  ChartBarIcon,
  LightBulbIcon,
  StarIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  PlusIcon,
  UserGroupIcon,
  CheckCircleIcon,
  XCircleIcon,
  InformationCircleIcon,
  XMarkIcon,
  CalendarIcon,
  ArrowUpIcon,
  ArrowTrendingUpIcon
} from '@heroicons/react/24/outline'
import { 
  RadarChart, 
  PolarGrid, 
  PolarAngleAxis, 
  PolarRadiusAxis, 
  Radar, 
  ResponsiveContainer,
  Tooltip,
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Legend
} from 'recharts'
import { motion } from 'framer-motion'
import api from '../utils/api'
import { toKST, formatKSTDateWithDay, formatKSTTime, formatKSTDateTime } from '../utils/datetime'

// 피드백 페이지네이션 컴포넌트
const FeedbackPagination = ({ feedback }: { feedback: string }) => {
  const [currentPage, setCurrentPage] = useState(0)
  const cardsPerPage = 2 // 한 페이지에 보여줄 카드 수 (가로로 넓은 형태)
  
  // 피드백을 헤더와 섹션으로 분리
  const parseFeedbackSections = (feedback: string) => {
    const lines = feedback.split('\n')
    let header = ''
    let footer = ''
    const sections: string[] = []
    let currentSection = ''
    
    // 헤더 부분 추출 (신희정님의 시험 결과 분석, 총점, 개선이 필요한 영역까지)
    let headerEndIndex = -1
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i].trim()
      if (line.startsWith('🎯 개선이 필요한 영역:')) {
        headerEndIndex = i
        break
      }
    }
    
    if (headerEndIndex >= 0) {
      header = lines.slice(0, headerEndIndex + 1).join('\n')
    }
    
    // 종합 평가 부분 찾기
    let footerStartIndex = -1
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i].trim()
      if (line.startsWith('💡 종합 평가:')) {
        footerStartIndex = i
        break
      }
    }
    
    // 문제별로 분리 (은행업무 - BO014 (95점), 상품지식 - PK032 (100점) 등) - 종합 평가 제외
    const endIndex = footerStartIndex >= 0 ? footerStartIndex : lines.length
    for (let i = headerEndIndex + 1; i < endIndex; i++) {
      const line = lines[i]
      // 문제 시작 (은행업무 - BO014 (95점), 상품지식 - PK032 (100점) 등)
      if (line.trim().match(/^[가-힣]+ - [A-Z]{2}\d+ \(\d+점\)$/)) {
        if (currentSection.trim()) {
          sections.push(currentSection.trim())
        }
        currentSection = line + '\n'
      } else {
        currentSection += line + '\n'
      }
    }
    
    // 마지막 섹션 추가
    if (currentSection.trim()) {
      sections.push(currentSection.trim())
    }
    
    // 종합 평가 부분 추출
    if (footerStartIndex >= 0) {
      footer = lines.slice(footerStartIndex).join('\n')
    }
    
    return { header, sections, footer }
  }
  
  const { header, sections, footer } = parseFeedbackSections(feedback)
  
  // 페이지네이션 계산
  const totalPages = Math.ceil(sections.length / cardsPerPage)
  const startIndex = currentPage * cardsPerPage
  const endIndex = startIndex + cardsPerPage
  const currentSections = sections.slice(startIndex, endIndex)
  
  const renderFeedbackLine = (line: string, index: number) => {
    if (line.trim().startsWith('•')) {
      return (
        <div key={index} className="ml-4 text-gray-600">
          {line.replace('•', '◦')}
        </div>
      )
    } else if (line.trim().startsWith('🎯') || line.trim().startsWith('💡')) {
      return (
        <div key={index} className="font-semibold text-gray-800 mt-4 mb-2">
          {line.replace(/[🎯💡]/g, '').trim()}
        </div>
      )
    } else if (line.trim().startsWith('📊')) {
      return (
        <div key={index} className="font-medium text-blue-600 mb-2">
          {line.replace(/[📊]/g, '').trim()}
        </div>
      )
    } else if (line.trim().match(/^\d+\./)) {
      return (
        <div key={index} className="font-semibold text-gray-800 mt-3 mb-1">
          {line}
        </div>
      )
    } else if (line.trim()) {
      return (
        <div key={index} className="text-gray-700">
          {line}
        </div>
      )
    }
    return null
  }
  
  if (sections.length === 0) return null
  
  return (
    <div className="mt-6">
      {/* 페이지네이션 영역 - 개선방안 피드백 내용만 */}
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-4">
        {/* 섹션 제목과 페이지네이션 컨트롤 */}
        <div className="flex items-center justify-between mb-6 pb-4 border-b border-gray-200">
          <div>
            <h4 className="font-semibold text-gray-800">개선 영역별 상세 내용</h4>
            <p className="text-sm text-gray-600 mt-1">각 영역별 학습 내용을 확인하세요</p>
          </div>
          <div className="flex items-center space-x-2">
            <span className="text-sm text-gray-600">
              {currentPage + 1} / {totalPages}
            </span>
            <div className="flex space-x-1">
              <button
                onClick={() => setCurrentPage(Math.max(0, currentPage - 1))}
                disabled={currentPage === 0}
                className="p-1 rounded-md bg-white border border-gray-300 disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
              >
                <ChevronLeftIcon className="w-4 h-4 text-gray-600" />
              </button>
              <button
                onClick={() => setCurrentPage(Math.min(totalPages - 1, currentPage + 1))}
                disabled={currentPage === totalPages - 1}
                className="p-1 rounded-md bg-white border border-gray-300 disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
              >
                <ChevronRightIcon className="w-4 h-4 text-gray-600" />
              </button>
            </div>
          </div>
        </div>
      
      {/* 섹션 내용 - 가로로 넓은 카드 형태로 표시 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {currentSections.map((section, index) => {
          const lines = section.split('\n')
          const rawTitle = lines[0] || `문제 ${startIndex + index + 1}`
          // 제목에서 문제 ID 제거 (예: "은행업무 - BO014 (95점)" -> "은행업무 (95점)")
          const title = rawTitle.replace(/ - [A-Z]{2}\d+/, '') // Remove problem ID
          const content = lines.slice(1)
          
          return (
            <div 
              key={startIndex + index}
              className="bg-white rounded-lg border border-gray-200 p-5 shadow-sm hover:shadow-md transition-shadow"
            >
              {/* 카드 헤더 */}
              <div className="flex items-center mb-4 pb-3 border-b border-gray-100">
                <div className="w-8 h-8 bg-gray-50 rounded-full flex items-center justify-center mr-3 border border-gray-200">
                  <span className="text-gray-700 font-semibold text-sm">{startIndex + index + 1}</span>
                </div>
                <h5 className="font-semibold text-gray-800 text-base">{title}</h5>
              </div>
              
              {/* 카드 내용 */}
              <div className="space-y-3 max-h-96 overflow-y-auto">
                {content.map((line, lineIndex) => {
                  if (line.trim().startsWith('📚')) {
                    return (
                      <div key={lineIndex} className="text-sm font-medium text-gray-700 mb-2 flex items-center">
                        <span className="text-gray-500 mr-2">📖</span>
                        <span className="text-gray-800">{line.replace('📚', '').trim()}</span>
                      </div>
                    )
                  } else if (line.trim().startsWith('•')) {
                    return (
                      <div key={lineIndex} className="text-sm text-gray-600 ml-3 flex items-start">
                        <span className="w-1.5 h-1.5 bg-gray-400 rounded-full mt-2 mr-2 flex-shrink-0"></span>
                        <span className="leading-relaxed">{line.replace('•', '').trim()}</span>
                      </div>
                    )
                  } else if (line.trim().startsWith('-')) {
                    return (
                      <div key={lineIndex} className="text-sm text-gray-500 ml-5 flex items-start">
                        <span className="w-1 h-1 bg-gray-300 rounded-full mt-2.5 mr-2 flex-shrink-0"></span>
                        <span className="leading-relaxed">{line.replace('-', '').trim()}</span>
                      </div>
                    )
                  } else if (line.trim()) {
                    return (
                      <div key={lineIndex} className="text-sm text-gray-700 leading-relaxed">
                        {line.trim()}
                      </div>
                    )
                  }
                  return null
                })}
              </div>
            </div>
          )
        })}
      </div>
      
      {/* 페이지 인디케이터 */}
      <div className="flex justify-center mt-6 space-x-2">
        {Array.from({ length: totalPages }, (_, index) => (
          <button
            key={index}
            onClick={() => setCurrentPage(index)}
            className={`w-2 h-2 rounded-full transition-colors ${
              index === currentPage ? 'bg-gray-600' : 'bg-gray-300'
            }`}
          />
        ))}
      </div>
      
        {/* 종합 평가 부분 - 하단 고정 */}
        {footer && (
          <div className="mt-6 pt-4 border-t border-gray-200">
            <div className="text-sm text-gray-700 leading-relaxed space-y-2">
              {footer.split('\n').map((line, index) => renderFeedbackLine(line, index))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default function Dashboard() {
  const { user } = useAuthStore()
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [currentTime, setCurrentTime] = useState(new Date())
  const [recordings, setRecordings] = useState<any[]>([]) // 시뮬레이션 녹화 목록
  
  // 관리자 매칭 관련 상태
  const [matchingData, setMatchingData] = useState<any>(null)
  const [showMatchingSection, setShowMatchingSection] = useState(false)
  const [selectedMentor, setSelectedMentor] = useState<any>(null)
  const [selectedMentee, setSelectedMentee] = useState<any>(null)
  const [showAssignModal, setShowAssignModal] = useState(false)
  const [assignNotes, setAssignNotes] = useState('')
  const [assigning, setAssigning] = useState(false)

  useEffect(() => {
    loadDashboard()
  }, [user])

  // 실시간 시간 업데이트 (30초마다)
  useEffect(() => {
    const interval = setInterval(() => {
      setCurrentTime(new Date())
    }, 30000) // 30초마다 업데이트

    return () => clearInterval(interval)
  }, [])

  const loadDashboard = async () => {
    try {
      setLoading(true)
      // 현재 시간을 정확하게 설정
      setCurrentTime(new Date())
      
      if (user?.role === 'mentee') {
        const dashboardData = await dashboardAPI.getMenteeDashboard()
        setData(dashboardData)
        
        // 멘티의 경우 녹화 목록도 함께 로드
        try {
          const recordingsData = await dashboardAPI.getMenteeRecordings()
          setRecordings(recordingsData.recordings || [])
        } catch (error) {
          console.error('Failed to load recordings:', error)
          setRecordings([])
        }
      } else if (user?.role === 'mentor') {
        const dashboardData = await dashboardAPI.getMentorDashboard()
        setData(dashboardData)
      } else if (user?.role === 'admin') {
        // 관리자는 매칭 대시보드 데이터 로드
        const response = await dashboardAPI.getMatchingDashboard()
        setMatchingData(response)
      }
    } catch (error) {
      console.error('Failed to load dashboard:', error)
    } finally {
      setLoading(false)
    }
  }

  // 관리자 매칭 관련 함수들
  const loadMatchingData = async () => {
    try {
      const response = await dashboardAPI.getMatchingDashboard()
      setMatchingData(response)
    } catch (error) {
      console.error('매칭 데이터 로드 실패:', error)
    }
  }

  const handleAssignClick = (mentor: any, mentee: any) => {
    setSelectedMentor(mentor)
    setSelectedMentee(mentee)
    setShowAssignModal(true)
  }

  const handleAssignConfirm = async () => {
    if (!selectedMentor || !selectedMentee) return

    try {
      setAssigning(true)
      await dashboardAPI.assignMentor(selectedMentee.id, selectedMentor.id, assignNotes || '')
      alert('멘토-멘티 매칭이 성공적으로 완료되었습니다!')
      setShowAssignModal(false)
      setAssignNotes('')
      await loadMatchingData() // 데이터 새로고침
    } catch (error) {
      console.error('매칭 실패:', error)
      alert('매칭에 실패했습니다.')
    } finally {
      setAssigning(false)
    }
  }

  const handleUnassign = async (relationId: number) => {
    if (!confirm('정말로 이 매칭을 해제하시겠습니까?')) return

    try {
      await dashboardAPI.unassignMentor(relationId)
      alert('매칭이 해제되었습니다.')
      await loadMatchingData() // 데이터 새로고침
    } catch (error) {
      console.error('매칭 해제 실패:', error)
      alert('매칭 해제에 실패했습니다.')
    }
  }

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
      </div>
    )
  }

  if (user?.role === 'mentee') {
          return <MenteeDashboard data={data} currentTime={currentTime} recordings={recordings} />
  } else if (user?.role === 'mentor') {
    return <MentorDashboard data={data} />
  } else if (user?.role === 'admin') {
      return (
        <AdminDashboard
          matchingData={matchingData}
          onAssignClick={handleAssignClick}
          onUnassign={handleUnassign}
          showMatchingSection={showMatchingSection}
          setShowMatchingSection={setShowMatchingSection}
          showAssignModal={showAssignModal}
          setShowAssignModal={setShowAssignModal}
          selectedMentor={selectedMentor}
          selectedMentee={selectedMentee}
          setSelectedMentee={setSelectedMentee}
          assignNotes={assignNotes}
          setAssignNotes={setAssignNotes}
          onAssignConfirm={handleAssignConfirm}
          assigning={assigning}
        />
      )
  }

  return null
}

function MenteeDashboard({ data, currentTime, recordings }: any) {
  const navigate = useNavigate()
  const location = useLocation()
  // location.state에서 activeTab 정보를 받아서 초기값 설정
  const [activeTab, setActiveTab] = useState<'dashboard' | 'simulation'>(
    location.state?.activeTab || 'dashboard'
  )
  const [feedbackHistory, setFeedbackHistory] = useState<any[]>([])
  const [allFeedbackHistory, setAllFeedbackHistory] = useState<any[]>([])  // 전체 데이터 보관
  const [loadingFeedback, setLoadingFeedback] = useState(false)
  const [currentPage, setCurrentPage] = useState(1)
  const itemsPerPage = 10
  const [selectedWeekOffset, setSelectedWeekOffset] = useState(0)  // 0: 이번주, -1: 지난주, -2: 2주전...
  
  // 6가지 지표 성적표 데이터
  const performanceData = [
    { skill: '은행업무', score: data?.performance_scores?.banking || 85 },
    { skill: '상품지식', score: data?.performance_scores?.product_knowledge || 78 },
    { skill: '고객응대', score: data?.performance_scores?.customer_service || 92 },
    { skill: '법규준수', score: data?.performance_scores?.compliance || 88 },
    { skill: 'IT활용', score: data?.performance_scores?.it_usage || 75 },
    { skill: '영업실적', score: data?.performance_scores?.sales_performance || 80 }
  ]
  
  // 최근 대화 더보기/접기 상태 관리 (index 기반)
  const [expandedChats, setExpandedChats] = useState<Record<number, boolean>>({})
  const toggleChatExpand = (idx: number) => {
    setExpandedChats(prev => ({ ...prev, [idx]: !prev[idx] }))
  }
  
  // 피드백 히스토리 로드
  useEffect(() => {
    loadFeedbackHistory()
  }, [])
  
  // 데이터 로드 후 자동으로 이번 주로 필터링
  useEffect(() => {
    if (allFeedbackHistory.length > 0 && selectedWeekOffset === 0) {
      filterByWeek(0)
    }
  }, [allFeedbackHistory])
  
  const loadFeedbackHistory = async () => {
    try {
      setLoadingFeedback(true)
      // 충분한 데이터 가져오기 (최대 100개)
      const response = await api.get('/rag-simulation/feedback-history?limit=100')
      const allData = response.data.history || []
      setAllFeedbackHistory(allData)
      setFeedbackHistory(allData)  // 초기에는 전체 데이터 표시
    } catch (error) {
      console.error('피드백 히스토리 로드 실패:', error)
    } finally {
      setLoadingFeedback(false)
    }
  }
  
  // 주차별 필터링 함수
  const filterByWeek = (weekOffset: number) => {
    const now = new Date()
    
    // 이번 주 월요일 계산
    const currentDay = now.getDay()  // 0(일) ~ 6(토)
    const mondayOffset = currentDay === 0 ? -6 : 1 - currentDay  // 월요일까지의 일수
    const thisMonday = new Date(now.getFullYear(), now.getMonth(), now.getDate() + mondayOffset)
    thisMonday.setHours(0, 0, 0, 0)
    
    // 선택한 주의 월요일
    const selectedMonday = new Date(thisMonday)
    selectedMonday.setDate(thisMonday.getDate() + (weekOffset * 7))
    
    // 선택한 주의 일요일
    const selectedSunday = new Date(selectedMonday)
    selectedSunday.setDate(selectedMonday.getDate() + 6)
    selectedSunday.setHours(23, 59, 59, 999)
    
    // 해당 주차 데이터만 필터링
    const filtered = allFeedbackHistory.filter(fb => {
      const fbDate = toKST(fb.created_at)
      return fbDate >= selectedMonday && fbDate <= selectedSunday
    })
    
    setFeedbackHistory(filtered)
    setSelectedWeekOffset(weekOffset)
    setCurrentPage(1)  // 페이지 1로 리셋
  }
  
  // 주차 레이블 생성
  const getWeekLabel = (weekOffset: number) => {
    const now = new Date()
    const currentDay = now.getDay()
    const mondayOffset = currentDay === 0 ? -6 : 1 - currentDay
    const thisMonday = new Date(now.getFullYear(), now.getMonth(), now.getDate() + mondayOffset)
    
    const selectedMonday = new Date(thisMonday)
    selectedMonday.setDate(thisMonday.getDate() + (weekOffset * 7))
    
    const selectedSunday = new Date(selectedMonday)
    selectedSunday.setDate(selectedMonday.getDate() + 6)
    
    const formatDate = (date: Date) => `${date.getMonth() + 1}/${date.getDate()}`
    
    if (weekOffset === 0) {
      return `이번 주 (${formatDate(selectedMonday)} ~ ${formatDate(selectedSunday)})`
    } else if (weekOffset === -1) {
      return `지난 주 (${formatDate(selectedMonday)} ~ ${formatDate(selectedSunday)})`
    } else {
      return `${Math.abs(weekOffset)}주 전 (${formatDate(selectedMonday)} ~ ${formatDate(selectedSunday)})`
    }
  }
  
  const viewFeedbackDetail = async (feedbackId: number) => {
    try {
      const response = await api.get(`/rag-simulation/feedback/${feedbackId}`)
      navigate('/simulation-feedback', {
        state: { 
          feedbackData: response.data.feedback,
          fromHistory: true // 히스토리에서 온 것을 표시
        }
      })
    } catch (error) {
      console.error('피드백 상세 조회 실패:', error)
      alert('피드백을 불러올 수 없습니다.')
    }
  }
  
  const getGrade = (score: number) => {
    if (score >= 90) return { grade: "A", color: "text-green-600", bg: "bg-green-50" }
    if (score >= 80) return { grade: "B", color: "text-blue-600", bg: "bg-blue-50" }
    if (score >= 70) return { grade: "C", color: "text-yellow-600", bg: "bg-yellow-50" }
    return { grade: "D", color: "text-red-600", bg: "bg-red-50" }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold text-gray-900">내 대시보드</h1>

      {/* 탭 네비게이션 */}
      <div className="bg-white rounded-xl shadow-md p-2">
        <div className="flex gap-2">
          <button
            onClick={() => setActiveTab('dashboard')}
            className={`flex-1 py-3 px-6 rounded-lg font-semibold transition-all ${
              activeTab === 'dashboard'
                ? 'bg-blue-600 text-white shadow-md'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            📊 학습 현황
          </button>
          <button
            onClick={() => setActiveTab('simulation')}
            className={`flex-1 py-3 px-6 rounded-lg font-semibold transition-all ${
              activeTab === 'simulation'
                ? 'bg-blue-600 text-white shadow-md'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            🎯 시뮬레이션
          </button>
        </div>
      </div>

      {/* 대시보드 탭 */}
      {activeTab === 'dashboard' && (
        <>
          {/* Stats Cards */}
      <div className="grid md:grid-cols-3 gap-6">
        <StatCard
          icon={ChatBubbleBottomCenterTextIcon}
          title="총 대화 수"
          value={data?.learning_progress?.total_chats || 0}
          color="primary"
        />
        <StatCard
          icon={AcademicCapIcon}
          title="학습 진행도"
          value={`${data?.learning_progress?.progress_percentage || 0}%`}
          color="amber"
        />
        <StatCard
          icon={TrophyIcon}
          title="최근 시험 점수"
          value={data?.exam_scores?.[0]?.total_score?.toFixed(1) || 'N/A'}
          color="bank"
        />
      </div>

      {/* Performance Radar Chart - 6가지 지표 성적표 */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="bg-white rounded-2xl shadow-lg p-8 border border-primary-100"
      >
        <div className="flex items-center mb-6">
          <img src="/assets/bear.png" alt="하경곰" className="w-8 h-8 mr-3 rounded-full" />
          <h2 className="text-2xl font-bold text-bank-800">성과 지표 분석</h2>
        </div>
        <div className="flex flex-col lg:flex-row gap-8">
          <div className="flex-1">
            <ResponsiveContainer width="100%" height={400}>
              <RadarChart data={performanceData}>
                <PolarGrid 
                  stroke="#e5e7eb" 
                  strokeWidth={1}
                />
                <PolarAngleAxis 
                  dataKey="skill" 
                  tick={{ fontSize: 12, fill: '#374151' }}
                  axisLine={{ stroke: '#9ca3af' }}
                />
                <PolarRadiusAxis 
                  angle={90} 
                  domain={[0, 100]} 
                  tick={{ fontSize: 10, fill: '#6b7280' }}
                  axisLine={false}
                  tickLine={{ stroke: '#d1d5db' }}
                />
                <Radar
                  name="점수"
                  dataKey="score"
                  stroke="#d4a574"
                  fill="#d4a574"
                  fillOpacity={0.3}
                  strokeWidth={2}
                  dot={{ r: 4, fill: '#d4a574' }}
                />
                <Tooltip 
                  formatter={(value: any) => [`${value}점`, '점수']}
                  labelFormatter={(label: string) => `지표: ${label}`}
                />
              </RadarChart>
            </ResponsiveContainer>
          </div>
          <div className="w-full lg:w-80">
            <div className="space-y-3">
              {performanceData.map((item, index) => (
                <div key={index} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                  <span className="text-sm font-medium text-gray-700">{item.skill}</span>
                  <div className="flex items-center space-x-2">
                    <div className="w-20 bg-gray-200 rounded-full h-2">
                      <div 
                        className="bg-gradient-to-r from-primary-500 to-primary-600 h-2 rounded-full transition-all duration-500"
                        style={{ width: `${item.score}%` }}
                      ></div>
                    </div>
                    <span className="text-sm font-bold text-gray-900 w-10 text-right">
                      {item.score}점
                    </span>
                  </div>
                </div>
              ))}
            </div>
            <div className="mt-6 p-4 bg-gradient-to-r from-primary-50 to-amber-50 rounded-xl border border-primary-200">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-primary-900">종합 점수</span>
                <span className="text-lg font-bold text-primary-600">
                  {(performanceData.reduce((sum, item) => sum + item.score, 0) / performanceData.length).toFixed(1)}점
                </span>
              </div>
            </div>
          </div>
        </div>
        {data?.exam_scores?.[0]?.feedback && (
          <FeedbackPagination feedback={data.exam_scores[0].feedback} />
        )}
      </motion.div>

      {/* Mentor Info */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="bg-white rounded-xl shadow-md p-6"
      >
        <h2 className="text-xl font-bold text-gray-900 mb-4">담당 멘토</h2>
        {data?.mentor_info ? (
          <div className="flex items-start space-x-4">
            {data.mentor_info.photo_url ? (
              <img
                src={data.mentor_info.photo_url}
                alt={data.mentor_info.name}
                className="w-16 h-16 rounded-full"
              />
            ) : (
              <div className="w-16 h-16 bg-primary-100 rounded-full flex items-center justify-center">
                <UserIcon className="w-8 h-8 text-primary-600" />
              </div>
            )}
            <div className="flex-1">
              <h3 className="text-lg font-semibold text-gray-900">{data.mentor_info.name}</h3>
              <p className="text-gray-600 text-sm">
                {data.mentor_info.team} • MBTI: {data.mentor_info.mbti}
              </p>
              {data.mentor_info.interests && (
                <p className="text-gray-600 text-sm mt-1">관심사: {data.mentor_info.interests}</p>
              )}
              {data.mentor_info.encouragement_message && (
                <div className="mt-3 p-4 bg-gradient-to-r from-primary-50 to-amber-50 rounded-xl border border-primary-200">
                  <p className="text-primary-800 text-sm italic">
                    "{data.mentor_info.encouragement_message}"
                  </p>
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className="text-center py-8">
            <UserIcon className="w-16 h-16 text-gray-300 mx-auto mb-4" />
            <p className="text-gray-500 text-lg mb-2">아직 담당 멘토가 배정되지 않았습니다</p>
            <p className="text-gray-400 text-sm">관리자에게 멘토 배정을 요청해보세요</p>
          </div>
        )}
      </motion.div>

      {/* Recent Feedbacks */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="bg-white rounded-xl shadow-md p-6"
      >
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center">
            <img src="/assets/bear.png" alt="하경곰" className="w-8 h-8 mr-3 rounded-full" />
            <h2 className="text-2xl font-bold text-bank-800">멘토 피드백</h2>
          </div>
          {data?.recent_feedbacks && data.recent_feedbacks.length > 0 && (
            <div className="flex items-center space-x-2">
              <span className="text-sm text-gray-500">총 {data.recent_feedbacks.length}개</span>
              {(() => {
                const recentCount = data.recent_feedbacks.filter((f: any) => {
                  const feedbackDate = toKST(f.created_at)
                  const diffInHours = (currentTime.getTime() - feedbackDate.getTime()) / (1000 * 60 * 60)
                  return diffInHours <= 24 && !f.is_read
                }).length
                
                if (recentCount > 0) {
                  return (
                    <span className="px-2 py-1 bg-accent-100 text-accent-800 text-xs rounded-full animate-pulse">
                      최신 피드백 {recentCount}개
                    </span>
                  )
                } else if (data.recent_feedbacks.filter((f: any) => !f.is_read).length > 0) {
                  return (
                    <span className="px-2 py-1 bg-primary-100 text-primary-800 text-xs rounded-full">
                      새 피드백 {data.recent_feedbacks.filter((f: any) => !f.is_read).length}개
                    </span>
                  )
                }
                return null
              })()}
            </div>
          )}
        </div>
        {data?.recent_feedbacks && data.recent_feedbacks.length > 0 ? (
          <div className="space-y-4">
            {data.recent_feedbacks.slice(0, 5).map((feedback: any, idx: number) => {
              const feedbackDate = toKST(feedback.created_at)
              const diffInHours = (currentTime.getTime() - feedbackDate.getTime()) / (1000 * 60 * 60)
              const isNew = diffInHours <= 24
              
              return (
                <div 
                  key={idx} 
                  className={`p-4 rounded-xl border transition-all ${
                    !feedback.is_read 
                      ? 'bg-gradient-to-r from-accent-50 to-accent-100 border-accent-300' 
                      : 'bg-gradient-to-r from-primary-50 to-amber-50 border-primary-100'
                  }`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <p className="text-xs text-gray-500">
                      {formatKSTDateTime(feedback.created_at)}
                    </p>
                    {isNew && !feedback.is_read && (
                      <span className="px-2 py-1 bg-accent-600 text-white text-xs rounded-full animate-pulse">
                        New
                      </span>
                    )}
                    {!isNew && !feedback.is_read && (
                      <span className="px-2 py-1 bg-primary-600 text-white text-xs rounded-full">
                        New
                      </span>
                    )}
                  </div>
                  <p className={`text-sm ${!feedback.is_read ? 'text-primary-900 font-semibold' : 'text-primary-700'}`}>
                    {feedback.feedback}
                  </p>
                </div>
              )
            })}
          </div>
        ) : (
          <div className="text-center py-8">
            <ChatBubbleLeftRightIcon className="w-16 h-16 text-gray-300 mx-auto mb-4" />
            <p className="text-gray-500 text-lg mb-2">아직 받은 피드백이 없습니다</p>
            <p className="text-gray-400 text-sm">멘토가 피드백을 보내면 여기에 표시됩니다</p>
          </div>
        )}
      </motion.div>

      {/* Recent Chats */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="bg-white rounded-xl shadow-md p-6"
      >
        <h2 className="text-xl font-bold text-gray-900 mb-4">최근 대화</h2>
        {data?.recent_chats && data.recent_chats.length > 0 ? (
          <div className="space-y-4">
            {data.recent_chats.slice(0, 5).map((chat: any, idx: number) => {
              const isExpanded = !!expandedChats[idx]
              const needsToggle = (chat?.bot_response?.length || 0) > 120
              return (
                <div key={idx} className="p-4 bg-gradient-to-r from-primary-50 to-amber-50 rounded-xl border border-primary-100">
                  <p className="font-medium text-bank-800 mb-1">{chat.user_message}</p>
                  <p className={isExpanded ? "text-sm text-primary-700 whitespace-prewrap" : "text-sm text-primary-700 line-clamp-2"}>
                    {chat.bot_response}
                  </p>
                  {needsToggle && (
                    <div className="mt-2 text-right">
                      <button
                        type="button"
                        onClick={() => toggleChatExpand(idx)}
                        className="text-amber-700 hover:text-amber-800 text-xs font-medium"
                      >
                        {isExpanded ? '접기' : '더보기'}
                      </button>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        ) : (
          <div className="text-center py-8">
            <ChatBubbleBottomCenterTextIcon className="w-16 h-16 text-gray-300 mx-auto mb-4" />
            <p className="text-gray-500 text-lg mb-2">아직 대화 기록이 없습니다</p>
            <p className="text-gray-400 text-sm">챗봇과 대화를 시작해보세요</p>
          </div>
        )}
      </motion.div>
      </>
      )}

      {/* 시뮬레이션 탭 */}
      {activeTab === 'simulation' && (
        <>
      {/* 시뮬레이션 피드백 히스토리 */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="bg-white rounded-xl shadow-md p-8"
      >
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-2xl font-bold text-gray-900">시뮬레이션 피드백 히스토리</h2>
          
          {/* 주차 선택 */}
          <div className="flex items-center gap-2">
            <button
              onClick={() => filterByWeek(selectedWeekOffset - 1)}
              disabled={selectedWeekOffset <= -4}  // 최대 4주 전까지
              className={`p-2 rounded-lg transition-all ${
                selectedWeekOffset <= -4
                  ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                  : 'bg-white text-gray-700 hover:bg-blue-50 border border-gray-200'
              }`}
            >
              <ChevronLeftIcon className="w-5 h-5" />
            </button>
            
            <div className="bg-gradient-to-r from-blue-50 to-purple-50 px-6 py-2 rounded-lg border border-blue-200">
              <p className="text-sm font-semibold text-blue-900">
                {getWeekLabel(selectedWeekOffset)}
              </p>
            </div>
            
            <button
              onClick={() => filterByWeek(selectedWeekOffset + 1)}
              disabled={selectedWeekOffset >= 0}  // 이번 주가 최대
              className={`p-2 rounded-lg transition-all ${
                selectedWeekOffset >= 0
                  ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                  : 'bg-white text-gray-700 hover:bg-blue-50 border border-gray-200'
              }`}
            >
              <ChevronRightIcon className="w-5 h-5" />
            </button>
            
            {selectedWeekOffset !== 0 && (
              <button
                onClick={() => filterByWeek(0)}
                className="ml-2 px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 transition-all"
              >
                이번 주
              </button>
            )}
          </div>
        </div>
        {loadingFeedback ? (
          <div className="text-center py-8">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
            <p className="text-gray-600 mt-4">로딩 중...</p>
          </div>
        ) : feedbackHistory.length > 0 ? (
          <>
          {/* 주요 통계 카드 */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="bg-white rounded-xl shadow-md p-6"
            >
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-gray-600 mb-2">주별 평균 점수</p>
                  <div className="flex items-end gap-2">
                    <span className="text-4xl font-bold text-blue-600">
                      {Math.round(feedbackHistory.reduce((sum, fb) => sum + fb.overall_score, 0) / feedbackHistory.length)}
                    </span>
                    <span className="text-gray-500 mb-1">점</span>
                  </div>
                </div>
                <div className="p-3 bg-blue-100 rounded-lg">
                  <TrophyIcon className="w-6 h-6 text-blue-600" />
                </div>
              </div>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="bg-white rounded-xl shadow-md p-6"
            >
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-gray-600 mb-2">주간 시뮬레이션 수</p>
                  <div className="flex items-end gap-2">
                    <span className="text-4xl font-bold text-purple-600">{feedbackHistory.length}</span>
                    <span className="text-gray-500 mb-1">회</span>
                  </div>
                </div>
                <div className="p-3 bg-purple-100 rounded-lg">
                  <CalendarIcon className="w-6 h-6 text-purple-600" />
                </div>
              </div>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="bg-white rounded-xl shadow-md p-6"
            >
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-gray-600 mb-2">주간 개선률</p>
                  <div className="flex items-end gap-2">
                    {(() => {
                      // 선택된 주차 데이터 사용 (feedbackHistory는 이미 필터링됨)
                      const weekData = feedbackHistory
                      
                      // 최소 2개 이상의 피드백이 필요
                      if (weekData.length >= 2) {
                        // 주간 데이터를 전반부와 후반부로 나누기
                        const midIndex = Math.ceil(weekData.length / 2)
                        const recentItems = weekData.slice(0, midIndex)
                        const olderItems = weekData.slice(midIndex)
                        
                        const recentAvg = recentItems.reduce((sum, fb) => sum + fb.overall_score, 0) / recentItems.length
                        const olderAvg = olderItems.reduce((sum, fb) => sum + fb.overall_score, 0) / olderItems.length
                        
                        // 0으로 나누기 방지
                        if (olderAvg > 0) {
                          const improvement = ((recentAvg - olderAvg) / olderAvg) * 100
                          const isPositive = improvement >= 0
                          const showMultiple = Math.abs(improvement) >= 100
                          const multiple = (Math.abs(improvement) / 100).toFixed(1)
                          
                          return (
                            <div className="flex flex-col items-start">
                              <div className="flex items-baseline gap-1">
                                <span className={`text-4xl font-bold ${isPositive ? 'text-green-600' : 'text-red-600'}`}>
                                  {isPositive ? '+' : ''}{Math.round(improvement)}
                                </span>
                                <span className="text-gray-500 text-lg">%</span>
                              </div>
                              <div className="flex flex-col mt-1">
                                {showMultiple && (
                                  <span className="text-sm text-gray-500 font-medium">
                                    ({multiple}배 {isPositive ? '향상' : '하락'})
                                  </span>
                                )}
                                <span className="text-xs text-gray-400 mt-0.5">
                                  주 전반 대비
                                </span>
                              </div>
                            </div>
                          )
                        }
                      }
                      
                      return <span className="text-2xl text-gray-400">N/A</span>
                    })()}
                  </div>
                </div>
                <div className={`p-3 ${
                  (() => {
                    const weekData = feedbackHistory
                    if (weekData.length >= 2) {
                      const midIndex = Math.ceil(weekData.length / 2)
                      const recentItems = weekData.slice(0, midIndex)
                      const olderItems = weekData.slice(midIndex)
                      const recentAvg = recentItems.reduce((sum, fb) => sum + fb.overall_score, 0) / recentItems.length
                      const olderAvg = olderItems.reduce((sum, fb) => sum + fb.overall_score, 0) / olderItems.length
                      
                      if (olderAvg > 0) {
                        const improvement = ((recentAvg - olderAvg) / olderAvg) * 100
                        return improvement >= 0 ? 'bg-green-100' : 'bg-red-100'
                      }
                    }
                    return 'bg-gray-100'
                  })()
                } rounded-lg`}>
                  <ArrowTrendingUpIcon className={`w-6 h-6 ${
                    (() => {
                      const weekData = feedbackHistory
                      if (weekData.length >= 2) {
                        const midIndex = Math.ceil(weekData.length / 2)
                        const recentItems = weekData.slice(0, midIndex)
                        const olderItems = weekData.slice(midIndex)
                        const recentAvg = recentItems.reduce((sum, fb) => sum + fb.overall_score, 0) / recentItems.length
                        const olderAvg = olderItems.reduce((sum, fb) => sum + fb.overall_score, 0) / olderItems.length
                        
                        if (olderAvg > 0) {
                          const improvement = ((recentAvg - olderAvg) / olderAvg) * 100
                          return improvement >= 0 ? 'text-green-600' : 'text-red-600'
                        }
                      }
                      return 'text-gray-400'
                    })()
                  }`} />
                </div>
              </div>
            </motion.div>
          </div>

          {/* 차트 섹션 */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 my-8">
            {/* 최근 시뮬레이션 점수 추이 */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="bg-gradient-to-br from-blue-50 to-white rounded-xl shadow-md p-6 border border-blue-100"
            >
              <h3 className="text-lg font-bold text-gray-900 mb-6 flex items-center gap-2">
                <div className="w-1 h-6 bg-blue-600 rounded-full"></div>
                주간 시뮬레이션 점수 추이
              </h3>
              <ResponsiveContainer width="100%" height={280}>
                <LineChart data={(() => {
                  if (feedbackHistory.length === 0) return []
                  
                  // 선택된 주차의 모든 데이터 사용 (이미 필터링됨)
                  const weekData = [...feedbackHistory].reverse()
                  
                  // 날짜 분포 확인 (몇 개의 서로 다른 날짜가 있는지)
                  const uniqueDates = [...new Set(weekData.map(fb => 
                    toKST(fb.created_at).toDateString()
                  ))]
                  
                  // 2일 이상에 걸쳐 있으면 → 날짜별 평균 점수 표시
                  if (uniqueDates.length > 1) {
                    const dailyData = new Map()
                    
                    // 날짜별로 점수들을 배열로 저장
                    weekData.forEach(fb => {
                      const dateKey = toKST(fb.created_at).toDateString()
                      if (!dailyData.has(dateKey)) {
                        dailyData.set(dateKey, [])
                      }
                      dailyData.get(dateKey).push(fb)
                    })
                    
                    // 각 날짜의 평균 점수 계산
                    return Array.from(dailyData.entries())
                      .map(([dateKey, feedbacks]) => {
                        const avgScore = feedbacks.reduce((sum, fb) => sum + fb.overall_score, 0) / feedbacks.length
                        const date = toKST(feedbacks[0].created_at)
                        const dayOfWeek = ['일','월','화','수','목','금','토'][date.getDay()]
                        return {
                          date: `${date.getMonth()+1}.${date.getDate()}.(${dayOfWeek})`,
                          score: Math.round(avgScore * 10) / 10,  // 소수점 1자리
                          fullDate: date.toLocaleDateString('ko-KR'),
                          count: feedbacks.length  // 해당 날짜 시뮬레이션 횟수
                        }
                      })
                      .sort((a, b) => {
                        // 날짜순 정렬
                        const dateA = new Date(a.fullDate)
                        const dateB = new Date(b.fullDate)
                        return dateA.getTime() - dateB.getTime()
                      })
                  }
                  
                  // 같은 날만 있으면 → 시간 표시 (주차 내 모든 데이터)
                  return weekData.map(fb => {
                    return {
                      date: formatKSTTime(fb.created_at),
                      score: fb.overall_score,
                      fullDate: formatKSTDateTime(fb.created_at)
                    }
                  })
                })()}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
                  <XAxis 
                    dataKey="date" 
                    tick={{ fontSize: 11, fill: '#6B7280' }}
                    stroke="#9CA3AF"
                    angle={0}
                    height={50}
                  />
                  <YAxis 
                    domain={[0, 100]} 
                    tick={{ fontSize: 11, fill: '#6B7280' }}
                    stroke="#9CA3AF"
                  />
                  <Tooltip 
                    contentStyle={{ 
                      backgroundColor: 'rgba(255, 255, 255, 0.95)', 
                      border: 'none', 
                      borderRadius: '8px',
                      boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)',
                      padding: '12px'
                    }}
                    labelStyle={{ fontWeight: 600, color: '#1F2937', marginBottom: '4px' }}
                    formatter={(value: number) => [`${value}점`, '평균 점수']}
                    labelFormatter={(label: string, payload: any) => {
                      if (payload && payload[0] && payload[0].payload) {
                        const data = payload[0].payload
                        if (data.count > 1) {
                          return `${data.fullDate} (${data.count}회 평균)`
                        }
                        return data.fullDate || label
                      }
                      return label
                    }}
                  />
                  <Line 
                    type="monotone" 
                    dataKey="score" 
                    stroke="#3B82F6" 
                    strokeWidth={3}
                    dot={{ r: 5, fill: '#3B82F6', strokeWidth: 2, stroke: '#fff' }}
                    activeDot={{ r: 7, fill: '#2563EB' }}
                    name="점수"
                  />
                </LineChart>
              </ResponsiveContainer>
            </motion.div>

            {/* 역량별 누적 평균 점수 */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="bg-gradient-to-br from-purple-50 to-white rounded-xl shadow-md p-6 border border-purple-100"
            >
              <div className="flex items-center justify-between mb-6">
                <h3 className="text-lg font-bold text-gray-900 flex items-center gap-2">
                  <div className="w-1 h-6 bg-purple-600 rounded-full"></div>
                  역량별 주간 평균 점수
                </h3>
                <span className="text-xs text-gray-500 bg-purple-50 px-3 py-1 rounded-full">
                  {feedbackHistory.length}회 평균
                </span>
              </div>
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={(() => {
                  if (feedbackHistory.length === 0) return []
                  
                  // competencies 배열에서 점수 추출 (더 안전한 방식)
                  const competencyScores = {
                    knowledge: 0,
                    skill: 0,
                    empathy: 0,
                    clarity: 0,
                    kindness: 0,
                    confidence: 0
                  }
                  
                  feedbackHistory.forEach(fb => {
                    // competencies 배열에서 추출
                    if (fb.competencies && Array.isArray(fb.competencies)) {
                      fb.competencies.forEach((comp: any) => {
                        if (comp.name === '지식') competencyScores.knowledge += comp.score
                        else if (comp.name === '기술') competencyScores.skill += comp.score
                        else if (comp.name === '공감도') competencyScores.empathy += comp.score
                        else if (comp.name === '명확성') competencyScores.clarity += comp.score
                        else if (comp.name === '친절도') competencyScores.kindness += comp.score
                        else if (comp.name === '자신감') competencyScores.confidence += comp.score
                      })
                    } 
                    // Fallback: 개별 필드에서 추출
                    else {
                      competencyScores.knowledge += fb.knowledge_score || 0
                      competencyScores.skill += fb.skill_score || 0
                      competencyScores.empathy += fb.empathy_score || 0
                      competencyScores.clarity += fb.clarity_score || 0
                      competencyScores.kindness += fb.kindness_score || 0
                      competencyScores.confidence += fb.confidence_score || 0
                    }
                  })
                  
                  const count = feedbackHistory.length
                  
                  return [
                    { name: '지식', score: Math.round(competencyScores.knowledge / count) },
                    { name: '기술', score: Math.round(competencyScores.skill / count) },
                    { name: '공감도', score: Math.round(competencyScores.empathy / count) },
                    { name: '명확성', score: Math.round(competencyScores.clarity / count) },
                    { name: '친절도', score: Math.round(competencyScores.kindness / count) },
                    { name: '자신감', score: Math.round(competencyScores.confidence / count) }
                  ]
                })()}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
                  <XAxis 
                    dataKey="name" 
                    tick={{ fontSize: 11, fill: '#6B7280' }}
                    stroke="#9CA3AF"
                  />
                  <YAxis 
                    domain={[0, 100]} 
                    tick={{ fontSize: 11, fill: '#6B7280' }}
                    stroke="#9CA3AF"
                  />
                  <Tooltip 
                    contentStyle={{ 
                      backgroundColor: 'rgba(255, 255, 255, 0.95)', 
                      border: 'none', 
                      borderRadius: '8px',
                      boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)'
                    }}
                    labelStyle={{ fontWeight: 600, color: '#1F2937' }}
                  />
                  <Bar 
                    dataKey="score" 
                    fill="#8B5CF6"
                    radius={[8, 8, 0, 0]}
                    name="점수"
                  />
                </BarChart>
              </ResponsiveContainer>
            </motion.div>
          </div>

          {/* 피드백 히스토리 테이블 */}
          <div className="mt-6">
            {/* 테이블 헤더와 총 개수 */}
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-gray-900">전체 기록</h3>
              <span className="text-sm text-gray-500">
                총 {feedbackHistory.length}개 • {currentPage} / {Math.ceil(feedbackHistory.length / itemsPerPage)} 페이지
              </span>
            </div>

            <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-gray-200">
                      <th className="text-left py-3 px-4 font-semibold text-gray-700">날짜</th>
                      <th className="text-left py-3 px-4 font-semibold text-gray-700">시나리오</th>
                      <th className="text-center py-3 px-4 font-semibold text-gray-700">종합 점수</th>
                      <th className="text-center py-3 px-4 font-semibold text-gray-700">등급</th>
                      <th className="text-center py-3 px-4 font-semibold text-gray-700">대화 턴</th>
                      <th className="text-right py-3 px-4 font-semibold text-gray-700">상세보기</th>
                    </tr>
                  </thead>
                  <tbody>
                    {feedbackHistory
                      .slice((currentPage - 1) * itemsPerPage, currentPage * itemsPerPage)
                      .map((fb) => {
                      const gradeInfo = getGrade(fb.overall_score)
                      const { date, dayOfWeek } = formatKSTDateWithDay(fb.created_at)
                      
                      return (
                        <tr key={fb.id} className="border-b border-gray-100 hover:bg-gray-50 transition-colors">
                          <td className="py-4 px-4">
                            <div>
                              <div className="text-sm font-medium text-gray-900">
                                {date}
                              </div>
                              <div className="text-xs text-gray-500">{dayOfWeek}요일</div>
                            </div>
                          </td>
                          <td className="py-4 px-4">
                            <div className="flex flex-col gap-1">
                              {fb.persona_info && (
                                <span className="inline-flex items-center px-2 py-1 bg-purple-50 text-purple-700 text-xs font-medium rounded-md w-fit">
                                  👤 {fb.persona_info}
                                </span>
                              )}
                              {fb.situation_info && (
                                <span className="inline-flex items-center px-2 py-1 bg-blue-50 text-blue-700 text-xs font-medium rounded-md w-fit">
                                  💼 {fb.situation_info}
                                </span>
                              )}
                              {!fb.persona_info && !fb.situation_info && (
                                <span className="text-xs text-gray-400">정보 없음</span>
                              )}
                            </div>
                          </td>
                          <td className="py-4 px-4 text-center">
                            <span className="text-lg font-bold text-blue-600">{fb.overall_score}점</span>
                          </td>
                          <td className="py-4 px-4 text-center">
                            <span className={`inline-block px-3 py-1 rounded-full text-sm font-medium ${gradeInfo.bg} ${gradeInfo.color}`}>
                              {gradeInfo.grade}
                            </span>
                          </td>
                          <td className="py-4 px-4 text-center">
                            <span className="text-sm text-gray-600">{fb.total_turns || 0}턴</span>
                          </td>
                          <td className="py-4 px-4 text-right">
                            <button
                              onClick={() => viewFeedbackDetail(fb.id)}
                              className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 transition-colors"
                            >
                              상세보기
                            </button>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
            </div>

            {/* 페이지네이션 */}
            {feedbackHistory.length > itemsPerPage && (
              <div className="mt-6 flex items-center justify-center gap-2">
                {/* 이전 페이지 버튼 */}
                <button
                  onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
                  disabled={currentPage === 1}
                  className={`px-4 py-2 rounded-lg font-medium transition-all ${
                    currentPage === 1
                      ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                      : 'bg-white text-gray-700 hover:bg-blue-50 hover:text-blue-600 border border-gray-200'
                  }`}
                >
                  이전
                </button>

                {/* 페이지 번호 버튼들 */}
                {(() => {
                  const totalPages = Math.ceil(feedbackHistory.length / itemsPerPage)
                  const pages = []
                  
                  // 5개 페이지씩 보여주기
                  let startPage = Math.max(1, currentPage - 2)
                  let endPage = Math.min(totalPages, startPage + 4)
                  
                  // 끝에서 5개가 안되면 시작을 조정
                  if (endPage - startPage < 4) {
                    startPage = Math.max(1, endPage - 4)
                  }
                  
                  // 첫 페이지
                  if (startPage > 1) {
                    pages.push(
                      <button
                        key={1}
                        onClick={() => setCurrentPage(1)}
                        className="px-3 py-2 rounded-lg font-medium bg-white text-gray-700 hover:bg-blue-50 hover:text-blue-600 border border-gray-200 transition-all"
                      >
                        1
                      </button>
                    )
                    if (startPage > 2) {
                      pages.push(<span key="dots1" className="px-2 text-gray-400">...</span>)
                    }
                  }
                  
                  // 중간 페이지들
                  for (let i = startPage; i <= endPage; i++) {
                    pages.push(
                      <button
                        key={i}
                        onClick={() => setCurrentPage(i)}
                        className={`px-3 py-2 rounded-lg font-medium transition-all ${
                          currentPage === i
                            ? 'bg-blue-600 text-white shadow-md'
                            : 'bg-white text-gray-700 hover:bg-blue-50 hover:text-blue-600 border border-gray-200'
                        }`}
                      >
                        {i}
                      </button>
                    )
                  }
                  
                  // 마지막 페이지
                  if (endPage < totalPages) {
                    if (endPage < totalPages - 1) {
                      pages.push(<span key="dots2" className="px-2 text-gray-400">...</span>)
                    }
                    pages.push(
                      <button
                        key={totalPages}
                        onClick={() => setCurrentPage(totalPages)}
                        className="px-3 py-2 rounded-lg font-medium bg-white text-gray-700 hover:bg-blue-50 hover:text-blue-600 border border-gray-200 transition-all"
                      >
                        {totalPages}
                      </button>
                    )
                  }
                  
                  return pages
                })()}

                {/* 다음 페이지 버튼 */}
                <button
                  onClick={() => setCurrentPage(prev => Math.min(Math.ceil(feedbackHistory.length / itemsPerPage), prev + 1))}
                  disabled={currentPage === Math.ceil(feedbackHistory.length / itemsPerPage)}
                  className={`px-4 py-2 rounded-lg font-medium transition-all ${
                    currentPage === Math.ceil(feedbackHistory.length / itemsPerPage)
                      ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                      : 'bg-white text-gray-700 hover:bg-blue-50 hover:text-blue-600 border border-gray-200'
                  }`}
                >
                  다음
                </button>
              </div>
            )}
          </div>
          </>
        ) : (
          <div className="text-center py-12">
            <TrophyIcon className="w-16 h-16 text-gray-300 mx-auto mb-4" />
            <p className="text-gray-500 text-lg mb-2">아직 시뮬레이션 피드백이 없습니다</p>
            <p className="text-gray-400 text-sm">시뮬레이션을 완료하면 피드백이 여기에 표시됩니다</p>
          </div>
        )}
      </motion.div>

      {/* 시뮬레이션 녹화 목록 */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="bg-white rounded-xl shadow-md p-6"
      >
        <h2 className="text-xl font-bold text-gray-900 mb-4">시뮬레이션 녹화</h2>
        {recordings && recordings.length > 0 ? (
          <div className="space-y-4">
            {recordings.slice(0, 5).map((recording: any) => (
              <div key={recording.id} className="p-4 bg-gray-50 rounded-lg border border-gray-200">
                <div className="flex items-start justify-between mb-2">
                  <div className="flex-1">
                    <p className="font-medium text-gray-900">
                      {formatKSTDateTime(recording.created_at)}
                    </p>
                    <p className="text-sm text-gray-500 mt-1">
                      파일 크기: {(recording.file_size / (1024 * 1024)).toFixed(2)} MB
                      {recording.duration && ` • 재생 시간: ${recording.duration}초`}
                    </p>
                  </div>
                </div>
                <video
                  controls
                  className="w-full rounded-lg mt-3"
                  style={{ maxHeight: '400px' }}
                >
                  <source src={`${import.meta.env.VITE_API_URL || '/api'}${recording.video_url}`} type="video/webm" />
                  브라우저가 비디오 태그를 지원하지 않습니다.
                </video>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-8">
            <svg className="w-16 h-16 text-gray-300 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
            </svg>
            <p className="text-gray-500 text-lg mb-2">아직 녹화된 시뮬레이션이 없습니다</p>
            <p className="text-gray-400 text-sm">시뮬레이션을 진행하면 녹화가 자동으로 저장됩니다</p>
          </div>
        )}
      </motion.div>
        </>
      )}
    </div>
  )
}

function MentorDashboard({ data }: any) {
  const [selectedMentee, setSelectedMentee] = useState<any>(null)
  const [showFeedbackModal, setShowFeedbackModal] = useState(false)
  const [showPerformanceModal, setShowPerformanceModal] = useState(false)
  const [feedbackText, setFeedbackText] = useState('')
  
  // 멘티 선택 관련 상태
  const [showMenteeSelectModal, setShowMenteeSelectModal] = useState(false)
  const [availableMentees, setAvailableMentees] = useState<any[]>([])
  const [loadingMentees, setLoadingMentees] = useState(false)
  const [selectingMentee, setSelectingMentee] = useState(false)

  const handleGiveFeedback = (mentee: any) => {
    setSelectedMentee(mentee)
    setShowFeedbackModal(true)
  }

  const handleViewPerformance = (mentee: any) => {
    console.log('Selected mentee for performance analysis:', mentee)
    console.log('Performance scores:', mentee.performance_scores)
    setSelectedMentee(mentee)
    setShowPerformanceModal(true)
  }

  // 멘티 선택 관련 함수들
  const handleSelectMenteeClick = async () => {
    try {
      setLoadingMentees(true)
      const response = await dashboardAPI.getAvailableMentees()
      setAvailableMentees(response.available_mentees)
      setShowMenteeSelectModal(true)
    } catch (error) {
      console.error('멘티 목록 로드 실패:', error)
      alert('멘티 목록을 불러오는데 실패했습니다.')
    } finally {
      setLoadingMentees(false)
    }
  }

  const handleMenteeSelect = async (mentee: any) => {
    if (!confirm(`${mentee.name} 멘티를 선택하시겠습니까?`)) {
      return
    }

    try {
      setSelectingMentee(true)
      await dashboardAPI.selectMentee(mentee.id)
      alert(`${mentee.name} 멘티가 성공적으로 선택되었습니다!`)
      setShowMenteeSelectModal(false)
      // 페이지 새로고침으로 업데이트된 데이터 반영
      window.location.reload()
    } catch (error) {
      console.error('멘티 선택 실패:', error)
      alert('멘티 선택에 실패했습니다.')
    } finally {
      setSelectingMentee(false)
    }
  }

  const handleUnassignMentee = async (mentee: any) => {
    if (!confirm(`${mentee.name} 멘티와의 관계를 해제하시겠습니까?`)) {
      return
    }

    try {
      await dashboardAPI.unassignMentor(mentee.id)
      alert(`${mentee.name} 멘티와의 관계가 성공적으로 해제되었습니다!`)
      // 페이지 새로고침으로 업데이트된 데이터 반영
      window.location.reload()
    } catch (error) {
      console.error('멘티 해제 실패:', error)
      alert('멘티 해제에 실패했습니다.')
    }
  }

  const submitFeedback = async () => {
    try {
      await dashboardAPI.createFeedback(selectedMentee.id, feedbackText, 'general')
      alert('피드백이 성공적으로 전송되었습니다!')
      setShowFeedbackModal(false)
      setFeedbackText('')
      setSelectedMentee(null)
      // 페이지 새로고침하여 최신 데이터 반영
      window.location.reload()
    } catch (error) {
      console.error('피드백 전송 실패:', error)
      alert('피드백 전송에 실패했습니다. 다시 시도해주세요.')
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold text-gray-900">멘토 대시보드</h1>

      {/* Stats */}
      <div className="grid md:grid-cols-3 gap-6">
        <StatCard
          icon={UserIcon}
          title="담당 멘티"
          value={data?.mentees?.length || 0}
          color="primary"
        />
        {/* 자주 묻는 질문 카드 제거 */}
        <StatCard
          icon={AcademicCapIcon}
          title="평균 성적"
          value={
            data?.mentees?.length > 0
              ? (
                  data.mentees.reduce((sum: number, m: any) => sum + (m.recent_score || 0), 0) /
                  data.mentees.length
                ).toFixed(1)
              : 'N/A'
          }
          color="bank"
        />
        <StatCard
          icon={ChartBarIcon}
          title="활성 멘티"
          value={data?.mentees?.filter((m: any) => m.chat_count > 0)?.length || 0}
          color="accent"
        />
      </div>

      {/* Mentees List with Enhanced Features */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="bg-white rounded-2xl shadow-lg p-8 border border-primary-100"
      >
        <div className="flex justify-between items-center mb-6">
          <h2 className="text-xl font-bold text-gray-900">담당 멘티 관리</h2>
          <button
            onClick={handleSelectMenteeClick}
            disabled={loadingMentees}
            className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors disabled:opacity-50 flex items-center space-x-2"
          >
            <PlusIcon className="w-4 h-4" />
            <span>{loadingMentees ? '로딩 중...' : '멘티 선택하기'}</span>
          </button>
                  </div>
        <div className="grid gap-6">
          {data?.mentees?.map((mentee: any) => (
            <MenteeCard 
              key={mentee.id} 
              mentee={mentee} 
              onGiveFeedback={handleGiveFeedback}
              onViewPerformance={handleViewPerformance}
              onUnassign={handleUnassignMentee}
            />
          ))}
          {(!data?.mentees || data.mentees.length === 0) && (
            <div className="text-center py-12">
              <UserIcon className="w-16 h-16 text-gray-300 mx-auto mb-4" />
              <p className="text-gray-500 text-lg">담당 멘티가 없습니다</p>
              <p className="text-gray-400 text-sm mt-2">관리자에게 멘티 배정을 요청해보세요</p>
            </div>
          )}
        </div>
      </motion.div>

      {/* Feedback Modal */}
      {showFeedbackModal && selectedMentee && (
        <FeedbackModal
          mentee={selectedMentee}
          feedbackText={feedbackText}
          setFeedbackText={setFeedbackText}
          onSubmit={submitFeedback}
          onClose={() => setShowFeedbackModal(false)}
        />
      )}

      {/* Performance Modal */}
      {showPerformanceModal && selectedMentee && (
        <PerformanceModal
          mentee={selectedMentee}
          onClose={() => setShowPerformanceModal(false)}
        />
      )}

      {/* 멘티 선택 모달 */}
      {showMenteeSelectModal && (
        <MenteeSelectModal
          availableMentees={availableMentees}
          onSelect={handleMenteeSelect}
          onClose={() => setShowMenteeSelectModal(false)}
          selecting={selectingMentee}
        />
      )}

      {/* 자주 묻는 질문 섹션 제거 */}
    </div>
  )
}

// 멘티 카드 컴포넌트
function MenteeCard({ mentee, onGiveFeedback, onViewPerformance, onUnassign }: any) {
  const getScoreColor = (score: number) => {
    if (score >= 90) return 'text-green-600'
    if (score >= 80) return 'text-blue-600'
    if (score >= 70) return 'text-yellow-600'
    return 'text-red-600'
  }

  const getPerformanceLevel = (score: number) => {
    if (score >= 90) return '우수'
    if (score >= 80) return '양호'
    if (score >= 70) return '보통'
    return '개선 필요'
  }

  // 프로필 사진 URL 처리 함수
  const getDisplayPhotoUrl = (photoUrl: string | null) => {
    if (!photoUrl) return null
    // /uploads로 시작하는 경우 /api를 추가하여 프록시 경로로 변환
    if (photoUrl.startsWith('/uploads')) {
      return `/api${photoUrl}`
    }
    return photoUrl
  }

  const displayPhotoUrl = getDisplayPhotoUrl(mentee.photo_url)

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-gradient-to-r from-white to-gray-50 rounded-xl p-6 border border-gray-200 hover:shadow-lg transition-all duration-300"
    >
      <div className="flex items-start justify-between">
        <div className="flex items-start space-x-4">
          {displayPhotoUrl ? (
            <div className="w-16 h-16 rounded-full overflow-hidden bg-gray-100">
              <img 
                src={displayPhotoUrl} 
                alt={mentee.name} 
                className="w-full h-full object-cover"
                onError={(e) => {
                  e.currentTarget.style.display = 'none'
                  e.currentTarget.nextElementSibling.style.display = 'flex'
                }}
              />
              <div className="w-full h-full bg-primary-100 rounded-full flex items-center justify-center hidden">
                <UserIcon className="w-8 h-8 text-primary-600" />
              </div>
            </div>
          ) : (
            <div className="w-16 h-16 bg-primary-100 rounded-full flex items-center justify-center">
              <UserIcon className="w-8 h-8 text-primary-600" />
                  </div>
                )}
          <div className="flex-1">
            <h3 className="text-xl font-bold text-gray-900 mb-1">{mentee.name}</h3>
            <p className="text-gray-600 mb-2">
              {mentee.team} • MBTI: {mentee.mbti || '미설정'}
            </p>
            {mentee.interests && (
              <div className="mb-2">
                <div className="flex items-start">
                  <p className="text-xs text-gray-500 mb-1 mr-2 flex-shrink-0">관심사:</p>
                  <div className="flex flex-wrap gap-1">
                    {(() => {
                      let interestsArray = []
                      if (Array.isArray(mentee.interests)) {
                        interestsArray = mentee.interests
                      } else if (typeof mentee.interests === 'string') {
                        // JSON 배열 문자열인 경우 파싱
                        try {
                          const parsed = JSON.parse(mentee.interests)
                          if (Array.isArray(parsed)) {
                            interestsArray = parsed
                          } else {
                            interestsArray = [mentee.interests]
                          }
                        } catch {
                          // JSON이 아닌 경우 컴마로 분리
                          interestsArray = mentee.interests.split(',').map(s => s.trim()).filter(s => s)
                        }
                      }
                      
                      return interestsArray.map((interest: string, idx: number) => (
                        <span key={idx} className="px-2 py-1 bg-blue-100 text-blue-800 text-xs rounded-full">
                          {interest}
                        </span>
                      ))
                    })()}
                </div>
              </div>
              </div>
            )}
            <div className="flex items-center space-x-4 text-sm text-gray-500">
              <span className="flex items-center">
                <ChatBubbleBottomCenterTextIcon className="w-4 h-4 mr-1" />
                대화 {mentee.chat_count || 0}회
              </span>
              <span className="flex items-center">
                <StarIcon className="w-4 h-4 mr-1" />
                {getPerformanceLevel(mentee.recent_score || 0)}
              </span>
            </div>
          </div>
        </div>
        
              <div className="text-right">
          <div className="flex items-center space-x-2 mb-2">
            <span className="text-sm text-gray-600">최근 점수</span>
            <span className={`text-2xl font-bold ${mentee.recent_score ? getScoreColor(mentee.recent_score) : 'text-blue-600'}`}>
                  {mentee.recent_score?.toFixed(1) || 'N/A'}
            </span>
          </div>
          <div className="flex space-x-2">
            <button
              onClick={() => onViewPerformance(mentee)}
              className="flex items-center px-3 py-2 bg-primary-100 text-primary-700 rounded-lg hover:bg-primary-200 transition-colors text-sm"
            >
              <EyeIcon className="w-4 h-4 mr-1" />
              성과 분석
            </button>
            <button
              onClick={() => onGiveFeedback(mentee)}
              className="flex items-center px-3 py-2 bg-amber-100 text-amber-700 rounded-lg hover:bg-amber-200 transition-colors text-sm"
            >
              <PencilIcon className="w-4 h-4 mr-1" />
              피드백
            </button>
            <button
              onClick={() => onUnassign(mentee)}
              className="flex items-center px-3 py-2 bg-red-100 text-red-700 rounded-lg hover:bg-red-200 transition-colors text-sm"
            >
              <XMarkIcon className="w-4 h-4 mr-1" />
              해제
            </button>
          </div>
        </div>
      </div>
    </motion.div>
  )
}

// 피드백 모달 컴포넌트
function FeedbackModal({ mentee, feedbackText, setFeedbackText, onSubmit, onClose }: any) {
  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <motion.div
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        className="bg-white rounded-xl p-6 w-full max-w-md mx-4"
      >
        <h3 className="text-xl font-bold text-gray-900 mb-4">
          {mentee.name}님에게 피드백 주기
        </h3>
        <textarea
          value={feedbackText}
          onChange={(e) => setFeedbackText(e.target.value)}
          placeholder="멘티에게 전달할 피드백을 작성해주세요..."
          className="w-full h-32 p-3 border border-primary-200 rounded-lg resize-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
        />
        <div className="flex space-x-3 mt-4">
          <button
            onClick={onSubmit}
            disabled={!feedbackText.trim()}
            className="flex-1 bg-gradient-to-r from-primary-600 to-primary-500 text-white py-2 px-4 rounded-lg hover:from-primary-700 hover:to-primary-600 disabled:bg-gray-300 disabled:cursor-not-allowed transition-all duration-200"
          >
            피드백 전송
          </button>
          <button
            onClick={onClose}
            className="flex-1 bg-gray-200 text-gray-800 py-2 px-4 rounded-lg hover:bg-gray-300 transition-colors"
          >
            취소
          </button>
        </div>
      </motion.div>
    </div>
  )
}

// 성과 분석 모달 컴포넌트
function PerformanceModal({ mentee, onClose }: any) {
  console.log('PerformanceModal received mentee:', mentee)
  console.log('PerformanceModal performance_scores:', mentee.performance_scores)
  
  // 멘티의 실제 성과 지표 데이터 사용
  const performanceData = [
    { skill: '은행업무', score: mentee.performance_scores?.banking || mentee.recent_score || 85 },
    { skill: '상품지식', score: mentee.performance_scores?.product_knowledge || mentee.recent_score || 78 },
    { skill: '고객응대', score: mentee.performance_scores?.customer_service || mentee.recent_score || 92 },
    { skill: '법규준수', score: mentee.performance_scores?.compliance || mentee.recent_score || 88 },
    { skill: 'IT활용', score: mentee.performance_scores?.it_usage || mentee.recent_score || 75 },
    { skill: '영업실적', score: mentee.performance_scores?.sales_performance || mentee.recent_score || 80 }
  ]
  
  console.log('PerformanceModal performanceData:', performanceData)

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <motion.div
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        className="bg-white rounded-xl p-6 w-full max-w-4xl mx-4 max-h-[90vh] overflow-y-auto"
      >
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-2xl font-bold text-gray-900">
            {mentee.name}님 성과 분석
          </h3>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600"
          >
            ✕
          </button>
        </div>
        
        <div className="grid lg:grid-cols-2 gap-6">
          {/* 레이더 차트 */}
          <div>
            <h4 className="text-lg font-semibold text-gray-900 mb-4">종합 성과</h4>
            <ResponsiveContainer width="100%" height={300}>
              <RadarChart data={performanceData}>
                <PolarGrid stroke="#e5e7eb" strokeWidth={1} />
                <PolarAngleAxis 
                  dataKey="skill" 
                  tick={{ fontSize: 12, fill: '#374151' }}
                />
                <PolarRadiusAxis 
                  angle={90} 
                  domain={[0, 100]} 
                  tick={{ fontSize: 10, fill: '#6b7280' }}
                />
                <Radar
                  name="점수"
                  dataKey="score"
                  stroke="#d4a574"
                  fill="#d4a574"
                  fillOpacity={0.3}
                  strokeWidth={2}
                  dot={{ r: 4, fill: '#d4a574' }}
                />
                <Tooltip 
                  formatter={(value: any) => [`${value}점`, '점수']}
                  labelFormatter={(label: string) => `지표: ${label}`}
                />
              </RadarChart>
            </ResponsiveContainer>
          </div>
          
          {/* 상세 점수 */}
          <div>
            <h4 className="text-lg font-semibold text-gray-900 mb-4">지표별 상세</h4>
            <div className="space-y-3">
              {performanceData.map((item, index) => (
                <div key={index} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                  <span className="text-sm font-medium text-gray-700">{item.skill}</span>
                  <div className="flex items-center space-x-2">
                    <div className="w-20 bg-gray-200 rounded-full h-2">
                      <div 
                        className="bg-gradient-to-r from-primary-500 to-primary-600 h-2 rounded-full transition-all duration-500"
                        style={{ width: `${item.score}%` }}
                      ></div>
                    </div>
                    <span className="text-sm font-bold text-gray-900 w-10 text-right">
                      {item.score}점
                    </span>
              </div>
            </div>
          ))}
            </div>
            
            {/* 개선 제안 */}
            <div className="mt-6 p-4 bg-gradient-to-r from-amber-50 to-primary-50 rounded-xl border border-amber-200">
              <h5 className="font-semibold text-amber-800 mb-2 flex items-center">
                <LightBulbIcon className="w-5 h-5 mr-2" />
                개선 제안
              </h5>
              <ul className="text-sm text-amber-700 space-y-1">
                <li>• IT활용 능력 향상을 위한 교육 프로그램 참여</li>
                <li>• 상품지식 강화를 위한 정기 학습 계획 수립</li>
                <li>• 고객응대 우수 사례 공유 및 학습</li>
              </ul>
            </div>
          </div>
        </div>
      </motion.div>
    </div>
  )
}

// 피드백 카드 컴포넌트 (댓글 기능 포함)
function FeedbackCard({ feedback, index, currentTime }: any) {
  const { user } = useAuthStore()
  const [showComments, setShowComments] = useState(false)
  const [comments, setComments] = useState<any[]>([])
  const [newComment, setNewComment] = useState('')
  const [isLoadingComments, setIsLoadingComments] = useState(false)
  
  const getDateBasedColor = (createdAt: string, colorSection?: string) => {
    // DB에 저장된 색상 섹션을 우선 사용
    if (colorSection) {
      switch (colorSection) {
        case 'red':
          return 'border-red-500 bg-red-50'
        case 'orange':
          return 'border-orange-500 bg-orange-50'
        case 'yellow':
          return 'border-yellow-500 bg-yellow-50'
        case 'gray':
          return 'border-gray-400 bg-gray-50'
        default:
          return 'border-gray-400 bg-gray-50'
      }
    }
    
    // 색상 섹션이 없으면 기존 시간 기반 계산 사용
    try {
      const now = new Date()
      const feedbackDate = toKST(createdAt)
      
      if (isNaN(feedbackDate.getTime())) {
        return 'border-gray-400 bg-gray-50'
      }
      
      const diffInHours = (now.getTime() - feedbackDate.getTime()) / (1000 * 60 * 60)
      
      if (diffInHours <= 24) {
        return 'border-red-500 bg-red-50'
      } else if (diffInHours <= 72) {
        return 'border-orange-500 bg-orange-50'
      } else if (diffInHours <= 168) {
        return 'border-yellow-500 bg-yellow-50'
      } else {
        return 'border-gray-400 bg-gray-50'
      }
    } catch (error) {
      console.error('색상 계산 오류:', error, createdAt)
      return 'border-gray-400 bg-gray-50'
    }
  }

  const getTimeLabel = (createdAt: string) => {
    try {
      // 항상 현재 시간을 새로 가져와서 계산
      const now = new Date()
      const feedbackDate = toKST(createdAt)
      
      // 유효한 날짜인지 확인
      if (isNaN(feedbackDate.getTime())) {
        console.error('Invalid date:', createdAt)
        return '시간 정보 없음'
      }
      
      const diffInMs = now.getTime() - feedbackDate.getTime()
      const diffInMinutes = diffInMs / (1000 * 60)
      const diffInHours = diffInMs / (1000 * 60 * 60)
      const diffInDays = diffInMs / (1000 * 60 * 60 * 24)
      
      // 디버깅 로그 (개발 환경에서만)
      if (process.env.NODE_ENV === 'development') {
        console.log('시간 계산 디버그:', {
          createdAt,
          now: now.toISOString(),
          feedbackDate: feedbackDate.toISOString(),
          diffInMs,
          diffInMinutes: Math.floor(diffInMinutes),
          diffInHours: Math.floor(diffInHours),
          diffInDays: Math.floor(diffInDays)
        })
      }
      
      if (diffInMinutes < 1) {
        return '방금 전'
      } else if (diffInMinutes < 60) {
        return `${Math.floor(diffInMinutes)}분 전`
      } else if (diffInHours < 24) {
        return `${Math.floor(diffInHours)}시간 전`
      } else if (diffInDays < 7) {
        return `${Math.floor(diffInDays)}일 전`
      } else {
        return feedbackDate.toLocaleDateString('ko-KR', {
          year: 'numeric',
          month: 'short',
          day: 'numeric'
        })
      }
    } catch (error) {
      console.error('시간 계산 오류:', error, createdAt)
      return '시간 계산 오류'
    }
  }

  const isRecent = () => {
    // 항상 현재 시간을 새로 가져와서 계산
    const now = new Date()
    const feedbackDate = toKST(feedback.created_at)
    const diffInHours = (now.getTime() - feedbackDate.getTime()) / (1000 * 60 * 60)
    return diffInHours <= 24
  }
  
  const loadComments = async () => {
    if (showComments && comments.length === 0) {
      setIsLoadingComments(true)
      try {
        const response = await dashboardAPI.getComments(feedback.id)
        setComments(response.comments || [])
      } catch (error) {
        console.error('댓글 로드 실패:', error)
      } finally {
        setIsLoadingComments(false)
      }
    }
  }
  
  const handleAddComment = async () => {
    if (!newComment.trim()) return
    
    try {
      await dashboardAPI.createComment(feedback.id, newComment)
      setNewComment('')
      // 댓글 목록 새로고침
      const response = await dashboardAPI.getComments(feedback.id)
      setComments(response.comments || [])
    } catch (error) {
      console.error('댓글 작성 실패:', error)
      alert('댓글 작성에 실패했습니다.')
    }
  }
  
  const handleDeleteComment = async (commentId: number) => {
    if (!confirm('댓글을 삭제하시겠습니까?')) return
    
    try {
      await dashboardAPI.deleteComment(commentId)
      // 댓글 목록 새로고침
      const response = await dashboardAPI.getComments(feedback.id)
      setComments(response.comments || [])
    } catch (error) {
      console.error('댓글 삭제 실패:', error)
      alert('댓글 삭제에 실패했습니다.')
    }
  }
  
  useEffect(() => {
    if (showComments) {
      loadComments()
    }
  }, [showComments])

  return (
    <motion.div
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.1 }}
      className={`p-4 rounded-lg border-l-4 transition-all duration-300 hover:shadow-md ${
        feedback.is_read 
          ? 'bg-gray-50 border-gray-300' 
          : getDateBasedColor(feedback.created_at, feedback.color_section)
      }`}
    >
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center space-x-3">
          <div className="flex items-center space-x-2">
            <div className={`w-2 h-2 rounded-full ${
              feedback.is_read ? 'bg-gray-400' : isRecent() ? 'bg-red-500' : 'bg-orange-500'
            }`}></div>
            <span className="text-sm font-medium text-gray-700">
              {feedback.mentor_name} 멘토
            </span>
          </div>
          <span className="text-xs text-gray-500">
            {getTimeLabel(feedback.created_at)}
          </span>
        </div>
        <div className="flex items-center space-x-2">
          {isRecent() && !feedback.is_read && (
            <span className="px-2 py-1 bg-red-100 text-red-800 text-xs rounded-full animate-pulse">
              최신 피드백
            </span>
          )}
        </div>
      </div>
      <p className="text-gray-800 leading-relaxed text-sm mb-3">{feedback.feedback_text}</p>
      
      {/* 댓글 토글 버튼 */}
        <button
          onClick={() => setShowComments(!showComments)}
          className="flex items-center space-x-2 text-sm text-primary-600 hover:text-primary-800 transition-colors"
        >
          <ChatBubbleLeftRightIcon className="w-4 h-4" />
          <span>{showComments ? '댓글 숨기기' : '댓글 보기'}</span>
          {comments.length > 0 && (
            <span className="px-2 py-0.5 bg-primary-100 text-primary-800 rounded-full text-xs">
              {comments.length}
            </span>
          )}
        </button>
      
      {/* 댓글 영역 */}
      {showComments && (
        <div className="mt-4 pt-4 border-t border-gray-200">
          {isLoadingComments ? (
            <div className="text-center text-gray-500 text-sm py-4">댓글 로딩 중...</div>
          ) : (
            <>
              {/* 댓글 목록 */}
              <div className="space-y-3 mb-4">
                {comments.map((comment: any) => (
                  <div key={comment.id} className="bg-white p-3 rounded-lg border border-gray-200">
                    <div className="flex items-start justify-between mb-2">
                      <div className="flex items-center space-x-2">
                        <span className={`text-xs font-semibold ${
                          comment.user_role === 'MENTOR' ? 'text-primary-600' : 'text-amber-600'
                        }`}>
                          {comment.user_name}
                        </span>
                        <span className="text-xs text-gray-500">
                          {getTimeLabel(comment.created_at)}
                        </span>
                      </div>
                      {comment.user_id === user?.id && (
                        <button
                          onClick={() => handleDeleteComment(comment.id)}
                          className="text-gray-400 hover:text-red-600 transition-colors"
                        >
                          <TrashIcon className="w-4 h-4" />
                        </button>
                      )}
                    </div>
                    <p className="text-sm text-gray-700">{comment.comment_text}</p>
                  </div>
                ))}
                
                {comments.length === 0 && (
                  <p className="text-center text-gray-500 text-sm py-4">
                    아직 댓글이 없습니다. 첫 댓글을 남겨보세요!
                  </p>
                )}
              </div>
              
              {/* 댓글 작성 폼 */}
              <div className="flex items-start space-x-2">
                <textarea
                  value={newComment}
                  onChange={(e) => setNewComment(e.target.value)}
                  placeholder="댓글을 입력하세요..."
                  className="flex-1 px-3 py-2 border border-primary-200 rounded-lg text-sm resize-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                  rows={2}
                />
                <button
                  onClick={handleAddComment}
                  disabled={!newComment.trim()}
                  className="px-4 py-2 bg-gradient-to-r from-primary-600 to-primary-500 text-white rounded-lg hover:from-primary-700 hover:to-primary-600 disabled:bg-gray-300 disabled:cursor-not-allowed transition-all duration-200 flex items-center space-x-1"
                >
                  <PaperAirplaneIcon className="w-4 h-4" />
                  <span>전송</span>
                </button>
              </div>
            </>
          )}
        </div>
      )}
      </motion.div>
  )
}

// 피드백 아코디언 컴포넌트
function FeedbackAccordion({ additionalFeedbacks, totalCount, currentTime }: any) {
  const [isExpanded, setIsExpanded] = useState(false)

  return (
    <div className="border-t border-gray-200 pt-3">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between p-3 text-left hover:bg-gray-50 rounded-lg transition-colors"
      >
        <div className="flex items-center space-x-2">
          <span className="text-sm font-medium text-gray-700">
            이전 피드백 {additionalFeedbacks.length}개 더 보기
          </span>
          <span className="text-xs text-gray-500">
            (총 {totalCount}개)
          </span>
        </div>
        <motion.div
          animate={{ rotate: isExpanded ? 180 : 0 }}
          transition={{ duration: 0.2 }}
        >
          <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </motion.div>
      </button>
      
      <motion.div
        initial={false}
        animate={{ 
          height: isExpanded ? 'auto' : 0,
          opacity: isExpanded ? 1 : 0
        }}
        transition={{ duration: 0.3 }}
        className="overflow-hidden"
      >
        <div className="space-y-3 mt-3">
          {additionalFeedbacks.map((feedback: any, idx: number) => (
            <FeedbackCard 
              key={idx + 3} 
              feedback={feedback} 
              index={idx + 3}
              currentTime={currentTime}
            />
          ))}
        </div>
      </motion.div>
    </div>
  )
}

function StatCard({ icon: Icon, title, value, color }: any) {
  const textColors: any = {
    primary: 'text-primary-600',
    amber: 'text-amber-600',
    bank: 'text-bank-600',
    accent: 'text-accent-600',
  }

  return (
    <div className="rounded-2xl p-6 bg-white border border-amber-100 shadow-sm hover:shadow-md transition-shadow">
      <div className={`w-12 h-12 mb-3 flex items-center justify-center rounded-full bg-gray-50 ${textColors[color]}`}>
        <Icon className="w-6 h-6" />
      </div>
      <p className="text-sm text-gray-500 mb-1 font-medium">{title}</p>
      <p className={`text-3xl font-bold text-gray-900`}>{value}</p>
    </div>
  )
}

// 관리자 대시보드 컴포넌트
// 관리자 대시보드 컴포넌트 (탭 구조)
function AdminDashboard({ 
  matchingData, 
  onAssignClick, 
  onUnassign, 
  showMatchingSection, 
  setShowMatchingSection,
  showAssignModal,
  setShowAssignModal,
  selectedMentor,
  selectedMentee,
  setSelectedMentee,
  assignNotes,
  setAssignNotes,
  onAssignConfirm,
  assigning
}: any) {
  const [activeTab, setActiveTab] = useState(0)
  const [userStats, setUserStats] = useState({
    totalUsers: 0,
    mentors: 0,
    mentees: 0,
    activeRelations: 0
  })
  const [recentActivities, setRecentActivities] = useState([])

  useEffect(() => {
    loadAdminStats()
  }, [])

  const loadAdminStats = async () => {
    try {
      const stats = await adminAPI.getStats()
      setUserStats({
        totalUsers: stats.users.total,
        mentors: stats.users.mentors,
        mentees: stats.users.mentees,
        activeRelations: stats.users.active_relations
      })
    } catch (error) {
      console.error('관리자 통계 로드 실패:', error)
      // 에러 시 기본값 설정
      setUserStats({
        totalUsers: 0,
        mentors: 0,
        mentees: 0,
        activeRelations: 0
      })
    }
  }

  const tabs = [
    { name: '사용자 관리', icon: UserIcon },
    { name: '멘토-멘티 관계', icon: AcademicCapIcon },
    { name: '학습 이력', icon: ChartBarIcon },
    { name: '문서 관리', icon: PaperAirplaneIcon },
    { name: '시스템 로그', icon: EyeIcon }
  ]

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold text-gray-900">관리자 대시보드</h1>

      {/* 전체 통계 */}
      <div className="grid md:grid-cols-4 gap-6">
        <StatCard
          icon={UserIcon}
          title="전체 사용자"
          value={userStats.totalUsers}
          color="primary"
        />
        <StatCard
          icon={AcademicCapIcon}
          title="멘토 수"
          value={userStats.mentors}
          color="amber"
        />
        <StatCard
          icon={LightBulbIcon}
          title="멘티 수"
          value={userStats.mentees}
          color="bank"
        />
        <StatCard
          icon={StarIcon}
          title="활성 매칭"
          value={userStats.activeRelations}
          color="success"
        />
      </div>

      {/* 탭 네비게이션 */}
      <div className="bg-white rounded-2xl shadow-lg border border-primary-100">
        <div className="border-b border-gray-200">
          <nav className="flex space-x-8 px-6">
            {tabs.map((tab, index) => (
              <button
                key={index}
                onClick={() => setActiveTab(index)}
                className={`py-4 px-1 border-b-2 font-medium text-sm flex items-center gap-2 transition-colors ${
                  activeTab === index
                    ? 'border-primary-500 text-primary-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                <tab.icon className="w-5 h-5" />
                {tab.name}
              </button>
            ))}
          </nav>
        </div>

        {/* 탭 콘텐츠 */}
        <div className="p-6">
          {activeTab === 0 && <UserManagementTab />}
          {activeTab === 1 && <MentorMenteeRelationTab 
            matchingData={matchingData}
            onAssignClick={onAssignClick}
            onUnassign={onUnassign}
            showMatchingSection={showMatchingSection}
            setShowMatchingSection={setShowMatchingSection}
          />}
          {activeTab === 2 && <LearningHistoryTab />}
          {activeTab === 3 && <DocumentManagementTab />}
          {activeTab === 4 && <SystemLogTab />}
        </div>
      </div>

      {/* 매칭 모달 */}
      {showAssignModal && (
        <AssignModal
          selectedMentor={selectedMentor}
          selectedMentee={selectedMentee}
          setSelectedMentee={setSelectedMentee}
          assignNotes={assignNotes}
          setAssignNotes={setAssignNotes}
          onConfirm={onAssignConfirm}
          onClose={() => {
            setShowAssignModal(false)
            setSelectedMentee(null)
            setAssignNotes('')
          }}
          assigning={assigning}
          matchingData={matchingData}
        />
      )}
    </div>
  )
}

// 멘토-멘티 관계 탭 (동료의 매칭 기능 통합)
function MentorMenteeRelationTab({ 
  matchingData, 
  onAssignClick, 
  onUnassign, 
  showMatchingSection, 
  setShowMatchingSection 
}: any) {
  if (!matchingData) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
      </div>
    )
  }

  return (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-white rounded-xl shadow-md p-6"
        >
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-bold text-gray-900 flex items-center">
          <UserGroupIcon className="w-6 h-6 mr-2 text-amber-600" />
          멘토-멘티 매칭 관리
        </h2>
        <button
          onClick={() => setShowMatchingSection(!showMatchingSection)}
          className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors"
        >
          {showMatchingSection ? '숨기기' : '관리하기'}
        </button>
      </div>

      {/* 통계 카드 */}
      <div className="grid md:grid-cols-4 gap-4 mb-6">
        <div className="bg-white rounded-lg p-4 border border-amber-100 shadow-sm">
          <div className="flex items-center">
            <UserIcon className="w-8 h-8 text-amber-600 mr-3" />
            <div>
              <p className="text-sm text-amber-700">총 멘토</p>
              <p className="text-2xl font-bold text-amber-900">{matchingData.statistics?.total_mentors || 0}</p>
            </div>
          </div>
        </div>
        <div className="bg-white rounded-lg p-4 border border-amber-100 shadow-sm">
          <div className="flex items-center">
            <AcademicCapIcon className="w-8 h-8 text-amber-600 mr-3" />
            <div>
              <p className="text-sm text-amber-700">총 멘티</p>
              <p className="text-2xl font-bold text-amber-900">{matchingData.statistics?.total_mentees || 0}</p>
            </div>
          </div>
        </div>
        <div className="bg-white rounded-lg p-4 border border-amber-100 shadow-sm">
          <div className="flex items-center">
            <CheckCircleIcon className="w-8 h-8 text-amber-600 mr-3" />
            <div>
              <p className="text-sm text-amber-700">매칭 완료</p>
              <p className="text-2xl font-bold text-amber-900">{matchingData.statistics?.assigned_mentees || 0}</p>
            </div>
          </div>
        </div>
        <div className="bg-white rounded-lg p-4 border border-amber-100 shadow-sm">
          <div className="flex items-center">
            <XCircleIcon className="w-8 h-8 text-amber-600 mr-3" />
            <div>
              <p className="text-sm text-amber-700">미매칭</p>
              <p className="text-2xl font-bold text-amber-900">{matchingData.statistics?.unassigned_mentees || 0}</p>
            </div>
          </div>
        </div>
      </div>

      {showMatchingSection && (
        <div className="grid lg:grid-cols-2 gap-6">
          {/* 멘토 목록 */}
          <div>
            <h3 className="text-lg font-semibold text-gray-900 mb-4">멘토 목록</h3>
            <div className="space-y-3 max-h-96 overflow-y-auto">
              {matchingData.mentors.map((mentor: any) => (
                <div key={mentor.id} className="p-4 border border-gray-200 rounded-lg">
                  <div className="flex justify-between items-start">
                    <div>
                      <h4 className="font-semibold text-gray-900">{mentor.name}</h4>
                      <p className="text-sm text-gray-600">{mentor.email}</p>
                      <p className="text-xs text-gray-500">담당 멘티: {mentor.current_mentee_count}명</p>
                    </div>
                    <div className="flex flex-col space-y-1">
                      {mentor.is_available && (
                        <button
                          onClick={() => onAssignClick(mentor, null)}
                          className="px-3 py-1 bg-primary-600 text-white rounded text-sm hover:bg-primary-700"
                        >
                          멘티 배정
                        </button>
                      )}
                    </div>
                  </div>
                </div>
            ))}
          </div>
          </div>

          {/* 멘티 목록 */}
          <div>
            <h3 className="text-lg font-semibold text-gray-900 mb-4">멘티 목록</h3>
            <div className="space-y-3 max-h-96 overflow-y-auto">
              {matchingData.mentees.map((mentee: any) => (
                <div key={mentee.id} className="p-4 border border-gray-200 rounded-lg">
                  <div className="flex justify-between items-start">
                    <div>
                      <h4 className="font-semibold text-gray-900">{mentee.name}</h4>
                      <p className="text-sm text-gray-600">{mentee.email}</p>
                      <p className="text-xs text-gray-500">
                        {mentee.current_mentor ? `담당 멘토: ${mentee.current_mentor.name}` : '미배정'}
                      </p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* 현재 매칭 현황 */}
      {showMatchingSection && matchingData.current_matches && matchingData.current_matches.length > 0 && (
        <div className="mt-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">현재 매칭 현황</h3>
          <div className="space-y-3">
            {matchingData.current_matches.map((match: any) => (
              <div key={match.relation_id} className="p-4 bg-white rounded-lg border border-gray-200">
                <div className="flex justify-between items-center">
                  <div className="flex-1">
                    <div className="flex items-center space-x-3 mb-2">
                      <span className="font-semibold text-gray-900">{match.mentor?.name || '알 수 없음'}</span>
                      <span className="text-gray-400">↔</span>
                      <span className="font-semibold text-gray-900">{match.mentee?.name || '알 수 없음'}</span>
                    </div>
                    {match.notes && (
                      <p className="text-sm text-gray-700 bg-gray-50 p-2 rounded">
                        <span className="font-medium">메모:</span> {match.notes}
                      </p>
                    )}
                    <p className="text-xs text-gray-500 mt-1">
                      매칭일: {match.matched_at ? new Date(match.matched_at + (match.matched_at.includes('Z') ? '' : 'Z')).toLocaleDateString('ko-KR') : '알 수 없음'}
                    </p>
                  </div>
                  <button
                    onClick={() => onUnassign(match.relation_id)}
                    className="px-3 py-1 bg-primary-600 text-white rounded text-sm hover:bg-primary-700 ml-4"
                  >
                    해제
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
        </motion.div>
  )
}

// 매칭 모달 컴포넌트
function AssignModal({
  selectedMentor,
  selectedMentee,
  setSelectedMentee,
  assignNotes,
  setAssignNotes,
  onConfirm,
  onClose,
  assigning,
  matchingData
}: any) {
  // 미매칭된 멘티들만 필터링
  const availableMentees = matchingData?.mentees?.filter((mentee: any) => !mentee.is_assigned) || []

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl p-6 max-w-md w-full mx-4">
        <h3 className="text-lg font-bold text-gray-900 mb-4">멘토-멘티 매칭</h3>
        
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">멘토</label>
            <p className="text-gray-900">{selectedMentor?.name || '선택된 멘토 없음'}</p>
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">멘티</label>
            <select
              value={selectedMentee?.id || ''}
              onChange={(e) => {
                const menteeId = parseInt(e.target.value)
                const mentee = availableMentees.find((m: any) => m.id === menteeId)
                setSelectedMentee(mentee)
              }}
              className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-amber-500 focus:border-transparent"
            >
              <option value="">멘티를 선택하세요</option>
              {availableMentees.map((mentee: any) => (
                <option key={mentee.id} value={mentee.id}>
                  {mentee.name} ({mentee.email})
                </option>
              ))}
            </select>
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">메모 (선택사항)</label>
            <textarea
              value={assignNotes}
              onChange={(e) => setAssignNotes(e.target.value)}
              className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-amber-500 focus:border-transparent"
              rows={3}
              placeholder="매칭 관련 메모를 입력하세요..."
            />
          </div>
        </div>
        
        <div className="flex justify-end space-x-3 mt-6">
          <button
            onClick={onClose}
            className="px-4 py-2 text-gray-600 hover:text-gray-800 transition-colors"
            disabled={assigning}
          >
            취소
          </button>
          <button
            onClick={onConfirm}
            disabled={assigning || !selectedMentor || !selectedMentee}
            className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors disabled:opacity-50"
          >
            {assigning ? '매칭 중...' : '매칭 완료'}
          </button>
        </div>
      </div>
    </div>
  )
}


// 멘티 선택 모달 컴포넌트
function MenteeSelectModal({ 
  availableMentees, 
  onSelect, 
  onClose, 
  selecting 
}: any) {
  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl p-6 max-w-2xl w-full mx-4 max-h-[80vh] overflow-hidden flex flex-col">
        <h3 className="text-lg font-bold text-gray-900 mb-4">멘티 선택하기</h3>
        
        <div className="flex-1 overflow-y-auto">
          {availableMentees.length === 0 ? (
            <div className="text-center py-8">
              <UserIcon className="w-16 h-16 text-gray-300 mx-auto mb-4" />
              <p className="text-gray-500 text-lg">선택 가능한 멘티가 없습니다</p>
              <p className="text-gray-400 text-sm">모든 멘티가 이미 배정되었습니다</p>
            </div>
          ) : (
            <div className="grid gap-4">
              {availableMentees.map((mentee: any) => (
                <div key={mentee.id} className="p-4 border border-gray-200 rounded-lg hover:shadow-md transition-shadow">
                  <div className="flex justify-between items-start">
                    <div className="flex-1">
                      <h4 className="font-semibold text-gray-900">{mentee.name}</h4>
                      <p className="text-sm text-gray-600">{mentee.email}</p>
                      <div className="mt-2 flex flex-wrap gap-2">
                        <span className="px-2 py-1 bg-amber-100 text-amber-800 text-xs rounded-full">
                          {mentee.team} {mentee.team_number}
                        </span>
                        {mentee.mbti && (
                          <span className="px-2 py-1 bg-green-100 text-green-800 text-xs rounded-full">
                            {mentee.mbti}
                          </span>
                        )}
                        {mentee.join_year && (
                          <span className="px-2 py-1 bg-purple-100 text-purple-800 text-xs rounded-full">
                            {mentee.join_year}년 입사
                          </span>
                        )}
                      </div>
                      {mentee.interests && (
                        <div className="mt-2">
                          <div className="flex items-start">
                            <p className="text-xl text-gray-500 mb-1 mr-2 flex-shrink-0">관심사:</p>
                            <div className="flex flex-wrap gap-1">
                              {(() => {
                                let interestsArray = []
                                if (Array.isArray(mentee.interests)) {
                                  interestsArray = mentee.interests
                                } else if (typeof mentee.interests === 'string') {
                                  // JSON 배열 문자열인 경우 파싱
                                  try {
                                    const parsed = JSON.parse(mentee.interests)
                                    if (Array.isArray(parsed)) {
                                      interestsArray = parsed
                                    } else {
                                      interestsArray = [mentee.interests]
                                    }
                                  } catch {
                                    // JSON이 아닌 경우 컴마로 분리
                                    interestsArray = mentee.interests.split(',').map(s => s.trim()).filter(s => s)
                                  }
                                }
                                
                                return interestsArray.map((interest: string, idx: number) => (
                                  <span key={idx} className="px-2 py-1 bg-orange-100 text-orange-800 text-xs rounded-full">
                                    {interest}
                                  </span>
                                ))
                              })()}
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                    <button
                      onClick={() => onSelect(mentee)}
                      disabled={selecting}
                      className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors disabled:opacity-50"
                    >
                      {selecting ? '선택 중...' : '선택하기'}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
        
        <div className="flex justify-end mt-6 pt-4 border-t border-gray-200">
          <button
            onClick={onClose}
            className="px-4 py-2 text-gray-600 hover:text-gray-800 transition-colors"
            disabled={selecting}
          >
            취소
          </button>
        </div>
      </div>
    </div>
  )
}

// 사용자 관리 탭
function UserManagementTab() {
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [searchTerm, setSearchTerm] = useState('')
  const [roleFilter, setRoleFilter] = useState('')

  useEffect(() => {
    loadUsers()
  }, [searchTerm, roleFilter])

  const loadUsers = async () => {
    try {
      setLoading(true)
      const response = await adminAPI.getAllUsers(0, 100, roleFilter || undefined, searchTerm || undefined)
      setUsers(response.users || [])
    } catch (error) {
      console.error('사용자 목록 로드 실패:', error)
      setUsers([])
    } finally {
      setLoading(false)
    }
  }

  const handleRoleChange = async (userId: number, newRole: string) => {
    try {
      await adminAPI.updateUserRole(userId, newRole)
      alert('사용자 역할이 성공적으로 변경되었습니다.')
      loadUsers() // 목록 새로고침
    } catch (error) {
      console.error('역할 변경 실패:', error)
      alert('역할 변경에 실패했습니다.')
    }
  }

  const handleBulkExamResults = async () => {
    try {
      const result = await dashboardAPI.processBulkExamResults()
      alert(`${result.message}\n처리된 멘티 수: ${result.processed_count}\n에러: ${result.errors.length}개`)
      if (result.errors.length > 0) {
        console.log('처리 실패한 멘티들:', result.errors)
      }
    } catch (error) {
      console.error('일괄 처리 실패:', error)
      alert('일괄 처리에 실패했습니다.')
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-xl font-semibold text-gray-900">사용자 관리</h2>
        <div className="flex gap-2">
          <button 
            onClick={handleBulkExamResults}
            className="bg-primary-600 text-white px-4 py-2 rounded-lg hover:bg-primary-700 transition-colors"
          >
            시험 결과 일괄 처리
          </button>
          <button className="bg-primary-600 text-white px-4 py-2 rounded-lg hover:bg-primary-700 transition-colors">
            새 사용자 추가
          </button>
        </div>
      </div>
      
      {/* 검색 및 필터 */}
      <div className="flex gap-4">
        <input
          type="text"
          placeholder="이름 또는 이메일 검색..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="flex-1 border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-primary-500 focus:border-transparent"
        />
        <select
          value={roleFilter}
          onChange={(e) => setRoleFilter(e.target.value)}
          className="border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-primary-500 focus:border-transparent"
        >
          <option value="">전체 역할</option>
          <option value="admin">관리자</option>
          <option value="mentor">멘토</option>
          <option value="mentee">멘티</option>
        </select>
      </div>

      {/* 사용자 목록 */}
      {loading ? (
        <div className="flex justify-center items-center h-32">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
        </div>
      ) : users.length > 0 ? (
        <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    사용자
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    이메일
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    역할
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    가입일
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    작업
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {users.map((user: any) => (
                  <tr key={user.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center">
                        <div className="flex-shrink-0 h-10 w-10">
                          {user.photo_url ? (
                            <img className="h-10 w-10 rounded-full" src={user.photo_url} alt="" />
                          ) : (
                            <div className="h-10 w-10 rounded-full bg-primary-100 flex items-center justify-center">
                              <UserIcon className="h-6 w-6 text-primary-600" />
                            </div>
                          )}
                        </div>
                        <div className="ml-4">
                          <div className="text-sm font-medium text-gray-900">{user.name}</div>
                          <div className="text-sm text-gray-500">{user.employee_number || '사원번호 없음'}</div>
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {user.email}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <select
                        value={user.role}
                        onChange={(e) => handleRoleChange(user.id, e.target.value)}
                        className="text-sm border border-gray-300 rounded px-2 py-1 focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                      >
                        <option value="admin">관리자</option>
                        <option value="mentor">멘토</option>
                        <option value="mentee">멘티</option>
                      </select>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {new Date(user.created_at + (user.created_at.includes('Z') ? '' : 'Z')).toLocaleDateString()}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                      <button className="text-primary-600 hover:text-primary-900">
                        상세보기
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <div className="bg-gray-50 rounded-lg p-8 text-center">
          <UserIcon className="w-16 h-16 text-gray-400 mx-auto mb-4" />
          <p className="text-gray-600">사용자를 찾을 수 없습니다.</p>
        </div>
      )}
    </div>
  )
}

// 학습 이력 탭
function LearningHistoryTab() {
  const [history, setHistory] = useState([])
  const [loading, setLoading] = useState(true)
  const [userId, setUserId] = useState('')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')

  useEffect(() => {
    loadHistory()
  }, [userId, startDate, endDate])

  const loadHistory = async () => {
    try {
      setLoading(true)
      const response = await adminAPI.getLearningHistory(
        userId ? parseInt(userId) : undefined,
        startDate || undefined,
        endDate || undefined
      )
      setHistory(response.history || [])
    } catch (error) {
      console.error('학습 이력 로드 실패:', error)
      setHistory([])
    } finally {
      setLoading(false)
    }
  }

  const getTypeLabel = (type: string) => {
    switch (type) {
      case 'chat': return '채팅'
      case 'exam': return '시험'
      case 'feedback': return '피드백'
      default: return type
    }
  }

  const getTypeColor = (type: string) => {
    switch (type) {
      case 'chat': return 'bg-blue-100 text-blue-800'
      case 'exam': return 'bg-green-100 text-green-800'
      case 'feedback': return 'bg-yellow-100 text-yellow-800'
      default: return 'bg-gray-100 text-gray-800'
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-xl font-semibold text-gray-900">학습 이력 관리</h2>
        <div className="flex gap-2">
          <button className="bg-gray-100 text-gray-700 px-4 py-2 rounded-lg hover:bg-gray-200 transition-colors">
            엑셀 다운로드
          </button>
          <button className="bg-primary-600 text-white px-4 py-2 rounded-lg hover:bg-primary-700 transition-colors">
            통계 보기
          </button>
        </div>
      </div>
      
      {/* 필터 */}
      <div className="flex gap-4">
        <input
          type="number"
          placeholder="사용자 ID (선택사항)"
          value={userId}
          onChange={(e) => setUserId(e.target.value)}
          className="border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-primary-500 focus:border-transparent"
        />
        <input
          type="date"
          placeholder="시작 날짜"
          value={startDate}
          onChange={(e) => setStartDate(e.target.value)}
          className="border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-primary-500 focus:border-transparent"
        />
        <input
          type="date"
          placeholder="종료 날짜"
          value={endDate}
          onChange={(e) => setEndDate(e.target.value)}
          className="border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-primary-500 focus:border-transparent"
        />
      </div>

      {/* 이력 목록 */}
      {loading ? (
        <div className="flex justify-center items-center h-32">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
        </div>
      ) : history.length > 0 ? (
        <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    타입
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    사용자
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    내용
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    일시
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {history.map((item: any, index: number) => (
                  <tr key={index} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${getTypeColor(item.type)}`}>
                        {getTypeLabel(item.type)}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm font-medium text-gray-900">{item.user_name}</div>
                      <div className="text-sm text-gray-500">ID: {item.user_id}</div>
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-900 max-w-md truncate">
                      {item.user_message}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {new Date(item.created_at + (item.created_at.includes('Z') ? '' : 'Z')).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <div className="bg-gray-50 rounded-lg p-8 text-center">
          <ChartBarIcon className="w-16 h-16 text-gray-400 mx-auto mb-4" />
          <p className="text-gray-600">학습 이력을 찾을 수 없습니다.</p>
        </div>
      )}
    </div>
  )
}

// 문서 관리 탭
function DocumentManagementTab() {
  const [documents, setDocuments] = useState([])
  const [loading, setLoading] = useState(true)
  const [categoryFilter, setCategoryFilter] = useState('')

  useEffect(() => {
    loadDocuments()
  }, [categoryFilter])

  const loadDocuments = async () => {
    try {
      setLoading(true)
      const response = await adminAPI.getAllDocuments(0, 100, categoryFilter || undefined)
      setDocuments(response.documents || [])
    } catch (error) {
      console.error('문서 목록 로드 실패:', error)
      setDocuments([])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-xl font-semibold text-gray-900">문서 관리</h2>
        <div className="flex gap-2">
          <button className="bg-gray-100 text-gray-700 px-4 py-2 rounded-lg hover:bg-gray-200 transition-colors">
            문서 업로드
          </button>
          <button className="bg-primary-600 text-white px-4 py-2 rounded-lg hover:bg-primary-700 transition-colors">
            카테고리 관리
          </button>
        </div>
      </div>
      
      {/* 카테고리 필터 */}
      <div className="flex gap-4">
        <select
          value={categoryFilter}
          onChange={(e) => setCategoryFilter(e.target.value)}
          className="border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-primary-500 focus:border-transparent"
        >
          <option value="">전체 카테고리</option>
          <option value="경제용어">경제용어</option>
          <option value="은행산업 기본지식">은행산업 기본지식</option>
          <option value="고객언어 가이드">고객언어 가이드</option>
          <option value="은행법">은행법</option>
          <option value="상품설명서">상품설명서</option>
          <option value="서식">서식</option>
          <option value="약관">약관</option>
          <option value="FAQ">FAQ</option>
        </select>
      </div>

      {/* 문서 목록 */}
      {loading ? (
        <div className="flex justify-center items-center h-32">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
        </div>
      ) : documents.length > 0 ? (
        <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    제목
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    카테고리
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    파일 타입
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    크기
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    다운로드 수
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    인덱싱 상태
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    업로드일
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {documents.map((doc: any) => (
                  <tr key={doc.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm font-medium text-gray-900">{doc.title}</div>
                      {doc.description && (
                        <div className="text-sm text-gray-500">{doc.description}</div>
                      )}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {doc.category}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {doc.file_type.toUpperCase()}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {(doc.file_size / 1024 / 1024).toFixed(2)} MB
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {doc.download_count}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${
                        doc.is_indexed 
                          ? 'bg-green-100 text-green-800' 
                          : 'bg-red-100 text-red-800'
                      }`}>
                        {doc.is_indexed ? '완료' : '대기'}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {new Date(doc.upload_date + (doc.upload_date.includes('Z') ? '' : 'Z')).toLocaleDateString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <div className="bg-gray-50 rounded-lg p-8 text-center">
          <PaperAirplaneIcon className="w-16 h-16 text-gray-400 mx-auto mb-4" />
          <p className="text-gray-600">문서를 찾을 수 없습니다.</p>
        </div>
      )}
    </div>
  )
}

// 시스템 로그 탭
function SystemLogTab() {
  const [logs, setLogs] = useState([])
  const [loading, setLoading] = useState(true)
  const [logType, setLogType] = useState('')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')

  useEffect(() => {
    loadLogs()
  }, [logType, startDate, endDate])

  const loadLogs = async () => {
    try {
      setLoading(true)
      const response = await adminAPI.getSystemLogs(
        logType || undefined,
        startDate || undefined,
        endDate || undefined
      )
      setLogs(response.logs || [])
    } catch (error) {
      console.error('시스템 로그 로드 실패:', error)
      setLogs([])
    } finally {
      setLoading(false)
    }
  }

  const getLogTypeColor = (type: string) => {
    switch (type) {
      case 'user_activity': return 'bg-blue-100 text-blue-800'
      case 'chat_activity': return 'bg-green-100 text-green-800'
      case 'system_error': return 'bg-red-100 text-red-800'
      default: return 'bg-gray-100 text-gray-800'
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-xl font-semibold text-gray-900">시스템 로그</h2>
        <div className="flex gap-2">
          <select 
            value={logType}
            onChange={(e) => setLogType(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-2"
          >
            <option value="">전체 로그</option>
            <option value="user_activity">사용자 활동</option>
            <option value="chat_activity">채팅 활동</option>
            <option value="system_error">시스템 오류</option>
          </select>
          <button className="bg-gray-100 text-gray-700 px-4 py-2 rounded-lg hover:bg-gray-200 transition-colors">
            로그 다운로드
          </button>
        </div>
      </div>
      
      {/* 날짜 필터 */}
      <div className="flex gap-4">
        <input
          type="date"
          placeholder="시작 날짜"
          value={startDate}
          onChange={(e) => setStartDate(e.target.value)}
          className="border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-primary-500 focus:border-transparent"
        />
        <input
          type="date"
          placeholder="종료 날짜"
          value={endDate}
          onChange={(e) => setEndDate(e.target.value)}
          className="border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-primary-500 focus:border-transparent"
        />
      </div>

      {/* 로그 목록 */}
      {loading ? (
        <div className="flex justify-center items-center h-32">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
        </div>
      ) : logs.length > 0 ? (
        <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    타입
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    메시지
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    상세 정보
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    시간
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {logs.map((log: any) => (
                  <tr key={log.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${getLogTypeColor(log.type)}`}>
                        {log.type}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-900">
                      {log.message}
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-500">
                      {log.details ? JSON.stringify(log.details) : '-'}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {new Date(log.timestamp + (log.timestamp.includes('Z') ? '' : 'Z')).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <div className="bg-gray-50 rounded-lg p-8 text-center">
          <EyeIcon className="w-16 h-16 text-gray-400 mx-auto mb-4" />
          <p className="text-gray-600">시스템 로그를 찾을 수 없습니다.</p>
        </div>
      )}
    </div>
  )
}
