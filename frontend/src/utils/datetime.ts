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
  const str = typeof utcDateString === 'string' ? utcDateString.trim() : ''

  // ISO 문자열에 포함된 타임존 오프셋(+09:00, Z 등)을 파싱한다.
  // - Z 또는 +00:00 → UTC로 간주하고 KST(+09:00)로 보정
  // - +09:00 등 명시된 오프셋 → 이미 오프셋이 있으므로 추가 보정 없음
  // - 오프셋이 없거나 Date 객체 → 입력 시간을 그대로 사용 (중복 보정 방지)
  const offsetMatch = str.match(/([+-]\d{2}):?(\d{2})$/)
  const isZulu = /z$/i.test(str)

  if (offsetMatch) {
    const sign = offsetMatch[1].startsWith('-') ? -1 : 1
    const hours = Math.abs(Number(offsetMatch[1]))
    const minutes = Number(offsetMatch[2])
    const offsetMinutes = sign * (hours * 60 + minutes)
    const kstOffsetMinutes = 9 * 60
    const diffMinutes = kstOffsetMinutes - offsetMinutes
    return new Date(date.getTime() + diffMinutes * 60 * 1000)
  }

  if (isZulu) {
    return new Date(date.getTime() + 9 * 60 * 60 * 1000)
  }

  // 오프셋 정보가 없으면 로컬 시간을 그대로 사용한다.
  return date
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

