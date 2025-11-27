import { useEffect, useMemo, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import {
  BookOpenIcon,
  ClipboardDocumentListIcon,
  SparklesIcon,
} from '@heroicons/react/24/outline'

import Documents from './Documents'
import { quizAPI, adminAPI, dashboardAPI, scheduleAPI } from '../utils/api'
import { QuizData, QuizMode, QuizQuestion, useQuizStore } from '../store/quizStore'
import { useAuthStore } from '../store/authStore'
import { toKST } from '../utils/datetime'

const CATEGORY_ORDER = [
  '금융영업',
  '상품개발 및 운용',
  '신용분석 및 리스크관리',
  '외환',
  '은행지식 및 관련법률',
  '하경은행',
]

const practiceModes = [
  {
    id: 'midfinal',
    title: '중간/최종 평가',
    description:
      '중간 평가 및 최종 평가 퀴즈를 풉니다. 한번만 응시할 수 있으며, 중도 포기시 횟수가 차감됩니다. 평가는 지정된 일정에 맞춰 수행바랍니다.',
    actions: [
      { label: '중간 평가', variant: 'primary', mode: 'midterm' as QuizMode },
      { label: '최종 평가', variant: 'primary', mode: 'final' as QuizMode },
    ],
  },
  {
    id: 'custom',
    title: '연습하기',
    description:
      '챕터별 동일하게 분포된 랜덤 퀴즈 세트를 생성하거나, 나의 취약 챕터 영역을 반영한 맞춤형 퀴즈 세트를 생성합니다. 맞춤형은 총 10번 응시할 수 있으며, 중도 포기시 횟수가 차감됩니다.',
    actions: [
      { label: '랜덤 세트', variant: 'primary', mode: 'random' as QuizMode },
      { label: '맞춤형 세트', variant: 'primary', mode: 'custom' as QuizMode },
    ],
  },
]

type QuizStartMode = QuizMode
type AssessmentSchedule = { midterm?: string; final?: string }

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
  const [activeTab, setActiveTab] = useState<'practice' | 'materials'>('practice')
  const [loadingMode, setLoadingMode] = useState<QuizStartMode | null>(null)
  const [apiError, setApiError] = useState<string | null>(null)
  const [remainingAttempts, setRemainingAttempts] = useState<Record<string, number> | null>(null)
  const navigate = useNavigate()
  const location = useLocation()

  const currentUser = useAuthStore((state) => state.user)
  const setQuiz = useQuizStore((state) => state.setQuiz)
  const quizHistory = useQuizStore((state) => state.history)
  const setHistory = useQuizStore((state) => state.setHistory)
  const [dashboardData, setDashboardData] = useState<any>(null)
  const [assessmentSchedule, setAssessmentSchedule] = useState<AssessmentSchedule>({})

  const userHistory = useMemo(() => {
    if (!currentUser) return []
    return quizHistory.filter((entry) => entry.userId === currentUser.id)
  }, [currentUser, quizHistory])

  // 대시보드 데이터 가져오기
  useEffect(() => {
    if (currentUser) {
      dashboardAPI.getMenteeDashboard()
        .then((data) => {
          setDashboardData(data)
        })
        .catch((error) => {
          console.error('대시보드 데이터 가져오기 실패:', error)
        })
    }
  }, [currentUser])

  useEffect(() => {
    const state = location.state as
      | { defaultTab?: 'practice' | 'materials'; justSubmitted?: boolean }
      | null
    if (state?.defaultTab) {
      setActiveTab(state.defaultTab)
      navigate('/learning', { replace: true })
    }
  }, [location.state, navigate])

  useEffect(() => {
    adminAPI.getQuizRemaining()
      .then((data: any) => {
        setRemainingAttempts(data?.remaining || null)
      })
      .catch(() => setRemainingAttempts(null))
  }, [])

  // 서버 저장된 퀴즈 이력(QuizGenerationLog)로 로컬 히스토리 덮어쓰기
  useEffect(() => {
    if (!currentUser) return
    quizAPI
      .getMyHistory(50)
      .then((items: any[]) => {
        const entries = items.map((item: any) => {
          const categoryStats: Record<string, { correct: number; total: number }> = {}
          const answers = item.answers || {}
          const questions = item.questions || []
          const rawToNormalized: Record<string, number> = {}
          const normalizedQuestions = questions.map((q: any, idx: number) => {
            const rawId = q.q_id ?? q.question_id ?? q.qid ?? q.id ?? idx + 1
            const numericId = Number(String(rawId).replace(/\D+/g, ''))
            const qId = Number.isFinite(numericId) && numericId > 0 ? numericId : idx + 1
            rawToNormalized[String(rawId)] = qId
            return {
              q_no: Number.isFinite(Number(q.q_no)) ? Number(q.q_no) : idx + 1,
              q_id: qId,
              question: q.question,
              category_name: q.category_name ?? q.category ?? '기타',
              ['보기 1']: q['보기 1'] ?? q.choice1 ?? '',
              ['보기 2']: q['보기 2'] ?? q.choice2 ?? '',
              ['보기 3']: q['보기 3'] ?? q.choice3 ?? '',
              ['보기 4']: q['보기 4'] ?? q.choice4 ?? '',
              answer: q.answer,
              comment: q.comment ?? '',
              source_files: q.source_files ?? [],
            }
          })

          const parsedAnswers: Record<number, string> = {}
          Object.entries(answers).forEach(([k, v]) => {
            const normalizedKey = rawToNormalized[k]
            if (normalizedKey) {
              parsedAnswers[normalizedKey] = v as string
              return
            }
            const keyNum = Number(String(k).replace(/\D+/g, ''))
            if (Number.isFinite(keyNum) && keyNum > 0) {
              parsedAnswers[keyNum] = v as string
            }
          })

          if ((item as any).category_stats) {
            Object.assign(categoryStats, (item as any).category_stats)
          }
          const normalize = (val?: string) => {
            if (!val) return ''
            const digits = val.replace(/\D+/g, '')
            return digits || val.replace(/\s+/g, '').toLowerCase()
          }
          questions.forEach((q: any) => {
            const cat = q?.category_name || q?.category || '기타'
            const qid = q?.q_id ?? q?.question_id ?? q?.qid
            if (qid === undefined || qid === null) return
            const key = String(qid)
            if (!categoryStats[cat]) categoryStats[cat] = { correct: 0, total: 0 }
            categoryStats[cat].total += 1
            const userAnswer = answers[key] ?? answers[qid]
            if (userAnswer && normalize(userAnswer) === normalize(q?.answer)) {
              categoryStats[cat].correct += 1
            }
          })

          const quizData =
            normalizedQuestions.length > 0
              ? {
                  exam_info: {
                    title:
                      item.mode === 'midterm'
                        ? '중간 평가'
                        : item.mode === 'final'
                        ? '최종 평가'
                        : item.mode === 'pre'
                        ? '초기 평가'
                        : '퀴즈',
                    mode: item.mode as QuizMode,
                    total_questions: item.total_questions ?? normalizedQuestions.length,
                  },
                  questions: normalizedQuestions,
                }
              : undefined

          return {
            id: `log-${item.id}`,
            userId: currentUser.id,
            date: item.created_at,
            mode: (item.mode as QuizMode) || 'random',
            score: Math.round(item.score ?? 0),
            total: item.total_questions ?? 0,
            note: item.mode === 'pre' ? '초기' : item.mode?.toUpperCase?.() || 'QUIZ',
            categoryStats,
            quizData,
            answers: parsedAnswers,
          }
        })
        setHistory(entries)
      })
      .catch(() => setHistory([]))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentUser?.id])

  const computeCategoryScores = useMemo(() => {
    const buildScores = (entries: typeof userHistory) => {
      const totals = CATEGORY_ORDER.reduce<Record<string, { correct: number; total: number }>>(
        (acc, cat) => {
          acc[cat] = { correct: 0, total: 0 }
          return acc
        },
        {}
      )

      entries.forEach((entry) => {
        if (entry.categoryStats) {
          CATEGORY_ORDER.forEach((cat) => {
            const stats = entry.categoryStats?.[cat]
            if (stats) {
              totals[cat].correct += stats.correct || 0
              totals[cat].total += stats.total || 0
            }
          })
        } else {
          const accuracy = entry.score ? Math.max(0, Math.min(1, entry.score / 100)) : 0
          const evenTotal = entry.total || 0
          const perCat = CATEGORY_ORDER.length > 0 ? evenTotal / CATEGORY_ORDER.length : 0
          CATEGORY_ORDER.forEach((cat) => {
            totals[cat].total += perCat
            totals[cat].correct += perCat * accuracy
          })
        }
      })

      return CATEGORY_ORDER.map((cat) => {
        const { correct, total } = totals[cat]
        const accuracy = total > 0 ? Math.max(0, Math.min(1, correct / total)) : 0
        return { category: cat, score: Math.round(accuracy * 100) }
      })
    }

    return {
      recent: buildScores(userHistory.slice(0, 1)),
      cumulative: buildScores(userHistory),
    }
  }, [userHistory])

  const weaknessSummary = useMemo(() => {
    const { recent, cumulative } = computeCategoryScores
    if (!recent.length || !cumulative.length) return null

    const spread = (() => {
      const scores = cumulative.map((item) => item.score)
      if (!scores.length) return null
      return Math.max(...scores) - Math.min(...scores)
    })()

    if (spread !== null && spread <= 8) {
      return {
        type: 'balanced' as const,
        message: '취약 영역이 없습니다. 랜덤 세트로 균형잡힌 학습을 권장드려요.',
      }
    }

    const findWeakCategories = (items: { category: string; score: number }[]) => {
      if (!items.length) return []
      const minScore = Math.min(...items.map((item) => item.score))
      return items.filter((item) => item.score === minScore).map((item) => item.category)
    }

    return {
      type: 'weak' as const,
      recentWeak: findWeakCategories(recent),
      cumulativeWeak: findWeakCategories(cumulative),
    }
  }, [computeCategoryScores])

  const handleStartQuiz = async (mode: QuizStartMode, totalQuestions?: number) => {
    setApiError(null)
    setLoadingMode(mode)

    if (mode === 'midterm' || mode === 'final') {
      try {
        const loader = STATIC_EXAM_LOADERS[mode]
        const payload = await loader()
        const total = payload.category.reduce((acc, cat) => acc + (cat.questions?.length || 0), 0)
        const reserve = await quizAPI.reserveStaticQuiz({ mode, total_questions: total })
        const quizPayload = buildStaticQuizPayload(payload, mode)
        if (reserve?.generation_id) {
          quizPayload.generation_id = reserve.generation_id
        }
        // 남은 횟수 갱신
        setRemainingAttempts(reserve?.remaining || remainingAttempts)
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
      // 남은 횟수 갱신
      adminAPI.getQuizRemaining()
        .then((data: any) => setRemainingAttempts(data?.remaining || null))
        .catch(() => {})
    }
  }

  const toKstDate = (value?: string) => {
    if (!value) return null
    const parsed = new Date(value)
    if (Number.isNaN(parsed.getTime())) return null
    return toKST(parsed)
  }

  const formatAssessmentDate = (value?: string) => {
    if (!value) return '미정'
    const date = toKstDate(value)
    if (!date) return '미정'
    const yy = String(date.getFullYear()).slice(-2)
    const mm = String(date.getMonth() + 1).padStart(2, '0')
    const dd = String(date.getDate()).padStart(2, '0')
    return `${yy}${mm}${dd}`
  }

  const isSameDate = (value?: string) => {
    const date = toKstDate(value)
    if (!date) return false
    const today = toKST(new Date())
    return date.getFullYear() === today.getFullYear() &&
      date.getMonth() === today.getMonth() &&
      date.getDate() === today.getDate()
  }

  const assessmentInfo = useMemo(
    () => ({
      midtermDateLabel: formatAssessmentDate(assessmentSchedule.midterm),
      finalDateLabel: formatAssessmentDate(assessmentSchedule.final),
      isMidtermToday: isSameDate(assessmentSchedule.midterm),
      isFinalToday: isSameDate(assessmentSchedule.final),
    }),
    [assessmentSchedule]
  )

  const assessmentDescription = useMemo(
    () =>
      [
        '중간 평가 및 최종 평가 퀴즈를 풉니다. 한번만 응시할 수 있으며, 중도 포기시 횟수가 차감됩니다. 평가는 지정된 일정에 맞춰 수행바랍니다.',
        `중간 평가 날짜: ${assessmentInfo.midtermDateLabel}`,
        `최종 평가 날짜: ${assessmentInfo.finalDateLabel}`,
      ].join('\n'),
    [assessmentInfo.finalDateLabel, assessmentInfo.midtermDateLabel]
  )

  useEffect(() => {
    scheduleAPI.getSchedules()
      .then((data: any[]) => {
        if (!Array.isArray(data)) return
        const companySchedules = data.filter((item) => item?.is_company_schedule)
        const normalize = (title: string) => (title || '').replace(/\s+/g, '').toLowerCase()
        const findByKeywords = (keywords: string[]) =>
          companySchedules.find((item) => {
            const normalized = normalize(item?.title || '')
            return keywords.some((key) => normalized.includes(normalize(key)))
          })
        const midterm = findByKeywords(['중간 평가', 'midterm'])
        const final = findByKeywords(['최종 평가', 'final'])
        setAssessmentSchedule({
          midterm: midterm?.start_time,
          final: final?.start_time,
        })
      })
      .catch(() => {
        setAssessmentSchedule({})
      })
  }, [])

  return (
    <div className="space-y-8">
      <header className="bg-white rounded-3xl shadow-lg border border-primary-100 p-8 flex flex-col gap-4">
        <div className="flex items-center gap-3 text-primary-600 font-semibold text-sm">
          <BookOpenIcon className="w-5 h-5" />
          학습 관리
        </div>
        <div>
          <h1 className="text-2xl md:text-3xl font-bold text-bank-900">학습 관리</h1>
          <p className="mt-2 text-bank-600 leading-relaxed">
            NCS에 기반한 금융 직무지식과 하경은행 실무지식을 학습하는 공간입니다.
          </p>
          {weaknessSummary && (
            <div className="mt-4 flex flex-wrap items-center gap-3 bg-primary-50/70 rounded-2xl px-4 py-3 text-primary-800 text-sm">
              <SparklesIcon className="w-5 h-5" />
              {weaknessSummary.type === 'balanced' ? (
                <span className="font-medium">{weaknessSummary.message}</span>
              ) : (
                <span className="font-medium">
                  나의 최근 취약한 영역은{' '}
                  <span className="font-semibold underline decoration-primary-500">
                    {weaknessSummary.recentWeak.join(', ')}
                  </span>
                  이고, 누적으로 취약한 영역은{' '}
                  <span className="font-semibold underline decoration-primary-500">
                    {weaknessSummary.cumulativeWeak.join(', ')}
                  </span>
                  입니다. 맞춤형 세트를 생성하면 해당 영역 문항 비중을 높여 학습할 수 있어요.
                </span>
              )}
              {remainingAttempts && (
                <p className="text-primary-700">
                  (맞춤형 남은 횟수: {remainingAttempts.custom ?? 0}회)
                </p>
              )}
            </div>
          )}
        </div>
      </header>

      <section className="bg-white rounded-3xl shadow-lg border border-primary-100 p-4">
        <div className="flex gap-2">
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
          {activeTab === 'practice' && (
            <Practice
              onStartQuiz={handleStartQuiz}
              loadingMode={loadingMode}
              apiError={apiError}
              assessmentInfo={assessmentInfo}
              assessmentDescription={assessmentDescription}
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

interface PracticeProps {
  onStartQuiz: (mode: QuizStartMode, totalQuestions?: number) => void
  loadingMode: QuizStartMode | null
  apiError: string | null
  assessmentInfo: AssessmentInfoState
  assessmentDescription: string
}

interface AssessmentInfoState {
  midtermDateLabel: string
  finalDateLabel: string
  isMidtermToday: boolean
  isFinalToday: boolean
}

function Practice({
  onStartQuiz,
  loadingMode,
  apiError,
  assessmentInfo,
  assessmentDescription,
}: PracticeProps) {
  const [questionCount, setQuestionCount] = useState(12)
  const [attempts, setAttempts] = useState<Record<string, number> | null>(null)

  useEffect(() => {
    adminAPI.getQuizRemaining()
      .then((data: any) => setAttempts(data?.remaining || null))
      .catch(() => setAttempts(null))
  }, [])

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
            <p className="text-sm text-primary-500 font-medium whitespace-pre-line">
              {mode.id === 'midfinal' ? assessmentDescription : mode.description}
            </p>
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
                const disabled =
                  loadingMode === modeType ||
                  (modeType === 'midterm' && !!attempts && attempts.midterm === 0) ||
                  (modeType === 'midterm' && !assessmentInfo.isMidtermToday) ||
                  (modeType === 'final' && !assessmentInfo.isFinalToday) ||
                  (modeType === 'final' && !!attempts && attempts.final === 0)
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
                    disabled={disabled}
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
  const baseScores = CATEGORY_ORDER.reduce<Record<string, number>>((acc, cat) => {
    acc[cat] = 0
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
