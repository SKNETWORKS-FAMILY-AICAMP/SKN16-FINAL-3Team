/**
 * 채팅 라이브러리 상태 관리 스토어
 * ChatGPT 스타일의 대화 세션 관리
 */
import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export interface ChatMessage {
  id: string
  text: string
  isBot: boolean
  sources?: any[]
  timestamp: Date
}

export interface ChatSession {
  id: string
  title: string
  messages: ChatMessage[]
  createdAt: Date
  updatedAt: Date
  isActive: boolean
}

interface ChatStore {
  // 상태
  sessions: ChatSession[]
  currentSessionId: string | null
  isLoading: boolean
  userId: number | null  // 현재 사용자 ID 저장
  
  // 액션
  createSession: (title?: string) => string
  deleteSession: (sessionId: string) => void
  updateSessionTitle: (sessionId: string, title: string) => void
  setActiveSession: (sessionId: string) => void
  addMessage: (sessionId: string, message: ChatMessage) => void
  clearSession: (sessionId: string) => void
  exportSession: (sessionId: string) => string
  importSession: (sessionData: string) => void
  clearAll: () => void  // 모든 세션 초기화
  setUserId: (userId: number | null) => void  // 사용자 ID 설정
}

// 세션 제목 자동 생성 함수
const generateSessionTitle = (firstMessage: string): string => {
  const maxLength = 50
  const cleanMessage = firstMessage.trim().replace(/\n/g, ' ')
  
  if (cleanMessage.length <= maxLength) {
    return cleanMessage
  }
  
  return cleanMessage.substring(0, maxLength) + '...'
}

export const useChatStore = create<ChatStore>()(
  persist(
    (set, get) => ({
      // 초기 상태
      sessions: [],
      currentSessionId: null,
      isLoading: false,
      userId: null,

      // 새 세션 생성
      createSession: (title?: string) => {
        const newSession: ChatSession = {
          id: `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
          title: title || '새 대화',
          messages: [
            {
              id: 'welcome',
              text: '안녕하세요! 저는 AI 하리보예요 🐻\n하경은행 온보딩 플랫폼에서 무엇이든 도와드릴게요!\n궁금한 점을 자유롭게 물어보세요.',
              isBot: true,
              timestamp: new Date(),
            }
          ],
          createdAt: new Date(),
          updatedAt: new Date(),
          isActive: true,
        }

        set((state) => ({
          sessions: [newSession, ...state.sessions.map(s => ({ ...s, isActive: false }))],
          currentSessionId: newSession.id,
        }))

        return newSession.id
      },

      // 세션 삭제
      deleteSession: (sessionId: string) => {
        set((state) => {
          const filteredSessions = state.sessions.filter(s => s.id !== sessionId)
          const newCurrentSessionId = state.currentSessionId === sessionId 
            ? (filteredSessions.length > 0 ? filteredSessions[0].id : null)
            : state.currentSessionId

          return {
            sessions: filteredSessions,
            currentSessionId: newCurrentSessionId,
          }
        })
      },

      // 세션 제목 업데이트
      updateSessionTitle: (sessionId: string, title: string) => {
        set((state) => ({
          sessions: state.sessions.map(session =>
            session.id === sessionId
              ? { ...session, title, updatedAt: new Date() }
              : session
          ),
        }))
      },

      // 활성 세션 설정
      setActiveSession: (sessionId: string) => {
        set((state) => ({
          sessions: state.sessions.map(session => ({
            ...session,
            isActive: session.id === sessionId
          })),
          currentSessionId: sessionId,
        }))
      },

      // 메시지 추가
      addMessage: (sessionId: string, message: ChatMessage) => {
        set((state) => {
          const updatedSessions = state.sessions.map(session => {
            if (session.id === sessionId) {
              const updatedMessages = [...session.messages, message]
              
              // 첫 번째 사용자 메시지로 제목 자동 생성
              let title = session.title
              if (session.messages.length === 1 && !message.isBot) {
                title = generateSessionTitle(message.text)
              }

              return {
                ...session,
                messages: updatedMessages,
                title,
                updatedAt: new Date(),
              }
            }
            return session
          })

          return { sessions: updatedSessions }
        })
      },

      // 세션 메시지 초기화
      clearSession: (sessionId: string) => {
        set((state) => ({
          sessions: state.sessions.map(session =>
            session.id === sessionId
              ? {
                  ...session,
                  messages: [
                    {
                      id: 'welcome',
                      text: '안녕하세요! 저는 AI 하리보예요 🐻\n하경은행 온보딩 플랫폼에서 무엇이든 도와드릴게요!\n궁금한 점을 자유롭게 물어보세요.',
                      isBot: true,
                      timestamp: new Date(),
                    }
                  ],
                  updatedAt: new Date(),
                }
              : session
          ),
        }))
      },

      // 세션 내보내기 (JSON 문자열)
      exportSession: (sessionId: string) => {
        const session = get().sessions.find(s => s.id === sessionId)
        if (!session) return ''
        
        return JSON.stringify(session, null, 2)
      },

      // 세션 가져오기
      importSession: (sessionData: string) => {
        try {
          const session = JSON.parse(sessionData) as ChatSession
          
          // 새로운 ID 생성하여 중복 방지
          const importedSession: ChatSession = {
            ...session,
            id: `imported_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
            createdAt: new Date(session.createdAt),
            updatedAt: new Date(session.updatedAt),
            isActive: false,
          }

          set((state) => ({
            sessions: [importedSession, ...state.sessions],
          }))
        } catch (error) {
          console.error('세션 가져오기 실패:', error)
        }
      },

      // 모든 세션 초기화
      clearAll: () => {
        set({
          sessions: [],
          currentSessionId: null,
          isLoading: false,
        })
      },

      // 사용자 ID 설정 (사용자 변경 시 세션 초기화)
      setUserId: (userId: number | null) => {
        const currentUserId = get().userId
        
        // 사용자가 변경되었으면 모든 세션 초기화
        if (currentUserId !== null && currentUserId !== userId) {
          set({
            sessions: [],
            currentSessionId: null,
            isLoading: false,
            userId,
          })
        } else {
          set({ userId })
        }
      },
    }),
    {
      name: 'chat-library-storage', // 로컬 스토리지 키
      // Date 객체 직렬화/역직렬화 처리
      partialize: (state) => ({
        sessions: state.sessions,
        currentSessionId: state.currentSessionId,
        userId: state.userId,
      }),
      onRehydrateStorage: () => (state) => {
        if (state) {
          // Date 객체 복원
          state.sessions = state.sessions.map(session => ({
            ...session,
            createdAt: new Date(session.createdAt),
            updatedAt: new Date(session.updatedAt),
            messages: session.messages.map(message => ({
              ...message,
              timestamp: new Date(message.timestamp),
            })),
          }))
        }
      },
    }
  )
)
