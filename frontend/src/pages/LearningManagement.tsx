import { useEffect, useMemo, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import {
  BookOpenIcon,
  ClipboardDocumentListIcon,
  ClockIcon,
  AdjustmentsHorizontalIcon,
  ChartBarSquareIcon,
  ArrowPathIcon,
  SparklesIcon,
} from '@heroicons/react/24/outline'
import {
  ResponsiveContainer,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  Tooltip as RadarTooltip,
} from 'recharts'

import Documents from './Documents'
import { quizAPI } from '../utils/api'
import { QuizData, QuizHistoryEntry, QuizMode, QuizQuestion, useQuizStore } from '../store/quizStore'

const CATEGORY_ORDER = [
  '금융영업',
  '상품개발 및 운용',
  '신용분석 및 리스크관리',
  '외환',
  '은행지식 및 관련법률',
  '하경은행',
]

const CHAPTER_NOTES = [
  '창구사무, 채권추심, 카드영업, 여신전문금융영업, 결제 등에 대한 직무 지식',
  '여수신, 펀드, 투자, 연금, 카드 상품개발과 펀드 및 파생상품운용 등에 대한 직무 지식',
  '개인신용분석, 여신심사, 리스크관리 등에 대한 직무 지식',
  '외화조달 및 외화대출, 외환 파생업무 등에 대한 직무 지식',
  '은행산업 관련 기본지식, 경제금융용어, 은행법률 등에 대한 실무 지식',
  '하경은행의 상품, 고객언어 가이드, FAQ 등에 대한 실무 지식',
]

const CATEGORY_COLOR_MAP: Record<string, string> = {
  '금융영업': '#2563eb',
  '상품개발 및 운용': '#ea580c',
  '신용분석 및 리스크관리': '#22c55e',
  '외환': '#0ea5e9',
  '은행지식 및 관련법률': '#a855f7',
  '하경은행': '#f97316',
}

const mockHistory = [
  {
    id: 'exam-1203',
    date: '2025-11-12',
    type: '중간 평가',
    score: 78,
    total: 120,
  },
  {
    id: 'exam-1187',
    date: '2025-11-05',
    type: '취약영역 집중',
    score: 84,
    total: 60,
  },
]

const mockProgress = [
  { category: '금융영업', accuracy: 0.82, solved: 240 },
  { category: '상품개발 및 운용', accuracy: 0.64, solved: 180 },
  { category: '신용분석 및 리스크관리', accuracy: 0.58, solved: 160 },
  { category: '외환', accuracy: 0.71, solved: 150 },
  { category: '은행지식 및 관련법률', accuracy: 0.69, solved: 200 },
  { category: '하경은행', accuracy: 0.76, solved: 130 },
]

const practiceModes = [
  {
    id: 'midfinal',
    title: '중간/최종 평가',
    description:
      '모든 연수생이 동일하게 응시하는 정규 평가 세트를 제공합니다. frontend/public/exams/의 midterm_quiz.json과 final_quiz.json을 통해 배포됩니다.',
    actions: [
      { label: '중간 평가', variant: 'primary', mode: 'midterm' as QuizMode },
      { label: '최종 평가', variant: 'primary', mode: 'final' as QuizMode },
    ],
  },
  {
    id: 'custom',
    title: '연습하기',
    description:
      '원하는 문항 수와 알고리즘으로 연습 세트를 생성합니다. 설정한 수만큼 dbquiz_eval.csv에서 문제를 추출합니다.',
    actions: [
      { label: '랜덤 세트', variant: 'primary', mode: 'random' as QuizMode },
      { label: '맞춤형 세트', variant: 'primary', mode: 'custom' as QuizMode },
    ],
  },
]

type QuizStartMode = QuizMode
type RadarDatum = { name: string; score: number; accuracy: number; solved: number; correct: number }

type StaticExamQuestion = Omit<QuizQuestion, 'category_name'>
type StaticExamCategory = { category_name: string; questions: StaticExamQuestion[] }
type StaticExamData = {
  exam_info: {
    title: string
    total_questions: number
    total_categories?: number
  }
  category: StaticExamCategory[]
}

const STATIC_EXAM_LOADERS: Record<'midterm' | 'final', () => Promise<StaticExamData>> = {
  midterm: () => fetch('/exams/midterm_quiz.json').then((res) => res.json()),
  final: () => fetch('/exams/final_quiz.json').then((res) => res.json()),
}

function buildStaticQuizPayload(data: StaticExamData, mode: QuizMode): QuizData {
  let runningIndex = 0
  const questions = data.category.flatMap((category) =>
    category.questions.map((question) => {
      runningIndex += 1
      return {
        ...question,
        category_name: category.category_name,
        q_no: question.q_no ?? runningIndex,
      }
    })
  )

  return {
    exam_info: {
      title: data.exam_info.title || (mode === 'midterm' ? '중간 평가' : '최종 평가'),
      mode,
      total_questions: questions.length || data.exam_info.total_questions,
    },
    questions,
  }
}

export default function LearningManagement() {
  const [activeTab, setActiveTab] = useState<'history' | 'practice' | 'materials'>('history')
  const [statusMessage, setStatusMessage] = useState<string | null>(null)
  const [loadingMode, setLoadingMode] = useState<QuizStartMode | null>(null)
  const [apiError, setApiError] = useState<string | null>(null)
  const navigate = useNavigate()
  const location = useLocation()

  const setQuiz = useQuizStore((state) => state.setQuiz)
  const quizHistory = useQuizStore((state) => state.history)

  useEffect(() => {
    const state = location.state as
      | { defaultTab?: 'history' | 'practice' | 'materials'; justSubmitted?: boolean }
      | null
    if (state?.defaultTab) {
      setActiveTab(state.defaultTab)
      if (state.justSubmitted && state.defaultTab === 'history') {
        setStatusMessage('퀴즈 결과가 저장되어 최근 학습 기록에 반영되었습니다.')
      }
      navigate('/learning', { replace: true })
    }
  }, [location.state, navigate])

  useEffect(() => {
    if (!statusMessage) return
    const timer = setTimeout(() => setStatusMessage(null), 5000)
    return () => clearTimeout(timer)
  }, [statusMessage])

const weakestCategory = useMemo(() => {
  const latest = quizHistory[0]
  if (latest) {
    const latestAccuracy = latest.total > 0 ? latest.score / latest.total : 0
    const generated = CATEGORY_ORDER.map((category) => ({
      category,
      accuracy: latestAccuracy,
      solved: latest.total,
    }))
    return generated.reduce((prev, curr) => (curr.accuracy < prev.accuracy ? curr : prev))
  }
  return mockProgress.reduce((prev, curr) => (curr.accuracy < prev.accuracy ? curr : prev))
}, [quizHistory])

  const radarData = useMemo(() => {
    const latest = quizHistory[0]
    if (latest) {
    const latestAccuracy = latest.total > 0 ? Math.max(0, Math.min(1, latest.score / latest.total)) : 0
    if (latest.categoryStats) {
      return CATEGORY_ORDER.map((category) => {
        const stats = latest.categoryStats?.[category]
        if (stats) {
          const accuracy = stats.total > 0 ? Math.max(0, Math.min(1, stats.correct / stats.total)) : 0
          return {
            name: category,
            score: Math.round(accuracy * 100),
            accuracy,
            solved: stats.total,
            correct: stats.correct,
          }
        }
        return {
          name: category,
          score: Math.round(latestAccuracy * 100),
          accuracy: latestAccuracy,
          solved: latest.total,
          correct: Math.round(latestAccuracy * latest.total),
        }
      })
    }
    return CATEGORY_ORDER.map((category) => ({
      name: category,
      score: Math.round(latestAccuracy * 100),
      accuracy: latestAccuracy,
      solved: latest.total,
      correct: Math.round(latestAccuracy * latest.total),
    }))
  }
  return mockProgress.map((item) => ({
    name: item.category,
    score: Math.round(item.accuracy * 100),
    accuracy: item.accuracy,
    solved: item.solved,
    correct: Math.round(item.accuracy * item.solved),
  }))
}, [quizHistory])

  const weakest =
    radarData.length > 0
      ? radarData.reduce<RadarDatum>(
          (prev, curr) => (curr.accuracy < prev.accuracy ? curr : prev),
          radarData[0]
        )
      : null

  const handleStartQuiz = async (mode: QuizStartMode, totalQuestions?: number) => {
    setApiError(null)
    setLoadingMode(mode)

    if (mode === 'midterm' || mode === 'final') {
      try {
        const loader = STATIC_EXAM_LOADERS[mode]
        const payload = await loader()
        const quizPayload = buildStaticQuizPayload(payload, mode)
        setQuiz(quizPayload)
        navigate('/learning/quiz-player')
      } catch (error) {
        setApiError(
          mode === 'midterm'
            ? '중간 평가를 불러오는 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.'
            : '최종 평가를 불러오는 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.'
        )
      } finally {
        setLoadingMode(null)
      }
      return
    }

    if (!totalQuestions) {
      setApiError('퀴즈 문항 수를 입력해주세요.')
      setLoadingMode(null)
      return
    }

    try {
      const payload = await quizAPI.generateQuiz({
        mode,
        total_questions: totalQuestions,
        profile: mode === 'custom' ? buildMockProfilePayload() : null,
      })
      setQuiz(payload)
      navigate('/learning/quiz-player')
    } catch (error: any) {
      const detail = error?.response?.data?.detail
      setApiError(
        typeof detail === 'string'
          ? detail
          : '퀴즈 세트를 불러오는 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.'
      )
    } finally {
      setLoadingMode(null)
    }
  }

    return (
    <div className="space-y-8">
      <header className="bg-white rounded-3xl shadow-lg border border-primary-100 p-8 flex flex-col gap-4">
        <div className="flex items-center gap-3 text-primary-600 font-semibold text-sm">
          <BookOpenIcon className="w-5 h-5" />
          학습 관리 · Quiz DB
        </div>
        <div>
          <h1 className="text-2xl md:text-3xl font-bold text-bank-900">학습 관리</h1>
          <p className="mt-2 text-bank-600 leading-relaxed">
            NCS에 기반한 금융 직무지식과 하경은행 실무지식을 학습하는 공간입니다.
          </p>
          {weakest && (
            <div className="mt-4 flex flex-wrap items-center gap-3 bg-primary-50/70 rounded-2xl px-4 py-3 text-primary-800 text-sm">
              <SparklesIcon className="w-5 h-5" />
              최근 데이터 기준 가장 취약한 영역은
              <span className="font-semibold">{weakest.name}</span>
              (정답률 {Math.round(weakest.accuracy * 100)}%)입니다.
              취약 세트를 생성하면 해당 영역 문항 비중을 높일 수 있어요.
            </div>
          )}
        </div>
      </header>

      <section className="bg-white rounded-3xl shadow-lg border border-primary-100 p-4">
        {statusMessage && (
          <div className="mb-4 rounded-2xl border border-primary-200 bg-primary-50/60 px-4 py-3 text-sm text-primary-700">
            {statusMessage}
          </div>
        )}
        <div className="flex gap-2">
          <TabButton
            label="내 학습"
            active={activeTab === 'history'}
            onClick={() => setActiveTab('history')}
          />
          <TabButton
            label="학습하기"
            active={activeTab === 'practice'}
            onClick={() => setActiveTab('practice')}
          />
          <TabButton
            label="학습자료"
            active={activeTab === 'materials'}
            onClick={() => setActiveTab('materials')}
          />
        </div>

        <div className="mt-6">
          {activeTab === 'history' && <MyLearning customHistory={quizHistory} radarData={radarData} />}
          {activeTab === 'practice' && (
            <Practice
              onStartQuiz={handleStartQuiz}
              loadingMode={loadingMode}
              apiError={apiError}
            />
          )}
          {activeTab === 'materials' && <LearningResources />}
        </div>
      </section>
    </div>
  )
}

function TabButton({
  label,
  active,
  onClick,
}: {
  label: string
  active: boolean
  onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      className={`flex-1 rounded-2xl py-3 text-sm font-semibold transition-all duration-200 ${
        active
          ? 'bg-primary-600 text-white shadow-md'
          : 'bg-primary-50 text-primary-500 hover:bg-primary-100 hover:text-primary-700'
      }`}
    >
      {label}
    </button>
  )
}

function MyLearning({
  customHistory,
  radarData,
}: {
  customHistory: QuizHistoryEntry[]
  radarData: RadarDatum[]
}) {
  const formatDate = (iso: string) => {
    const date = new Date(iso)
    if (Number.isNaN(date.getTime())) return iso
    return date.toISOString().slice(0, 10)
  }

  const dynamicEntries = customHistory.map((entry) => ({
    id: entry.id,
    date: formatDate(entry.date),
    type:
      entry.mode === 'custom'
        ? '맞춤형 세트'
        : entry.mode === 'midterm'
        ? '중간 평가'
        : entry.mode === 'final'
        ? '최종 평가'
        : '랜덤 세트',
    score: entry.score,
    total: entry.total,
    note: entry.note ?? `${entry.total}문항`,
  }))

  const combinedHistory = [...dynamicEntries, ...mockHistory]
  const averageScore = radarData.length
    ? Math.round(
        radarData.reduce((sum: number, item: RadarDatum) => sum + item.score, 0) /
          radarData.length
      )
    : 0

  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-2">
        <div className="rounded-2xl border border-primary-100 p-5 bg-gradient-to-br from-white to-primary-50/60 space-y-4">
          <div className="flex items-center gap-3 text-sm text-primary-500 font-semibold">
            <ChartBarSquareIcon className="w-5 h-5" />
            내 학습 평가
          </div>
          {radarData.length > 0 && (
            <>
              <div className="bg-white rounded-xl border border-primary-100 p-4 mb-6">
                <ResponsiveContainer width="100%" height={240}>
                  <RadarChart
                    data={radarData.map((entry) => ({
                      ...entry,
                      average: averageScore,
                    }))}
                  >
                    <PolarGrid stroke="#E2E8F0" strokeWidth={1} />
                    <PolarAngleAxis
                      dataKey="name"
                      tick={{ fill: '#475569', fontSize: 11, fontWeight: 600 }}
                    />
                    <PolarRadiusAxis
                      angle={90}
                      domain={[0, 100]}
                      tick={{ fill: '#94A3B8', fontSize: 10 }}
                      stroke="#E2E8F0"
                    />
                    <Radar
                      name="정답률"
                      dataKey="score"
                      stroke="#3B82F6"
                      fill="#3B82F6"
                      fillOpacity={0.45}
                      dot={{ r: 3, fill: '#3B82F6' }}
                      strokeWidth={2}
                    />
                    <Radar
                      name="평균"
                      dataKey="average"
                      stroke="#f97316"
                      fill="#f97316"
                      fillOpacity={0.15}
                      strokeWidth={2}
                      strokeDasharray="6 4"
                    />
                    <RadarTooltip formatter={(value: number, name: string) => [`${value}%`, name]} />
                  </RadarChart>
                </ResponsiveContainer>
              </div>
              <div className="grid gap-3 lg:grid-cols-2">
                {radarData.map((item, index) => (
                  <div key={item.name} className="bg-white rounded-xl border border-primary-100 p-3">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-semibold text-bank-800">{item.name}</span>
                      <span className="text-base font-bold text-bank-900">
                        {Math.round(item.accuracy * 100)}점
                      </span>
                    </div>
                    <div className="w-full bg-primary-50 rounded-full h-2.5 overflow-hidden">
                      <div
                        className="h-2.5 rounded-full transition-all duration-700 ease-out"
                        style={{
                          width: `${item.accuracy * 100}%`,
                          backgroundColor: getCategoryColor(item.name),
                        }}
                      />
                    </div>
                    {CHAPTER_NOTES[index] && (
                      <p className="text-xs text-bank-500 mt-1">{CHAPTER_NOTES[index]}</p>
                    )}
                  </div>
                ))}
              </div>
            </>
          )}
        </div>

        <div className="rounded-2xl border border-primary-100 p-5 space-y-4">
          <div className="flex items-center gap-3 text-sm text-primary-500 font-semibold">
            <ArrowPathIcon className="w-5 h-5" />
            최근 학습 기록
          </div>
          <div className="space-y-4">
            {combinedHistory.map((history) => (
              <div
                key={history.id}
                className="rounded-2xl border border-primary-50 p-4 bg-primary-50/40"
              >
                <div className="flex flex-wrap items-center gap-2 text-xs text-primary-500 font-semibold">
                  <ClockIcon className="w-4 h-4" />
                  {history.date}
                  <span className="px-2 py-0.5 bg-white rounded-full text-primary-600">
                    {history.type}
                  </span>
                </div>
                <div className="mt-2 flex items-end gap-2">
                  <span className="text-3xl font-bold text-bank-900">{history.score}점  </span>
                  <p className="text-xs text-bank-500">
                    {Math.round((history.score / 100) * history.total)} / {history.total}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

interface PracticeProps {
  onStartQuiz: (mode: QuizStartMode, totalQuestions?: number) => void
  loadingMode: QuizStartMode | null
  apiError: string | null
}

function Practice({ onStartQuiz, loadingMode, apiError }: PracticeProps) {
  const [questionCount, setQuestionCount] = useState(12)

  const handleQuestionCountChange = (value: string) => {
    const parsed = Number(value)
    if (Number.isNaN(parsed)) return
    const clamped = Math.max(1, Math.min(60, parsed))
    setQuestionCount(clamped)
  }

  return (
    <div className="space-y-6">
      <div className="grid gap-4 lg:grid-cols-2">
        {practiceModes.map((mode) => (
          <div
            key={mode.id}
            className="rounded-2xl border border-primary-100 p-5 bg-gradient-to-br from-white to-primary-50/50 flex flex-col gap-4"
          >
            <div className="flex items-center gap-3 text-primary-600 font-semibold text-sm">
              <ClipboardDocumentListIcon className="w-5 h-5" />
              {mode.title}
            </div>
            <p className="text-sm text-primary-500 font-medium">{mode.description}</p>
            {mode.id === 'custom' && (
              <label className="flex items-center gap-3 text-sm font-semibold text-primary-700">
                문항 수
                <input
                  type="number"
                  min={1}
                  max={60}
                  value={questionCount}
                  onChange={(e) => handleQuestionCountChange(e.target.value)}
                  className="w-20 rounded-xl border border-primary-200 px-3 py-2 text-bank-800 focus:outline-none focus:ring-2 focus:ring-primary-300"
                />
                <span className="text-xs text-primary-500">(1~60, 기본 12문항)</span>
              </label>
            )}
            <div className="flex flex-wrap gap-2">
              {mode.actions.map((action) => {
                const modeType = action.mode
                return (
                  <button
                    key={action.label}
                    className={`px-4 py-2 rounded-xl text-sm font-semibold transition-colors ${
                      action.variant === 'primary'
                        ? 'bg-primary-600 text-white shadow-md hover:bg-primary-700 disabled:opacity-60'
                        : action.variant === 'secondary'
                        ? 'bg-primary-100 text-primary-700 hover:bg-primary-200 disabled:opacity-60'
                        : 'text-primary-600 hover:bg-primary-100'
                    }`}
                    onClick={() =>
                      onStartQuiz(
                        modeType,
                        modeType === 'random' || modeType === 'custom' ? questionCount : undefined
                      )
                    }
                    disabled={loadingMode === modeType}
                  >
                    {loadingMode === modeType ? '로딩 중...' : action.label}
                  </button>
                )
              })}
            </div>
            {mode.id === 'custom' && apiError && (
              <p className="text-sm text-red-500 bg-red-50 rounded-2xl px-4 py-2">{apiError}</p>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

function buildMockProfilePayload() {
  const baseScores = mockProgress.reduce<Record<string, number>>((acc, curr) => {
    acc[curr.category] = Math.round(curr.accuracy * 100)
    return acc
  }, {})
  return {
    wrong_question_ids: [],
    recent_category_scores: baseScores,
    cumulative_category_scores: baseScores,
  }
}

function LearningResources() {
  return (
    <div className="rounded-3xl border border-primary-100 bg-white shadow-lg">
      <Documents />
    </div>
  )
}

function getCategoryColor(category: string) {
  return CATEGORY_COLOR_MAP[category] ?? '#4f46e5'}
