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
  ArrowLeftIcon
} from '@heroicons/react/24/outline'

interface CompetencyScore {
  name: string
  score: number
  maxScore: number
}

interface FeedbackData {
  overallScore: number
  grade: string
  performanceLevel: string
  summary: string
  competencies: CompetencyScore[]
  detailedFeedback: {
    knowledge: { score: number; feedback: string }
    skill: { score: number; feedback: string }
    empathy: { score: number; feedback: string }
    clarity: { score: number; feedback: string }
    kindness: { score: number; feedback: string }
    confidence: { score: number; feedback: string }
  }
  improvements: string
}

const SimulationFeedback: React.FC = () => {
  const navigate = useNavigate()
  const location = useLocation()
  const [feedbackData, setFeedbackData] = useState<FeedbackData | null>(null)
  const [loading, setLoading] = useState(true)
  const fromHistory = location.state?.fromHistory || false // 히스토리에서 온 경우인지 확인

  useEffect(() => {
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
        { name: '공감도', score: 92, maxScore: 100 },
        { name: '명확성', score: 88, maxScore: 100 },
        { name: '친절도', score: 95, maxScore: 100 },
        { name: '자신감', score: 82, maxScore: 100 }
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
        empathy: {
          score: 92,
          feedback: '고객의 상황에 공감하는 표현을 적절히 사용하였습니다. \'고객님의 상황을 잘 이해합니다.\', \'그러한 부분이 걱정되실 수 있습니다.\'등 고객의 입장을 이해하는 말을 자주 사용하여 신뢰감을 형성했습니다.'
        },
        clarity: {
          score: 88,
          feedback: '문장이 간결하고 명확합니다. 복잡한 금융용어를 쉽게 풀어서 설명하였고, 한 문장에 한 가지 내용만 전달하여 고객이 이해하기 쉽게 안내하였습니다. 적절한 문장 길이를 유지하고 있습니다.'
        },
        kindness: {
          score: 95,
          feedback: '매우 친절한 응대를 보여주었습니다. \'감사합니다.\', \'도움이 되셨기를 바랍니다.\', \'궁금하신 점이 더 있으신가요?\' 등 정중한 표현을 자주 사용하였고, 고객을 배려하는 태도가 돋보였습니다.'
        },
        confidence: {
          score: 82,
          feedback: '대부분 단정적이고 확실한 어투로 안내하였습니다. \'~입니다.\', \'~됩니다.\'의 명확한 표현을 사용했으나, 간혹 \'~같습니다.\', \'~것 같아요.\' 같은 불확실한 표현이 사용되었습니다. 더욱 자신감 있는 어투를 유지하세요.'
        }
      },
      improvements: '친절도와 공감도는 잘 유지하시면서 \'질문 → 응답 → 확인\' 흐름을 더 체계적으로 수행하고 확실한 어투를 사용하는 연습을 하시면 더욱 전문적인 응대가 가능합니다.'
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
    <div className="min-h-screen bg-gray-50 py-8 px-4">
      <div className="max-w-5xl mx-auto">
        {/* 히스토리에서 온 경우 상단에 뒤로가기 버튼 */}
        {fromHistory && (
          <div className="mb-6">
            <button
              onClick={() => navigate('/dashboard', { state: { activeTab: 'simulation' } })}
              className="flex items-center gap-2 px-4 py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg transition-colors"
            >
              <ArrowLeftIcon className="w-5 h-5" />
              <span className="font-medium">대시보드로 돌아가기</span>
            </button>
          </div>
        )}

        {/* 종합 점수 섹션 */}
        <div className="bg-white rounded-lg shadow-md p-8 mb-6">
          <h2 className="text-xl font-semibold text-gray-800 mb-4 text-center">종합 점수</h2>
          <div className="flex items-center justify-center mb-4">
            <div className="flex items-baseline">
              <span className={`text-6xl font-bold ${getGradeColor(feedbackData.grade)}`}>
                {feedbackData.overallScore}
              </span>
              <span className="text-2xl text-gray-600 ml-2">{feedbackData.grade} 등급</span>
            </div>
          </div>
          <div className="flex justify-center mb-4">
            <div className={`px-4 py-2 rounded-lg ${getPerformanceLevelStyle(feedbackData.performanceLevel)}`}>
              {feedbackData.performanceLevel}
            </div>
          </div>
          <p className="text-gray-700 mt-4 leading-relaxed">
            {feedbackData.summary}
          </p>
        </div>

        {/* 역량별 평가 섹션 */}
        <div className="bg-white rounded-lg shadow-md p-8 mb-6">
          <h2 className="text-xl font-semibold text-gray-800 mb-6">역량별 평가</h2>
          
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            {/* 레이더 차트 */}
            <div className="relative bg-gradient-to-br from-blue-50 to-indigo-50 rounded-2xl p-6 shadow-inner">
              <div className="absolute inset-0 bg-white/40 backdrop-blur-sm rounded-2xl"></div>
              <div className="relative">
                <ResponsiveContainer width="100%" height={320}>
                  <RadarChart data={feedbackData.competencies}>
                    <defs>
                      <linearGradient id="radarGradient" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#3B82F6" stopOpacity={0.8} />
                        <stop offset="100%" stopColor="#8B5CF6" stopOpacity={0.3} />
                      </linearGradient>
                      <filter id="shadow" x="-50%" y="-50%" width="200%" height="200%">
                        <feGaussianBlur in="SourceAlpha" stdDeviation="3" />
                        <feOffset dx="0" dy="2" result="offsetblur" />
                        <feComponentTransfer>
                          <feFuncA type="linear" slope="0.3" />
                        </feComponentTransfer>
                        <feMerge>
                          <feMergeNode />
                          <feMergeNode in="SourceGraphic" />
                        </feMerge>
                      </filter>
                    </defs>
                    <PolarGrid 
                      stroke="#CBD5E1"
                      strokeWidth={1.5}
                      strokeDasharray="3 3"
                    />
                    <PolarAngleAxis 
                      dataKey="name" 
                      tick={{ 
                        fill: '#1E293B', 
                        fontSize: 13, 
                        fontWeight: 600,
                        fontFamily: 'system-ui, -apple-system, sans-serif'
                      }}
                    />
                    <PolarRadiusAxis 
                      angle={90} 
                      domain={[0, 100]}
                      tick={{ fill: '#64748B', fontSize: 10, fontWeight: 500 }}
                      tickCount={6}
                      stroke="#E2E8F0"
                    />
                    <Radar 
                      name="점수" 
                      dataKey="score" 
                      stroke="#3B82F6" 
                      fill="url(#radarGradient)"
                      fillOpacity={0.7}
                      strokeWidth={3}
                    dot={false}
                    activeDot={false}
                      isAnimationActive={true}
                      animationBegin={200}
                      animationDuration={1800}
                      animationEasing="ease-in-out"
                    />
                    <Tooltip 
                      contentStyle={{
                        backgroundColor: 'rgba(255, 255, 255, 0.95)',
                        border: 'none',
                        borderRadius: '12px',
                        padding: '12px 16px',
                        boxShadow: '0 10px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)',
                        backdropFilter: 'blur(10px)'
                      }}
                      labelStyle={{ 
                        color: '#1E293B',
                        fontWeight: 700,
                        marginBottom: '6px',
                        fontSize: '14px'
                      }}
                      itemStyle={{ 
                        color: '#3B82F6',
                        fontSize: '15px',
                        fontWeight: 600
                      }}
                      formatter={(value: number) => [`${value}점`, '점수']}
                      cursor={{ stroke: '#3B82F6', strokeWidth: 2, strokeDasharray: '5 5' }}
                    />
                  </RadarChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* 막대 그래프 */}
            <div className="space-y-4">
              {feedbackData.competencies.map((comp, index) => (
                <div key={index}>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium text-gray-700">{comp.name}</span>
                    <span className="text-sm font-bold text-gray-900">{comp.score}점</span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-3">
                    <div
                      className="h-3 rounded-full transition-all duration-500"
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
        <div className="bg-white rounded-lg shadow-md p-8 mb-6">
          <h2 className="text-xl font-semibold text-gray-800 mb-6">상세 역량별 피드백</h2>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* 지식 */}
            <div className="border border-gray-200 rounded-lg p-6">
              <div className="flex items-center mb-3">
                {getCompetencyIcon('지식')}
                <h3 className="text-lg font-semibold text-gray-800 ml-2">지식</h3>
              </div>
              <div className="text-2xl font-bold text-blue-600 mb-2">
                {feedbackData.detailedFeedback.knowledge.score}/100
              </div>
              <p className="text-gray-700 text-sm leading-relaxed">
                {feedbackData.detailedFeedback.knowledge.feedback}
              </p>
            </div>

            {/* 기술 */}
            <div className="border border-gray-200 rounded-lg p-6">
              <div className="flex items-center mb-3">
                {getCompetencyIcon('기술')}
                <h3 className="text-lg font-semibold text-gray-800 ml-2">기술</h3>
              </div>
              <div className="text-2xl font-bold text-purple-600 mb-2">
                {feedbackData.detailedFeedback.skill.score}/100
              </div>
              <p className="text-gray-700 text-sm leading-relaxed">
                {feedbackData.detailedFeedback.skill.feedback}
              </p>
            </div>

            {/* 공감도 */}
            <div className="border border-gray-200 rounded-lg p-6">
              <div className="flex items-center mb-3">
                {getCompetencyIcon('공감도')}
                <h3 className="text-lg font-semibold text-gray-800 ml-2">공감도</h3>
              </div>
              <div className="text-2xl font-bold text-red-600 mb-2">
                {feedbackData.detailedFeedback.empathy.score}/100
              </div>
              <p className="text-gray-700 text-sm leading-relaxed">
                {feedbackData.detailedFeedback.empathy.feedback}
              </p>
            </div>

            {/* 명확성 */}
            <div className="border border-gray-200 rounded-lg p-6">
              <div className="flex items-center mb-3">
                {getCompetencyIcon('명확성')}
                <h3 className="text-lg font-semibold text-gray-800 ml-2">명확성</h3>
              </div>
              <div className="text-2xl font-bold text-green-600 mb-2">
                {feedbackData.detailedFeedback.clarity.score}/100
              </div>
              <p className="text-gray-700 text-sm leading-relaxed">
                {feedbackData.detailedFeedback.clarity.feedback}
              </p>
            </div>

            {/* 친절도 */}
            <div className="border border-gray-200 rounded-lg p-6">
              <div className="flex items-center mb-3">
                {getCompetencyIcon('친절도')}
                <h3 className="text-lg font-semibold text-gray-800 ml-2">친절도</h3>
              </div>
              <div className="text-2xl font-bold text-yellow-600 mb-2">
                {feedbackData.detailedFeedback.kindness.score}/100
              </div>
              <p className="text-gray-700 text-sm leading-relaxed">
                {feedbackData.detailedFeedback.kindness.feedback}
              </p>
            </div>

            {/* 자신감 */}
            <div className="border border-gray-200 rounded-lg p-6">
              <div className="flex items-center mb-3">
                {getCompetencyIcon('자신감')}
                <h3 className="text-lg font-semibold text-gray-800 ml-2">자신감</h3>
              </div>
              <div className="text-2xl font-bold text-orange-600 mb-2">
                {feedbackData.detailedFeedback.confidence.score}/100
              </div>
              <p className="text-gray-700 text-sm leading-relaxed">
                {feedbackData.detailedFeedback.confidence.feedback}
              </p>
            </div>
          </div>
        </div>

        {/* 개선 제안 섹션 */}
        <div className="bg-white rounded-lg shadow-md p-8">
          <h2 className="text-xl font-semibold text-gray-800 mb-4">개선 제안</h2>
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-6">
            <p className="text-gray-700 leading-relaxed">
              {feedbackData.improvements}
            </p>
          </div>
        </div>

        {/* 하단 액션 버튼 (히스토리에서 온 경우 표시하지 않음) */}
        {!fromHistory && (
          <div className="flex justify-center gap-4 mt-8">
            <button
              onClick={() => navigate('/simulation')}
              className="px-8 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium"
            >
              새로운 시뮬레이션 시작
            </button>
            <button
              onClick={() => navigate('/dashboard', { state: { activeTab: 'simulation' } })}
              className="px-8 py-3 bg-gray-600 text-white rounded-lg hover:bg-gray-700 font-medium"
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

