/**
 * 인증 상태 관리 스토어 (Zustand)
 */
import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface User {
  id: number
  email: string
  name: string
  role: 'admin' | 'mentor' | 'mentee'
  team?: string
  team_number?: string
  employee_number?: string
  interests?: string | string[]
  photo_url?: string
  phone?: string
  extension?: string
  hobbies?: string
  mbti?: string
}

interface AuthState {
  user: User | null
  token: string | null
  refreshToken: string | null
  isAuthenticated: boolean
  login: (token: string, refreshToken: string, user: User) => void
  logout: () => void
  updateUser: (user: User) => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      token: null,
      refreshToken: null,
      isAuthenticated: false,
      
      login: (token, refreshToken, user) => {
        set({
          user,
          token,
          refreshToken,
          isAuthenticated: true,
        })
      },
      
      logout: () => {
        // 챗봇 히스토리 로컬 스토리지 삭제
        try {
          localStorage.removeItem('chat-library-storage')
        } catch (error) {
          console.log('챗봇 스토리지 삭제 실패:', error)
        }
        
        set({
          user: null,
          token: null,
          refreshToken: null,
          isAuthenticated: false,
        })
      },
      
      updateUser: (user) => {
        set({ user })
      },
    }),
    {
      name: 'auth-storage',
    }
  )
)





