/**
 * 날짜/시간 유틸리티
 * UTC를 한국 시간대(KST)로 자동 변환
 */

/**
 * UTC 날짜 문자열을 한국 시간대 Date 객체로 변환
 * @param utcDateString - ISO 형식의 UTC 날짜 문자열
 * @returns KST 시간대의 Date 객체
 */
export const toKST = (utcDateString: string | Date): Date => {
  const date = typeof utcDateString === 'string' ? new Date(utcDateString) : utcDateString
  // UTC 시간에 9시간 추가 (KST = UTC+9)
  return new Date(date.getTime() + (9 * 60 * 60 * 1000))
}

/**
 * UTC 날짜 문자열을 한국 시간대로 포맷팅
 * @param utcDateString - ISO 형식의 UTC 날짜 문자열
 * @param options - Intl.DateTimeFormat 옵션
 * @returns 포맷팅된 한국 시간 문자열
 */
export const formatKST = (
  utcDateString: string | Date,
  options?: Intl.DateTimeFormatOptions
): string => {
  const kstDate = toKST(utcDateString)
  return kstDate.toLocaleString('ko-KR', options)
}

/**
 * 날짜만 표시 (YYYY. M. D.)
 */
export const formatKSTDate = (utcDateString: string | Date): string => {
  return formatKST(utcDateString, {
    year: 'numeric',
    month: 'numeric',
    day: 'numeric'
  })
}

/**
 * 날짜 + 요일 표시
 */
export const formatKSTDateWithDay = (utcDateString: string | Date): {
  date: string
  dayOfWeek: string
} => {
  const kstDate = toKST(utcDateString)
  const dayOfWeek = ['일', '월', '화', '수', '목', '금', '토'][kstDate.getDay()]
  return {
    date: kstDate.toLocaleDateString('ko-KR'),
    dayOfWeek
  }
}

/**
 * 시간만 표시 (HH:MM)
 */
export const formatKSTTime = (utcDateString: string | Date): string => {
  const kstDate = toKST(utcDateString)
  const hours = kstDate.getHours().toString().padStart(2, '0')
  const minutes = kstDate.getMinutes().toString().padStart(2, '0')
  return `${hours}:${minutes}`
}

/**
 * 전체 날짜시간 표시
 */
export const formatKSTDateTime = (utcDateString: string | Date): string => {
  return formatKST(utcDateString, {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
}

