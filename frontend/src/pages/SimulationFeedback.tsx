/**
 * 시뮬레이션 피드백 페이지
 * 6가지 역량 평가 결과를 시각화하여 표시
 */
import { useState, useEffect } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import {
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Cell
} from 'recharts'
import {
  BookOpenIcon,
  WrenchScrewdriverIcon,
  HeartIcon,
  ChatBubbleLeftIcon,
  FaceSmileIcon,
  BoltIcon,
  TrophyIcon,
  ArrowLeftIcon,
  CheckCircleIcon,
  XCircleIcon,
  UserIcon,
  DocumentTextIcon,
  ChevronDownIcon,
  ChevronUpIcon
} from '@heroicons/react/24/outline'

interface CompetencyScore {
  name: string
  score: number
  maxScore: number
}

interface GoalAchievement {
  total: number
  achieved: number
  rate: number
  goals: Array<{
    text: string
    achieved: boolean
    turn?: number  // 🔍 2단계: 달성한 턴 번호
    evidence?: string  // 🔍 3단계: 달성 증거 발화
  }>
}

interface FeedbackData {
  overallScore: number
  grade: string
  performanceLevel: string
  summary: string
  persona_info?: string
  situation_info?: string
  competencies: CompetencyScore[]
  detailedFeedback: {
    knowledge: { score: number; feedback: string }
    skill: { score: number; feedback: string }
    kindness: { score: number; feedback: string }
    clarity_confidence: { score: number; feedback: string }
    // 하위 호환성을 위해 기존 필드도 유지 (deprecated)
    empathy?: { score: number; feedback: string }
    clarity?: { score: number; feedback: string }
    confidence?: { score: number; feedback: string }
  }
  improvements: string | string[]  // 문자열 또는 배열 모두 허용
  duration_seconds?: number
  conversation_history?: Array<{ role: string; text: string; timestamp?: string }>
  goalAchievement?: GoalAchievement
}

