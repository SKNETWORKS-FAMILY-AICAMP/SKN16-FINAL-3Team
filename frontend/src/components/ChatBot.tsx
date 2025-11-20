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
  Bars3Icon
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
  const [isSidebarOpen, setIsSidebarOpen] = useState(false)
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  
  // 챗봇 크기 조절 상태
  const [chatSize, setChatSize] = useState(() => {
    const saved = localStorage.getItem('chatbot-size')
    return saved ? JSON.parse(saved) : { width: 384, height: 600 }
  })
  const [isResizing, setIsResizing] = useState(false)
  const resizeRef = useRef<HTMLDivElement>(null)

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
  const startPosRef = useRef({ x: 0, y: 0, width: 0, height: 0 })
  
  useEffect(() => {
    if (!isResizing) return

    const handleMouseMove = (e: MouseEvent) => {
      const deltaX = startPosRef.current.x - e.clientX
      const deltaY = startPosRef.current.y - e.clientY
      
      const newWidth = startPosRef.current.width + deltaX
      const newHeight = startPosRef.current.height + deltaY
      
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
  const handleResizeStart = (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    startPosRef.current = {
      x: e.clientX,
      y: e.clientY,
      width: chatSize.width,
      height: chatSize.height
    }
    setIsResizing(true)
  }

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

  const handleSourceClick = (sourceTitle: string) => {
    // "RAG - " 접두사 제거
    const cleanTitle = sourceTitle.replace('RAG - ', '')
    // 자료실로 이동하면서 검색어를 URL 파라미터로 전달
    navigate(`/documents?search=${encodeURIComponent(cleanTitle)}`)
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
              height: `${chatSize.height}px` 
            }}
            className={`fixed bottom-24 right-6 bg-white rounded-2xl shadow-2xl flex flex-col z-40 ${isResizing ? 'select-none' : ''}`}
          >
            {/* 리사이즈 핸들 - 좌상단 */}
            <div
              onMouseDown={handleResizeStart}
              className="absolute -top-1 -left-1 w-4 h-4 cursor-nwse-resize hover:bg-primary-400 bg-primary-300 rounded-full opacity-0 hover:opacity-100 transition-opacity z-50"
              title="크기 조절"
            />
            
            {/* 리사이즈 핸들 - 좌하단 */}
            <div
              onMouseDown={handleResizeStart}
              className="absolute -bottom-1 -left-1 w-4 h-4 cursor-nesw-resize hover:bg-primary-400 bg-primary-300 rounded-full opacity-0 hover:opacity-100 transition-opacity z-50"
              title="크기 조절"
            />
            
            {/* 리사이즈 핸들 - 우상단 */}
            <div
              onMouseDown={handleResizeStart}
              className="absolute -top-1 -right-1 w-4 h-4 cursor-nesw-resize hover:bg-primary-400 bg-primary-300 rounded-full opacity-0 hover:opacity-100 transition-opacity z-50"
              title="크기 조절"
            />
            
            {/* 리사이즈 핸들 - 우하단 */}
            <div
              onMouseDown={handleResizeStart}
              className="absolute -bottom-1 -right-1 w-4 h-4 cursor-nwse-resize hover:bg-primary-400 bg-primary-300 rounded-full opacity-0 hover:opacity-100 transition-opacity z-50"
              title="크기 조절"
            />
            
            {/* 리사이즈 핸들 - 왼쪽 */}
            <div
              onMouseDown={handleResizeStart}
              className="absolute top-1/2 -translate-y-1/2 -left-1 w-3 h-12 cursor-ew-resize hover:bg-primary-400 bg-primary-300 rounded-r-full opacity-0 hover:opacity-100 transition-opacity z-50"
              title="크기 조절"
            />
            
            {/* 리사이즈 핸들 - 위쪽 */}
            <div
              onMouseDown={handleResizeStart}
              className="absolute left-1/2 -translate-x-1/2 -top-1 h-3 w-12 cursor-ns-resize hover:bg-primary-400 bg-primary-300 rounded-b-full opacity-0 hover:opacity-100 transition-opacity z-50"
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
              className="bg-gradient-to-r from-primary-600 via-primary-500 to-amber-500 p-4 rounded-t-2xl flex items-center justify-between"
              onDoubleClick={() => {
                const defaultSize = { width: 384, height: 600 }
                setChatSize(defaultSize)
                localStorage.setItem('chatbot-size', JSON.stringify(defaultSize))
              }}
              title="더블클릭하여 기본 크기로 리셋"
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
                        <ReactMarkdown
                          remarkPlugins={[remarkGfm]}
                          components={{
                            p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
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
                          {message.text}
                        </ReactMarkdown>
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
                          return uniqueSources.slice(0, 3).map((source, idx) => (
                            <p 
                              key={idx} 
                              className="text-xs text-blue-600 hover:text-blue-800 cursor-pointer hover:underline"
                              onClick={() => handleSourceClick(source.title)}
                            >
                              • {source.title.replace('RAG - ', '')}
                            </p>
                          ));
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
        className="fixed bottom-6 right-6 w-16 h-16 bg-gradient-to-br from-primary-600 to-primary-700 text-white rounded-full shadow-lg flex items-center justify-center z-50 hover:shadow-xl transition-shadow"
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



