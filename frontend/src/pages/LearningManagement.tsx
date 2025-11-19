import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  BookOpenIcon,
  ClipboardDocumentListIcon,
  ClockIcon,
  AdjustmentsHorizontalIcon,
  ChartBarSquareIcon,
  ArrowPathIcon,
  SparklesIcon,
} from '@heroicons/react/24/outline'
import { quizAPI } from '../utils/api'
import { useQuizStore } from '../store/quizStore'

const CATEGORY_ORDER = [
  '금융영업',
  '상품개발 및 운용',
  '신용분석 및 리스크관리',
  '외환',
  '은행지식 및 관련법률',
  '하경은행',
]

const mockHistory = [
  {
    id: 'exam-1203',
    date: '2025-11-12',
    type: '균등 세트',
    score: 78,
    total: 120,
    note: '상품개발, 외환 파트에서 재도전 필요',
  },
  {
    id: 'exam-1187',
    date: '2025-11-05',
    type: '취약영역 집중',
    score: 84,
    total: 60,
    note: '신용분석 × 리스크관리 세트',
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

export default function LearningManagement() {
  const [activeTab, setActiveTab] = useState<'history' | 'practice'>('history')
  const [loadingMode, setLoadingMode] = useState<'random' | 'custom' | null>(null)
  const [apiError, setApiError] = useState<string | null>(null)
  const navigate = useNavigate()
  const setQuiz = useQuizStore((state) => state.setQuiz)

  const weakestCategory = useMemo(() => {
    return mockProgress.reduce((prev, curr) =>
      curr.accuracy < prev.accuracy ? curr : prev
    )
  }, [])

  const handleStartQuiz = async (mode: 'random' | 'custom', totalQuestions: number) => {
    setApiError(null)
    setLoadingMode(mode)
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
          <h1 className="text-2xl md:text-3xl font-bold text-bank-900">
            학습 관리
          </h1>
          <p className="mt-2 text-bank-600 leading-relaxed">
            quizdb(dbquiz_eval.csv)에서 추출한 은행 실무 문제로 학습을 관리합니다.
            공통 세트로 실력을 비교하고, 개인 기록을 기반으로 취약 영역을 재훈련할 수 있습니다.
          </p>
        </div>
        {weakestCategory && (
          <div className="flex flex-wrap items-center gap-4 bg-primary-50/70 rounded-2xl px-5 py-4 text-primary-800 text-sm">
            <SparklesIcon className="w-5 h-5" />
            최근 데이터 기준 가장 취약한 영역은
            <span className="font-semibold">{weakestCategory.category}</span>
            (정답률 {(weakestCategory.accuracy * 100).toFixed(0)}%)입니다.
            취약 세트를 생성하면 해당 영역 문항 비중을 높여 드릴게요.
          </div>
        )}
      </header>

      <section className="bg-white rounded-3xl shadow-lg border border-primary-100 p-4">
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
        </div>

        <div className="mt-6">
          {activeTab === 'history' ? (
            <MyLearning />
          ) : (
            <Practice
              onStartQuiz={handleStartQuiz}
              loadingMode={loadingMode}
              apiError={apiError}
            />
          )}
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

function MyLearning() {
  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-2">
        <div className="rounded-2xl border border-primary-100 p-5 bg-gradient-to-br from-white to-primary-50/60">
          <div className="flex items-center gap-3 text-sm text-primary-500 font-semibold">
            <ChartBarSquareIcon className="w-5 h-5" />
            카테고리별 정답률
          </div>
          <div className="mt-4 space-y-4">
            {mockProgress.map((item) => (
              <div key={item.category}>
                <div className="flex justify-between text-sm text-bank-700 font-medium">
                  <span>{item.category}</span>
                  <span>{Math.round(item.accuracy * 100)}%</span>
                </div>
                <div className="h-2 bg-primary-50 rounded-full mt-2">
                  <div
                    className="h-2 rounded-full bg-primary-500"
                    style={{ width: `${item.accuracy * 100}%` }}
                  />
                </div>
                <p className="text-xs text-bank-500 mt-1">
                  누적 {item.solved}문항 풀이
                </p>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-2xl border border-primary-100 p-5 space-y-4">
          <div className="flex items-center gap-3 text-sm text-primary-500 font-semibold">
            <ArrowPathIcon className="w-5 h-5" />
            최근 학습 기록
          </div>
          <div className="space-y-4">
            {mockHistory.map((history) => (
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
                  <span className="text-3xl font-bold text-bank-900">
                    {history.score}
                  </span>
                  <span className="text-sm text-bank-500">/ {history.total}</span>
                </div>
                <p className="mt-2 text-sm text-bank-600">{history.note}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="rounded-2xl border border-primary-100 p-5 bg-primary-50/40">
        <p className="text-sm text-bank-600 leading-relaxed">
          위 데이터는 예시이며, 실제 서비스에서는 사용자별 퀴즈 제출 결과를 집계하여
          RDS/Firestore 등에서 읽어옵니다. API가 연결되면{' '}
          <code className="px-2 py-1 rounded bg-white text-primary-600 text-xs">
            /api/quiz-results
          </code>{' '}
          엔드포인트를 통해 학습 내역을 불러오도록 설정하면 됩니다.
        </p>
      </div>
    </div>
  )
}

interface PracticeProps {
  onStartQuiz: (mode: 'random' | 'custom', totalQuestions: number) => void
  loadingMode: 'random' | 'custom' | null
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
        <div className="rounded-2xl border border-primary-100 p-5 bg-gradient-to-br from-white to-primary-50/50 flex flex-col gap-4">
          <div className="flex items-center gap-3 text-primary-600 font-semibold text-sm">
            <ClipboardDocumentListIcon className="w-5 h-5" />
            중간/최종 평가
          </div>
          <div>
            <p className="text-sm text-primary-500 font-medium">
              모든 연수생이 동일하게 응시하는 정규 평가 세트
            </p>
            <p className="mt-2 text-bank-700 text-sm leading-relaxed">
              <code className="px-2 py-1 bg-white rounded text-primary-600 text-xs">
                backend/data/midterm_quiz.json
              </code>{' '}
              파일은 중간 평가,{' '}
              <code className="px-2 py-1 bg-white rounded text-primary-600 text-xs">
                backend/data/final_quiz.json
              </code>{' '}
              파일은 최종 평가용 60문항 세트를 제공합니다.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button className="px-4 py-2 rounded-xl text-sm font-semibold bg-primary-600 text-white shadow-md hover:bg-primary-700">
              중간 평가
            </button>
            <button className="px-4 py-2 rounded-xl text-sm font-semibold bg-primary-100 text-primary-700 hover:bg-primary-200">
              최종 평가
            </button>
          </div>
        </div>

        <div className="rounded-2xl border border-primary-100 p-5 bg-gradient-to-br from-white to-primary-50/50 flex flex-col gap-4">
          <div className="flex items-center gap-3 text-primary-600 font-semibold text-sm">
            <AdjustmentsHorizontalIcon className="w-5 h-5" />
            연습하기
          </div>
          <div>
            <p className="text-sm text-primary-500 font-medium">
              원하는 문항 수와 알고리즘으로 연습 세트를 생성
            </p>
            <p className="mt-2 text-bank-700 text-sm leading-relaxed">
              입력한 문항 수만큼{' '}
              <code className="px-2 py-1 bg-white rounded text-primary-600 text-xs">
                backend/data/rag_sources/dbquiz_eval.csv
              </code>{' '}
              에서 문제를 가져와 랜덤 또는 맞춤형 세트를 구성합니다.
            </p>
          </div>
          <div className="space-y-3">
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
            <div className="flex flex-wrap gap-2">
              <button
                className="px-4 py-2 rounded-xl text-sm font-semibold bg-primary-600 text-white shadow-md hover:bg-primary-700 disabled:opacity-60"
                onClick={() => onStartQuiz('random', questionCount)}
                disabled={loadingMode === 'random'}
              >
                {loadingMode === 'random' ? '로딩 중...' : '랜덤 세트'}
              </button>
              <button
                className="px-4 py-2 rounded-xl text-sm font-semibold bg-primary-100 text-primary-700 hover:bg-primary-200 disabled:opacity-60"
                onClick={() => onStartQuiz('custom', questionCount)}
                disabled={loadingMode === 'custom'}
              >
                {loadingMode === 'custom' ? '로딩 중...' : '맞춤형 세트'}
              </button>
            </div>
            {apiError && (
              <p className="text-sm text-red-500 bg-red-50 rounded-2xl px-4 py-2">
                {apiError}
              </p>
            )}
          </div>
        </div>
      </div>

      <div className="rounded-2xl border border-primary-100 p-5 bg-white space-y-4">
        <div className="flex items-center gap-3 text-primary-600 font-semibold text-sm">
          <ClipboardDocumentListIcon className="w-5 h-5" />
          카테고리 구성
        </div>
        <div className="grid sm:grid-cols-2 gap-4">
          {CATEGORY_ORDER.map((category, index) => (
            <div
              key={category}
              className="rounded-2xl border border-primary-50 p-4 flex justify-between items-center bg-primary-50/40"
            >
              <div>
                <p className="text-xs text-primary-500 font-semibold">
                  카테고리 {index + 1}
                </p>
                <p className="text-base font-semibold text-bank-800">
                  {category}
                </p>
              </div>
              <span className="text-sm text-primary-600 font-semibold">
                10문항
              </span>
            </div>
          ))}
        </div>
        <p className="text-sm text-bank-600 bg-primary-50/50 rounded-2xl p-4 leading-relaxed">
          모든 연수생에게 동일하게 배포되는 공통 세트는 backend/random_quiz.py 스크립트에서
          dbquiz_eval.csv를 읽어 카테고리별 10문항씩 샘플링하여 Json으로 변환합니다.
          프론트엔드는 이후 API 또는 S3 Json을 호출해 세트를 로드한 뒤, 답안 제출 API와 연동하면 됩니다.
        </p>
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
