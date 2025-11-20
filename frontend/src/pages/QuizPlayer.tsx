import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { quizAPI } from '../utils/api'
import { useQuizStore } from '../store/quizStore'

export default function QuizPlayer() {
  const quizData = useQuizStore((state) => state.quizData)
  const answers = useQuizStore((state) => state.answers)
  const setAnswer = useQuizStore((state) => state.setAnswer)
  const resetQuiz = useQuizStore((state) => state.resetQuiz)
  const addHistoryEntry = useQuizStore((state) => state.addHistoryEntry)
  const navigate = useNavigate()

  const [currentIndex, setCurrentIndex] = useState(0)
  const [showConfirm, setShowConfirm] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  const questions = quizData?.questions ?? []
  const currentQuestion = questions[currentIndex]
  const totalQuestions = questions.length

  const optionKeys = useMemo(() => ['보기 1', '보기 2', '보기 3', '보기 4'], [])

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

  const handlePaginationClick = (index: number) => {
    setCurrentIndex(index)
  }

  const handleSubmit = async () => {
    if (!quizData.generation_id) {
      setErrorMessage('세션 정보가 올바르지 않습니다.')
      return
    }
    const payloadAnswers: Record<number, string> = {}
    for (const question of questions) {
      const choice = answers[question.q_id]
      if (choice) {
        payloadAnswers[question.q_id] = choice
      }
    }

    setSubmitting(true)
    setErrorMessage(null)
    try {
      const response = await quizAPI.submitQuiz({
        generation_id: quizData.generation_id,
        answers: payloadAnswers,
      })
      addHistoryEntry({
        id: `quiz-${quizData.generation_id}-${Date.now()}`,
        date: new Date().toISOString(),
        mode: quizData.exam_info.mode,
        score: response.score,
        total: response.total_questions,
        note: quizData.exam_info.mode === 'custom' ? '맞춤형 세트 제출' : '랜덤 세트 제출',
      })
      setShowConfirm(false)
      resetQuiz()
      navigate('/learning', {
        state: { defaultTab: 'history', justSubmitted: true },
      })
    } catch (error: any) {
      const detail = error?.response?.data?.detail
      setErrorMessage(
        typeof detail === 'string' ? detail : '제출 중 오류가 발생했습니다. 다시 시도해주세요.'
      )
    } finally {
      setSubmitting(false)
    }
  }

  const handleExit = () => {
    resetQuiz()
    navigate('/learning')
  }

  const handleConfirmAction = async (action: 'submit' | 'exit') => {
    if (action === 'submit') {
      await handleSubmit()
    } else {
      handleExit()
      setShowConfirm(false)
    }
  }

  return (
    <div className="space-y-6">
      <header className="bg-white rounded-3xl shadow-lg border border-primary-100 p-6 flex flex-col gap-2">
        <p className="text-sm font-semibold text-primary-500">
          {quizData.exam_info.mode === 'custom' ? '맞춤형 세트' : '랜덤 세트'}
        </p>
        <h1 className="text-2xl font-bold text-bank-900">{quizData.exam_info.title}</h1>
        <p className="text-sm text-bank-600">
          총 {quizData.exam_info.total_questions}문항 | {currentIndex + 1} /{' '}
          {quizData.exam_info.total_questions}
        </p>
      </header>

      {currentQuestion && (
        <div className="bg-white rounded-3xl shadow-lg border border-primary-100 p-6 flex flex-col gap-6">
          <div className="text-center">
            <p className="text-sm text-primary-500 font-semibold">
              {currentQuestion.category_name}
            </p>
            <h2 className="mt-2 text-xl font-bold text-bank-900">{currentQuestion.question}</h2>
          </div>

          <div className="space-y-3 max-w-2xl mx-auto w-full">
            {optionKeys.map((key) => {
              const label = currentQuestion[key as keyof typeof currentQuestion]
              if (!label) return null
              const choiceValue = key as '보기 1' | '보기 2' | '보기 3' | '보기 4'
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
                    className="w-4 h-4 text-primary-600 focus:ring-primary-500"
                  />
                  <span className="text-bank-800 text-sm">
                    <strong className="text-primary-500 mr-2">{choiceValue}</strong>
                    {label}
                  </span>
                </label>
              )
            })}
          </div>

          <div className="flex justify-between items-center flex-wrap gap-2 pt-4 border-t border-primary-100">
            <div className="flex gap-2">
              <button
                onClick={() => setCurrentIndex((prev) => Math.max(prev - 1, 0))}
                disabled={currentIndex === 0}
                className="px-4 py-2 rounded-xl border border-primary-200 text-sm font-semibold text-primary-600 disabled:opacity-50"
              >
                이전
              </button>
              <button
                onClick={() =>
                  setCurrentIndex((prev) => Math.min(prev + 1, totalQuestions - 1))
                }
                disabled={currentIndex === totalQuestions - 1}
                className="px-4 py-2 rounded-xl border border-primary-200 text-sm font-semibold text-primary-600 disabled:opacity-50"
              >
                다음
              </button>
            </div>
            <button
              onClick={() => setShowConfirm(true)}
              className="px-4 py-2 rounded-xl bg-primary-600 text-white font-semibold hover:bg-primary-700 transition-all"
            >
              종료
            </button>
          </div>
        </div>
      )}

      {totalQuestions > 0 && (
        <div className="bg-white rounded-3xl shadow-lg border border-primary-100 p-4 flex flex-wrap gap-2 justify-center">
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
      )}

      {errorMessage && (
        <div className="bg-red-50 border border-red-200 rounded-2xl p-4 text-sm text-red-600">
          {errorMessage}
        </div>
      )}

      {showConfirm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-3xl shadow-xl p-6 w-full max-w-md space-y-4">
            <h3 className="text-xl font-bold text-bank-900">종료하시겠습니까?</h3>
            <p className="text-sm text-bank-600">
              제출하면 선택한 답안이 저장되고 채점됩니다. 취소하고 나가기 선택 시 기록 없이
              이전 화면으로 돌아갑니다.
            </p>
            <div className="flex flex-col gap-2">
              <button
                onClick={() => handleConfirmAction('submit')}
                disabled={submitting}
                className="px-4 py-2 rounded-xl bg-primary-600 text-white font-semibold hover:bg-primary-700 disabled:opacity-60"
              >
                {submitting ? '제출 중...' : '제출하기'}
              </button>
              <button
                onClick={() => handleConfirmAction('exit')}
                className="px-4 py-2 rounded-xl border border-primary-200 text-primary-600 font-semibold hover:bg-primary-50"
              >
                취소하고 나가기
              </button>
              <button
                onClick={() => setShowConfirm(false)}
                className="px-4 py-2 rounded-xl text-sm text-bank-500"
              >
                계속 풀기
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
