/**
 * 플로팅 챗봇 컴포넌트
 * RAG 기반 AI 챗봇 with 채팅 라이브러리
 */
import { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import { 
  ChatBubbleLeftRightIcon, 
  XMarkIcon, 
  PaperAirplaneIcon,
  SparklesIcon,
  Bars3Icon,
  BookOpenIcon
} from '@heroicons/react/24/solid'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { chatAPI } from '../utils/api'
import { useChatStore, ChatMessage } from '../store/chatStore'
import { useAuthStore } from '../store/authStore'
import ChatSidebar from './ChatSidebar'

interface ChatBotProps {
  forceOpen?: boolean
  onClose?: () => void
}

export default function ChatBot({ forceOpen = false, onClose }: ChatBotProps = {}) {
  const navigate = useNavigate()
  const [isOpen, setIsOpen] = useState(false)
  const [expandedSchedules, setExpandedSchedules] = useState<{ [key: string]: boolean }>({})
  const [isSidebarOpen, setIsSidebarOpen] = useState(false)
  const [isGuideOpen, setIsGuideOpen] = useState(false)
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  
  // 챗봇 크기 조절 상태
  const [chatSize, setChatSize] = useState(() => {
    const saved = localStorage.getItem('chatbot-size')
    return saved ? JSON.parse(saved) : { width: 384, height: 600 }
  })
  const [isResizing, setIsResizing] = useState(false)
  const resizeRef = useRef<HTMLDivElement>(null)
  
  // 챗봇 위치 상태
  const [chatPosition, setChatPosition] = useState(() => {
    const saved = localStorage.getItem('chatbot-position')
    return saved ? JSON.parse(saved) : { x: null, y: null } // null이면 기본 위치 사용
  })
  const [isDragging, setIsDragging] = useState(false)
  const dragStartPos = useRef({ x: 0, y: 0, offsetX: 0, offsetY: 0 })

  const {
    sessions,
    currentSessionId,
    createSession,
    addMessage,
    setActiveSession,
    setUserId,
  } = useChatStore()
  
  const { user } = useAuthStore()

  // 현재 활성 세션의 메시지들
  const currentSession = sessions.find(s => s.id === currentSessionId)
  const messages = currentSession?.messages || []

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

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
      
      if (handleType === 'top-left') {
        // 좌상단: 왼쪽/위로 드래그하면 크기 증가
        widthDelta = -deltaX
        heightDelta = -deltaY
      } else if (handleType === 'top-right') {
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
      const width = Math.max(320, Math.min(800, newWidth))
      const height = Math.max(400, Math.min(window.innerHeight - 150, newHeight))
      
      setChatSize({ width, height })
    }

    const handleMouseUp = () => {
      setIsResizing(false)
      // 크기를 localStorage에 저장
      localStorage.setItem('chatbot-size', JSON.stringify(chatSize))
    }

    document.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseup', handleMouseUp)

    return () => {
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
    }
  }, [isResizing, chatSize])

  // 리사이즈 시작
  const handleResizeStart = (e: React.MouseEvent, handleType: string) => {
    e.preventDefault()
    e.stopPropagation()
    const rect = resizeRef.current?.getBoundingClientRect()
    if (!rect) return
    
    startPosRef.current = {
      x: e.clientX,
      y: e.clientY,
      width: chatSize.width,
      height: chatSize.height,
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
      const maxX = window.innerWidth - chatSize.width
      const maxY = window.innerHeight - chatSize.height
      
      const clampedX = Math.max(0, Math.min(maxX, newX))
      const clampedY = Math.max(0, Math.min(maxY, newY))
      
      const newPosition = { x: clampedX, y: clampedY }
      setChatPosition(newPosition)
      // 실시간으로 위치 저장
      localStorage.setItem('chatbot-position', JSON.stringify(newPosition))
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
  }, [isDragging, chatSize.width, chatSize.height])

  // 사용자 변경 감지 및 세션 초기화
  useEffect(() => {
    if (user) {
      setUserId(user.id.toString())
    } else {
      setUserId(null)
    }
  }, [user, setUserId])

  // 컴포넌트 마운트 시 기본 세션 생성
  useEffect(() => {
    if (sessions.length === 0) {
      createSession()
    } else if (!currentSessionId) {
      setActiveSession(sessions[0].id)
    }
  }, [sessions.length, currentSessionId, createSession, setActiveSession])

  useEffect(() => {
    if (forceOpen) {
      setIsOpen(true)
    }
  }, [forceOpen])

  // 채팅창이 열렸을 때 입력창에 포커스 주기
  useEffect(() => {
    if (isOpen && !loading) {
      // 약간의 지연을 주어 DOM이 완전히 렌더링된 후 포커스
      const timer = setTimeout(() => {
        inputRef.current?.focus()
      }, 100)
      return () => clearTimeout(timer)
    }
  }, [isOpen, loading])

  const handleClose = () => {
    setIsOpen(false)
    if (onClose) {
      onClose()
    }
  }

  const handleSend = async () => {
    if (!input.trim() || loading || !currentSessionId) return

    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      text: input,
      isBot: false,
      timestamp: new Date(),
    }

    // 사용자 메시지를 현재 세션에 추가
    addMessage(currentSessionId, userMessage)
    setInput('')
    setLoading(true)

    try {
      const response = await chatAPI.sendMessage(input)
      
      const botMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        text: response.answer,
        isBot: true,
        sources: response.sources,
        timestamp: new Date(),
      }

      // 봇 응답을 현재 세션에 추가
      addMessage(currentSessionId, botMessage)
    } catch (error) {
      console.error('Chat error:', error)
      const errorMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        text: '앗, 잠깐만요! 🐻\n일시적인 오류가 발생했어요.\n잠시 후 다시 시도해주세요.',
        isBot: true,
        timestamp: new Date(),
      }
      addMessage(currentSessionId, errorMessage)
    } finally {
      setLoading(false)
      // 입력창에 포커스 다시 주기
      setTimeout(() => {
        inputRef.current?.focus()
      }, 100)
    }
  }

  const handleNewChat = () => {
    createSession()
    setIsSidebarOpen(false)
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleSourceClick = (source: any) => {
    console.log('🔍 [참고자료 클릭] source:', source)
    
    // source가 문자열인 경우 (기존 호환성)
    if (typeof source === 'string') {
      const cleanTitle = source.replace('RAG - ', '')
      navigate(`/documents?search=${encodeURIComponent(cleanTitle)}`)
      return
    }
    
    // source가 객체인 경우
    // 동아리 라운지 게시물인지 확인 (title에 [동아리 라운지]가 포함되어 있거나 type이 post인 경우)
    const isClubPost = source.type === 'post' || 
                       source.title?.includes('[동아리 라운지]') || 
                       source.title?.startsWith('[동아리 라운지]')
    
    if (isClubPost) {
      // 동아리 라운지 게시물인 경우 동아리 라운지 목록 페이지로 이동
      console.log('🔍 [참고자료 클릭] 동아리 라운지 목록으로 이동', source)
      window.location.href = '/board'
    } else {
      // 일반 문서인 경우 자료실로 이동
      const cleanTitle = source.title?.replace('RAG - ', '').replace('[동아리 라운지] ', '') || ''
      navigate(`/documents?search=${encodeURIComponent(cleanTitle)}`)
    }
  }

  return (
    <>
      {/* Chat Window */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            ref={resizeRef}
            initial={{ opacity: 0, y: 20, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 20, scale: 0.95 }}
            style={{ 
              width: `${chatSize.width}px`, 
              height: `${chatSize.height}px`,
              ...(chatPosition.x !== null && chatPosition.y !== null 
                ? { left: `${chatPosition.x}px`, top: `${chatPosition.y}px`, bottom: 'auto', right: 'auto' }
                : { bottom: '96px', right: '24px' }
              )
            }}
            className={`fixed bg-white rounded-2xl shadow-2xl flex flex-col z-40 ${isResizing || isDragging ? 'select-none' : ''}`}
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
                    {chatSize.width} × {chatSize.height}
                  </p>
                </div>
              </div>
            )}

            {/* Header */}
            <div 
              className="bg-gradient-to-r from-primary-600 via-primary-500 to-amber-500 p-4 rounded-t-2xl flex items-center justify-between cursor-move"
              onMouseDown={handleDragStart}
              onDoubleClick={() => {
                const defaultSize = { width: 384, height: 600 }
                setChatSize(defaultSize)
                localStorage.setItem('chatbot-size', JSON.stringify(defaultSize))
              }}
              title="드래그하여 이동, 더블클릭하여 기본 크기로 리셋"
            >
              <div className="flex items-center space-x-3">
                <img src="/assets/bear.png" alt="하경곰" className="w-10 h-10 rounded-full shadow-md" />
                <div>
                  <h3 className="font-bold text-white">AI 하리보</h3>
                  <p className="text-xs text-white/90">온보딩 파트너 🐻</p>
                </div>
              </div>
              <div className="flex items-center space-x-2">
                <button
                  onClick={() => setIsSidebarOpen(true)}
                  className="text-white hover:bg-white/20 p-2 rounded-lg transition-colors"
                  title="채팅 라이브러리"
                >
                  <Bars3Icon className="w-5 h-5" />
                </button>
                <button
                  onClick={handleNewChat}
                  className="text-white hover:bg-white/20 p-2 rounded-lg transition-colors"
                  title="새 대화"
                >
                  <SparklesIcon className="w-5 h-5" />
                </button>
                <button
                  onClick={() => setIsGuideOpen(true)}
                  className="text-white hover:bg-white/20 p-2 rounded-lg transition-colors"
                  title="가이드라인"
                >
                  <BookOpenIcon className="w-5 h-5" />
                </button>
                <button
                  onClick={handleClose}
                  className="text-white hover:bg-white/20 p-2 rounded-lg transition-colors"
                >
                  <XMarkIcon className="w-5 h-5" />
                </button>
              </div>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {messages.map((message) => (
                <div
                  key={message.id}
                  className={`flex ${message.isBot ? 'justify-start' : 'justify-end'}`}
                >
                  <div
                    className={`max-w-[80%] rounded-2xl px-4 py-3 ${
                      message.isBot
                        ? 'bg-gradient-to-r from-primary-50 to-amber-50 text-bank-800 border border-primary-200'
                        : 'bg-gradient-to-r from-primary-600 to-primary-500 text-white shadow-md'
                    }`}
                  >
                    {message.isBot ? (
                      <div className="text-sm markdown-content">
                        {(() => {
                          // 일정 확장 데이터 파싱
                          const expandMatch = message.text.match(/<!-- EXPAND_SCHEDULES:(\d+):(.+?) -->/);
                          let processedText = message.text;
                          let scheduleData: any[] = [];
                          let scheduleCount = 0;
                          
                          if (expandMatch) {
                            scheduleCount = parseInt(expandMatch[1]);
                            try {
                              scheduleData = JSON.parse(expandMatch[2]);
                            } catch (e) {
                              console.error('일정 데이터 파싱 오류:', e);
                            }
                            // HTML 주석 제거
                            processedText = processedText.replace(/<!-- EXPAND_SCHEDULES:.*? -->/g, '');
                          }
                          
                          const isExpanded = expandedSchedules[message.id] || false;
                          const messageKey = message.id;
                          
                          return (
                            <>
                              <ReactMarkdown
                                remarkPlugins={[remarkGfm]}
                                components={{
                                  p: ({ children }) => {
                                    const text = typeof children === 'string' ? children : String(children);
                                    if (text.includes('... 외') && text.includes('개의 일정이 더 있어요')) {
                                      return <p className="mb-2 last:mb-0"></p>;
                                    }
                                    return <p className="mb-2 last:mb-0">{children}</p>;
                                  },
                                  h1: ({ children }) => <h1 className="text-lg font-bold mb-2 mt-3 first:mt-0">{children}</h1>,
                                  h2: ({ children }) => <h2 className="text-base font-bold mb-2 mt-3 first:mt-0">{children}</h2>,
                                  h3: ({ children }) => <h3 className="text-sm font-bold mb-2 mt-3 first:mt-0">{children}</h3>,
                                  ul: ({ children }) => <ul className="list-disc list-inside mb-2 space-y-1">{children}</ul>,
                                  ol: ({ children }) => <ol className="list-decimal list-inside mb-2 space-y-1">{children}</ol>,
                                  li: ({ children }) => <li className="ml-2">{children}</li>,
                                  code: ({ inline, children }) => 
                                    inline ? (
                                      <code className="bg-gray-200 text-gray-800 px-1.5 py-0.5 rounded text-xs font-mono">{children}</code>
                                    ) : (
                                      <code className="block bg-gray-100 text-gray-800 p-2 rounded text-xs font-mono overflow-x-auto mb-2">{children}</code>
                                    ),
                                  pre: ({ children }) => <pre className="mb-2">{children}</pre>,
                                  blockquote: ({ children }) => <blockquote className="border-l-4 border-primary-300 pl-3 italic mb-2">{children}</blockquote>,
                                  a: ({ href, children }) => <a href={href} className="text-primary-600 hover:text-primary-800 underline" target="_blank" rel="noopener noreferrer">{children}</a>,
                                  strong: ({ children }) => <strong className="font-bold">{children}</strong>,
                                  em: ({ children }) => <em className="italic">{children}</em>,
                                  hr: () => <hr className="my-3 border-gray-300" />,
                                  table: ({ children }) => <table className="border-collapse border border-gray-300 mb-2 w-full text-xs">{children}</table>,
                                  th: ({ children }) => <th className="border border-gray-300 bg-gray-100 px-2 py-1 font-bold">{children}</th>,
                                  td: ({ children }) => <td className="border border-gray-300 px-2 py-1">{children}</td>,
                                }}
                              >
                                {processedText.replace(/\.\.\. 외 \d+개의 일정이 더 있어요/g, '')}
                              </ReactMarkdown>
                              {scheduleData.length > 0 && (
                                <>
                                  {processedText.includes('... 외') && (
                                    <button
                                      onClick={() => {
                                        setExpandedSchedules(prev => ({
                                          ...prev,
                                          [messageKey]: !prev[messageKey]
                                        }));
                                      }}
                                      className="mt-2 text-primary-600 hover:text-primary-800 underline text-sm font-medium cursor-pointer"
                                    >
                                      {isExpanded ? '▲ 일정 접기' : `▼ ... 외 ${scheduleCount}개의 일정이 더 있어요`}
                                    </button>
                                  )}
                                  {isExpanded && (
                                    <div className="mt-3 space-y-2 border-t border-gray-200 pt-3">
                                      {scheduleData.map((schedule, idx) => {
                                        const startDate = new Date(schedule.start_time);
                                        const endDate = schedule.end_time ? new Date(schedule.end_time) : null;
                                        const startTimeStr = `${startDate.getMonth() + 1}월 ${startDate.getDate()}일 ${startDate.getHours().toString().padStart(2, '0')}:${startDate.getMinutes().toString().padStart(2, '0')}`;
                                        const scheduleNumber = 6 + idx; // 6번부터 시작
                                        
                                        return (
                                          <div key={idx} className="text-sm">
                                            <div className="font-semibold">{scheduleNumber}. {schedule.title}</div>
                                            <div className="text-gray-600 ml-4">🕐 {startTimeStr}</div>
                                            {schedule.location && (
                                              <div className="text-gray-600 ml-4">📍 {schedule.location}</div>
                                            )}
                                          </div>
                                        );
                                      })}
                                    </div>
                                  )}
                                </>
                              )}
                            </>
                          );
                        })()}
                      </div>
                    ) : (
                      <p className="text-sm whitespace-pre-wrap">{message.text}</p>
                    )}
                    {message.sources && message.sources.length > 0 && (
                      <div className="mt-2 pt-2 border-t border-gray-300">
                        <p className="text-xs text-gray-600 mb-1">참고 자료:</p>
                        {(() => {
                          // 중복 제거 (title 기준)
                          const uniqueSources = message.sources.filter((source, index, self) => 
                            index === self.findIndex(s => s.title === source.title)
                          );
                          return uniqueSources.slice(0, 3).map((source, idx) => {
                            const displayTitle = source.title?.replace('RAG - ', '').replace('[동아리 라운지] ', '') || ''
                            return (
                              <p 
                                key={idx} 
                                className="text-xs text-blue-600 hover:text-blue-800 cursor-pointer hover:underline"
                                onClick={() => handleSourceClick(source)}
                              >
                                • {displayTitle}
                              </p>
                            )
                          });
                        })()}
                      </div>
                    )}
                  </div>
                </div>
              ))}
              {loading && (
                <div className="flex justify-start">
                  <div className="bg-gradient-to-r from-primary-50 to-amber-50 rounded-2xl px-4 py-3 border border-primary-200">
                    <div className="flex items-center space-x-2">
                      <img src="/assets/bear.png" alt="하경곰" className="w-4 h-4 rounded-full" />
                      <div className="flex space-x-1">
                        <div className="w-2 h-2 bg-primary-500 rounded-full animate-bounce"></div>
                        <div className="w-2 h-2 bg-primary-500 rounded-full animate-bounce delay-100"></div>
                        <div className="w-2 h-2 bg-primary-500 rounded-full animate-bounce delay-200"></div>
                      </div>
                    </div>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Input */}
            <div className="p-4 border-t border-primary-100">
              <div className="flex space-x-2">
                <input
                  ref={inputRef}
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyPress={handleKeyPress}
                  placeholder="AI 하리보에게 질문해보세요..."
                  className="flex-1 px-4 py-3 border border-primary-200 rounded-xl focus:ring-2 focus:ring-primary-500 focus:border-transparent bg-white/50 backdrop-blur-sm"
                  disabled={loading}
                />
                <button
                  onClick={handleSend}
                  disabled={loading || !input.trim()}
                  className="p-3 bg-gradient-to-r from-primary-600 to-primary-500 text-white rounded-xl hover:from-primary-700 hover:to-primary-600 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed shadow-md hover:shadow-lg"
                >
                  <PaperAirplaneIcon className="w-5 h-5" />
                </button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* 채팅 라이브러리 사이드바 */}
      <ChatSidebar 
        isOpen={isSidebarOpen} 
        onClose={() => setIsSidebarOpen(false)} 
      />

      {/* 가이드라인 모달 */}
      <AnimatePresence>
        {isGuideOpen && (
          <>
            {/* 오버레이 */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setIsGuideOpen(false)}
              className="fixed inset-0 bg-black/50 z-50"
            />
            
            {/* 모달 */}
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 20 }}
              className="fixed inset-0 z-50 flex items-center justify-center p-4"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="bg-white rounded-2xl shadow-2xl max-w-2xl w-full max-h-[80vh] flex flex-col">
                {/* 헤더 */}
                <div className="bg-gradient-to-r from-primary-600 via-primary-500 to-amber-500 p-6 rounded-t-2xl flex items-center justify-between">
                  <div className="flex items-center space-x-3">
                    <BookOpenIcon className="w-6 h-6 text-white" />
                    <h2 className="text-xl font-bold text-white">가이드라인</h2>
                  </div>
                  <button
                    onClick={() => setIsGuideOpen(false)}
                    className="text-white hover:bg-white/20 p-2 rounded-lg transition-colors"
                  >
                    <XMarkIcon className="w-5 h-5" />
                  </button>
                </div>
                
                {/* 내용 */}
                <div className="flex-1 overflow-y-auto p-6">
                  <div className="space-y-4">
                    <div>
                      <h3 className="text-lg font-semibold text-gray-800 mb-2">AI 하리보 사용 가이드</h3>
                      <p className="text-gray-600">
                        AI 하리보는 하경은행 온보딩 플랫폼에서 여러분의 학습을 도와드리는 AI 파트너입니다.
                      </p>
                    </div>
                    
                    <div>
                      <h4 className="text-base font-semibold text-gray-800 mb-2">💡 질문 예시</h4>
                      <ul className="list-disc list-inside space-y-2 text-gray-600">
                        <li>"학습현황 알려줘"</li>
                        <li>"시뮬레이션 점수는?"</li>
                        <li>"내 약점이 뭐야?"</li>
                        <li>"어떤 공부를 해야 할까?"</li>
                      </ul>
                    </div>
                    
                    <div>
                      <h4 className="text-base font-semibold text-gray-800 mb-2">📚 주요 기능</h4>
                      <ul className="list-disc list-inside space-y-2 text-gray-600">
                        <li>학습현황 분석 및 피드백</li>
                        <li>시뮬레이션 성과 확인</li>
                        <li>맞춤형 학습 추천</li>
                        <li>은행 업무 관련 질문 답변</li>
                      </ul>
                    </div>
                    
                    <div>
                      <h4 className="text-base font-semibold text-gray-800 mb-2">🎯 팁</h4>
                      <ul className="list-disc list-inside space-y-2 text-gray-600">
                        <li>구체적인 질문을 하면 더 정확한 답변을 받을 수 있어요</li>
                        <li>채팅 라이브러리에서 이전 대화를 확인할 수 있어요</li>
                        <li>새 대화 버튼으로 새로운 주제를 시작할 수 있어요</li>
                      </ul>
                    </div>
                  </div>
                </div>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>

      {/* Floating Button */}
      <motion.button
        whileHover={{ scale: 1.1 }}
        whileTap={{ scale: 0.9 }}
        onClick={() => {
          if (isOpen) {
            handleClose()
          } else {
            setIsOpen(true)
          }
        }}
        className="fixed bottom-6 right-6 w-16 h-16 bg-gradient-to-r from-primary-600 via-primary-500 to-amber-500 text-white rounded-full shadow-lg flex items-center justify-center z-50 hover:shadow-xl transition-shadow"
      >
        {isOpen ? (
          <XMarkIcon className="w-8 h-8" />
        ) : (
          <img src="/assets/bear.png" alt="하경곰" className="w-10 h-10 rounded-full" />
        )}
      </motion.button>
    </>
  )
}



