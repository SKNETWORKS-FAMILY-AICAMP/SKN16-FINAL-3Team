/**
 * 플로팅 알림봇 컴포넌트
 * 캘린더 일정을 분석하여 사용자에게 알림 제공
 */
import React, { useState, useEffect, useCallback } from 'react'
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
  
  // 새 일정 알림 관련 상태 (멘티용)
  const [newScheduleNotification, setNewScheduleNotification] = useState<Schedule | null>(null)
  const [showNewScheduleNotification, setShowNewScheduleNotification] = useState(false)
  const [previousScheduleIds, setPreviousScheduleIds] = useState<Set<number>>(new Set())
  
  // Skip 알림 관련 상태
  const [showSkipNotification, setShowSkipNotification] = useState(false)
  const [skipForMentor, setSkipForMentor] = useState(false)
  
  // 알림 확인 상태 (현재 주차 식별용)
  const getCurrentWeekKey = (): string => {
    const now = new Date()
    const dayOfWeek = now.getDay()
    const monday = new Date(now)
    monday.setDate(now.getDate() - dayOfWeek + 1) // 월요일로 이동
    return monday.toISOString().split('T')[0] // YYYY-MM-DD 형식
  }
  
  // 알림이 이미 확인되었는지 체크
  const isNotificationConfirmed = (notificationType: string): boolean => {
    const weekKey = getCurrentWeekKey()
    const key = `${notificationType}_${weekKey}`
    const confirmed = localStorage.getItem(key)
    return confirmed === 'true'
  }
  
  // 알림 확인 처리
  const confirmNotification = (notificationType: string) => {
    const weekKey = getCurrentWeekKey()
    const key = `${notificationType}_${weekKey}`
    localStorage.setItem(key, 'true')
    console.log(`✅ [알림 확인] ${notificationType} - 주차: ${weekKey}`)
  }

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
      // 401, 403 에러는 인증/권한 문제이므로 조용히 처리
      if (error?.response?.status === 401 || error?.response?.status === 403) {
        setSchedules([])
      } else if (error?.response?.status === 500) {
        // 500 에러는 서버 문제이므로 조용히 처리하되 로그만 남김
        console.error('Server error loading schedules:', error?.response?.data || error?.message)
        setSchedules([])
      } else {
        console.error('Error loading schedules:', error?.response?.data || error?.message)
        setSchedules([])
      }
    } finally {
      setLoading(false)
    }
  }, [isAuthenticated])

  // 공통 빈 일정 로드 함수 (멘토에게만)
  const loadCommonFreeSlots = useCallback(async () => {
    // 멘토가 아니면 알림을 로드하지 않음
    if (!isAuthenticated || !isMentor) {
      setLunchNotifications([])
      setShowLunchNotification(false)
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

  // 매주 월요일 오전 9시에 점심 식사 날짜 추천 알림 (멘토에게만)
  useEffect(() => {
    // 멘토가 아니면 알림 체크하지 않음
    if (!isAuthenticated || !isMentor) {
      setLunchNotifications([])
      setShowLunchNotification(false)
      return
    }

    // 이미 확인된 알림이면 표시하지 않음
    if (isNotificationConfirmed('mentor_lunch_recommendation')) {
      console.log('✅ [알림 건너뜀] 멘토 점심 추천 알림이 이미 확인됨')
      setShowLunchNotification(false)
      return
    }

    // 초기 로드
    loadCommonFreeSlots()

    // 매주 월요일 오전 9시에 체크하는 함수
    const checkMondayMorning = () => {
      const now = new Date()
      const dayOfWeek = now.getDay() // 0=일요일, 1=월요일, 2=화요일, ...
      const hour = now.getHours()
      const minute = now.getMinutes()
      
      // 월요일 오전 9시 0~5분 사이면 체크 (확인되지 않은 경우만)
      if (dayOfWeek === 1 && hour === 9 && minute >= 0 && minute <= 5) {
        if (!isNotificationConfirmed('mentor_lunch_recommendation')) {
          console.log('🔔 [월요일 오전 9시] 멘토-멘티 점심 식사 날짜 추천 알림 실행')
          loadCommonFreeSlots()
        }
      }
    }

    // 1분마다 체크 (월요일 오전 9시인지 확인)
    const minuteInterval = setInterval(() => {
      checkMondayMorning()
    }, 60000) // 1분마다

    // 컴포넌트 마운트 시 현재 시간이 월요일 오전 9시대라면 즉시 실행
    const now = new Date()
    if (now.getDay() === 1 && now.getHours() === 9) {
      if (!isNotificationConfirmed('mentor_lunch_recommendation')) {
        console.log('🔔 [컴포넌트 마운트] 현재 월요일 오전 9시 - 즉시 알림 실행')
        loadCommonFreeSlots()
      }
    }

    return () => {
      clearInterval(minuteInterval)
    }
  }, [isAuthenticated, isMentor, loadCommonFreeSlots])

  // 멘티가 Skip 알림 감지 (로컬스토리지 사용)
  useEffect(() => {
    if (!isAuthenticated || isMentor) {
      return
    }
    
    const checkSkipNotification = () => {
      const skipInfo = localStorage.getItem('lunch_skip_notification')
      if (skipInfo) {
        try {
          const parsed = JSON.parse(skipInfo)
          const skipTime = new Date(parsed.timestamp)
          const now = new Date()
          
          // 10초 이내의 알림만 표시하고, 아직 확인하지 않은 경우만
          if (now.getTime() - skipTime.getTime() < 10000) {
            // 이미 확인된 알림이면 표시하지 않음
            if (!isNotificationConfirmed('mentee_skip_notification')) {
              setSkipForMentor(false)
              setShowSkipNotification(true)
            }
          } else {
            // 오래된 알림 삭제
            localStorage.removeItem('lunch_skip_notification')
          }
        } catch (e) {
          console.error('Skip notification parse error:', e)
        }
      }
    }
    
    // 1초마다 체크
    const interval = setInterval(checkSkipNotification, 1000)
    
    return () => clearInterval(interval)
  }, [isAuthenticated, isMentor])

  // 일정 로드 및 분석
  useEffect(() => {
    // 인증된 경우에만 일정 로드
    if (!isAuthenticated) {
      setSchedules([])
      setLoading(false)
      return
    }
    
    // 초기 로드
    loadSchedules()
    
    // 멘티는 10초마다, 멘토는 1분마다 일정 업데이트 (멘티에게 빠른 알림 전달)
    const pollInterval = isMentor ? 60000 : 10000
    const interval = setInterval(() => {
      if (isAuthenticated) {
        loadSchedules()
      }
    }, pollInterval)
    
    return () => {
      clearInterval(interval)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAuthenticated, isMentor])

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

  // 다가오는 일정 계산 및 새 일정 감지
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
    
    // 멘티인 경우, 새로 추가된 일정 감지
    if (!isMentor && schedules.length > 0) {
      const currentScheduleIds = new Set(schedules.map(s => s.id))
      
      // 새로 추가된 일정 찾기
      const newSchedules = schedules.filter(schedule => {
        const isNew = !previousScheduleIds.has(schedule.id)
        const isMealSchedule = schedule.title.includes('멘토-멘티와의 식사') || 
                               schedule.title.includes('식사')
        return isNew && isMealSchedule
      })
      
      // 새 일정이 있으면 알림 표시 (가장 최근 것 하나만)
      if (newSchedules.length > 0 && previousScheduleIds.size > 0) {
        const latestNewSchedule = newSchedules[0]
        setNewScheduleNotification(latestNewSchedule)
        setShowNewScheduleNotification(true)
        
        // 10초 후 자동으로 알림 숨김
        setTimeout(() => {
          setShowNewScheduleNotification(false)
        }, 10000)
      }
      
      setPreviousScheduleIds(currentScheduleIds)
    }
  }, [schedules, isMentor, previousScheduleIds])

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
  const getDailyBriefing = (): React.ReactNode => {
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
        
        return (
          <>
            안녕하세요! 오늘은 특별한 일정이 없네요.{' '}
            <span className="font-bold underline">
              {nextMonth}월 {nextDate}일에 {nextTitle}
            </span>
            이(가) 있어요. 일정을 확인하고, 다가오는 날들을 위해 준비해 보세요! 😊
          </>
        )
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
      return (
        <>
          안녕하세요! 오늘은{' '}
          <span className="font-bold underline">{scheduleInfo}</span>
          {' '}일정이 있어요. 즐거운 하루 보내세요! 😊
        </>
      )
    } else {
      return (
        <>
          안녕하세요! 오늘은{' '}
          <span className="font-bold underline">{scheduleInfo}</span>
          {' '}일정을 포함해 총 {todaySchedules.length}개의 일정이 있어요. 즐거운 하루 보내세요! 😊
        </>
      )
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
  
  // Skip 버튼 핸들러 (멘토가 이번 주 점심 약속 건너뛰기)
  const handleSkipLunch = () => {
    // 멘토 점심 추천 알림 확인 처리
    confirmNotification('mentor_lunch_recommendation')
    
    // 멘토 알림 표시
    setSkipForMentor(true)
    setShowSkipNotification(true)
    setShowLunchNotification(false)
    
    // 5초 후 알림 숨김
    setTimeout(() => {
      setShowSkipNotification(false)
    }, 5000)
    
    // 멘티들에게 알림 보내기 위해 로컬스토리지 사용
    const skipInfo = {
      timestamp: new Date().toISOString(),
      mentor_id: user?.id,
      week: getCurrentWeekKey() // 주차 식별용
    }
    localStorage.setItem('lunch_skip_notification', JSON.stringify(skipInfo))
    
    console.log('🔔 [Skip] 이번 주 점심 약속 건너뛰기')
  }
  
  // 멘토 점심 추천 알림 확인 핸들러
  const handleConfirmLunchRecommendation = () => {
    confirmNotification('mentor_lunch_recommendation')
    setShowLunchNotification(false)
  }
  
  // 멘티 새 일정 알림 확인 핸들러
  const handleConfirmNewSchedule = () => {
    confirmNotification('mentee_new_schedule')
    setShowNewScheduleNotification(false)
  }
  
  // Skip 알림 확인 핸들러 (멘토용)
  const handleConfirmSkipMentor = () => {
    confirmNotification('mentor_skip_notification')
    setShowSkipNotification(false)
  }
  
  // Skip 알림 확인 핸들러 (멘티용)
  const handleConfirmSkipMentee = () => {
    confirmNotification('mentee_skip_notification')
    setShowSkipNotification(false)
    localStorage.removeItem('lunch_skip_notification')
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
      
      console.log(`[일정 생성] 멘티 ID: ${menteeId}, 멘티 이름: ${menteeName}, 날짜: ${dateString}`)
      
      // 멘토-멘티 식사 일정 생성 (멘토와 멘티 모두의 일정에 추가됨)
      const response = await scheduleAPI.createMentorMenteeMealSchedule(
        menteeId,
        dateString,
        '멘토-멘티와의 식사',
        `${menteeName}님과의 식사`
      )
      
      console.log(`[일정 생성 성공] 응답:`, response)
      console.log(`[일정 생성 성공] 멘토 일정 ID: ${response.mentor_schedule_id}, 멘티 일정 ID: ${response.mentee_schedule_id}`)
      
      // 선택한 날짜 저장
      setSelectedDates(prev => ({ ...prev, [menteeId]: dateString }))
      
      // 멘토 점심 추천 알림 확인 처리 (날짜 선택 = 확인으로 간주)
      confirmNotification('mentor_lunch_recommendation')
      setShowLunchNotification(false) // 알림 닫기
      
      // 일정 목록 새로고침 (멘토의 일정)
      await loadSchedules()
      
      // 성공 메시지
      console.log(`일정이 생성되었습니다: ${menteeName}님과의 식사 - ${formatDate(dateString)}`)
      console.log(`[일정 생성 완료] 멘토 일정 ID: ${response.mentor_schedule_id}, 멘티 일정 ID: ${response.mentee_schedule_id}`)
      alert(`${formatDate(dateString)}에 멘토와 멘티 모두의 일정이 추가되었습니다.\n\n멘토 일정 ID: ${response.mentor_schedule_id}\n멘티 일정 ID: ${response.mentee_schedule_id}`)
      
    } catch (error: any) {
      console.error('[일정 생성 실패] 전체 에러:', error)
      console.error('[일정 생성 실패] 에러 응답:', error?.response)
      console.error('[일정 생성 실패] 에러 데이터:', error?.response?.data)
      console.error('[일정 생성 실패] 에러 상태:', error?.response?.status)
      
      let errorMessage = '일정 생성에 실패했습니다. 다시 시도해주세요.'
      
      if (error?.response?.status === 403) {
        errorMessage = '멘토-멘티 관계가 없거나 활성화되지 않았습니다.'
      } else if (error?.response?.status === 404) {
        errorMessage = '멘티를 찾을 수 없습니다.'
      } else if (error?.response?.status === 400) {
        errorMessage = error?.response?.data?.detail || '잘못된 요청입니다.'
      } else if (error?.response?.data?.detail) {
        errorMessage = error.response.data.detail
      }
      
      alert(errorMessage)
    } finally {
      setCreatingSchedule(prev => ({ ...prev, [menteeId]: false }))
    }
  }

  return (
    <>
      {/* Skip 알림 (멘토용 - 화면 하단) */}
      <AnimatePresence>
        {skipForMentor && showSkipNotification && (
          <motion.div
            initial={{ opacity: 0, y: 100 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 100 }}
            className="fixed bottom-6 left-1/2 transform -translate-x-1/2 z-[75] max-w-md w-full px-4"
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              className="bg-gradient-to-r from-gray-500 to-gray-600 text-white rounded-xl shadow-2xl p-5"
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-2xl">⏭️</span>
                    <h3 className="font-bold text-lg">이번 주는 점심 약속을 건너뛰었네요!</h3>
                  </div>
                  <p className="text-sm opacity-90">
                    다음 주엔 꼭 날짜를 정해주세요! 😊
                  </p>
                </div>
                <button
                  onClick={handleConfirmSkipMentor}
                  className="ml-3 p-2 hover:bg-white/20 rounded-lg transition-colors flex-shrink-0"
                >
                  <XMarkIcon className="w-5 h-5" />
                </button>
              </div>
              
              <button
                onClick={handleConfirmSkipMentor}
                className="w-full mt-4 bg-white/20 hover:bg-white/30 text-white font-semibold py-2 px-4 rounded-lg transition-colors"
              >
                확인
              </button>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Skip 알림 (멘티용 - 화면 왼쪽) */}
      <AnimatePresence>
        {!skipForMentor && showSkipNotification && (
          <motion.div
            initial={{ opacity: 0, x: -100 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -100 }}
            className="fixed top-24 left-6 z-[75] max-w-sm w-full"
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              className="bg-gradient-to-br from-gray-500 via-gray-600 to-gray-700 text-white rounded-2xl shadow-2xl p-6 border-2 border-white/30"
            >
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-3">
                  <div className="w-12 h-12 bg-white/20 backdrop-blur-sm rounded-full flex items-center justify-center">
                    <span className="text-3xl">📅</span>
                  </div>
                  <div>
                    <h3 className="font-bold text-xl mb-1">이번 주 점심 약속 없음</h3>
                    <p className="text-sm opacity-90">다음 주를 기대해주세요</p>
                  </div>
                </div>
                <button
                  onClick={() => setShowSkipNotification(false)}
                  className="p-2 hover:bg-white/20 rounded-lg transition-colors flex-shrink-0"
                >
                  <XMarkIcon className="w-5 h-5" />
                </button>
              </div>
              
              <div className="text-center mt-4">
                <p className="font-semibold text-base leading-relaxed">
                  이번 주는 멘토님과 점심 약속이 없습니다
                </p>
              </div>
              
              <button
                onClick={handleConfirmSkipMentee}
                className="w-full mt-4 bg-white/20 hover:bg-white/30 text-white font-semibold py-2 px-4 rounded-lg transition-colors"
              >
                확인
              </button>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* 새 일정 알림 (멘티용 - 화면 왼쪽) */}
      <AnimatePresence>
        {!isMentor && showNewScheduleNotification && newScheduleNotification && (
          <motion.div
            initial={{ opacity: 0, x: -100 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -100 }}
            className="fixed top-24 left-6 z-[75] max-w-sm w-full"
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              className="bg-gradient-to-br from-emerald-500 via-teal-500 to-cyan-600 text-white rounded-2xl shadow-2xl p-6 border-2 border-white/30"
            >
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className="w-12 h-12 bg-white/20 backdrop-blur-sm rounded-full flex items-center justify-center">
                    <span className="text-3xl">🍽️</span>
                  </div>
                  <div>
                    <h3 className="font-bold text-xl mb-1">점심 약속 확정!</h3>
                    <p className="text-sm opacity-90">멘토님이 일정을 추가하셨어요</p>
                  </div>
                </div>
                <button
                  onClick={() => setShowNewScheduleNotification(false)}
                  className="p-2 hover:bg-white/20 rounded-lg transition-colors flex-shrink-0"
                >
                  <XMarkIcon className="w-5 h-5" />
                </button>
              </div>
              
              <div className="bg-white/20 backdrop-blur-sm rounded-xl p-4 mb-3">
                <div className="flex items-center gap-2 mb-2">
                  <CalendarIcon className="w-5 h-5" />
                  <p className="font-bold text-lg">
                    {(() => {
                      const date = new Date(newScheduleNotification.start_time)
                      const month = date.getMonth() + 1
                      const day = date.getDate()
                      const dayNames = ['일요일', '월요일', '화요일', '수요일', '목요일', '금요일', '토요일']
                      const dayName = dayNames[date.getDay()]
                      return `${month}월 ${day}일 ${dayName}`
                    })()}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <ClockIcon className="w-5 h-5" />
                  <p className="font-semibold">
                    {(() => {
                      const date = new Date(newScheduleNotification.start_time)
                      const hours = date.getHours()
                      const minutes = String(date.getMinutes()).padStart(2, '0')
                      const ampm = hours >= 12 ? '오후' : '오전'
                      const displayHours = hours % 12 || 12
                      return `${ampm} ${displayHours}:${minutes}`
                    })()}
                  </p>
                </div>
              </div>
              
              <div className="text-center">
                <p className="font-semibold text-base leading-relaxed">
                  멘토님과 의미있는 시간 보내세요! 💚
                </p>
              </div>
              
              <button
                onClick={handleConfirmNewSchedule}
                className="w-full mt-4 bg-white/20 hover:bg-white/30 text-white font-semibold py-2 px-4 rounded-lg transition-colors"
              >
                확인
              </button>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* 점심 약속 추천 알림 (화면 하단) - 멘토에게만 표시 */}
      <AnimatePresence>
        {isMentor && showLunchNotification && lunchNotifications.length > 0 && (
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
                        🍽️ 이번 주 멘티 {notification.mentee_name}님과 점심 식사 어떠세요?
                      </p>
                      <p className="text-xs text-white/90">
                        → 공통으로 비는 날짜 중 식사 날짜를 선택해주세요.
                      </p>
                    </div>
                    <div className="flex gap-2">
                      <button
                        onClick={handleSkipLunch}
                        className="p-2 hover:bg-white/20 rounded-lg transition-colors flex-shrink-0"
                        title="이번 주 건너뛰기"
                      >
                        <span className="text-lg">⏭️</span>
                      </button>
                      <button
                        onClick={handleCloseLunchNotification}
                        className="p-2 hover:bg-white/20 rounded-lg transition-colors flex-shrink-0"
                      >
                        <XMarkIcon className="w-5 h-5" />
                      </button>
                    </div>
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
                  
                  {/* 확인 버튼 */}
                  <div className="mt-4 pt-3 border-t border-white/20">
                    <button
                      onClick={handleConfirmLunchRecommendation}
                      className="w-full bg-white/20 hover:bg-white/30 text-white font-semibold py-2 px-4 rounded-lg transition-colors"
                    >
                      확인
                    </button>
                  </div>
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

