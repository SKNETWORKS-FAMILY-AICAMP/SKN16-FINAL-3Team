/**
 * 일정 관리 캘린더 컴포넌트
 */
import { useState, useEffect } from 'react'
import type { MouseEvent } from 'react'
import { scheduleAPI } from '../utils/api'
import {
  ChevronLeftIcon,
  ChevronRightIcon,
  XMarkIcon
} from '@heroicons/react/24/outline'
import { motion, AnimatePresence } from 'framer-motion'

interface Schedule {
  id: number
  title: string
  description?: string
  start_time: string
  end_time?: string
  location?: string
  color?: string
}

interface CalendarProps {
  className?: string
}

export default function Calendar({ className = '' }: CalendarProps) {
  const [currentDate, setCurrentDate] = useState(new Date())
  const [selectedDate, setSelectedDate] = useState<Date | null>(null)
  const [schedules, setSchedules] = useState<Schedule[]>([])
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [isEditMode, setIsEditMode] = useState(false)
  const [editingSchedule, setEditingSchedule] = useState<Schedule | null>(null)
  const [viewingSchedule, setViewingSchedule] = useState<Schedule | null>(null)
  const [isViewMode, setIsViewMode] = useState(false)
  const [loading, setLoading] = useState(false)
  const [holidays, setHolidays] = useState<any[]>([])

  // 색상 옵션
  const colorOptions = [
    { name: '파란색', value: '#3B82F6' },
    { name: '회색', value: '#6B7280' },
    { name: '초록색', value: '#10B981' },
    { name: '노란색', value: '#F59E0B' },
    { name: '보라색', value: '#8B5CF6' },
    { name: '분홍색', value: '#EC4899' }
  ]

  // 날짜/시간 포맷팅 함수
  const formatDateTimeForDisplay = (dateTimeString: string): string => {
    if (!dateTimeString) return ''
    try {
      const date = new Date(dateTimeString)
      // 유효한 날짜인지 확인
      if (isNaN(date.getTime())) {
        return ''
      }
      const year = date.getFullYear()
      const month = String(date.getMonth() + 1).padStart(2, '0')
      const day = String(date.getDate()).padStart(2, '0')
      const hours = date.getHours()
      const minutes = String(date.getMinutes()).padStart(2, '0')
      const ampm = hours >= 12 ? '오후' : '오전'
      const displayHours = hours % 12 || 12
      return `${year}-${month}-${day} ${ampm} ${displayHours} : ${minutes}`
    } catch (error) {
      console.error('Error formatting datetime:', error)
      return ''
    }
  }

  // 날짜/시간 파싱 함수 (datetime-local 형식으로 변환)
  const parseDateTimeForInput = (dateTimeString: string): string => {
    if (!dateTimeString) return ''
    try {
      // ISO 형식 문자열을 datetime-local 형식으로 변환
      if (dateTimeString.includes('T')) {
        const date = new Date(dateTimeString)
        // 유효한 날짜인지 확인
        if (isNaN(date.getTime())) {
          return ''
        }
        // 로컬 시간으로 변환하여 YYYY-MM-DDTHH:mm 형식으로 반환
        const year = date.getFullYear()
        const month = String(date.getMonth() + 1).padStart(2, '0')
        const day = String(date.getDate()).padStart(2, '0')
        const hours = String(date.getHours()).padStart(2, '0')
        const minutes = String(date.getMinutes()).padStart(2, '0')
        return `${year}-${month}-${day}T${hours}:${minutes}`
      }
      return dateTimeString
    } catch (error) {
      console.error('Error parsing datetime:', error)
      return ''
    }
  }

  // 로컬 날짜를 ISO 형식으로 변환 (시간대 문제 방지)
  const toLocalISOString = (date: Date): string => {
    const year = date.getFullYear()
    const month = String(date.getMonth() + 1).padStart(2, '0')
    const day = String(date.getDate()).padStart(2, '0')
    const hours = String(date.getHours()).padStart(2, '0')
    const minutes = String(date.getMinutes()).padStart(2, '0')
    const seconds = String(date.getSeconds()).padStart(2, '0')
    return `${year}-${month}-${day}T${hours}:${minutes}:${seconds}`
  }

  // 날짜 문자열을 로컬 날짜로 변환 (시간대 문제 방지)
  const parseLocalDate = (dateStr: string): Date => {
    // YYYY-MM-DD 형식의 날짜 문자열을 로컬 시간대로 파싱
    const [year, month, day] = dateStr.split('-').map(Number)
    return new Date(year, month - 1, day)
  }

  // 폼 상태
  const [formData, setFormData] = useState({
    title: '',
    description: '',
    start_time: '',
    end_time: '',
    location: '',
    color: '#3B82F6'
  })

  // 현재 월의 첫 날과 마지막 날 계산
  const year = currentDate.getFullYear()
  const month = currentDate.getMonth()
  const firstDay = new Date(year, month, 1)
  const lastDay = new Date(year, month + 1, 0)
  const firstDayOfWeek = firstDay.getDay()
  const daysInMonth = lastDay.getDate()

  // 일정 및 공휴일 로드
  useEffect(() => {
    loadSchedules()
    loadHolidays()
  }, [currentDate])

  const loadSchedules = async () => {
    try {
      setLoading(true)
      const startDate = new Date(year, month, 1).toISOString().split('T')[0]
      const endDate = new Date(year, month + 1, 0).toISOString().split('T')[0]
      const data = await scheduleAPI.getSchedules(startDate, endDate)
      setSchedules(data || [])
    } catch (error: any) {
      console.error('Failed to load schedules:', error)
      // 403 에러는 멘티가 아닌 경우이므로 조용히 처리 (에러 메시지 표시 안 함)
      if (error?.response?.status !== 403) {
        console.error('Error loading schedules:', error?.response?.data || error?.message)
      }
      setSchedules([])
    } finally {
      setLoading(false)
    }
  }

  const loadHolidays = async () => {
    try {
      console.log('📅 공휴일 로드 시작:', { year, month: month + 1 })
      const data = await scheduleAPI.getHolidays(year, month + 1)
      console.log('📅 공휴일 데이터 받음:', data)
      console.log('📅 공휴일 첫 번째 항목:', data?.[0])
      setHolidays(data || [])
    } catch (error: any) {
      console.error('❌ 공휴일 로드 실패:', error)
      console.error('에러 상세:', error?.response?.data || error?.message)
      setHolidays([])
    }
  }

  // 이전 달
  const goToPreviousMonth = () => {
    setCurrentDate(new Date(year, month - 1, 1))
  }

  // 다음 달
  const goToNextMonth = () => {
    setCurrentDate(new Date(year, month + 1, 1))
  }

  // 오늘로 이동
  const goToToday = () => {
    setCurrentDate(new Date())
  }

  // 날짜 클릭
  const handleDateClick = (day: number) => {
    try {
      const clickedDate = new Date(year, month, day, 9, 0, 0) // 오전 9시로 기본 설정
      setSelectedDate(clickedDate)
      
      // 로컬 시간을 ISO 형식으로 변환 (타임존 문제 방지)
      const isoDateTime = toLocalISOString(clickedDate)
      
      setFormData({
        ...formData,
        start_time: isoDateTime,
        end_time: ''
      })
      setIsEditMode(false)
      setEditingSchedule(null)
      setIsModalOpen(true)
    } catch (error) {
      console.error('Error handling date click:', error)
    }
  }

  // 일정 저장
  const handleSave = async () => {
    try {
      // 데이터 형식 변환
      const scheduleData: any = {
        title: formData.title,
        description: formData.description || null,
        start_time: formData.start_time, // ISO 형식 문자열
        end_time: formData.end_time || null, // 빈 문자열이면 null로 변환
        location: formData.location || null,
        color: formData.color || '#3B82F6'
      }

      // 빈 문자열을 null로 변환
      if (scheduleData.description === '') scheduleData.description = null
      if (scheduleData.end_time === '') scheduleData.end_time = null
      if (scheduleData.location === '') scheduleData.location = null

      // 디버깅을 위한 로그
      console.log('Saving schedule data:', scheduleData)

      if (isEditMode && editingSchedule) {
        await scheduleAPI.updateSchedule(editingSchedule.id, scheduleData)
      } else {
        await scheduleAPI.createSchedule(scheduleData)
      }
      setIsModalOpen(false)
      resetForm()
      loadSchedules()
    } catch (error: any) {
      console.error('Failed to save schedule:', error)
      let errorMessage = '일정 저장에 실패했습니다.'
      
      if (error?.response?.status === 400) {
        errorMessage = error?.response?.data?.detail || '입력한 정보를 확인해주세요.'
      } else if (error?.response?.status === 500) {
        errorMessage = error?.response?.data?.detail || '서버 오류가 발생했습니다. 잠시 후 다시 시도해주세요.'
      } else {
        errorMessage = error?.response?.data?.detail || error?.message || '일정 저장에 실패했습니다.'
      }
      
      console.error('Error details:', error?.response?.data)
      alert(errorMessage)
    }
  }

  // 일정 삭제
  const handleDelete = async (scheduleId: number) => {
    if (!window.confirm('정말로 이 일정을 삭제하시겠습니까?')) {
      return
    }
    try {
      console.log('Deleting schedule with id:', scheduleId)
      const response = await scheduleAPI.deleteSchedule(scheduleId)
      console.log('Delete response:', response)
      // 삭제 성공 후 모달 닫기 및 폼 리셋
      setIsModalOpen(false)
      resetForm()
      loadSchedules()
      alert('일정이 삭제되었습니다.')
    } catch (error: any) {
      console.error('Failed to delete schedule:', error)
      console.error('Error details:', error?.response?.data)
      console.error('Error status:', error?.response?.status)
      let errorMessage = '일정 삭제에 실패했습니다.'
      
      if (error?.response?.status === 403) {
        errorMessage = '이 일정을 삭제할 권한이 없습니다.'
      } else if (error?.response?.status === 404) {
        errorMessage = '일정을 찾을 수 없습니다.'
      } else if (error?.response?.status === 500) {
        errorMessage = '서버 오류가 발생했습니다. 잠시 후 다시 시도해주세요.'
      } else if (error?.response?.data?.detail) {
        errorMessage = error.response.data.detail
      }
      
      alert(errorMessage)
    }
  }

  // 일정 상세 보기
  const handleViewSchedule = (schedule: Schedule) => {
    setViewingSchedule(schedule)
    setIsViewMode(true)
    setIsEditMode(false)
    setIsModalOpen(true)
  }

  // 일정 수정 모드로 전환
  const handleEditFromView = () => {
    if (!viewingSchedule) return
    setEditingSchedule(viewingSchedule)
    setIsEditMode(true)
    setIsViewMode(false)
    setFormData({
      title: viewingSchedule.title,
      description: viewingSchedule.description || '',
      start_time: viewingSchedule.start_time,
      end_time: viewingSchedule.end_time || '',
      location: viewingSchedule.location || '',
      color: viewingSchedule.color || '#3B82F6'
    })
  }

  // 일정 수정
  const handleEdit = (schedule: Schedule) => {
    setEditingSchedule(schedule)
    setIsEditMode(true)
    setIsViewMode(false)
    setViewingSchedule(null)
    setFormData({
      title: schedule.title,
      description: schedule.description || '',
      start_time: schedule.start_time,
      end_time: schedule.end_time || '',
      location: schedule.location || '',
      color: schedule.color || '#3B82F6'
    })
    setIsModalOpen(true)
  }

  // 폼 리셋
  const resetForm = () => {
    setFormData({
      title: '',
      description: '',
      start_time: '',
      end_time: '',
      location: '',
      color: '#3B82F6'
    })
    setIsEditMode(false)
    setIsViewMode(false)
    setEditingSchedule(null)
    setViewingSchedule(null)
  }

  // 특정 날짜의 공휴일 가져오기
  const getHolidayForDate = (day: number) => {
    const checkDate = new Date(year, month, day)
    checkDate.setHours(0, 0, 0, 0)
    
    return holidays.find((holiday: any) => {
      // holiday.holiday_date 또는 holiday.date 사용 (API 응답에 따라 다를 수 있음)
      const holidayDateStr = holiday.holiday_date || holiday.date
      if (!holidayDateStr) return false
      
      // 문자열이거나 Date 객체일 수 있음
      let holidayDate: Date
      if (typeof holidayDateStr === 'string') {
        // YYYY-MM-DD 형식의 문자열인 경우
        const dateParts = holidayDateStr.split('T')[0].split('-') // ISO 형식 처리
        if (dateParts.length === 3) {
          const [y, m, d] = dateParts.map(Number)
          holidayDate = new Date(y, m - 1, d)
        } else {
          return false
        }
      } else {
        holidayDate = new Date(holidayDateStr)
      }
      holidayDate.setHours(0, 0, 0, 0)
      
      return (
        holidayDate.getDate() === checkDate.getDate() &&
        holidayDate.getMonth() === checkDate.getMonth() &&
        holidayDate.getFullYear() === checkDate.getFullYear()
      )
    })
  }

  // 특정 날짜의 일정 가져오기 (시작일부터 종료일까지 포함)
  const getSchedulesForDate = (day: number) => {
    // 날짜를 시간 부분을 제거하고 날짜만 비교하기 위해 00:00:00으로 설정
    const checkDate = new Date(year, month, day)
    checkDate.setHours(0, 0, 0, 0)
    
    return schedules.filter((schedule: Schedule) => {
      const startDate = new Date(schedule.start_time)
      startDate.setHours(0, 0, 0, 0)
      
      // 종료일이 있으면 시작일부터 종료일까지 모든 날짜에 표시
      if (schedule.end_time) {
        const endDate = new Date(schedule.end_time)
        endDate.setHours(0, 0, 0, 0) // 종료일도 날짜만 비교
        
        return checkDate >= startDate && checkDate <= endDate
      } else {
        // 종료일이 없으면 시작일만 표시
        return (
          startDate.getDate() === checkDate.getDate() &&
          startDate.getMonth() === checkDate.getMonth() &&
          startDate.getFullYear() === checkDate.getFullYear()
        )
      }
    })
  }

  // 일정이 특정 날짜에서 시작일인지 확인
  const isScheduleStart = (schedule: Schedule, day: number) => {
    const checkDate = new Date(year, month, day)
    checkDate.setHours(0, 0, 0, 0)
    const startDate = new Date(schedule.start_time)
    startDate.setHours(0, 0, 0, 0)
    
    return (
      startDate.getDate() === checkDate.getDate() &&
      startDate.getMonth() === checkDate.getMonth() &&
      startDate.getFullYear() === checkDate.getFullYear()
    )
  }

  // 일정이 특정 날짜에서 종료일인지 확인
  const isScheduleEnd = (schedule: Schedule, day: number) => {
    if (!schedule.end_time) return false
    
    const checkDate = new Date(year, month, day)
    checkDate.setHours(0, 0, 0, 0)
    const endDate = new Date(schedule.end_time)
    endDate.setHours(0, 0, 0, 0)
    
    return (
      endDate.getDate() === checkDate.getDate() &&
      endDate.getMonth() === checkDate.getMonth() &&
      endDate.getFullYear() === checkDate.getFullYear()
    )
  }

  // 일정이 연속된 일정인지 확인 (시작일과 종료일이 다름)
  const isMultiDaySchedule = (schedule: Schedule) => {
    if (!schedule.end_time) return false
    
    const startDate = new Date(schedule.start_time)
    startDate.setHours(0, 0, 0, 0)
    const endDate = new Date(schedule.end_time)
    endDate.setHours(0, 0, 0, 0)
    
    return startDate.getTime() !== endDate.getTime()
  }

  // 날짜가 오늘인지 확인
  const isToday = (day: number) => {
    const today = new Date()
    return (
      day === today.getDate() &&
      month === today.getMonth() &&
      year === today.getFullYear()
    )
  }

  // 날짜 배열 생성
  const days = []
  // 빈 칸 추가 (첫 주)
  for (let i = 0; i < firstDayOfWeek; i++) {
    days.push(null)
  }
  // 날짜 추가
  for (let day = 1; day <= daysInMonth; day++) {
    days.push(day)
  }

  const weekDays = ['일', '월', '화', '수', '목', '금', '토']
  const monthNames = [
    '1월', '2월', '3월', '4월', '5월', '6월',
    '7월', '8월', '9월', '10월', '11월', '12월'
  ]

  return (
    <div className={`bg-white rounded-2xl shadow-lg p-6 border border-primary-100 ${className}`}>
      {/* 헤더 */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center space-x-4">
          <button
            onClick={goToPreviousMonth}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <ChevronLeftIcon className="w-5 h-5" />
          </button>
          <h2 className="text-2xl font-bold text-gray-800">
            {year}년 {monthNames[month]}
          </h2>
          <button
            onClick={goToNextMonth}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <ChevronRightIcon className="w-5 h-5" />
          </button>
        </div>
        <button
          onClick={goToToday}
          className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors"
        >
          오늘
        </button>
      </div>

      {/* 요일 헤더 */}
      <div className="grid grid-cols-7 gap-1 mb-2">
        {weekDays.map((day, index) => (
          <div
            key={index}
            className="text-center text-sm font-semibold text-gray-600 py-2"
          >
            {day}
          </div>
        ))}
      </div>

      {/* 캘린더 그리드 */}
      <div className="grid grid-cols-7 gap-0">
        {days.map((day, index) => {
          if (day === null) {
            return <div key={index} className="aspect-square" />
          }

          const daySchedules = getSchedulesForDate(day)
          const isTodayDate = isToday(day)
          const holiday = getHolidayForDate(day)
          const isHoliday = !!holiday
          const isSunday = index % 7 === 0
          
          // 디버깅: 공휴일이 있는 날짜 확인 (처음 몇 개만)
          if (holiday && day <= 5) {
            console.log(`🎉 공휴일 발견: ${year}-${month + 1}-${day} = ${holiday.name || holiday.holiday_name}`, holiday)
          }

          return (
            <div
              key={index}
              onClick={() => handleDateClick(day)}
              className={`
                aspect-square border border-gray-200 p-1 cursor-pointer
                hover:bg-gray-50 transition-colors relative overflow-visible
                ${isTodayDate ? 'bg-primary-50 border-primary-300' : ''}
                ${isHoliday || isSunday ? 'bg-red-50' : ''}
                ${index % 7 === 0 ? 'rounded-l-lg' : ''}
                ${index % 7 === 6 ? 'rounded-r-lg' : ''}
              `}
            >
              <div className="flex flex-col mb-1">
                <div className="flex items-center gap-0.5">
                  <div
                    className={`
                      text-sm font-medium
                      ${isTodayDate ? 'text-primary-600 font-bold' : ''}
                      ${isHoliday || isSunday ? 'text-red-600 font-bold' : 'text-gray-700'}
                    `}
                  >
                    {day}
                  </div>
                  {holiday && (
                    <span
                      className="text-[9px] text-red-600 font-semibold leading-tight"
                      title={holiday.name || holiday.holiday_name || '공휴일'}
                    >
                      {holiday.name || holiday.holiday_name || '공휴일'}
                    </span>
                  )}
                </div>
              </div>
              <div className="space-y-0.5 relative z-10">
                {daySchedules.slice(0, 3).map((schedule: Schedule) => {
                  const isMultiDay = isMultiDaySchedule(schedule)
                  const isStart = isScheduleStart(schedule, day)
                  const isEnd = isScheduleEnd(schedule, day)
                  
                  // 연속된 일정의 스타일 결정
                  let roundedClass = 'rounded'
                  let marginClass = ''
                  
                  if (isMultiDay) {
                    if (isStart && isEnd) {
                      // 시작일이면서 종료일 (단일일)
                      roundedClass = 'rounded'
                    } else if (isStart) {
                      // 시작일: 왼쪽만 둥글게, 왼쪽 여백 없음
                      roundedClass = 'rounded-l'
                      marginClass = 'ml-0'
                    } else if (isEnd) {
                      // 종료일: 오른쪽만 둥글게, 오른쪽 여백 없음
                      roundedClass = 'rounded-r'
                      marginClass = 'mr-0'
                    } else {
                      // 중간일: 모서리 둥글게 하지 않음, 양쪽 여백 없음
                      roundedClass = 'rounded-none'
                      marginClass = 'mx-0'
                    }
                  }
                  
                  return (
                    <div
                      key={schedule.id}
                      onClick={(e: MouseEvent) => {
                        e.stopPropagation()
                        handleViewSchedule(schedule)
                      }}
                      className={`text-xs px-1 truncate ${roundedClass} ${marginClass} relative z-20 flex items-center cursor-pointer hover:opacity-90`}
                      style={{
                        backgroundColor: schedule.color || '#3B82F6',
                        color: 'white',
                        marginLeft: isMultiDay && !isStart ? '-4px' : '0',
                        marginRight: isMultiDay && !isEnd ? '-4px' : '0',
                        height: '20px',
                        minHeight: '20px',
                        lineHeight: '20px'
                      }}
                      title={schedule.title}
                    >
                      {isStart ? schedule.title : '\u00A0'}
                    </div>
                  )
                })}
                {daySchedules.length > 3 && (
                  <div className="text-xs text-gray-500 px-1">
                    +{daySchedules.length - 3}개
                  </div>
                )}
              </div>
            </div>
          )
        })}
      </div>

      {/* 일정 모달 */}
      <AnimatePresence>
        {isModalOpen && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="bg-white rounded-2xl max-w-md w-full max-h-[90vh] flex flex-col"
            >
              {/* 헤더 - 고정 */}
              <div className="flex items-center justify-between p-6 pb-4 flex-shrink-0">
                <h3 className="text-xl font-bold text-gray-900">
                  {isViewMode ? '일정 상세' : isEditMode ? '일정 수정' : '일정 추가'}
                </h3>
                <button
                  onClick={() => {
                    setIsModalOpen(false)
                    resetForm()
                  }}
                  className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
                >
                  <XMarkIcon className="w-5 h-5" />
                </button>
              </div>

              {/* 상세 보기 모드 */}
              {isViewMode && viewingSchedule && (
                <>
                  {/* 내용 - 스크롤 가능 */}
                  <div className="px-6 overflow-y-auto flex-1">
                    <div className="space-y-4">
                      {/* 제목 */}
                      <div>
                        <label className="block text-sm font-medium text-gray-500 mb-1">
                          제목
                        </label>
                        <div className="text-lg font-semibold text-gray-900">
                          {viewingSchedule.title}
                        </div>
                      </div>

                      {/* 시작 시간 */}
                      <div>
                        <label className="block text-sm font-medium text-gray-500 mb-1">
                          시작 시간
                        </label>
                        <div className="text-base text-gray-900">
                          {formatDateTimeForDisplay(viewingSchedule.start_time)}
                        </div>
                      </div>

                      {/* 종료 시간 */}
                      {viewingSchedule.end_time && (
                        <div>
                          <label className="block text-sm font-medium text-gray-500 mb-1">
                            종료 시간
                          </label>
                          <div className="text-base text-gray-900">
                            {formatDateTimeForDisplay(viewingSchedule.end_time)}
                          </div>
                        </div>
                      )}

                      {/* 장소 - 있을 때만 표시 */}
                      {viewingSchedule.location && (
                        <div>
                          <label className="block text-sm font-medium text-gray-500 mb-1">
                            장소
                          </label>
                          <div className="text-base text-gray-900">
                            {viewingSchedule.location}
                          </div>
                        </div>
                      )}

                      {/* 설명 - 있을 때만 표시 */}
                      {viewingSchedule.description && (
                        <div>
                          <label className="block text-sm font-medium text-gray-500 mb-1">
                            설명
                          </label>
                          <div className="text-base text-gray-900 whitespace-pre-wrap">
                            {viewingSchedule.description}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* 하단 버튼 - 고정 */}
                  <div className="p-6 pt-4 border-t border-gray-200 flex gap-3 flex-shrink-0">
                    <button
                      onClick={() => {
                        if (viewingSchedule) {
                          handleDelete(viewingSchedule.id)
                        }
                      }}
                      className="flex-1 px-4 py-2 bg-red-500 text-white rounded-lg hover:bg-red-600 transition-colors font-medium"
                    >
                      삭제
                    </button>
                    <button
                      onClick={handleEditFromView}
                      className="flex-1 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors font-medium"
                    >
                      수정
                    </button>
                  </div>
                </>
              )}

              {/* 수정/추가 모드 */}
              {!isViewMode && (
                <>
                  {/* 내용 - 스크롤 가능 */}
                  <div className="px-6 overflow-y-auto flex-1">
                    <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    제목 *
                  </label>
                  <input
                    type="text"
                    value={formData.title}
                    onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                    placeholder="일정 제목을 입력하세요"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    시작 시간 *
                  </label>
                  <div className="flex gap-2">
                    <input
                      type="date"
                      value={formData.start_time ? (() => {
                        const date = new Date(formData.start_time)
                        const year = date.getFullYear()
                        const month = String(date.getMonth() + 1).padStart(2, '0')
                        const day = String(date.getDate()).padStart(2, '0')
                        return `${year}-${month}-${day}`
                      })() : ''}
                      onChange={(e) => {
                        const dateStr = e.target.value
                        if (dateStr && formData.start_time) {
                          const existingDate = new Date(formData.start_time)
                          const newDate = parseLocalDate(dateStr)
                          newDate.setHours(existingDate.getHours())
                          newDate.setMinutes(existingDate.getMinutes())
                          newDate.setSeconds(0)
                          setFormData({ ...formData, start_time: toLocalISOString(newDate) })
                        } else if (dateStr) {
                          const newDate = parseLocalDate(dateStr)
                          newDate.setHours(9)
                          newDate.setMinutes(0)
                          newDate.setSeconds(0)
                          setFormData({ ...formData, start_time: toLocalISOString(newDate) })
                        } else {
                          setFormData({ ...formData, start_time: '' })
                        }
                      }}
                      className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                    />
                    <select
                      value={formData.start_time ? String(new Date(formData.start_time).getHours()) : ''}
                      onChange={(e) => {
                        const hours = parseInt(e.target.value)
                        if (formData.start_time) {
                          const date = new Date(formData.start_time)
                          date.setHours(hours)
                          date.setSeconds(0)
                          setFormData({ ...formData, start_time: toLocalISOString(date) })
                        } else {
                          const today = new Date()
                          today.setHours(hours)
                          today.setMinutes(0)
                          today.setSeconds(0)
                          setFormData({ ...formData, start_time: toLocalISOString(today) })
                        }
                      }}
                      className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                    >
                      <option value="">시</option>
                      {Array.from({ length: 24 }, (_, i) => (
                        <option key={i} value={String(i)}>
                          {String(i).padStart(2, '0')}시
                        </option>
                      ))}
                    </select>
                    <select
                      value={formData.start_time ? String(Math.round(new Date(formData.start_time).getMinutes() / 30) * 30) : ''}
                      onChange={(e) => {
                        const minutes = parseInt(e.target.value)
                        if (formData.start_time) {
                          const date = new Date(formData.start_time)
                          date.setMinutes(minutes)
                          date.setSeconds(0)
                          setFormData({ ...formData, start_time: toLocalISOString(date) })
                        } else {
                          const today = new Date()
                          today.setMinutes(minutes)
                          today.setSeconds(0)
                          setFormData({ ...formData, start_time: toLocalISOString(today) })
                        }
                      }}
                      className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                    >
                      <option value="">분</option>
                      <option value="0">00분</option>
                      <option value="30">30분</option>
                    </select>
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    종료 시간
                  </label>
                  <div className="flex gap-2">
                    <input
                      type="date"
                      value={formData.end_time ? (() => {
                        const date = new Date(formData.end_time)
                        const year = date.getFullYear()
                        const month = String(date.getMonth() + 1).padStart(2, '0')
                        const day = String(date.getDate()).padStart(2, '0')
                        return `${year}-${month}-${day}`
                      })() : ''}
                      onChange={(e) => {
                        const dateStr = e.target.value
                        if (dateStr && formData.end_time) {
                          const existingDate = new Date(formData.end_time)
                          const newDate = parseLocalDate(dateStr)
                          newDate.setHours(existingDate.getHours())
                          newDate.setMinutes(existingDate.getMinutes())
                          newDate.setSeconds(0)
                          setFormData({ ...formData, end_time: toLocalISOString(newDate) })
                        } else if (dateStr) {
                          const newDate = parseLocalDate(dateStr)
                          newDate.setHours(18)
                          newDate.setMinutes(0)
                          newDate.setSeconds(0)
                          setFormData({ ...formData, end_time: toLocalISOString(newDate) })
                        } else {
                          setFormData({ ...formData, end_time: '' })
                        }
                      }}
                      className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                    />
                    <select
                      value={formData.end_time ? String(new Date(formData.end_time).getHours()) : ''}
                      onChange={(e) => {
                        const hours = parseInt(e.target.value)
                        if (formData.end_time) {
                          const date = new Date(formData.end_time)
                          date.setHours(hours)
                          date.setSeconds(0)
                          setFormData({ ...formData, end_time: toLocalISOString(date) })
                        } else if (formData.start_time) {
                          const date = new Date(formData.start_time)
                          date.setHours(hours)
                          date.setSeconds(0)
                          setFormData({ ...formData, end_time: toLocalISOString(date) })
                        } else {
                          const today = new Date()
                          today.setHours(hours)
                          today.setMinutes(0)
                          today.setSeconds(0)
                          setFormData({ ...formData, end_time: toLocalISOString(today) })
                        }
                      }}
                      className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                    >
                      <option value="">시</option>
                      {Array.from({ length: 24 }, (_, i) => (
                        <option key={i} value={String(i)}>
                          {String(i).padStart(2, '0')}시
                        </option>
                      ))}
                    </select>
                    <select
                      value={formData.end_time ? String(Math.round(new Date(formData.end_time).getMinutes() / 30) * 30) : ''}
                      onChange={(e) => {
                        const minutes = parseInt(e.target.value)
                        if (formData.end_time) {
                          const date = new Date(formData.end_time)
                          date.setMinutes(minutes)
                          date.setSeconds(0)
                          setFormData({ ...formData, end_time: toLocalISOString(date) })
                        } else if (formData.start_time) {
                          const date = new Date(formData.start_time)
                          date.setMinutes(minutes)
                          date.setSeconds(0)
                          setFormData({ ...formData, end_time: toLocalISOString(date) })
                        } else {
                          const today = new Date()
                          today.setMinutes(minutes)
                          today.setSeconds(0)
                          setFormData({ ...formData, end_time: toLocalISOString(today) })
                        }
                      }}
                      className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                    >
                      <option value="">분</option>
                      <option value="0">00분</option>
                      <option value="30">30분</option>
                    </select>
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    설명
                  </label>
                  <textarea
                    value={formData.description}
                    onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                    rows={3}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent resize-none"
                    placeholder="일정 설명을 입력하세요"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    장소
                  </label>
                  <input
                    type="text"
                    value={formData.location}
                    onChange={(e) => setFormData({ ...formData, location: e.target.value })}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                    placeholder="장소를 입력하세요"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    색상
                  </label>
                  <div className="grid grid-cols-6 gap-2 mb-3">
                    {colorOptions.map((color) => (
                      <button
                        key={color.value}
                        type="button"
                        onClick={() => setFormData({ ...formData, color: color.value })}
                        className={`
                          w-full h-12 rounded-lg border-2 transition-all
                          ${formData.color === color.value 
                            ? 'border-gray-800 scale-105 shadow-md' 
                            : 'border-gray-300 hover:border-gray-400'
                          }
                        `}
                        style={{ backgroundColor: color.value }}
                        title={color.name}
                      >
                        {formData.color === color.value && (
                          <div className="flex items-center justify-center h-full">
                            <svg
                              className="w-6 h-6 text-white drop-shadow-lg"
                              fill="none"
                              stroke="currentColor"
                              viewBox="0 0 24 24"
                            >
                              <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={3}
                                d="M5 13l4 4L19 7"
                              />
                            </svg>
                          </div>
                        )}
                      </button>
                    ))}
                  </div>
                  <div className="mt-2 pt-3 border-t border-gray-200">
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      커스텀 색상
                    </label>
                    <div className="flex items-center space-x-2">
                      <input
                        type="color"
                        value={formData.color}
                        onChange={(e) => setFormData({ ...formData, color: e.target.value })}
                        className="w-16 h-12 border border-gray-300 rounded-lg cursor-pointer"
                      />
                      <input
                        type="text"
                        value={formData.color}
                        onChange={(e) => {
                          // HEX 색상 형식 검증
                          const hexPattern = /^#[0-9A-Fa-f]{6}$/
                          if (hexPattern.test(e.target.value) || e.target.value === '') {
                            setFormData({ ...formData, color: e.target.value || '#3B82F6' })
                          }
                        }}
                        className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                        placeholder="#3B82F6"
                      />
                    </div>
                    <p className="mt-1 text-xs text-gray-500">
                      원하는 색상을 직접 선택하거나 HEX 코드를 입력하세요
                    </p>
                  </div>
                </div>
                    </div>
                  </div>

                {/* 버튼 - 하단 고정 */}
                <div className="p-6 pt-4 flex-shrink-0 border-t border-gray-200">
                  <div className="flex space-x-3">
                    {isEditMode && editingSchedule && (
                      <button
                        onClick={() => handleDelete(editingSchedule.id)}
                        className="flex-1 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
                      >
                        삭제
                      </button>
                    )}
                    <button
                      onClick={() => {
                        setIsModalOpen(false)
                        resetForm()
                      }}
                      className="flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors"
                    >
                      취소
                    </button>
                    <button
                      onClick={handleSave}
                      disabled={!formData.title || !formData.start_time}
                      className="flex-1 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      저장
                    </button>
                  </div>
                </div>
                </>
              )}
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  )
}

