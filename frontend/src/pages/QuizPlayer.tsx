import { useEffect, useMemo, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { QuizMode, useQuizStore } from '../store/quizStore'
import { useAuthStore } from '../store/authStore'

type GradedInfo = {
  status: 'correct' | 'incorrect'
  selected: string
}

export default function QuizPlayer() {
  const quizData = useQuizStore((state) => state.quizData)
  const answers = useQuizStore((state) => state.answers)
  const setAnswer = useQuizStore((state) => state.setAnswer)
  const setQuiz = useQuizStore((state) => state.setQuiz)
  const setAnswers = useQuizStore((state) => state.setAnswers)
  const resetQuiz = useQuizStore((state) => state.resetQuiz)
  const addHistoryEntry = useQuizStore((state) => state.addHistoryEntry)
  const historyEntries = useQuizStore((state) => state.history)
  const currentUser = useAuthStore((state) => state.user)
  const location = useLocation()
  const navigate = useNavigate()

  const [currentIndex, setCurrentIndex] = useState(0)
  const [sourcePreview, setSourcePreview] = useState<{ file: string; url: string } | null>(null)
  const [sourceError, setSourceError] = useState<string | null>(null)
  const [sourceContent, setSourceContent] = useState<string[] | null>(null)
  const [sourceLoading, setSourceLoading] = useState(false)
  const [graded, setGraded] = useState<Record<number, GradedInfo>>({})

  const questions = quizData?.questions ?? []
  const currentQuestion = questions[currentIndex]
  const totalQuestions = questions.length

  const isAssessmentMode =
    quizData?.exam_info.mode === 'midterm' || quizData?.exam_info.mode === 'final'

  const modeLabel = useMemo(() => {
    const mode = quizData?.exam_info.mode as QuizMode | undefined
    if (mode === 'midterm') return '중간 평가'
    if (mode === 'final') return '최종 평가'
    if (mode === 'custom') return '맞춤 세트'
    return '랜덤 세트'
  }, [quizData?.exam_info.mode])

  const reviewEntryId = (location.state as any)?.reviewEntryId ?? null
  const isReviewMode = !!reviewEntryId

  const unansweredCount = useMemo(
    () => questions.filter((q) => !answers[q.q_id]).length,
    [answers, questions]
  )

  const optionKeys = useMemo(() => ['보기 1', '보기 2', '보기 3', '보기 4'], [])

  const normalizeAnswer = (value?: string) => {
    if (!value) return ''
    const match = value.match(/\d+/)
    if (match) return match[0]
    return value.replace(/\s+/g, '').toLowerCase()
  }

  const handleCheckAnswer = () => {
    if (!currentQuestion || isAssessmentMode) return
    if (graded[currentQuestion.q_id]) return

    const selected = answers[currentQuestion.q_id]
    if (!selected) {
      window.alert('보기를 선택하세요.')
      return
    }

    const isCorrect =
      normalizeAnswer(selected) && normalizeAnswer(selected) === normalizeAnswer(currentQuestion.answer)

    setGraded((prev) => ({
      ...prev,
      [currentQuestion.q_id]: { status: isCorrect ? 'correct' : 'incorrect', selected },
    }))
  }

  const handleShowSource = () => {
    if (!currentQuestion?.source_files?.length) {
      setSourceError('학습자료가 없습니다.')
      return
    }
    const file = currentQuestion.source_files[0]
    setSourceError(null)
    setSourcePreview({
      file,
      url: `/api/quiz/source-file?file_name=${encodeURIComponent(file)}`,
    })
  }

  const calculateCategoryStats = () => {
    const stats: Record<
      string,
      {
        correct: number
        total: number
      }
    > = {}

    questions.forEach((q) => {
      const cat = q.category_name || '기타'
      if (!stats[cat]) {
        stats[cat] = { correct: 0, total: 0 }
      }
      stats[cat].total += 1
      const userAnswer = answers[q.q_id]
      if (userAnswer && normalizeAnswer(userAnswer) === normalizeAnswer(q.answer)) {
        stats[cat].correct += 1
      }
    })
    return stats
  }

  const handleExit = () => {
    const categoryStats = calculateCategoryStats()
    const totalAnswered = Object.keys(answers).length
    const correctTotal = Object.values(categoryStats).reduce((sum, c) => sum + c.correct, 0)
    const totalQuestions = questions.length
    const computedScore =
      totalQuestions > 0 ? Math.round((correctTotal / totalQuestions) * 100) : 0

    if (isReviewMode) {
      resetQuiz()
      navigate('/learning')
      return
    }

    if (unansweredCount > 0) {
      const message = `안 푼 문제가 ${unansweredCount}개 있습니다. 종료하시겠습니까?`
      if (!window.confirm(message)) return
    } else if (isAssessmentMode) {
      if (!window.confirm('제출하시겠습니까?')) return
    }

    if (isAssessmentMode) {
      addHistoryEntry({
        id: `assessment-${quizData?.exam_info.mode ?? 'random'}-${Date.now()}`,
        userId: currentUser?.id ?? null,
        date: new Date().toISOString(),
        mode: (quizData?.exam_info.mode as QuizMode | undefined) ?? 'random',
        score: computedScore,
        total: totalQuestions,
        note: '평가 제출',
        categoryStats,
        quizData,
        answers,
      })
    } else {
      if (totalAnswered > 0) {
        addHistoryEntry({
          id: `check-session-${Date.now()}`,
          userId: currentUser?.id ?? null,
          date: new Date().toISOString(),
          mode: (quizData?.exam_info.mode as QuizMode | undefined) ?? 'random',
          score: computedScore,
          total: totalQuestions,
          note: '정답확인 종료',
          categoryStats,
          quizData,
          answers,
        })
      }
    }

    resetQuiz()
    navigate('/learning')
  }

  const handlePaginationClick = (index: number) => setCurrentIndex(index)

  const renderOptions = () => {
    if (!currentQuestion) return null
    return (
      <div className="space-y-3 max-w-2xl mx-auto w-full">
        {optionKeys.map((key) => {
          const label = currentQuestion[key as keyof typeof currentQuestion]
          if (!label) return null
          const choiceValue = key as '보기 1' | '보기 2' | '보기 3' | '보기 4'
          const gradedInfo = graded[currentQuestion.q_id]
          const isCorrectChoice =
            normalizeAnswer(choiceValue) === normalizeAnswer(currentQuestion.answer)
          let badge: { text: string; color: string } | null = null
          if (gradedInfo) {
            if (gradedInfo.selected === choiceValue) {
              badge =
                gradedInfo.status === 'correct'
                  ? { text: '✔ 정답', color: 'text-green-600' }
                  : { text: '✖ 오답', color: 'text-red-500' }
            } else if (isCorrectChoice) {
              badge = { text: '✔ 정답', color: 'text-green-600' }
            }
          } else if (isReviewMode && isCorrectChoice) {
            badge = { text: '✔ 정답', color: 'text-green-600' }
          }
          return (
            <label
              key={choiceValue}
              className="flex items-center gap-3 border border-primary-100 rounded-2xl px-4 py-3 hover:border-primary-300 transition-colors cursor-pointer"
            >
              <input
                type="radio"
                name={`question-${currentQuestion.q_id}`}
                value={choiceValue}
                checked={answers[currentQuestion.q_id] === choiceValue}
                onChange={() => setAnswer(currentQuestion.q_id, choiceValue)}
                 disabled={isReviewMode || (!!gradedInfo && !isAssessmentMode)}
                 className="w-4 h-4 text-primary-600 focus:ring-primary-500 disabled:opacity-70"
              />
              <span className="text-bank-800 text-sm">
                <strong className="text-primary-500 mr-2">{choiceValue}</strong>
                {label}
              </span>
              {badge && <span className={`ml-auto text-xs font-semibold ${badge.color}`}>{badge.text}</span>}
            </label>
          )
        })}
      </div>
    )
  }

  useEffect(() => {
    setSourcePreview(null)
    setSourceError(null)
    setSourceContent(null)
  }, [currentQuestion?.q_id])

  useEffect(() => {
    if (!sourcePreview) {
      setSourceContent(null)
      setSourceLoading(false)
      return
    }
    const isJsonl = sourcePreview.file.toLowerCase().endsWith('.jsonl')
    if (!isJsonl) {
      setSourceContent(null)
      return
    }
    setSourceLoading(true)
    fetch(sourcePreview.url)
      .then((res) => {
        if (!res.ok) throw new Error('failed to fetch source')
        return res.text()
      })
      .then((text) => {
        const pretty = text
          .split('\n')
          .filter((line) => line.trim().length > 0)
          .map((line) => {
            try {
              return JSON.stringify(JSON.parse(line), null, 2)
            } catch (e) {
              return line
            }
          })
        setSourceContent(pretty)
      })
      .catch(() => {
        setSourceError('본문을 불러오지 못했습니다.')
        setSourceContent(null)
      })
      .finally(() => setSourceLoading(false))
  }, [sourcePreview])

  useEffect(() => {
    if (!reviewEntryId) return
    const entry = historyEntries.find((h) => h.id === reviewEntryId)
    if (!entry?.quizData) return

    setQuiz(entry.quizData)
    setAnswers(entry.answers ?? {})

    const gradedMap: Record<number, GradedInfo> = {}
    entry.quizData.questions.forEach((q) => {
      const selected = entry.answers?.[q.q_id] ?? ''
      const isCorrect =
        selected &&
        normalizeAnswer(selected) &&
        normalizeAnswer(selected) === normalizeAnswer(q.answer)
      gradedMap[q.q_id] = { status: isCorrect ? 'correct' : 'incorrect', selected }
    })
    setGraded(gradedMap)
    setCurrentIndex(0)
  }, [historyEntries, reviewEntryId, setAnswers, setQuiz])

  if (!quizData) {
    return (
      <div className="bg-white rounded-3xl shadow-lg p-8 border border-primary-100 text-center space-y-4">
        <p className="text-lg font-semibold text-bank-700">진행 중인 퀴즈가 없습니다.</p>
        <button
          onClick={() => navigate('/learning')}
          className="px-4 py-2 rounded-xl bg-primary-600 text-white font-semibold hover:bg-primary-700 transition-colors"
        >
          학습 관리로 돌아가기
        </button>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <header className="bg-white rounded-3xl shadow-lg border border-primary-100 p-6 flex flex-col gap-3">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-sm font-semibold text-primary-500">{modeLabel}</p>
            <h1 className="text-2xl font-bold text-bank-900">{quizData.exam_info.title}</h1>
            <p className="text-sm text-bank-600">
              총 {quizData.exam_info.total_questions}문항 | {currentIndex + 1} / {quizData.exam_info.total_questions}
            </p>
          </div>
          <button
            onClick={handleExit}
            className="px-4 py-2 rounded-xl bg-primary-600 text-white font-semibold hover:bg-primary-700 transition-all"
          >
            종료
          </button>
        </div>
      </header>

        {currentQuestion && (
        <div className="bg-white rounded-3xl shadow-lg border border-primary-100 p-6 flex flex-col gap-6">
          {isAssessmentMode ? (
            isReviewMode ? (
              <div className="flex flex-col gap-6 md:flex-row">
                <div className="md:w-1/2 w-full border border-primary-100 rounded-2xl p-4 bg-primary-50/40 min-h-[220px]">
                  {sourcePreview ? (
                    <div className="flex flex-col gap-3 h-full">
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-semibold text-primary-700 truncate">{sourcePreview.file}</span>
                        <button
                          onClick={() => setSourcePreview(null)}
                          className="text-xs text-primary-500 hover:text-primary-700"
                        >
                          닫기
                        </button>
                      </div>
                      <div className="flex-1 border border-primary-100 rounded-xl overflow-hidden bg-white">
                        {sourceContent ? (
                          <div className="h-full max-h-[420px] overflow-y-auto p-3 space-y-3 text-xs font-mono text-bank-800 bg-gray-50">
                            {sourceContent.map((line, idx) => (
                              <pre key={idx} className="whitespace-pre-wrap break-words">
                                {line}
                              </pre>
                            ))}
                          </div>
                        ) : (
                          <iframe
                            title="source-preview"
                            src={sourcePreview.url}
                            className="w-full h-60 md:h-[420px] border-0"
                          />
                        )}
                      </div>
                      {sourceLoading && (
                        <p className="text-xs text-primary-500 mt-2 text-center">본문을 불러오는 중입니다...</p>
                      )}
                    </div>
                  ) : (
                    <div className="h-full flex flex-col items-center justify-center text-primary-500 text-sm">
                      <p>본문보기 버튼을 눌러 학습자료를 확인하세요.</p>
                    </div>
                  )}
                  {sourceError && <p className="text-xs text-red-500 mt-2 text-center">{sourceError}</p>}
                </div>
                <div className="flex-1 flex flex-col gap-4">
                  <div className="text-center">
                    <p className="text-sm text-primary-500 font-semibold">{currentQuestion.category_name}</p>
                    <h2 className="mt-2 text-xl font-bold text-bank-900 max-h-40 overflow-y-auto">
                      {currentQuestion.question}
                    </h2>
                  </div>
                  {renderOptions()}
                  {currentQuestion.comment && (
                    <div className="mt-2 w-full max-w-2xl mx-auto rounded-2xl bg-primary-50 border border-primary-100 p-3 text-sm text-bank-800">
                      <p className="font-semibold text-primary-700 mb-1">해설</p>
                      <p className="whitespace-pre-wrap leading-relaxed">{currentQuestion.comment}</p>
                    </div>
                  )}
                  <div className="flex justify-center gap-3 pt-2">
                    <button
                      type="button"
                      onClick={handleShowSource}
                      className="px-4 py-2 rounded-xl border border-primary-200 text-sm font-semibold text-primary-600 hover:bg-primary-50 transition-colors"
                    >
                      본문보기
                    </button>
                    <button
                      type="button"
                      onClick={handleCheckAnswer}
                      disabled
                      className="px-4 py-2 rounded-xl border border-primary-200 text-sm font-semibold text-primary-400 bg-primary-50 cursor-not-allowed"
                    >
                      정답확인
                    </button>
                  </div>
                </div>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-6">
                <div className="text-center space-y-4 w-full max-w-3xl">
                  <p className="text-sm text-primary-500 font-semibold">{currentQuestion.category_name}</p>
                  <h2 className="mt-2 text-xl font-bold text-bank-900 leading-relaxed">
                    {currentQuestion.question}
                  </h2>
                  {renderOptions()}
                </div>
              </div>
            )
          ) : (
            <div className="flex flex-col gap-6 md:flex-row">
              <div className="md:w-1/2 w-full border border-primary-100 rounded-2xl p-4 bg-primary-50/40 min-h-[220px]">
                {sourcePreview ? (
                  <div className="flex flex-col gap-3 h-full">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-semibold text-primary-700 truncate">{sourcePreview.file}</span>
                      <button
                        onClick={() => setSourcePreview(null)}
                        className="text-xs text-primary-500 hover:text-primary-700"
                      >
                        닫기
                      </button>
                    </div>
                    <div className="flex-1 border border-primary-100 rounded-xl overflow-hidden bg-white">
                      {sourceContent ? (
                        <div className="h-full max-h-[420px] overflow-y-auto p-3 space-y-3 text-xs font-mono text-bank-800 bg-gray-50">
                          {sourceContent.map((line, idx) => (
                            <pre key={idx} className="whitespace-pre-wrap break-words">
                              {line}
                            </pre>
                          ))}
                        </div>
                      ) : (
                        <iframe
                          title="source-preview"
                          src={sourcePreview.url}
                          className="w-full h-60 md:h-[420px] border-0"
                        />
                      )}
                    </div>
                    {sourceLoading && (
                      <p className="text-xs text-primary-500 mt-2 text-center">본문을 불러오는 중입니다...</p>
                    )}
                  </div>
                ) : (
                  <div className="h-full flex flex-col items-center justify-center text-primary-500 text-sm">
                    <p>본문보기 버튼을 눌러 학습자료를 확인하세요.</p>
                  </div>
                )}
                {sourceError && <p className="text-xs text-red-500 mt-2 text-center">{sourceError}</p>}
              </div>
              <div className="flex-1 flex flex-col gap-4">
                <div className="text-center">
                  <p className="text-sm text-primary-500 font-semibold">{currentQuestion.category_name}</p>
                  <h2 className="mt-2 text-xl font-bold text-bank-900 max-h-40 overflow-y-auto">
                    {currentQuestion.question}
                  </h2>
                </div>
                {renderOptions()}
                {graded[currentQuestion.q_id] && currentQuestion.comment && (
                  <div className="mt-2 w-full max-w-2xl mx-auto rounded-2xl bg-primary-50 border border-primary-100 p-3 text-sm text-bank-800">
                    <p className="font-semibold text-primary-700 mb-1">해설</p>
                    <p className="whitespace-pre-wrap leading-relaxed">{currentQuestion.comment}</p>
                  </div>
                )}
                <div className="flex justify-center gap-3 pt-2">
                  <button
                    type="button"
                    onClick={handleShowSource}
                    className="px-4 py-2 rounded-xl border border-primary-200 text-sm font-semibold text-primary-600 hover:bg-primary-50 transition-colors"
                  >
                    본문보기
                  </button>
                  <button
                    type="button"
                    onClick={handleCheckAnswer}
                    disabled={isReviewMode}
                    className="px-4 py-2 rounded-xl border border-primary-200 text-sm font-semibold text-primary-600 hover:bg-primary-50 transition-colors"
                  >
                    정답확인
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {totalQuestions > 0 && (
        <div className="bg-white rounded-3xl shadow-lg border border-primary-100 p-4 flex items-center gap-3 flex-wrap">
          <button
            onClick={() => setCurrentIndex((prev) => Math.max(prev - 1, 0))}
            disabled={currentIndex === 0}
            className="px-4 py-2 rounded-xl border border-primary-200 text-sm font-semibold text-primary-600 disabled:opacity-50"
          >
            이전
          </button>
          <div className="flex-1 flex flex-wrap gap-2 justify-center">
            {questions.map((q, index) => {
              const answered = Boolean(answers[q.q_id])
              return (
                <button
                  key={q.q_id}
                  onClick={() => handlePaginationClick(index)}
                  className={`w-10 h-10 rounded-full text-sm font-semibold border transition-colors ${
                    index === currentIndex
                      ? 'bg-primary-600 text-white border-primary-600'
                      : answered
                      ? 'bg-primary-50 text-primary-600 border-primary-200'
                      : 'border-primary-100 text-bank-500'
                  }`}
                >
                  {q.q_no}
                </button>
              )
            })}
          </div>
          <button
            onClick={() => setCurrentIndex((prev) => Math.min(prev + 1, totalQuestions - 1))}
            disabled={currentIndex === totalQuestions - 1}
            className="px-4 py-2 rounded-xl border border-primary-200 text-sm font-semibold text-primary-600 disabled:opacity-50"
          >
            다음
          </button>
        </div>
      )}
    </div>
  )
}
