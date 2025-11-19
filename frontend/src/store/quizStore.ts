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
}

export interface QuizData {
  generation_id?: number
  exam_info: {
    title: string
    mode: 'random' | 'custom'
    total_questions: number
  }
  category_summary?: Record<string, number>
  questions: QuizQuestion[]
  remaining_custom_attempts?: number
}

interface QuizState {
  quizData?: QuizData
  answers: Record<number, string>
  setQuiz: (data: QuizData) => void
  setAnswer: (qId: number, choice: string) => void
  resetQuiz: () => void
}

export const useQuizStore = create<QuizState>((set) => ({
  quizData: undefined,
  answers: {},
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
  resetQuiz: () =>
    set({
      quizData: undefined,
      answers: {},
    }),
}))
