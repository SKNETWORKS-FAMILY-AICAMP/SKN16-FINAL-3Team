/**
 * 일정 관리 캘린더 컴포넌트
 */
import { useState, useEffect } from 'react'
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
  const [loading, setLoading] = useState(false)

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

  // 일정 로드
  useEffect(() => {
    loadSchedules()
  }, [currentDate])

  const loadSchedules = async () => {
    try {
      setLoading(true)
      const startDate = new Date(year, month, 1).toISOString().split('T')[0]
      const endDate = new Date(year, month + 1, 0).toISOString().split('T')[0]
      const data = await scheduleAPI.getSchedules(startDate, endDate)
      setSchedules(data || [])
    } catch (error) {
      console.error('Failed to load schedules:', error)
    } finally {
      setLoading(false)
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
    const clickedDate = new Date(year, month, day)
    setSelectedDate(clickedDate)
    const dateStr = clickedDate.toISOString().split('T')[0]
    const timeStr = clickedDate.toTimeString().split(' ')[0].slice(0, 5)
    setFormData({
      ...formData,
      start_time: `${dateStr}T${timeStr}`,
      end_time: ''
    })
    setIsEditMode(false)
    setEditingSchedule(null)
    setIsModalOpen(true)
  }

  // 일정 저장
  const handleSave = async () => {
    try {
      if (isEditMode && editingSchedule) {
        await scheduleAPI.updateSchedule(editingSchedule.id, formData)
      } else {
        await scheduleAPI.createSchedule(formData)
      }
      setIsModalOpen(false)
      resetForm()
      loadSchedules()
    } catch (error) {
      console.error('Failed to save schedule:', error)
      alert('일정 저장에 실패했습니다.')
    }
  }

  // 일정 삭제
  const handleDelete = async (scheduleId: number) => {
    if (!window.confirm('정말로 이 일정을 삭제하시겠습니까?')) {
      return
    }
    try {
      await scheduleAPI.deleteSchedule(scheduleId)
      loadSchedules()
    } catch (error) {
      console.error('Failed to delete schedule:', error)
      alert('일정 삭제에 실패했습니다.')
    }
  }

  // 일정 수정
  const handleEdit = (schedule: Schedule) => {
    setEditingSchedule(schedule)
    setIsEditMode(true)
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
    setEditingSchedule(null)
  }

  // 특정 날짜의 일정 가져오기
  const getSchedulesForDate = (day: number) => {
    const date = new Date(year, month, day)
    return schedules.filter(schedule => {
      const scheduleDate = new Date(schedule.start_time)
      return (
        scheduleDate.getDate() === date.getDate() &&
        scheduleDate.getMonth() === date.getMonth() &&
        scheduleDate.getFullYear() === date.getFullYear()
      )
    })
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
      <div className="grid grid-cols-7 gap-1">
        {days.map((day, index) => {
          if (day === null) {
            return <div key={index} className="aspect-square" />
          }

          const daySchedules = getSchedulesForDate(day)
          const isTodayDate = isToday(day)

          return (
            <div
              key={index}
              onClick={() => handleDateClick(day)}
              className={`
                aspect-square border border-gray-200 rounded-lg p-1 cursor-pointer
                hover:bg-gray-50 transition-colors relative
                ${isTodayDate ? 'bg-primary-50 border-primary-300' : ''}
              `}
            >
              <div
                className={`
                  text-sm font-medium mb-1
                  ${isTodayDate ? 'text-primary-600 font-bold' : 'text-gray-700'}
                `}
              >
                {day}
              </div>
              <div className="space-y-0.5">
                {daySchedules.slice(0, 3).map((schedule) => (
                  <div
                    key={schedule.id}
                    onClick={(e) => {
                      e.stopPropagation()
                      handleEdit(schedule)
                    }}
                    className="text-xs px-1 py-0.5 rounded truncate"
                    style={{
                      backgroundColor: schedule.color || '#3B82F6',
                      color: 'white'
                    }}
                    title={schedule.title}
                  >
                    {schedule.title}
                  </div>
                ))}
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
              className="bg-white rounded-2xl p-6 max-w-md w-full"
            >
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-xl font-bold text-gray-900">
                  {isEditMode ? '일정 수정' : '일정 추가'}
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
                  <input
                    type="datetime-local"
                    value={formData.start_time}
                    onChange={(e) => setFormData({ ...formData, start_time: e.target.value })}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    종료 시간
                  </label>
                  <input
                    type="datetime-local"
                    value={formData.end_time}
                    onChange={(e) => setFormData({ ...formData, end_time: e.target.value })}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                  />
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
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    색상
                  </label>
                  <div className="flex items-center space-x-2">
                    <input
                      type="color"
                      value={formData.color}
                      onChange={(e) => setFormData({ ...formData, color: e.target.value })}
                      className="w-12 h-12 border border-gray-300 rounded-lg cursor-pointer"
                    />
                    <input
                      type="text"
                      value={formData.color}
                      onChange={(e) => setFormData({ ...formData, color: e.target.value })}
                      className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                      placeholder="#3B82F6"
                    />
                  </div>
                </div>

                <div className="flex space-x-3 pt-4">
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
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  )
}

