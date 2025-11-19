/**
 * 플로팅 알림봇 컴포넌트
 * 캘린더 일정을 분석하여 사용자에게 알림 제공
 */
import { useState, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { 
  BellIcon,
  XMarkIcon,
  CalendarIcon,
  ClockIcon
} from '@heroicons/react/24/solid'
import { scheduleAPI } from '../utils/api'
import { useAuthStore } from '../store/authStore'

interface Schedule {
  id: number
  title: string
  description?: string
  start_time: string
  end_time?: string
  location?: string
  color?: string
}

interface CommonFreeSlot {
  mentee_id: number
  mentee_name: string
  free_dates: string[]
}

interface NotificationBotProps {
  // 필요시 props 추가
}

export default function NotificationBot(_props?: NotificationBotProps) {
  console.log('🔔🔔🔔 NotificationBot 함수 실행됨!')
  
  const isAuthenticated = useAuthStore((state: { isAuthenticated: boolean }) => state.isAuthenticated)
  const user = useAuthStore((state: { user: any }) => state.user)
  const isMentor = user?.role === 'mentor' || user?.role === 'admin'
  
  const [isOpen, setIsOpen] = useState(false)
  const [schedules, setSchedules] = useState<Schedule[]>([])
  const [upcomingSchedules, setUpcomingSchedules] = useState<Schedule[]>([])
  const [todaySchedules, setTodaySchedules] = useState<Schedule[]>([])
  const [loading, setLoading] = useState(false)
  const [unreadCount, setUnreadCount] = useState(0)
  
  // 점심 약속 추천 알림 관련 상태
  const [lunchNotifications, setLunchNotifications] = useState<CommonFreeSlot[]>([])
  const [showLunchNotification, setShowLunchNotification] = useState(false)
  const [selectedDates, setSelectedDates] = useState<{ [menteeId: number]: string | null }>({})
  const [creatingSchedule, setCreatingSchedule] = useState<{ [menteeId: number]: boolean }>({})

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

  // 일정 로드 함수 (useCallback으로 메모이제이션)
  const loadSchedules = useCallback(async () => {
    // 인증되지 않은 경우 API 호출하지 않음
    if (!isAuthenticated) {
      setSchedules([])
      setLoading(false)
      return
    }
    
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
      // 401, 403 에러는 인증/권한 문제이므로 조용히 처리
      if (error?.response?.status === 401 || error?.response?.status === 403) {
        setSchedules([])
      } else {
        console.error('Error loading schedules:', error?.response?.data || error?.message)
        setSchedules([])
      }
    } finally {
      setLoading(false)
    }
  }, [isAuthenticated])

  // 공통 빈 일정 로드 함수
  const loadCommonFreeSlots = useCallback(async () => {
    if (!isAuthenticated || !isMentor) {
      return
    }
    
    try {
      const data = await scheduleAPI.getCommonFreeSlots()
      if (data?.common_free_slots && data.common_free_slots.length > 0) {
        setLunchNotifications(data.common_free_slots)
        setShowLunchNotification(true)
      } else {
        setLunchNotifications([])
        setShowLunchNotification(false)
      }
    } catch (error: any) {
      console.error('Failed to load common free slots:', error)
      // 401, 403 에러는 인증/권한 문제이므로 조용히 처리
      if (error?.response?.status !== 401 && error?.response?.status !== 403) {
        console.error('Error loading common free slots:', error?.response?.data || error?.message)
        console.error('Error details:', JSON.stringify(error?.response?.data, null, 2))
      }
      setLunchNotifications([])
      setShowLunchNotification(false)
    }
  }, [isAuthenticated, isMentor])

  // 매주 수요일 오후 2시 43분에 체크하는 로직
  useEffect(() => {
    if (!isAuthenticated || !isMentor) {
      return
    }

    // 초기 로드
    loadCommonFreeSlots()

    // 매주 수요일 오후 2시 43분에 체크하는 함수
    const checkWednesdayAfternoon = () => {
      const now = new Date()
      const dayOfWeek = now.getDay() // 0=일요일, 1=월요일, 2=화요일, 3=수요일, ..., 6=토요일
      const hour = now.getHours()
      const minute = now.getMinutes()
      
      // 수요일이고 오후 2시 43분이면 체크
      if (dayOfWeek === 3 && hour === 14 && minute === 43) {
        loadCommonFreeSlots()
      }
    }

    // 매 시간마다 체크 (수요일 오후 2시인지 확인)
    const interval = setInterval(() => {
      checkWednesdayAfternoon()
    }, 60 * 60 * 1000) // 1시간마다

    // 1분마다도 체크 (더 정확한 타이밍을 위해)
    const minuteInterval = setInterval(() => {
      const now = new Date()
      const dayOfWeek = now.getDay()
      const hour = now.getHours()
      const minute = now.getMinutes()
      
      // 수요일 오후 2시 43분~48분 사이면 체크
      if (dayOfWeek === 3 && hour === 14 && minute >= 43 && minute <= 48) {
        loadCommonFreeSlots()
      }
    }, 60000) // 1분마다

    return () => {
      clearInterval(interval)
      clearInterval(minuteInterval)
    }
  }, [isAuthenticated, isMentor, loadCommonFreeSlots])

  // 일정 로드 및 분석
  useEffect(() => {
    // 인증된 경우에만 일정 로드
    if (!isAuthenticated) {
      return
    }
    
    loadSchedules()
    // 1분마다 일정 업데이트
    const interval = setInterval(() => {
      if (isAuthenticated) {
        loadSchedules()
      }
    }, 60000)
    return () => clearInterval(interval)
  }, [isAuthenticated, loadSchedules])

  // 오늘 일정 계산
  useEffect(() => {
    const now = new Date()
    const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 0, 0, 0)
    const todayEnd = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 23, 59, 59)
    
    const today = schedules.filter((schedule: Schedule) => {
      const startTime = new Date(schedule.start_time)
      return startTime >= todayStart && startTime <= todayEnd
    }).sort((a: Schedule, b: Schedule) => {
      return new Date(a.start_time).getTime() - new Date(b.start_time).getTime()
    })

    setTodaySchedules(today)
  }, [schedules])

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

  // 일일 브리핑 메시지 생성
  const getDailyBriefing = (): string => {
    if (todaySchedules.length === 0) {
      // 오늘 이후 가장 빠른 일정 찾기
      const now = new Date()
      const todayEnd = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 23, 59, 59)
      
      const futureSchedules = schedules.filter((schedule: Schedule) => {
        const startTime = new Date(schedule.start_time)
        return startTime > todayEnd
      }).sort((a: Schedule, b: Schedule) => {
        return new Date(a.start_time).getTime() - new Date(b.start_time).getTime()
      })
      
      if (futureSchedules.length > 0) {
        const nextSchedule = futureSchedules[0]
        const nextScheduleDate = new Date(nextSchedule.start_time)
        const nextDate = nextScheduleDate.getDate()
        const nextMonth = nextScheduleDate.getMonth() + 1
        const nextTitle = nextSchedule.title
        
        return `안녕하세요! 오늘은 특별한 일정이 없네요. ${nextMonth}월 ${nextDate}일에 ${nextTitle}이(가) 있어요. 일정을 확인하고, 다가오는 날들을 위해 준비해 보세요! 😊`
      } else {
        return '안녕하세요! 오늘은 일정이 없어요. 즐거운 하루 보내세요! 😊'
      }
    }
    
    // 첫 번째 일정으로 브리핑 생성
    const firstSchedule = todaySchedules[0]
    const scheduleTime = new Date(firstSchedule.start_time)
    const scheduleHour = scheduleTime.getHours()
    const scheduleMinute = scheduleTime.getMinutes()
    
    // 시간 형식: "3시" 또는 "3시 30분"
    const timeStr = scheduleMinute === 0 
      ? `${scheduleHour}시` 
      : `${scheduleHour}시 ${scheduleMinute}분`
    
    // 장소와 제목 조합
    const location = firstSchedule.location || ''
    const title = firstSchedule.title
    const scheduleInfo = location && title 
      ? `${timeStr} ${location} ${title}` 
      : location 
      ? `${timeStr} ${location}` 
      : title 
      ? `${timeStr} ${title}` 
      : timeStr
    
    if (todaySchedules.length === 1) {
      return `안녕하세요! 오늘은 ${scheduleInfo} 일정이 있어요. 즐거운 하루 보내세요!`
    } else {
      return `안녕하세요! 오늘은 ${scheduleInfo} 일정을 포함해 총 ${todaySchedules.length}개의 일정이 있어요. 즐거운 하루 보내세요!`
    }
  }

  // 브리핑 표시 여부 확인 (오전 12시부터 오후 11시 59분 59초까지)
  const shouldShowBriefing = (): boolean => {
    const now = new Date()
    const hour = now.getHours()
    
    // 오전 12시(00:00:00)부터 오후 11시 59분 59초(23:59:59)까지
    // 0시 0분 0초부터 23시 59분 59초까지 모두 포함
    return hour >= 0 && hour < 24
  }

  const handleClose = () => {
    setIsOpen(false)
    setUnreadCount(0) // 알림 패널을 닫으면 읽음 처리
  }

  const handleCloseLunchNotification = () => {
    setShowLunchNotification(false)
  }

  // 날짜 포맷팅 (11/19 형식)
  const formatDate = (dateString: string): string => {
    try {
      const date = new Date(dateString)
      const month = date.getMonth() + 1
      const day = date.getDate()
      return `${month}/${day}`
    } catch (error) {
      return dateString
    }
  }

  // 날짜 선택 핸들러
  const handleDateSelect = async (menteeId: number, menteeName: string, dateString: string) => {
    try {
      setCreatingSchedule(prev => ({ ...prev, [menteeId]: true }))
      
      // 선택한 날짜의 12시~13시로 일정 생성
      const selectedDate = new Date(dateString)
      selectedDate.setHours(12, 0, 0, 0) // 오후 12시
      const startTime = selectedDate.toISOString()
      
      const endDate = new Date(selectedDate)
      endDate.setHours(13, 0, 0, 0) // 오후 1시
      const endTime = endDate.toISOString()
      
      // 일정 생성
      await scheduleAPI.createSchedule({
        title: '멘토-멘티와의 식사',
        description: `${menteeName}님과의 식사`,
        start_time: startTime,
        end_time: endTime,
        color: '#10B981' // 초록색
      })
      
      // 선택한 날짜 저장
      setSelectedDates(prev => ({ ...prev, [menteeId]: dateString }))
      
      // 일정 목록 새로고침
      loadSchedules()
      
      // 성공 메시지 (선택사항)
      console.log(`일정이 생성되었습니다: ${menteeName}님과의 식사 - ${formatDate(dateString)}`)
      
    } catch (error: any) {
      console.error('일정 생성 실패:', error)
      alert('일정 생성에 실패했습니다. 다시 시도해주세요.')
    } finally {
      setCreatingSchedule(prev => ({ ...prev, [menteeId]: false }))
    }
  }

  return (
    <>
      {/* 점심 약속 추천 알림 (화면 하단) */}
      <AnimatePresence>
        {showLunchNotification && lunchNotifications.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 100 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 100 }}
            className="fixed bottom-6 left-1/2 transform -translate-x-1/2 z-[70] max-w-2xl w-full px-4"
          >
            {lunchNotifications.map((notification) => {
              const selectedDate = selectedDates[notification.mentee_id]
              const isCreating = creatingSchedule[notification.mentee_id]
              
              return (
                <motion.div
                  key={notification.mentee_id}
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  className="bg-gradient-to-r from-green-500 to-emerald-600 text-white rounded-xl shadow-2xl p-4 mb-3"
                >
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex-1">
                      <p className="font-semibold text-sm mb-1">
                        멘티 {notification.mentee_name}님과 공통으로 비는 날짜가 있어요!
                      </p>
                      <p className="text-xs text-white/90">
                        → 아래 날짜 중 식사 날짜를 선택해주세요.
                      </p>
                    </div>
                    <button
                      onClick={handleCloseLunchNotification}
                      className="ml-4 p-2 hover:bg-white/20 rounded-lg transition-colors flex-shrink-0"
                    >
                      <XMarkIcon className="w-5 h-5" />
                    </button>
                  </div>
                  
                  {/* 날짜 선택 박스들 */}
                  <div className="flex flex-wrap gap-2 mt-3">
                    {notification.free_dates.map((dateString) => {
                      const isSelected = selectedDate === dateString
                      const isDisabled = isCreating || isSelected
                      
                      return (
                        <button
                          key={dateString}
                          onClick={() => !isDisabled && handleDateSelect(notification.mentee_id, notification.mentee_name, dateString)}
                          disabled={isDisabled}
                          className={`
                            px-4 py-2 rounded-lg font-medium text-sm transition-all
                            ${isSelected 
                              ? 'bg-white text-emerald-600 shadow-lg scale-105' 
                              : isDisabled
                              ? 'bg-white/30 text-white/50 cursor-not-allowed'
                              : 'bg-white/20 text-white hover:bg-white/30 hover:scale-105 active:scale-95'
                            }
                          `}
                        >
                          {isSelected ? (
                            <span className="flex items-center gap-1">
                              <span>✓</span>
                              <span>{formatDate(dateString)}</span>
                            </span>
                          ) : isCreating ? (
                            <span className="flex items-center gap-1">
                              <span className="animate-spin">⏳</span>
                              <span>{formatDate(dateString)}</span>
                            </span>
                          ) : (
                            formatDate(dateString)
                          )}
                        </button>
                      )
                    })}
                  </div>
                  
                  {selectedDate && (
                    <p className="text-xs text-white/80 mt-3 pt-3 border-t border-white/20">
                      ✓ {formatDate(selectedDate)}에 "멘토-멘티와의 식사" 일정이 추가되었습니다.
                    </p>
                  )}
                </motion.div>
              )
            })}
          </motion.div>
        )}
      </AnimatePresence>

      {/* 알림 패널 */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, y: 20, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 20, scale: 0.95 }}
            className="fixed bottom-[230px] right-6 w-72 h-[300px] bg-white rounded-2xl shadow-2xl flex flex-col z-[55]"
          >
            {/* Header */}
            <div className="bg-gradient-to-r from-amber-500 via-amber-400 to-yellow-400 p-3 rounded-t-2xl flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <div className="w-8 h-8 bg-white rounded-full flex items-center justify-center shadow-md">
                  <BellIcon className="w-5 h-5 text-amber-600" />
                </div>
                <div>
                  <h3 className="font-bold text-white text-sm">일정 알림</h3>
                  <p className="text-xs text-white/90">다가오는 일정을 확인하세요 🔔</p>
                </div>
              </div>
              <button
                onClick={handleClose}
                className="text-white hover:bg-white/20 p-1.5 rounded-lg transition-colors"
              >
                <XMarkIcon className="w-4 h-4" />
              </button>
            </div>

            {/* 일일 브리핑 */}
            {shouldShowBriefing() && (
              <div className="px-3 pt-3 pb-2">
                <motion.div
                  initial={{ opacity: 0, y: -10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="bg-gradient-to-r from-blue-500 to-indigo-600 text-white rounded-xl p-3 shadow-lg"
                >
                  <p className="text-xs leading-relaxed font-medium">
                    {getDailyBriefing()}
                  </p>
                </motion.div>
              </div>
            )}

            {/* 알림 목록 */}
            <div className="flex-1 overflow-y-auto p-3 space-y-2">
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
                    className="bg-gradient-to-r from-amber-50 to-yellow-50 rounded-lg p-3 border border-amber-200 hover:shadow-md transition-shadow"
                  >
                    <div className="flex items-start space-x-2">
                      <div
                        className="w-2.5 h-2.5 rounded-full mt-1.5 flex-shrink-0"
                        style={{ backgroundColor: schedule.color || '#F59E0B' }}
                      />
                      <div className="flex-1 min-w-0">
                        <h4 className="font-semibold text-gray-800 mb-1 truncate text-sm">
                          {schedule.title}
                        </h4>
                        <div className="flex items-center space-x-1.5 text-xs text-gray-600 mb-1">
                          <ClockIcon className="w-3.5 h-3.5" />
                          <span className="text-xs">{formatDateTime(schedule.start_time)}</span>
                          <span className="text-amber-600 font-medium text-xs">
                            ({getTimeUntil(schedule.start_time)})
                          </span>
                        </div>
                        {schedule.location && (
                          <p className="text-xs text-gray-500 mt-0.5">
                            📍 {schedule.location}
                          </p>
                        )}
                        {schedule.description && (
                          <p className="text-xs text-gray-600 mt-1 line-clamp-1">
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
            <div className="p-3 border-t border-amber-100 bg-amber-50 rounded-b-2xl">
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

