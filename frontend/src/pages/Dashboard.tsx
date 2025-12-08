/**
 * 대시보드 페이지
 * 멘티/멘토별 맞춤 대시보드
 */
import { useState, useEffect, useRef, useCallback, useMemo, Dispatch, SetStateAction } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'
import { useQuizStore, QuizHistoryEntry, QuizMode } from '../store/quizStore'
import { dashboardAPI, adminAPI, quizAPI } from '../utils/api'
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
  ChartBarSquareIcon,
  ClockIcon,
  LightBulbIcon,
  StarIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  PlusIcon,
  UserGroupIcon,
  CheckCircleIcon,
  XCircleIcon,
  InformationCircleIcon,
  XMarkIcon,
  CalendarIcon,
  ExclamationTriangleIcon,
  ArrowUpIcon,
  ArrowTrendingUpIcon,
  PaperClipIcon,
  PlayIcon,
  CpuChipIcon,
  ArrowPathIcon,
  SpeakerWaveIcon
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
  Cell,
  CartesianGrid,
  YAxis,
  Legend
} from 'recharts'
import { motion } from 'framer-motion'
import api from '../utils/api'
import { toKST, formatKSTDateWithDay, formatKSTTime, formatKSTDateTime, formatKSTDate } from '../utils/datetime'
import LangGraphMermaidView from '../components/LangGraphMermaidView'
import NodeDetailPanel from '../components/NodeDetailPanel'

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

// TRAINING_LEARNING_SECTIONS는 CATEGORY_ORDER와 동일한 값 사용
const TRAINING_LEARNING_SECTIONS = CATEGORY_ORDER

type RadarDatum = { name: string; score: number; accuracy: number; solved: number; correct: number }
type ModeFilter = 'all' | 'assessment' | 'practice'
type AggregationMode = 'single' | 'cumulative'
type PercentileInfo = {
  upper_percent: number | null
  lower_percent: number | null
  total_samples: number
  percentile: number | null
} | null
type DisplayHistoryEntry = {
  id: string
  displayDate: string
  orderLabel: string
  mode: QuizMode
  type: string
  score: number
  total: number
  note?: string
}

const CATEGORY_COLOR_MAP: Record<string, string> = {
  '금융영업': '#2563eb',
  '상품개발 및 운용': '#ea580c',
  '신용분석 및 리스크관리': '#22c55e',
  '외환': '#0ea5e9',
  '은행지식 및 관련법률': '#a855f7',
  '하경은행': '#f97316',
}

function getCategoryColor(category: string) {
  return CATEGORY_COLOR_MAP[category] ?? '#4f46e5'
}

const MODE_LABEL: Record<QuizMode | 'custom', string> = {
  random: '랜덤 세트',
  custom: '맞춤형 세트',
  pre: '초기 평가',
  midterm: '중간 평가',
  final: '최종 평가',
}

function formatHistoryDate(iso: string) {
  try {
    return formatKSTDate(iso)
  } catch {
    const date = new Date(iso)
    if (Number.isNaN(date.getTime())) return iso
    return date.toISOString().slice(0, 10)
  }
}

function mapHistoryEntries(entries: QuizHistoryEntry[]): DisplayHistoryEntry[] {
  return entries.map((entry, idx) => ({
    id: entry.id,
    mode: entry.mode,
    displayDate: formatHistoryDate(entry.date),
    orderLabel: `${entry.attempt ?? entries.length - idx}회차`,
    type: MODE_LABEL[entry.mode] ?? '랜덤 세트',
    score: entry.score,
    total: entry.total,
    note: entry.note ?? `${entry.total}문항`,
  }))
}

function computeRadarFromEntries(entries: QuizHistoryEntry[], fallback: RadarDatum[]) {
    if (!entries.length) return fallback

    const agg: Record<string, { correct: number; total: number }> = {}
    CATEGORY_ORDER.forEach((cat) => {
      agg[cat] = { correct: 0, total: 0 }
    })

    entries.forEach((entry) => {
      if (entry.categoryStats) {
        CATEGORY_ORDER.forEach((cat) => {
          const stats = entry.categoryStats?.[cat]
          if (stats) {
            agg[cat].correct += stats.correct
            agg[cat].total += stats.total
          }
        })
      } else {
        const accuracy = entry.score > 0 ? entry.score / 100 : 0
        const evenTotal = entry.total / CATEGORY_ORDER.length
        CATEGORY_ORDER.forEach((cat) => {
          agg[cat].total += evenTotal
          agg[cat].correct += evenTotal * accuracy
        })
      }
    })

    return CATEGORY_ORDER.map((cat) => {
      const { correct, total } = agg[cat]
      const accuracy = total > 0 ? Math.max(0, Math.min(1, correct / total)) : 0
      return {
        name: cat,
        score: Math.round(accuracy * 100),
        accuracy,
        solved: total,
        correct,
      }
    })
  }

function pickEffectiveRadarData(
  aggregation: AggregationMode,
  filtered: QuizHistoryEntry[],
  selected: QuizHistoryEntry | undefined,
  fallback: RadarDatum[]
) {
  const sourceEntries = aggregation === 'cumulative' ? filtered : selected ? [selected] : []
  return computeRadarFromEntries(sourceEntries, fallback)
}

function MyLearning({
  customHistory,
  radarData: baseRadarData,
  globalAverageData,
  percentileInfo,
  setPercentileInfo,
}: {
  customHistory: QuizHistoryEntry[]
  radarData: RadarDatum[]
  globalAverageData: RadarDatum[] | null
  percentileInfo?: PercentileInfo
  setPercentileInfo: Dispatch<SetStateAction<PercentileInfo>>
}) {
  const navigate = useNavigate()
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [modeFilter, setModeFilter] = useState<ModeFilter>('all')
  const [aggregation, setAggregation] = useState<AggregationMode>('single')
  const [trendCategory, setTrendCategory] = useState<string>('total')

  const filteredHistory = useMemo(() => {
    return customHistory.filter((entry) => {
      if (modeFilter === 'assessment') {
        return entry.mode === 'pre' || entry.mode === 'midterm' || entry.mode === 'final'
      }
      if (modeFilter === 'practice') {
        return entry.mode === 'random' || entry.mode === 'custom'
      }
      return true
    })
  }, [customHistory, modeFilter])

  useEffect(() => {
    if (aggregation === 'cumulative') {
      setSelectedId(null)
      return
    }
    if (!filteredHistory.length) {
      setSelectedId(null)
      return
    }
    if (selectedId && filteredHistory.some((entry) => entry.id === selectedId)) return
    setSelectedId(filteredHistory[0].id)
  }, [aggregation, filteredHistory, selectedId])

  const dynamicEntries = useMemo(() => mapHistoryEntries(filteredHistory), [filteredHistory])

  const selectedEntry = filteredHistory.find((entry) => entry.id === selectedId)

  const effectiveRadarData = useMemo(
    () => pickEffectiveRadarData(aggregation, filteredHistory, selectedEntry, baseRadarData),
    [aggregation, baseRadarData, filteredHistory, selectedEntry]
  )

  const fallbackGlobalAverage = useMemo(() => {
    return []
  }, [])

  const totalRadarCounts = useMemo(() => {
    // 단일 모드에서는 현재 선택된 기록의 원본 총문항/정답을 사용한다.
    if (aggregation === 'single' && selectedEntry) {
      if (selectedEntry.categoryStats) {
        const sum = Object.values(selectedEntry.categoryStats).reduce(
          (acc, stat) => {
            acc.correct += stat.correct || 0
            acc.solved += stat.total || 0
            return acc
          },
          { correct: 0, solved: 0 }
        )
        return sum
      }
      const solved = selectedEntry.total || 0
      const accuracy = selectedEntry.total > 0 ? Math.max(0, Math.min(1, selectedEntry.score / selectedEntry.total)) : 0
      const correct = Math.round(solved * accuracy)
      return { correct, solved }
    }

    // 누계 모드에서는 레이더 데이터 합산
    return effectiveRadarData.reduce(
      (acc, item) => {
        acc.correct += item.correct ?? 0
        acc.solved += item.solved ?? 0
        return acc
      },
      { correct: 0, solved: 0 }
    )
  }, [aggregation, effectiveRadarData, selectedEntry])

  const averageScore = useMemo(() => {
    const { correct, solved } = totalRadarCounts
    if (!solved) return 0
    return Math.round((correct / solved) * 100)
  }, [totalRadarCounts])

  // 선택/집계된 점수 기준으로 퍼센타일 갱신
  useEffect(() => {
    const targetScore =
      aggregation === 'single'
        ? selectedEntry?.score
        : aggregation === 'cumulative'
        ? averageScore
        : undefined

    if (targetScore === undefined || targetScore === null || Number.isNaN(targetScore)) {
      setPercentileInfo(null)
      return
    }

    quizAPI
      .getScorePercentile(targetScore)
      .then((info) => setPercentileInfo(info))
      .catch(() => setPercentileInfo(null))
  }, [aggregation, selectedEntry?.score, averageScore])

  const effectiveGlobalAverage = useMemo(
    () =>
      globalAverageData && globalAverageData.length === CATEGORY_ORDER.length
        ? globalAverageData
        : fallbackGlobalAverage,
    [fallbackGlobalAverage, globalAverageData]
  )

  const modeCounts = useMemo(() => {
    const assessment = customHistory.filter(
      (entry) => entry.mode === 'pre' || entry.mode === 'midterm' || entry.mode === 'final'
    ).length
    const practice = customHistory.filter(
      (entry) => entry.mode === 'random' || entry.mode === 'custom'
    ).length
    return {
      total: customHistory.length,
      assessment,
      practice,
    }
  }, [customHistory])

  const trendOptions = useMemo(
    () => [
      { value: 'total', label: '총점' },
      ...CATEGORY_ORDER.map((category) => ({ value: category, label: category })),
    ],
    []
  )

  const trendChartData = useMemo(() => {
    type TrendPoint = { id: string; label: string; score: number }
    const sortedHistory = [...filteredHistory].sort((a, b) => {
      const aTime = Date.parse(a.date)
      const bTime = Date.parse(b.date)
      if (Number.isNaN(aTime) && Number.isNaN(bTime)) return 0
      if (Number.isNaN(aTime)) return -1
      if (Number.isNaN(bTime)) return 1
      return aTime - bTime
    })

    return sortedHistory
      .map<TrendPoint | null>((entry) => {
        let score: number | null = null

        if (trendCategory === 'total') {
          score = typeof entry.score === 'number' ? entry.score : null
        } else {
          const stats = entry.categoryStats?.[trendCategory]
          if (stats && stats.total > 0) {
            score = Math.round((stats.correct / stats.total) * 100)
          }
        }

        if (score == null) return null

        return {
          id: entry.id,
          label: formatHistoryDate(entry.date, entry.mode),
          score,
        }
      })
      .filter((item): item is TrendPoint => item !== null)
  }, [filteredHistory, trendCategory])

  const trendLineColor = useMemo(
    () => (trendCategory === 'total' ? '#2563eb' : getCategoryColor(trendCategory)),
    [trendCategory]
  )

  const trendLabel = trendCategory === 'total' ? '총점' : trendCategory

  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-2">
        <div className="rounded-2xl border border-primary-100 p-5 bg-gradient-to-br from-white to-primary-50/60 space-y-4">
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-center gap-3 text-sm text-primary-500 font-semibold">
              <ChartBarSquareIcon className="w-5 h-5" />
              내 학습 평가
            </div>
            <div className="flex items-center gap-1">
              <button
                type="button"
                onClick={() => setAggregation('single')}
                className={`px-3 py-1 rounded-lg text-xs font-semibold transition-colors ${
                  aggregation === 'single'
                    ? 'bg-primary-600 text-white'
                    : 'bg-primary-50 text-primary-600 hover:bg-primary-100'
                }`}
              >
                단일
              </button>
              <button
                type="button"
                onClick={() => setAggregation('cumulative')}
                className={`px-3 py-1 rounded-lg text-xs font-semibold transition-colors ${
                  aggregation === 'cumulative'
                    ? 'bg-primary-600 text-white'
                    : 'bg-primary-50 text-primary-600 hover:bg-primary-100'
                }`}
              >
                누계
              </button>
        </div>
      </div>
      {effectiveRadarData.length > 0 && (
        <>
          <div className="bg-white rounded-xl border border-primary-100 p-5 mb-6 space-y-4">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <p className="text-4xl font-extrabold text-bank-900 leading-tight">{averageScore}점</p>
                <div className="px-3 py-1.5 inline-flex rounded-full bg-primary-50 text-primary-700 text-sm font-semibold">
                  {percentileInfo?.percentile != null
                    ? percentileInfo.percentile >= 50
                      ? `상위 ${percentileInfo.percentile}%`
                      : `하위 ${percentileInfo.percentile}%`
                    : '퍼센타일 정보를 불러오는 중...'}
                </div>
              </div>
              <p className="text-sm font-semibold text-bank-600">
                {totalRadarCounts.correct} / {totalRadarCounts.solved}
              </p>
            </div>
          </div>
          <div className="bg-white rounded-xl border border-primary-100 p-4 mb-6 relative">
            <ResponsiveContainer width="100%" height={240}>
              <RadarChart
                data={effectiveRadarData.map((entry) => {
                  const global = effectiveGlobalAverage.find((g) => g.name === entry.name)
                      return {
                        ...entry,
                        average: global?.score ?? 0,
                      }
                    })}
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
                      name="점수"
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
                    <Tooltip formatter={(value: number, name: string) => [`${value}`, name]} />
                  </RadarChart>
                </ResponsiveContainer>
              </div>
              <div className="grid gap-3 lg:grid-cols-2">
                {effectiveRadarData.map((item, index) => (
                  <div key={item.name} className="bg-white rounded-xl border border-primary-100 p-3">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-semibold text-bank-800">{item.name}</span>
                      <span className="text-sm font-semibold text-bank-700">
                        {item.correct} / {item.solved}
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
                    {CATEGORY_ORDER[index] && (
                      <p className="text-xs text-bank-500 mt-1">{CHAPTER_NOTES[index]}</p>
                    )}
                  </div>
                ))}
              </div>
            </>
          )}
        </div>

        <div className="rounded-2xl border border-primary-100 p-5 space-y-4">
          <div className="flex flex-wrap items-center gap-3 text-sm text-primary-500 font-semibold">
            <ArrowPathIcon className="w-5 h-5" />
            학습 기록
            <select
              value={modeFilter}
              onChange={(e) => setModeFilter(e.target.value as 'all' | 'assessment' | 'practice')}
              className="rounded-lg border border-primary-200 px-2 py-1 text-bank-700 text-xs focus:outline-none focus:ring-2 focus:ring-primary-200"
            >
              <option value="all">전체</option>
              <option value="assessment">평가 (초기/중간/최종)</option>
              <option value="practice">연습 (랜덤/맞춤)</option>
            </select>
          </div>

          <div className="space-y-3 max-h-[30rem] overflow-y-auto pr-1">
            {dynamicEntries.length === 0 && (
              <p className="text-sm text-bank-500 px-2">조건에 맞는 학습 기록이 없습니다.</p>
            )}
            {dynamicEntries.map((history) => {
              const isActive = aggregation === 'single' && history.id === selectedId
              return (
                <button
                  key={history.id}
                  type="button"
                  onClick={() => {
                    if (aggregation === 'cumulative') return
                    setSelectedId(history.id)
                  }}
                  className={`w-full text-left rounded-2xl border p-4 transition-colors ${
                    isActive
                      ? 'border-primary-300 bg-primary-50'
                      : 'border-primary-50 bg-primary-50/40 hover:border-primary-200'
                  }`}
                  >
                  <div className="flex flex-wrap items-center gap-2 text-xs text-primary-500 font-semibold">
                    <ClockIcon className="w-4 h-4" />
                    <span>{history.orderLabel}</span>
                    <span>{history.displayDate}</span>
                    <span className="px-2 py-0.5 bg-white rounded-full text-primary-600">
                      {history.mode === 'pre' ? '초기 평가' : history.type}
                    </span>
                  </div>
                  <div className="mt-2 flex items-end justify-between gap-3">
                    <div className="flex items-end gap-2">
                      <span className="text-3xl font-bold text-bank-900">{history.score}점 </span>
                      <p className="text-xs text-bank-500">
                        {Math.round((history.score / 100) * history.total)} / {history.total}
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation()
                        const entry = filteredHistory.find((h) => h.id === history.id)
                        if (!entry?.quizData) {
                          window.alert('저장된 상세 문항 정보가 없어 결과를 조회할 수 없습니다.')
                          return
                        }
                        navigate('/learning/quiz-player', { state: { reviewEntryId: history.id } })
                      }}
                      className="px-3 py-1.5 rounded-lg border border-primary-200 text-primary-600 text-xs font-semibold hover:bg-primary-50"
                    >
                      결과 보기
                    </button>
                  </div>
                </button>
              )
            })}
          </div>
        </div>
      </div>

      <div className="rounded-2xl border border-primary-100 bg-white p-5 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3 text-sm text-primary-500 font-semibold">
            <ArrowTrendingUpIcon className="w-5 h-5" />
            <span>학습 기록 추이</span>
            <div className="flex items-center gap-2 text-[11px] text-bank-600 bg-primary-50 px-3 py-1 rounded-full">
              <span>전체 {modeCounts.total}회</span>
              <span className="text-primary-600">평가 {modeCounts.assessment}회</span>
              <span className="text-emerald-600">연습 {modeCounts.practice}회</span>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <select
              value={modeFilter}
              onChange={(e) => setModeFilter(e.target.value as ModeFilter)}
              className="rounded-lg border border-primary-200 px-3 py-2 text-bank-700 text-xs focus:outline-none focus:ring-2 focus:ring-primary-200"
            >
              <option value="all">전체</option>
              <option value="assessment">평가 (초기/중간/최종)</option>
              <option value="practice">연습 (랜덤/맞춤)</option>
            </select>
            <select
              value={trendCategory}
              onChange={(e) => setTrendCategory(e.target.value)}
              className="rounded-lg border border-primary-200 px-3 py-2 text-bank-700 text-xs focus:outline-none focus:ring-2 focus:ring-primary-200"
            >
              {trendOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        {trendChartData.length > 0 ? (
          <ResponsiveContainer width="100%" height={320}>
            <LineChart
              data={trendChartData}
              margin={{ top: 10, right: 20, bottom: 10, left: 0 }}
            >
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="label" tick={{ fontSize: 11 }} minTickGap={12} />
              <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} />
              <Tooltip
                formatter={(value: number) => [`${value}점`, trendLabel]}
                labelFormatter={(label) => label}
              />
              <Line
                type="monotone"
                dataKey="score"
                name={`${trendLabel} 추이`}
                stroke={trendLineColor}
                strokeWidth={2}
                dot={{ r: 3 }}
                activeDot={{ r: 5 }}
              />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <p className="text-sm text-bank-500">표시할 추이 데이터가 없습니다.</p>
        )}
      </div>
    </div>
  )
}

