/**
 * 플로팅 피드봇 컴포넌트
 * 멘토 피드백을 표시하는 플로팅 봇
 */
import React, { useState, useEffect, useCallback, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { 
  XMarkIcon,
} from '@heroicons/react/24/solid'
import { dashboardAPI } from '../utils/api'
import { useAuthStore } from '../store/authStore'

interface FeedbackBotProps {
  // 필요시 props 추가
}

// 피드봇 아이콘 SVG 컴포넌트 (사람 + 말풍선)
const FeedbackBotIcon = ({ className = "w-8 h-8" }: { className?: string }) => (
  <svg 
    className={className} 
    viewBox="0 0 64 64" 
    fill="none" 
    xmlns="http://www.w3.org/2000/svg"
  >
    {/* 사람 아이콘 - 머리 (원) */}
    <circle cx="18" cy="18" r="7" fill="currentColor" />
    {/* 사람 아이콘 - 어깨와 상체 (둥근 사다리꼴) */}
    <path 
      d="M10 32 C10 26, 12 24, 18 24 C24 24, 26 26, 26 32 L26 38 C26 40, 24 42, 18 42 C12 42, 10 40, 10 38 Z" 
      fill="currentColor"
    />
    
    {/* 말풍선 */}
    <rect 
      x="32" 
      y="12" 
      width="24" 
      height="20" 
      rx="4" 
      fill="currentColor"
    />
    {/* 말풍선 꼬리 (사람을 향함) */}
    <path 
      d="M32 20 L28 24 L32 24 Z" 
      fill="currentColor"
    />
    
    {/* 말풍선 안의 점들 (타이핑 표시) - 가로로 3개 */}
    <circle cx="40" cy="20" r="2.5" fill="white" />
    <circle cx="46" cy="20" r="2.5" fill="white" />
    <circle cx="52" cy="20" r="2.5" fill="white" />
  </svg>
)

export default function FeedbackBot(_props?: FeedbackBotProps) {
  const isAuthenticated = useAuthStore((state: { isAuthenticated: boolean }) => state.isAuthenticated)
  const user = useAuthStore((state: { user: any }) => state.user)
  const isMentor = user?.role === 'mentor' || user?.role === 'admin'
  
  const [isOpen, setIsOpen] = useState(false)
  const [feedbacks, setFeedbacks] = useState<any[]>([])
  const [loadingFeedbacks, setLoadingFeedbacks] = useState(false)
  const [unreadFeedbackCount, setUnreadFeedbackCount] = useState(0)
  
  // 크기 조절 상태
  const [botSize, setBotSize] = useState(() => {
    const saved = localStorage.getItem('feedbackbot-size')
    return saved ? JSON.parse(saved) : { width: 288, height: 300 }
  })
  const [isResizing, setIsResizing] = useState(false)
  const resizeRef = useRef<HTMLDivElement>(null)
  
  // 위치 상태
  const [botPosition, setBotPosition] = useState(() => {
    const saved = localStorage.getItem('feedbackbot-position')
    return saved ? JSON.parse(saved) : { x: null, y: null } // null이면 기본 위치 사용
  })
  const [isDragging, setIsDragging] = useState(false)
  const dragStartPos = useRef({ x: 0, y: 0, offsetX: 0, offsetY: 0 })

  // 피드백 로드 (멘티용)
  const loadFeedbacks = useCallback(async () => {
    if (!isAuthenticated || isMentor || !user) {
      return
    }
    
    try {
      setLoadingFeedbacks(true)
      const data = await dashboardAPI.getMenteeFeedbacks()
      setFeedbacks(data || [])
      
      // 읽지 않은 피드백 개수 계산
      const unread = (data || []).filter((fb: any) => !fb.is_read).length
      setUnreadFeedbackCount(unread)
    } catch (error) {
      console.error('피드백 로드 실패:', error)
      setFeedbacks([])
    } finally {
      setLoadingFeedbacks(false)
    }
  }, [isAuthenticated, isMentor, user])

  // 피드백 로드 (알림 패널이 열릴 때)
  useEffect(() => {
    if (isOpen && !isMentor) {
      loadFeedbacks()
    }
  }, [isOpen, isMentor, loadFeedbacks])

  // 주기적으로 피드백 확인 (30초마다)
  useEffect(() => {
    if (!isAuthenticated || isMentor) {
      return
    }

    // 초기 로드
    loadFeedbacks()

    // 30초마다 업데이트
    const interval = setInterval(() => {
      loadFeedbacks()
    }, 30000)

    return () => clearInterval(interval)
  }, [isAuthenticated, isMentor, loadFeedbacks])

  // 피드백 읽음 처리
  const markFeedbackAsRead = async (feedbackId: number) => {
    try {
      await dashboardAPI.markFeedbackAsRead(feedbackId)
      // 피드백 목록 업데이트
      setFeedbacks(prev => 
        prev.map(fb => 
          fb.id === feedbackId ? { ...fb, is_read: true } : fb
        )
      )
      setUnreadFeedbackCount(prev => Math.max(0, prev - 1))
    } catch (error) {
      console.error('피드백 읽음 처리 실패:', error)
    }
  }

  const handleClose = () => {
    setIsOpen(false)
  }

  // 리사이즈 핸들러
  const startPosRef = useRef({ x: 0, y: 0, width: 0, height: 0, handleType: '', startLeft: 0, startTop: 0 })
  
  useEffect(() => {
    if (!isResizing) return

    const handleMouseMove = (e: MouseEvent) => {
      // 정방향 delta 계산
      const deltaX = e.clientX - startPosRef.current.x
      const deltaY = e.clientY - startPosRef.current.y
      
      let widthDelta = 0
      let heightDelta = 0
      
      // 핸들 타입에 따라 delta 적용
      const handleType = startPosRef.current.handleType
      
      if (handleType === 'top-right') {
        // 우상단: 오른쪽/위로 드래그하면 크기 증가
        widthDelta = deltaX
        heightDelta = -deltaY
      } else if (handleType === 'bottom-left') {
        // 좌하단: 왼쪽/아래로 드래그하면 크기 증가
        widthDelta = -deltaX
        heightDelta = deltaY
      } else if (handleType === 'bottom-right') {
        // 우하단: 오른쪽/아래로 드래그하면 크기 증가
        widthDelta = deltaX
        heightDelta = deltaY
      } else if (handleType === 'left') {
        // 왼쪽: 왼쪽으로 드래그하면 크기 증가
        widthDelta = -deltaX
      } else if (handleType === 'top') {
        // 위쪽: 위로 드래그하면 크기 증가
        heightDelta = -deltaY
      } else if (handleType === 'right') {
        // 오른쪽: 오른쪽으로 드래그하면 크기 증가
        widthDelta = deltaX
      } else if (handleType === 'bottom') {
        // 아래쪽: 아래로 드래그하면 크기 증가
        heightDelta = deltaY
      }
      
      const newWidth = startPosRef.current.width + widthDelta
      const newHeight = startPosRef.current.height + heightDelta
      
      // 최소/최대 크기 제한
      const width = Math.max(240, Math.min(600, newWidth))
      const height = Math.max(200, Math.min(window.innerHeight - 200, newHeight))
      
      setBotSize({ width, height })
    }

    const handleMouseUp = () => {
      setIsResizing(false)
      // 크기를 localStorage에 저장
      localStorage.setItem('feedbackbot-size', JSON.stringify(botSize))
    }

    document.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseup', handleMouseUp)

    return () => {
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
    }
  }, [isResizing, botSize])

  // 리사이즈 시작
  const handleResizeStart = (e: React.MouseEvent, handleType: string) => {
    e.preventDefault()
    e.stopPropagation()
    const rect = resizeRef.current?.getBoundingClientRect()
    if (!rect) return
    
    startPosRef.current = {
      x: e.clientX,
      y: e.clientY,
      width: botSize.width,
      height: botSize.height,
      handleType: handleType, // 핸들 타입 저장
      startLeft: rect.left,
      startTop: rect.top
    }
    setIsResizing(true)
  }

  // 드래그 시작
  const handleDragStart = (e: React.MouseEvent) => {
    if (isResizing) return // 리사이즈 중이면 드래그 안 함
    // 버튼이나 링크 클릭 시 드래그 안 함
    const target = e.target as HTMLElement
    if (target.closest('button') || target.closest('a')) {
      return
    }
    
    e.preventDefault()
    e.stopPropagation()
    
    const rect = resizeRef.current?.getBoundingClientRect()
    if (!rect) return
    
    dragStartPos.current = {
      x: e.clientX,
      y: e.clientY,
      offsetX: e.clientX - rect.left,
      offsetY: e.clientY - rect.top
    }
    setIsDragging(true)
  }

  // 드래그 핸들러
  useEffect(() => {
    if (!isDragging) return

    const handleMouseMove = (e: MouseEvent) => {
      const newX = e.clientX - dragStartPos.current.offsetX
      const newY = e.clientY - dragStartPos.current.offsetY
      
      // 화면 경계 체크
      const maxX = window.innerWidth - botSize.width
      const maxY = window.innerHeight - botSize.height
      
      const clampedX = Math.max(0, Math.min(maxX, newX))
      const clampedY = Math.max(0, Math.min(maxY, newY))
      
      const newPosition = { x: clampedX, y: clampedY }
      setBotPosition(newPosition)
      // 실시간으로 위치 저장
      localStorage.setItem('feedbackbot-position', JSON.stringify(newPosition))
    }

    const handleMouseUp = () => {
      setIsDragging(false)
    }

    document.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseup', handleMouseUp)

    return () => {
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
    }
  }, [isDragging, botSize.width, botSize.height])

  // 멘토는 피드봇을 표시하지 않음
  if (isMentor || !isAuthenticated) {
    return null
  }

  return (
    <>
      {/* 피드백 패널 */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            ref={resizeRef}
            initial={{ opacity: 0, y: 20, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 20, scale: 0.95 }}
            style={{ 
              width: `${botSize.width}px`, 
              height: `${botSize.height}px`,
              ...(botPosition.x !== null && botPosition.y !== null
                ? { left: `${botPosition.x}px`, top: `${botPosition.y}px`, bottom: 'auto', right: 'auto' }
                : { bottom: '230px', right: '24px' }
              )
            }}
            className={`fixed bg-white rounded-2xl shadow-2xl flex flex-col z-[55] ${isResizing || isDragging ? 'select-none' : ''}`}
          >
            {/* 리사이즈 핸들 - 좌하단 */}
            <div
              onMouseDown={(e) => handleResizeStart(e, 'bottom-left')}
              className="absolute -bottom-1 -left-1 w-4 h-4 cursor-nesw-resize hover:bg-primary-400 bg-primary-300 rounded-full opacity-0 hover:opacity-100 transition-opacity z-50"
              title="크기 조절"
            />
            
            {/* 리사이즈 핸들 - 우상단 */}
            <div
              onMouseDown={(e) => handleResizeStart(e, 'top-right')}
              className="absolute -top-1 -right-1 w-4 h-4 cursor-nesw-resize hover:bg-primary-400 bg-primary-300 rounded-full opacity-0 hover:opacity-100 transition-opacity z-50"
              title="크기 조절"
            />
            
            {/* 리사이즈 핸들 - 우하단 */}
            <div
              onMouseDown={(e) => handleResizeStart(e, 'bottom-right')}
              className="absolute -bottom-1 -right-1 w-4 h-4 cursor-nwse-resize hover:bg-primary-400 bg-primary-300 rounded-full opacity-0 hover:opacity-100 transition-opacity z-50"
              title="크기 조절"
            />
            
            {/* 리사이즈 핸들 - 왼쪽 */}
            <div
              onMouseDown={(e) => handleResizeStart(e, 'left')}
              className="absolute top-1/2 -translate-y-1/2 -left-1 w-3 h-12 cursor-ew-resize hover:bg-primary-400 bg-primary-300 rounded-r-full opacity-0 hover:opacity-100 transition-opacity z-50"
              title="크기 조절"
            />
            
            {/* 리사이즈 핸들 - 위쪽 */}
            <div
              onMouseDown={(e) => handleResizeStart(e, 'top')}
              className="absolute left-1/2 -translate-x-1/2 -top-1 h-3 w-12 cursor-ns-resize hover:bg-primary-400 bg-primary-300 rounded-b-full opacity-0 hover:opacity-100 transition-opacity z-50"
              title="크기 조절"
            />
            
            {/* 리사이즈 핸들 - 오른쪽 */}
            <div
              onMouseDown={(e) => handleResizeStart(e, 'right')}
              className="absolute top-1/2 -translate-y-1/2 -right-1 w-3 h-12 cursor-ew-resize hover:bg-primary-400 bg-primary-300 rounded-l-full opacity-0 hover:opacity-100 transition-opacity z-50"
              title="크기 조절"
            />
            
            {/* 리사이즈 핸들 - 아래쪽 */}
            <div
              onMouseDown={(e) => handleResizeStart(e, 'bottom')}
              className="absolute left-1/2 -translate-x-1/2 -bottom-1 h-3 w-12 cursor-ns-resize hover:bg-primary-400 bg-primary-300 rounded-t-full opacity-0 hover:opacity-100 transition-opacity z-50"
              title="크기 조절"
            />
            
            {/* 리사이즈 안내 오버레이 */}
            {isResizing && (
              <div className="absolute inset-0 bg-primary-500/10 backdrop-blur-sm flex items-center justify-center rounded-2xl z-40 pointer-events-none">
                <div className="bg-white/90 px-6 py-3 rounded-xl shadow-lg">
                  <p className="text-sm font-medium text-gray-700">
                    {botSize.width} × {botSize.height}
                  </p>
                </div>
              </div>
            )}
            {/* Header */}
            <div 
              onMouseDown={handleDragStart}
              className="bg-gradient-to-r from-primary-600 via-primary-500 to-amber-500 p-3 rounded-t-2xl cursor-move"
            >
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center space-x-2">
                  <div className="w-8 h-8 bg-white rounded-full flex items-center justify-center shadow-md">
                    <FeedbackBotIcon className="w-5 h-5 text-primary-600" />
                  </div>
                  <div>
                    <h3 className="font-bold text-white text-sm">피드봇</h3>
                    <p className="text-xs text-white/90">멘토 피드백을 확인하세요 💬</p>
                  </div>
                </div>
                <button
                  onClick={handleClose}
                  className="text-white hover:bg-white/20 p-1.5 rounded-lg transition-colors"
                >
                  <XMarkIcon className="w-4 h-4" />
                </button>
              </div>
            </div>

            {/* 피드백 목록 */}
            <div className="flex-1 overflow-y-auto p-3 space-y-2">
              {loadingFeedbacks ? (
                <div className="flex items-center justify-center h-full">
                  <div className="flex space-x-2">
                    <div className="w-2 h-2 bg-primary-500 rounded-full animate-bounce"></div>
                    <div className="w-2 h-2 bg-primary-500 rounded-full animate-bounce delay-100"></div>
                    <div className="w-2 h-2 bg-primary-500 rounded-full animate-bounce delay-200"></div>
                  </div>
                </div>
              ) : feedbacks.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-full text-gray-400">
                  <FeedbackBotIcon className="w-16 h-16 mb-4 opacity-50 text-gray-300" />
                  <p className="text-sm">받은 피드백이 없습니다</p>
                  <p className="text-xs mt-2">멘토님의 피드백이 여기에 표시됩니다</p>
                </div>
              ) : (
                feedbacks.map((feedback: any) => (
                  <motion.div
                    key={feedback.id}
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    onClick={() => !feedback.is_read && markFeedbackAsRead(feedback.id)}
                    className={`bg-gradient-to-r rounded-lg p-3 border cursor-pointer hover:shadow-md transition-shadow ${
                      feedback.is_read
                        ? 'from-gray-50 to-gray-100 border-gray-200'
                        : 'from-primary-50 to-amber-50 border-primary-200'
                    }`}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-xs font-semibold text-gray-700">
                            {feedback.mentor_name || '멘토'}님의 피드백
                          </span>
                          {!feedback.is_read && (
                            <span className="w-2 h-2 bg-red-500 rounded-full"></span>
                          )}
                        </div>
                        <p className="text-xs text-gray-600 line-clamp-3 mb-2">
                          {feedback.feedback_text}
                        </p>
                        <div className="flex items-center justify-between">
                          <p className="text-xs text-gray-400">
                            {new Date(feedback.created_at).toLocaleDateString('ko-KR', {
                              month: 'short',
                              day: 'numeric',
                              hour: '2-digit',
                              minute: '2-digit'
                            })}
                          </p>
                          {feedback.feedback_type && (
                            <span className="text-xs px-2 py-0.5 rounded-full bg-primary-100 text-primary-700">
                              {feedback.feedback_type === 'general' ? '일반' : 
                               feedback.feedback_type === 'exam' ? '시험' : 
                               feedback.feedback_type === 'simulation' ? '시뮬레이션' : '피드백'}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  </motion.div>
                ))
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* 플로팅 버튼 */}
      <motion.button
        onClick={() => setIsOpen(!isOpen)}
        whileHover={{ scale: 1.1 }}
        whileTap={{ scale: 0.9 }}
        className="fixed bottom-[170px] right-6 w-16 h-16 bg-gradient-to-r from-primary-600 via-primary-500 to-amber-500 text-white rounded-full shadow-2xl flex items-center justify-center hover:shadow-primary-500/50 transition-shadow z-[60]"
        style={{
          position: 'fixed',
          bottom: '170px',
          right: '24px',
          width: '64px',
          height: '64px',
          zIndex: 60
        }}
      >
        {isOpen ? (
          <XMarkIcon className="w-8 h-8" />
        ) : (
          <>
            <FeedbackBotIcon className="w-8 h-8 text-white" />
            {unreadFeedbackCount > 0 && (
              <motion.div
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                className="absolute -top-1 -right-1 w-6 h-6 bg-red-500 rounded-full flex items-center justify-center text-xs font-bold text-white shadow-md"
              >
                {unreadFeedbackCount > 9 ? '9+' : unreadFeedbackCount}
              </motion.div>
            )}
          </>
        )}
      </motion.button>
    </>
  )
}

