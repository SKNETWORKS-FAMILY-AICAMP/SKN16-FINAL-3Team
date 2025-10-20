/**
 * API 클라이언트
 * Axios 기반 HTTP 요청 처리
 */
import axios, { AxiosError } from 'axios'
import { useAuthStore } from '../store/authStore'

// Docker 환경에서는 Vite의 proxy를 통해 /api로 접근
// 로컬 개발 환경에서는 http://localhost:8000 사용
const API_URL = import.meta.env.VITE_API_URL || '/api'

// Axios 인스턴스 생성
export const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// 요청 인터셉터: 토큰 자동 추가
api.interceptors.request.use(
  (config) => {
    const token = useAuthStore.getState().token
    console.log('API request interceptor - token:', token ? 'present' : 'missing')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    console.log('API request config:', {
      url: config.url,
      method: config.method,
      headers: config.headers
    })
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 응답 인터셉터: 에러 처리
api.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    console.error('API Error:', error)
    
    if (error.response?.status === 401) {
      // 토큰 만료 시 로그아웃
      useAuthStore.getState().logout()
      window.location.href = '/login'
    } else if (error.code === 'ECONNREFUSED' || error.code === 'NETWORK_ERROR') {
      // 네트워크 에러 처리
      console.error('Network error - server may be down')
    }
    
    return Promise.reject(error)
  }
)

// API 함수들

