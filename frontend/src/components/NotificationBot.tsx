/**
 * 플로팅 알림봇 컴포넌트
 * 캘린더 일정을 분석하여 사용자에게 알림 제공
 */
import React, { useState, useEffect, useCallback, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  BellIcon,
  XMarkIcon,
  CalendarIcon,
  ClockIcon,
  PlusIcon
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
  const [activeTab, setActiveTab] = useState<'notifications' | 'meal-schedules'>('notifications')
  const [schedules, setSchedules] = useState<Schedule[]>([])
  const [upcomingSchedules, setUpcomingSchedules] = useState<Schedule[]>([])
  const [todaySchedules, setTodaySchedules] = useState<Schedule[]>([])
  const [loading, setLoading] = useState(false)
  const [unreadCount, setUnreadCount] = useState(0)
  
  // 크기 조절 상태
  const [botSize, setBotSize] = useState(() => {
    const saved = localStorage.getItem('notificationbot-size')
    return saved ? JSON.parse(saved) : { width: 288, height: 300 }
  })
  const [isResizing, setIsResizing] = useState(false)
  const resizeRef = useRef<HTMLDivElement>(null)
  
  // 위치 상태
  const [botPosition, setBotPosition] = useState(() => {
    const saved = localStorage.getItem('notificationbot-position')
    return saved ? JSON.parse(saved) : { x: null, y: null } // null이면 기본 위치 사용
  })
  const [isDragging, setIsDragging] = useState(false)
  const dragStartPos = useRef({ x: 0, y: 0, offsetX: 0, offsetY: 0 })
  
  // 식사 일정 관리 관련 상태
  const [mealSchedules, setMealSchedules] = useState<Schedule[]>([])
  const [editingSchedule, setEditingSchedule] = useState<Schedule | null>(null)
  const [editDate, setEditDate] = useState<string>('')
  const [editTime, setEditTime] = useState<string>('')
  const [savingSchedule, setSavingSchedule] = useState(false)
  const [selectedMenteeForNewSchedule, setSelectedMenteeForNewSchedule] = useState<string>('')
  
  // 점심 약속 추천 알림 관련 상태
  const [lunchNotifications, setLunchNotifications] = useState<CommonFreeSlot[]>([])
  const [showLunchNotification, setShowLunchNotification] = useState(false)
  const [selectedDates, setSelectedDates] = useState<{ [menteeId: number]: string | null }>({})
  const [creatingSchedule, setCreatingSchedule] = useState<{ [menteeId: number]: boolean }>({})

  // 이미 처리한 멘티 ID 목록 (날짜 선택 또는 skip한 멘티)
  const [processedMenteeIds, setProcessedMenteeIds] = useState<Set<number>>(new Set())
  
  // 새 일정 알림 관련 상태 (멘티용)
  const [newScheduleNotification, setNewScheduleNotification] = useState<Schedule | null>(null)
  const [showNewScheduleNotification, setShowNewScheduleNotification] = useState(false)
  const [previousScheduleIds, setPreviousScheduleIds] = useState<Set<number>>(new Set())
  
  // Skip 알림 관련 상태
  const [showSkipNotification, setShowSkipNotification] = useState(false)
  const [skipForMentor, setSkipForMentor] = useState(false)

  // 일정 변경 알림 관련 상태 (멘티용)
  const [showScheduleNotification, setShowScheduleNotification] = useState(false)
  const [scheduleNotificationInfo, setScheduleNotificationInfo] = useState<{
    mentorName: string
    date: string
    action: 'created' | 'updated' | 'deleted'
  } | null>(null)
  
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
      console.log('[알림 로드] 공통 빈 일정 조회 시작')
      console.log('[알림 로드] 현재 처리된 멘티 ID:', Array.from(processedMenteeIds))

      const data = await scheduleAPI.getCommonFreeSlots()
      if (data?.common_free_slots && data.common_free_slots.length > 0) {
        // 이미 처리한 멘티(날짜 선택 또는 skip한 멘티)는 제외
        const filtered = data.common_free_slots.filter(
          (slot: CommonFreeSlot) => !processedMenteeIds.has(slot.mentee_id)
        )

        console.log('[알림 로드] 전체 멘티:', data.common_free_slots.length, '필터링 후:', filtered.length)

        if (filtered.length > 0) {
          setLunchNotifications(filtered)
          setShowLunchNotification(true)
        } else {
          // 모든 멘티가 이미 처리되었으면 알림 숨기기
          setLunchNotifications([])
          setShowLunchNotification(false)
        }
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
  }, [isAuthenticated, isMentor, processedMenteeIds])

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
    if (!isAuthenticated || isMentor || !user) {
      return
    }

    const checkSkipNotification = () => {
      // 현재 멘티의 모든 skip 알림 확인
      const skipKeys: string[] = []
      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i)
        if (key && key.startsWith('mealSkipped_')) {
          skipKeys.push(key)
        }
      }

      // 현재 멘티 ID와 관련된 skip 정보 찾기
      const menteeId = user?.id
      if (menteeId) {
        skipKeys.forEach(key => {
          try {
            const skipInfo = JSON.parse(localStorage.getItem(key) || '{}')
            if (skipInfo.menteeId === menteeId) {
              const skipTime = new Date(skipInfo.timestamp)
              const now = new Date()

              // 이번주 skip인지 확인 (월요일 기준)
              const daysSinceMonday = now.getDay() === 0 ? 6 : now.getDay() - 1
              const monday = new Date(now)
              monday.setDate(now.getDate() - daysSinceMonday)
              monday.setHours(0, 0, 0, 0)

              // 이번주 월요일 이후의 skip이고, 10초 이내의 알림만 표시
              if (skipTime >= monday && now.getTime() - skipTime.getTime() < 10000) {
                // 이미 확인된 알림이면 표시하지 않음
                if (!isNotificationConfirmed(`mentee_skip_notification_${skipInfo.mentorId}`)) {
                  setSkipForMentor(false)
                  setShowSkipNotification(true)
                  console.log(`[멘티 알림] 멘토 ${skipInfo.mentorName}님이 이번주 밥약을 건너뛰셨습니다.`)
                }
              }
            }
          } catch (e) {
            console.error('Skip notification parse error:', e)
          }
        })
      }
    }

    // 1초마다 체크
    const interval = setInterval(checkSkipNotification, 1000)

    return () => clearInterval(interval)
  }, [isAuthenticated, isMentor, user])

  // 일정 변경 알림 확인 (멘티용) - 이벤트 기반
  useEffect(() => {
    if (!isAuthenticated || isMentor) return

    // BroadcastChannel을 사용한 실시간 알림 수신
    const channel = new BroadcastChannel('schedule-notifications')

    channel.onmessage = (event) => {
      const notificationInfo = event.data

      // 현재 멘티 ID와 관련된 알림인지 확인
      if (notificationInfo.mentee_id === user?.id) {
        // 이미 확인된 알림이면 표시하지 않음
        const notificationKey = `mentee_schedule_notification_${notificationInfo.mentor_id}_${notificationInfo.action}_${notificationInfo.timestamp}`
        if (!isNotificationConfirmed(notificationKey)) {
          setScheduleNotificationInfo({
            mentorName: notificationInfo.mentor_name,
            date: notificationInfo.date || '',
            action: notificationInfo.action
          })
          setShowScheduleNotification(true)
          console.log(`[멘티 일정 알림] ${notificationInfo.mentor_name}님과의 일정이 ${notificationInfo.action === 'created' ? '잡혔습니다' : notificationInfo.action === 'updated' ? '수정되었습니다' : '삭제되었습니다'}`)

          // 10초 후 자동으로 알림 숨김
          setTimeout(() => {
            setShowScheduleNotification(false)
          }, 10000)
        }
      }
    }

    // 컴포넌트 언마운트 시 채널 정리
    return () => {
      channel.close()
    }
  }, [isAuthenticated, isMentor, user])

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
      
      // previousScheduleIds를 업데이트하되, Set의 내용이 실제로 변경되었을 때만
      setPreviousScheduleIds(prev => {
        // Set의 크기나 내용이 같으면 같은 Set 반환 (참조 동일성 유지)
        if (prev.size === currentScheduleIds.size && 
            Array.from(prev).every(id => currentScheduleIds.has(id))) {
          return prev
        }
        return currentScheduleIds
      })
    }
  }, [schedules, isMentor]) // previousScheduleIds를 의존성에서 제거

  // 멘토의 현재 식사 일정 상태에 따라 processedMenteeIds 업데이트
  useEffect(() => {
    if (!isAuthenticated || !isMentor || schedules.length === 0) {
      return
    }

    // 현재 존재하는 "멘토-멘티와의 식사" 일정들의 멘티 ID 수집
    const currentMealMenteeIds = new Set<number>()

    schedules.forEach(schedule => {
      // "멘토-멘티와의 식사" 제목의 일정 확인
      if (schedule.title && schedule.title.includes('멘토-멘티와의 식사') && schedule.color === '#10B981') {
        // 일정 설명에서 상대방 이름 추출
        // 멘토의 경우: "멘티이름님과 점심식사"
        // 멘티의 경우: "멘토이름님과 점심식사"
        if (schedule.description) {
          if (isMentor) {
            // 멘토인 경우: "멘티이름님과 점심식사"에서 멘티 이름 추출
            const menteeNameMatch = schedule.description.match(/^(.+?)님과 점심식사$/)
            if (menteeNameMatch) {
              const menteeName = menteeNameMatch[1]
              // lunchNotifications에서 멘티 ID 찾기
              const menteeSlot = lunchNotifications.find(slot => slot.mentee_name === menteeName)
              if (menteeSlot) {
                currentMealMenteeIds.add(menteeSlot.mentee_id)
                console.log(`[식사 일정 확인] 멘티 ${menteeName} (${menteeSlot.mentee_id})의 일정이 존재함`)
              }
            }
          } else {
            // 멘티인 경우: "멘토이름님과 점심식사" 확인
            const mentorNameMatch = schedule.description.match(/^(.+?)님과 점심식사$/)
            if (mentorNameMatch) {
              // 멘티의 경우 식사 일정이 있으면 자신의 일정이므로 추가
              console.log(`[식사 일정 확인] 멘티의 식사 일정이 존재함`)
            }
          }
        }
      }
    })

    // processedMenteeIds 업데이트: 현재 식사 일정이 있는 멘티만 유지
    setProcessedMenteeIds(prev => {
      const updated = new Set<number>()

      // 현재 식사 일정이 있는 멘티들은 유지
      currentMealMenteeIds.forEach(id => updated.add(id))

      // 기존에 있었지만 이제 식사 일정이 없는 멘티들은 제거 (알림 재개)
      const removedMentees: number[] = []
      prev.forEach(id => {
        if (!currentMealMenteeIds.has(id)) {
          removedMentees.push(id)
        } else {
          updated.add(id)
        }
      })

      if (removedMentees.length > 0) {
        console.log(`[식사 일정 삭제 감지] 다음 멘티들의 일정이 삭제되어 알림 재개:`, removedMentees)

        // 삭제된 멘티들의 localStorage 정보 정리
        removedMentees.forEach(menteeId => {
          try {
            localStorage.removeItem(`menteeNotificationSchedule_${menteeId}`)
            console.log(`[알림 스케줄 정리] 멘티 ${menteeId}의 알림 스케줄 제거`)
          } catch (error) {
            console.error(`Failed to remove notification schedule for mentee ${menteeId}:`, error)
          }
        })

        // 알림 다시 로드 (삭제된 멘티들의 알림이 다시 표시되도록)
        // setTimeout으로 지연시켜 무한 루프 방지
        setTimeout(() => {
          loadCommonFreeSlots()
        }, 100)
      }

      return updated
    })

  }, [schedules, isAuthenticated, isMentor, lunchNotifications]) // loadCommonFreeSlots를 의존성에서 제거

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
    setActiveTab('notifications') // 탭 초기화
    setUnreadCount(0) // 알림 패널을 닫으면 읽음 처리
    setEditingSchedule(null) // 편집 상태 초기화
  }
  
  // 식사 일정 목록 로드
  const loadMealSchedules = useCallback(async () => {
    if (!isAuthenticated || !isMentor) {
      return
    }
    
    try {
      const today = new Date()
      const nextMonth = new Date(today.getTime() + 30 * 24 * 60 * 60 * 1000)
      const startDate = today.toISOString().split('T')[0]
      const endDate = nextMonth.toISOString().split('T')[0]
      
      const data = await scheduleAPI.getSchedules(startDate, endDate)
      // "멘토-멘티와의 식사" 또는 "식사"가 포함된 일정만 필터링
      const mealSchedulesList = (data || []).filter((schedule: Schedule) => 
        schedule.title.includes('멘토-멘티와의 식사') || 
        schedule.title.includes('식사')
      )
      setMealSchedules(mealSchedulesList)
    } catch (error: any) {
      console.error('식사 일정 로드 실패:', error)
      setMealSchedules([])
    }
  }, [isAuthenticated, isMentor])
  
  // 식사 일정 수정 시작
  const handleStartEdit = (schedule: Schedule) => {
    setEditingSchedule(schedule)
    const date = new Date(schedule.start_time)
    setEditDate(date.toISOString().split('T')[0])
    const hours = String(date.getHours()).padStart(2, '0')
    const minutes = String(date.getMinutes()).padStart(2, '0')
    setEditTime(`${hours}:${minutes}`)
  }
  
  // 식사 일정 수정 취소
  const handleCancelEdit = () => {
    setEditingSchedule(null)
    setEditDate('')
    setEditTime('')
  }
  
  // 새 식사 일정 생성 시작
  const handleStartNewSchedule = () => {
    setEditingSchedule({ id: 'new' } as Schedule)
    setEditDate('')
    setEditTime('12:00') // 기본값 12시
    setSelectedMenteeForNewSchedule('')
  }

  // 새 식사 일정 생성
  const handleCreateNewSchedule = async () => {
    if (!editDate || !editTime) {
      alert('날짜와 시간을 입력해주세요.')
      return
    }

    if (lunchNotifications.length === 0) {
      alert('추천된 멘티가 없습니다.')
      return
    }

    try {
      setSavingSchedule(true)

      // 추천된 첫 번째 멘티를 자동 선택
      const mentee = lunchNotifications[0]
      const menteeId = mentee.mentee_id
      const menteeName = mentee.mentee_name

      console.log(`[새 일정 생성] 멘티 ID: ${menteeId}, 멘티 이름: ${menteeName}, 날짜: ${editDate}`)

      // 멘토-멘티 식사 일정 생성
      const response = await scheduleAPI.createMentorMenteeMealSchedule(
        menteeId,
        editDate,
        '멘토-멘티와의 식사',
        `${menteeName}님과의 식사`, // 멘토의 일정 설명
        `${user?.name}님과의 식사`  // 멘티의 일정 설명
      )

      console.log(`[새 일정 생성 성공] 응답:`, response)

      // 성공 처리
      setProcessedMenteeIds(prev => new Set([...prev, menteeId]))
      setSelectedDates(prev => ({ ...prev, [menteeId]: editDate }))

      // 멘티에게 일정 생성 알림 보내기
      const scheduleCreatedInfo = {
        timestamp: new Date().toISOString(),
        mentor_id: user?.id,
        mentor_name: user?.name || '멘토',
        mentee_id: menteeId,
        date: editDate,
        action: 'created'
      }

      // BroadcastChannel을 통해 실시간 알림 전송
      const channel = new BroadcastChannel('schedule-notifications')
      channel.postMessage(scheduleCreatedInfo)
      channel.close()

      console.log(`[일정 생성 알림] 멘티 ${menteeId}에게 실시간 알림 전송`)

      // 알림 숨기기
      setEditingSchedule(null)
      setSelectedMenteeForNewSchedule('')

      // 일정 목록 새로고침
      await loadSchedules()
      await loadMealSchedules()

      alert(`${editDate}에 ${menteeName}님과의 식사 일정이 생성되었습니다.`)

    } catch (error: any) {
      console.error('[새 일정 생성 실패] 전체 에러:', error)
      console.error('[새 일정 생성 실패] 에러 응답:', error?.response)
      console.error('[새 일정 생성 실패] 에러 데이터:', error?.response?.data)

      let errorMessage = '일정 생성에 실패했습니다. 다시 시도해주세요.'

      if (error?.response?.status === 403) {
        errorMessage = '멘토-멘티 관계가 없거나 활성화되지 않았습니다.'
      } else if (error?.response?.status === 404) {
        errorMessage = '멘티를 찾을 수 없습니다.'
      }

      alert(errorMessage)
    } finally {
      setSavingSchedule(false)
    }
  }

  // 식사 일정 수정 저장
  const handleSaveEdit = async () => {
    if (!editingSchedule || !editDate || !editTime) {
      alert('날짜와 시간을 입력해주세요.')
      return
    }
    
    try {
      setSavingSchedule(true)
      const [hours, minutes] = editTime.split(':')
      const startDateTime = new Date(editDate)
      startDateTime.setHours(parseInt(hours), parseInt(minutes), 0, 0)
      const endDateTime = new Date(startDateTime)
      endDateTime.setHours(startDateTime.getHours() + 1) // 1시간 후
      
      // 멘토-멘티 식사 일정인지 확인
      const isMealSchedule = editingSchedule && (
        editingSchedule.title === '멘토-멘티와의 식사' &&
        editingSchedule.color === '#10B981' &&
        editingSchedule.description &&
        editingSchedule.description.includes('님과 점심식사')
      )

      if (isMealSchedule) {
        // 멘토-멘티 식사 일정이면 양쪽 모두 수정하는 API 사용
        await scheduleAPI.updateMentorMenteeMealSchedule(editingSchedule.id, {
          start_time: startDateTime.toISOString(),
          end_time: endDateTime.toISOString()
        })

        // 멘티에게 일정 수정 알림 보내기
        if (editingSchedule.description) {
          const menteeNameMatch = editingSchedule.description.match(/^(.+?)님과의 식사$/)
          if (menteeNameMatch) {
            const menteeName = menteeNameMatch[1]
            // lunchNotifications에서 멘티 ID 찾기
            const mentee = lunchNotifications.find(n => n.mentee_name === menteeName)
            if (mentee) {
              const scheduleUpdatedInfo = {
                timestamp: new Date().toISOString(),
                mentor_id: user?.id,
                mentor_name: user?.name || '멘토',
                mentee_id: mentee.mentee_id,
                date: editDate,
                action: 'updated'
              }

              // BroadcastChannel을 통해 실시간 알림 전송
              const channel = new BroadcastChannel('schedule-notifications')
              channel.postMessage(scheduleUpdatedInfo)
              channel.close()

              console.log(`[일정 수정 알림] 멘티 ${mentee.mentee_id}에게 실시간 알림 전송`)
            }
          }
        }

        alert('식사 일정이 양쪽 모두 수정되었습니다.')
      } else {
        // 일반 일정이면 기존 API 사용
        await scheduleAPI.updateSchedule(editingSchedule.id, {
          start_time: startDateTime.toISOString(),
          end_time: endDateTime.toISOString()
        })
        alert('일정이 수정되었습니다.')
      }

      // 일정 목록 새로고침
      await loadSchedules()
      await loadMealSchedules()
      handleCancelEdit()
    } catch (error: any) {
      console.error('일정 수정 실패:', error)
      alert('일정 수정에 실패했습니다.')
    } finally {
      setSavingSchedule(false)
    }
  }
  
  // 식사 일정 삭제
  const handleDeleteSchedule = async (scheduleId: number) => {
    if (!confirm('정말로 이 일정을 삭제하시겠습니까?\n\n* 멘토-멘티 식사 일정인 경우 양쪽 모두의 일정이 삭제됩니다.')) {
      return
    }

    try {
      // 삭제할 일정 찾기
      const scheduleToDelete = mealSchedules.find(s => s.id === scheduleId)

      // 멘토-멘티 식사 일정인지 확인
      const isMealSchedule = scheduleToDelete && (
        scheduleToDelete.title === '멘토-멘티와의 식사' &&
        scheduleToDelete.color === '#10B981' &&
        scheduleToDelete.description &&
        scheduleToDelete.description.includes('님과 점심식사')
      )

      if (isMealSchedule) {
        // 멘토-멘티 식사 일정이면 양쪽 모두 삭제하는 API 사용
        await scheduleAPI.deleteMentorMenteeMealSchedule(scheduleId)

        // 멘티에게 일정 삭제 알림 보내기
        if (scheduleToDelete.description) {
          const menteeNameMatch = scheduleToDelete.description.match(/^(.+?)님과의 식사$/)
          if (menteeNameMatch) {
            const menteeName = menteeNameMatch[1]
            // lunchNotifications에서 멘티 ID 찾기
            const mentee = lunchNotifications.find(n => n.mentee_name === menteeName)
            if (mentee) {
              const scheduleDeletedInfo = {
                timestamp: new Date().toISOString(),
                mentor_id: user?.id,
                mentor_name: user?.name || '멘토',
                mentee_id: mentee.mentee_id,
                action: 'deleted'
              }

              // BroadcastChannel을 통해 실시간 알림 전송
              const channel = new BroadcastChannel('schedule-notifications')
              channel.postMessage(scheduleDeletedInfo)
              channel.close()

              console.log(`[일정 삭제 알림] 멘티 ${mentee.mentee_id}에게 실시간 알림 전송`)
            }
          }
        }

        alert('식사 일정이 양쪽 모두 삭제되었습니다.')
      } else {
        // 일반 일정이면 기존 API 사용
        await scheduleAPI.deleteSchedule(scheduleId)
        alert('일정이 삭제되었습니다.')
      }

      // 일정 목록 새로고침
      await loadSchedules()
      await loadMealSchedules()

      // processedMenteeIds 업데이트 (식사 일정이 삭제되었을 수 있음)
      await loadCommonFreeSlots()

    } catch (error: any) {
      console.error('일정 삭제 실패:', error)
      alert('일정 삭제에 실패했습니다.')
    }
  }
  
  // 식사 일정 관리 탭 열기 시 일정 로드
  useEffect(() => {
    if (isOpen && activeTab === 'meal-schedules' && isMentor) {
      loadMealSchedules()
    }
  }, [isOpen, activeTab, isMentor, loadMealSchedules])

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
      localStorage.setItem('notificationbot-size', JSON.stringify(botSize))
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
      localStorage.setItem('notificationbot-position', JSON.stringify(newPosition))
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

  const handleCloseLunchNotification = () => {
    setShowLunchNotification(false)
  }
  
  // Skip 버튼 핸들러 (멘토가 이번 주 점심 약속 건너뛰기)
  const handleSkipLunch = () => {
    console.log('[Skip] 멘토가 이번주 점심 약속을 건너뜀')

    // 현재 표시된 모든 멘티를 처리 완료 목록에 추가 (더 이상 알림에 표시하지 않음)
    setProcessedMenteeIds(prev => {
      const newSet = new Set(prev)
      lunchNotifications.forEach(notification => {
        newSet.add(notification.mentee_id)
        console.log(`[Skip] 멘티 ID ${notification.mentee_id}를 처리 완료 목록에 추가`)
      })
      console.log(`[Skip] 처리 완료 멘티 목록 업데이트:`, Array.from(newSet))
      return newSet
    })

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
    lunchNotifications.forEach(notification => {
      const skipInfo = {
        timestamp: new Date().toISOString(),
        mentor_id: user?.id,
        mentor_name: user?.name,
        mentee_id: notification.mentee_id,
        week: getCurrentWeekKey() // 주차 식별용
      }
      localStorage.setItem(`mealSkipped_${notification.mentee_id}_${user?.id}`, JSON.stringify(skipInfo))
      console.log(`[Skip] 멘티 ${notification.mentee_id}에게 skip 알림 정보 저장`)
    })

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
    // 현재 멘티의 모든 skip 알림을 확인 처리
    const skipKeys: string[] = []
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i)
      if (key && key.startsWith('mealSkipped_')) {
        skipKeys.push(key)
      }
    }

    const menteeId = user?.id
    if (menteeId) {
      skipKeys.forEach(key => {
        try {
          const skipInfo = JSON.parse(localStorage.getItem(key) || '{}')
          if (skipInfo.menteeId === menteeId) {
            // 멘토별로 알림 확인 처리
            confirmNotification(`mentee_skip_notification_${skipInfo.mentorId}`)
            // 해당 skip 정보 제거
            localStorage.removeItem(key)
            console.log(`[멘티 알림 확인] skip 정보 제거: ${key}`)
          }
        } catch (error) {
          console.error('Failed to parse skip info:', error)
        }
      })
    }

    setShowSkipNotification(false)
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
      // 멘토의 설명: "멘티이름님과의 식사"
      // 멘티의 설명: "멘토이름님과의 식사"
      const mentorName = user?.name || '멘토'
      const response = await scheduleAPI.createMentorMenteeMealSchedule(
        menteeId,
        dateString,
        '멘토-멘티와의 식사',
        `${menteeName}님과의 식사`, // 멘토의 일정 설명
        `${mentorName}님과의 식사`  // 멘티의 일정 설명
      )
      
      console.log(`[일정 생성 성공] 응답:`, response)
      console.log(`[일정 생성 성공] 멘토 일정 ID: ${response.mentor_schedule_id}, 멘티 일정 ID: ${response.mentee_schedule_id}`)
      
      // 선택한 날짜 저장
      setSelectedDates(prev => ({ ...prev, [menteeId]: dateString }))

      // 날짜를 선택한 멘티를 처리 완료 목록에 추가 (더 이상 알림에 표시하지 않음)
      setProcessedMenteeIds(prev => {
        const newSet = new Set(prev)
        newSet.add(menteeId)
        console.log(`[날짜 선택] 멘티 ID ${menteeId}를 처리 완료 목록에 추가. 현재 처리된 멘티:`, Array.from(newSet))
        return newSet
      })

      // 멘토 점심 추천 알림 확인 처리 (날짜 선택 = 확인으로 간주)
      confirmNotification('mentor_lunch_recommendation')
      setShowLunchNotification(false) // 알림 닫기

      // 멘티에게 일정 생성 알림 보내기
      const scheduleCreatedInfo = {
        timestamp: new Date().toISOString(),
        mentor_id: user?.id,
        mentor_name: mentorName,
        mentee_id: menteeId,
        date: dateString,
        action: 'created'
      }

      // BroadcastChannel을 통해 실시간 알림 전송
      const channel = new BroadcastChannel('schedule-notifications')
      channel.postMessage(scheduleCreatedInfo)
      channel.close()

      console.log(`[일정 생성 알림] 멘티 ${menteeId}에게 실시간 알림 전송`)

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

      {/* 일정 변경 알림 (멘티용 - 화면 왼쪽) */}
      <AnimatePresence>
        {!isMentor && showScheduleNotification && scheduleNotificationInfo && (
          <motion.div
            initial={{ opacity: 0, x: -100 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -100 }}
            className="fixed top-24 left-6 z-[75] max-w-sm w-full"
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              className="bg-gradient-to-br from-blue-500 via-indigo-500 to-purple-600 text-white rounded-2xl shadow-2xl p-6 border-2 border-white/30"
            >
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className="w-12 h-12 bg-white/20 backdrop-blur-sm rounded-full flex items-center justify-center">
                    <span className="text-3xl">
                      {scheduleNotificationInfo.action === 'created' ? '✅' :
                       scheduleNotificationInfo.action === 'updated' ? '🔄' : '❌'}
                    </span>
                  </div>
                  <div>
                    <h3 className="font-bold text-xl mb-1">
                      {scheduleNotificationInfo.action === 'created' ? '점심 약속 확정!' :
                       scheduleNotificationInfo.action === 'updated' ? '점심 약속 변경!' : '점심 약속 취소'}
                    </h3>
                    <p className="text-sm opacity-90">
                      {scheduleNotificationInfo.mentorName}님과의 일정이 {scheduleNotificationInfo.action === 'created' ? '잡혔습니다' :
                       scheduleNotificationInfo.action === 'updated' ? '수정되었습니다' : '삭제되었습니다'}
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => setShowScheduleNotification(false)}
                  className="p-2 hover:bg-white/20 rounded-lg transition-colors flex-shrink-0"
                >
                  <XMarkIcon className="w-5 h-5" />
                </button>
              </div>

              {scheduleNotificationInfo.date && (
                <div className="bg-white/20 backdrop-blur-sm rounded-xl p-4 mb-3">
                  <div className="flex items-center gap-2 mb-2">
                    <CalendarIcon className="w-5 h-5" />
                    <p className="font-bold text-lg">
                      {new Date(scheduleNotificationInfo.date).toLocaleDateString('ko-KR', {
                        year: 'numeric',
                        month: 'long',
                        day: 'numeric',
                        weekday: 'long'
                      })}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <ClockIcon className="w-5 h-5" />
                    <p className="font-semibold">
                      오후 12:00 - 13:00
                    </p>
                  </div>
                </div>
              )}

              <div className="text-center">
                <p className="font-semibold text-base leading-relaxed">
                  {scheduleNotificationInfo.action === 'created' ? '멘토님과 의미있는 시간 보내세요! 💙' :
                   scheduleNotificationInfo.action === 'updated' ? '변경된 일정 확인해주세요! 🔄' :
                   '다음 기회를 기대해주세요! 😊'}
                </p>
              </div>

              <button
                onClick={() => setShowScheduleNotification(false)}
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
                  
                  {/* 날짜 선택 박스들 및 Skip 버튼 */}
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

                    {/* Skip 버튼 - 날짜 버튼들과 완전히 동일한 크기와 스타일로 나란히 배치 */}
                    <button
                      onClick={handleSkipLunch}
                      disabled={isCreating}
                      className={`
                        px-4 py-2 rounded-lg font-medium text-sm transition-all
                        bg-white/20 text-white hover:bg-white/30 hover:scale-105 active:scale-95
                        border border-white/30 min-w-[80px] h-[40px]
                        ${isCreating ? 'cursor-not-allowed opacity-50' : ''}
                      `}
                    >
                      {isCreating ? (
                        <span className="flex items-center gap-1">
                          <span className="animate-spin">⏳</span>
                          <span>Skip</span>
                        </span>
                      ) : (
                        <span className="flex items-center gap-1">
                          <span>⏭️</span>
                          <span>Skip</span>
                        </span>
                      )}
                    </button>
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
                    <BellIcon className="w-5 h-5 text-primary-600" />
                  </div>
                  <div>
                    <h3 className="font-bold text-white text-sm">알림봇</h3>
                    <p className="text-xs text-white/90">일정을 관리하세요 🔔</p>
                  </div>
                </div>
                <button
                  onClick={handleClose}
                  className="text-white hover:bg-white/20 p-1.5 rounded-lg transition-colors"
                >
                  <XMarkIcon className="w-4 h-4" />
                </button>
              </div>
              
              {/* 탭 메뉴 (멘토에게만 표시) */}
              {isMentor && (
                <div className="flex gap-2 mt-2">
                  <button
                    onClick={() => setActiveTab('notifications')}
                    className={`flex-1 py-2 px-3 rounded-lg text-xs font-semibold transition-colors ${
                      activeTab === 'notifications'
                        ? 'bg-white text-primary-600'
                        : 'bg-white/20 text-white hover:bg-white/30'
                    }`}
                  >
                    일정 알림
                  </button>
                  <button
                    onClick={() => setActiveTab('meal-schedules')}
                    className={`flex-1 py-2 px-3 rounded-lg text-xs font-semibold transition-colors ${
                      activeTab === 'meal-schedules'
                        ? 'bg-white text-primary-600'
                        : 'bg-white/20 text-white hover:bg-white/30'
                    }`}
                  >
                    식사 일정 관리
                  </button>
                </div>
              )}
            </div>

            {/* 일일 브리핑 - 일정 알림 탭에서만 표시 */}
            {activeTab === 'notifications' && shouldShowBriefing() && (
              <div className="px-3 pt-3 pb-2">
                <motion.div
                  initial={{ opacity: 0, y: -10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="bg-gradient-to-r from-primary-500 to-amber-500 text-white rounded-xl p-3 shadow-lg"
                >
                  <p className="text-xs leading-relaxed font-medium">
                    {getDailyBriefing()}
                  </p>
                </motion.div>
              </div>
            )}

            {/* 탭 내용 */}
            {activeTab === 'notifications' && (
              <div className="flex-1 overflow-y-auto p-3 space-y-2">
              {loading ? (
                <div className="flex items-center justify-center h-full">
                  <div className="flex space-x-2">
                    <div className="w-2 h-2 bg-primary-500 rounded-full animate-bounce"></div>
                    <div className="w-2 h-2 bg-primary-500 rounded-full animate-bounce delay-100"></div>
                    <div className="w-2 h-2 bg-primary-500 rounded-full animate-bounce delay-200"></div>
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
                    className="bg-gradient-to-r from-primary-50 to-amber-50 rounded-lg p-3 border border-primary-200 hover:shadow-md transition-shadow"
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
                            <span className="text-primary-600 font-medium text-xs">
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
            )}

            {/* 식사 일정 관리 페이지 */}
            {activeTab === 'meal-schedules' && isMentor && (
              <div className="flex-1 overflow-y-auto p-3 space-y-2">
                {/* 새 일정 추가/수정 폼 - 항상 표시 */}
                <div className="bg-gradient-to-r from-blue-50 to-indigo-50 rounded-lg p-3 border border-blue-200 mb-3">
                  {editingSchedule && editingSchedule.id === 'new' ? (
                    // 새 일정 생성 모드
                    <div className="space-y-2">
                      <div>
                        <label className="text-xs text-gray-600 block mb-1">날짜</label>
                        <input
                          type="date"
                          value={editDate}
                          onChange={(e) => setEditDate(e.target.value)}
                          className="w-full px-2 py-1 text-xs border border-gray-300 rounded"
                        />
                      </div>
                      <div>
                        <label className="text-xs text-gray-600 block mb-1">시간</label>
                        <input
                          type="time"
                          value={editTime}
                          onChange={(e) => setEditTime(e.target.value)}
                          className="w-full px-2 py-1 text-xs border border-gray-300 rounded"
                        />
                      </div>
                      <div className="flex gap-2 mt-3">
                        <button
                          onClick={handleCreateNewSchedule}
                          disabled={savingSchedule || lunchNotifications.length === 0}
                          className="flex-1 bg-blue-500 hover:bg-blue-600 text-white text-xs font-semibold py-2 px-3 rounded transition-colors disabled:opacity-50"
                        >
                          {savingSchedule ? '생성 중...' : '일정 생성'}
                        </button>
                        <button
                          onClick={handleCancelEdit}
                          disabled={savingSchedule}
                          className="flex-1 bg-gray-300 hover:bg-gray-400 text-gray-700 text-xs font-semibold py-2 px-3 rounded transition-colors disabled:opacity-50"
                        >
                          취소
                        </button>
                      </div>
                    </div>
                  ) : (
                    // 새 일정 생성 버튼
                    <button
                      onClick={handleStartNewSchedule}
                      className="w-full bg-blue-500 hover:bg-blue-600 text-white text-sm font-semibold py-2 px-4 rounded-lg transition-colors flex items-center justify-center gap-2"
                    >
                      <PlusIcon className="w-4 h-4" />
                      새 식사 일정 만들기
                    </button>
                  )}
                </div>

                {/* 기존 일정 목록 */}
                {mealSchedules.length === 0 ? (
                  <div className="flex flex-col items-center justify-center py-8 text-gray-400">
                    <CalendarIcon className="w-12 h-12 mb-3 opacity-50" />
                    <p className="text-sm">등록된 식사 일정이 없습니다</p>
                    <p className="text-xs mt-2">위에서 새 일정을 만들거나 월요일 추천 알림을 기다려보세요</p>
                  </div>
                ) : (
                  mealSchedules.map((schedule: Schedule) => (
                    <div
                      key={schedule.id}
                      className="bg-gradient-to-r from-emerald-50 to-teal-50 rounded-lg p-3 border border-emerald-200"
                    >
                      {editingSchedule?.id === schedule.id ? (
                        // 편집 모드
                        <div className="space-y-2">
                          <div>
                            <label className="text-xs text-gray-600 block mb-1">날짜</label>
                            <input
                              type="date"
                              value={editDate}
                              onChange={(e) => setEditDate(e.target.value)}
                              className="w-full px-2 py-1 text-xs border border-gray-300 rounded"
                            />
                          </div>
                          <div>
                            <label className="text-xs text-gray-600 block mb-1">시간</label>
                            <input
                              type="time"
                              value={editTime}
                              onChange={(e) => setEditTime(e.target.value)}
                              className="w-full px-2 py-1 text-xs border border-gray-300 rounded"
                            />
                          </div>
                          <div className="flex gap-2 mt-3">
                            <button
                              onClick={handleSaveEdit}
                              disabled={savingSchedule}
                              className="flex-1 bg-emerald-500 hover:bg-emerald-600 text-white text-xs font-semibold py-2 px-3 rounded transition-colors disabled:opacity-50"
                            >
                              {savingSchedule ? '저장 중...' : '저장'}
                            </button>
                            <button
                              onClick={handleCancelEdit}
                              disabled={savingSchedule}
                              className="flex-1 bg-gray-300 hover:bg-gray-400 text-gray-700 text-xs font-semibold py-2 px-3 rounded transition-colors disabled:opacity-50"
                            >
                              취소
                            </button>
                          </div>
                        </div>
                      ) : (
                        // 보기 모드
                        <div>
                          <div className="flex items-start justify-between mb-2">
                            <div className="flex-1">
                              <h4 className="font-semibold text-gray-800 text-sm mb-1">
                                {schedule.title}
                              </h4>
                              <div className="flex items-center gap-1 text-xs text-gray-600">
                                <CalendarIcon className="w-3 h-3" />
                                <span>{formatDateTime(schedule.start_time)}</span>
                              </div>
                              {schedule.description && (
                                <p className="text-xs text-gray-500 mt-1">{schedule.description}</p>
                              )}
                            </div>
                          </div>
                          <div className="flex gap-2 mt-2">
                            <button
                              onClick={() => handleStartEdit(schedule)}
                              className="flex-1 bg-emerald-500 hover:bg-emerald-600 text-white text-xs font-semibold py-1.5 px-3 rounded transition-colors"
                            >
                              수정
                            </button>
                            <button
                              onClick={() => handleDeleteSchedule(schedule.id)}
                              className="flex-1 bg-red-500 hover:bg-red-600 text-white text-xs font-semibold py-1.5 px-3 rounded transition-colors"
                            >
                              삭제
                            </button>
                          </div>
                        </div>
                      )}
                    </div>
                  ))
                )}
              </div>
            )}

            {/* Footer */}
            {activeTab === 'notifications' && (
              <div className="p-3 border-t border-amber-100 bg-amber-50 rounded-b-2xl">
                <p className="text-xs text-center text-gray-600">
                  총 {upcomingSchedules.length}개의 일정이 24시간 이내에 시작됩니다
                </p>
              </div>
            )}
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
        className="fixed bottom-[94px] right-6 w-16 h-16 bg-gradient-to-r from-primary-600 via-primary-500 to-amber-500 text-white rounded-full shadow-lg flex items-center justify-center z-[60] hover:shadow-xl transition-shadow relative"
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

