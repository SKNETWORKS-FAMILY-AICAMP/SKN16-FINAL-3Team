/**
 * 채팅 라이브러리 사이드바 컴포넌트
 * ChatGPT 스타일의 대화 세션 관리 UI
 */
import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { 
  PlusIcon,
  TrashIcon,
  PencilIcon,
  CheckIcon,
  XMarkIcon,
  FolderIcon,
  EllipsisVerticalIcon,
  ArrowDownTrayIcon,
  ClockIcon
} from '@heroicons/react/24/outline'
import { useChatStore, ChatSession, ChatMessage } from '../store/chatStore'
import { chatAPI } from '../utils/api'

interface ChatSidebarProps {
  isOpen: boolean
  onClose: () => void
}

export default function ChatSidebar({ isOpen, onClose }: ChatSidebarProps) {
  const {
    sessions,
    currentSessionId,
    createSession,
    deleteSession,
    updateSessionTitle,
    setActiveSession,
    clearSession,
  } = useChatStore()

  const [editingSessionId, setEditingSessionId] = useState<string | null>(null)
  const [editTitle, setEditTitle] = useState('')
  const [hoveredSessionId, setHoveredSessionId] = useState<string | null>(null)
  const [isLoadingHistory, setIsLoadingHistory] = useState(false)
  const [serverHistoryCount, setServerHistoryCount] = useState<number | null>(null)
  const [isHistoryVisible, setIsHistoryVisible] = useState(false) // 히스토리 표시 여부
  const [loadedHistoryIds, setLoadedHistoryIds] = useState<Set<string>>(new Set()) // 불러온 히스토리 ID 추적

  const handleCreateSession = () => {
    createSession()
  }

  const handleDeleteSession = (sessionId: string, e: React.MouseEvent) => {
    e.stopPropagation()
    deleteSession(sessionId)
  }

  const handleEditStart = (session: ChatSession, e: React.MouseEvent) => {
    e.stopPropagation()
    setEditingSessionId(session.id)
    setEditTitle(session.title)
  }

  const handleEditSave = () => {
    if (editingSessionId && editTitle.trim()) {
      updateSessionTitle(editingSessionId, editTitle.trim())
    }
    setEditingSessionId(null)
    setEditTitle('')
  }

  const handleEditCancel = () => {
    setEditingSessionId(null)
    setEditTitle('')
  }

  const handleSessionClick = (sessionId: string) => {
    setActiveSession(sessionId)
    onClose() // 사이드바 닫기
  }

  const formatDate = (date: Date) => {
    const now = new Date()
    const diffTime = Math.abs(now.getTime() - date.getTime())
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24))

    if (diffDays === 1) return '오늘'
    if (diffDays === 2) return '어제'
    if (diffDays <= 7) return `${diffDays}일 전`
    
    return date.toLocaleDateString('ko-KR', {
      month: 'short',
      day: 'numeric'
    })
  }

  const truncateTitle = (title: string, maxLength: number = 30) => {
    return title.length > maxLength ? title.substring(0, maxLength) + '...' : title
  }

  // 서버 히스토리 개수 확인 (사이드바 열릴 때)
  useEffect(() => {
    const checkHistoryCount = async () => {
      try {
        const history = await chatAPI.getHistory(1)
        // 히스토리가 있으면 표시 (정확한 개수는 알 수 없으므로 있음/없음만 표시)
        if (history && history.length > 0) {
          setServerHistoryCount(history.length) // 최소 1개 이상 있다는 의미
        } else {
          setServerHistoryCount(null)
        }
      } catch (error) {
        console.error('히스토리 개수 확인 실패:', error)
        setServerHistoryCount(null)
      }
    }
    if (isOpen) {
      checkHistoryCount()
    }
  }, [isOpen])

  // 서버에서 대화 히스토리 불러오기/숨기기 토글
  const handleLoadHistory = async () => {
    // 이미 히스토리가 표시되어 있으면 숨기기
    if (isHistoryVisible) {
      // 불러온 히스토리 세션들 제거
      const { sessions: currentSessions } = useChatStore.getState()
      const filteredSessions = currentSessions.filter(s => !loadedHistoryIds.has(s.id))
      
      useChatStore.setState({
        sessions: filteredSessions,
        currentSessionId: currentSessionId && !loadedHistoryIds.has(currentSessionId) 
          ? currentSessionId 
          : (filteredSessions.length > 0 ? filteredSessions[0].id : null)
      })
      
      setLoadedHistoryIds(new Set())
      setIsHistoryVisible(false)
      return
    }
    
    // 히스토리 불러오기
    setIsLoadingHistory(true)
    try {
      const history = await chatAPI.getHistory(20) // 최근 20개 불러오기
      
      if (history && history.length > 0) {
        const newHistoryIds = new Set<string>()
        
        // 각 히스토리 항목을 세션으로 변환
        history.forEach((item: any) => {
          const sessionId = `history_${item.created_at || Date.now()}`
          
          // 이미 존재하는 세션인지 확인
          const existingSession = sessions.find(s => s.id === sessionId)
          if (existingSession) {
            newHistoryIds.add(sessionId)
            return
          }
          
          // 히스토리 항목을 메시지로 변환
          const messages: ChatMessage[] = [
            {
              id: `user_${item.created_at}`,
              text: item.user_message || '',
              isBot: false,
              timestamp: new Date(item.created_at),
            },
            {
              id: `bot_${item.created_at}`,
              text: item.bot_response || '',
              isBot: true,
              sources: item.sources || [],
              timestamp: new Date(item.created_at),
            }
          ]
          
          // 세션 제목 생성 (사용자 메시지의 첫 부분)
          const title = item.user_message 
            ? (item.user_message.length > 30 
                ? item.user_message.substring(0, 30) + '...' 
                : item.user_message)
            : '불러온 대화'
          
          // 새 세션 생성
          const newSession: ChatSession = {
            id: sessionId,
            title: title,
            messages: messages,
            createdAt: new Date(item.created_at),
            updatedAt: new Date(item.created_at),
            isActive: false,
          }
          
          // 세션 추가 (중복 방지)
          const { sessions: currentSessions } = useChatStore.getState()
          if (!currentSessions.find(s => s.id === sessionId)) {
            useChatStore.setState({
              sessions: [newSession, ...currentSessions],
            })
            newHistoryIds.add(sessionId)
          }
        })
        
        // 불러온 히스토리 ID 저장
        setLoadedHistoryIds(newHistoryIds)
        setIsHistoryVisible(true)
        
        // 불러온 히스토리 개수 업데이트
        const loadedCount = history.length
        setServerHistoryCount(loadedCount)
        
        // 성공 메시지 (선택사항)
        if (loadedCount > 0) {
          console.log(`✅ ${loadedCount}개의 대화 히스토리를 불러왔습니다.`)
        }
      }
    } catch (error) {
      console.error('히스토리 불러오기 실패:', error)
      alert('대화 히스토리를 불러오는데 실패했습니다.')
    } finally {
      setIsLoadingHistory(false)
    }
  }

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* 오버레이 */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 bg-black/50 z-40"
          />

          {/* 사이드바 */}
          <motion.div
            initial={{ x: -320 }}
            animate={{ x: 0 }}
            exit={{ x: -320 }}
            transition={{ type: 'tween', duration: 0.2 }}
            className="fixed left-0 top-0 w-80 h-full bg-white shadow-2xl z-50 flex flex-col"
          >
            {/* 헤더 */}
            <div className="p-4 border-b border-gray-200">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold text-gray-800">채팅 라이브러리</h2>
                <button
                  onClick={onClose}
                  className="p-1 hover:bg-gray-100 rounded-lg transition-colors"
                >
                  <XMarkIcon className="w-5 h-5 text-gray-500" />
                </button>
              </div>
              
              <button
                onClick={handleCreateSession}
                className="w-full flex items-center justify-center space-x-2 px-4 py-3 bg-gradient-to-r from-primary-600 to-primary-500 text-white rounded-xl hover:from-primary-700 hover:to-primary-600 transition-all duration-200 shadow-md hover:shadow-lg"
              >
                <PlusIcon className="w-5 h-5" />
                <span>새 대화</span>
              </button>
            </div>

            {/* 세션 목록 */}
            <div className="flex-1 overflow-y-auto">
              {sessions.length === 0 ? (
                <div className="p-6 text-center text-gray-500">
                  <FolderIcon className="w-12 h-12 mx-auto mb-3 text-gray-300" />
                  <p className="text-sm">아직 대화가 없어요</p>
                  <p className="text-xs text-gray-400 mt-1">새 대화를 시작해보세요!</p>
                </div>
              ) : (
                <div className="p-2 space-y-1">
                  {sessions.map((session) => (
                    <motion.div
                      key={session.id}
                      whileHover={{ scale: 1.02 }}
                      className={`relative group p-3 rounded-xl cursor-pointer transition-all duration-200 ${
                        currentSessionId === session.id
                          ? 'bg-gradient-to-r from-primary-50 to-amber-50 border border-primary-200'
                          : 'hover:bg-gray-50 border border-transparent'
                      }`}
                      onClick={() => handleSessionClick(session.id)}
                      onMouseEnter={() => setHoveredSessionId(session.id)}
                      onMouseLeave={() => setHoveredSessionId(null)}
                    >
                      {/* 세션 제목 */}
                      <div className="flex items-start justify-between">
                        <div className="flex-1 min-w-0">
                          {editingSessionId === session.id ? (
                            <div className="flex items-center space-x-2">
                              <input
                                type="text"
                                value={editTitle}
                                onChange={(e) => setEditTitle(e.target.value)}
                                onKeyDown={(e) => {
                                  if (e.key === 'Enter') handleEditSave()
                                  if (e.key === 'Escape') handleEditCancel()
                                }}
                                className="flex-1 px-2 py-1 text-sm border border-gray-300 rounded focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                                autoFocus
                              />
                              <button
                                onClick={handleEditSave}
                                className="p-1 text-green-600 hover:bg-green-50 rounded"
                              >
                                <CheckIcon className="w-4 h-4" />
                              </button>
                              <button
                                onClick={handleEditCancel}
                                className="p-1 text-red-600 hover:bg-red-50 rounded"
                              >
                                <XMarkIcon className="w-4 h-4" />
                              </button>
                            </div>
                          ) : (
                            <h3 className="text-sm font-medium text-gray-800 truncate">
                              {truncateTitle(session.title)}
                            </h3>
                          )}
                          
                          <p className="text-xs text-gray-500 mt-1">
                            {formatDate(session.updatedAt)}
                          </p>
                        </div>

                        {/* 액션 버튼들 */}
                        <AnimatePresence>
                          {hoveredSessionId === session.id && !editingSessionId && (
                            <motion.div
                              initial={{ opacity: 0, scale: 0.8 }}
                              animate={{ opacity: 1, scale: 1 }}
                              exit={{ opacity: 0, scale: 0.8 }}
                              className="flex items-center space-x-1"
                            >
                              <button
                                onClick={(e) => handleEditStart(session, e)}
                                className="p-1 text-gray-400 hover:text-primary-600 hover:bg-primary-50 rounded transition-colors"
                                title="제목 수정"
                              >
                                <PencilIcon className="w-4 h-4" />
                              </button>
                              <button
                                onClick={(e) => handleDeleteSession(session.id, e)}
                                className="p-1 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded transition-colors"
                                title="삭제"
                              >
                                <TrashIcon className="w-4 h-4" />
                              </button>
                            </motion.div>
                          )}
                        </AnimatePresence>
                      </div>

                      {/* 활성 표시 */}
                      {currentSessionId === session.id && (
                        <div className="absolute left-0 top-0 bottom-0 w-1 bg-gradient-to-b from-primary-600 to-primary-500 rounded-r-full"></div>
                      )}
                    </motion.div>
                  ))}
                </div>
              )}
            </div>

            {/* 푸터 */}
            <div className="p-4 border-t border-gray-200 space-y-3">
              {/* 서버 히스토리 불러오기/숨기기 토글 */}
              <button
                onClick={handleLoadHistory}
                disabled={isLoadingHistory}
                className={`w-full flex items-center justify-center space-x-2 px-4 py-2.5 rounded-lg transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed border ${
                  isHistoryVisible
                    ? 'bg-primary-50 hover:bg-primary-100 text-primary-700 border-primary-200'
                    : 'bg-gray-50 hover:bg-gray-100 text-gray-700 border-gray-200'
                }`}
              >
                {isLoadingHistory ? (
                  <>
                    <div className="w-4 h-4 border-2 border-gray-400 border-t-transparent rounded-full animate-spin"></div>
                    <span className="text-sm font-medium">불러오는 중...</span>
                  </>
                ) : isHistoryVisible ? (
                  <>
                    <XMarkIcon className="w-4 h-4" />
                    <span className="text-sm font-medium">히스토리 숨기기</span>
                  </>
                ) : (
                  <>
                    <ArrowDownTrayIcon className="w-4 h-4" />
                    <span className="text-sm font-medium">서버 히스토리 불러오기</span>
                  </>
                )}
              </button>
              
              {/* 통계 정보 */}
              <div className="text-xs text-gray-500 text-center space-y-1">
                <p>총 {sessions.length}개의 대화</p>
                {serverHistoryCount !== null && (
                  <p className="flex items-center justify-center gap-1">
                    <ClockIcon className="w-3 h-3" />
                    서버에 {serverHistoryCount}개 이상 저장됨
                  </p>
                )}
                <p className="text-gray-400">데이터는 브라우저에 저장됩니다</p>
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