const SimulationFeedback: React.FC = () => {
  const navigate = useNavigate()
  const location = useLocation()
  const [feedbackData, setFeedbackData] = useState<FeedbackData | null>(null)
  const [loading, setLoading] = useState(true)
  const [isGoalsExpanded, setIsGoalsExpanded] = useState(false) // 목표 달성 현황 접기/펼치기 상태
  const fromHistory = location.state?.fromHistory || false // 히스토리에서 온 경우인지 확인
  const returnScrollY = location.state?.returnScrollY || 0 // 돌아갈 스크롤 위치

  useEffect(() => {
    // 페이지 진입 시 항상 맨 위로 스크롤
    window.scrollTo(0, 0)
    
    // location.state에서 피드백 데이터를 받아오거나, API에서 조회
    if (location.state?.feedbackData) {
      setFeedbackData(location.state.feedbackData)
      setLoading(false)
    } else {
      // 샘플 데이터로 폴백 (테스트 및 미리보기용)
      loadFeedbackData()
    }
  }, [location.state])

  const loadFeedbackData = async () => {
    // 샘플 데이터 (테스트 및 미리보기용)
    // 실제 시뮬레이션에서는 location.state로 데이터가 전달됨
    setFeedbackData({
      overallScore: 87,
      grade: 'B',
      performanceLevel: '우수한 성과',
      summary: '전반적으로 우수한 고객 응대 역량을 보여주고 있습니다. 특히 친절도와 공감도 부분에서 탁월한 능력을 발휘하고 있으며, 안내 흐름을 더욱 체계적으로 수행한다면 완벽한 은행원으로 성장할 수 있을 것입니다.',
      competencies: [
        { name: '지식', score: 85, maxScore: 100 },
        { name: '기술', score: 78, maxScore: 100 },
        { name: '친절도', score: 95, maxScore: 100 },
        { name: '전달력', score: 85, maxScore: 100 }
      ],
      detailedFeedback: {
        knowledge: {
          score: 85,
          feedback: '상품에 대한 설명이 정확하고 상세합니다. 예적금, 대출, 카드 등 주요 상품의 특징과 이자, 가입조건을 정확하게 안내하였습니다. 다만 신상품에 대한 추가 학습이 필요합니다.'
        },
        skill: {
          score: 78,
          feedback: '고객의 니즈를 파악하는 질문 단계와 상담 안내 후 확인 절차를 대체로 잘 수행하였습니다. 다만 일부 상황에서 \'질문 → 응답 → 확인\'의 흐름이 생략되거나 순서가 바뀌는 경우가 있었습니다.'
        },
        kindness: {
          score: 95,
          feedback: '매우 친절한 응대를 보여주었습니다. \'감사합니다.\', \'도움이 되셨기를 바랍니다.\', \'궁금하신 점이 더 있으신가요?\' 등 정중한 표현을 자주 사용하였고, 고객을 배려하는 태도가 돋보였습니다.'
        },
        clarity_confidence: {
          score: 85,
          feedback: '명확성과 자신감을 종합 평가한 결과입니다.\n\n명확성 측면: 문장이 간결하고 명확합니다. 복잡한 금융용어를 쉽게 풀어서 설명하였고, 한 문장에 한 가지 내용만 전달하여 고객이 이해하기 쉽게 안내하였습니다. 적절한 문장 길이를 유지하고 있습니다.\n\n자신감 측면: 대부분 단정적이고 확실한 어투로 안내하였습니다. \'~입니다.\', \'~됩니다.\'의 명확한 표현을 사용했으나, 간혹 \'~같습니다.\', \'~것 같아요.\' 같은 불확실한 표현이 사용되었습니다. 더욱 자신감 있는 어투를 유지하세요.\n\n전반적으로 정보를 명확하고 확신 있게 전달하는 역량입니다.'
        }
      },
      improvements: '친절도는 잘 유지하시면서 \'질문 → 응답 → 확인\' 흐름을 더 체계적으로 수행하고 전달력을 향상시키는 연습을 하시면 더욱 전문적인 응대가 가능합니다.'
    })
    setLoading(false)
  }

  const getGradeColor = (grade: string) => {
    switch (grade) {
      case 'A': return 'text-green-600'
      case 'B': return 'text-blue-600'
      case 'C': return 'text-yellow-600'
      case 'D': return 'text-orange-600'
      case 'F': return 'text-red-600'
      default: return 'text-gray-600'
    }
  }

  const getPerformanceLevelStyle = (level: string) => {
    if (level.includes('우수') || level.includes('탁월')) {
      return 'bg-blue-500 text-white'
    } else if (level.includes('양호') || level.includes('보통')) {
      return 'bg-green-500 text-white'
    } else {
      return 'bg-yellow-500 text-white'
    }
  }

  const getCompetencyIcon = (name: string) => {
    switch (name) {
      case '지식':
        return <BookOpenIcon className="w-6 h-6 text-blue-600" />
      case '기술':
        return <WrenchScrewdriverIcon className="w-6 h-6 text-purple-600" />
      case '친절도':
        return <FaceSmileIcon className="w-6 h-6 text-yellow-600" />
      case '전달력':
        return <ChatBubbleLeftIcon className="w-6 h-6 text-green-600" />
      // 하위 호환성 (deprecated)
      case '공감도':
        return <HeartIcon className="w-6 h-6 text-red-600" />
      case '명확성':
        return <ChatBubbleLeftIcon className="w-6 h-6 text-green-600" />
      case '친절도':
        return <FaceSmileIcon className="w-6 h-6 text-yellow-600" />
      case '자신감':
        return <BoltIcon className="w-6 h-6 text-orange-600" />
      default:
        return null
    }
  }

  const getCompetencyColor = (name: string) => {
    // 모든 막대 그래프를 파란색으로 통일
    return '#3B82F6' // blue-600
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="text-gray-600 mt-4">피드백을 불러오는 중...</p>
        </div>
      </div>
    )
  }

  if (!feedbackData) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <p className="text-gray-600">피드백 데이터를 찾을 수 없습니다.</p>
          <button
            onClick={() => navigate('/simulation')}
            className="mt-4 px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            시뮬레이션으로 돌아가기
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 via-gray-50 to-blue-50/30 py-6 px-4">
      <div className="max-w-6xl mx-auto">
        {/* 히스토리에서 온 경우 상단에 뒤로가기 버튼 */}
        {fromHistory && (
          <div className="mb-4">
            <button
              onClick={() => navigate('/dashboard', { 
                state: { 
                  activeTab: 'simulation',
                  returnScrollY: returnScrollY
                } 
              })}
              className="flex items-center gap-2 px-4 py-2 bg-white hover:bg-gray-50 text-gray-700 rounded-lg border border-gray-200 shadow-sm transition-all"
            >
              <ArrowLeftIcon className="w-5 h-5" />
              <span className="font-medium">대시보드로 돌아가기</span>
            </button>
          </div>
        )}

        {/* 페이지 헤더 */}
        <div className="mb-6">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">시뮬레이션 평가 결과</h1>
          <p className="text-gray-600">고객 응대 역량을 종합적으로 평가한 결과입니다</p>
        </div>

        {/* 시뮬레이션 정보 섹션 - 페르소나와 상황 정보 */}
        {(feedbackData.persona_info || feedbackData.situation_info) && (
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5 mb-6">
            <div className="flex items-center gap-2 mb-4">
              <div className="w-1 h-5 bg-blue-600 rounded-full"></div>
              <h2 className="text-base font-semibold text-gray-800">시뮬레이션 정보</h2>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {feedbackData.persona_info && (
                <div className="flex items-center gap-3 p-3 bg-blue-50/50 rounded-lg border border-blue-100">
                  <div className="flex-shrink-0 p-2 bg-blue-500 rounded-lg">
                    <UserIcon className="w-4 h-4 text-white" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-xs font-medium text-gray-600 mb-0.5">페르소나</div>
                    <div className="text-sm font-semibold text-gray-900">
                      {feedbackData.persona_info}
                    </div>
                  </div>
                </div>
              )}
              
              {feedbackData.situation_info && (
                <div className="flex items-center gap-3 p-3 bg-indigo-50/50 rounded-lg border border-indigo-100">
                  <div className="flex-shrink-0 p-2 bg-indigo-500 rounded-lg">
                    <DocumentTextIcon className="w-4 h-4 text-white" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-xs font-medium text-gray-600 mb-0.5">상황</div>
                    <div className="text-sm font-semibold text-gray-900">
                      {feedbackData.situation_info}
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* 종합 점수 섹션 */}
        <div className="bg-gradient-to-br from-white to-blue-50/30 rounded-xl shadow-lg border-2 border-blue-100 p-8 mb-8">
          <div className="text-center mb-6">
            <h2 className="text-sm font-semibold text-gray-600 uppercase tracking-wider mb-2">종합 평가</h2>
            <div className="flex items-baseline justify-center gap-3 mb-3">
              <span className={`text-7xl font-extrabold ${getGradeColor(feedbackData.grade)}`}>
                {feedbackData.overallScore.toFixed(1)}
              </span>
              <span className="text-3xl font-bold text-gray-700">/ 100</span>
            </div>
            <div className="flex items-center justify-center gap-3 mb-4">
              <span className={`text-2xl font-bold ${getGradeColor(feedbackData.grade)}`}>
                {feedbackData.grade}
              </span>
              <span className="text-gray-400">등급</span>
              <div className={`px-4 py-1.5 rounded-full text-sm font-semibold ${getPerformanceLevelStyle(feedbackData.performanceLevel)}`}>
                {feedbackData.performanceLevel}
              </div>
            </div>
          </div>
          <div className="bg-white/60 backdrop-blur-sm rounded-lg p-5 border border-gray-200">
            <p className="text-gray-800 leading-relaxed text-center">
              {feedbackData.summary}
            </p>
          </div>
        </div>

        {/* 역량별 평가 섹션 */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
          <div className="flex items-center gap-2 mb-6">
            <div className="w-1 h-5 bg-indigo-600 rounded-full"></div>
            <h2 className="text-lg font-bold text-gray-900">역량별 평가</h2>
          </div>
          
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* 레이더 차트 */}
            <div className="bg-gray-50 rounded-lg p-4 border border-gray-200">
              <h3 className="text-sm font-semibold text-gray-700 mb-4 text-center">종합 역량 분포</h3>
              <ResponsiveContainer width="100%" height={300}>
                <RadarChart data={feedbackData.competencies}>
                  <PolarGrid 
                    stroke="#E2E8F0"
                    strokeWidth={1}
                  />
                  <PolarAngleAxis 
                    dataKey="name" 
                    tick={{ 
                      fill: '#475569', 
                      fontSize: 12, 
                      fontWeight: 600
                    }}
                  />
                  <PolarRadiusAxis 
                    angle={90} 
                    domain={[0, 100]}
                    tick={{ fill: '#94A3B8', fontSize: 9 }}
                    tickCount={5}
                    stroke="#E2E8F0"
                  />
                  <Radar 
                    name="점수" 
                    dataKey="score" 
                    stroke="#3B82F6" 
                    fill="#3B82F6"
                    fillOpacity={0.6}
                    strokeWidth={2}
                    dot={{ fill: '#3B82F6', r: 4 }}
                  />
                  <Tooltip 
                    contentStyle={{
                      backgroundColor: 'white',
                      border: '1px solid #E2E8F0',
                      borderRadius: '8px',
                      padding: '8px 12px',
                      boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)'
                    }}
                    formatter={(value: number) => [`${value}점`, '']}
                  />
                </RadarChart>
              </ResponsiveContainer>
            </div>

            {/* 막대 그래프 */}
            <div className="space-y-3">
              <h3 className="text-sm font-semibold text-gray-700 mb-4">역량별 점수</h3>
              {feedbackData.competencies.map((comp, index) => (
                <div key={index} className="bg-gray-50 rounded-lg p-3 border border-gray-200">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-semibold text-gray-800">{comp.name}</span>
                    <span className="text-base font-bold text-gray-900">{comp.score}점</span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-2.5 overflow-hidden">
                    <div
                      className="h-2.5 rounded-full transition-all duration-700 ease-out"
                      style={{
                        width: `${(comp.score / comp.maxScore) * 100}%`,
                        backgroundColor: getCompetencyColor(comp.name)
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* 상세 피드백 섹션 */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
          <div className="flex items-center gap-2 mb-6">
            <div className="w-1 h-5 bg-purple-600 rounded-full"></div>
            <h2 className="text-lg font-bold text-gray-900">상세 역량별 피드백</h2>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {/* 지식 */}
            <div className="bg-gray-50 border border-gray-200 rounded-lg p-5 hover:shadow-md transition-shadow">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  {getCompetencyIcon('지식')}
                  <h3 className="text-base font-semibold text-gray-900">지식</h3>
                </div>
                <span className="text-lg font-bold text-blue-600">
                  {feedbackData.detailedFeedback.knowledge.score}
                </span>
              </div>
              <p className="text-sm text-gray-700 leading-relaxed">
                {feedbackData.detailedFeedback.knowledge.feedback}
              </p>
            </div>

            {/* 기술 */}
            <div className="bg-gray-50 border border-gray-200 rounded-lg p-5 hover:shadow-md transition-shadow">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  {getCompetencyIcon('기술')}
                  <h3 className="text-base font-semibold text-gray-900">기술</h3>
                </div>
                <span className="text-lg font-bold text-purple-600">
                  {feedbackData.detailedFeedback.skill.score}
                </span>
              </div>
              <p className="text-sm text-gray-700 leading-relaxed">
                {feedbackData.detailedFeedback.skill.feedback}
              </p>
            </div>

            {/* 친절도 */}
            <div className="bg-gray-50 border border-gray-200 rounded-lg p-5 hover:shadow-md transition-shadow">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  {getCompetencyIcon('친절도')}
                  <h3 className="text-base font-semibold text-gray-900">친절도</h3>
                </div>
                <span className="text-lg font-bold text-yellow-600">
                  {feedbackData.detailedFeedback.kindness.score}
                </span>
              </div>
              <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-line">
                {feedbackData.detailedFeedback.kindness.feedback}
              </p>
            </div>

            {/* 전달력 */}
            <div className="bg-gray-50 border border-gray-200 rounded-lg p-5 hover:shadow-md transition-shadow">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  {getCompetencyIcon('전달력')}
                  <h3 className="text-base font-semibold text-gray-900">전달력</h3>
                </div>
                <span className="text-lg font-bold text-green-600">
                  {feedbackData.detailedFeedback.clarity_confidence.score}
                </span>
              </div>
              <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-line">
                {feedbackData.detailedFeedback.clarity_confidence.feedback}
              </p>
            </div>
          </div>
        </div>

        {/* 개선 제안 섹션 */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
          <div className="flex items-center gap-2 mb-5">
            <div className="w-1 h-5 bg-amber-600 rounded-full"></div>
            <h2 className="text-lg font-bold text-gray-900">개선 제안</h2>
          </div>
          <div className="bg-amber-50/50 border border-amber-200 rounded-lg p-5">
            {Array.isArray(feedbackData.improvements) ? (
              <ul className="space-y-2.5">
                {feedbackData.improvements.map((item, index) => (
                  <li key={index} className="flex items-start gap-3">
                    <span className="flex-shrink-0 w-5 h-5 rounded-full bg-amber-500 text-white text-xs font-bold flex items-center justify-center mt-0.5">
                      {index + 1}
                    </span>
                    <span className="text-sm text-gray-800 leading-relaxed flex-1 pt-0.5">{item}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-gray-800 leading-relaxed">
                {feedbackData.improvements}
              </p>
            )}
          </div>
        </div>

        {/* 목표 달성 현황 섹션 */}
        {feedbackData.goalAchievement && feedbackData.goalAchievement.total > 0 && (
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
            <div className="flex items-center gap-2 mb-5">
              <div className="w-1 h-5 bg-green-600 rounded-full"></div>
              <h2 className="text-lg font-bold text-gray-900 flex items-center gap-2">
                <TrophyIcon className="w-5 h-5 text-green-600" />
                목표 달성 현황
              </h2>
            </div>
            
            {/* 달성률 헤더 */}
            <div className="bg-gray-50 rounded-lg p-5 mb-4 border border-gray-200">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-baseline gap-2">
                  <span className="text-4xl font-extrabold text-green-600">
                    {feedbackData.goalAchievement.achieved}
                  </span>
                  <span className="text-xl text-gray-400">/</span>
                  <span className="text-xl font-semibold text-gray-600">
                    {feedbackData.goalAchievement.total}
                  </span>
                </div>
                <div className="text-right">
                  <div className="text-xs text-gray-600 mb-1">달성률</div>
                  <div className="text-2xl font-bold text-green-600">
                    {Math.round(feedbackData.goalAchievement.rate * 100)}%
                  </div>
                </div>
              </div>
              
              {/* 진행률 바 */}
              <div className="w-full bg-gray-200 rounded-full h-3 overflow-hidden mb-4">
                <div 
                  className="h-3 rounded-full transition-all duration-700 ease-out"
                  style={{ 
                    width: `${feedbackData.goalAchievement.rate * 100}%`,
                    background: feedbackData.goalAchievement.rate >= 0.8 
                      ? 'linear-gradient(90deg, #10B981 0%, #34D399 100%)'
                      : feedbackData.goalAchievement.rate >= 0.5
                      ? 'linear-gradient(90deg, #3B82F6 0%, #60A5FA 100%)'
                      : 'linear-gradient(90deg, #F59E0B 0%, #FBBF24 100%)'
                  }}
                />
              </div>
              
              {/* 접기/펼치기 토글 버튼 */}
              <button
                onClick={() => setIsGoalsExpanded(!isGoalsExpanded)}
                className="flex items-center justify-between w-full p-2.5 text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 border border-gray-300 rounded-lg transition-all"
              >
                <span className="flex items-center gap-2">
                  목표 상세 보기
                  <span className="text-xs text-gray-500 font-normal">
                    ({feedbackData.goalAchievement.goals.length}개)
                  </span>
                </span>
                {isGoalsExpanded ? (
                  <ChevronUpIcon className="w-4 h-4 text-gray-500" />
                ) : (
                  <ChevronDownIcon className="w-4 h-4 text-gray-500" />
                )}
              </button>
            </div>
            
            {/* 목표 목록 - 간결한 체크리스트 (증거 포함) */}
            {isGoalsExpanded && (
              <div className="space-y-2.5 mb-5">
                {feedbackData.goalAchievement.goals.map((goal, idx) => (
                  <div 
                    key={idx} 
                    className={`rounded-lg border transition-all ${
                      goal.achieved 
                        ? 'bg-green-50/50 border-green-300' 
                        : 'bg-gray-50 border-gray-300'
                    }`}
                  >
                    {/* 목표 제목 */}
                    <div className="flex items-start gap-3 p-3">
                      {goal.achieved ? (
                        <CheckCircleIcon className="w-5 h-5 text-green-600 flex-shrink-0 mt-0.5" />
                      ) : (
                        <XCircleIcon className="w-5 h-5 text-gray-400 flex-shrink-0 mt-0.5" />
                      )}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className={`text-sm font-medium ${
                            goal.achieved ? 'text-gray-900' : 'text-gray-600'
                          }`}>
                            {goal.text}
                          </span>
                          {/* 턴 번호 표시 */}
                          {goal.achieved && goal.turn && (
                            <span className="px-2 py-0.5 bg-green-500 text-white text-xs rounded font-semibold">
                              턴 {goal.turn}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                    
                    {/* 증거 발화 표시 */}
                    {goal.achieved && goal.evidence && goal.evidence.trim() && (
                      <div className="px-3 pb-3 pl-11">
                        <div className="bg-white border border-green-300 rounded-lg p-3">
                          <div className="flex items-center gap-2 mb-1.5">
                            <ChatBubbleLeftIcon className="w-3.5 h-3.5 text-green-600" />
                            <span className="text-xs font-semibold text-green-700">달성 발화</span>
                          </div>
                          <p className="text-xs text-gray-800 leading-relaxed pl-5">
                            "{goal.evidence}"
                          </p>
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
            
            {/* 하단 통계 */}
            {isGoalsExpanded && (
              <div className="pt-4 border-t border-gray-300">
                <div className="grid grid-cols-3 gap-3 text-center">
                  <div className="bg-gray-50 rounded-lg p-3">
                    <p className="text-xs text-gray-600 mb-1">전체 목표</p>
                    <p className="text-lg font-bold text-gray-900">{feedbackData.goalAchievement.total}개</p>
                  </div>
                  <div className="bg-green-50 rounded-lg p-3">
                    <p className="text-xs text-gray-600 mb-1">달성 목표</p>
                    <p className="text-lg font-bold text-green-600">{feedbackData.goalAchievement.achieved}개</p>
                  </div>
                  <div className="bg-orange-50 rounded-lg p-3">
                    <p className="text-xs text-gray-600 mb-1">미달성 목표</p>
                    <p className="text-lg font-bold text-orange-600">
                      {feedbackData.goalAchievement.total - feedbackData.goalAchievement.achieved}개
                    </p>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* 대화 로그 섹션 */}
        {feedbackData.conversation_history && feedbackData.conversation_history.length > 0 && (
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <div className="w-1 h-5 bg-gray-600 rounded-full"></div>
                <h2 className="text-lg font-bold text-gray-900">대화 로그</h2>
              </div>
              {feedbackData.duration_seconds && (
                <span className="text-xs text-gray-600 bg-gray-100 px-3 py-1 rounded-full">
                  {Math.floor(feedbackData.duration_seconds / 60)}분 {feedbackData.duration_seconds % 60}초
                </span>
              )}
            </div>
            <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 max-h-96 overflow-y-auto">
              <div className="space-y-3">
                {(() => {
                  // 직원 발화 턴 번호 계산 (직원 발화만 카운트)
                  let employeeTurnCount = 0
                  
                  // 목표 달성 정보를 턴 번호로 매핑
                  const goalByTurn = new Map<number, Array<{ text: string; evidence?: string }>>()
                  if (feedbackData.goalAchievement) {
                    feedbackData.goalAchievement.goals.forEach(goal => {
                      if (goal.achieved && goal.turn) {
                        if (!goalByTurn.has(goal.turn)) {
                          goalByTurn.set(goal.turn, [])
                        }
                        goalByTurn.get(goal.turn)!.push({
                          text: goal.text,
                          evidence: goal.evidence
                        })
                      }
                    })
                  }
                  
                  return feedbackData.conversation_history.map((msg, index) => {
                    // 직원 발화인 경우 턴 번호 증가
                    const isEmployee = msg.role === 'employee' || msg.role === 'user'
                    if (isEmployee) {
                      employeeTurnCount++
                    }
                    
                    // 현재 발화가 달성한 목표 찾기
                    const achievedGoals = isEmployee && employeeTurnCount > 0 
                      ? goalByTurn.get(employeeTurnCount) || []
                      : []
                    
                    return (
                      <div 
                        key={index} 
                        className={`flex ${isEmployee ? 'justify-end' : 'justify-start'}`}
                      >
                        <div 
                          className={`max-w-[75%] rounded-lg px-3 py-2.5 ${
                            isEmployee
                              ? 'bg-blue-600 text-white' 
                              : 'bg-white border border-gray-300 text-gray-900 shadow-sm'
                          }`}
                        >
                          <div className="flex items-center justify-between mb-1.5">
                            <div className="text-xs font-medium opacity-80">
                              {isEmployee ? '신입사원' : '고객'}
                            </div>
                            {isEmployee && employeeTurnCount > 0 && (
                              <span className="text-xs font-medium opacity-80">
                                턴 {employeeTurnCount}
                              </span>
                            )}
                          </div>
                          <p className="text-sm leading-relaxed whitespace-pre-wrap">{msg.text}</p>
                          
                          {/* 목표 달성 배지 */}
                          {achievedGoals.length > 0 && (
                            <div className="mt-2 pt-2 border-t border-opacity-20">
                              {achievedGoals.map((goal, goalIdx) => (
                                <div 
                                  key={goalIdx}
                                  className="flex items-center gap-2 mb-1.5 last:mb-0"
                                >
                                  <CheckCircleIcon className={`w-4 h-4 flex-shrink-0 ${
                                    isEmployee ? 'text-green-200' : 'text-green-600'
                                  }`} />
                                  <div className={`text-xs font-semibold ${
                                    isEmployee ? 'text-green-100' : 'text-green-700'
                                  }`}>
                                    목표 달성: {goal.text}
                                  </div>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>
                    )
                  })
                })()}
              </div>
            </div>
          </div>
        )}

        {/* 하단 액션 버튼 (히스토리에서 온 경우 표시하지 않음) */}
        {!fromHistory && (
          <div className="flex justify-center gap-3 mt-8 mb-6">
            <button
              onClick={() => navigate('/simulation')}
              className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-semibold shadow-md hover:shadow-lg transition-all"
            >
              새로운 시뮬레이션 시작
            </button>
            <button
              onClick={() => navigate('/dashboard', { state: { activeTab: 'simulation' } })}
              className="px-6 py-3 bg-white text-gray-700 rounded-lg hover:bg-gray-50 font-semibold border border-gray-300 shadow-sm hover:shadow-md transition-all"
            >
              대시보드로 이동
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

export default SimulationFeedback