// 인증
export const authAPI = {
  login: async (email: string, password: string) => {
    const formData = new FormData()
    formData.append('username', email)
    formData.append('password', password)
    const response = await api.post('/auth/login', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return response.data
  },
  
  register: async (userData: any) => {
    const response = await api.post('/auth/register', userData)
    return response.data
  },
  
  getCurrentUser: async () => {
    const response = await api.get('/auth/me')
    return response.data
  },
  
  updateProfile: async (userData: any) => {
    const response = await api.put('/auth/me', userData)
    return response.data
  },

  uploadProfilePhoto: async (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    const response = await api.post('/auth/me/photo', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return response.data
  },

  resetProfilePhoto: async () => {
    const response = await api.delete('/auth/me/photo')
    return response.data
  },
  
  findId: async (name: string, employeeNumber: string) => {
    const response = await api.post('/auth/find-id', null, {
      params: { name, employee_number: employeeNumber }
    })
    return response.data
  },
  
  resetPassword: async (email: string, employeeNumber: string, newPassword: string) => {
    const response = await api.post('/auth/reset-password', null, {
      params: { 
        email, 
        employee_number: employeeNumber,
        new_password: newPassword
      }
    })
    return response.data
  },
  
  qrLogin: async (qrData: string) => {
    const response = await api.post('/auth/qr-login', null, {
      params: { qr_data: qrData }
    })
    return response.data
  },
}

// 챗봇
export const chatAPI = {
  sendMessage: async (message: string) => {
    const response = await api.post('/chat/', { message })
    return response.data
  },
  
  getHistory: async (limit: number = 10) => {
    const response = await api.get(`/chat/history?limit=${limit}`)
    return response.data
  },
  
  provideFeedback: async (chatId: number, isHelpful: boolean) => {
    const response = await api.post(`/chat/feedback/${chatId}`, { is_helpful: isHelpful })
    return response.data
  },
}

// 문서
export const documentAPI = {
  getDocuments: async (category?: string) => {
    const params = category ? `?category=${encodeURIComponent(category)}` : ''
    const response = await api.get(`/documents/${params}`)
    return response.data
  },
  
  getDocument: async (id: number) => {
    const response = await api.get(`/documents/${id}`)
    return response.data
  },
  
  uploadDocument: async (file: File, title: string, category: string, description?: string) => {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('title', title)
    formData.append('category', category)
    if (description) formData.append('description', description)
    
    const response = await api.post('/documents/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return response.data
  },

  uploadDocumentsBulk: async (files: File[], category: string, description?: string) => {
    const formData = new FormData()
    files.forEach((file) => formData.append('files', file))
    formData.append('category', category)
    if (description) formData.append('description', description)

    const response = await api.post('/documents/upload-bulk', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return response.data
  },
  
  downloadDocument: async (id: number) => {
    const response = await api.get(`/documents/${id}/download`, {
      responseType: 'blob',
    })
    return response.data
  },
  
  deleteDocument: async (id: number) => {
    const response = await api.delete(`/documents/${id}`)
    return response.data
  },
  
  getCategories: async () => {
    const response = await api.get('/documents/categories/list')
    return response.data
  },
  
  getRecentDocuments: async (limit: number = 3) => {
    const response = await api.get(`/documents/recent?limit=${limit}`)
    return response.data
  },
}

// 게시판
export const postAPI = {
  getPosts: async (skip: number = 0, limit: number = 20) => {
    console.log('postAPI.getPosts called with:', { skip, limit })
    console.log('API base URL:', API_URL)
    const response = await api.get(`/posts/?skip=${skip}&limit=${limit}`)
    console.log('postAPI.getPosts response:', response.data)
    return response.data
  },
  
  getPost: async (id: number) => {
    const response = await api.get(`/posts/${id}`)
    return response.data
  },
  
  createPost: async (title: string, content: string) => {
    const response = await api.post('/posts/', { title, content })
    return response.data
  },
  
  deletePost: async (id: number) => {
    const response = await api.delete(`/posts/${id}`)
    return response.data
  },
  
  createComment: async (postId: number, content: string) => {
    const response = await api.post('/posts/comments', { post_id: postId, content })
    return response.data
  },
  
  deleteComment: async (id: number) => {
    const response = await api.delete(`/posts/comments/${id}`)
    return response.data
  },

  // 꿀추/꿀통 시스템
  likePost: async (postId: number) => {
    const response = await api.post(`/posts/${postId}/like`)
    return response.data
  },

  unlikePost: async (postId: number) => {
    const response = await api.delete(`/posts/${postId}/like`)
    return response.data
  },

  dislikePost: async (postId: number) => {
    const response = await api.post(`/posts/${postId}/dislike`)
    return response.data
  },

  undislikePost: async (postId: number) => {
    const response = await api.delete(`/posts/${postId}/dislike`)
    return response.data
  },

  // 댓글 꿀추/꿀통 시스템
  likeComment: async (commentId: number) => {
    const response = await api.post(`/posts/comments/${commentId}/like`)
    return response.data
  },

  unlikeComment: async (commentId: number) => {
    const response = await api.delete(`/posts/comments/${commentId}/like`)
    return response.data
  },

  dislikeComment: async (commentId: number) => {
    const response = await api.post(`/posts/comments/${commentId}/dislike`)
    return response.data
  },

  undislikeComment: async (commentId: number) => {
    const response = await api.delete(`/posts/comments/${commentId}/dislike`)
    return response.data
  },

  // 인기 게시글 (기존 기능 유지)
  getPopularPosts: async (limit: number = 3) => {
    const response = await api.get(`/posts/popular?limit=${limit}`)
    return response.data
  },
}

// 대시보드
export const dashboardAPI = {
  getMenteeDashboard: async () => {
    const response = await api.get('/dashboard/mentee')
    return response.data
  },
  
  getMentorDashboard: async () => {
    const response = await api.get('/dashboard/mentor')
    return response.data
  },

  // 동료의 새로운 매칭 관련 API들
  getMatchingDashboard: async () => {
    const response = await api.get('/dashboard/matching')
    return response.data
  },
  
  assignMentor: async (menteeId: number, mentorId: number, notes: string = '') => {
    const response = await api.post('/dashboard/assign-mentor', { 
      mentee_id: menteeId, 
      mentor_id: mentorId,
      notes
    })
    return response.data
  },

  unassignMentor: async (relationIdOrMenteeId: number) => {
    // 멘토 화면에서는 menteeId만 전달되므로 mentor 전용 해제 API 호출
    try {
      const response = await api.post('/dashboard/mentor/unassign', { mentee_id: relationIdOrMenteeId })
      return response.data
    } catch (e) {
      // 혹시 관리자 화면에서 호출될 수 있으니 기존 관리자용 엔드포인트도 fallback
      const response = await api.delete(`/dashboard/mentor-relations/${relationIdOrMenteeId}`)
      return response.data
    }
  },

  // mentorUnassign는 unassignMentor로 통합

  getAvailableMentees: async () => {
    const response = await api.get('/dashboard/mentor/available-mentees')
    return response.data
  },

  selectMentee: async (menteeId: number) => {
    const response = await api.post('/dashboard/mentor/select-mentee', { mentee_id: menteeId })
    return response.data
  },

  // 일괄 시험 결과 처리 (관리자 전용)
  processBulkExamResults: async () => {
    const response = await api.post('/dashboard/bulk-exam-results')
    return response.data
  },
  
  addExamScore: async (menteeId: number, examName: string, scoreData: any, totalScore: number, grade?: string) => {
    const response = await api.post('/dashboard/exam-score', {
      mentee_id: menteeId,
      exam_name: examName,
      score_data: scoreData,
      total_score: totalScore,
      grade,
    })
    return response.data
  },
  
  // 피드백 관련 API
  createFeedback: async (menteeId: number, feedbackText: string, feedbackType: string = 'general') => {
    const response = await api.post('/dashboard/feedback', {
      mentee_id: menteeId,
      feedback_text: feedbackText,
      feedback_type: feedbackType
    })
    return response.data
  },
  
  getFeedbacksForMentee: async (menteeId: number) => {
    const response = await api.get(`/dashboard/feedback/${menteeId}`)
    return response.data
  },
  
  getMenteeFeedbacks: async () => {
    const response = await api.get('/dashboard/mentee/feedbacks')
    return response.data
  },
  
  markFeedbackAsRead: async (feedbackId: number) => {
    const response = await api.put(`/dashboard/feedback/${feedbackId}/read`)
    return response.data
  },
  
  // 댓글 관련 API
  getComments: async (feedbackId: number) => {
    const response = await api.get(`/dashboard/feedback/${feedbackId}/comments`)
    return response.data
  },
  
  createComment: async (feedbackId: number, commentText: string) => {
    const response = await api.post(`/dashboard/feedback/${feedbackId}/comments`, {
      comment_text: commentText
    })
    return response.data
  },
  
  deleteComment: async (commentId: number) => {
    const response = await api.delete(`/dashboard/feedback/comments/${commentId}`)
    return response.data
  },

}

// 관리자 API
export const adminAPI = {
  // 통계
  getStats: async () => {
    const response = await api.get('/admin/stats')
    return response.data
  },
  
  // 사용자 관리
  getAllUsers: async (skip: number = 0, limit: number = 100, role?: string, search?: string) => {
    const params = new URLSearchParams({
      skip: skip.toString(),
      limit: limit.toString()
    })
    if (role) params.append('role', role)
    if (search) params.append('search', search)
    
    const response = await api.get(`/admin/users?${params}`)
    return response.data
  },
  
  updateUserRole: async (userId: number, newRole: string) => {
    const response = await api.post(`/admin/users/${userId}/role`, { new_role: newRole })
    return response.data
  },
  
  // 멘토-멘티 관계 관리
  getMentorMenteeRelations: async (skip: number = 0, limit: number = 100, isActive?: boolean) => {
    const params = new URLSearchParams({
      skip: skip.toString(),
      limit: limit.toString()
    })
    if (isActive !== undefined) params.append('is_active', isActive.toString())
    
    const response = await api.get(`/admin/mentor-mentee-relations?${params}`)
    return response.data
  },
  
  createMentorMenteeRelation: async (mentorId: number, menteeId: number, notes?: string) => {
    const response = await api.post('/admin/mentor-mentee-relations', {
      mentor_id: mentorId,
      mentee_id: menteeId,
      notes
    })
    return response.data
  },
  
  deactivateMentorMenteeRelation: async (relationId: number) => {
    const response = await api.delete(`/admin/mentor-mentee-relations/${relationId}`)
    return response.data
  },
  
  // 학습 이력 관리
  getLearningHistory: async (
    userId?: number,
    startDate?: string,
    endDate?: string,
    skip: number = 0,
    limit: number = 100
  ) => {
    const params = new URLSearchParams({
      skip: skip.toString(),
      limit: limit.toString()
    })
    if (userId) params.append('user_id', userId.toString())
    if (startDate) params.append('start_date', startDate)
    if (endDate) params.append('end_date', endDate)
    
    const response = await api.get(`/admin/learning-history?${params}`)
    return response.data
  },
  
  // 문서 관리
  getAllDocuments: async (skip: number = 0, limit: number = 100, category?: string) => {
    const params = new URLSearchParams({
      skip: skip.toString(),
      limit: limit.toString()
    })
    if (category) params.append('category', category)
    
    const response = await api.get(`/admin/documents?${params}`)
    return response.data
  },
  
  // 시스템 로그
  getSystemLogs: async (
    logType?: string,
    startDate?: string,
    endDate?: string,
    skip: number = 0,
    limit: number = 100
  ) => {
    const params = new URLSearchParams({
      skip: skip.toString(),
      limit: limit.toString()
    })
    if (logType) params.append('log_type', logType)
    if (startDate) params.append('start_date', startDate)
    if (endDate) params.append('end_date', endDate)
    
    const response = await api.get(`/admin/system-logs?${params}`)
    return response.data
  },
}

export default api