// STT 버그 신고 탭 컴포넌트
function STTBugReportTabComponent() {
  const [bugReports, setBugReports] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [statusFilter, setStatusFilter] = useState<string>('all') // all, pending, resolved, rejected
  const [selectedReport, setSelectedReport] = useState<any | null>(null)
  const [adminComment, setAdminComment] = useState('')
  const [updating, setUpdating] = useState(false)
  const [playingText, setPlayingText] = useState<string | null>(null) // 재생 중인 텍스트

  useEffect(() => {
    loadBugReports()
  }, [statusFilter])

  const loadBugReports = async () => {
    setLoading(true)
    try {
      const response = await api.get('/rag-simulation/stt-bug-reports', {
        params: statusFilter !== 'all' ? { status: statusFilter } : {}
      })
      setBugReports(response.data)
    } catch (error) {
      console.error('버그 신고 목록 로드 실패:', error)
      alert('버그 신고 목록을 불러오는데 실패했습니다.')
    } finally {
      setLoading(false)
    }
  }

  const updateBugReportStatus = async (reportId: number, status: string) => {
    setUpdating(true)
    try {
      await api.patch(`/rag-simulation/stt-bug-reports/${reportId}`, null, {
        params: {
          status,
          admin_comment: adminComment || null
        }
      })
      await loadBugReports()
      setSelectedReport(null)
      setAdminComment('')
      alert('상태가 업데이트되었습니다.')
    } catch (error) {
      console.error('버그 신고 상태 업데이트 실패:', error)
      alert('상태 업데이트에 실패했습니다.')
    } finally {
      setUpdating(false)
    }
  }

  const saveAdminComment = async (reportId: number) => {
    if (!adminComment.trim()) {
      alert('코멘트를 입력해주세요.')
      return
    }
    
    setUpdating(true)
    try {
      const response = await api.patch(`/rag-simulation/stt-bug-reports/${reportId}`, null, {
        params: {
          admin_comment: adminComment.trim()
        }
      })
      // 선택된 리포트 즉시 업데이트 (PATCH 응답 사용)
      setSelectedReport(response.data)
      // 입력란 초기화 (저장 후 입력란이 사라지도록)
      setAdminComment('')
      // 목록도 즉시 새로고침
      await loadBugReports()
      alert('관리자 코멘트가 저장되었습니다. 신고자에게 알림이 전송되었습니다.')
    } catch (error) {
      console.error('관리자 코멘트 저장 실패:', error)
      alert('코멘트 저장에 실패했습니다.')
    } finally {
      setUpdating(false)
    }
  }

  const getStatusBadge = (status: string) => {
    const styles: Record<string, string> = {
      pending: 'bg-yellow-100 text-yellow-800',
      resolved: 'bg-green-100 text-green-800',
      rejected: 'bg-red-100 text-red-800'
    }
    const labels: Record<string, string> = {
      pending: '대기중',
      resolved: '해결됨',
      rejected: '거부됨'
    }
    return (
      <span className={`px-2 py-1 rounded-full text-xs font-medium ${styles[status] || 'bg-gray-100 text-gray-800'}`}>
        {labels[status] || status}
      </span>
    )
  }

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-xl shadow-md p-6">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-2xl font-bold text-gray-900">STT 버그 신고</h2>
          <div className="flex gap-2">
            <button
              onClick={() => setStatusFilter('all')}
              className={`px-4 py-2 rounded-lg font-medium transition-all ${
                statusFilter === 'all'
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              전체
            </button>
            <button
              onClick={() => setStatusFilter('pending')}
              className={`px-4 py-2 rounded-lg font-medium transition-all ${
                statusFilter === 'pending'
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              대기중
            </button>
            <button
              onClick={() => setStatusFilter('resolved')}
              className={`px-4 py-2 rounded-lg font-medium transition-all ${
                statusFilter === 'resolved'
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              해결됨
            </button>
            <button
              onClick={() => setStatusFilter('rejected')}
              className={`px-4 py-2 rounded-lg font-medium transition-all ${
                statusFilter === 'rejected'
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              거부됨
            </button>
          </div>
        </div>

        {loading ? (
          <div className="text-center py-12">
            <ArrowPathIcon className="w-8 h-8 text-gray-400 mx-auto animate-spin" />
            <p className="text-gray-500 mt-4">로딩 중...</p>
          </div>
        ) : bugReports.length === 0 ? (
          <div className="text-center py-12">
            <ExclamationTriangleIcon className="w-12 h-12 text-gray-300 mx-auto mb-4" />
            <p className="text-gray-500">버그 신고가 없습니다.</p>
          </div>
        ) : (
          <div className="space-y-4">
            {bugReports.map((report) => (
              <div
                key={report.id}
                className="border border-gray-200 rounded-lg p-4 hover:bg-gray-50 transition-colors cursor-pointer"
                onClick={() => setSelectedReport(report)}
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      {getStatusBadge(report.status)}
                      <span className="text-sm text-gray-600">
                        {report.user_name || '사용자'}
                      </span>
                      <span className="text-xs text-gray-500">
                        {formatKSTDateTime(report.created_at)}
                      </span>
                    </div>
                    <div className="space-y-2">
                      <div>
                        <span className="text-xs font-medium text-gray-500">STT 인식:</span>
                        <p className="text-sm text-gray-700 bg-gray-50 p-2 rounded mt-1">
                          {report.recognized_text}
                        </p>
                      </div>
                      <div>
                        <span className="text-xs font-medium text-gray-500">실제 발화:</span>
                        <p className="text-sm text-gray-700 bg-blue-50 p-2 rounded mt-1">
                          {report.original_text}
                        </p>
                      </div>
                      {report.description && (
                        <div>
                          <span className="text-xs font-medium text-gray-500">상세 설명:</span>
                          <p className="text-sm text-gray-600 mt-1">{report.description}</p>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 상세 모달 */}
      {selectedReport && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            <div className="sticky top-0 bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
              <h3 className="text-lg font-bold text-gray-900">버그 신고 상세</h3>
              <button
                onClick={() => {
                  // 모달 닫을 때 재생 중지
                  window.speechSynthesis.cancel()
                  setPlayingText(null)
                  setSelectedReport(null)
                  setAdminComment('')
                }}
                className="text-gray-400 hover:text-gray-600 transition-colors"
              >
                <XMarkIcon className="w-6 h-6" />
              </button>
            </div>

            <div className="px-6 py-4 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">상태</label>
                {getStatusBadge(selectedReport.status)}
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">신고자</label>
                <p className="text-sm text-gray-600">{selectedReport.user_name || '사용자'}</p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">신고 일시</label>
                <p className="text-sm text-gray-600">{formatKSTDateTime(selectedReport.created_at)}</p>
              </div>

              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="block text-sm font-medium text-gray-700">STT 인식 텍스트 (오인식)</label>
                  <button
                    onClick={() => {
                      if (playingText === selectedReport.recognized_text) {
                        // 이미 재생 중이면 중지
                        window.speechSynthesis.cancel()
                        setPlayingText(null)
                      } else {
                        // 재생 시작
                        window.speechSynthesis.cancel() // 기존 재생 중지
                        const utterance = new SpeechSynthesisUtterance(selectedReport.recognized_text)
                        utterance.lang = 'ko-KR'
                        utterance.rate = 1.0
                        utterance.pitch = 1.0
                        utterance.volume = 1.0
                        
                        utterance.onend = () => {
                          setPlayingText(null)
                        }
                        utterance.onerror = () => {
                          setPlayingText(null)
                        }
                        
                        window.speechSynthesis.speak(utterance)
                        setPlayingText(selectedReport.recognized_text)
                      }
                    }}
                    className="flex items-center gap-1 px-3 py-1.5 bg-green-500 hover:bg-green-600 text-white rounded-lg transition-colors text-sm font-medium"
                    title="재생"
                  >
                    <SpeakerWaveIcon className="w-4 h-4" />
                    <span>재생</span>
                  </button>
                </div>
                <p className="text-sm text-gray-700 bg-gray-50 p-3 rounded">{selectedReport.recognized_text}</p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">실제 발화 내용</label>
                <p className="text-sm text-gray-700 bg-blue-50 p-3 rounded">{selectedReport.original_text}</p>
              </div>

              {selectedReport.description && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">상세 설명</label>
                  <p className="text-sm text-gray-600 whitespace-pre-wrap">{selectedReport.description}</p>
                </div>
              )}

              {selectedReport.admin_comment && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">관리자 코멘트</label>
                  <p className="text-sm text-gray-600 whitespace-pre-wrap bg-blue-50 p-3 rounded border border-blue-200">{selectedReport.admin_comment}</p>
                </div>
              )}

              {!selectedReport.admin_comment && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">관리자 코멘트</label>
                  <textarea
                    value={adminComment}
                    onChange={(e) => setAdminComment(e.target.value)}
                    placeholder="관리자 코멘트를 입력하세요..."
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
                    rows={4}
                  />
                </div>
              )}
            </div>

            <div className="sticky bottom-0 bg-gray-50 border-t border-gray-200 px-6 py-4 flex justify-between items-center gap-3">
              <div className="flex gap-3">
                {selectedReport.status !== 'resolved' && (
                  <button
                    onClick={() => updateBugReportStatus(selectedReport.id, 'resolved')}
                    disabled={updating}
                    className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
                  >
                    {updating ? '처리 중...' : '해결됨으로 표시'}
                  </button>
                )}
                {selectedReport.status !== 'rejected' && (
                  <button
                    onClick={() => updateBugReportStatus(selectedReport.id, 'rejected')}
                    disabled={updating}
                    className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
                  >
                    {updating ? '처리 중...' : '거부'}
                  </button>
                )}
              </div>
              <div className="flex gap-3">
                {!selectedReport.admin_comment && (
                  <button
                    onClick={() => saveAdminComment(selectedReport.id)}
                    disabled={updating || !adminComment.trim()}
                    className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
                  >
                    {updating ? '저장 중...' : '코멘트 저장'}
                  </button>
                )}
                <button
                  onClick={() => {
                    // 모달 닫을 때 재생 중지
                    window.speechSynthesis.cancel()
                    setPlayingText(null)
                    setSelectedReport(null)
                    setAdminComment('')
                  }}
                  className="px-4 py-2 text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
                  disabled={updating}
                >
                  닫기
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

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
    if (user) {
      loadDashboard()
    }
  }, [user?.id, user?.role])

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
      // 이전 데이터 초기화
      setData(null)
      setRecordings([])
      setMatchingData(null)
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
    return <MenteeDashboard data={data} currentTime={currentTime} recordings={recordings} onRefresh={loadDashboard} />
  } else if (user?.role === 'mentor') {
    return <MentorDashboard data={data} currentTime={currentTime} onRefresh={loadDashboard} />
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

function MenteeDashboard({ data, currentTime, recordings, onRefresh }: any) {
  const navigate = useNavigate()
  const location = useLocation()
  // location.state에서 activeTab 정보를 받아서 초기값 설정
  const [activeTab, setActiveTab] = useState<'dashboard' | 'simulation' | 'stt-bug'>(
    location.state?.activeTab || 'dashboard'
  )
  
  // 🆕 테스트 평가서로 스크롤 (테스트 모드에서 평가서 완료 후 대시보드로 이동 시)
  useEffect(() => {
    if (location.state?.scrollToTestEvaluations && activeTab === 'simulation') {
      // 시뮬레이션 탭이 활성화된 후 약간의 지연을 두고 스크롤
      setTimeout(() => {
        const testEvaluationSection = document.getElementById('test-evaluation-section')
        if (testEvaluationSection) {
          testEvaluationSection.scrollIntoView({ behavior: 'smooth', block: 'start' })
        }
      }, 300)
    }
  }, [location.state?.scrollToTestEvaluations, activeTab])
  const quizHistory = useQuizStore((state) => state.history)
  const setHistory = useQuizStore((state) => state.setHistory)
  const currentUser = useAuthStore((state) => state.user)
  const [globalAverageData, setGlobalAverageData] = useState<any[] | null>(null)
  const [feedbackHistory, setFeedbackHistory] = useState<any[]>([])
  const [allFeedbackHistory, setAllFeedbackHistory] = useState<any[]>([])  // 전체 데이터 보관
  const [loadingFeedback, setLoadingFeedback] = useState(false)
  const [currentPage, setCurrentPage] = useState(1)
  const itemsPerPage = 10
  const [selectedWeekOffset, setSelectedWeekOffset] = useState(0)  // 0: 이번주, -1: 지난주, -2: 2주전...
  const [hasInitialized, setHasInitialized] = useState(false)  // 초기 필터링 완료 여부
  
  // 시뮬레이션 녹화 관련 상태
  const [showRecordingModal, setShowRecordingModal] = useState(false)
  const [selectedRecording, setSelectedRecording] = useState<any>(null)
  const [recordingsMap, setRecordingsMap] = useState<Record<number, any>>({}) // feedback_id -> recording
  const [percentileInfo, setPercentileInfo] = useState<PercentileInfo>(null)
  
  // 학습 현황 집계용 데이터
  useEffect(() => {
    if (!currentUser) return
    quizAPI
      .getMyHistory(50)
      .then((items) => {
        const entries = items.map((item: any) => {
          let categoryStats: Record<string, { correct: number; total: number }> = {}
          const answers = item.answers || {}
          const questions = item.questions || []
          const rawToNormalized: Record<string, number> = {}
          const normalizedQuestions = questions.map((q: any, idx: number) => ({
            q_no: Number.isFinite(Number(q.q_no)) ? Number(q.q_no) : idx + 1,
            q_id: (() => {
              const rawId = q.q_id ?? q.question_id ?? q.qid ?? q.id ?? idx + 1
              const numericId = Number(String(rawId).replace(/\D+/g, ''))
              const qId = Number.isFinite(numericId) && numericId > 0 ? numericId : idx + 1
              rawToNormalized[String(rawId)] = qId
              return qId
            })(),
            question: q.question,
            category_name: q.category_name ?? q.category ?? '기타',
            ['보기 1']: q['보기 1'] ?? q.choice1 ?? '',
            ['보기 2']: q['보기 2'] ?? q.choice2 ?? '',
            ['보기 3']: q['보기 3'] ?? q.choice3 ?? '',
            ['보기 4']: q['보기 4'] ?? q.choice4 ?? '',
            answer: q.answer,
            comment: q.comment ?? '',
            source_files: q.source_files ?? [],
          }))

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

          if (item.category_stats) {
            categoryStats = { ...item.category_stats }
          } else {
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
          }

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
            mode: item.mode as QuizMode,
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
  }, [currentUser?.id, setHistory])

  useEffect(() => {
    quizAPI
      .getAggregateStats()
      .then((agg) => {
        if (!agg?.categories?.length) return
        const mapped = agg.categories.map((cat: any) => ({
          name: cat.category,
          score: Math.round((cat.accuracy ?? 0) * 100),
          accuracy: cat.accuracy ?? 0,
          solved: cat.total ?? 0,
          correct: cat.correct ?? 0,
        }))
        setGlobalAverageData(mapped)
      })
      .catch(() => setGlobalAverageData(null))
  }, [])

  const userHistory = useMemo(() => {
    if (!currentUser) return []
    return quizHistory.filter((entry: QuizHistoryEntry) => entry.userId === currentUser.id)
  }, [currentUser, quizHistory])

  const performanceData = useMemo(() => {
    const latest = userHistory[0]
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
    return []
  }, [userHistory])
  
  // 최근 대화 더보기/접기 상태 관리 (index 기반)
  const [expandedChats, setExpandedChats] = useState<Record<number, boolean>>({})
  const toggleChatExpand = (idx: number) => {
    setExpandedChats(prev => ({ ...prev, [idx]: !prev[idx] }))
  }
  
  // 피드백 히스토리 로드
  useEffect(() => {
    loadFeedbackHistory()
  }, [])
  
  // 시뮬레이션 탭이 활성화될 때마다 데이터 리프레시
  useEffect(() => {
    if (activeTab === 'simulation') {
      console.log('🔄 시뮬레이션 탭 활성화 - 피드백 히스토리 리프레시')
      loadFeedbackHistory()
    }
  }, [activeTab])
  
  // 데이터 로드 후 자동으로 이번 주로 필터링 (없으면 전체 데이터 표시)
  useEffect(() => {
    if (allFeedbackHistory.length > 0 && !hasInitialized) {
      // 초기 로드 시에만 이번 주로 필터링 시도 (filterByWeek 내부에서 자동으로 전체 데이터로 전환됨)
      console.log(`🔄 초기 필터링 시작: 전체 ${allFeedbackHistory.length}개 데이터 중 이번 주 필터링 시도`)
      filterByWeek(0)
      setHasInitialized(true)
    }
  }, [allFeedbackHistory, hasInitialized])
  
  // 피드백 상세보기에서 돌아올 때 스크롤 위치 복원
  useEffect(() => {
    if (location.state?.returnScrollY !== undefined) {
      // DOM이 완전히 렌더링된 후 스크롤 위치 복원
      setTimeout(() => {
        window.scrollTo({
          top: location.state.returnScrollY,
          behavior: 'smooth'
        })
        // state 정리 (뒤로가기 시 다시 스크롤되지 않도록)
        window.history.replaceState({}, '')
      }, 100)
    }
  }, [location.state?.returnScrollY])
  
  const loadFeedbackHistory = async () => {
    try {
      console.log('📥 피드백 히스토리 로드 시작...')
      setLoadingFeedback(true)
      // 충분한 데이터 가져오기 (최대 100개)
      // 일반 모드 평가서만 조회 (is_test_mode=false)
      const response = await api.get('/rag-simulation/feedback-history?limit=100&is_test_mode=false')
      const allData = response.data.history || []
      console.log(`✅ 피드백 히스토리 로드 완료: ${allData.length}개 (일반 모드만)`)
      setAllFeedbackHistory(allData)
      // 초기에는 전체 데이터 표시 (필터링은 useEffect에서 처리)
      setFeedbackHistory(allData)
      setHasInitialized(false)  // 초기화 플래그 리셋하여 필터링 실행
    } catch (error) {
      console.error('❌ 피드백 히스토리 로드 실패:', error)
    } finally {
      setLoadingFeedback(false)
    }
  }
  
  // 주차별 필터링 함수
  const filterByWeek = (weekOffset: number) => {
    if (allFeedbackHistory.length === 0) return
    
    const now = new Date()
    
    // 이번 주 월요일 계산
    const currentDay = now.getDay() // 0(일) ~ 6(토)
    const mondayOffset = currentDay === 0 ? -6 : 1 - currentDay // 월요일까지의 일수
    const thisMonday = new Date(now.getFullYear(), now.getMonth(), now.getDate() + mondayOffset)
    thisMonday.setHours(0, 0, 0, 0)
    
    // 선택한 주의 월요일
    const selectedMonday = new Date(thisMonday)
    selectedMonday.setDate(thisMonday.getDate() + weekOffset * 7)
    
    // 선택한 주의 일요일
    const selectedSunday = new Date(selectedMonday)
    selectedSunday.setDate(selectedMonday.getDate() + 6)
    selectedSunday.setHours(23, 59, 59, 999)
    
    // 해당 주차 데이터만 필터링
    const filtered = allFeedbackHistory.filter((fb) => {
      const fbDate = toKST(fb.created_at)
      return fbDate >= selectedMonday && fbDate <= selectedSunday
    })
    
    // 항상 선택한 주차 기준으로만 보여주고, 데이터가 없으면 빈 목록 + 0회로 표시
      setFeedbackHistory(filtered)
      setSelectedWeekOffset(weekOffset)
    setCurrentPage(1) // 페이지 1로 리셋
  }
  
  // 주차 레이블 생성
  const getWeekLabel = (weekOffset: number) => {
    // 전체 보기 모드
    if (weekOffset === -999) {
      return `전체 기록 (${allFeedbackHistory.length}개)`
    }
    
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
      // 현재 스크롤 위치 저장
      const currentScrollY = window.scrollY
      
      const response = await api.get(`/rag-simulation/feedback/${feedbackId}`)
      navigate('/simulation-feedback', {
        state: { 
          feedbackData: response.data.feedback,
          fromHistory: true, // 히스토리에서 온 것을 표시
          returnScrollY: currentScrollY // 돌아갈 스크롤 위치
        }
      })
    } catch (error) {
      console.error('피드백 상세 조회 실패:', error)
      alert('피드백을 불러올 수 없습니다.')
    }
  }
  
  const getGrade = (score: number) => {
    if (score >= 90) return { grade: "A+", color: "text-green-600", bg: "bg-green-50" }
    if (score >= 85) return { grade: "A", color: "text-green-600", bg: "bg-green-50" }
    if (score >= 80) return { grade: "B+", color: "text-blue-600", bg: "bg-blue-50" }
    if (score >= 75) return { grade: "B", color: "text-blue-600", bg: "bg-blue-50" }
    if (score >= 70) return { grade: "C+", color: "text-yellow-600", bg: "bg-yellow-50" }
    if (score >= 65) return { grade: "C", color: "text-yellow-600", bg: "bg-yellow-50" }
    if (score >= 60) return { grade: "D", color: "text-orange-600", bg: "bg-orange-50" }
    return { grade: "F", color: "text-red-600", bg: "bg-red-50" }
  }


  // 녹화 재생
  const playRecording = (feedbackId: number) => {
    console.log('▶️ 재생 버튼 클릭:', { feedbackId, recordingsMap, hasRecording: !!recordingsMap[feedbackId] })
    const recording = recordingsMap[feedbackId]
    
    if (recording) {
      console.log('✅ 녹화 찾음:', recording)
      setSelectedRecording(recording)
      setShowRecordingModal(true)
      console.log('📺 모달 표시 상태 업데이트')
    } else {
      console.warn('⚠️ 녹화를 찾을 수 없음:', { feedbackId, availableIds: Object.keys(recordingsMap) })
      alert('저장된 녹화가 없습니다.')
    }
  }

  // 녹화 정보 로드 (파일 시스템 기반)
  useEffect(() => {
    const loadRecordings = async () => {
      try {
        console.log('📹 녹화 목록 로드 시작...')
        // 새로운 API 엔드포인트 사용
        const response = await api.get('/rag-simulation/recordings/list')
        const recordingsList = response.data || []
        console.log('📹 녹화 목록 받음:', recordingsList.length, '개')
        
        // feedback_id와 매칭하여 맵에 저장
        const map: Record<number, any> = {}
        recordingsList.forEach((recording: any) => {
          // feedback_id가 직접 있는 경우
          if (recording.feedback_id) {
            console.log('📝 녹화 매칭:', { feedback_id: recording.feedback_id, video_url: recording.video_url })
            map[recording.feedback_id] = recording
          } else {
            console.log('⚠️ feedback_id가 없는 녹화:', recording.id)
          }
        })
        console.log('📹 녹화 맵 생성 완료:', Object.keys(map).length, '개')
        setRecordingsMap(map)
      } catch (error) {
        console.error('❌ 녹화 목록 로드 실패:', error)
      }
    }
    
    if (activeTab === 'simulation') {
      loadRecordings()
    }
  }, [activeTab, feedbackHistory])

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
          {/* 관리자만 STT 버그 탭 표시 */}
          {currentUser?.role === 'admin' && (
            <button
              onClick={() => setActiveTab('stt-bug')}
              className={`flex-1 py-3 px-6 rounded-lg font-semibold transition-all ${
                activeTab === 'stt-bug'
                  ? 'bg-blue-600 text-white shadow-md'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              🐛 STT 버그
            </button>
          )}
        </div>
      </div>

      {/* 대시보드 탭 */}
      {activeTab === 'dashboard' && (
        <MyLearning
          customHistory={userHistory}
          radarData={performanceData}
          globalAverageData={globalAverageData}
          percentileInfo={percentileInfo}
          setPercentileInfo={setPercentileInfo}
        />
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
            {selectedWeekOffset !== -999 && (
              <>
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
              </>
            )}
            
            <div className={`px-6 py-2 rounded-lg border ${
              selectedWeekOffset === -999
                ? 'bg-gradient-to-r from-gray-50 to-gray-100 border-gray-300'
                : 'bg-gradient-to-r from-blue-50 to-purple-50 border-blue-200'
            }`}>
              <p className={`text-sm font-semibold ${
                selectedWeekOffset === -999 ? 'text-gray-700' : 'text-blue-900'
              }`}>
                {getWeekLabel(selectedWeekOffset)}
              </p>
            </div>
            
            {selectedWeekOffset !== -999 && (
              <>
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
              </>
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
                      // 선택된 주차 데이터 (currentWeek)
                      const currentWeek = feedbackHistory
                      
                      if (currentWeek.length === 0) {
                        return <span className="text-2xl text-gray-400">N/A</span>
                      }
                      
                      // 이전 주차 데이터 계산
                      const now = new Date()
                      const currentDay = now.getDay()
                      const mondayOffset = currentDay === 0 ? -6 : 1 - currentDay
                      const thisMonday = new Date(now.getFullYear(), now.getMonth(), now.getDate() + mondayOffset)
                      thisMonday.setHours(0, 0, 0, 0)
                      
                      // 선택된 주의 월요일
                      const selectedMonday = new Date(thisMonday)
                      selectedMonday.setDate(thisMonday.getDate() + (selectedWeekOffset * 7))
                      
                      // 이전 주의 월요일과 일요일
                      const prevMonday = new Date(selectedMonday)
                      prevMonday.setDate(selectedMonday.getDate() - 7)
                      
                      const prevSunday = new Date(prevMonday)
                      prevSunday.setDate(prevMonday.getDate() + 6)
                      prevSunday.setHours(23, 59, 59, 999)
                      
                      // 이전 주차 데이터 필터링
                      const previousWeek = allFeedbackHistory.filter(fb => {
                        const fbDate = toKST(fb.created_at)
                        return fbDate >= prevMonday && fbDate <= prevSunday
                      })
                      
                      // 이전 주 데이터가 있어야 비교 가능
                      if (previousWeek.length > 0) {
                        const currentAvg = currentWeek.reduce((sum, fb) => sum + fb.overall_score, 0) / currentWeek.length
                        const previousAvg = previousWeek.reduce((sum, fb) => sum + fb.overall_score, 0) / previousWeek.length
                        
                        const improvement = ((currentAvg - previousAvg) / previousAvg) * 100
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
                                전주 대비
                              </span>
                            </div>
                          </div>
                        )
                      }
                      
                      return <span className="text-2xl text-gray-400">N/A</span>
                    })()}
                  </div>
                </div>
                <div className={`p-3 ${
                  (() => {
                    const currentWeek = feedbackHistory
                    if (currentWeek.length === 0) return 'bg-gray-100'
                    
                    // 이전 주차 계산
                    const now = new Date()
                    const currentDay = now.getDay()
                    const mondayOffset = currentDay === 0 ? -6 : 1 - currentDay
                    const thisMonday = new Date(now.getFullYear(), now.getMonth(), now.getDate() + mondayOffset)
                    thisMonday.setHours(0, 0, 0, 0)
                    
                    const selectedMonday = new Date(thisMonday)
                    selectedMonday.setDate(thisMonday.getDate() + (selectedWeekOffset * 7))
                    
                    const prevMonday = new Date(selectedMonday)
                    prevMonday.setDate(selectedMonday.getDate() - 7)
                    
                    const prevSunday = new Date(prevMonday)
                    prevSunday.setDate(prevMonday.getDate() + 6)
                    prevSunday.setHours(23, 59, 59, 999)
                    
                    const previousWeek = allFeedbackHistory.filter(fb => {
                      const fbDate = toKST(fb.created_at)
                      return fbDate >= prevMonday && fbDate <= prevSunday
                    })
                    
                    if (previousWeek.length > 0) {
                      const currentAvg = currentWeek.reduce((sum, fb) => sum + fb.overall_score, 0) / currentWeek.length
                      const previousAvg = previousWeek.reduce((sum, fb) => sum + fb.overall_score, 0) / previousWeek.length
                      const improvement = ((currentAvg - previousAvg) / previousAvg) * 100
                      return improvement >= 0 ? 'bg-green-100' : 'bg-red-100'
                    }
                    return 'bg-gray-100'
                  })()
                } rounded-lg`}>
                  <ArrowTrendingUpIcon className={`w-6 h-6 ${
                    (() => {
                      const currentWeek = feedbackHistory
                      if (currentWeek.length === 0) return 'text-gray-400'
                      
                      const now = new Date()
                      const currentDay = now.getDay()
                      const mondayOffset = currentDay === 0 ? -6 : 1 - currentDay
                      const thisMonday = new Date(now.getFullYear(), now.getMonth(), now.getDate() + mondayOffset)
                      thisMonday.setHours(0, 0, 0, 0)
                      
                      const selectedMonday = new Date(thisMonday)
                      selectedMonday.setDate(thisMonday.getDate() + (selectedWeekOffset * 7))
                      
                      const prevMonday = new Date(selectedMonday)
                      prevMonday.setDate(selectedMonday.getDate() - 7)
                      
                      const prevSunday = new Date(prevMonday)
                      prevSunday.setDate(prevMonday.getDate() + 6)
                      prevSunday.setHours(23, 59, 59, 999)
                      
                      const previousWeek = allFeedbackHistory.filter(fb => {
                        const fbDate = toKST(fb.created_at)
                        return fbDate >= prevMonday && fbDate <= prevSunday
                      })
                      
                      if (previousWeek.length > 0) {
                        const currentAvg = currentWeek.reduce((sum, fb) => sum + fb.overall_score, 0) / currentWeek.length
                        const previousAvg = previousWeek.reduce((sum, fb) => sum + fb.overall_score, 0) / previousWeek.length
                        const improvement = ((currentAvg - previousAvg) / previousAvg) * 100
                        return improvement >= 0 ? 'text-green-600' : 'text-red-600'
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
                  
                  // 2일 이상에 걸쳐 있으면 → 날짜별 평균 점수 표시 (월~일 모두 포함)
                  if (uniqueDates.length > 1) {
                    // 선택된 주차의 월요일과 일요일 계산
                    const now = new Date()
                    const currentDay = now.getDay()
                    const mondayOffset = currentDay === 0 ? -6 : 1 - currentDay
                    const thisMonday = new Date(now.getFullYear(), now.getMonth(), now.getDate() + mondayOffset)
                    thisMonday.setHours(0, 0, 0, 0)
                    
                    const selectedMonday = new Date(thisMonday)
                    selectedMonday.setDate(thisMonday.getDate() + (selectedWeekOffset * 7))
                    
                    const selectedSunday = new Date(selectedMonday)
                    selectedSunday.setDate(selectedMonday.getDate() + 6)
                    selectedSunday.setHours(23, 59, 59, 999)
                    
                    // 날짜별로 점수들을 배열로 저장
                    const dailyData = new Map()
                    weekData.forEach(fb => {
                      const dateKey = toKST(fb.created_at).toDateString()
                      if (!dailyData.has(dateKey)) {
                        dailyData.set(dateKey, [])
                      }
                      dailyData.get(dateKey).push(fb)
                    })
                    
                    // 월~일 7일 모두 생성 (데이터 없는 날은 null)
                    const weekChartData = []
                    for (let i = 0; i < 7; i++) {
                      const currentDate = new Date(selectedMonday)
                      currentDate.setDate(selectedMonday.getDate() + i)
                      const dateKey = currentDate.toDateString()
                      
                      const dayOfWeek = ['일','월','화','수','목','금','토'][currentDate.getDay()]
                      const dateLabel = `${currentDate.getMonth()+1}.${currentDate.getDate()}.(${dayOfWeek})`
                      
                      if (dailyData.has(dateKey)) {
                        // 데이터가 있는 날: 평균 점수 계산
                        const feedbacks = dailyData.get(dateKey)
                        const avgScore = feedbacks.reduce((sum, fb) => sum + fb.overall_score, 0) / feedbacks.length
                        weekChartData.push({
                          date: dateLabel,
                          score: Math.round(avgScore * 10) / 10,  // 소수점 1자리
                          fullDate: currentDate.toLocaleDateString('ko-KR'),
                          count: feedbacks.length  // 해당 날짜 시뮬레이션 횟수
                        })
                      } else {
                        // 데이터가 없는 날: null로 표시
                        weekChartData.push({
                          date: dateLabel,
                          score: null,
                          fullDate: currentDate.toLocaleDateString('ko-KR'),
                          count: 0
                        })
                      }
                    }
                    
                    return weekChartData
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
                    formatter={(value: number | null) => {
                      if (value === null) return ['데이터 없음', '']
                      return [`${value}점`, '평균 점수']
                    }}
                    labelFormatter={(label: string, payload: any) => {
                      if (payload && payload[0] && payload[0].payload) {
                        const data = payload[0].payload
                        if (data.score === null) {
                          return `${data.fullDate} (데이터 없음)`
                        }
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
                    dot={(props: any) => {
                      // null 값은 점 표시 안 함
                      if (props.payload.score === null) return null
                      return <circle key={`dot-${props.index}`} cx={props.cx} cy={props.cy} r={5} fill="#3B82F6" strokeWidth={2} stroke="#fff" />
                    }}
                    activeDot={{ r: 7, fill: '#2563EB' }}
                    connectNulls={true}  // null 값도 선으로 연결
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
                    empathy: 0,  // 통합 계산용
                    clarity: 0,  // 통합 계산용
                    kindness: 0,  // 통합 계산용
                    confidence: 0,  // 통합 계산용
                    persona_fit: 0  // 페르소나 정합도
                  }
                  
                  feedbackHistory.forEach(fb => {
                    // competencies 배열에서 추출
                    if (fb.competencies && Array.isArray(fb.competencies)) {
                      fb.competencies.forEach((comp: any) => {
                        if (comp.name === '지식') competencyScores.knowledge += comp.score
                        else if (comp.name === '기술') competencyScores.skill += comp.score
                        else if (comp.name === '친절도') {
                          competencyScores.kindness += comp.score
                        }
                        else if (comp.name === '전달력') {
                          // 전달력은 명확성과 자신감의 평균이므로 각각에 더함
                          competencyScores.clarity += comp.score
                          competencyScores.confidence += comp.score
                        }
                        else if (comp.name === '페르소나 정합도') {
                          competencyScores.persona_fit += comp.score
                        }
                        // 하위 호환성: 기존 6가지 역량도 지원
                        else if (comp.name === '공감도') competencyScores.empathy += comp.score
                        else if (comp.name === '명확성') competencyScores.clarity += comp.score
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
                      competencyScores.persona_fit += fb.persona_fit_score || 0
                    }
                  })
                  
                  const count = feedbackHistory.length
                  
                  // 통합된 5가지 역량으로 변환 (페르소나 정합도 추가)
                  return [
                    { name: '지식', score: Math.round(competencyScores.knowledge / count) },
                    { name: '기술', score: Math.round(competencyScores.skill / count) },
                    { name: '친절도', score: Math.round(competencyScores.kindness / count) },
                    { name: '전달력', score: Math.round((competencyScores.clarity + competencyScores.confidence) / (count * 2)) },
                    { name: '페르소나 정합도', score: Math.round(competencyScores.persona_fit / count) }
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

          {/* 역량별 주간 변화 추이 */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-gradient-to-br from-indigo-50 to-white rounded-xl shadow-md p-6 border border-indigo-100 mt-6"
          >
            <h3 className="text-lg font-bold text-gray-900 mb-6 flex items-center gap-2">
              <div className="w-1 h-6 bg-indigo-600 rounded-full"></div>
              역량별 주간 변화 추이
            </h3>
            
            <div className="grid grid-cols-2 gap-4">
              {(() => {
                const competencies = [
                  { name: '지식', key: 'knowledge', color: '#3B82F6' },
                  { name: '기술', key: 'skill', color: '#8B5CF6' },
                  { name: '친절도', key: 'kindness', color: '#F59E0B' },
                  { name: '페르소나 정합도', key: 'persona_fit', color: '#EC4899' },
                  { name: '전달력', key: 'delivery', color: '#10B981' }
                ]
                
                const chartData = (() => {
                  if (feedbackHistory.length === 0) return []
                  
                  const weekData = [...feedbackHistory].reverse()
                  const uniqueDates = [...new Set(weekData.map(fb => 
                    toKST(fb.created_at).toDateString()
                  ))]
                  
                  // 2일 이상에 걸쳐 있으면 → 날짜별 평균 점수 표시 (월~일 모두 포함)
                  if (uniqueDates.length > 1) {
                    // 선택된 주차의 월요일과 일요일 계산
                    const now = new Date()
                    const currentDay = now.getDay()
                    const mondayOffset = currentDay === 0 ? -6 : 1 - currentDay
                    const thisMonday = new Date(now.getFullYear(), now.getMonth(), now.getDate() + mondayOffset)
                    thisMonday.setHours(0, 0, 0, 0)
                    
                    const selectedMonday = new Date(thisMonday)
                    selectedMonday.setDate(thisMonday.getDate() + (selectedWeekOffset * 7))
                    
                    // 날짜별로 점수들을 배열로 저장
                    const dailyData = new Map()
                    weekData.forEach(fb => {
                      const dateKey = toKST(fb.created_at).toDateString()
                      if (!dailyData.has(dateKey)) {
                        dailyData.set(dateKey, [])
                      }
                      dailyData.get(dateKey).push(fb)
                    })
                    
                    // 월~일 7일 모두 생성 (데이터 없는 날은 null)
                    const weekChartData = []
                    for (let i = 0; i < 7; i++) {
                      const currentDate = new Date(selectedMonday)
                      currentDate.setDate(selectedMonday.getDate() + i)
                      const dateKey = currentDate.toDateString()
                      
                      const dayOfWeek = ['일','월','화','수','목','금','토'][currentDate.getDay()]
                      const dateLabel = `${currentDate.getMonth()+1}.${currentDate.getDate()}`
                      
                      if (dailyData.has(dateKey)) {
                        // 데이터가 있는 날: 각 역량의 평균 점수 계산
                        const feedbacks = dailyData.get(dateKey)
                        const competencyScores = {
                          knowledge: 0, skill: 0, empathy: 0,
                          clarity: 0, kindness: 0, confidence: 0,  // 통합 계산용
                          persona_fit: 0  // 페르소나 정합도
                        }
                        
                        feedbacks.forEach((fb: any) => {
                          if (fb.competencies && Array.isArray(fb.competencies)) {
                            fb.competencies.forEach((comp: any) => {
                              if (comp.name === '지식') competencyScores.knowledge += comp.score
                              else if (comp.name === '기술') competencyScores.skill += comp.score
                              else if (comp.name === '친절도') {
                                competencyScores.kindness += comp.score
                              }
                              else if (comp.name === '전달력') {
                                // 전달력은 명확성과 자신감의 평균이므로 각각에 더함
                                competencyScores.clarity += comp.score
                                competencyScores.confidence += comp.score
                              }
                              else if (comp.name === '페르소나 정합도') {
                                competencyScores.persona_fit += comp.score
                              }
                              // 하위 호환성: 기존 6가지 역량도 지원
                              else if (comp.name === '공감도') competencyScores.empathy += comp.score
                              else if (comp.name === '명확성') competencyScores.clarity += comp.score
                              else if (comp.name === '자신감') competencyScores.confidence += comp.score
                            })
                          } else {
                            competencyScores.knowledge += fb.knowledge_score || 0
                            competencyScores.skill += fb.skill_score || 0
                            competencyScores.empathy += fb.empathy_score || 0
                            competencyScores.clarity += fb.clarity_score || 0
                            competencyScores.kindness += fb.kindness_score || 0
                            competencyScores.confidence += fb.confidence_score || 0
                            competencyScores.persona_fit += fb.persona_fit_score || 0
                          }
                        })
                        
                        const count = feedbacks.length
                        weekChartData.push({
                          date: dateLabel,
                          knowledge: Math.round(competencyScores.knowledge / count * 10) / 10,
                          skill: Math.round(competencyScores.skill / count * 10) / 10,
                          kindness: Math.round(competencyScores.kindness / count * 10) / 10,
                          delivery: Math.round((competencyScores.clarity + competencyScores.confidence) / (count * 2) * 10) / 10,
                          persona_fit: Math.round(competencyScores.persona_fit / count * 10) / 10,
                        })
                      } else {
                        // 데이터가 없는 날: null로 표시
                        weekChartData.push({
                          date: dateLabel,
                          knowledge: null, skill: null, kindness: null, delivery: null, persona_fit: null,
                        })
                      }
                    }
                    
                    return weekChartData
                  }
                  
                  // 같은 날만 있으면 → 시간별 표시
                  return weekData.map(fb => {
                    const competencyScores = { knowledge: 0, skill: 0, empathy: 0, clarity: 0, kindness: 0, confidence: 0, persona_fit: 0 }
                    
                    let deliveryScore = 0
                    if (fb.competencies && Array.isArray(fb.competencies)) {
                      fb.competencies.forEach((comp: any) => {
                        if (comp.name === '지식') competencyScores.knowledge = comp.score
                        else if (comp.name === '기술') competencyScores.skill = comp.score
                        else if (comp.name === '공감도') competencyScores.empathy = comp.score
                        else if (comp.name === '명확성') competencyScores.clarity = comp.score
                        else if (comp.name === '친절도') competencyScores.kindness = comp.score
                        else if (comp.name === '자신감') competencyScores.confidence = comp.score
                        else if (comp.name === '페르소나 정합도') competencyScores.persona_fit = comp.score
                        else if (comp.name === '전달력') deliveryScore = comp.score  // 전달력 직접 사용
                      })
                    } else {
                      competencyScores.knowledge = fb.knowledge_score || 0
                      competencyScores.skill = fb.skill_score || 0
                      competencyScores.empathy = fb.empathy_score || 0
                      competencyScores.clarity = fb.clarity_score || 0
                      competencyScores.kindness = fb.kindness_score || 0
                      competencyScores.confidence = fb.confidence_score || 0
                      competencyScores.persona_fit = fb.persona_fit_score || 0
                    }
                    
                    // 전달력이 없으면 clarity와 confidence의 평균으로 계산
                    if (deliveryScore === 0) {
                      deliveryScore = (competencyScores.clarity + competencyScores.confidence) / 2
                    }
                    
                    return {
                      date: formatKSTTime(fb.created_at),
                      knowledge: competencyScores.knowledge,
                      skill: competencyScores.skill,
                      kindness: competencyScores.kindness,
                      delivery: deliveryScore,
                      persona_fit: competencyScores.persona_fit
                    }
                  })
                })()
                
                return competencies.map(comp => (
                  <div key={comp.key} className="bg-white rounded-lg p-4 border border-gray-200 shadow-sm">
                    <h4 className="text-sm font-semibold text-gray-700 mb-3">{comp.name}</h4>
                    <ResponsiveContainer width="100%" height={140}>
                      <LineChart data={chartData}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
                        <XAxis 
                          dataKey="date" 
                          tick={{ fontSize: 10, fill: '#6B7280' }}
                          stroke="#D1D5DB"
                          height={30}
                        />
                        <YAxis 
                          domain={[0, 100]} 
                          tick={{ fontSize: 10, fill: '#6B7280' }}
                          stroke="#D1D5DB"
                          width={35}
                        />
                        <Tooltip 
                          contentStyle={{ 
                            backgroundColor: 'rgba(255, 255, 255, 0.98)', 
                            border: 'none', 
                            borderRadius: '8px',
                            boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)',
                            padding: '8px 12px'
                          }}
                          labelStyle={{ fontWeight: 600, color: '#1F2937', fontSize: '11px' }}
                          formatter={(value: number | null) => {
                            if (value === null) return ['데이터 없음', '']
                            return [`${value}점`, comp.name]
                          }}
                        />
                        <Line 
                          type="monotone" 
                          dataKey={comp.key}
                          stroke={comp.color}
                          strokeWidth={2.5}
                          dot={{ r: 3, fill: comp.color, strokeWidth: 2, stroke: '#fff' }}
                          activeDot={{ r: 5 }}
                          connectNulls={true}
                        />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                ))
              })()}
            </div>
          </motion.div>

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
                      <th className="text-left py-3 px-4 font-semibold text-gray-700">페르소나</th>
                      <th className="text-left py-3 px-4 font-semibold text-gray-700">상황</th>
                      <th className="text-center py-3 px-4 font-semibold text-gray-700">종합 점수</th>
                      <th className="text-center py-3 px-4 font-semibold text-gray-700">등급</th>
                      <th className="text-center py-3 px-4 font-semibold text-gray-700">대화 턴</th>
                      <th className="text-center py-3 px-4 font-semibold text-gray-700">경과 시간</th>
                      <th className="text-center py-3 px-4 font-semibold text-gray-700">시뮬레이션 녹화</th>
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
                            {fb.persona_info ? (
                              <span className="inline-flex items-center px-2 py-1 bg-purple-50 text-purple-700 text-xs font-medium rounded-md">
                                {fb.persona_info}
                              </span>
                            ) : (
                              <span className="text-xs text-gray-400">정보 없음</span>
                            )}
                          </td>
                          <td className="py-4 px-4">
                            {fb.situation_info ? (
                              <span className="inline-flex items-center px-2 py-1 bg-blue-50 text-blue-700 text-xs font-medium rounded-md">
                                {fb.situation_info}
                              </span>
                            ) : (
                              <span className="text-xs text-gray-400">정보 없음</span>
                            )}
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
                          <td className="py-4 px-4 text-center">
                            <span className="text-sm text-gray-600">
                              {fb.duration_seconds 
                                ? `${Math.floor(fb.duration_seconds / 60)}분 ${fb.duration_seconds % 60}초`
                                : '-'}
                            </span>
                          </td>
                          <td className="py-4 px-4 text-center">
                            <div className="flex items-center justify-center gap-2">
                              {recordingsMap[fb.id] ? (
                                <button
                                  onClick={() => playRecording(fb.id)}
                                  className="px-3 py-1.5 bg-green-600 text-white text-sm rounded-lg hover:bg-green-700 transition-colors flex items-center gap-1"
                                >
                                  <PlayIcon className="w-4 h-4" />
                                  재생
                                </button>
                              ) : (
                                <span className="text-gray-400 text-sm">녹화 없음</span>
                              )}
                            </div>
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
            <p className="text-gray-500 text-lg mb-2">
              {selectedWeekOffset === 0 
                ? '이번 주 시뮬레이션 피드백이 없습니다'
                : `${getWeekLabel(selectedWeekOffset)} 시뮬레이션 기록이 없습니다`
              }
            </p>
            <p className="text-gray-400 text-sm">
              {selectedWeekOffset === 0
                ? '시뮬레이션을 완료하면 피드백이 여기에 표시됩니다'
                : '다른 주를 선택하거나 시뮬레이션을 진행해보세요'
              }
            </p>
            {selectedWeekOffset !== 0 && (
              <button
                onClick={() => filterByWeek(0)}
                className="mt-4 px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-all"
              >
                이번 주 보기
              </button>
            )}
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

      {/* STT 버그 탭 (관리자 전용) */}
      {activeTab === 'stt-bug' && currentUser?.role === 'admin' && (
        <STTBugReportTabComponent />
      )}

      {/* 녹화 재생 모달 - 모든 탭에서 표시 */}
      {showRecordingModal && selectedRecording && (
        <div 
          className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-[9999]"
          onClick={(e) => {
            if (e.target === e.currentTarget) {
              setShowRecordingModal(false)
              setSelectedRecording(null)
            }
          }}
        >
          <div className="bg-white rounded-xl shadow-xl p-6 max-w-4xl w-full mx-4 relative z-[10000]">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-xl font-bold text-gray-900">시뮬레이션 녹화 재생</h3>
              <button
                onClick={() => {
                  console.log('❌ 모달 닫기 버튼 클릭')
                  setShowRecordingModal(false)
                  setSelectedRecording(null)
                }}
                className="text-gray-400 hover:text-gray-600"
              >
                <XMarkIcon className="w-6 h-6" />
              </button>
            </div>
            <div className="mb-4">
              <p className="text-sm text-gray-600">
                {selectedRecording.saved_at ? formatKSTDateTime(selectedRecording.saved_at) : 
                 selectedRecording.created_at ? formatKSTDateTime(selectedRecording.created_at) : '날짜 없음'}
                {selectedRecording.file_size && (
                  <span className="ml-2">
                    • 파일 크기: {(selectedRecording.file_size / (1024 * 1024)).toFixed(2)} MB
                  </span>
                )}
              </p>
            </div>
            <video
              controls
              className="w-full rounded-lg"
              style={{ maxHeight: '600px' }}
              autoPlay
              crossOrigin="anonymous"
              onError={(e) => {
                const video = e.currentTarget
                console.error('❌ 비디오 로드 실패:', {
                  error: video.error,
                  networkState: video.networkState,
                  readyState: video.readyState,
                  src: video.src,
                  video_url: selectedRecording.video_url
                })
              }}
              onLoadStart={() => {
                console.log('📹 비디오 로드 시작')
              }}
              onCanPlay={() => {
                console.log('✅ 비디오 재생 가능')
              }}
              onLoadedMetadata={() => {
                console.log('📹 비디오 메타데이터 로드 완료')
              }}
            >
              <source 
                src={`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}${selectedRecording.video_url}`} 
                type="video/webm" 
              />
              <source 
                src={`http://localhost:8000${selectedRecording.video_url}`} 
                type="video/webm" 
              />
              브라우저가 비디오 태그를 지원하지 않습니다.
            </video>
            <div className="mt-2 text-xs text-gray-500">
              비디오 URL: {`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}${selectedRecording.video_url}`}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function MentorDashboard({ data, currentTime, onRefresh }: any) {
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

      {/* 보낸 피드백 섹션 */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="bg-white rounded-xl shadow-md p-6"
      >
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center">
            <img src="/assets/bear.png" alt="하경곰" className="w-8 h-8 mr-3 rounded-full" />
            <h2 className="text-2xl font-bold text-bank-800">보낸 피드백</h2>
          </div>
          {data?.sent_feedbacks && data.sent_feedbacks.length > 0 && (
            <span className="text-sm text-gray-500">총 {data.sent_feedbacks.length}개</span>
          )}
        </div>
        {data?.sent_feedbacks && data.sent_feedbacks.length > 0 ? (
          <div className="space-y-4">
            {data.sent_feedbacks.slice(0, 5).map((feedback: any, idx: number) => {
              const feedbackDate = toKST(feedback.created_at)
              const diffInHours = (currentTime.getTime() - feedbackDate.getTime()) / (1000 * 60 * 60)
              const isRecent = diffInHours <= 24
              
              return (
                <div 
                  key={idx} 
                  className={`p-4 rounded-xl border transition-all ${
                    !feedback.is_read 
                      ? 'bg-gradient-to-r from-yellow-50 to-orange-50 border-yellow-300' 
                      : 'bg-gradient-to-r from-primary-50 to-amber-50 border-primary-100'
                  }`}
                >
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center space-x-2">
                      <span className="font-medium text-primary-700 text-sm">
                        📨 {feedback.mentee_name}에게
                      </span>
                      <span className="text-xs text-gray-400">•</span>
                      <p className="text-xs text-gray-500">
                        {formatKSTDateTime(feedback.created_at)}
                      </p>
                    </div>
                    <div className="flex items-center space-x-2">
                      {isRecent && (
                        <span className="px-2 py-1 bg-green-100 text-green-700 text-xs rounded-full">
                          최근
                        </span>
                      )}
                      {feedback.is_read ? (
                        <span className="px-2 py-1 bg-blue-100 text-blue-700 text-xs rounded-full flex items-center">
                          <CheckCircleIcon className="w-3 h-3 mr-1" />
                          읽음
                        </span>
                      ) : (
                        <span className="px-2 py-1 bg-orange-100 text-orange-700 text-xs rounded-full">
                          안 읽음
                        </span>
                      )}
                    </div>
                  </div>
                  <p className="text-sm text-primary-700 whitespace-pre-wrap">
                    {feedback.feedback_text}
                  </p>
                  {feedback.feedback_type && (
                    <div className="mt-2 pt-2 border-t border-gray-200">
                      <span className={`text-xs px-2 py-1 rounded-full ${
                        feedback.color_section === 'red' 
                          ? 'bg-red-100 text-red-700'
                          : feedback.color_section === 'yellow'
                          ? 'bg-yellow-100 text-yellow-700'
                          : 'bg-green-100 text-green-700'
                      }`}>
                        {feedback.feedback_type === 'general' ? '일반 피드백' : 
                         feedback.feedback_type === 'exam' ? '시험 피드백' : 
                         feedback.feedback_type === 'simulation' ? '시뮬레이션 피드백' : '피드백'}
                      </span>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        ) : (
          <div className="text-center py-8">
            <ChatBubbleLeftRightIcon className="w-16 h-16 text-gray-300 mx-auto mb-4" />
            <p className="text-gray-500 text-lg mb-2">아직 보낸 피드백이 없습니다</p>
            <p className="text-gray-400 text-sm">멘티에게 피드백을 보내보세요</p>
          </div>
        )}
      </motion.div>

      {/* 최근 대화 섹션 */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="bg-white rounded-xl shadow-md p-6"
      >
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center">
            <ChatBubbleLeftRightIcon className="w-6 h-6 text-primary-600 mr-3" />
            <h2 className="text-2xl font-bold text-bank-800">최근 대화</h2>
          </div>
          <div className="flex items-center space-x-3">
            {data?.recent_chats && data.recent_chats.length > 0 && (
              <>
                <span className="text-sm text-gray-500">최근 {data.recent_chats.length}개</span>
                <button
                  onClick={async () => {
                    if (window.confirm('담당 멘티들의 모든 대화 내역을 삭제하시겠습니까? 이 작업은 되돌릴 수 없습니다.')) {
                      try {
                        const result = await dashboardAPI.deleteAllChats()
                        alert(result.message)
                        onRefresh()
                      } catch (error) {
                        console.error('Failed to delete all chats:', error)
                        alert('전체 대화 삭제에 실패했습니다.')
                      }
                    }
                  }}
                  className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white text-sm rounded-lg transition-colors flex items-center space-x-2"
                >
                  <TrashIcon className="w-4 h-4" />
                  <span>전체 삭제</span>
                </button>
              </>
            )}
          </div>
        </div>
        {data?.recent_chats && data.recent_chats.length > 0 ? (
          <div className="space-y-4">
            {data.recent_chats.slice(0, 5).map((chat: any, idx: number) => (
              <div 
                key={idx} 
                className="p-4 rounded-xl border border-gray-200 bg-gray-50 hover:bg-gray-100 transition-colors"
              >
                <div className="flex items-start space-x-3">
                  <div className="flex-shrink-0 w-8 h-8 bg-primary-100 rounded-full flex items-center justify-center">
                    <UserIcon className="w-5 h-5 text-primary-600" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium text-gray-700">
                        {chat.mentee_name || '멘티'}
                      </span>
                      <div className="flex items-center space-x-2">
                        <span className="text-xs text-gray-500">
                          {formatKSTDateTime(chat.created_at)}
                        </span>
                        <button
                          onClick={async () => {
                            if (window.confirm(`${chat.mentee_name}의 대화를 삭제하시겠습니까?`)) {
                              try {
                                await dashboardAPI.deleteChat(chat.id)
                                onRefresh()
                              } catch (error) {
                                console.error('Failed to delete chat:', error)
                                alert('대화 삭제에 실패했습니다.')
                              }
                            }
                          }}
                          className="text-gray-400 hover:text-red-600 transition-colors"
                        >
                          <TrashIcon className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                    <p className="text-sm text-gray-600 line-clamp-2">
                      {chat.user_message}
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-8">
            <ChatBubbleLeftRightIcon className="w-16 h-16 text-gray-300 mx-auto mb-4" />
            <p className="text-gray-500 text-lg mb-2">최근 대화가 없습니다</p>
            <p className="text-gray-400 text-sm">멘티들의 챗봇 대화가 여기에 표시됩니다</p>
          </div>
        )}
      </motion.div>

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
  const location = useLocation()
  const [activeTab, setActiveTab] = useState(0)
  const [userStats, setUserStats] = useState({
    totalUsers: 0,
    mentors: 0,
    mentees: 0,
    activeRelations: 0
  })
  const [recentActivities, setRecentActivities] = useState([])

  const tabs = [
    { name: '사용자 관리', icon: UserIcon },
    { name: '멘토-멘티 관계', icon: AcademicCapIcon },
    { name: '학습 이력', icon: ChartBarIcon },
    { name: '연수원 연동', icon: AcademicCapIcon },
    { name: '매칭 시스템', icon: UserGroupIcon },
    { name: '멘티 EDA', icon: ChartBarIcon },
    { name: '문서 관리', icon: PaperAirplaneIcon },
    { name: '시스템 로그', icon: EyeIcon },
    { name: '챗봇 설정', icon: ChatBubbleLeftRightIcon },
    { name: '챗봇 성능 검증', icon: ChatBubbleBottomCenterTextIcon },
    { name: '테스트 평가서', icon: ChartBarIcon },
    { name: 'LangGraph', icon: CpuChipIcon },
    { name: '시뮬레이션 분석', icon: ChartBarIcon },
    { name: 'STT 버그', icon: ExclamationTriangleIcon }
  ]
  
  // 🆕 location.state에서 adminTab 정보를 받아서 해당 탭으로 이동
  useEffect(() => {
    if (location.state?.adminTab) {
      const tabName = location.state.adminTab
      const tabIndex = tabs.findIndex(tab => tab.name === tabName)
      if (tabIndex !== -1) {
        setActiveTab(tabIndex)
      }
    }
  }, [location.state?.adminTab])

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
          <nav className="flex flex-wrap gap-2 md:flex-nowrap md:space-x-6 px-4 md:px-6 overflow-x-auto scrollbar-hide py-2">
            {tabs.map((tab, index) => (
              <button
                key={index}
                onClick={() => setActiveTab(index)}
                className={`py-3 px-2 border-b-2 font-medium text-sm flex items-center gap-2 transition-colors whitespace-nowrap ${
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
          {activeTab === 3 && <TrainingSyncTab />}
          {activeTab === 4 && <MatchingTab />}
          {activeTab === 5 && <MenteeEDATab />}
          {activeTab === 6 && <DocumentManagementTab />}
          {activeTab === 7 && <SystemLogTab />}
          {activeTab === 8 && <ChatbotSettingsTab />}
          {activeTab === 9 && <ChatbotValidationTab />}
          {activeTab === 10 && <TestFeedbackTab />}
          {activeTab === 11 && <LangGraphTab />}
          {activeTab === 12 && <SimulationAnalyticsTab />}
          {activeTab === 13 && <STTBugReportTabComponent />}
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

// LangGraph 탭 (관리자 전용)
function LangGraphTab() {
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)
  const getInitialBaseUrl = () => {
    if (typeof window === 'undefined') {
      return 'http://127.0.0.1:2024'
    }
    return localStorage.getItem('langgraphStudioBaseUrl') || 'http://127.0.0.1:2024'
  }
  const [studioBaseUrl, setStudioBaseUrl] = useState(getInitialBaseUrl)

  useEffect(() => {
    if (typeof window === 'undefined') return
    localStorage.setItem('langgraphStudioBaseUrl', studioBaseUrl)
  }, [studioBaseUrl])

  const openStudio = () => {
    if (!studioBaseUrl) {
      alert('LangGraph Studio base URL을 먼저 입력해주세요.')
      return
    }
    const studioUrl = `https://smith.langchain.com/studio/?baseUrl=${encodeURIComponent(studioBaseUrl)}`
    window.open(studioUrl, '_blank', 'noopener,noreferrer')
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">LangGraph 아키텍처</h2>
          <p className="mt-1 text-sm text-gray-600">
            멀티 에이전트 시스템의 구조 시각화와 LangGraph Studio 연동을 한 곳에서 관리합니다.
          </p>
        </div>
      </div>

      {/* LangGraph Studio Section */}
      <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div>
            <h3 className="text-xl font-semibold text-gray-900">LANGGRAPH 2 Studio</h3>
            <p className="text-sm text-gray-600">
              LangSmith Studio를 통해 그래프 실행을 실시간으로 모니터링하고 디버깅할 수 있습니다.
            </p>
          </div>
          <button
            onClick={openStudio}
            className="inline-flex items-center px-4 py-2 rounded-lg bg-primary-600 text-white hover:bg-primary-700 transition-colors"
          >
            LangGraph Studio 열기
          </button>
        </div>

        <div className="mt-4 grid gap-4 md:grid-cols-[1fr_auto]">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              LangGraph Studio baseUrl
            </label>
            <input
              type="text"
              value={studioBaseUrl}
              onChange={(e) => setStudioBaseUrl(e.target.value)}
              placeholder="https://<tunnel-host>.app"
              className="w-full rounded-lg border border-gray-300 px-3 py-2 focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
            />
            <p className="mt-1 text-xs text-gray-500">
              `langgraph dev --tunnel` 실행 후 콘솔에 출력된 HTTPS 주소를 입력하세요.
            </p>
          </div>
        </div>

        <div className="mt-6 bg-gray-50 rounded-xl p-4 border border-gray-200">
          <h4 className="text-sm font-semibold text-gray-800 mb-2 flex items-center gap-2">
            <InformationCircleIcon className="w-4 h-4 text-primary-600" />
            LangSmith Studio 접속 절차
          </h4>
          <ol className="list-decimal list-inside space-y-1 text-sm text-gray-700">
            <li>도커 백엔드 컨테이너에서 자동 실행되는 `langgraph dev --host 0.0.0.0 --port 2024 --tunnel` 로그에서 HTTPS baseUrl을 확인합니다.</li>
            <li>위 baseUrl을 입력 필드에 붙여넣고 저장됩니다(브라우저 LocalStorage).</li>
            <li>LangSmith 웹 UI에서 Deployments → Studio → Connect를 선택한 뒤 동일한 baseUrl을 입력합니다.</li>
            <li>`LangGraph Studio 열기` 버튼을 클릭하거나 LangSmith UI에서 Connect를 눌러 그래프를 시각화합니다.</li>
          </ol>
          <p className="text-xs text-amber-600 mt-2">
            HTTPS가 아닌 http://127.0.0.1:2024를 사용할 경우 브라우저가 혼합 콘텐츠를 차단하여 연결에 실패할 수 있습니다.
          </p>
        </div>
      </div>

      {/* LangGraph 다이어그램 */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <LangGraphMermaidView />
      </div>

      {/* 노드 상세 정보 패널 */}
      <NodeDetailPanel
        nodeId={selectedNodeId}
        onClose={() => setSelectedNodeId(null)}
      />

      {/* 추가 정보 섹션 */}
      <div className="grid md:grid-cols-2 gap-6">
        {/* 아키텍처 설명 */}
        <div className="bg-gradient-to-br from-purple-50 to-blue-50 rounded-xl p-6 border border-purple-200">
          <h3 className="text-lg font-semibold text-gray-900 mb-3 flex items-center gap-2">
            <CpuChipIcon className="w-5 h-5 text-purple-600" />
            아키텍처 개요
          </h3>
          <div className="space-y-2 text-sm text-gray-700">
            <p>
              <strong>구조:</strong> Hierarchical + Network (하이라키 + 네트워크)
            </p>
            <p>
              <strong>특징:</strong> 멀티 에이전트 시스템으로 각 에이전트가 특화된 역할을 수행하며
              상호 협력하여 복잡한 시뮬레이션을 처리합니다.
            </p>
            <ul className="mt-2 space-y-1 ml-4 list-disc">
              <li>Orchestrator: 전체 프롬프트 및 대화 흐름 관리</li>
              <li>Processor: 시뮬레이션 및 데이터 처리</li>
              <li>Retriever: RAG 기반 문서 검색</li>
              <li>Evaluator: 성능 평가 및 피드백 생성</li>
              <li>Detector: 주제 이탈 감지</li>
              <li>Generator: 음성 및 응답 생성</li>
            </ul>
          </div>
        </div>

        {/* 사용 가이드 */}
        <div className="bg-gradient-to-br from-amber-50 to-orange-50 rounded-xl p-6 border border-amber-200">
          <h3 className="text-lg font-semibold text-gray-900 mb-3 flex items-center gap-2">
            <InformationCircleIcon className="w-5 h-5 text-amber-600" />
            사용 가이드
          </h3>
          <div className="space-y-3 text-sm text-gray-700">
            <div>
              <strong className="text-amber-800">노드 클릭:</strong>
              <p className="mt-1">
                다이어그램의 노드를 클릭하면 오른쪽 패널에 에이전트의 상세 정보가 표시됩니다.
              </p>
            </div>
            <div>
              <strong className="text-amber-800">화살표:</strong>
              <p className="mt-1">
                노드 간 화살표는 데이터 흐름을 나타냅니다. 레이블은 전달되는 데이터의 종류를 표시합니다.
              </p>
            </div>
            <div>
              <strong className="text-amber-800">색상:</strong>
              <p className="mt-1">
                각 노드의 색상은 에이전트 타입을 나타냅니다 (보라색=오케스트레이터, 파란색=프로세서 등).
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* LangSmith 연동 정보 */}
      <div className="bg-blue-50 border border-blue-200 rounded-xl p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-3 flex items-center gap-2">
          <ChartBarIcon className="w-5 h-5 text-blue-600" />
          LangSmith 추적
        </h3>
        <p className="text-sm text-gray-700 mb-3">
          실시간 에이전트 실행 추적 및 디버깅 기능이 곧 추가될 예정입니다.
        </p>
        <div className="flex items-center gap-2 text-sm">
          <CheckCircleIcon className="w-5 h-5 text-green-600" />
          <span className="text-gray-700">
            LangSmith API 키가 구성되어 있습니다.
          </span>
        </div>
      </div>
    </div>
  )
}

// 테스트 평가서 탭 (관리자 전용)
function TestFeedbackTab() {
  const navigate = useNavigate()
  const [feedbackHistory, setFeedbackHistory] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [currentPage, setCurrentPage] = useState(1)
  const itemsPerPage = 10

  useEffect(() => {
    loadTestFeedbackHistory()
  }, [])

  const loadTestFeedbackHistory = async () => {
    try {
      setLoading(true)
      // 테스트 모드 평가서만 조회 (is_test_mode=true)
      console.log('🔍 테스트 평가서 히스토리 조회 시작...')
      const response = await api.get('/rag-simulation/feedback-history?limit=100&is_test_mode=true')
      console.log('📥 API 응답:', response.data)
      const allData = response.data.history || []
      console.log(`✅ 테스트 평가서 히스토리 로드 완료: ${allData.length}개`)
      
      // 디버깅: 각 평가서의 is_test_mode 확인
      allData.forEach((fb: any, idx: number) => {
        console.log(`  [${idx}] 피드백 ID=${fb.id}, is_test_mode=${fb.is_test_mode}, overall_score=${fb.overall_score}, created_at=${fb.created_at}`)
      })
      
      setFeedbackHistory(allData)
    } catch (error: any) {
      console.error('❌ 테스트 평가서 히스토리 로드 실패:', error)
      console.error('   상세:', error.response?.data || error.message)
    } finally {
      setLoading(false)
    }
  }

  const viewFeedbackDetail = async (feedbackId: number) => {
    try {
      const response = await api.get(`/rag-simulation/feedback/${feedbackId}`)
      navigate('/simulation-feedback', {
        state: { 
          feedbackData: response.data.feedback,
          fromHistory: true
        }
      })
    } catch (error) {
      console.error('테스트 평가서 상세 조회 실패:', error)
      alert('평가서를 불러올 수 없습니다.')
    }
  }

  const getGrade = (score: number) => {
    if (score >= 90) return 'A+'
    if (score >= 85) return 'A'
    if (score >= 80) return 'B+'
    if (score >= 75) return 'B'
    if (score >= 70) return 'C+'
    if (score >= 65) return 'C'
    if (score >= 60) return 'D'
    return 'F'
  }

  const getGradeColor = (grade: string) => {
    switch (grade) {
      case 'A+': return 'text-green-600 bg-green-50'
      case 'A': return 'text-green-600 bg-green-50'
      case 'B+': return 'text-blue-600 bg-blue-50'
      case 'B': return 'text-blue-600 bg-blue-50'
      case 'C+': return 'text-yellow-600 bg-yellow-50'
      case 'C': return 'text-yellow-600 bg-yellow-50'
      case 'D': return 'text-orange-600 bg-orange-50'
      case 'F': return 'text-red-600 bg-red-50'
      default: return 'text-gray-600 bg-gray-50'
    }
  }

  const formatDate = (dateString: string) => {
    const date = new Date(dateString)
    return date.toLocaleDateString('ko-KR', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  const totalPages = Math.ceil(feedbackHistory.length / itemsPerPage)
  const startIndex = (currentPage - 1) * itemsPerPage
  const endIndex = startIndex + itemsPerPage
  const currentFeedbacks = feedbackHistory.slice(startIndex, endIndex)

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">테스트 평가서</h2>
          <p className="text-gray-600 mt-1">테스트 모드 시뮬레이션 평가서만 표시됩니다.</p>
        </div>
        <button
          onClick={loadTestFeedbackHistory}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
        >
          새로고침
        </button>
      </div>

      {loading ? (
        <div className="text-center py-12">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          <p className="mt-4 text-gray-600">로딩 중...</p>
        </div>
      ) : feedbackHistory.length === 0 ? (
        <div className="text-center py-12 bg-gray-50 rounded-lg">
          <p className="text-gray-500">테스트 평가서가 없습니다.</p>
        </div>
      ) : (
        <>
          <div className="bg-white rounded-lg shadow-sm border border-gray-200">
            <div className="divide-y divide-gray-200">
              {currentFeedbacks.map((feedback: any, index: number) => {
                const grade = getGrade(feedback.overall_score)
                return (
                  <div
                    key={feedback.id || index}
                    className="p-6 hover:bg-gray-50 transition-colors cursor-pointer"
                    onClick={() => viewFeedbackDetail(feedback.id)}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-3 mb-2">
                          <span className={`px-3 py-1 rounded-full text-sm font-semibold ${getGradeColor(grade)}`}>
                            {grade}
                          </span>
                          <span className="text-lg font-semibold text-gray-900">
                            {feedback.overall_score.toFixed(1)}점
                          </span>
                          {feedback.is_test_mode && (
                            <span className="px-2 py-1 bg-purple-100 text-purple-700 rounded text-xs font-medium">
                              🧪 테스트 모드
                            </span>
                          )}
                        </div>
                        <div className="text-sm text-gray-600 space-y-1">
                          {feedback.persona_info && (
                            <p>고객: {feedback.persona_info}</p>
                          )}
                          {feedback.situation_info && (
                            <p>상황: {feedback.situation_info}</p>
                          )}
                          {feedback.total_turns && (
                            <p>대화 턴: {feedback.total_turns}턴</p>
                          )}
                        </div>
                        <p className="text-xs text-gray-400 mt-2">
                          {formatDate(feedback.created_at)}
                        </p>
                      </div>
                      <div className="ml-4">
                        <button className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm">
                          상세보기
                        </button>
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>

          {/* 페이지네이션 */}
          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-2">
              <button
                onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
                disabled={currentPage === 1}
                className="px-4 py-2 border border-gray-300 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
              >
                이전
              </button>
              <span className="px-4 py-2 text-gray-700">
                {currentPage} / {totalPages}
              </span>
              <button
                onClick={() => setCurrentPage(prev => Math.min(totalPages, prev + 1))}
                disabled={currentPage === totalPages}
                className="px-4 py-2 border border-gray-300 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
              >
                다음
              </button>
            </div>
          )}
        </>
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
  const [detailUser, setDetailUser] = useState<any | null>(null)
  const [showDetail, setShowDetail] = useState(false)
  const [attemptModalUser, setAttemptModalUser] = useState<any | null>(null)
  const [attemptInfo, setAttemptInfo] = useState<any | null>(null)
  const [attemptForm, setAttemptForm] = useState({ random: '', custom: '', midterm: '', final: '' })
  const [attemptLoading, setAttemptLoading] = useState(false)
  const [attemptSaving, setAttemptSaving] = useState(false)
  const formatDate = (value: any, withTime: boolean = false) => {
    if (!value) return '-'
    try {
      const d = new Date(value)
      if (Number.isNaN(d.getTime())) return '-'
      return withTime ? d.toLocaleString() : d.toLocaleDateString()
    } catch (e) {
      return '-'
    }
  }

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

  const handleHardDelete = async (userId: number) => {
    if (!confirm('해당 사용자를 영구 삭제하시겠습니까? (복구 불가)')) return
    try {
      await adminAPI.deleteUserHard(userId)
      alert('영구 삭제되었습니다.')
      loadUsers()
    } catch (e: any) {
      alert(`삭제 실패: ${e?.response?.data?.detail || e?.message}`)
    }
  }

  const handleResetUsersToSeed = async () => {
    if (!confirm('admin, mentor1, mentor2, mentee1, mentee2를 제외하고 모든 사용자를 삭제합니다. 진행하시겠습니까?')) return
    try {
      const result = await adminAPI.resetUsersToSeed()
      alert(result.message || '사용자를 초기화했습니다.')
      loadUsers()
    } catch (e: any) {
      alert(`초기화 실패: ${e?.response?.data?.detail || e?.message}`)
    }
  }

  const summarizeAttempts = (attempts: any) => {
    if (!attempts) return '-'
    const remaining = attempts.remaining || {}
    const limits = attempts.limits || {}
    const fmt = (mode: 'random' | 'custom' | 'midterm' | 'final', label: string) =>
      `${label} ${remaining?.[mode] ?? 0}/${limits?.[mode] ?? 0}`
    return `${fmt('random', '랜')} · ${fmt('custom', '맞')} · ${fmt('midterm', '중')} · ${fmt('final', '최')}`
  }

  const handleAttemptReset = async (user: any) => {
    try {
      const data = await adminAPI.getUserQuizAttempts(user.id)
      const used = data?.used || {}
      const remaining = data?.remaining || {}
      const msg =
        `현재 사용횟수는 랜덤 ${used.random ?? 0}, 맞춤 ${used.custom ?? 0}, ` +
        `중간 ${used.midterm ?? 0}, 최종 ${used.final ?? 0}이고, 남은 횟수는 ` +
        `랜덤 ${remaining.random ?? 0}, 맞춤 ${remaining.custom ?? 0}, ` +
        `중간 ${remaining.midterm ?? 0}, 최종 ${remaining.final ?? 0} 입니다.\n` +
        `초기화 하시겠습니까? (초기값 랜덤 200, 맞춤 10, 중간 1, 최종 1)`
      if (!confirm(msg)) return
      await adminAPI.updateUserQuizAttemptLimits(user.id, { reset: true })
      loadUsers()
    } catch (err: any) {
      alert(`초기화 실패: ${err?.response?.data?.detail || err?.message}`)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-xl font-semibold text-gray-900">사용자 관리</h2>
        <div className="flex gap-2">
          <button 
            onClick={handleResetUsersToSeed}
            className="bg-red-100 text-red-700 px-4 py-2 rounded-lg hover:bg-red-200 transition-colors"
            title="admin/mentor1/mentor2/mentee1/mentee2만 남기고 삭제"
          >
            유저 초기화
          </button>
          <button className="bg-primary-600 text-white px-4 py-2 rounded-lg hover:bg-primary-700 transition-colors">
            새 사용자 추가
          </button>
        </div>
      </div>
      
      {/* 역할 서브 탭 */}
      <div className="bg-white rounded-xl border border-gray-200 p-2">
        <div className="flex flex-wrap gap-2">
          {[
            { key: '', label: '전체' },
            { key: 'admin', label: '관리자' },
            { key: 'mentor', label: '멘토' },
            { key: 'mentee', label: '멘티' },
          ].map((tab) => (
            <button
              key={tab.key}
              onClick={() => setRoleFilter(tab.key)}
              className={`px-4 py-2 rounded-lg text-sm border transition-colors ${
                roleFilter === tab.key
                  ? 'bg-primary-600 text-white border-primary-600'
                  : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>
      
      {/* 검색 및 필터 */}
      <div className="flex gap-4 items-center flex-wrap">
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
        {/* 엑셀 업로드 (역할 선택) */}
        <div className="flex items-center gap-2">
          <label htmlFor="user-upload-file" className="cursor-pointer inline-flex items-center gap-2 bg-primary-50 text-primary-700 border border-primary-200 hover:bg-primary-100 px-3 py-2 rounded-lg text-sm">
            <PaperClipIcon className="w-4 h-4" /> 파일 선택
          </label>
          <input id="user-upload-file" type="file" accept=".xlsx,.xls" className="hidden" />
          <select id="user-upload-role" className="border border-gray-300 rounded-lg px-3 py-2 text-sm">
            <option value="mentor">멘토</option>
            <option value="mentee">멘티</option>
            <option value="admin">관리자</option>
          </select>
          <button
            className="bg-primary-600 text-white px-3 py-2 rounded-lg text-sm hover:bg-primary-700"
            onClick={async () => {
              const fileInput = document.getElementById('user-upload-file') as HTMLInputElement
              const roleSelect = document.getElementById('user-upload-role') as HTMLSelectElement
              const file = fileInput?.files?.[0]
              const role = (roleSelect?.value as 'admin' | 'mentor' | 'mentee')
              if (!file) { alert('엑셀 파일을 선택해주세요 (.xlsx/.xls)'); return }
              try {
                const result = await adminAPI.uploadUsersExcel(file, role)
                alert(`업로드 완료\n생성: ${result.created_users}, 업데이트: ${result.updated_users}, 에러: ${result.error_count}`)
                loadUsers()
                fileInput.value = ''
              } catch (err: any) {
                const msg = err?.response?.data?.detail || err?.message || '업로드 실패'
                alert(`업로드 실패: ${msg}`)
              }
            }}
          >
            엑셀 업로드
          </button>
        </div>
      </div>

      {/* 사용자 목록 */}
      {loading ? (
        <div className="flex justify-center items-center h-32">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
        </div>
      ) : users.length > 0 ? (
        <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
          <div className="overflow-x-auto max-h-[720px] overflow-y-auto">
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
                      {formatDate((user as any).created_at)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium space-x-3">
                      <button
                        className="text-primary-600 hover:text-primary-900"
                        onClick={() => { setDetailUser(user); setShowDetail(true) }}
                      >
                        상세보기
                      </button>
                      <button
                        className="text-orange-600 hover:text-orange-800"
                        onClick={() => handleAttemptReset(user)}
                      >
                        횟수 초기화
                      </button>
                      <button
                        className="text-red-600 hover:text-red-800"
                        onClick={() => handleHardDelete(user.id)}
                      >
                        하드 삭제
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
      {/* 상세 모달 */}
      {showDetail && detailUser && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="bg-white rounded-xl shadow-xl p-6 max-w-lg w-full mx-4"
          >
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-xl font-bold text-gray-900">사용자 상세</h3>
              <button className="text-gray-400 hover:text-gray-600" onClick={() => setShowDetail(false)}>
                <XMarkIcon className="w-6 h-6" />
              </button>
            </div>
            <div className="space-y-2 text-sm">
              <div className="grid grid-cols-3 gap-2">
                <div className="text-gray-500">이름</div><div className="col-span-2">{detailUser.name}</div>
                <div className="text-gray-500">역할</div><div className="col-span-2">{detailUser.role}</div>
                <div className="text-gray-500">사번</div><div className="col-span-2">{detailUser.employee_number || '-'}</div>
                <div className="text-gray-500">부서</div><div className="col-span-2">{detailUser.team || '-'}</div>
                <div className="text-gray-500">직책</div><div className="col-span-2">{detailUser.position || '-'}</div>
                <div className="text-gray-500">연락처</div><div className="col-span-2">{detailUser.phone || '-'}</div>
                <div className="text-gray-500">이메일</div><div className="col-span-2">{detailUser.email || '-'}</div>
                <div className="text-gray-500">가입일</div><div className="col-span-2">{formatDate(detailUser.created_at, true)}</div>
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-6">
              <button className="px-4 py-2 text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200" onClick={() => setShowDetail(false)}>닫기</button>
              <button className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700" onClick={() => handleHardDelete(detailUser.id)}>하드 삭제</button>
            </div>
          </motion.div>
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
  const [cohortId, setCohortId] = useState<string>('')
  const [mode, setMode] = useState<string>('')
  const [cohorts, setCohorts] = useState<Array<{id: number, date: string, label: string, count: number}>>([])

  useEffect(() => {
    loadCohorts()
  }, [])

  useEffect(() => {
    loadHistory()
  }, [userId, startDate, endDate, cohortId, mode])

  const loadCohorts = async () => {
    try {
      const response = await adminAPI.getCohorts()
      setCohorts(response.cohorts || [])
    } catch (error) {
      console.error('기수 목록 로드 실패:', error)
    }
  }

  const loadHistory = async () => {
    try {
      setLoading(true)
      const response = await adminAPI.getLearningHistory(
        userId ? parseInt(userId) : undefined,
        startDate || undefined,
        endDate || undefined,
        cohortId ? parseInt(cohortId) : undefined,
        mode || undefined
      )
      setHistory(response.history || [])
    } catch (error) {
      console.error('학습 이력 로드 실패:', error)
      setHistory([])
    } finally {
      setLoading(false)
    }
  }

  const handleSeedPreQuiz = async () => {
    if (!confirm('모든 멘티/멘토 시험 성적(초기·중간·최종)을 자동 생성합니다.\n이미 존재하는 성적은 유지됩니다. 계속하시겠습니까?')) return
    try {
      setLoading(true)
      const res = await adminAPI.seedPreQuizHistory()
      alert(res.message || '성적 생성이 완료되었습니다.')
      loadHistory()
    } catch (error: any) {
      alert(error?.response?.data?.detail || error?.message || '생성 실패')
    } finally {
      setLoading(false)
    }
  }

  const modeLabel = (mode: string) => {
    switch (mode) {
      case 'pre': return '초기'
      case 'midterm': return '중간'
      case 'final': return '최종'
      case 'random': return '랜덤'
      case 'custom': return '맞춤'
      default: return mode
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
            <button
              className="bg-amber-500 text-white px-4 py-2 rounded-lg hover:bg-amber-600 transition-colors"
              onClick={handleSeedPreQuiz}
            >
              성적 생성
            </button>
          </div>
        </div>
      
      {/* 필터 */}
      <div className="flex gap-4 flex-wrap">
        <input
          type="number"
          placeholder="사용자 ID (선택사항)"
          value={userId}
          onChange={(e) => setUserId(e.target.value)}
          className="border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-primary-500 focus:border-transparent"
        />
        <select
          value={cohortId}
          onChange={(e) => setCohortId(e.target.value)}
          className="border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-primary-500 focus:border-transparent"
        >
          <option value="">전체 기수</option>
          {cohorts.map((cohort) => (
            <option key={cohort.id} value={cohort.id.toString()}>
              {cohort.label}
            </option>
          ))}
        </select>
        <select
          value={mode}
          onChange={(e) => setMode(e.target.value)}
          className="border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-primary-500 focus:border-transparent"
        >
          <option value="">전체 모드</option>
          <option value="pre">초기</option>
          <option value="midterm">중간</option>
          <option value="final">최종</option>
          <option value="random">랜덤</option>
          <option value="custom">맞춤</option>
        </select>
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
          <div className="overflow-x-auto max-h-[720px] overflow-y-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">일시</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">기수</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">사용자 ID</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">사용자 이름</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">모드</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">문항수</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">총점</th>
                  {[
                    '금융영업',
                    '상품개발 및 운용',
                    '신용분석 및 리스크관리',
                    '외환',
                    '은행지식 및 관련법률',
                    '하경은행',
                  ].map((cat) => (
                    <th key={cat} className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      {cat}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {history.map((item: any, index: number) => (
                  <tr key={index} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {item.created_at
                        ? new Date(
                            (typeof item.created_at === 'string'
                              ? item.created_at
                              : item.created_at.toString()) + (item.created_at.includes?.('Z') ? '' : 'Z')
                          ).toLocaleString()
                        : '-'}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {item.cohort_label || '-'}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{item.user_id}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{item.user_name}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{modeLabel(item.mode || '')}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{item.total_questions ?? 0}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {item.score != null ? Number(item.score).toFixed(1) : '0.0'}
                    </td>
                    {[
                      '금융영업',
                      '상품개발 및 운용',
                      '신용분석 및 리스크관리',
                      '외환',
                      '은행지식 및 관련법률',
                      '하경은행',
                    ].map((cat) => {
                      const stat = item.category_stats?.[cat]
                      return (
                        <td key={`${index}-${cat}`} className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                          {stat ? `${stat.correct}/${stat.total}` : '-'}
                        </td>
                      )
                    })}
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
  const [syncing, setSyncing] = useState(false)

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

  const handleSyncRag = async () => {
    if (!confirm('RAG 데이터 소스 폴더(backend/data/rag_sources)의 모든 파일을 스캔하여\n데이터베이스와 동기화합니다.\n\n- 일반 문서: document_chunks 테이블에 인덱싱\n- 상품 데이터: product_chunks 테이블에 인덱싱\n\n진행하시겠습니까?')) {
      return
    }

    try {
      setSyncing(true)
      // reindex-rag API가 이제 동기화 로직으로 변경됨
      const response = await adminAPI.reindexRag()
      
      let message = `동기화 완료!\n\n총 스캔 파일: ${response.total_files_scanned}개\n`
      if (response.general_files_count !== undefined) {
        message += `- 일반 문서: ${response.general_files_count}개 파일, ${response.processed_count}개 처리\n`
      } else {
        message += `- 일반 문서: ${response.processed_count}개 처리\n`
      }
      if (response.product_files_count !== undefined && response.product_files_count > 0) {
        message += `- 상품 데이터: ${response.product_files_count}개 파일, ${response.product_indexed_count || 0}개 청크 인덱싱\n`
      }
      
      alert(message)
      loadDocuments() // 목록 새로고침
    } catch (error: any) {
      console.error('동기화 실패:', error)
      alert(`동기화 실패: ${error.response?.data?.detail || error.message}`)
    } finally {
      setSyncing(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-xl font-semibold text-gray-900">문서 관리</h2>
        <div className="flex gap-2">
          <button 
            onClick={handleSyncRag}
            disabled={syncing}
            className="bg-amber-500 text-white px-4 py-2 rounded-lg hover:bg-amber-600 transition-colors disabled:opacity-50 flex items-center gap-2"
          >
            {syncing ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                동기화 중...
              </>
            ) : (
              <>
                <ArrowPathIcon className="w-5 h-5" />
                RAG 데이터 동기화
              </>
            )}
          </button>
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

// 연수원 연동 탭: 멘티 시험 엑셀 업로드 및 처리 결과 표시
function TrainingSyncTab() {
  type TrainingFilters = { cohortDate: string; search: string }
  type TrainingCategory = 'mentee' | 'mentor'
  const SCORE_COLUMNS = TRAINING_LEARNING_SECTIONS
  const CATEGORY_TABS: { key: TrainingCategory; label: string; description: string }[] = [
    { key: 'mentee', label: '신입 멘티', description: '연수원 기수별 신입 30명/월' },
    { key: 'mentor', label: '기존 멘토', description: '창구사무 선배 직원 풀' }
  ]

  const [records, setRecords] = useState<any[]>([])
  const [loadingRecords, setLoadingRecords] = useState(true)
  const [syncing, setSyncing] = useState(false)
  const [total, setTotal] = useState(0)
  const [totalCohorts, setTotalCohorts] = useState(0)
  const [cohortOptions, setCohortOptions] = useState<any[]>([])
  const [lastSyncedAt, setLastSyncedAt] = useState<string | null>(null)
  const [filters, setFilters] = useState<TrainingFilters>({ cohortDate: '', search: '' })
  const [selectedCohort, setSelectedCohort] = useState('')
  const [searchInput, setSearchInput] = useState('')
  const [legacyUploading, setLegacyUploading] = useState(false)
  const [legacyProcessed, setLegacyProcessed] = useState<any[]>([])
  const [legacyErrors, setLegacyErrors] = useState<string[]>([])
  const [activeCategory, setActiveCategory] = useState<TrainingCategory>('mentee')
  const [expandedRecordId, setExpandedRecordId] = useState<number | null>(null)
  const [columnFilters, setColumnFilters] = useState<Record<string, string>>({})
  const [filterDropdowns, setFilterDropdowns] = useState<Record<string, boolean>>({})
  const [selectedRecords, setSelectedRecords] = useState<Set<number>>(new Set())
  const [deleting, setDeleting] = useState(false)

  // 필터링된 레코드 계산
  const filteredRecords = records.filter((record: any) => {
    return Object.entries(columnFilters).every(([key, value]) => {
      if (!value) return true
      let recordValue: any
      if (key.startsWith('section_scores.')) {
        const sectionKey = key.replace('section_scores.', '')
        recordValue = record.section_scores?.[sectionKey]
      } else if (key === 'hobby1') {
        recordValue = [record.hobby1, record.hobby2].filter(Boolean).join(', ')
      } else {
        recordValue = record[key]
      }
      if (recordValue === null || recordValue === undefined) return false
      return String(recordValue).toLowerCase().includes(String(value).toLowerCase())
    })
  })

  // 각 컬럼의 고유값 추출 (필터 옵션용)
  const getUniqueValues = (key: string) => {
    const values = new Set<string>()
    records.forEach((record: any) => {
      let value: any
      if (key.startsWith('section_scores.')) {
        const sectionKey = key.replace('section_scores.', '')
        value = record.section_scores?.[sectionKey]
      } else if (key === 'hobby1') {
        value = [record.hobby1, record.hobby2].filter(Boolean).join(', ')
      } else {
        value = record[key]
      }
      if (value !== null && value !== undefined) {
        if (Array.isArray(value)) {
          value.forEach((v: any) => values.add(String(v)))
        } else {
          values.add(String(value))
        }
      }
    })
    return Array.from(values).sort()
  }

  const toggleFilterDropdown = (columnKey: string) => {
    setFilterDropdowns(prev => ({
      ...prev,
      [columnKey]: !prev[columnKey]
    }))
  }

  const applyColumnFilter = (columnKey: string, value: string) => {
    setColumnFilters(prev => ({
      ...prev,
      [columnKey]: value
    }))
    setFilterDropdowns(prev => ({
      ...prev,
      [columnKey]: false
    }))
  }

  const clearColumnFilter = (columnKey: string) => {
    setColumnFilters(prev => {
      const newFilters = { ...prev }
      delete newFilters[columnKey]
      return newFilters
    })
  }

  const loadRecords = useCallback(async (filterState: TrainingFilters, category: TrainingCategory) => {
    setLoadingRecords(true)
    try {
      const fetcher = category === 'mentee' ? adminAPI.getTrainingCenterMentees : adminAPI.getTrainingCenterMentors
      // 전체 데이터를 한 번에 로드 (페이지네이션 없음)
      const data = await fetcher({
        page: 1,
        pageSize: 10000,
        cohortDate: filterState.cohortDate || undefined,
        search: filterState.search || undefined
      })
      setRecords(data.records || [])
      setTotal(data.total || 0)
      setTotalCohorts(data.total_cohorts || 0)
      setCohortOptions(data.cohorts || [])
      setLastSyncedAt(data.last_synced_at || null)
    } catch (error) {
      console.error('연수원 데이터 로드 실패:', error)
    } finally {
      setLoadingRecords(false)
    }
  }, [columnFilters])

  useEffect(() => {
    loadRecords(filters, activeCategory)
  }, [filters, activeCategory, loadRecords])

  // 필터가 변경되면 데이터 다시 로드
  useEffect(() => {
    loadRecords(filters, activeCategory)
  }, [columnFilters])

  const handleSync = async () => {
    if (selectedCohorts.size === 0) {
      alert('생성할 기수를 최소 1개 이상 선택해주세요.')
      return
    }

    if (!createMentees && !createMentors) {
      alert('멘티 또는 멘토 중 최소 하나는 선택해야 합니다.')
      return
    }
    
    try {
      setSyncing(true)
      const result = await adminAPI.syncTrainingCenterData({
        selected_cohort_dates: Array.from(selectedCohorts),
        create_accounts: true,  // 항상 계정 자동 생성
        create_mentees: createMentees,
        create_mentors: createMentors,
      })
      alert(`연수원 DB 재생성 완료\n신입 ${result.generated_mentees}명 / 멘토 ${result.generated_mentors}명\n계정 ${result.created_accounts || 0}개 생성됨`)
      await loadRecords(filters, activeCategory)
      // 옵션 초기화
      setSelectedCohorts(new Set())
      setCreateMentees(true)
      setCreateMentors(true)
    } catch (error: any) {
      const detail = error?.response?.data?.detail || error?.message || '동기화 실패'
      alert(detail)
    } finally {
      setSyncing(false)
    }
  }

  const toggleSelectRecord = (recordId: number) => {
    setSelectedRecords(prev => {
      const newSet = new Set(prev)
      if (newSet.has(recordId)) {
        newSet.delete(recordId)
      } else {
        newSet.add(recordId)
      }
      return newSet
    })
  }

  const toggleSelectAll = () => {
    const displayedRecords = Object.keys(columnFilters).length > 0 ? filteredRecords : records
    if (selectedRecords.size === displayedRecords.length) {
      setSelectedRecords(new Set())
    } else {
      setSelectedRecords(new Set(displayedRecords.map((r: any) => r.id)))
    }
  }

  const handleDeleteSelected = async () => {
    if (selectedRecords.size === 0) {
      alert('삭제할 레코드를 선택해주세요.')
      return
    }

    if (!confirm(`선택한 ${selectedRecords.size}개의 레코드를 삭제하시겠습니까?`)) {
      return
    }

    try {
      setDeleting(true)
      const result = await adminAPI.deleteTrainingCenterRecords(Array.from(selectedRecords))
      alert(result.message)
      setSelectedRecords(new Set())
      await loadRecords(filters, activeCategory)
    } catch (error: any) {
      const detail = error?.response?.data?.detail || error?.message || '삭제 실패'
      alert(detail)
    } finally {
      setDeleting(false)
    }
  }

  const handleDeleteAll = async () => {
    if (!confirm(
      '⚠️ 전체 연수원 데이터를 완전히 삭제하시겠습니까?\n\n' +
      '삭제되는 항목 (하드 삭제):\n' +
      '✅ 연수원 레코드 (멘티/멘토 데이터)\n' +
      '✅ 연수원 기수 정보\n' +
      '✅ 매칭 결과 및 리포트\n' +
      '✅ 연수원으로 생성된 User 계정\n' +
      '✅ 시험 점수 (ExamScore)\n' +
      '✅ 멘토-멘티 관계\n' +
      '✅ 채팅 기록\n' +
      '✅ 피드백\n' +
      '✅ 시뮬레이션 녹화\n' +
      '✅ 퀴즈 기록\n' +
      '✅ 기타 모든 사용자 활동 기록\n\n' +
      '⚠️ 주의: 이 작업은 되돌릴 수 없습니다!'
    )) {
      return
    }

    try {
      setDeleting(true)
      const result = await adminAPI.deleteAllTrainingCenterRecords()
      alert(result.message)
      setSelectedRecords(new Set())
      await loadRecords(filters, activeCategory)
    } catch (error: any) {
      const detail = error?.response?.data?.detail || error?.message || '삭제 실패'
      alert(detail)
    } finally {
      setDeleting(false)
    }
  }

  const applyFilters = () => {
    setFilters({
      cohortDate: selectedCohort,
      search: searchInput.trim()
    })
  }

  const resetFilters = () => {
    setSelectedCohort('')
    setSearchInput('')
    setFilters({ cohortDate: '', search: '' })
  }

  const formatDate = (value?: string) => {
    if (!value) return '-'
    return new Date(value).toLocaleDateString('ko-KR', { year: 'numeric', month: 'long', day: 'numeric' })
  }

  const formatDateTime = (value?: string | null) => {
    if (!value) return '-'
    return new Date(value).toLocaleString('ko-KR', { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
  }

  // DB 생성 옵션 상태
  const [selectedCohorts, setSelectedCohorts] = useState<Set<string>>(new Set())
  const [createMentees, setCreateMentees] = useState(true)
  const [createMentors, setCreateMentors] = useState(true)
  const [initializingDemo, setInitializingDemo] = useState(false)

  // 원클릭 데모 초기화
  const handleInitializeDemo = async () => {
    if (!confirm(
      '🚀 데모 데이터 초기화\n\n' +
      '다음 작업이 수행됩니다:\n' +
      '1. 기존 데이터 전체 삭제 (관리자 계정 제외)\n' +
      '2. 1~3기 완수 데이터 로드 (시드 데이터)\n' +
      '3. 4기 진행 중 데이터 생성 (멘티 30명, 멘토 15명)\n' +
      '4. 4기 자동 매칭 실행\n\n' +
      '⚠️ 기존 데이터가 모두 삭제됩니다. 계속하시겠습니까?'
    )) {
      return
    }

    try {
      setInitializingDemo(true)
      const result = await adminAPI.initializeDemo()
      
      const stats = result.stats
      const cohort4 = stats?.cohort_4 || {}
      const matching = stats?.matching || {}
      
      alert(
        '✅ 데모 데이터 초기화 완료!\n\n' +
        `📊 1~3기 시드 데이터 로드: ${result.cohorts_loaded?.length || 0}개 기수\n` +
        `👥 4기 생성: 멘티 ${cohort4.mentees || 0}명, 멘토 ${cohort4.mentors || 0}명\n` +
        `🔗 매칭 완료: ${matching.matched_count || 0}쌍`
      )
      
      await loadRecords(filters, activeCategory)
    } catch (error: any) {
      const detail = error?.response?.data?.detail || error?.message || '초기화 실패'
      alert(`데모 초기화 실패: ${detail}`)
    } finally {
      setInitializingDemo(false)
    }
  }

  // 기수 옵션 정의 (체크박스용)
  const cohortCheckboxOptions = [
    { label: '2025년 1기', date: '2025-01-01' },
    { label: '2025년 2기', date: '2025-04-01' },
    { label: '2025년 3기', date: '2025-07-01' },
    { label: '2025년 4기', date: '2025-10-01' },
  ]

  const toggleCohort = (date: string) => {
    setSelectedCohorts(prev => {
      const newSet = new Set(prev)
      if (newSet.has(date)) {
        newSet.delete(date)
      } else {
        newSet.add(date)
      }
      return newSet
    })
  }

  const showScoreColumns = false
  const totalLabel = activeCategory === 'mentee' ? '총 신입 멘티' : '총 멘토'

  const handleLegacyUpload = async () => {
    const fileInput = document.getElementById('training-upload-file') as HTMLInputElement
    const file = fileInput?.files?.[0]
    if (!file) { alert('연수원 시험 엑셀 파일을 선택해주세요 (.xlsx/.xls)'); return }
    try {
      setLegacyUploading(true)
      const result = await adminAPI.uploadMenteeExamExcel(file)
      setLegacyProcessed(result.processed || [])
      setLegacyErrors(result.errors || [])
      alert(`업로드 완료\n처리: ${result.processed_count}, 에러: ${(result.errors||[]).length}`)
      fileInput.value = ''
    } catch (err: any) {
      const msg = err?.response?.data?.detail || err?.message || '업로드 실패'
      alert(`업로드 실패: ${msg}`)
    } finally {
      setLegacyUploading(false)
    }
  }

  const legacyTotalFormatter = (scores: any) => {
    return SCORE_COLUMNS.map((key) => scores?.[key] || 0).reduce((acc, cur) => acc + cur, 0)
  }

  // 통계 계산
  const menteeCount = records.filter((r: any) => r.employee_type === 'mentee').length
  const mentorCount = records.filter((r: any) => r.employee_type === 'mentor').length
  const genderStats = {
    남성: records.filter((r: any) => r.gender === '남성').length,
    여성: records.filter((r: any) => r.gender === '여성').length,
  }
  const avgScore = '0'

  return (
    <div className="space-y-6">
      {/* 🚀 원클릭 데모 초기화 섹션 */}
      <div className="bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500 rounded-2xl p-6 text-white shadow-xl">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <h2 className="text-2xl font-bold flex items-center gap-2">
              🚀 데모 데이터 초기화
            </h2>
            <p className="text-white/90 mt-2">
              원클릭으로 1~3기 완수 데이터 + 4기 진행 중 데이터를 생성합니다.
            </p>
            <div className="mt-3 flex flex-wrap gap-2 text-sm">
              <span className="bg-white/20 px-3 py-1 rounded-full">✅ 1~3기: 완수 상태 (퀴즈/시뮬레이션 이력 포함)</span>
              <span className="bg-white/20 px-3 py-1 rounded-full">🔄 4기: 진행 중 (0~4회 학습)</span>
              <span className="bg-white/20 px-3 py-1 rounded-full">🔗 자동 매칭</span>
            </div>
          </div>
          <button
            onClick={handleInitializeDemo}
            disabled={initializingDemo || syncing || deleting}
            className="flex-shrink-0 bg-white text-purple-600 font-bold px-8 py-4 rounded-xl hover:bg-purple-50 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-lg hover:shadow-xl transform hover:scale-105"
          >
            {initializingDemo ? (
              <span className="flex items-center gap-2">
                <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                초기화 중...
              </span>
            ) : (
              '🚀 원클릭 초기화'
            )}
          </button>
        </div>
        <p className="text-xs text-white/70 mt-4">
          최근 재생성: {formatDateTime(lastSyncedAt)}
        </p>
      </div>

      <div className="flex flex-col gap-4">
        <div className="flex flex-col gap-4">
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
            <div>
              <h2 className="text-xl font-semibold text-gray-900">연수원 데이터 조회</h2>
              <p className="text-sm text-gray-600 mt-1">생성된 멘티/멘토 데이터를 조회하고 관리합니다.</p>
            </div>
            <div className="flex gap-2 items-center">
              <button
                onClick={handleDeleteSelected}
                disabled={syncing || deleting || selectedRecords.size === 0 || initializingDemo}
                className="inline-flex items-center justify-center bg-orange-600 text-white px-4 py-2 rounded-lg hover:bg-orange-700 disabled:opacity-50"
              >
                {deleting ? '삭제 중...' : `선택 삭제 (${selectedRecords.size})`}
              </button>
            </div>
          </div>
        </div>

        {/* 요약 통계 */}
        {records.length > 0 && (
          <div className="grid md:grid-cols-4 gap-4">
            <div className="bg-white border border-gray-200 rounded-xl p-4">
              <p className="text-sm text-gray-500">전체 인원</p>
              <p className="text-2xl font-bold text-gray-900 mt-1">{records.length}명</p>
              <div className="flex gap-4 mt-2 text-xs text-gray-600">
                <span>멘티: {menteeCount}명</span>
                <span>멘토: {mentorCount}명</span>
              </div>
            </div>
            <div className="bg-white border border-gray-200 rounded-xl p-4">
              <p className="text-sm text-gray-500">성별 분포</p>
              <div className="flex gap-4 mt-2">
                <div>
                  <p className="text-lg font-bold text-blue-600">{genderStats.남성}명</p>
                  <p className="text-xs text-gray-600">남성</p>
                </div>
                <div>
                  <p className="text-lg font-bold text-pink-600">{genderStats.여성}명</p>
                  <p className="text-xs text-gray-600">여성</p>
                </div>
              </div>
            </div>
            <div className="bg-white border border-gray-200 rounded-xl p-4">
              <p className="text-sm text-gray-500">평균 시험 점수</p>
              <p className="text-2xl font-bold text-primary-600 mt-1">{avgScore}점</p>
            </div>
            <div className="bg-white border border-gray-200 rounded-xl p-4">
              <p className="text-sm text-gray-500">기수 수</p>
              <p className="text-2xl font-bold text-gray-900 mt-1">{totalCohorts}개</p>
            </div>
          </div>
        )}

        <div className="flex flex-wrap gap-3">
          {CATEGORY_TABS.map(({ key, label, description }) => (
            <button
              key={key}
              onClick={() => {
                setActiveCategory(key)
                setSelectedCohort('')
                setSearchInput('')
                setFilters({ cohortDate: '', search: '' })
              }}
              className={`flex-1 min-w-[140px] rounded-lg border px-4 py-3 text-left transition ${
                activeCategory === key
                  ? 'border-primary-500 bg-primary-50 text-primary-700'
                  : 'border-gray-200 bg-white text-gray-700 hover:border-primary-200'
              }`}
            >
              <p className="font-semibold">{label}</p>
              <p className="text-xs text-gray-500 mt-1">{description}</p>
            </button>
          ))}
        </div>
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        <div className="bg-white border border-gray-200 rounded-xl p-4">
          <p className="text-sm text-gray-500">{totalLabel}</p>
          <p className="text-2xl font-bold text-gray-900 mt-1">{total.toLocaleString()}명</p>
        </div>
        <div className="bg-white border border-gray-200 rounded-xl p-4">
          <p className="text-sm text-gray-500">총 기수</p>
          <p className="text-2xl font-bold text-gray-900 mt-1">{totalCohorts.toLocaleString()}기</p>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 p-4 space-y-4">
        <div className="flex flex-col md:flex-row gap-3">
          <input
            type="text"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            placeholder="이름 또는 사번 검색"
            className="flex-1 border border-gray-300 rounded-lg px-4 py-2 focus:ring-2 focus:ring-primary-500 focus:border-transparent"
          />
          <select
            value={selectedCohort}
            onChange={(e) => {
              setSelectedCohort(e.target.value)
              setFilters({
                cohortDate: e.target.value,
                search: searchInput.trim()
              })
            }}
            className="w-full md:w-64 border border-gray-300 rounded-lg px-4 py-2 focus:ring-2 focus:ring-primary-500 focus:border-transparent"
          >
            <option value="">전체 기수</option>
            {cohortOptions.map((cohort: any) => (
              <option key={cohort.date} value={cohort.date}>
                {cohort.label} ({cohort.count || 0}명)
              </option>
            ))}
          </select>
        </div>
        <div className="flex gap-2 justify-end">
          <button
            onClick={resetFilters}
            className="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50"
          >
            초기화
          </button>
          <button
            onClick={applyFilters}
            className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700"
          >
            검색 적용
          </button>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        {loadingRecords ? (
          <div className="flex flex-col items-center justify-center py-16">
            <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-primary-600 mb-4"></div>
            <p className="text-gray-500">연수원 데이터를 불러오는 중입니다...</p>
          </div>
        ) : records.length === 0 ? (
          <div className="text-center py-16">
            <p className="text-gray-500">표시할 연수원 데이터가 없습니다.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    <input
                      type="checkbox"
                      checked={selectedRecords.size > 0 && selectedRecords.size === (Object.keys(columnFilters).length > 0 ? filteredRecords : records).length}
                      onChange={toggleSelectAll}
                      className="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                    />
                  </th>
                  {[
                    { key: 'cohort_label', label: '기수' },
                    { key: 'cohort_date', label: '수료일' },
                    { key: 'name', label: '이름' },
                    { key: 'employee_number', label: '사번' },
                    { key: 'gender', label: '성별' },
                    { key: 'birth', label: '생년월일' },
                    { key: 'email', label: '이메일' },
                    { key: 'phone', label: '전화번호' },
                    { key: 'join_year', label: '입행연도' },
                    { key: 'city', label: '거주지' },
                    { key: 'hobby1', label: '취미' },
                    { key: 'major', label: '전공' },
                    { key: 'career_goal', label: '커리어목표' },
                    { key: 'team', label: '팀' },
                    { key: 'mbti', label: 'MBTI' },
                    { key: 'position', label: '직급' },
                    // 점수/상세 컬럼 제거
                  ].map(({ key, label, noFilter }) => (
                    <th key={key} className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider relative">
                      <div className="flex items-center justify-between">
                        <span>{label}</span>
                        {!noFilter && (
                          <div className="relative">
                            <button
                              onClick={() => toggleFilterDropdown(key)}
                              className={`ml-2 p-1 rounded hover:bg-gray-200 ${columnFilters[key] ? 'text-primary-600' : 'text-gray-400'}`}
                              title="필터"
                            >
                              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z" />
                              </svg>
                            </button>
                            {filterDropdowns[key] && (
                              <div className="absolute right-0 mt-1 w-48 bg-white rounded-md shadow-lg z-10 border border-gray-200">
                                <div className="p-2">
                                  <input
                                    type="text"
                                    placeholder="검색..."
                                    value={columnFilters[key] || ''}
                                    onChange={(e) => applyColumnFilter(key, e.target.value)}
                                    className="w-full px-2 py-1 text-sm border border-gray-300 rounded"
                                    autoFocus
                                  />
                                  <div className="mt-2 max-h-48 overflow-y-auto">
                                    {getUniqueValues(key).slice(0, 20).map((value) => (
                                      <button
                                        key={value}
                                        onClick={() => applyColumnFilter(key, value)}
                                        className={`w-full text-left px-2 py-1 text-sm hover:bg-gray-100 ${
                                          columnFilters[key] === value ? 'bg-primary-50 text-primary-700' : ''
                                        }`}
                                      >
                                        {value}
                                      </button>
                                    ))}
                                  </div>
                                  {columnFilters[key] && (
                                    <button
                                      onClick={() => clearColumnFilter(key)}
                                      className="w-full mt-2 px-2 py-1 text-sm text-red-600 hover:bg-red-50 rounded"
                                    >
                                      필터 제거
                                    </button>
                                  )}
                                </div>
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {filteredRecords.map((record: any) => {
                  const isExpanded = expandedRecordId === record.id
                  return (
                    <tr key={record.id} className="hover:bg-gray-50">
                        <td className="px-4 py-2 whitespace-nowrap text-sm">
                          <input
                            type="checkbox"
                            checked={selectedRecords.has(record.id)}
                            onChange={() => toggleSelectRecord(record.id)}
                            className="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                          />
                        </td>
                    <td className="px-4 py-2 whitespace-nowrap text-sm text-gray-900">{record.cohort_label}</td>
                    <td className="px-4 py-2 whitespace-nowrap text-sm text-gray-700">{formatDate(record.cohort_date)}</td>
                    <td className="px-4 py-2 whitespace-nowrap text-sm font-semibold text-gray-900">{record.name}</td>
                    <td className="px-4 py-2 whitespace-nowrap text-sm text-gray-700">{record.employee_number}</td>
                        <td className="px-4 py-2 whitespace-nowrap text-sm text-gray-700">{record.gender || '-'}</td>
                        <td className="px-4 py-2 whitespace-nowrap text-sm text-gray-700">
                          {record.birth ? formatDate(record.birth) : '-'}
                        </td>
                        <td className="px-4 py-2 whitespace-nowrap text-sm text-gray-700">
                          {record.email || '-'}
                        </td>
                        <td className="px-4 py-2 whitespace-nowrap text-sm text-gray-700">
                          {record.phone || '-'}
                        </td>
                    <td className="px-4 py-2 whitespace-nowrap text-sm text-gray-700">{record.join_year}</td>
                    <td className="px-4 py-2 whitespace-nowrap text-sm text-gray-700">{record.city}</td>
                        <td className="px-4 py-2 whitespace-nowrap text-sm text-gray-700">
                          {[record.hobby1, record.hobby2].filter(Boolean).join(', ') || '-'}
                        </td>
                        <td className="px-4 py-2 whitespace-nowrap text-sm text-gray-700">{record.major || '-'}</td>
                        <td className="px-4 py-2 whitespace-nowrap text-sm text-gray-700">{record.career_goal || '-'}</td>
                    <td className="px-4 py-2 whitespace-nowrap text-sm text-gray-700">{record.team}</td>
                    <td className="px-4 py-2 whitespace-nowrap text-sm text-gray-700">{record.mbti}</td>
                    <td className="px-4 py-2 whitespace-nowrap text-sm text-gray-700">{record.position}</td>
                    {/* 점수/상세 컬럼 제거 */}
                  </tr>
              )
            })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {Object.keys(columnFilters).some(key => columnFilters[key]) && (
        <div className="flex items-center justify-center gap-2 text-sm text-gray-600">
          <span>필터 적용 중: {filteredRecords.length}개 결과 표시</span>
          <button
            onClick={() => {
              setColumnFilters({})
            }}
            className="px-3 py-1 text-primary-600 hover:text-primary-800 underline"
          >
            필터 모두 제거
          </button>
        </div>
      )}
      {records.length > 0 && (
        <div className="text-center text-sm text-gray-500">
          총 {records.length}개 레코드 표시 중
        </div>
      )}

      <div className="bg-white border border-amber-200 rounded-xl p-4">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-2">
          <div>
            <h3 className="text-lg font-semibold text-amber-800">레거시 엑셀 업로드 (테스트)</h3>
            <p className="text-sm text-amber-600">기존 엑셀 업로드 경로도 유지하고 싶을 때 사용하세요.</p>
          </div>
          <div className="flex items-center gap-3">
            <label htmlFor="training-upload-file" className="cursor-pointer inline-flex items-center gap-2 bg-amber-50 text-amber-700 border border-amber-200 hover:bg-amber-100 px-3 py-2 rounded-lg text-sm">
              <PaperClipIcon className="w-4 h-4" /> Excel 선택
            </label>
            <input id="training-upload-file" type="file" accept=".xlsx,.xls" className="hidden" />
            <button
              onClick={handleLegacyUpload}
              disabled={legacyUploading}
              className="bg-amber-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-amber-700 disabled:opacity-50"
            >
              {legacyUploading ? '업로드 중...' : '업로드 실행'}
            </button>
          </div>
        </div>

        <div className="mt-4 overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200 text-sm">
            <thead className="bg-amber-50">
              <tr>
                <th className="px-4 py-2 text-left font-semibold text-amber-800">이름</th>
                <th className="px-4 py-2 text-left font-semibold text-amber-800">사번</th>
                {SCORE_COLUMNS.map((label) => (
                  <th key={`legacy-${label}`} className="px-4 py-2 text-left font-semibold text-amber-800">{label}</th>
                ))}
                <th className="px-4 py-2 text-left font-semibold text-amber-800">총점(60)</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {legacyProcessed.map((p: any, idx: number) => (
                <tr key={idx}>
                  <td className="px-4 py-2">{p.name}</td>
                  <td className="px-4 py-2">{p.employee_number}</td>
                  {SCORE_COLUMNS.map((label) => (
                    <td key={`legacy-${idx}-${label}`} className="px-4 py-2">{p.scores?.[label] || 0}</td>
                  ))}
                  <td className="px-4 py-2 font-semibold text-amber-700">{legacyTotalFormatter(p.scores)}</td>
                </tr>
              ))}
              {legacyProcessed.length === 0 && (
                <tr>
                  <td className="px-4 py-6 text-center text-gray-500" colSpan={SCORE_COLUMNS.length + 3}>
                    업로드된 엑셀 데이터가 없습니다.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {legacyErrors.length > 0 && (
          <div className="mt-4 bg-red-50 border border-red-200 rounded-lg p-4">
            <h4 className="font-semibold text-red-800 mb-2">오류 {legacyErrors.length}건</h4>
            <ul className="text-sm text-red-700 list-disc pl-5 space-y-1 max-h-36 overflow-auto">
              {legacyErrors.map((e, i) => (<li key={i}>{e}</li>))}
            </ul>
          </div>
        )}
      </div>
    </div>
  )
}

// 매칭 시스템 탭
function MatchingTab() {
  const [matching, setMatching] = useState(false)
  const [report, setReport] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const [showScoringModal, setShowScoringModal] = useState(false)
  const [showWeightFormulaModal, setShowWeightFormulaModal] = useState(false)

  const runMatching = async () => {
    if (!confirm('매칭을 실행하시겠습니까? 기존 매칭 결과는 비활성화됩니다.')) {
      return
    }
    try {
      setMatching(true)
      const result = await adminAPI.runMatching()
      alert(`매칭 완료!\n매칭된 쌍: ${result.matched_count}개\n전체 평균 점수: ${(result.overall_score * 100).toFixed(1)}%`)
      await loadReport()
    } catch (error: any) {
      const msg = error?.response?.data?.detail || error?.message || '매칭 실패'
      alert(`매칭 실패: ${msg}`)
    } finally {
      setMatching(false)
    }
  }

  const loadReport = async () => {
    setLoading(true)
    try {
      const data = await adminAPI.getMatchingReport()
      setReport(data)
    } catch (error: any) {
      if (error?.response?.status !== 404) {
        console.error('리포트 로드 실패:', error)
      }
      setReport(null)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadReport()
  }, [])

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h2 className="text-xl font-semibold text-gray-900">멘토-멘티 매칭 시스템</h2>
            <p className="text-sm text-gray-600 mt-1">N차원 분류 기반 매칭 (팀 &gt; 약점-강점 &gt; 커리어 &gt; 거주지 &gt; 취미 &gt; 전공)</p>
        </div>
        <button
          onClick={runMatching}
          disabled={matching}
          className="inline-flex items-center justify-center bg-primary-600 text-white px-4 py-2 rounded-lg hover:bg-primary-700 disabled:opacity-50"
        >
          {matching ? '매칭 중...' : '매칭 실행'}
        </button>
      </div>

      {loading ? (
        <div className="flex flex-col items-center justify-center py-16">
          <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-primary-600 mb-4"></div>
          <p className="text-gray-500">리포트를 불러오는 중입니다...</p>
        </div>
      ) : !report ? (
        <div className="text-center py-16 bg-white rounded-xl border border-gray-200">
          <p className="text-gray-500">매칭 리포트가 없습니다. 매칭을 실행해주세요.</p>
        </div>
      ) : (
        <>
          {/* 전체 통계 */}
          <div className="grid md:grid-cols-4 gap-4">
            <div className="bg-white border border-gray-200 rounded-xl p-4">
              <p className="text-sm text-gray-500">전체 멘티</p>
              <p className="text-2xl font-bold text-gray-900 mt-1">{report.total_mentees}명</p>
            </div>
            <div className="bg-white border border-gray-200 rounded-xl p-4">
              <p className="text-sm text-gray-500">전체 멘토</p>
              <p className="text-2xl font-bold text-gray-900 mt-1">{report.total_mentors}명</p>
            </div>
            <div className="bg-white border border-gray-200 rounded-xl p-4">
              <p className="text-sm text-gray-500">매칭된 쌍</p>
              <p className="text-2xl font-bold text-gray-900 mt-1">{report.total_matched}개</p>
            </div>
            <div className="bg-white border border-gray-200 rounded-xl p-4">
              <div className="flex items-center justify-between">
                <p className="text-sm text-gray-500">전체 평균 점수</p>
                <button
                  onClick={() => setShowWeightFormulaModal(true)}
                  className="text-primary-600 hover:text-primary-800 cursor-pointer"
                  title="가중치 계산식 보기"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 7h6m0 10v-3m-3 3h.01M9 17h.01M9 14h.01M12 14h.01M15 11h.01M12 11h.01M9 11h.01M7 21h10a2 2 0 002-2V5a2 2 0 00-2-2H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
                  </svg>
                </button>
              </div>
              <p className="text-2xl font-bold text-primary-600 mt-1">{(report.overall_score * 100).toFixed(1)}%</p>
            </div>
          </div>

          {/* 팀별 통계 */}
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <div className="px-6 py-4 bg-gray-50 border-b border-gray-200">
              <h3 className="text-lg font-semibold text-gray-900">팀별 매칭 통계</h3>
            </div>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">팀</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">매칭 수</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">평균 전체 점수</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                      <div className="flex items-center gap-1">
                        <span>팀</span>
                        <button
                          onClick={() => setShowScoringModal(true)}
                          className="text-primary-600 hover:text-primary-800 cursor-pointer"
                          title="팀 매칭 점수 산정 방식 보기"
                        >
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                          </svg>
                        </button>
                      </div>
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">약점-강점</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">커리어</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">거주지</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">취미</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">전공</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {Object.entries(report.team_statistics || {}).map(([team, stats]: [string, any]) => (
                    <tr key={team} className="hover:bg-gray-50">
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{team}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-700">{stats.matched_count}개</td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-bold text-primary-600">
                        {(stats.average_total_score * 100).toFixed(1)}%
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-700">
                        {(stats.average_team_score * 100).toFixed(1)}%
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-700">
                        {((stats.average_weakness_strength_score || 0) * 100).toFixed(1)}%
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-700">
                        {((stats.average_career_score || 0) * 100).toFixed(1)}%
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-700">
                        {(stats.average_city_score * 100).toFixed(1)}%
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-700">
                        {(stats.average_hobby_score * 100).toFixed(1)}%
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-700">
                        {((stats.average_major_score || 0) * 100).toFixed(1)}%
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* 시각화 보고서 */}
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <div className="px-6 py-4 bg-gray-50 border-b border-gray-200">
              <h3 className="text-lg font-semibold text-gray-900">매칭 점수 시각화</h3>
              <p className="text-sm text-gray-600 mt-1">각 피처별 매칭 점수 분포</p>
            </div>
            <div className="p-6 space-y-6">
              {/* 피처별 점수 분포 바 차트 */}
              <div className="space-y-4">
                <h4 className="font-medium text-gray-900">피처별 평균 점수</h4>
                {[
                  { label: '팀', key: 'team_score', color: 'bg-blue-500' },
                  { label: '약점-강점 보완', key: 'weakness_strength_score', color: 'bg-purple-500' },
                  { label: '커리어 목표', key: 'career_score', color: 'bg-green-500' },
                  { label: '거주지', key: 'city_score', color: 'bg-yellow-500' },
                  { label: '취미', key: 'hobby_score', color: 'bg-pink-500' },
                  { label: '전공', key: 'major_score', color: 'bg-indigo-500' },
                ].map(({ label, key, color }) => {
                  const avgScore = report.matches?.reduce((sum: number, m: any) => sum + (m[key] || 0), 0) / (report.matches?.length || 1)
                  const percentage = (avgScore * 100).toFixed(1)
                  return (
                    <div key={key} className="space-y-2">
                      <div className="flex justify-between items-center">
                        <span className="text-sm font-medium text-gray-700">{label}</span>
                        <span className="text-sm font-bold text-gray-900">{percentage}%</span>
                      </div>
                      <div className="w-full bg-gray-200 rounded-full h-3">
                        <div
                          className={`h-3 rounded-full ${color} transition-all duration-500`}
                          style={{ width: `${percentage}%` }}
                        ></div>
                      </div>
                    </div>
                  )
                })}
              </div>

              {/* 전체 점수 분포 히스토그램 */}
              <div className="space-y-4 pt-6 border-t border-gray-200">
                <h4 className="font-medium text-gray-900">매칭 점수 분포</h4>
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart
                    data={[
                      {
                        range: '0-20%',
                        count: report.matches?.filter((m: any) => {
                          const score = m.total_score || 0
                          return score >= 0 && score < 0.2
                        }).length || 0
                      },
                      {
                        range: '20-40%',
                        count: report.matches?.filter((m: any) => {
                          const score = m.total_score || 0
                          return score >= 0.2 && score < 0.4
                        }).length || 0
                      },
                      {
                        range: '40-60%',
                        count: report.matches?.filter((m: any) => {
                          const score = m.total_score || 0
                          return score >= 0.4 && score < 0.6
                        }).length || 0
                      },
                      {
                        range: '60-80%',
                        count: report.matches?.filter((m: any) => {
                          const score = m.total_score || 0
                          return score >= 0.6 && score < 0.8
                        }).length || 0
                      },
                      {
                        range: '80-100%',
                        count: report.matches?.filter((m: any) => {
                          const score = m.total_score || 0
                          return score >= 0.8 && score <= 1.0
                        }).length || 0
                      }
                    ]}
                    margin={{ top: 20, right: 30, left: 20, bottom: 5 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis 
                      dataKey="range" 
                      tick={{ fontSize: 12, fill: '#6B7280' }}
                      stroke="#9CA3AF"
                    />
                    <YAxis 
                      tick={{ fontSize: 12, fill: '#6B7280' }}
                      stroke="#9CA3AF"
                      label={{ value: '매칭 수', angle: -90, position: 'insideLeft', style: { textAnchor: 'middle', fill: '#6B7280' } }}
                    />
                    <Tooltip 
                      contentStyle={{ 
                        backgroundColor: 'rgba(255, 255, 255, 0.95)', 
                        border: 'none', 
                        borderRadius: '8px',
                        boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)',
                        padding: '12px'
                      }}
                      formatter={(value: number) => [`${value}개`, '매칭 수']}
                    />
                    <Bar 
                      dataKey="count" 
                      fill="#3B82F6"
                      radius={[8, 8, 0, 0]}
                    >
                      {[
                        '#EF4444', // 0-20%: 빨간색
                        '#F97316', // 20-40%: 주황색
                        '#EAB308', // 40-60%: 노란색
                        '#84CC16', // 60-80%: 연두색
                        '#22C55E'  // 80-100%: 초록색
                      ].map((color, index) => (
                        <Cell key={`cell-${index}`} fill={color} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>

          {/* 매칭 상세 목록 */}
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <div className="px-6 py-4 bg-gray-50 border-b border-gray-200">
              <h3 className="text-lg font-semibold text-gray-900">매칭 상세 목록</h3>
            </div>
            <div className="overflow-x-auto max-h-96">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50 sticky top-0">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">멘티</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">멘티 팀</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">멘토</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">멘토 팀</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">전체 점수</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">팀</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">약점-강점</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">커리어</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">거주지</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">취미</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">전공</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {report.matches?.map((match: any, idx: number) => (
                    <tr key={idx} className="hover:bg-gray-50">
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900">
                        {match.mentee_name} ({match.mentee_employee_number})
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-700">{match.mentee_team}</td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900">
                        {match.mentor_name} ({match.mentor_employee_number})
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-700">{match.mentor_team}</td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm font-bold text-primary-600">
                        {(match.total_score * 100).toFixed(1)}%
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-700">
                        {(match.team_score * 100).toFixed(0)}%
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-700">
                        {((match.weakness_strength_score || 0) * 100).toFixed(0)}%
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-700">
                        {((match.career_score || 0) * 100).toFixed(0)}%
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-700">
                        {(match.city_score * 100).toFixed(0)}%
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-700">
                        {(match.hobby_score * 100).toFixed(0)}%
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-700">
                        {((match.major_score || 0) * 100).toFixed(0)}%
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {/* 가중치 계산식 모달 */}
      {showWeightFormulaModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50" onClick={() => setShowWeightFormulaModal(false)}>
          <div className="bg-white rounded-xl shadow-xl max-w-3xl w-full mx-4 max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
              <h3 className="text-lg font-semibold text-gray-900">매칭 점수 가중치 계산식</h3>
              <button
                onClick={() => setShowWeightFormulaModal(false)}
                className="text-gray-400 hover:text-gray-600"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="px-6 py-4 space-y-6">
              <div className="space-y-3">
                <h4 className="font-semibold text-gray-900">가중치 설정</h4>
                <div className="bg-gray-50 rounded-lg p-4 space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-gray-700">팀 매칭</span>
                    <span className="font-semibold text-blue-700">가중치 3.0</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-700">약점-강점 보완</span>
                    <span className="font-semibold text-gray-600">가중치 2.0</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-700">커리어 목표</span>
                    <span className="font-semibold text-gray-600">가중치 1.5</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-700">거주지</span>
                    <span className="font-semibold text-gray-600">가중치 1.0</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-700">취미</span>
                    <span className="font-semibold text-gray-600">가중치 0.8</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-700">전공</span>
                    <span className="font-semibold text-gray-600">가중치 0.5</span>
                  </div>
                </div>
              </div>

              <div className="space-y-3">
                <h4 className="font-semibold text-gray-900">계산식</h4>
                <div className="bg-blue-50 rounded-lg p-4">
                  <p className="text-sm font-mono text-gray-800 mb-2">
                    전체 점수 = (팀점수 × 3.0 + 약점강점점수 × 2.0 + 커리어점수 × 1.5 + 거주지점수 × 1.0 + 취미점수 × 0.8 + 전공점수 × 0.5) / (3.0 + 2.0 + 1.5 + 1.0 + 0.8 + 0.5)
                  </p>
                  <p className="text-xs text-gray-600 mt-2">
                    총 가중치 합계: 8.8
                  </p>
                </div>
              </div>

              <div className="space-y-3">
                <h4 className="font-semibold text-gray-900">점수 범위</h4>
                <div className="bg-yellow-50 rounded-lg p-4 text-sm text-gray-700">
                  <p className="mb-2">각 피처별 점수는 0.0 ~ 1.0 사이의 값입니다:</p>
                  <ul className="list-disc list-inside space-y-1 ml-2">
                    <li><span className="font-semibold">팀 점수:</span> 같은 팀이면 1.0, 다르면 0.0</li>
                    <li><span className="font-semibold">약점-강점 점수:</span> 멘티 약점 분야에서 멘토가 잘하는 정도 (0.0 ~ 1.0)</li>
                    <li><span className="font-semibold">커리어 점수:</span> 같은 목표면 1.0, 다르면 0.0</li>
                    <li><span className="font-semibold">거주지 점수:</span> 같은 거주지면 1.0, 다르면 0.0</li>
                    <li><span className="font-semibold">취미 점수:</span> 공통 취미 비율 (0.0 ~ 1.0)</li>
                    <li><span className="font-semibold">전공 점수:</span> 같은 전공이면 1.0, 다르면 0.0</li>
                  </ul>
                </div>
              </div>

              <div className="space-y-3">
                <h4 className="font-semibold text-gray-900">예시 계산</h4>
                <div className="bg-green-50 rounded-lg p-4 text-sm text-gray-700">
                  <p className="mb-2"><span className="font-semibold">예시:</span> 모든 피처가 100% 일치하는 경우</p>
                  <p className="font-mono text-xs mb-2">
                    전체 점수 = (1.0 × 3.0 + 1.0 × 2.0 + 1.0 × 1.5 + 1.0 × 1.0 + 1.0 × 0.8 + 1.0 × 0.5) / 8.8
                  </p>
                  <p className="font-mono text-xs mb-2">
                    = (3.0 + 2.0 + 1.5 + 1.0 + 0.8 + 0.5) / 8.8
                  </p>
                  <p className="font-mono text-xs font-semibold">
                    = 8.8 / 8.8 = 1.0 (100%)
                  </p>
                </div>
              </div>
            </div>
            <div className="px-6 py-4 border-t border-gray-200 flex justify-end">
              <button
                onClick={() => setShowWeightFormulaModal(false)}
                className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors"
              >
                확인
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 팀 매칭 점수 산정 방식 모달 */}
      {showScoringModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50" onClick={() => setShowScoringModal(false)}>
          <div className="bg-white rounded-xl shadow-xl max-w-2xl w-full mx-4 max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
              <h3 className="text-lg font-semibold text-gray-900">팀 매칭 점수 산정 방식</h3>
              <button
                onClick={() => setShowScoringModal(false)}
                className="text-gray-400 hover:text-gray-600"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="px-6 py-4 space-y-4">
              <div className="space-y-3">
                <h4 className="font-semibold text-gray-900">기본 원칙</h4>
                <p className="text-sm text-gray-700">
                  팀 매칭은 가장 높은 우선순위를 가지며, 같은 팀의 멘토-멘티를 우선적으로 매칭합니다.
                </p>
              </div>

              <div className="space-y-3">
                <h4 className="font-semibold text-gray-900">점수 산정 방식</h4>
                <div className="bg-gray-50 rounded-lg p-4 space-y-2">
                  <div className="flex items-start gap-3">
                    <div className="flex-shrink-0 w-8 h-8 bg-green-100 rounded-full flex items-center justify-center text-green-700 font-bold text-sm">
                      ✓
                    </div>
                    <div>
                      <p className="font-medium text-gray-900">같은 팀 매칭</p>
                      <p className="text-sm text-gray-600">멘티와 멘토가 같은 팀인 경우: <span className="font-semibold text-green-600">100% (1.0점)</span></p>
                    </div>
                  </div>
                  <div className="flex items-start gap-3">
                    <div className="flex-shrink-0 w-8 h-8 bg-red-100 rounded-full flex items-center justify-center text-red-700 font-bold text-sm">
                      ✗
                    </div>
                    <div>
                      <p className="font-medium text-gray-900">다른 팀 매칭</p>
                      <p className="text-sm text-gray-600">멘티와 멘토가 다른 팀인 경우: <span className="font-semibold text-red-600">0% (0.0점)</span></p>
                    </div>
                  </div>
                </div>
              </div>

              <div className="space-y-3">
                <h4 className="font-semibold text-gray-900">가중치 시스템</h4>
                <div className="bg-blue-50 rounded-lg p-4">
                  <p className="text-sm text-gray-700 mb-3">
                    팀 매칭은 전체 매칭 점수 계산 시 <span className="font-bold text-blue-700">가중치 10.0</span>을 적용받습니다.
                  </p>
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-gray-700">팀 매칭</span>
                      <span className="font-semibold text-blue-700">가중치 10.0</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-700">약점-강점 보완</span>
                      <span className="font-semibold text-gray-600">가중치 0.8</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-700">커리어 목표</span>
                      <span className="font-semibold text-gray-600">가중치 0.7</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-700">거주지</span>
                      <span className="font-semibold text-gray-600">가중치 0.6</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-700">취미</span>
                      <span className="font-semibold text-gray-600">가중치 0.4</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-700">전공</span>
                      <span className="font-semibold text-gray-600">가중치 0.3</span>
                    </div>
                  </div>
                </div>
              </div>

              <div className="space-y-3">
                <h4 className="font-semibold text-gray-900">매칭 우선순위</h4>
                <div className="space-y-2 text-sm text-gray-700">
                  <p>1. <span className="font-semibold">팀 매칭</span> - 같은 팀 우선 (가장 중요)</p>
                  <p>2. 약점-강점 보완 - 멘티의 약점 분야를 멘토가 잘하는지</p>
                  <p>3. 커리어 목표 - 같은 목표 지향</p>
                  <p>4. 거주지 - 가까운 지역</p>
                  <p>5. 취미 - 공통 관심사</p>
                  <p>6. 전공 - 같은 학문 배경</p>
                </div>
              </div>

              <div className="space-y-3 pt-4 border-t border-gray-200">
                <h4 className="font-semibold text-gray-900">예시</h4>
                <div className="bg-yellow-50 rounded-lg p-4 text-sm text-gray-700">
                  <p className="mb-2"><span className="font-semibold">시나리오:</span> 멘티 A (창구영업1팀)를 매칭할 때</p>
                  <ul className="list-disc list-inside space-y-1 ml-2">
                    <li>멘토 B (창구영업1팀, 다른 피처 50% 일치) → <span className="font-semibold text-green-600">우선 매칭</span></li>
                    <li>멘토 C (VIP창구팀, 다른 피처 100% 일치) → <span className="font-semibold text-red-600">후순위</span></li>
                  </ul>
                  <p className="mt-2 text-xs text-gray-600">
                    * 팀이 다르면 다른 피처가 완벽하게 일치해도 팀이 같은 경우보다 낮은 점수가 나옵니다.
                  </p>
                </div>
              </div>
            </div>
            <div className="px-6 py-4 border-t border-gray-200 flex justify-end">
              <button
                onClick={() => setShowScoringModal(false)}
                className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors"
              >
                확인
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// 멘티 EDA 탭
function MenteeEDATab() {
  const [records, setRecords] = useState<any[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadMenteeData()
  }, [])

  const loadMenteeData = async () => {
    try {
      setLoading(true)
      // 모든 멘티 데이터 가져오기 (페이징 없이)
      const response = await adminAPI.getTrainingCenterMentees({ page: 1, pageSize: 10000 })
      setRecords(response.records || [])
    } catch (error: any) {
      console.error('멘티 데이터 로드 실패:', error)
      setRecords([])
    } finally {
      setLoading(false)
    }
  }

  // 각 피처별 분포 계산
  const calculateDistribution = (key: string) => {
    const distribution: Record<string, number> = {}
    records.forEach((record: any) => {
      let value: any
      if (key === 'hobby') {
        value = [record.hobby1, record.hobby2].filter(Boolean).join(', ')
        if (!value) value = '없음'
      } else {
        value = record[key] || '없음'
      }
      distribution[value] = (distribution[value] || 0) + 1
    })
    return Object.entries(distribution)
      .map(([label, count]) => ({ label, count, percentage: (count / records.length) * 100 }))
      .sort((a, b) => b.count - a.count)
  }

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-16">
        <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-primary-600 mb-4"></div>
        <p className="text-gray-500">멘티 데이터를 불러오는 중입니다...</p>
      </div>
    )
  }

  if (records.length === 0) {
    return (
      <div className="text-center py-16 bg-white rounded-xl border border-gray-200">
        <p className="text-gray-500">멘티 데이터가 없습니다.</p>
      </div>
    )
  }

  const features = [
    { key: 'gender', label: '성별', color: 'bg-cyan-500' },
    { key: 'major', label: '전공', color: 'bg-blue-500' },
    { key: 'career_goal', label: '커리어 목표', color: 'bg-green-500' },
    { key: 'city', label: '거주지', color: 'bg-yellow-500' },
    { key: 'hobby', label: '취미', color: 'bg-pink-500' },
    { key: 'team', label: '팀', color: 'bg-purple-500' },
    { key: 'mbti', label: 'MBTI', color: 'bg-indigo-500' },
  ]

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold text-gray-900">멘티 데이터 탐색적 분석 (EDA)</h2>
        <p className="text-sm text-gray-600 mt-1">총 {records.length}명의 멘티 데이터 분석</p>
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        {features.map(({ key, label, color }) => {
          const distribution = calculateDistribution(key)
          const maxCount = Math.max(...distribution.map(d => d.count), 1)

          return (
            <div key={key} className="bg-white rounded-xl border border-gray-200 overflow-hidden">
              <div className="px-6 py-4 bg-gray-50 border-b border-gray-200">
                <h3 className="text-lg font-semibold text-gray-900">{label} 분포</h3>
              </div>
              <div className="p-6 space-y-3">
                {distribution.slice(0, 10).map(({ label: itemLabel, count, percentage }) => (
                  <div key={itemLabel} className="space-y-1">
                    <div className="flex justify-between items-center">
                      <span className="text-sm font-medium text-gray-700 truncate flex-1">{itemLabel}</span>
                      <span className="text-sm font-bold text-gray-900 ml-2">{count}명 ({percentage.toFixed(1)}%)</span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-2">
                      <div
                        className={`h-2 rounded-full ${color} transition-all duration-500`}
                        style={{ width: `${(count / maxCount) * 100}%` }}
                      ></div>
                    </div>
                  </div>
                ))}
                {distribution.length > 10 && (
                  <p className="text-xs text-gray-500 text-center pt-2">
                    외 {distribution.length - 10}개 항목...
                  </p>
                )}
              </div>
            </div>
          )
        })}
      </div>

      {/* 입사년도 및 연령 분석 */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="px-6 py-4 bg-gray-50 border-b border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900">입사년도 및 연령 분석</h3>
        </div>
        <div className="p-6">
          <div className="grid md:grid-cols-2 gap-6">
            {/* 입사년도별 분포 */}
            <div className="space-y-4">
              <h4 className="font-semibold text-gray-900">입사년도별 분포</h4>
              {(() => {
                const yearDist = calculateDistribution('join_year')
                const maxCount = Math.max(...yearDist.map(d => d.count), 1)
                return yearDist.map(({ label, count, percentage }) => (
                  <div key={label} className="space-y-1">
                    <div className="flex justify-between items-center">
                      <span className="text-sm font-medium text-gray-700">{label}년</span>
                      <span className="text-sm font-bold text-gray-900">{count}명 ({percentage.toFixed(1)}%)</span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-2">
                      <div
                        className="h-2 rounded-full bg-indigo-500 transition-all duration-500"
                        style={{ width: `${(count / maxCount) * 100}%` }}
                      ></div>
                    </div>
                  </div>
                ))
              })()}
            </div>

            {/* 연령대 분포 */}
            <div className="space-y-4">
              <h4 className="font-semibold text-gray-900">연령대 분포</h4>
              {(() => {
                const ageGroups: Record<string, number> = {}
                const currentYear = new Date().getFullYear()
                records.forEach((record: any) => {
                  if (record.birth) {
                    const birthYear = new Date(record.birth).getFullYear()
                    const age = currentYear - birthYear
                    let ageGroup = ''
                    if (age < 25) ageGroup = '24세 이하'
                    else if (age < 30) ageGroup = '25-29세'
                    else if (age < 35) ageGroup = '30-34세'
                    else if (age < 40) ageGroup = '35-39세'
                    else ageGroup = '40세 이상'
                    ageGroups[ageGroup] = (ageGroups[ageGroup] || 0) + 1
                  }
                })
                const ageDist = Object.entries(ageGroups)
                  .map(([label, count]) => ({ label, count, percentage: (count / records.length) * 100 }))
                  .sort((a, b) => {
                    const order = ['24세 이하', '25-29세', '30-34세', '35-39세', '40세 이상']
                    return order.indexOf(a.label) - order.indexOf(b.label)
                  })
                const maxCount = Math.max(...ageDist.map(d => d.count), 1)
                return ageDist.map(({ label, count, percentage }) => (
                  <div key={label} className="space-y-1">
                    <div className="flex justify-between items-center">
                      <span className="text-sm font-medium text-gray-700">{label}</span>
                      <span className="text-sm font-bold text-gray-900">{count}명 ({percentage.toFixed(1)}%)</span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-2">
                      <div
                        className="h-2 rounded-full bg-teal-500 transition-all duration-500"
                        style={{ width: `${(count / maxCount) * 100}%` }}
                      ></div>
                    </div>
                  </div>
                ))
              })()}
            </div>
          </div>
        </div>
      </div>

      {/* 시험 점수 분석 */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="px-6 py-4 bg-gray-50 border-b border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900">시험 점수 분석</h3>
        </div>
        <div className="p-6">
          <div className="grid md:grid-cols-3 gap-4 mb-6">
            <div className="bg-blue-50 rounded-lg p-4">
              <p className="text-sm text-gray-600">평균 총점</p>
              <p className="text-2xl font-bold text-blue-700">
                {(records.reduce((sum, r) => sum + (r.total_score || 0), 0) / records.length).toFixed(1)}점
              </p>
            </div>
            <div className="bg-green-50 rounded-lg p-4">
              <p className="text-sm text-gray-600">최고 점수</p>
              <p className="text-2xl font-bold text-green-700">
                {Math.max(...records.map(r => r.total_score || 0))}점
              </p>
            </div>
            <div className="bg-red-50 rounded-lg p-4">
              <p className="text-sm text-gray-600">최저 점수</p>
              <p className="text-2xl font-bold text-red-700">
                {Math.min(...records.map(r => r.total_score || 0))}점
              </p>
            </div>
          </div>

          <div className="space-y-4">
            <h4 className="font-semibold text-gray-900">카테고리별 평균 점수</h4>
            {TRAINING_LEARNING_SECTIONS.map((category) => {
              const avgScore = records.reduce((sum, r) => {
                return sum + (r.section_scores?.[category] || 0)
              }, 0) / records.length

              return (
                <div key={category} className="space-y-1">
                  <div className="flex justify-between items-center">
                    <span className="text-sm font-medium text-gray-700">{category}</span>
                    <span className="text-sm font-bold text-gray-900">{avgScore.toFixed(1)}점</span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-3">
                    <div
                      className="h-3 rounded-full bg-primary-500 transition-all duration-500"
                      style={{ width: `${(avgScore / 10) * 100}%` }}
                    ></div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </div>
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

type ToastMessage = { type: 'success' | 'error'; text: string } | null

// 챗봇 설정 탭
function ChatbotSettingsTab() {
  const [config, setConfig] = useState<any>(null)
  const syncFormWithConfig = (data: any) => ({
    selected_model: data?.selected_model || 'openai',
    openai_model: data?.openai_model || 'gpt-4o-mini',
    qwen_model: data?.qwen_model || 'qwen2.5-7b-instruct',
    qwen_api_base: data?.qwen_api_base || '',
    qwen_api_key: '',
    temperature: data?.temperature ?? 0.2,
    max_tokens: data?.max_tokens ?? 800,
    top_k: data?.top_k ?? 6,
    response_style: data?.response_style || 'structured',
    verbosity: data?.verbosity || 'concise',
  })
  const [form, setForm] = useState({
    selected_model: 'openai',
    openai_model: 'gpt-4o-mini',
    qwen_model: 'qwen2.5-7b-instruct',
    qwen_api_base: '',
    qwen_api_key: '',
    temperature: 0.2,
    max_tokens: 800,
    top_k: 6,
    response_style: 'structured',
    verbosity: 'concise',
  })
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<ToastMessage>(null)
  const [resetQwenKey, setResetQwenKey] = useState(false)

  useEffect(() => {
    loadConfig()
  }, [])

  const loadConfig = async () => {
    try {
      setLoading(true)
      const data = await adminAPI.getChatbotConfig()
      setConfig(data)
      setForm(syncFormWithConfig(data))
      setResetQwenKey(false)
    } catch (error) {
      console.error('챗봇 설정 로드 실패:', error)
      setMessage({ type: 'error', text: '설정 정보를 불러오지 못했습니다.' })
    } finally {
      setLoading(false)
    }
  }

  const handleSave = async () => {
    try {
      setSaving(true)
      setMessage(null)

      const payload: any = {
        selected_model: form.selected_model,
        openai_model: form.openai_model.trim(),
        qwen_model: form.qwen_model.trim(),
        qwen_api_base: form.qwen_api_base.trim(),
        temperature: form.temperature,
        max_tokens: form.max_tokens,
        top_k: form.top_k,
        response_style: form.response_style,
        verbosity: form.verbosity,
      }

      if (resetQwenKey) {
        payload.qwen_api_key = ''
      } else if (form.qwen_api_key.trim()) {
        payload.qwen_api_key = form.qwen_api_key.trim()
      }

      const updated = await adminAPI.updateChatbotConfig(payload)
      setConfig(updated)
      setForm(syncFormWithConfig(updated))
      setResetQwenKey(false)
      setMessage({ type: 'success', text: '챗봇 설정을 저장했습니다.' })
    } catch (error: any) {
      console.error('챗봇 설정 저장 실패:', error)
      const detail = error?.response?.data?.detail
      setMessage({
        type: 'error',
        text: detail || '설정 저장 중 오류가 발생했습니다.',
      })
    } finally {
      setSaving(false)
    }
  }

  const providerOptions = config?.provider_options || ['openai', 'qwen_local']
  const responseStyleOptions = config?.response_style_options || ['structured', 'narrative']
  const verbosityOptions = config?.verbosity_options || ['concise', 'detailed']

  const renderMessage = () => {
    if (!message) return null
    const baseClass =
      message.type === 'success'
        ? 'bg-green-50 border border-green-200 text-green-800'
        : 'bg-red-50 border border-red-200 text-red-800'
    return (
      <div className={`${baseClass} px-4 py-3 rounded-lg flex items-center justify-between`}>
        <span>{message.text}</span>
        <button onClick={() => setMessage(null)} className="text-sm underline">
          닫기
        </button>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-gray-900 flex items-center gap-2">
          <ChatBubbleLeftRightIcon className="w-6 h-6 text-primary-600" />
          챗봇 모델 설정
        </h2>
        <div className="flex gap-2">
          <button
            onClick={loadConfig}
            className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors"
            disabled={loading}
          >
            새로고침
          </button>
          <button
            onClick={handleSave}
            className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors disabled:opacity-50"
            disabled={saving || loading}
          >
            {saving ? '저장 중...' : '설정 저장'}
          </button>
        </div>
      </div>

      {renderMessage()}

      {loading ? (
        <div className="flex justify-center items-center h-40">
          <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-primary-600"></div>
        </div>
      ) : (
        <div className="grid lg:grid-cols-2 gap-6">
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 space-y-4">
            <h3 className="text-lg font-semibold text-gray-900">모델 선택</h3>
            <div className="space-y-3">
              <label className="block text-sm font-medium text-gray-700">기본 제공자</label>
              <select
                value={form.selected_model}
                onChange={(e) =>
                  setForm((prev) => ({ ...prev, selected_model: e.target.value as 'openai' | 'qwen_local' }))
                }
                className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-primary-500 focus:border-primary-500"
              >
                {providerOptions.map((option: string) => (
                  <option key={option} value={option}>
                    {option === 'openai' ? 'OpenAI (GPT)' : '로컬 Qwen'}
                  </option>
                ))}
              </select>

              <div className="space-y-2">
                <label className="block text-sm font-medium text-gray-700">OpenAI 모델명</label>
                <input
                  type="text"
                  value={form.openai_model}
                  onChange={(e) =>
                    setForm((prev) => ({ ...prev, openai_model: e.target.value }))
                  }
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-primary-500 focus:border-primary-500"
                  placeholder="예: gpt-4o-mini"
                />
                <p className="text-xs text-gray-500">
                  OpenAI API Key는 서버 환경 변수 OPENAI_API_KEY로 관리됩니다.
                </p>
              </div>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700">Qwen 모델명</label>
                  <input
                    type="text"
                    value={form.qwen_model}
                    onChange={(e) =>
                      setForm((prev) => ({ ...prev, qwen_model: e.target.value }))
                    }
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-primary-500 focus:border-primary-500"
                    placeholder="예: qwen2.5-7b-instruct"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700">
                    Qwen API Base URL
                  </label>
                  <input
                    type="text"
                    value={form.qwen_api_base}
                    onChange={(e) =>
                      setForm((prev) => ({ ...prev, qwen_api_base: e.target.value }))
                    }
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-primary-500 focus:border-primary-500"
                    placeholder="예: http://localhost:8001/v1"
                  />
                </div>

                <div className="space-y-2">
                  <label className="block text-sm font-medium text-gray-700">
                    Qwen API Key (선택)
                  </label>
                  <input
                    type="password"
                    value={form.qwen_api_key}
                    onChange={(e) =>
                      setForm((prev) => ({ ...prev, qwen_api_key: e.target.value }))
                    }
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-primary-500 focus:border-primary-500"
                    placeholder={config?.has_qwen_api_key ? '저장된 Key 변경 시 입력' : '필요 시 입력'}
                  />
                  {config?.has_qwen_api_key && !form.qwen_api_key && (
                    <div className="flex items-center gap-2 text-sm text-gray-600">
                      <input
                        type="checkbox"
                        id="reset-qwen-key"
                        checked={resetQwenKey}
                        onChange={(e) => setResetQwenKey(e.target.checked)}
                      />
                      <label htmlFor="reset-qwen-key">저장된 Key 초기화</label>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>

          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 space-y-4">
            <h3 className="text-lg font-semibold text-gray-900">RAG 및 생성 파라미터</h3>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700">Temperature</label>
                <input
                  type="number"
                  min={0}
                  max={1.5}
                  step={0.05}
                  value={form.temperature}
                  onChange={(e) => {
                    const value = Number(e.target.value)
                    setForm((prev) => ({
                      ...prev,
                      temperature: Number.isNaN(value) ? prev.temperature : value,
                    }))
                  }}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-primary-500 focus:border-primary-500"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700">Max Tokens</label>
                <input
                  type="number"
                  min={100}
                  max={4096}
                  value={form.max_tokens}
                  onChange={(e) => {
                    const value = Number(e.target.value)
                    setForm((prev) => ({
                      ...prev,
                      max_tokens: Number.isNaN(value) ? prev.max_tokens : value,
                    }))
                  }}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-primary-500 focus:border-primary-500"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700">Top-K (검색 문서 수)</label>
                <input
                  type="number"
                  min={1}
                  max={20}
                  value={form.top_k}
                  onChange={(e) => {
                    const value = Number(e.target.value)
                    setForm((prev) => ({
                      ...prev,
                      top_k: Number.isNaN(value) ? prev.top_k : value,
                    }))
                  }}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-primary-500 focus:border-primary-500"
                />
              </div>

              <div className="bg-primary-50 border border-primary-100 rounded-lg p-4 text-sm text-primary-800">
                <p className="font-semibold mb-2">로컬 Qwen 모델 가이드</p>
                <ul className="list-disc list-inside space-y-1">
                  <li>
                    Hugging Face에서 <code>Qwen/Qwen2.5-7B-Instruct</code> GGUF 또는 GPTQ 모델을 다운로드하여
                    OpenAI 호환 서버(vLLM, llama.cpp, LM Studio 등)로 실행하세요.
                  </li>
                  <li>서버가 실행 중이면 Base URL에 OpenAI 호환 엔드포인트를 입력하고, 필요 시 인증 토큰을 설정하세요.</li>
                  <li>설정을 저장한 뒤 챗봇 테스트에서 모델을 전환해 결과를 비교할 수 있습니다.</li>
                </ul>
              </div>

              <div className="border-t border-gray-200 pt-4 mt-6 space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700">응답 형식</label>
                  <select
                    value={form.response_style}
                    onChange={(e) =>
                      setForm((prev) => ({ ...prev, response_style: e.target.value as 'structured' | 'narrative' }))
                    }
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-primary-500 focus:border-primary-500"
                  >
                    {responseStyleOptions.map((option: string) => (
                      <option key={option} value={option}>
                        {option === 'structured' ? '구조화(제목+불릿)' : '자연스러운 문단'}
                      </option>
                    ))}
                  </select>
                  <p className="text-xs text-gray-500 mt-1">
                    구조화 형식은 제목과 불릿/번호 목록으로 응답을 정리하고, 자연스러운 문단 형식은 서술형 답변을 제공합니다.
                  </p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700">응답 길이</label>
                  <select
                    value={form.verbosity}
                    onChange={(e) =>
                      setForm((prev) => ({ ...prev, verbosity: e.target.value as 'concise' | 'detailed' }))
                    }
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-primary-500 focus:border-primary-500"
                  >
                    {verbosityOptions.map((option: string) => (
                      <option key={option} value={option}>
                        {option === 'concise' ? '간결하게' : '상세하게'}
                      </option>
                    ))}
                  </select>
                  <p className="text-xs text-gray-500 mt-1">
                    간결 모드는 핵심 요약 중심의 짧은 답변을, 상세 모드는 배경 설명과 예시를 포함한 풍부한 답변을 생성합니다.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// 챗봇 성능 검증 탭
function ChatbotValidationTab() {
  const [testQuestion, setTestQuestion] = useState('')
  const [testResult, setTestResult] = useState<any>(null)
  const [testing, setTesting] = useState(false)
  const [stats, setStats] = useState<any>(null)
  const [loadingStats, setLoadingStats] = useState(true)
  const [testHistory, setTestHistory] = useState<any[]>([])
  const [currentConfig, setCurrentConfig] = useState<any>(null)
  
  // 청킹 설정
  const [chunkSize, setChunkSize] = useState(1000)
  const [chunkOverlap, setChunkOverlap] = useState(200)
  const [topK, setTopK] = useState(5)
  const [chunkingMethod, setChunkingMethod] = useState('fixed')
  const [embeddingModel, setEmbeddingModel] = useState('text-embedding-ada-002')
  const [temperature, setTemperature] = useState(0.7)
  const [showAdvanced, setShowAdvanced] = useState(false)

  useEffect(() => {
    loadStats()
    loadConfig()
  }, [])

  const loadStats = async () => {
    try {
      setLoadingStats(true)
      const response = await adminAPI.getChatbotStats()
      setStats(response)
    } catch (error) {
      console.error('챗봇 통계 로드 실패:', error)
    } finally {
      setLoadingStats(false)
    }
  }

  const loadConfig = async () => {
    try {
      const response = await adminAPI.getChatbotConfig()
      setCurrentConfig(response)
    } catch (error) {
      console.error('챗봇 설정 로드 실패:', error)
    }
  }

  const handleTest = async () => {
    if (!testQuestion.trim()) {
      alert('테스트 질문을 입력해주세요.')
      return
    }

    try {
      setTesting(true)
      const response = await adminAPI.testChatbotPerformance(
        testQuestion,
        chunkSize,
        chunkOverlap,
        topK,
        chunkingMethod,
        embeddingModel,
        temperature
      )
      setTestResult(response)
      
      // 테스트 히스토리에 추가
      setTestHistory([response, ...testHistory])
    } catch (error: any) {
      console.error('챗봇 테스트 실패:', error)
      alert(`테스트 실패: ${error.response?.data?.detail || error.message}`)
    } finally {
      setTesting(false)
    }
  }

  const getResponseTimeColor = (time: number) => {
    if (time < 2) return 'text-green-600'
    if (time < 5) return 'text-yellow-600'
    return 'text-red-600'
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-xl font-semibold text-gray-900">챗봇 성능 검증</h2>
        <button
          onClick={loadStats}
          className="bg-gray-100 text-gray-700 px-4 py-2 rounded-lg hover:bg-gray-200 transition-colors"
        >
          통계 새로고침
        </button>
      </div>

      {currentConfig && (
        <div className="bg-white border border-gray-200 rounded-xl p-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <p className="text-sm text-gray-500">현재 활성화된 챗봇 설정</p>
            <p className="text-lg font-semibold text-gray-900">
              {currentConfig.selected_model === 'openai' ? 'OpenAI (GPT)' : '로컬 Qwen'} ·{' '}
              {currentConfig.selected_model === 'openai'
                ? currentConfig.openai_model
                : currentConfig.qwen_model}
            </p>
          </div>
          <div className="flex flex-col sm:items-end text-sm text-gray-600">
            <span>응답 형식: {currentConfig.response_style === 'structured' ? '구조화' : '자연 문단'}</span>
            <span>응답 길이: {currentConfig.verbosity === 'concise' ? '간결' : '상세'}</span>
          </div>
        </div>
      )}

      {/* 통계 카드 */}
      <div className="grid md:grid-cols-3 gap-6">
        {loadingStats ? (
          <div className="col-span-3 flex justify-center items-center h-32">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
          </div>
        ) : stats ? (
          <>
            <div className="bg-gradient-to-br from-primary-50 to-primary-100 rounded-xl p-6 border border-primary-200">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-primary-600">총 대화 수</p>
                  <p className="text-3xl font-bold text-primary-900 mt-2">{stats.total_chats}</p>
                </div>
                <ChatBubbleBottomCenterTextIcon className="w-12 h-12 text-primary-400" />
              </div>
            </div>
            
            <div className="bg-gradient-to-br from-amber-50 to-amber-100 rounded-xl p-6 border border-amber-200">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-amber-600">일 평균 대화</p>
                  <p className="text-3xl font-bold text-amber-900 mt-2">
                    {stats.daily_stats?.length > 0 
                      ? Math.round(stats.total_chats / stats.daily_stats.length) 
                      : 0}
                  </p>
                </div>
                <ChartBarIcon className="w-12 h-12 text-amber-400" />
              </div>
            </div>
            
            <div className="bg-gradient-to-br from-green-50 to-green-100 rounded-xl p-6 border border-green-200">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-green-600">활성 사용자</p>
                  <p className="text-3xl font-bold text-green-900 mt-2">{stats.top_users?.length || 0}</p>
                </div>
                <UserIcon className="w-12 h-12 text-green-400" />
              </div>
            </div>
          </>
        ) : null}
      </div>

      {/* 테스트 섹션 */}
      <div className="bg-white rounded-xl p-6 border border-gray-200">
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-lg font-semibold text-gray-900">챗봇 응답 테스트</h3>
          <button
            onClick={() => setShowAdvanced(!showAdvanced)}
            className="text-sm text-primary-600 hover:text-primary-700 font-medium flex items-center gap-1"
          >
            {showAdvanced ? '설정 숨기기' : '고급 설정'}
            <svg className={`w-4 h-4 transition-transform ${showAdvanced ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>
        </div>
        
        {/* 청킹 & RAG 설정 */}
        {showAdvanced && (
          <div className="mb-6 p-4 bg-gradient-to-r from-blue-50 to-indigo-50 rounded-lg border border-blue-200">
            <h4 className="text-sm font-semibold text-blue-900 mb-3 flex items-center gap-2">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
              청킹 & RAG 설정
            </h4>
            <div className="grid md:grid-cols-2 gap-4">
              {/* 청킹 방식 */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  청킹 방식
                </label>
                <select
                  value={chunkingMethod}
                  onChange={(e) => setChunkingMethod(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500"
                >
                  <option value="fixed">고정 크기 (Fixed Size)</option>
                  <option value="sentence">문장 단위 (Sentence)</option>
                  <option value="semantic">의미 단위 (Semantic)</option>
                </select>
              </div>

              {/* 임베딩 모델 */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  임베딩 모델
                </label>
                <select
                  value={embeddingModel}
                  onChange={(e) => setEmbeddingModel(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500"
                >
                  <option value="text-embedding-ada-002">Ada-002 (1536D)</option>
                  <option value="text-embedding-3-small">3-Small (1536D)</option>
                  <option value="text-embedding-3-large">3-Large (3072D)</option>
                </select>
              </div>
              
              {/* 검색할 청크 수 */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  검색할 청크 수 (Top-K): <span className="text-primary-600 font-bold">{topK}</span>
                </label>
                <input
                  type="range"
                  min="1"
                  max="20"
                  value={topK}
                  onChange={(e) => setTopK(parseInt(e.target.value))}
                  className="w-full"
                />
                <div className="flex justify-between text-xs text-gray-500 mt-1">
                  <span>1</span>
                  <span>10</span>
                  <span>20</span>
                </div>
              </div>

              {/* Temperature */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Temperature: <span className="text-primary-600 font-bold">{temperature.toFixed(1)}</span>
                </label>
                <input
                  type="range"
                  min="0"
                  max="2"
                  step="0.1"
                  value={temperature}
                  onChange={(e) => setTemperature(parseFloat(e.target.value))}
                  className="w-full"
                />
                <div className="flex justify-between text-xs text-gray-500 mt-1">
                  <span>0.0 (정확)</span>
                  <span>1.0 (균형)</span>
                  <span>2.0 (창의적)</span>
                </div>
              </div>
              
              {/* 청크 크기 */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  청크 크기 (Chunk Size): <span className="text-primary-600 font-bold">{chunkSize}</span>
                </label>
                <input
                  type="range"
                  min="200"
                  max="2000"
                  step="100"
                  value={chunkSize}
                  onChange={(e) => setChunkSize(parseInt(e.target.value))}
                  className="w-full"
                />
                <div className="flex justify-between text-xs text-gray-500 mt-1">
                  <span>200</span>
                  <span>1000</span>
                  <span>2000</span>
                </div>
              </div>
              
              {/* 청크 오버랩 */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  청크 오버랩 (Overlap): <span className="text-primary-600 font-bold">{chunkOverlap}</span>
                </label>
                <input
                  type="range"
                  min="0"
                  max="500"
                  step="50"
                  value={chunkOverlap}
                  onChange={(e) => setChunkOverlap(parseInt(e.target.value))}
                  className="w-full"
                />
                <div className="flex justify-between text-xs text-gray-500 mt-1">
                  <span>0</span>
                  <span>250</span>
                  <span>500</span>
                </div>
              </div>
            </div>
            
            {/* 프리셋 버튼 */}
            <div className="mt-4 flex gap-2 flex-wrap">
              <button
                onClick={() => {
                  setChunkSize(1000)
                  setChunkOverlap(200)
                  setTopK(5)
                  setChunkingMethod('fixed')
                  setEmbeddingModel('text-embedding-ada-002')
                  setTemperature(0.7)
                }}
                className="px-3 py-1 text-xs bg-white border border-blue-300 text-blue-700 rounded-md hover:bg-blue-50"
              >
                기본 설정
              </button>
              <button
                onClick={() => {
                  setChunkSize(500)
                  setChunkOverlap(100)
                  setTopK(10)
                  setChunkingMethod('sentence')
                  setEmbeddingModel('text-embedding-3-small')
                  setTemperature(0.3)
                }}
                className="px-3 py-1 text-xs bg-white border border-green-300 text-green-700 rounded-md hover:bg-green-50"
              >
                정밀 검색
              </button>
              <button
                onClick={() => {
                  setChunkSize(1500)
                  setChunkOverlap(300)
                  setTopK(3)
                  setChunkingMethod('semantic')
                  setEmbeddingModel('text-embedding-3-large')
                  setTemperature(1.0)
                }}
                className="px-3 py-1 text-xs bg-white border border-purple-300 text-purple-700 rounded-md hover:bg-purple-50"
              >
                빠른 검색
              </button>
            </div>
          </div>
        )}
        
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              테스트 질문
            </label>
            <textarea
              value={testQuestion}
              onChange={(e) => setTestQuestion(e.target.value)}
              placeholder="예: 70대 고객에게 추천할 만한 대출 상품이 있나요?"
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent resize-none"
              rows={3}
            />
          </div>
          <button
            onClick={handleTest}
            disabled={testing || !testQuestion.trim()}
            className="w-full bg-primary-600 text-white px-6 py-3 rounded-lg hover:bg-primary-700 transition-colors disabled:bg-gray-300 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          >
            {testing ? (
              <>
                <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white"></div>
                테스트 중...
              </>
            ) : (
              <>
                <PaperAirplaneIcon className="w-5 h-5" />
                테스트 실행
              </>
            )}
          </button>
        </div>
      </div>

      {/* 테스트 결과 */}
      {testResult && (
        <div className="space-y-6">
          <div className="bg-white rounded-xl p-6 border border-gray-200">
            <div className="flex justify-between items-start mb-4">
              <h3 className="text-lg font-semibold text-gray-900">테스트 결과</h3>
              <div className="flex items-center gap-2">
                <span className="text-sm text-gray-500">응답 시간:</span>
                <span className={`text-lg font-bold ${getResponseTimeColor(testResult.response_time)}`}>
                  {testResult.response_time}초
                </span>
              </div>
            </div>

            {/* 사용된 청킹 설정 표시 */}
            {testResult.chunking_config && (
              <div className="mb-4 p-3 bg-blue-50 rounded-lg border border-blue-200">
                <div className="flex items-center gap-2 mb-2">
                  <svg className="w-4 h-4 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  <span className="text-sm font-semibold text-blue-900">청킹 & RAG 설정</span>
                </div>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
                  <div className="bg-white rounded px-2 py-1">
                    <span className="text-gray-500">방식:</span>
                    <span className="ml-1 font-semibold text-gray-900">
                      {testResult.chunking_config.chunking_method === 'fixed' ? '고정' :
                       testResult.chunking_config.chunking_method === 'sentence' ? '문장' : '의미'}
                    </span>
                  </div>
                  <div className="bg-white rounded px-2 py-1">
                    <span className="text-gray-500">임베딩:</span>
                    <span className="ml-1 font-semibold text-gray-900">
                      {testResult.chunking_config.embedding_model?.includes('ada') ? 'Ada-002' :
                       testResult.chunking_config.embedding_model?.includes('small') ? '3-Small' : '3-Large'}
                    </span>
                  </div>
                  <div className="bg-white rounded px-2 py-1">
                    <span className="text-gray-500">크기:</span>
                    <span className="ml-1 font-semibold text-gray-900">{testResult.chunking_config.chunk_size}</span>
                  </div>
                  <div className="bg-white rounded px-2 py-1">
                    <span className="text-gray-500">오버랩:</span>
                    <span className="ml-1 font-semibold text-gray-900">{testResult.chunking_config.chunk_overlap}</span>
                  </div>
                  <div className="bg-white rounded px-2 py-1">
                    <span className="text-gray-500">Top-K:</span>
                    <span className="ml-1 font-semibold text-gray-900">{testResult.chunking_config.top_k}</span>
                  </div>
                  <div className="bg-white rounded px-2 py-1">
                    <span className="text-gray-500">Temp:</span>
                    <span className="ml-1 font-semibold text-gray-900">{testResult.chunking_config.temperature}</span>
                  </div>
                  <div className="bg-white rounded px-2 py-1 md:col-span-2">
                    <span className="text-gray-500">검색됨:</span>
                    <span className="ml-1 font-semibold text-green-600">{testResult.chunking_config.total_chunks_found}개</span>
                  </div>
                </div>
              </div>
            )}
            
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">질문</label>
                <div className="bg-gray-50 rounded-lg p-4 text-gray-900">
                  {testResult.question}
                </div>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">답변</label>
                <div className="bg-primary-50 rounded-lg p-4 text-gray-900 whitespace-pre-wrap">
                  {testResult.answer}
                </div>
              </div>
              
              {testResult.sources && testResult.sources.length > 0 && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    참고 자료 ({testResult.sources.length}개)
                  </label>
                  <div className="space-y-2">
                    {testResult.sources.map((source: any, index: number) => (
                      <div key={index} className="bg-amber-50 rounded-lg p-3 border border-amber-200">
                        <p className="font-semibold text-amber-900 mb-1">{source.title}</p>
                        <p className="text-sm text-amber-700">{source.content}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              
              <div className="flex justify-between items-center pt-4 border-t border-gray-200">
                <span className="text-sm text-gray-500">
                  테스트 시각: {new Date(testResult.tested_at).toLocaleString()}
                </span>
                <span className={`px-3 py-1 rounded-full text-sm font-semibold ${
                  testResult.status === 'success' 
                    ? 'bg-green-100 text-green-800' 
                    : 'bg-red-100 text-red-800'
                }`}>
                  {testResult.status === 'success' ? '성공' : '실패'}
                </span>
              </div>
            </div>
          </div>

          {/* 성능 분석 Radar Chart */}
          {testResult.performance_scores && testResult.performance_scores.length > 0 && (
            <div className="bg-white rounded-xl p-6 border border-gray-200">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">성능 분석 (9개 카테고리)</h3>
              <div className="grid md:grid-cols-2 gap-6">
                {/* Radar Chart */}
                <div className="flex items-center justify-center">
                  <ResponsiveContainer width="100%" height={400}>
                    <RadarChart data={testResult.performance_scores}>
                      <PolarGrid stroke="#e5e7eb" />
                      <PolarAngleAxis 
                        dataKey="category" 
                        tick={{ fill: '#6b7280', fontSize: 12 }}
                      />
                      <PolarRadiusAxis 
                        angle={90} 
                        domain={[0, 100]}
                        tick={{ fill: '#6b7280', fontSize: 11 }}
                      />
                      <Radar 
                        name="성능 점수" 
                        dataKey="score" 
                        stroke="#0066cc" 
                        fill="#0066cc" 
                        fillOpacity={0.6}
                      />
                      <Tooltip 
                        contentStyle={{
                          backgroundColor: 'white',
                          border: '1px solid #e5e7eb',
                          borderRadius: '8px',
                          padding: '8px'
                        }}
                      />
                    </RadarChart>
                  </ResponsiveContainer>
                </div>

                {/* 점수 상세 목록 */}
                <div className="space-y-3">
                  {testResult.performance_scores.map((item: any, index: number) => (
                    <div key={index} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                      <div className="flex items-center gap-3">
                        <div className={`w-8 h-8 rounded-full flex items-center justify-center font-semibold text-sm ${
                          item.score >= 90 ? 'bg-green-100 text-green-800' :
                          item.score >= 75 ? 'bg-blue-100 text-blue-800' :
                          item.score >= 60 ? 'bg-yellow-100 text-yellow-800' :
                          'bg-red-100 text-red-800'
                        }`}>
                          {index + 1}
                        </div>
                        <span className="font-medium text-gray-900">{item.category}</span>
                      </div>
                      <div className="flex items-center gap-3">
                        <div className="w-32 bg-gray-200 rounded-full h-2">
                          <div 
                            className={`h-2 rounded-full ${
                              item.score >= 90 ? 'bg-green-500' :
                              item.score >= 75 ? 'bg-blue-500' :
                              item.score >= 60 ? 'bg-yellow-500' :
                              'bg-red-500'
                            }`}
                            style={{ width: `${item.score}%` }}
                          ></div>
                        </div>
                        <span className={`font-bold text-lg min-w-[3rem] text-right ${
                          item.score >= 90 ? 'text-green-600' :
                          item.score >= 75 ? 'text-blue-600' :
                          item.score >= 60 ? 'text-yellow-600' :
                          'text-red-600'
                        }`}>
                          {item.score}
                        </span>
                      </div>
                    </div>
                  ))}
                  
                  {/* 평균 점수 */}
                  <div className="mt-4 p-4 bg-gradient-to-r from-primary-50 to-primary-100 rounded-lg border border-primary-200">
                    <div className="flex justify-between items-center">
                      <span className="text-lg font-semibold text-primary-900">평균 점수</span>
                      <span className="text-2xl font-bold text-primary-600">
                        {Math.round(testResult.performance_scores.reduce((sum: number, item: any) => sum + item.score, 0) / testResult.performance_scores.length)}점
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* 테스트 히스토리 */}
      {testHistory.length > 1 && (
        <div className="bg-white rounded-xl p-6 border border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">최근 테스트 이력</h3>
          <div className="space-y-3">
            {testHistory.slice(1, 6).map((test, index) => (
              <div key={index} className="flex justify-between items-center p-3 bg-gray-50 rounded-lg">
                <div className="flex-1">
                  <p className="text-sm font-medium text-gray-900">{test.question}</p>
                  <p className="text-xs text-gray-500 mt-1">
                    {new Date(test.tested_at).toLocaleString()}
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <span className={`text-sm font-semibold ${getResponseTimeColor(test.response_time)}`}>
                    {test.response_time}초
                  </span>
                  <button
                    onClick={() => setTestResult(test)}
                    className="text-primary-600 hover:text-primary-700 text-sm font-medium"
                  >
                    보기
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 사용자별 통계 */}
      {stats?.top_users && stats.top_users.length > 0 && (
        <div className="bg-white rounded-xl p-6 border border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">활성 사용자 TOP 10</h3>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    순위
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    이름
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    이메일
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    대화 수
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {stats.top_users.map((user: any, index: number) => (
                  <tr key={index} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={`inline-flex items-center justify-center w-8 h-8 rounded-full font-semibold ${
                        index === 0 ? 'bg-yellow-100 text-yellow-800' :
                        index === 1 ? 'bg-gray-100 text-gray-800' :
                        index === 2 ? 'bg-orange-100 text-orange-800' :
                        'bg-blue-50 text-blue-800'
                      }`}>
                        {index + 1}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                      {user.name}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {user.email}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {user.chat_count}회
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

// 시뮬레이션 분석 탭
function SimulationAnalyticsTab() {
  const [analyticsData, setAnalyticsData] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [autoRefresh, setAutoRefresh] = useState(true)
  const refreshIntervalRef = useRef<NodeJS.Timeout | null>(null)
  
  // 비교 분석 Zone 상태
  const [comparisonMode, setComparisonMode] = useState<'filter' | 'combination'>('filter')
  const [comparisonFilter, setComparisonFilter] = useState<'gender' | 'age' | 'occupation' | 'customer_style'>('gender')
  const [selectedGroups, setSelectedGroups] = useState<string[]>([])
  
  // 페르소나 조합 모드 상태
  const [personaCombinations, setPersonaCombinations] = useState<Array<{
    id: string
    gender: string
    ageGroup: string
    occupation: string
    customerStyle: string
    scores?: any
  }>>([])
  const [newCombination, setNewCombination] = useState({
    gender: '',
    ageGroup: '',
    occupation: '',
    customerStyle: ''
  })
  
  // 탭 상태
  const [activeTab, setActiveTab] = useState<'comparison' | 'trend' | 'ranking'>('comparison')
  // 기간별 평균 점수 추이 - 기수 선택 상태 (여러 기수 동시 선택 가능, 기본은 4기)
  const [selectedCohorts, setSelectedCohorts] = useState<number[]>([4])

  const loadAnalytics = async () => {
    try {
      setLoading(true)
      setError(null)
      const data = await adminAPI.getSimulationAnalytics()
      setAnalyticsData(data)
    } catch (err: any) {
      console.error('시뮬레이션 분석 데이터 로드 실패:', err)
      setError(err?.response?.data?.detail || '데이터를 불러오는데 실패했습니다.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadAnalytics()

    // 자동 새로고침 설정
    if (autoRefresh) {
      refreshIntervalRef.current = setInterval(() => {
        loadAnalytics()
      }, 30000) // 30초마다 자동 새로고침
    }

    return () => {
      if (refreshIntervalRef.current) {
        clearInterval(refreshIntervalRef.current)
      }
    }
  }, [autoRefresh])

  // 필터 변경 시 선택된 그룹 초기화 및 첫 2개 자동 선택
  useEffect(() => {
    if (!analyticsData) return
    
    let availableGroups: string[] = []
    
    switch (comparisonFilter) {
      case 'gender':
        availableGroups = ['남자', '여자']
        break
      case 'age':
        availableGroups = Object.keys(analyticsData.age_group_distribution || {}).sort()
        break
      case 'occupation':
        availableGroups = Object.keys(analyticsData.occupation_comparison || {})
        break
      case 'customer_style':
        availableGroups = Object.keys(analyticsData.customer_style_radar || {})
        break
    }
    
    // 필터 변경 시 선택 초기화 (사용자가 자유롭게 선택)
    setSelectedGroups([])
  }, [comparisonFilter, analyticsData])


  if (loading && !analyticsData) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-4">
        <p className="text-red-800">{error}</p>
        <button
          onClick={loadAnalytics}
          className="mt-4 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700"
        >
          다시 시도
        </button>
      </div>
    )
  }

  if (!analyticsData) {
    return <div className="text-gray-500">데이터가 없습니다.</div>
  }

  // KPI 계산
  const totalSimulations = analyticsData.gender_comparison?.total_count || 0
  const avgScore = analyticsData.weekly_trend 
    ? Object.values(analyticsData.weekly_trend).reduce((sum: number, week: any) => sum + (week.overall || 0), 0) / Math.max(1, Object.keys(analyticsData.weekly_trend).length)
    : 0
  const lastMonthChange = 0 // TODO: 지난달 대비 계산 로직 추가 필요
  const avgPersonaFit = analyticsData.persona_fit_ranking?.top5 
    ? analyticsData.persona_fit_ranking.top5.reduce((sum: number, p: any) => sum + (p.avg_persona_fit || 0), 0) / Math.max(1, analyticsData.persona_fit_ranking.top5.length)
    : 0

  // 기간별 평균 점수 추이 데이터 (실제 주간 평균 점수)
  const weeklyTrendData = Object.entries(analyticsData.weekly_trend || {}).map(([week, data]: [string, any]) => ({
    week,
    평균점수: data.overall || 0,
  })).sort((a, b) => a.week.localeCompare(b.week))

  // 기수(주차 단위) 계산 - 0주차 포함해서 0~13주차까지 14개 좌표, 최대 4기까지 표시
  const cohortSize = 14
  const MAX_COHORTS = 4

  const getCohortWeekScore = (cohort: number, weekIndex: number) => {
    // 0주차는 기준선: 점수 0
    if (weekIndex === 0) return 0

    // 4기: 실제 데이터 사용 (현재 존재하는 주차 데이터)
    if (cohort === 4) {
      const source = weeklyTrendData[weekIndex - 1]
      // 아직 도달하지 않은 주차는 null로 두어 선이 이어지지 않도록 함
      return source ? source.평균점수 : null
    }

    // 1~3기: 가상 데이터 (기수별 시작/종료 점수 + 변동성)
    let start = 50
    let end = 80

    if (cohort === 2) {
      start = 40
      end = 75
    } else if (cohort === 3) {
      start = 55
      end = 77
    }

    const steps = cohortSize - 1 // 0주차를 제외한 실제 주차 개수
    const t = weekIndex / steps
    const baseScore = start + (end - start) * t
    const wave = Math.sin(weekIndex / 1.2) * 6 // 대략 -6 ~ +6 정도의 변동
    return baseScore + wave
  }

  // X축(주차) 기준으로 0~13까지 고정하고, 각 기수별 점수를 한 데이터셋에 병합
  const cohortChartData = Array.from({ length: cohortSize }, (_, i) => {
    const row: any = { weekIndex: i }
    for (let cohort = 1; cohort <= MAX_COHORTS; cohort++) {
      row[`cohort${cohort}`] = getCohortWeekScore(cohort, i)
    }
    return row
  })

  // 페르소나 랭킹 데이터 (상위 5 / 하위 5)
  const top5Personas = analyticsData.persona_fit_ranking?.top5 || []
  const low5Personas = analyticsData.persona_fit_ranking?.low5 || []
  
  // persona_info 포맷팅 함수 (통일된 형식: "나이대, 성별 띄고 직장, 성격")
  const formatPersonaInfo = (personaInfo: string | null | undefined): string => {
    if (!personaInfo) return '알 수 없음'
    
    // 공백으로 분리
    const parts = personaInfo.trim().split(/\s+/)
    
    // 패턴 정의
    const agePatterns = ['60대 이상', '10대', '20대', '30대', '40대', '50대']
    const genderPatterns = ['남성', '여성', '남자', '여자']
    const occupationPatterns = ['학생', '직장인', '무직', '자영업자', '은퇴자']
    const customerStylePatterns = ['불만형', '긍정형', '급함형', '불안형', '의심형']
    
    let ageGroup = ''
    let gender = ''
    let occupation = ''
    let customerStyle = ''
    
    // 연령대 찾기 (긴 패턴부터)
    for (const agePattern of agePatterns) {
      if (personaInfo.includes(agePattern)) {
        ageGroup = agePattern
        break
      }
    }
    
    // 나머지 부분에서 성별, 직업, 고객 성향 찾기
    let remainingText = personaInfo
    if (ageGroup) {
      remainingText = remainingText.replace(ageGroup, '').trim()
    }
    const remainingParts = remainingText.split(/\s+/)
    
    for (const part of remainingParts) {
      if (!gender && genderPatterns.includes(part)) {
        // 성별 통일 (남성/남자 -> 남자, 여성/여자 -> 여자)
        if (part === '남성' || part === '남자') {
          gender = '남자'
        } else if (part === '여성' || part === '여자') {
          gender = '여자'
        } else {
          gender = part
        }
      } else if (!occupation && occupationPatterns.includes(part)) {
        occupation = part
      } else if (!customerStyle && customerStylePatterns.includes(part)) {
        customerStyle = part
      }
    }
    
    // 포맷팅: "나이대, 성별 직장, 성격"
    const formattedParts: string[] = []
    if (ageGroup) formattedParts.push(ageGroup)
    if (gender) formattedParts.push(gender)
    if (occupation) formattedParts.push(occupation)
    if (customerStyle) formattedParts.push(customerStyle)
    
    // 모든 정보가 있으면 "나이대, 성별 직장, 성격" 형식
    if (ageGroup && gender && occupation && customerStyle) {
      return `${ageGroup}, ${gender} ${occupation}, ${customerStyle}`
    }
    
    // 일부 정보만 있으면 기존 형식 유지하거나 최대한 포맷팅
    if (formattedParts.length > 0) {
      return formattedParts.join(' ')
    }
    
    // 파싱 실패 시 원본 반환
    return personaInfo
  }

  // 비교 분석 Zone: 사용 가능한 그룹 목록
  const getAvailableGroups = (): string[] => {
    switch (comparisonFilter) {
      case 'gender':
        return ['남자', '여자']
      case 'age':
        return Object.keys(analyticsData.age_group_distribution || {}).sort()
      case 'occupation':
        return Object.keys(analyticsData.occupation_comparison || {})
      case 'customer_style':
        return Object.keys(analyticsData.customer_style_radar || {})
      default:
        return []
    }
  }

  // 비교 분석 Zone: 레이더 차트 데이터 준비
  const getRadarChartData = () => {
    const radarData: any[] = [
      { name: '지식' },
      { name: '기술' },
      { name: '친절도' },
      { name: '전달력' },
      { name: '페르소나 적합도' },
    ]

    // 대비가 극명한 색상 팔레트 (보색 관계 활용, 명확한 구분)
    const colorPalette = [
      '#1E40AF', // 진한 파란색 (Blue-700)
      '#DC2626', // 진한 빨간색 (Red-600)
      '#F59E0B', // 진한 주황색 (Amber-500)
      '#7C3AED', // 진한 보라색 (Violet-600)
      '#059669', // 진한 초록색 (Emerald-600)
      '#EA580C', // 진한 오렌지색 (Orange-600)
      '#BE185D', // 진한 분홍색 (Pink-700)
      '#0D9488', // 진한 청록색 (Teal-600)
    ]
    
    selectedGroups.forEach((group, index) => {
      let groupData: any = {}
      
      switch (comparisonFilter) {
        case 'gender':
          const genderData = group === '남자' 
            ? analyticsData.gender_comparison?.male 
            : analyticsData.gender_comparison?.female
          groupData = {
            knowledge: genderData?.knowledge || 0,
            skill: genderData?.skill || 0,
            kindness: genderData?.kindness || 0,
            delivery: genderData?.delivery || 0,
            persona_fit: genderData?.persona_fit || 0,
          }
          break
        case 'age':
          const ageData = analyticsData.age_group_distribution?.[group]
          groupData = {
            knowledge: ageData?.knowledge?.avg || 0,
            skill: ageData?.skill?.avg || 0,
            kindness: ageData?.kindness?.avg || 0,
            delivery: ageData?.delivery?.avg || 0,
            persona_fit: ageData?.persona_fit?.avg || 0,
          }
          break
        case 'occupation':
          const occData = analyticsData.occupation_comparison?.[group]
          groupData = {
            knowledge: occData?.knowledge || 0,
            skill: occData?.skill || 0,
            kindness: occData?.kindness || 0,
            delivery: occData?.delivery || 0,
            persona_fit: occData?.persona_fit || 0,
          }
          break
        case 'customer_style':
          const styleData = analyticsData.customer_style_radar?.[group]
          groupData = {
            knowledge: styleData?.knowledge || 0,
            skill: styleData?.skill || 0,
            kindness: styleData?.kindness || 0,
            delivery: styleData?.delivery || 0,
            persona_fit: styleData?.persona_fit || 0,
          }
          break
      }
      
      radarData[0][group] = groupData.knowledge
      radarData[1][group] = groupData.skill
      radarData[2][group] = groupData.kindness
      radarData[3][group] = groupData.delivery
      radarData[4][group] = groupData.persona_fit
    })

    return { radarData, colors: colorPalette }
  }

  const handleGroupToggle = (group: string) => {
    setSelectedGroups(prev => {
      if (prev.includes(group)) {
        return prev.filter(g => g !== group)
      } else {
        return [...prev, group]
      }
    })
  }

  const { radarData, colors } = getRadarChartData()
  const availableGroups = getAvailableGroups()

  return (
    <div className="space-y-6">
      {/* 헤더 */}
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-bold text-gray-900">시뮬레이션 분석</h2>
        <div className="flex items-center gap-4">
          <label className="flex items-center gap-2 text-sm text-gray-600">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
              className="rounded"
            />
            자동 새로고침 (30초)
          </label>
          <button
            onClick={loadAnalytics}
            className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors"
          >
            <ArrowPathIcon className="w-5 h-5" />
            새로고침
          </button>
        </div>
      </div>

      {/* 탭 메뉴 */}
      <div className="bg-white rounded-xl shadow-md p-2">
        <div className="flex gap-2">
          <button
            onClick={() => setActiveTab('comparison')}
            className={`flex-1 px-4 py-3 rounded-lg font-medium transition-colors ${
              activeTab === 'comparison'
                ? 'bg-primary-600 text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
          >
            페르소나 비교 분석
          </button>
          <button
            onClick={() => setActiveTab('trend')}
            className={`flex-1 px-4 py-3 rounded-lg font-medium transition-colors ${
              activeTab === 'trend'
                ? 'bg-primary-600 text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
          >
            기간별 평균 점수 추이
          </button>
          <button
            onClick={() => setActiveTab('ranking')}
            className={`flex-1 px-4 py-3 rounded-lg font-medium transition-colors ${
              activeTab === 'ranking'
                ? 'bg-primary-600 text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
          >
            페르소나 랭킹
          </button>
        </div>
      </div>

      {/* 탭별 컨텐츠 */}
      {activeTab === 'comparison' && (
        <>
      {/* 1. 상단 KPI 카드 */}
      <div className="grid md:grid-cols-4 gap-4">
        <div className="bg-white rounded-lg p-4 border border-gray-200 shadow-sm">
          <p className="text-sm text-gray-600">총 시뮬레이션 수</p>
          <p className="text-2xl font-bold text-gray-900">{totalSimulations.toLocaleString()}</p>
        </div>
        <div className="bg-white rounded-lg p-4 border border-gray-200 shadow-sm">
          <p className="text-sm text-gray-600">평균 점수</p>
          <p className="text-2xl font-bold text-primary-600">{avgScore.toFixed(1)}</p>
        </div>
        <div className="bg-white rounded-lg p-4 border border-gray-200 shadow-sm">
          <p className="text-sm text-gray-600">지난달 대비 변화량</p>
          <div className="flex items-center gap-2">
            <p className="text-2xl font-bold text-gray-900">{lastMonthChange > 0 ? '+' : ''}{lastMonthChange.toFixed(1)}%</p>
            {lastMonthChange !== 0 && (
              lastMonthChange > 0 ? (
                <ArrowTrendingUpIcon className="w-5 h-5 text-green-600" />
              ) : (
                <ArrowTrendingUpIcon className="w-5 h-5 text-red-600 rotate-180" />
              )
            )}
          </div>
        </div>
        <div className="bg-white rounded-lg p-4 border border-gray-200 shadow-sm">
          <p className="text-sm text-gray-600">페르소나 적합도 평균</p>
          <p className="text-2xl font-bold text-purple-600">{avgPersonaFit.toFixed(1)}</p>
        </div>
      </div>

      {/* 비교 분석 Zone (통합) */}
      <div className="bg-white rounded-xl shadow-md p-6">
        <h3 className="text-xl font-bold text-gray-900 mb-6">페르소나 비교 분석</h3>
        
        {/* 모드 선택: 필터 vs 페르소나 조합 */}
        <div className="mb-6">
          <label className="block text-sm font-medium text-gray-700 mb-2">비교 모드 선택</label>
          <div className="flex gap-3">
            <button
              onClick={() => setComparisonMode('filter')}
              className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                comparisonMode === 'filter'
                  ? 'bg-primary-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              필터 기반 비교
            </button>
            <button
              onClick={() => setComparisonMode('combination')}
              className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                comparisonMode === 'combination'
                  ? 'bg-primary-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              페르소나 조합 비교
            </button>
          </div>
        </div>

        {comparisonMode === 'filter' ? (
          <>
            {/* Step 1: 필터 선택 */}
            <div className="mb-6">
              <label className="block text-sm font-medium text-gray-700 mb-2">분석 관점 선택</label>
              <div className="flex flex-wrap gap-3">
                {[
                  { value: 'gender', label: '성별' },
                  { value: 'age', label: '연령대' },
                  { value: 'occupation', label: '직업' },
                  { value: 'customer_style', label: '고객 성향' },
                ].map((option) => (
                  <button
                    key={option.value}
                    onClick={() => setComparisonFilter(option.value as any)}
                    className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                      comparisonFilter === option.value
                        ? 'bg-primary-600 text-white'
                        : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                    }`}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Step 2: 그룹 선택 */}
            <div className="mb-6">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                비교할 그룹 선택 (자유 선택)
              </label>
              <div className="flex flex-wrap gap-3">
                {availableGroups.map((group) => (
                  <label
                    key={group}
                    className={`flex items-center gap-2 px-4 py-2 rounded-lg border cursor-pointer transition-colors ${
                      selectedGroups.includes(group)
                        ? 'bg-primary-50 border-primary-500 text-primary-700'
                      : 'bg-white border-gray-300 text-gray-700 hover:bg-gray-50'
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={selectedGroups.includes(group)}
                      onChange={() => handleGroupToggle(group)}
                      className="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                    />
                    <span>{group}</span>
                  </label>
                ))}
              </div>

            </div>

            {/* Step 3: 레이더 차트 */}
            <div>
              <h4 className="text-lg font-semibold text-gray-900 mb-4">역량 비교 (레이더 차트)</h4>
              <ResponsiveContainer width="100%" height={400}>
                <RadarChart data={radarData}>
                  <PolarGrid />
                  <PolarAngleAxis dataKey="name" tick={{ fontSize: 12 }} />
                  <PolarRadiusAxis angle={90} domain={[0, 100]} />
                  {selectedGroups.map((group, index) => {
                    const color = colors[index % colors.length]
                    // 짝수 인덱스는 실선, 홀수 인덱스는 점선으로 구분
                    const strokeDasharray = index % 2 === 0 ? undefined : '5 5'
                    return (
                    <Radar
                      key={group}
                      name={group}
                      dataKey={group}
                        stroke={color}
                        fill={color}
                        fillOpacity={0.25}
                        strokeWidth={4}
                        strokeDasharray={strokeDasharray}
                        dot={{ r: 5, fill: color, strokeWidth: 2, stroke: '#fff' }}
                        activeDot={{ r: 7, fill: color, strokeWidth: 2, stroke: '#fff' }}
                      />
                    )
                  })}
                  <Tooltip />
                  <Legend />
                </RadarChart>
              </ResponsiveContainer>
              {selectedGroups.length === 0 && (
                <p className="mt-2 text-sm text-gray-500 text-center">
                  비교할 그룹을 선택하면 레이더 차트가 표시됩니다.
                </p>
              )}
            </div>
          </>
        ) : (
          <>
            {/* 페르소나 조합 모드 */}
            <div className="mb-6">
              <h4 className="text-lg font-semibold text-gray-900 mb-4">페르소나 조합 추가</h4>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">성별</label>
                  <select
                    value={newCombination.gender}
                    onChange={(e) => setNewCombination({ ...newCombination, gender: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                  >
                    <option value="">선택</option>
                    <option value="남자">남자</option>
                    <option value="여자">여자</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">연령대</label>
                  <select
                    value={newCombination.ageGroup}
                    onChange={(e) => setNewCombination({ ...newCombination, ageGroup: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                  >
                    <option value="">선택</option>
                    <option value="10대">10대</option>
                    <option value="20대">20대</option>
                    <option value="30대">30대</option>
                    <option value="40대">40대</option>
                    <option value="50대">50대</option>
                    <option value="60대 이상">60대 이상</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">직업</label>
                  <select
                    value={newCombination.occupation}
                    onChange={(e) => setNewCombination({ ...newCombination, occupation: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                  >
                    <option value="">선택</option>
                    <option value="학생">학생</option>
                    <option value="직장인">직장인</option>
                    <option value="자영업자">자영업자</option>
                    <option value="은퇴자">은퇴자</option>
                    <option value="무직">무직</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">고객 성향</label>
                  <select
                    value={newCombination.customerStyle}
                    onChange={(e) => setNewCombination({ ...newCombination, customerStyle: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                  >
                    <option value="">선택</option>
                    <option value="긍정형">긍정형</option>
                    <option value="불만형">불만형</option>
                    <option value="급함형">급함형</option>
                  </select>
                </div>
              </div>
              <button
                onClick={async () => {
                  // 최소 한 가지 조건은 선택해야 의미 있는 조합이 됨
                  if (!newCombination.gender && !newCombination.ageGroup && !newCombination.occupation && !newCombination.customerStyle) {
                    alert('최소 한 가지 이상 조건을 선택해주세요.')
                    return
                  }
                  const combinationId = `${newCombination.gender || '전체'}_${newCombination.ageGroup || '전체'}_${newCombination.occupation || '전체'}_${newCombination.customerStyle || '전체'}`
                  if (personaCombinations.find(c => c.id === combinationId)) {
                    alert('이미 추가된 조합입니다.')
                    return
                  }
                  if (personaCombinations.length >= 5) {
                    alert('최대 5개까지 추가할 수 있습니다.')
                    return
                  }
                  try {
                    const scores = await adminAPI.getPersonaCombinationScores(
                      newCombination.gender || undefined,
                      newCombination.ageGroup || undefined,
                      newCombination.occupation || undefined,
                      newCombination.customerStyle || undefined
                    )
                    setPersonaCombinations([...personaCombinations, {
                      id: combinationId,
                      ...newCombination,
                      scores
                    }])
                    setNewCombination({ gender: '', ageGroup: '', occupation: '', customerStyle: '' })
                  } catch (err) {
                    console.error('페르소나 조합 점수 조회 실패:', err)
                    alert('점수 조회에 실패했습니다.')
                  }
                }}
                className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors"
              >
                조합 추가
              </button>
            </div>

            {/* 선택된 페르소나 조합 목록 */}
            {personaCombinations.length > 0 && (
              <div className="mb-6">
                <h4 className="text-lg font-semibold text-gray-900 mb-4">선택된 페르소나 조합</h4>
                <div className="space-y-2">
                  {personaCombinations.map((combo) => {
                    const fields = [
                      combo.gender,
                      combo.ageGroup,
                      combo.occupation,
                      combo.customerStyle,
                    ].filter(Boolean)
                    const hasAllFields = combo.gender && combo.ageGroup && combo.occupation && combo.customerStyle
                    const label = hasAllFields
                      ? fields.join(' ')
                      : `${fields.join(' ') || '전체'} 전체`
                    return (
                    <div key={combo.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                      <div className="flex items-center gap-3">
                        <span className="font-bold text-gray-900">
                          {label}
                        </span>
                        {combo.scores && (
                          <span className="text-sm text-gray-500">
                            (데이터: {combo.scores.count}건)
                          </span>
                        )}
                      </div>
                      <button
                        onClick={() => setPersonaCombinations(personaCombinations.filter(c => c.id !== combo.id))}
                        className="text-red-600 hover:text-red-700 text-sm font-medium"
                      >
                        제거
                      </button>
                    </div>
                  )})}
                </div>
              </div>
            )}

            {/* 페르소나 조합 레이더 차트 */}
            {personaCombinations.length >= 2 && (
              <div>
                <h4 className="text-lg font-semibold text-gray-900 mb-4">역량 비교 (레이더 차트)</h4>
                <ResponsiveContainer width="100%" height={400}>
                  <RadarChart data={[
                    {
                      name: '지식',
                      ...personaCombinations.reduce((acc, combo) => {
                        acc[combo.id] = combo.scores?.knowledge || 0
                        return acc
                      }, {} as any)
                    },
                    {
                      name: '기술',
                      ...personaCombinations.reduce((acc, combo) => {
                        acc[combo.id] = combo.scores?.skill || 0
                        return acc
                      }, {} as any)
                    },
                    {
                      name: '친절도',
                      ...personaCombinations.reduce((acc, combo) => {
                        acc[combo.id] = combo.scores?.kindness || 0
                        return acc
                      }, {} as any)
                    },
                    {
                      name: '전달력',
                      ...personaCombinations.reduce((acc, combo) => {
                        acc[combo.id] = combo.scores?.delivery || 0
                        return acc
                      }, {} as any)
                    },
                    {
                      name: '페르소나 적합도',
                      ...personaCombinations.reduce((acc, combo) => {
                        acc[combo.id] = combo.scores?.persona_fit || 0
                        return acc
                      }, {} as any)
                    }
                  ]}>
                    <PolarGrid />
                    <PolarAngleAxis dataKey="name" tick={{ fontSize: 12 }} />
                    <PolarRadiusAxis angle={90} domain={[0, 100]} />
                    {personaCombinations.map((combo, index) => {
                      const color = colors[index % colors.length]
                      // 짝수 인덱스는 실선, 홀수 인덱스는 점선으로 구분
                      const strokeDasharray = index % 2 === 0 ? undefined : '5 5'
                      return (
                      <Radar
                        key={combo.id}
                        name={`${combo.gender} ${combo.ageGroup} ${combo.occupation} ${combo.customerStyle}`}
                        dataKey={combo.id}
                          stroke={color}
                          fill={color}
                          fillOpacity={0.25}
                          strokeWidth={4}
                          strokeDasharray={strokeDasharray}
                          dot={{ r: 5, fill: color, strokeWidth: 2, stroke: '#fff' }}
                          activeDot={{ r: 7, fill: color, strokeWidth: 2, stroke: '#fff' }}
                        />
                      )
                    })}
                    <Tooltip />
                    <Legend />
                  </RadarChart>
                </ResponsiveContainer>
              </div>
            )}
          </>
        )}
      </div>
        </>
      )}

      {activeTab === 'trend' && (
        <div className="bg-white rounded-xl shadow-md p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-xl font-bold text-gray-900">기간별 평균 점수 추이</h3>
            <div className="flex items-center gap-2 text-sm">
              <span className="text-gray-600">기수 선택</span>
              <div className="flex gap-1">
                {Array.from({ length: MAX_COHORTS }, (_, idx) => {
                  const cohortNumber = idx + 1
                  const isSelected = selectedCohorts.includes(cohortNumber)
                  return (
                    <button
                      key={cohortNumber}
                      type="button"
                      onClick={() =>
                        setSelectedCohorts((prev) => {
                          if (prev.includes(cohortNumber)) {
                            // 최소 1개는 유지
                            if (prev.length === 1) return prev
                            return prev.filter((c) => c !== cohortNumber)
                          }
                          return [...prev, cohortNumber].sort()
                        })
                      }
                      className={`px-2 py-1 rounded border text-xs font-medium transition-colors ${
                        isSelected
                          ? 'bg-primary-600 text-white border-primary-600'
                          : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-100'
                      }`}
                    >
                      {cohortNumber}기
                    </button>
                  )
                })}
              </div>
            </div>
          </div>
          <p className="text-xs text-gray-500 mb-3">
            각 기수는 최대 13주의 시뮬레이션 결과로 구성됩니다.
          </p>
          {/* 최고/최저 점수 계산 (0주차 제외) */}
          {(() => {
            const allScores: Array<{ score: number; cohort: number; week: number }> = []
            selectedCohorts.forEach(cohort => {
              cohortChartData.forEach((row: any) => {
                // 0주차는 제외 (기준선이므로)
                if (row.weekIndex === 0) return
                
                const score = row[`cohort${cohort}`]
                if (score !== null && score !== undefined && typeof score === 'number') {
                  allScores.push({
                    score,
                    cohort,
                    week: row.weekIndex
                  })
                }
              })
            })
            
            if (allScores.length === 0) {
              return null
            }
            
            const maxEntry = allScores.reduce((max, entry) => entry.score > max.score ? entry : max)
            const minEntry = allScores.reduce((min, entry) => entry.score < min.score ? entry : min)
            
            return (
              <div className="mb-4 flex items-center gap-4 text-sm">
                <div className="flex items-center gap-2">
                  <span className="text-gray-600">최고 점수:</span>
                  <span className="font-semibold text-green-600">
                    {Math.round(maxEntry.score)}점 ({maxEntry.cohort}기, {maxEntry.week}주차)
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-gray-600">최저 점수:</span>
                  <span className="font-semibold text-red-600">
                    {Math.round(minEntry.score)}점 ({minEntry.cohort}기, {minEntry.week}주차)
                  </span>
                </div>
              </div>
            )
          })()}
          <ResponsiveContainer width="100%" height={400}>
            <LineChart data={cohortChartData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis 
                dataKey="weekIndex" 
                type="number" 
                domain={[0, cohortSize - 1]}
                tickCount={cohortSize}
                tickFormatter={(value) => String(value)}
                label={{ value: '주차', position: 'insideBottomRight', offset: -5 }}
              />
              <YAxis 
                domain={[0, 100]} 
                tickFormatter={(value) => Math.round(value).toString()}
              />
              <Tooltip 
                formatter={(value: any, name: string) => {
                  if (value === null || value === undefined) return ['데이터 없음', name]
                  return [`${Math.round(Number(value))}점`, name]
                }}
              />
              <Legend />
              {selectedCohorts.includes(1) && (
                <Line 
                  key="cohort1"
                  type="monotone" 
                  dataKey="cohort1" 
                  name="1기"
                  stroke="#3B82F6" 
                  strokeWidth={2}
                  dot={{ r: 3 }}
                  activeDot={{ r: 5 }}
                />
              )}
              {selectedCohorts.includes(2) && (
                <Line 
                  key="cohort2"
                  type="monotone" 
                  dataKey="cohort2" 
                  name="2기"
                  stroke="#10B981" 
                  strokeWidth={2}
                  dot={{ r: 3 }}
                  activeDot={{ r: 5 }}
                />
              )}
              {selectedCohorts.includes(3) && (
                <Line 
                  key="cohort3"
                  type="monotone" 
                  dataKey="cohort3" 
                  name="3기"
                  stroke="#F59E0B" 
                  strokeWidth={2}
                  dot={{ r: 3 }}
                  activeDot={{ r: 5 }}
                />
              )}
              {selectedCohorts.includes(4) && (
                <Line 
                  key="cohort4"
                  type="monotone" 
                  dataKey="cohort4" 
                  name="4기"
                  stroke="#EF4444" 
                  strokeWidth={2}
                  dot={{ r: 3 }}
                  activeDot={{ r: 5 }}
                />
              )}
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {activeTab === 'ranking' && (
        <div className="grid md:grid-cols-2 gap-6">
          <div className="bg-white rounded-xl shadow-md p-6">
            <h3 className="text-xl font-bold text-gray-900 mb-4">상위 5 페르소나</h3>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart 
                data={top5Personas.map((p: any, idx: number) => ({
                  name: formatPersonaInfo(p.persona_info) || `페르소나 ${idx + 1}`,
                  점수: p.avg_overall || 0
                }))}
                layout="vertical"
              >
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis type="number" domain={[0, 100]} />
                <YAxis dataKey="name" type="category" width={120} />
                <Tooltip />
                <Bar dataKey="점수" fill="#10B981" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="bg-white rounded-xl shadow-md p-6">
            <h3 className="text-xl font-bold text-gray-900 mb-4">하위 5 페르소나</h3>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart 
                data={low5Personas.map((p: any, idx: number) => ({
                  name: formatPersonaInfo(p.persona_info) || `페르소나 ${idx + 1}`,
                  점수: p.avg_overall || 0
                }))}
                layout="vertical"
              >
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis type="number" domain={[0, 100]} />
                <YAxis dataKey="name" type="category" width={120} />
                <Tooltip />
                <Bar dataKey="점수" fill="#EF4444" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  )
}
