/**
 * 플로팅 알림봇 컴포넌트
 * 캘린더 일정을 분석하여 사용자에게 알림 제공
 */
import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { 
  BellIcon,
  XMarkIcon,
  CalendarIcon,
  ClockIcon
} from '@heroicons/react/24/solid'
import { scheduleAPI } from '../utils/api'

interface Schedule {
  id: number
  title: string
  description?: string
  start_time: string
  end_time?: string
  location?: string
  color?: string
}

interface NotificationBotProps {
  // 필요시 props 추가
}

export default function NotificationBot(_props?: NotificationBotProps) {
  console.log('🔔🔔🔔 NotificationBot 함수 실행됨!')
  
  const [isOpen, setIsOpen] = useState(false)
  const [schedules, setSchedules] = useState<Schedule[]>([])
  const [upcomingSchedules, setUpcomingSchedules] = useState<Schedule[]>([])
  const [loading, setLoading] = useState(false)
  const [unreadCount, setUnreadCount] = useState(0)

  // 디버깅: 컴포넌트 렌더링 확인
  useEffect(() => {
    console.log('═══════════════════════════════════════')
    console.log('🔔 NotificationBot 컴포넌트 마운트됨!')
    console.log('📍 위치: bottom-[94px], right-6')
    console.log('📊 unreadCount:', unreadCount)
    console.log('═══════════════════════════════════════')
    return () => {
      console.log('🔔 NotificationBot 컴포넌트 언마운트됨')
    }
  }, [])

  // 일정 로드 및 분석
  useEffect(() => {
    loadSchedules()
    // 1분마다 일정 업데이트
    const interval = setInterval(() => {
      loadSchedules()
    }, 60000)
    return () => clearInterval(interval)
  }, [])

  // 다가오는 일정 계산
  useEffect(() => {
    const now = new Date()
    const next24Hours = new Date(now.getTime() + 24 * 60 * 60 * 1000)
    
    const upcoming = schedules.filter((schedule: Schedule) => {
      const startTime = new Date(schedule.start_time)
      return startTime >= now && startTime <= next24Hours
    }).sort((a: Schedule, b: Schedule) => {
      return new Date(a.start_time).getTime() - new Date(b.start_time).getTime()
    })

    setUpcomingSchedules(upcoming)
    
    // 읽지 않은 알림 개수 업데이트 (24시간 이내 일정)
    setUnreadCount(upcoming.length)
  }, [schedules])

  const loadSchedules = async () => {
    try {
      setLoading(true)
      const today = new Date()
      const nextWeek = new Date(today.getTime() + 7 * 24 * 60 * 60 * 1000)
      
      const startDate = today.toISOString().split('T')[0]
      const endDate = nextWeek.toISOString().split('T')[0]
      
      const data = await scheduleAPI.getSchedules(startDate, endDate)
      setSchedules(data || [])
    } catch (error: any) {
      console.error('Failed to load schedules:', error)
      // 403 에러는 멘티가 아닌 경우이므로 조용히 처리
      if (error?.response?.status !== 403) {
        console.error('Error loading schedules:', error?.response?.data || error?.message)
      }
      setSchedules([])
    } finally {
      setLoading(false)
    }
  }

  const formatDateTime = (dateTimeString: string): string => {
    if (!dateTimeString) return ''
    try {
      const date = new Date(dateTimeString)
      if (isNaN(date.getTime())) return ''
      
      const today = new Date()
      const tomorrow = new Date(today)
      tomorrow.setDate(tomorrow.getDate() + 1)
      
      const isToday = date.toDateString() === today.toDateString()
      const isTomorrow = date.toDateString() === tomorrow.toDateString()
      
      const hours = date.getHours()
      const minutes = String(date.getMinutes()).padStart(2, '0')
      const ampm = hours >= 12 ? '오후' : '오전'
      const displayHours = hours % 12 || 12
      const timeStr = `${ampm} ${displayHours}:${minutes}`
      
      if (isToday) {
        return `오늘 ${timeStr}`
      } else if (isTomorrow) {
        return `내일 ${timeStr}`
      } else {
        const month = date.getMonth() + 1
        const day = date.getDate()
        return `${month}/${day} ${timeStr}`
      }
    } catch (error) {
      console.error('Error formatting datetime:', error)
      return ''
    }
  }

  const getTimeUntil = (dateTimeString: string): string => {
    if (!dateTimeString) return ''
    try {
      const scheduleTime = new Date(dateTimeString)
      const now = new Date()
      const diff = scheduleTime.getTime() - now.getTime()
      
      if (diff < 0) return '지난 일정'
      
      const hours = Math.floor(diff / (1000 * 60 * 60))
      const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60))
      
      if (hours > 0) {
        return `${hours}시간 ${minutes}분 후`
      } else if (minutes > 0) {
        return `${minutes}분 후`
      } else {
        return '곧 시작'
      }
    } catch (error) {
      return ''
    }
  }

  const handleClose = () => {
    setIsOpen(false)
    setUnreadCount(0) // 알림 패널을 닫으면 읽음 처리
  }

  return (
    <>
      {/* 알림 패널 */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, y: 20, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 20, scale: 0.95 }}
            className="fixed bottom-[230px] right-6 w-96 h-[500px] bg-white rounded-2xl shadow-2xl flex flex-col z-[55]"
          >
            {/* Header */}
            <div className="bg-gradient-to-r from-amber-500 via-amber-400 to-yellow-400 p-4 rounded-t-2xl flex items-center justify-between">
              <div className="flex items-center space-x-3">
                <div className="w-10 h-10 bg-white rounded-full flex items-center justify-center shadow-md">
                  <BellIcon className="w-6 h-6 text-amber-600" />
                </div>
                <div>
                  <h3 className="font-bold text-white">일정 알림</h3>
                  <p className="text-xs text-white/90">다가오는 일정을 확인하세요 🔔</p>
                </div>
              </div>
              <button
                onClick={handleClose}
                className="text-white hover:bg-white/20 p-2 rounded-lg transition-colors"
              >
                <XMarkIcon className="w-5 h-5" />
              </button>
            </div>

            {/* 알림 목록 */}
            <div className="flex-1 overflow-y-auto p-4 space-y-3">
              {loading ? (
                <div className="flex items-center justify-center h-full">
                  <div className="flex space-x-2">
                    <div className="w-2 h-2 bg-amber-500 rounded-full animate-bounce"></div>
                    <div className="w-2 h-2 bg-amber-500 rounded-full animate-bounce delay-100"></div>
                    <div className="w-2 h-2 bg-amber-500 rounded-full animate-bounce delay-200"></div>
                  </div>
                </div>
              ) : upcomingSchedules.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-full text-gray-400">
                  <CalendarIcon className="w-16 h-16 mb-4 opacity-50" />
                  <p className="text-sm">다가오는 일정이 없습니다</p>
                  <p className="text-xs mt-2">24시간 이내 일정이 여기에 표시됩니다</p>
                </div>
              ) : (
                upcomingSchedules.map((schedule: Schedule) => (
                  <motion.div
                    key={schedule.id}
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    className="bg-gradient-to-r from-amber-50 to-yellow-50 rounded-xl p-4 border border-amber-200 hover:shadow-md transition-shadow"
                  >
                    <div className="flex items-start space-x-3">
                      <div
                        className="w-3 h-3 rounded-full mt-2 flex-shrink-0"
                        style={{ backgroundColor: schedule.color || '#F59E0B' }}
                      />
                      <div className="flex-1 min-w-0">
                        <h4 className="font-semibold text-gray-800 mb-1 truncate">
                          {schedule.title}
                        </h4>
                        <div className="flex items-center space-x-2 text-xs text-gray-600 mb-1">
                          <ClockIcon className="w-4 h-4" />
                          <span>{formatDateTime(schedule.start_time)}</span>
                          <span className="text-amber-600 font-medium">
                            ({getTimeUntil(schedule.start_time)})
                          </span>
                        </div>
                        {schedule.location && (
                          <p className="text-xs text-gray-500 mt-1">
                            📍 {schedule.location}
                          </p>
                        )}
                        {schedule.description && (
                          <p className="text-xs text-gray-600 mt-2 line-clamp-2">
                            {schedule.description}
                          </p>
                        )}
                      </div>
                    </div>
                  </motion.div>
                ))
              )}
            </div>

            {/* Footer */}
            <div className="p-4 border-t border-amber-100 bg-amber-50 rounded-b-2xl">
              <p className="text-xs text-center text-gray-600">
                총 {upcomingSchedules.length}개의 일정이 24시간 이내에 시작됩니다
              </p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* 플로팅 버튼 */}
      <motion.button
        whileHover={{ scale: 1.1 }}
        whileTap={{ scale: 0.9 }}
        onClick={() => {
          console.log('🔔 알림봇 버튼 클릭됨')
          if (isOpen) {
            handleClose()
          } else {
            setIsOpen(true)
          }
        }}
        className="fixed bottom-[94px] right-6 w-16 h-16 bg-gradient-to-br from-primary-600 to-primary-700 text-white rounded-full shadow-lg flex items-center justify-center z-[60] hover:shadow-xl transition-shadow relative"
        style={{ 
          position: 'fixed',
          bottom: '94px',
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
            <BellIcon className="w-8 h-8" />
            {unreadCount > 0 && (
              <motion.div
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                className="absolute -top-1 -right-1 w-6 h-6 bg-red-500 rounded-full flex items-center justify-center text-xs font-bold text-white shadow-md"
              >
                {unreadCount > 9 ? '9+' : unreadCount}
              </motion.div>
            )}
          </>
        )}
      </motion.button>
    </>
  )
}

