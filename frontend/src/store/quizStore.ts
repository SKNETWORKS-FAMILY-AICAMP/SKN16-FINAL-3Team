import { create } from 'zustand'

export interface QuizQuestion {
  q_no: number
  q_id: number
  question: string
  category_name: string
  ['보기 1']: string
  ['보기 2']: string
  ['보기 3']: string
  ['보기 4']: string
  answer: string
  comment: string
  source_files?: string[]
}

export type QuizMode = 'random' | 'custom' | 'midterm' | 'final' | 'pre'

export interface QuizData {
  generation_id?: number
  exam_info: {
    title: string
    mode: QuizMode
    total_questions: number
  }
  category_summary?: Record<string, number>
  questions: QuizQuestion[]
  remaining_attempts?: Partial<Record<QuizMode, number>>
  remaining_custom_attempts?: number
}

export interface QuizHistoryEntry {
  id: string
  userId?: number | null
  date: string
  mode: QuizMode
  score: number
  total: number
  note?: string
  attempt?: number
  categoryStats?: Record<
    string,
    {
      correct: number
      total: number
    }
  >
  quizData?: QuizData
  answers?: Record<number, string>
}

interface QuizState {
  quizData?: QuizData
  answers: Record<number, string>
  history: QuizHistoryEntry[]
  setQuiz: (data: QuizData) => void
  setAnswer: (qId: number, choice: string) => void
  setAnswers: (answers: Record<number, string>) => void
  resetQuiz: () => void
  addHistoryEntry: (entry: QuizHistoryEntry) => void
  setHistory: (entries: QuizHistoryEntry[]) => void
}

const INITIAL_STATE = {
  quizData: undefined as QuizData | undefined,
  answers: {} as Record<number, string>,
  history: [] as QuizHistoryEntry[],
}

export const useQuizStore = create<QuizState>((set) => ({
  quizData: undefined,
  answers: {},
  history: [],
  setQuiz: (data) =>
    set({
      quizData: data,
      answers: {},
    }),
  setAnswer: (qId, choice) =>
    set((state) => ({
      answers: {
        ...state.answers,
        [qId]: choice,
      },
    })),
  setAnswers: (answers) => set({ answers }),
  resetQuiz: () => set({ quizData: undefined, answers: {} }),
  addHistoryEntry: (entry) =>
    set((state) => ({
      history: (() => {
        const maxAttempt = state.history.reduce((max, h) => Math.max(max, h.attempt ?? 0), 0)
        const nextAttempt = (entry.attempt ?? 0) > 0 ? entry.attempt! : maxAttempt + 1
        const withAttempt = { ...entry, attempt: nextAttempt }
        const sorted = [withAttempt, ...state.history].sort((a, b) => {
          const tA = new Date(a.date).getTime()
          const tB = new Date(b.date).getTime()
          if (Number.isNaN(tA) || Number.isNaN(tB)) return 0
          return tB - tA
        })
        return sorted.slice(0, 10)
      })(),
    })),
  setHistory: (entries) =>
    set(() => {
      const sortedAsc = [...entries].sort((a, b) => {
        const tA = new Date(a.date).getTime()
        const tB = new Date(b.date).getTime()
        if (Number.isNaN(tA) || Number.isNaN(tB)) return 0
        return tA - tB
      })
      const withAttempt = sortedAsc.map((entry, idx) => ({ ...entry, attempt: idx + 1 }))
      const sortedDesc = [...withAttempt].sort((a, b) => {
        const tA = new Date(a.date).getTime()
        const tB = new Date(b.date).getTime()
        if (Number.isNaN(tA) || Number.isNaN(tB)) return 0
        return tB - tA
      })
      return { history: sortedDesc }
    }),
}))
