/**
 * 시뮬레이션 피드백 페이지
 * 5가지 역량 평가 결과를 시각화하여 표시
 */
import React, { useState, useEffect } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import {
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Cell
} from 'recharts'
import {
  BookOpenIcon,
  WrenchScrewdriverIcon,
  HeartIcon,
  ChatBubbleLeftIcon,
  FaceSmileIcon,
  BoltIcon,
  TrophyIcon,
  ArrowLeftIcon,
  CheckCircleIcon,
  XCircleIcon,
  UserIcon,
  DocumentTextIcon,
  ChevronDownIcon,
  ChevronUpIcon
} from '@heroicons/react/24/outline'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkBreaks from 'remark-breaks'
import { useAuthStore } from '../store/authStore'
import { api } from '../utils/api'
import {
  ExclamationTriangleIcon,
  XMarkIcon
} from '@heroicons/react/24/outline'

interface CompetencyScore {
  name: string
  score: number
  maxScore: number
}

interface GoalAchievement {
  total: number
  achieved: number
  rate: number
  goals: Array<{
    text: string
    achieved: boolean
    turn?: number  // 🔍 2단계: 달성한 턴 번호
    evidence?: string  // 🔍 3단계: 달성 증거 발화
  }>
}

interface BreakdownItem {
  score: number
  max: number
  reason: string
}

interface BreakdownData {
  knowledge?: Record<string, BreakdownItem>
  skill?: Record<string, BreakdownItem>
  clarity?: Record<string, BreakdownItem>
  kindness?: Record<string, BreakdownItem>
  confidence?: Record<string, BreakdownItem>
  persona_fit?: Record<string, BreakdownItem>
}

type BreakdownKey = 'knowledge' | 'skill' | 'kindness' | 'clarity' | 'persona_fit'

// 세부 평가 근거 항목 라벨 매핑 (백엔드 키 → 화면용 한국어)
const BREAKDOWN_LABELS: Record<string, string> = {
  // 지식(knowledge)
  product_accuracy: '상품 정보 정확성',
  product_knowledge: '상품 지식',
  procedure_knowledge: '절차/규정 지식',
  general_finance: '일반 금융 지식',
  category_specific: '상품 특성 이해',
  regulation_policy: '규정·정책 이해',
  general_banking: '일반 은행 실무 지식',
  procedure_explanation: '절차 설명 정확성',
  exchange_rate_fee_info: '환율·수수료 안내',
  foreign_exchange_regulation: '외환 규정 이해',

  // 기술(skill)
  conversation_flow: '대화 흐름 관리',
  goal_achievement: '목표 달성도',
  question_usage: '질문 활용',
  feedback_loop: '이해도 확인·피드백',

  // 전달력(clarity)
  sentence_structure: '문장 구조·전달력',
  assertive_ratio: '확정적 표현 비율',
  terminology: '용어 사용 적절성',
  number_clarity: '수치·단위 명확성',

  // 친절도(kindness)
  politeness: '기본 예의·존댓말',
  choice_respect: '선택 존중·강요 여부',
  empathy: '공감 표현',
  help_willingness: '도움 의지 표현',
  negative_avoidance: '부정적 표현 회피',

  // 페르소나 정합도(persona_fit) - 기본(불만형 기준)
  empathy_apology: '공감·사과 타이밍',
  solution_presentation: '해결책 제시 방식',
  negative_pattern_avoidance: '부정 패턴 회피'
}

type PersonaCategory = 'complaint' | 'urgent' | 'positive' | 'general'

// 페르소나 정보 문구에서 고객 타입 유추 (불만형/급함형/긍정형/일반)
const detectPersonaCategory = (personaInfo?: string | null): PersonaCategory => {
  if (!personaInfo) return 'general'
  if (personaInfo.includes('불만형')) return 'complaint'
  if (personaInfo.includes('급함형')) return 'urgent'
  if (personaInfo.includes('긍정형')) return 'positive'
  return 'general'
}

// 페르소나 타입별 세부 항목 라벨 오버라이드
const PERSONA_BREAKDOWN_LABELS_BY_TYPE: Record<PersonaCategory, Record<string, string>> = {
  // A. 불만형 고객
  complaint: {
    empathy_apology: '공감·사과 타이밍',
    solution_presentation: '해결책 제시 방식',
    negative_pattern_avoidance: '부정 패턴 회피'
  },
  // B. 급함형 고객
  urgent: {
    empathy_apology: '빠른 응답·처리 의지',
    solution_presentation: '설명의 간결성',
    negative_pattern_avoidance: '핵심 정보 전달'
  },
  // C. 긍정형 고객
  positive: {
    empathy_apology: '긍정 반응 대응',
    solution_presentation: '추가 안내·제안',
    negative_pattern_avoidance: '분위기 저해 표현 회피'
  },
  // D. 일반 고객 (기본 친절도 기준)
  general: {
    empathy_apology: '공감·안심 전달',
    solution_presentation: '안내·정리 방식',
    negative_pattern_avoidance: '부정적 표현 회피'
  }
}

const getPersonaBreakdownLabel = (key: string, personaInfo?: string | null): string => {
  const base = BREAKDOWN_LABELS[key] || key
  const category = detectPersonaCategory(personaInfo)
  const overrides = PERSONA_BREAKDOWN_LABELS_BY_TYPE[category]
  return overrides[key] || base
}

interface FeedbackData {
  overallScore: number
  grade: string
  performanceLevel: string
  summary: string
  persona_info?: string
  situation_info?: string
  competencies: CompetencyScore[]
  detailedFeedback: {
    knowledge: { score: number; feedback: string; breakdown?: Record<string, BreakdownItem> }
    skill: { score: number; feedback: string; breakdown?: Record<string, BreakdownItem> }
    kindness: { score: number; feedback: string; breakdown?: Record<string, BreakdownItem> }
    clarity: { score: number; feedback: string; breakdown?: Record<string, BreakdownItem> }  // 전달력 (명확성)
    persona_fit: { score: number; feedback: string; breakdown?: Record<string, BreakdownItem> }  // 페르소나 정합도
  }
  breakdown?: BreakdownData  // 🧪 테스트 모드용: 전체 breakdown 데이터
  improvements: string | string[]  // 문자열 또는 배열 모두 허용
  duration_seconds?: number
  conversation_history?: Array<{ role: string; text: string; timestamp?: string }>
  goalAchievement?: GoalAchievement
          rag_evaluations?: Array<{  // 🧪 테스트 모드: RAG 평가 결과
            turn_index: number
            role: string
            expected_product_code?: string
            utterance?: string  // 발화 내용
            evaluation: {
              score: number
              keyword_score: number
              rag_product_info_score?: number
              product_extraction_score?: number
              found_keywords: string[]
              missing_keywords: string[]
              rag_info_keywords_found?: string[]
              extracted_product_keywords?: string[]
              extracted_categories?: string[]  // 자동 추출된 카테고리
              claim_verifications?: Array<{  // 🆕 claim 검증 결과
                claim: string
                is_accurate: boolean
                ground_truth?: string
                similarity?: number
                verification_method?: string
                llm_reasoning?: string
              }>
              product_evidence?: {  // 🧪 상품 데이터 근거
                matched_chunks?: Array<{
                  subsection_title?: string
                  text?: string
                  breadcrumb?: string
                  similarity?: number  // 벡터 검색 유사도 점수
                }>
                similarity_scores?: number[]  // 벡터 검색 유사도 점수 목록
                key_information?: string[]
                missing_information?: string[]
                error?: string  // 벡터 검색 실패 시 오류 메시지
                error_detail?: string  // 벡터 검색 실패 시 상세 오류 메시지
              }
            }
          }>
  rag_summary?: {  // 🧪 테스트 모드: RAG 평가 종합 결과
    total_evaluations: number
    average_score: number
    employee_count: number
    customer_count: number
    employee_average: number
    customer_average: number
  }
}

const naturalizeBeforeAfter = (text: string): string => {
  if (!text) return text
  const combinedPattern = /Before:\s*([^→\n]+?)\s*→\s*After:\s*([^\n]+)/gi
  let transformed = text.replace(
    combinedPattern,
    (_, before, after) => `예시(이전 표현): ${before.trim()} ⇒ 개선 제안: ${after.trim()}`
  )
  transformed = transformed
    .replace(/Before:\s*([^\n]+)/gi, '예전 표현: $1')
    .replace(/After:\s*([^\n]+)/gi, '개선 표현: $1')
  return transformed
}

// 마크다운 렌더링 전처리: 특수문자 포함된 볼드 텍스트 처리
const preprocessMarkdown = (input: string): string => {
  if (!input || typeof input !== 'string') return input || ''
  
  try {
    let processed = input.replace(/\*\*['"](.*?)['"]\*\*/g, '**$1**')
    processed = processed.replace(/\*\*[\u2018\u2019\u201C\u201D«»](.*?)[\u2018\u2019\u201C\u201D«»]\*\*/g, '**$1**')
    processed = processed.replace(/\*\*([^\*]*?)[\u2018\u2019\u201C\u201D«»]\*\*/g, '**$1**')
    processed = processed.replace(/\*\*[\u2018\u2019\u201C\u201D«»]([^\*]*?)\*\*/g, '**$1**')
    processed = processed.replace(/\*\*([^\*]+?)([!?.,])\*\*/g, '**$1$2**')
    processed = processed.replace(/(\*\*)\s+([^\*]+)\s+(\*\*)/g, '**$2**')
    processed = naturalizeBeforeAfter(processed)
    return processed
  } catch (error) {
    console.error('preprocessMarkdown error:', error)
    return input || ''
  }
}

// 공통 마크다운 컴포넌트 생성 함수
const createMarkdownComponents = (colorClass: string, bgClass: string) => {
  return {
    strong: ({ children }: { children?: React.ReactNode }) => (
      <strong className={`font-bold ${colorClass} ${bgClass} px-1.5 py-0.5 rounded`}>
        {children}
      </strong>
    ),
    p: ({ children }: { children?: React.ReactNode }) => <p className="mb-2 last:mb-0">{children}</p>,
    ul: ({ children }: { children?: React.ReactNode }) => <ul className="list-disc list-inside mb-2 space-y-1 ml-2">{children}</ul>,
    ol: ({ children }: { children?: React.ReactNode }) => <ol className="list-decimal list-inside mb-2 space-y-1 ml-2">{children}</ol>,
    li: ({ children }: { children?: React.ReactNode }) => <li className="ml-1">{children}</li>,
    h1: ({ children }: { children?: React.ReactNode }) => <h1 className="text-base font-bold mb-2 mt-3 first:mt-0 text-gray-900">{children}</h1>,
    h2: ({ children }: { children?: React.ReactNode }) => <h2 className="text-sm font-bold mb-2 mt-3 first:mt-0 text-gray-900">{children}</h2>,
    h3: ({ children }: { children?: React.ReactNode }) => <h3 className="text-sm font-semibold mb-1 mt-2 first:mt-0 text-gray-900">{children}</h3>,
    code: ({ children, className }: { children?: React.ReactNode; className?: string }) => (
      <code className={`${className || ''} bg-gray-100 px-1 py-0.5 rounded text-sm font-mono`}>
        {children}
      </code>
    ),
    blockquote: ({ children }: { children?: React.ReactNode }) => (
      <blockquote className="border-l-4 border-gray-300 pl-4 italic my-2 text-gray-600">
        {children}
      </blockquote>
    ),
    br: () => <br />,
    hr: () => <hr className="my-3 border-gray-300" />
  }
}

const SimulationFeedback: React.FC = () => {
  const navigate = useNavigate()
  const location = useLocation()
  const [feedbackData, setFeedbackData] = useState<FeedbackData | null>(null)
  const [loading, setLoading] = useState(true)
  const [isGoalsExpanded, setIsGoalsExpanded] = useState(false) // 목표 달성 현황 접기/펼치기 상태
  const [breakdownOpen, setBreakdownOpen] = useState<Record<BreakdownKey, boolean>>({
    knowledge: false,
    skill: false,
    kindness: false,
    clarity: false,
    persona_fit: false
  }) // 역량별 세부 평가 근거 접기/펼치기 상태
  const fromHistory = location.state?.fromHistory || false // 히스토리에서 온 경우인지 확인
  const returnScrollY = location.state?.returnScrollY || 0 // 돌아갈 스크롤 위치
  
  // 버그 신고 관련 상태
  const [bugReportModalOpen, setBugReportModalOpen] = useState(false)
  const [selectedMessageIndex, setSelectedMessageIndex] = useState<number | null>(null)
  const [bugReportOriginalText, setBugReportOriginalText] = useState('')
  const [bugReportRecognizedText, setBugReportRecognizedText] = useState('')
  const [bugReportDescription, setBugReportDescription] = useState('')
  const [bugReportSubmitting, setBugReportSubmitting] = useState(false)

  const toggleBreakdown = (key: BreakdownKey) => {
    setBreakdownOpen((prev) => ({ ...prev, [key]: !prev[key] }))
  }

  // 버그 신고 모달 열기
  const openBugReportModal = (messageIndex: number, messageText: string) => {
    setSelectedMessageIndex(messageIndex)
    setBugReportRecognizedText(messageText) // STT가 인식한 텍스트
    setBugReportOriginalText('') // 사용자가 실제로 말한 내용 (입력 필요)
    setBugReportDescription('') // 상세 설명 초기화
    setBugReportModalOpen(true)
  }

  // 버그 신고 제출
  const submitBugReport = async () => {
    if (!selectedMessageIndex !== null && !bugReportOriginalText.trim()) {
      alert('실제로 말한 내용을 입력해주세요.')
      return
    }

    if (!feedbackData?.conversation_history || selectedMessageIndex === null) {
      return
    }

    const message = feedbackData.conversation_history[selectedMessageIndex]
    const isEmployee = message.role === 'employee' || message.role === 'user'

    setBugReportSubmitting(true)
    try {
      // 피드백 ID 가져오기 (location.state에서)
      const feedbackId = location.state?.feedbackId || null

      await api.post('/rag-simulation/stt-bug-report', {
        feedback_id: feedbackId,
        conversation_index: selectedMessageIndex,
        message_role: isEmployee ? 'employee' : 'customer',
        original_text: bugReportOriginalText.trim(),
        recognized_text: bugReportRecognizedText,
        description: bugReportDescription.trim() || null
      })

      alert('버그 신고가 접수되었습니다. 감사합니다.')
      setBugReportModalOpen(false)
      setBugReportOriginalText('')
      setBugReportRecognizedText('')
      setBugReportDescription('')
      setSelectedMessageIndex(null)
    } catch (error: any) {
      console.error('버그 신고 제출 실패:', error)
      alert('버그 신고 제출에 실패했습니다. 다시 시도해주세요.')
    } finally {
      setBugReportSubmitting(false)
    }
  }

  useEffect(() => {
    // 페이지 진입 시 항상 맨 위로 스크롤
    window.scrollTo(0, 0)
    
    // location.state에서 피드백 데이터를 받아오거나, API에서 조회
    if (location.state?.feedbackData) {
      const feedback = location.state.feedbackData
      console.log('📊 피드백 데이터 수신:', {
        hasRagEvaluations: !!feedback.rag_evaluations,
        ragEvaluationsCount: feedback.rag_evaluations?.length || 0,
        hasRagSummary: !!feedback.rag_summary,
        ragSummary: feedback.rag_summary,
        allKeys: Object.keys(feedback),
        ragEvaluationsSample: feedback.rag_evaluations?.slice(0, 2) // 처음 2개만 샘플
      })
      
      // 🧪 RAG 평가 결과가 없으면 경고 (테스트 모드일 때만)
      // 일반 모드(is_test_mode: false)에서는 RAG 평가 결과가 없는 것이 정상이므로 경고하지 않음
      const isTestMode = feedback.is_test_mode === true
      if (isTestMode && (!feedback.rag_evaluations || feedback.rag_evaluations.length === 0)) {
        console.warn('🧪 ⚠️ 테스트 모드인데 피드백 데이터에 RAG 평가 결과가 없습니다!', {
          feedbackKeys: Object.keys(feedback),
          hasRagEvaluations: !!feedback.rag_evaluations,
          ragEvaluationsType: typeof feedback.rag_evaluations,
          ragEvaluationsValue: feedback.rag_evaluations,
          hasRagSummary: !!feedback.rag_summary,
          situation: feedback.situation,
          persona: feedback.persona,
          is_test_mode: feedback.is_test_mode
        })
      } else if (!isTestMode) {
        console.log('✅ 일반 모드: RAG 평가 결과가 없는 것이 정상입니다.', {
          is_test_mode: feedback.is_test_mode
        })
      } else {
        console.log('🧪 ✅ RAG 평가 결과 확인:', {
          total: feedback.rag_evaluations.length,
          firstEval: feedback.rag_evaluations[0],
          summary: feedback.rag_summary,
          allEvaluations: feedback.rag_evaluations.map((e: any) => ({
            turn: e.turn_index,
            role: e.role,
            score: e.evaluation?.score
          }))
        })
      }
      
      setFeedbackData(feedback)
      setLoading(false)
    } else {
      // 샘플 데이터로 폴백 (테스트 및 미리보기용)
      loadFeedbackData()
    }
  }, [location.state])

  const loadFeedbackData = async () => {
    // 샘플 데이터 (테스트 및 미리보기용)
    // 실제 시뮬레이션에서는 location.state로 데이터가 전달됨
    setFeedbackData({
      overallScore: 87,
      grade: 'B',
      performanceLevel: '우수한 성과',
      summary: '전반적으로 우수한 고객 응대 역량을 보여주고 있습니다. 특히 친절도와 공감도 부분에서 탁월한 능력을 발휘하고 있으며, 안내 흐름을 더욱 체계적으로 수행한다면 완벽한 은행원으로 성장할 수 있을 것입니다.',
      competencies: [
        { name: '지식', score: 85, maxScore: 100 },
        { name: '기술', score: 78, maxScore: 100 },
        { name: '친절도', score: 95, maxScore: 100 },
        { name: '전달력', score: 85, maxScore: 100 },
        { name: '페르소나 정합도', score: 80, maxScore: 100 }
      ],
      detailedFeedback: {
        knowledge: {
          score: 85,
          feedback: '상품에 대한 설명이 정확하고 상세합니다. 예적금, 대출, 카드 등 주요 상품의 특징과 이자, 가입조건을 정확하게 안내하였습니다. 다만 신상품에 대한 추가 학습이 필요합니다.'
        },
        skill: {
          score: 78,
          feedback: '고객의 니즈를 파악하는 질문 단계와 상담 안내 후 확인 절차를 대체로 잘 수행하였습니다. 다만 일부 상황에서 \'질문 → 응답 → 확인\'의 흐름이 생략되거나 순서가 바뀌는 경우가 있었습니다.'
        },
        kindness: {
          score: 95,
          feedback: '매우 친절한 응대를 보여주었습니다. \'감사합니다.\', \'도움이 되셨기를 바랍니다.\', \'궁금하신 점이 더 있으신가요?\' 등 정중한 표현을 자주 사용하였고, 고객을 배려하는 태도가 돋보였습니다.'
        },
        clarity: {
          score: 85,
          feedback: '문장이 간결하고 명확하며, 대부분 단정적이고 확실한 어투로 안내하였습니다. 복잡한 금융용어를 쉽게 풀어서 설명하였고, 한 문장에 한 가지 내용만 전달하여 고객이 이해하기 쉽게 안내하였습니다. \'~입니다.\', \'~됩니다.\'의 명확한 표현을 주로 사용했으나, 간혹 \'~같습니다.\', \'~것 같아요.\' 같은 불확실한 표현이 사용되어 아쉬웠습니다. 적절한 문장 길이를 유지하면서도 더욱 자신감 있는 어투로 정보를 전달한다면 고객에게 더욱 신뢰감을 줄 수 있을 것입니다.'
        },
        persona_fit: {
          score: 80,
          feedback: '고객의 페르소나 타입에 맞는 대응을 보여주었습니다. 고객의 성향을 파악하고 적절한 톤과 스타일로 응대하였습니다.'
        }
      },
      improvements: '친절도는 잘 유지하시면서 \'질문 → 응답 → 확인\' 흐름을 더 체계적으로 수행하고 전달력을 향상시키는 연습을 하시면 더욱 전문적인 응대가 가능합니다.'
    })
    setLoading(false)
  }

  const getGradeColor = (grade: string) => {
    switch (grade) {
      case 'A+': return 'text-green-600'
      case 'A': return 'text-green-600'
      case 'B+': return 'text-blue-600'
      case 'B': return 'text-blue-600'
      case 'C+': return 'text-yellow-600'
      case 'C': return 'text-yellow-600'
      case 'D': return 'text-orange-600'
      case 'F': return 'text-red-600'
      default: return 'text-gray-600'
    }
  }

  const getPerformanceLevelStyle = (level: string) => {
    if (level.includes('우수') || level.includes('탁월')) {
      return 'bg-blue-500 text-white'
    } else if (level.includes('양호') || level.includes('보통')) {
      return 'bg-green-500 text-white'
    } else {
      return 'bg-yellow-500 text-white'
    }
  }

  const getCompetencyIcon = (name: string) => {
    switch (name) {
      case '지식':
        return <BookOpenIcon className="w-6 h-6 text-blue-600" />
      case '기술':
        return <WrenchScrewdriverIcon className="w-6 h-6 text-purple-600" />
      case '친절도':
        return <FaceSmileIcon className="w-6 h-6 text-yellow-600" />
      case '전달력':
        return <ChatBubbleLeftIcon className="w-6 h-6 text-green-600" />
      case '페르소나 정합도':
        return <UserIcon className="w-6 h-6 text-pink-600" />
      // 하위 호환성 (deprecated)
      case '공감도':
        return <HeartIcon className="w-6 h-6 text-red-600" />
      case '명확성':
        return <ChatBubbleLeftIcon className="w-6 h-6 text-green-600" />
      case '자신감':
        return <BoltIcon className="w-6 h-6 text-orange-600" />
      default:
        return null
    }
  }

  const getCompetencyColor = (name: string) => {
    // 모든 막대 그래프를 파란색으로 통일
    return '#3B82F6' // blue-600
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="text-gray-600 mt-4">피드백을 불러오는 중...</p>
        </div>
      </div>
    )
  }

  if (!feedbackData) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <p className="text-gray-600">피드백 데이터를 찾을 수 없습니다.</p>
          <button
            onClick={() => navigate('/simulation')}
            className="mt-4 px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            시뮬레이션으로 돌아가기
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 via-gray-50 to-blue-50/30 py-6 px-4">
      <div className="max-w-6xl mx-auto">
        {/* 히스토리에서 온 경우 상단에 뒤로가기 버튼 */}
        {fromHistory && (
          <div className="mb-4">
            <button
              onClick={() => navigate('/dashboard', { 
                state: { 
                  activeTab: 'simulation',
                  returnScrollY: returnScrollY
                } 
              })}
              className="flex items-center gap-2 px-4 py-2 bg-white hover:bg-gray-50 text-gray-700 rounded-lg border border-gray-200 shadow-sm transition-all"
            >
              <ArrowLeftIcon className="w-5 h-5" />
              <span className="font-medium">대시보드로 돌아가기</span>
            </button>
          </div>
        )}

        {/* 페이지 헤더 */}
        <div className="mb-6">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">시뮬레이션 평가 결과</h1>
          <p className="text-gray-600">고객 응대 역량을 종합적으로 평가한 결과입니다</p>
        </div>

        {/* 시뮬레이션 정보 섹션 - 페르소나와 상황 정보 */}
        {(feedbackData.persona_info || feedbackData.situation_info) && (
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5 mb-6">
            <div className="flex items-center gap-2 mb-4">
              <div className="w-1 h-5 bg-blue-600 rounded-full"></div>
              <h2 className="text-base font-semibold text-gray-800">시뮬레이션 정보</h2>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {feedbackData.persona_info && (
                <div className="flex items-center gap-3 p-3 bg-blue-50/50 rounded-lg border border-blue-100">
                  <div className="flex-shrink-0 p-2 bg-blue-500 rounded-lg">
                    <UserIcon className="w-4 h-4 text-white" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-xs font-medium text-gray-600 mb-0.5">페르소나</div>
                    <div className="text-sm font-semibold text-gray-900">
                      {feedbackData.persona_info}
                    </div>
                  </div>
                </div>
              )}
              
              {feedbackData.situation_info && (
                <div className="flex items-center gap-3 p-3 bg-indigo-50/50 rounded-lg border border-indigo-100">
                  <div className="flex-shrink-0 p-2 bg-indigo-500 rounded-lg">
                    <DocumentTextIcon className="w-4 h-4 text-white" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-xs font-medium text-gray-600 mb-0.5">상황</div>
                    <div className="text-sm font-semibold text-gray-900">
                      {feedbackData.situation_info}
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* 종합 점수 섹션 */}
        <div className="bg-gradient-to-br from-white to-blue-50/30 rounded-xl shadow-lg border-2 border-blue-100 p-8 mb-8">
          <div className="text-center mb-6">
            <h2 className="text-sm font-semibold text-gray-600 uppercase tracking-wider mb-2">종합 평가</h2>
            <div className="flex items-baseline justify-center gap-3 mb-3">
              <span className={`text-7xl font-extrabold ${getGradeColor(feedbackData.grade)}`}>
                {Math.floor(feedbackData.overallScore)}
              </span>
              <span className="text-3xl font-bold text-gray-700">/ 100</span>
            </div>
            <div className="flex items-center justify-center gap-3 mb-4">
              <span className={`text-2xl font-bold ${getGradeColor(feedbackData.grade)}`}>
                {feedbackData.grade}
              </span>
              <span className="text-gray-400">등급</span>
              <div className={`px-4 py-1.5 rounded-full text-sm font-semibold ${getPerformanceLevelStyle(feedbackData.performanceLevel)}`}>
                {feedbackData.performanceLevel}
              </div>
            </div>
          </div>
          <div className="bg-white/60 backdrop-blur-sm rounded-lg p-5 border border-gray-200">
            <div className="text-gray-800 leading-relaxed text-center space-y-2">
              {/* 문장 단위로 줄바꿈 처리 */}
              {feedbackData.summary.split(/(?<=[.!?])\s+/).map((sentence, index) => (
                <p key={index}>{sentence.trim()}</p>
              ))}
            </div>
          </div>
        </div>

        {/* 역량별 평가 섹션 */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
          <div className="flex items-center gap-2 mb-6">
            <div className="w-1 h-5 bg-indigo-600 rounded-full"></div>
            <h2 className="text-lg font-bold text-gray-900">역량별 평가</h2>
          </div>
          
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* 레이더 차트 */}
            <div className="bg-gray-50 rounded-lg p-4 border border-gray-200">
              <h3 className="text-sm font-semibold text-gray-700 mb-4 text-center">종합 역량 분포</h3>
              <ResponsiveContainer width="100%" height={300}>
                <RadarChart data={feedbackData.competencies}>
                  <PolarGrid 
                    stroke="#E2E8F0"
                    strokeWidth={1}
                  />
                  <PolarAngleAxis 
                    dataKey="name" 
                    tick={{ 
                      fill: '#475569', 
                      fontSize: 12, 
                      fontWeight: 600
                    }}
                  />
                  <PolarRadiusAxis 
                    angle={90} 
                    domain={[0, 100]}
                    tick={{ fill: '#94A3B8', fontSize: 9 }}
                    tickCount={5}
                    stroke="#E2E8F0"
                  />
                  <Radar 
                    name="점수" 
                    dataKey="score" 
                    stroke="#3B82F6" 
                    fill="#3B82F6"
                    fillOpacity={0.6}
                    strokeWidth={2}
                    dot={{ fill: '#3B82F6', r: 4 }}
                  />
                  <Tooltip 
                    contentStyle={{
                      backgroundColor: 'white',
                      border: '1px solid #E2E8F0',
                      borderRadius: '8px',
                      padding: '8px 12px',
                      boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)'
                    }}
                    formatter={(value: number) => [`${value}점`, '']}
                  />
                </RadarChart>
              </ResponsiveContainer>
            </div>

            {/* 막대 그래프 */}
            <div className="space-y-3">
              <h3 className="text-sm font-semibold text-gray-700 mb-4">역량별 점수</h3>
              {feedbackData.competencies.map((comp, index) => (
                <div key={index} className="bg-gray-50 rounded-lg p-3 border border-gray-200">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-semibold text-gray-800">{comp.name}</span>
                    <span className="text-base font-bold text-gray-900">{comp.score}점</span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-2.5 overflow-hidden">
                    <div
                      className="h-2.5 rounded-full transition-all duration-700 ease-out"
                      style={{
                        width: `${(comp.score / comp.maxScore) * 100}%`,
                        backgroundColor: getCompetencyColor(comp.name)
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* 상세 피드백 섹션 */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
          <div className="flex items-center gap-2 mb-6">
            <div className="w-1 h-5 bg-purple-600 rounded-full"></div>
            <h2 className="text-lg font-bold text-gray-900">상세 역량별 피드백</h2>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* 지식 */}
            <div className="bg-gray-50 border border-gray-200 rounded-lg p-5 hover:shadow-md transition-shadow">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  {getCompetencyIcon('지식')}
                  <h3 className="text-base font-semibold text-gray-900">지식</h3>
                </div>
                <span className="text-lg font-bold text-blue-600">
                  {feedbackData.detailedFeedback.knowledge.score}
                </span>
              </div>
              <div className="text-sm text-gray-700 leading-relaxed">
                  <ReactMarkdown
                remarkPlugins={[remarkGfm, remarkBreaks]}
                components={createMarkdownComponents('text-blue-700', 'bg-blue-50')}
              >
                {preprocessMarkdown(feedbackData.detailedFeedback.knowledge.feedback || '')}
                  </ReactMarkdown>
              </div>
              
              {/* 🧪 Breakdown 데이터 표시 (테스트 모드) */}
              {feedbackData.detailedFeedback.knowledge.breakdown && Object.keys(feedbackData.detailedFeedback.knowledge.breakdown).length > 0 && (
                <div className="mt-4 pt-4 border-t border-gray-300">
                  <button
                    type="button"
                    onClick={() => toggleBreakdown('knowledge')}
                    className="w-full flex items-center justify-between text-xs font-semibold text-gray-700 mb-2 focus:outline-none"
                  >
                    <span>📊 세부 평가 근거</span>
                    {breakdownOpen.knowledge ? (
                      <ChevronUpIcon className="w-4 h-4 text-gray-500" />
                    ) : (
                      <ChevronDownIcon className="w-4 h-4 text-gray-500" />
                    )}
                  </button>
                  {breakdownOpen.knowledge && (
                  <div className="space-y-2">
                    {Object.entries(feedbackData.detailedFeedback.knowledge.breakdown).map(([key, item]) => (
                      <div key={key} className="bg-white rounded p-2 border border-gray-200">
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-xs font-medium text-gray-800">{BREAKDOWN_LABELS[key] || key}</span>
                          <span className="text-xs font-bold text-blue-600">{item.score}/{item.max}점</span>
                        </div>
                        <p className="text-xs text-gray-600 leading-relaxed">{item.reason}</p>
                      </div>
                    ))}
                  </div>
                  )}
                </div>
              )}
            </div>

            {/* 기술 */}
            <div className="bg-gray-50 border border-gray-200 rounded-lg p-5 hover:shadow-md transition-shadow">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  {getCompetencyIcon('기술')}
                  <h3 className="text-base font-semibold text-gray-900">기술</h3>
                </div>
                <span className="text-lg font-bold text-purple-600">
                  {feedbackData.detailedFeedback.skill.score}
                </span>
              </div>
              <div className="text-sm text-gray-700 leading-relaxed">
                  <ReactMarkdown
                remarkPlugins={[remarkGfm, remarkBreaks]}
                components={createMarkdownComponents('text-purple-700', 'bg-purple-50')}
              >
                {preprocessMarkdown(feedbackData.detailedFeedback.skill.feedback || '')}
                  </ReactMarkdown>
              </div>
              
              {/* 🧪 Breakdown 데이터 표시 (테스트 모드) */}
              {feedbackData.detailedFeedback.skill.breakdown && Object.keys(feedbackData.detailedFeedback.skill.breakdown).length > 0 && (
                <div className="mt-4 pt-4 border-t border-gray-300">
                  <button
                    type="button"
                    onClick={() => toggleBreakdown('skill')}
                    className="w-full flex items-center justify-between text-xs font-semibold text-gray-700 mb-2 focus:outline-none"
                  >
                    <span>📊 세부 평가 근거</span>
                    {breakdownOpen.skill ? (
                      <ChevronUpIcon className="w-4 h-4 text-gray-500" />
                    ) : (
                      <ChevronDownIcon className="w-4 h-4 text-gray-500" />
                    )}
                  </button>
                  {breakdownOpen.skill && (
                  <div className="space-y-2">
                    {Object.entries(feedbackData.detailedFeedback.skill.breakdown).map(([key, item]) => (
                      <div key={key} className="bg-white rounded p-2 border border-gray-200">
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-xs font-medium text-gray-800">{BREAKDOWN_LABELS[key] || key}</span>
                          <span className="text-xs font-bold text-purple-600">{item.score}/{item.max}점</span>
                        </div>
                        <p className="text-xs text-gray-600 leading-relaxed">{item.reason}</p>
                      </div>
                    ))}
                  </div>
                  )}
                </div>
              )}
            </div>

            {/* 친절도 */}
            <div className="bg-gray-50 border border-gray-200 rounded-lg p-5 hover:shadow-md transition-shadow">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  {getCompetencyIcon('친절도')}
                  <h3 className="text-base font-semibold text-gray-900">친절도</h3>
                </div>
                <span className="text-lg font-bold text-yellow-600">
                  {feedbackData.detailedFeedback.kindness.score}
                </span>
              </div>
              <div className="text-sm text-gray-700 leading-relaxed">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm, remarkBreaks]}
                  components={createMarkdownComponents('text-yellow-700', 'bg-yellow-50')}
                >
                  {preprocessMarkdown(feedbackData.detailedFeedback.kindness.feedback || '')}
                </ReactMarkdown>
              </div>
              
              {/* 🧪 Breakdown 데이터 표시 (테스트 모드) */}
              {feedbackData.detailedFeedback.kindness.breakdown && Object.keys(feedbackData.detailedFeedback.kindness.breakdown).length > 0 && (
                <div className="mt-4 pt-4 border-t border-gray-300">
                  <button
                    type="button"
                    onClick={() => toggleBreakdown('kindness')}
                    className="w-full flex items-center justify-between text-xs font-semibold text-gray-700 mb-2 focus:outline-none"
                  >
                    <span>📊 세부 평가 근거</span>
                    {breakdownOpen.kindness ? (
                      <ChevronUpIcon className="w-4 h-4 text-gray-500" />
                    ) : (
                      <ChevronDownIcon className="w-4 h-4 text-gray-500" />
                    )}
                  </button>
                  {breakdownOpen.kindness && (
                  <div className="space-y-2">
                    {Object.entries(feedbackData.detailedFeedback.kindness.breakdown).map(([key, item]) => (
                      <div key={key} className="bg-white rounded p-2 border border-gray-200">
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-xs font-medium text-gray-800">{BREAKDOWN_LABELS[key] || key}</span>
                          <span className="text-xs font-bold text-yellow-600">{item.score}/{item.max}점</span>
                        </div>
                        <p className="text-xs text-gray-600 leading-relaxed">{item.reason}</p>
                      </div>
                    ))}
                  </div>
                  )}
                </div>
              )}
            </div>

            {/* 전달력 */}
            <div className="bg-gray-50 border border-gray-200 rounded-lg p-5 hover:shadow-md transition-shadow">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  {getCompetencyIcon('전달력')}
                  <h3 className="text-base font-semibold text-gray-900">전달력</h3>
                </div>
                <span className="text-lg font-bold text-green-600">
                  {feedbackData.detailedFeedback.clarity.score}
                </span>
              </div>
              <div className="text-sm text-gray-700 leading-relaxed">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm, remarkBreaks]}
                  components={createMarkdownComponents('text-green-700', 'bg-green-50')}
                >
                  {preprocessMarkdown(feedbackData.detailedFeedback.clarity.feedback || '')}
                </ReactMarkdown>
              </div>
              
              {/* 🧪 Breakdown 데이터 표시 (테스트 모드) */}
              {feedbackData.detailedFeedback.clarity.breakdown && 
               Object.keys(feedbackData.detailedFeedback.clarity.breakdown).length > 0 && (
                <div className="mt-4 pt-4 border-t border-gray-300">
                  <button
                    type="button"
                    onClick={() => toggleBreakdown('clarity')}
                    className="w-full flex items-center justify-between text-xs font-semibold text-gray-700 mb-2 focus:outline-none"
                  >
                    <span>📊 세부 평가 근거</span>
                    {breakdownOpen.clarity ? (
                      <ChevronUpIcon className="w-4 h-4 text-gray-500" />
                    ) : (
                      <ChevronDownIcon className="w-4 h-4 text-gray-500" />
                    )}
                  </button>
                  {breakdownOpen.clarity && (
                        <div className="space-y-2">
                      {Object.entries(feedbackData.detailedFeedback.clarity.breakdown).map(([key, item]) => (
                            <div key={key} className="bg-white rounded p-2 border border-gray-200">
                              <div className="flex items-center justify-between mb-1">
                          <span className="text-xs font-medium text-gray-800">{BREAKDOWN_LABELS[key] || key}</span>
                                <span className="text-xs font-bold text-green-600">{item.score}/{item.max}점</span>
                              </div>
                              <p className="text-xs text-gray-600 leading-relaxed">{item.reason}</p>
                            </div>
                          ))}
                      </div>
                    )}
                </div>
              )}
            </div>

            {/* 페르소나 정합도 */}
            <div className="bg-gray-50 border border-gray-200 rounded-lg p-5 hover:shadow-md transition-shadow">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  {getCompetencyIcon('페르소나 정합도')}
                  <h3 className="text-base font-semibold text-gray-900">페르소나 정합도</h3>
                </div>
                <span className="text-lg font-bold text-pink-600">
                  {feedbackData.detailedFeedback.persona_fit?.score || 0}
                </span>
              </div>
              <div className="text-sm text-gray-700 leading-relaxed">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm, remarkBreaks]}
                  components={createMarkdownComponents('text-pink-700', 'bg-pink-50')}
                >
                  {preprocessMarkdown(feedbackData.detailedFeedback.persona_fit?.feedback || '')}
                </ReactMarkdown>
              </div>
              
              {/* 🧪 Breakdown 데이터 표시 (테스트 모드) */}
              {feedbackData.detailedFeedback.persona_fit?.breakdown && Object.keys(feedbackData.detailedFeedback.persona_fit.breakdown).length > 0 && (
                <div className="mt-4 pt-4 border-t border-gray-300">
                  <button
                    type="button"
                    onClick={() => toggleBreakdown('persona_fit')}
                    className="w-full flex items-center justify-between text-xs font-semibold text-gray-700 mb-2 focus:outline-none"
                  >
                    <span>📊 세부 평가 근거</span>
                    {breakdownOpen.persona_fit ? (
                      <ChevronUpIcon className="w-4 h-4 text-gray-500" />
                    ) : (
                      <ChevronDownIcon className="w-4 h-4 text-gray-500" />
                    )}
                  </button>
                  {breakdownOpen.persona_fit && (
                  <div className="space-y-2">
                    {Object.entries(feedbackData.detailedFeedback.persona_fit.breakdown).map(([key, item]) => (
                      <div key={key} className="bg-white rounded p-2 border border-gray-200">
                        <div className="flex items-center justify-between mb-1">
                            <span className="text-xs font-medium text-gray-800">
                              {getPersonaBreakdownLabel(key, feedbackData.persona_info)}
                            </span>
                          <span className="text-xs font-bold text-pink-600">{item.score}/{item.max}점</span>
                        </div>
                        <p className="text-xs text-gray-600 leading-relaxed">{item.reason}</p>
                      </div>
                    ))}
                  </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* 개선 제안 섹션 */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
          <div className="flex items-center gap-2 mb-5">
            <div className="w-1 h-5 bg-amber-600 rounded-full"></div>
            <h2 className="text-lg font-bold text-gray-900">개선 제안</h2>
          </div>
          <div className="bg-amber-50/50 border border-amber-200 rounded-lg p-5">
            {Array.isArray(feedbackData.improvements) ? (
              <ul className="space-y-2.5">
                {feedbackData.improvements.map((item, index) => (
                  <li key={index} className="flex items-start gap-3">
                    <span className="flex-shrink-0 w-5 h-5 rounded-full bg-amber-500 text-white text-xs font-bold flex items-center justify-center mt-0.5">
                      {index + 1}
                    </span>
                    <span className="text-sm text-gray-800 leading-relaxed flex-1 pt-0.5">{item}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-gray-800 leading-relaxed">
                {feedbackData.improvements}
              </p>
            )}
          </div>
        </div>

        {/* 목표 달성 현황 섹션 */}
        {feedbackData.goalAchievement && feedbackData.goalAchievement.total > 0 && (
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
            <div className="flex items-center gap-2 mb-5">
              <div className="w-1 h-5 bg-green-600 rounded-full"></div>
              <h2 className="text-lg font-bold text-gray-900 flex items-center gap-2">
                <TrophyIcon className="w-5 h-5 text-green-600" />
                목표 달성 현황
              </h2>
            </div>
            
            {/* 달성률 헤더 */}
            <div className="bg-gray-50 rounded-lg p-5 mb-4 border border-gray-200">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-baseline gap-2">
                  <span className="text-4xl font-extrabold text-green-600">
                    {feedbackData.goalAchievement.achieved}
                  </span>
                  <span className="text-xl text-gray-400">/</span>
                  <span className="text-xl font-semibold text-gray-600">
                    {feedbackData.goalAchievement.total}
                  </span>
                </div>
                <div className="text-right">
                  <div className="text-xs text-gray-600 mb-1">달성률</div>
                  <div className="text-2xl font-bold text-green-600">
                    {Math.round(feedbackData.goalAchievement.rate * 100)}%
                  </div>
                </div>
              </div>
              
              {/* 진행률 바 */}
              <div className="w-full bg-gray-200 rounded-full h-3 overflow-hidden mb-4">
                <div 
                  className="h-3 rounded-full transition-all duration-700 ease-out"
                  style={{ 
                    width: `${feedbackData.goalAchievement.rate * 100}%`,
                    background: feedbackData.goalAchievement.rate >= 0.8 
                      ? 'linear-gradient(90deg, #10B981 0%, #34D399 100%)'
                      : feedbackData.goalAchievement.rate >= 0.5
                      ? 'linear-gradient(90deg, #3B82F6 0%, #60A5FA 100%)'
                      : 'linear-gradient(90deg, #F59E0B 0%, #FBBF24 100%)'
                  }}
                />
              </div>
              
              {/* 접기/펼치기 토글 버튼 */}
              <button
                onClick={() => setIsGoalsExpanded(!isGoalsExpanded)}
                className="flex items-center justify-between w-full p-2.5 text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 border border-gray-300 rounded-lg transition-all"
              >
                <span className="flex items-center gap-2">
                  목표 상세 보기
                  <span className="text-xs text-gray-500 font-normal">
                    ({feedbackData.goalAchievement.goals.length}개)
                  </span>
                </span>
                {isGoalsExpanded ? (
                  <ChevronUpIcon className="w-4 h-4 text-gray-500" />
                ) : (
                  <ChevronDownIcon className="w-4 h-4 text-gray-500" />
                )}
              </button>
            </div>
            
            {/* 목표 목록 - 간결한 체크리스트 (증거 포함) */}
            {isGoalsExpanded && (
              <div className="space-y-2.5 mb-5">
                {feedbackData.goalAchievement.goals.map((goal, idx) => (
                  <div 
                    key={idx} 
                    className={`rounded-lg border transition-all ${
                      goal.achieved 
                        ? 'bg-green-50/50 border-green-300' 
                        : 'bg-gray-50 border-gray-300'
                    }`}
                  >
                    {/* 목표 제목 */}
                    <div className="flex items-start gap-3 p-3">
                      {goal.achieved ? (
                        <CheckCircleIcon className="w-5 h-5 text-green-600 flex-shrink-0 mt-0.5" />
                      ) : (
                        <XCircleIcon className="w-5 h-5 text-gray-400 flex-shrink-0 mt-0.5" />
                      )}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className={`text-sm font-medium ${
                            goal.achieved ? 'text-gray-900' : 'text-gray-600'
                          }`}>
                            {goal.text}
                          </span>
                          {/* 턴 번호 표시 */}
                          {goal.achieved && goal.turn && (
                            <span className="px-2 py-0.5 bg-green-500 text-white text-xs rounded font-semibold">
                              턴 {goal.turn}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                    
                    {/* 증거 발화 표시 */}
                    {goal.achieved && goal.evidence && goal.evidence.trim() && (
                      <div className="px-3 pb-3 pl-11">
                        <div className="bg-white border border-green-300 rounded-lg p-3">
                          <div className="flex items-center gap-2 mb-1.5">
                            <ChatBubbleLeftIcon className="w-3.5 h-3.5 text-green-600" />
                            <span className="text-xs font-semibold text-green-700">달성 발화</span>
                          </div>
                          <p className="text-xs text-gray-800 leading-relaxed pl-5">
                            "{goal.evidence}"
                          </p>
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
            
            {/* 하단 통계 */}
            {isGoalsExpanded && (
              <div className="pt-4 border-t border-gray-300">
                <div className="grid grid-cols-3 gap-3 text-center">
                  <div className="bg-gray-50 rounded-lg p-3">
                    <p className="text-xs text-gray-600 mb-1">전체 목표</p>
                    <p className="text-lg font-bold text-gray-900">{feedbackData.goalAchievement.total}개</p>
                  </div>
                  <div className="bg-green-50 rounded-lg p-3">
                    <p className="text-xs text-gray-600 mb-1">달성 목표</p>
                    <p className="text-lg font-bold text-green-600">{feedbackData.goalAchievement.achieved}개</p>
                  </div>
                  <div className="bg-orange-50 rounded-lg p-3">
                    <p className="text-xs text-gray-600 mb-1">미달성 목표</p>
                    <p className="text-lg font-bold text-orange-600">
                      {feedbackData.goalAchievement.total - feedbackData.goalAchievement.achieved}개
                    </p>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* 대화 로그 섹션 */}
        {feedbackData.conversation_history && feedbackData.conversation_history.length > 0 && (
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <div className="w-1 h-5 bg-gray-600 rounded-full"></div>
                <h2 className="text-lg font-bold text-gray-900">대화 로그</h2>
              </div>
              {feedbackData.duration_seconds && (
                <span className="text-xs text-gray-600 bg-gray-100 px-3 py-1 rounded-full">
                  {Math.floor(feedbackData.duration_seconds / 60)}분 {feedbackData.duration_seconds % 60}초
                </span>
              )}
            </div>
            <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 max-h-96 overflow-y-auto">
              <div className="space-y-3">
                {(() => {
                  // 직원 발화 턴 번호 계산 (직원 발화만 카운트)
                  let employeeTurnCount = 0
                  
                  // 목표 달성 정보를 턴 번호로 매핑
                  const goalByTurn = new Map<number, Array<{ text: string; evidence?: string }>>()
                  if (feedbackData.goalAchievement) {
                    feedbackData.goalAchievement.goals.forEach(goal => {
                      if (goal.achieved && goal.turn) {
                        if (!goalByTurn.has(goal.turn)) {
                          goalByTurn.set(goal.turn, [])
                        }
                        goalByTurn.get(goal.turn)!.push({
                          text: goal.text,
                          evidence: goal.evidence
                        })
                      }
                    })
                  }
                  
                  return feedbackData.conversation_history.map((msg, index) => {
                    // 직원 발화인 경우 턴 번호 증가
                    const isEmployee = msg.role === 'employee' || msg.role === 'user'
                    if (isEmployee) {
                      employeeTurnCount++
                    }
                    
                    // 현재 발화가 달성한 목표 찾기
                    const achievedGoals = isEmployee && employeeTurnCount > 0 
                      ? goalByTurn.get(employeeTurnCount) || []
                      : []
                    
                    return (
                      <div 
                        key={index} 
                        className={`flex ${isEmployee ? 'justify-end' : 'justify-start'}`}
                      >
                        <div 
                          className={`max-w-[75%] rounded-lg px-3 py-2.5 ${
                            isEmployee
                              ? 'bg-blue-600 text-white' 
                              : 'bg-white border border-gray-300 text-gray-900 shadow-sm'
                          }`}
                        >
                          <div className="flex items-center justify-between mb-1.5">
                            <div className="flex items-center gap-2">
                              <div className="text-xs font-medium opacity-80">
                                {isEmployee ? '신입사원' : '고객'}
                              </div>
                              {isEmployee && employeeTurnCount > 0 && (
                                <span className="text-xs font-medium opacity-80">
                                  턴 {employeeTurnCount}
                                </span>
                              )}
                            </div>
                            <div className="flex items-center gap-2">
                              {msg.timestamp && (
                                <span className="text-xs text-gray-500 opacity-70">
                                  {new Date(msg.timestamp).toLocaleTimeString()}
                                </span>
                              )}
                              {/* 버그 신고 버튼 (직원 발화만) */}
                              {isEmployee && (
                                <button
                                  onClick={() => openBugReportModal(index, msg.text)}
                                  className="flex items-center gap-1 px-2 py-1 text-xs bg-red-50 text-red-600 hover:bg-red-100 rounded transition-colors"
                                  title="STT 오인식 버그 신고"
                                >
                                  <ExclamationTriangleIcon className="w-3 h-3" />
                                  버그 신고
                                </button>
                              )}
                            </div>
                          </div>
                          <p className="text-sm leading-relaxed whitespace-pre-wrap">{msg.text}</p>
                          
                          {/* 목표 달성 배지 */}
                          {achievedGoals.length > 0 && (
                            <div className="mt-2 pt-2 border-t border-opacity-20">
                              {achievedGoals.map((goal, goalIdx) => (
                                <div 
                                  key={goalIdx}
                                  className="flex items-center gap-2 mb-1.5 last:mb-0"
                                >
                                  <CheckCircleIcon className={`w-4 h-4 flex-shrink-0 ${
                                    isEmployee ? 'text-green-200' : 'text-green-600'
                                  }`} />
                                  <div className={`text-xs font-semibold ${
                                    isEmployee ? 'text-green-100' : 'text-green-700'
                                  }`}>
                                    목표 달성: {goal.text}
                                  </div>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>
                    )
                  })
                })()}
              </div>
            </div>
          </div>
        )}

        {/* 🧪 RAG 연동 테스트 결과 섹션 (테스트 모드에서만 표시) */}
        {(() => {
          const hasRagEvaluations = feedbackData.rag_evaluations && feedbackData.rag_evaluations.length > 0
          const isTestMode = feedbackData.is_test_mode === true
          
          if (!hasRagEvaluations) {
            console.log('🧪 RAG 평가 결과 섹션 표시 조건 불만족:', {
              hasRagEvaluations,
              isTestMode,
              ragEvaluations: feedbackData.rag_evaluations,
              ragEvaluationsLength: feedbackData.rag_evaluations?.length || 0,
              ragEvaluationsType: typeof feedbackData.rag_evaluations,
              feedbackDataKeys: Object.keys(feedbackData),
              hasRagSummary: !!feedbackData.rag_summary,
              ragSummary: feedbackData.rag_summary
            })
            
            // 테스트 모드인데 RAG 평가 결과가 없으면 경고
            if (isTestMode) {
              console.error('🧪 ❌ 테스트 모드인데 RAG 평가 결과가 없습니다!', {
                is_test_mode: feedbackData.is_test_mode,
                rag_evaluations: feedbackData.rag_evaluations,
                allFeedbackKeys: Object.keys(feedbackData)
              })
            }
          } else {
            console.log('🧪 ✅ RAG 평가 결과 섹션 표시 조건 만족:', {
              hasRagEvaluations: true,
              isTestMode,
              ragEvaluationsLength: feedbackData.rag_evaluations.length,
              hasRagSummary: !!feedbackData.rag_summary
            })
          }
          return hasRagEvaluations
        })() && (
          <div className="bg-gradient-to-br from-purple-50 to-blue-50 rounded-xl shadow-sm border-2 border-purple-200 p-6 mb-6">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <div className="w-1 h-5 bg-purple-600 rounded-full"></div>
                <h2 className="text-lg font-bold text-gray-900">🧪 RAG 연동 테스트 결과</h2>
              </div>
              <span className="text-sm font-semibold text-purple-700 bg-purple-100 px-3 py-1 rounded-full">
                평균 {feedbackData.rag_summary?.average_score?.toFixed(1) || 
                      (feedbackData.rag_evaluations && feedbackData.rag_evaluations.length > 0 
                        ? (feedbackData.rag_evaluations.reduce((sum: number, e: any) => sum + (e.evaluation?.score || 0), 0) / feedbackData.rag_evaluations.length).toFixed(1)
                        : '0.0')}점
              </span>
            </div>
            
            {/* 종합 통계 */}
            {(() => {
              // 🚫 고객 발화 평가는 제외하고 직원 발화 평가만 사용
              const ragEvals = (feedbackData.rag_evaluations || []).filter((e: any) => e.role === 'employee')
              const summary = feedbackData.rag_summary || (() => {
                const employeeEvals = ragEvals.filter((e: any) => e.role === 'employee')
                const allScores = employeeEvals.map((e: any) => e.evaluation?.score || 0)
                const avgScore = allScores.length > 0 ? allScores.reduce((a: number, b: number) => a + b, 0) / allScores.length : 0
                const empAvg = employeeEvals.length > 0 
                  ? employeeEvals.reduce((sum: number, e: any) => sum + (e.evaluation?.score || 0), 0) / employeeEvals.length 
                  : 0
                return {
                  total_evaluations: employeeEvals.length,
                  employee_count: employeeEvals.length,
                  employee_average: empAvg,
                  average_score: avgScore
                }
              })()
              
              return (
                <div className="grid grid-cols-3 gap-3 mb-6">
                  <div className="bg-white rounded-lg p-3 text-center border border-purple-200">
                    <p className="text-xs text-gray-600 mb-1">전체 평가</p>
                    <p className="text-xl font-bold text-purple-600">{summary.total_evaluations}개</p>
                  </div>
                  <div className="bg-white rounded-lg p-3 text-center border border-blue-200">
                    <p className="text-xs text-gray-600 mb-1">직원 발화</p>
                    <p className="text-xl font-bold text-blue-600">{summary.employee_count}개</p>
                    <p className="text-xs text-gray-500 mt-1">{summary.employee_average.toFixed(1)}점</p>
                  </div>
                  <div className="bg-white rounded-lg p-3 text-center border border-orange-200">
                    <p className="text-xs text-gray-600 mb-1">평균 점수</p>
                    <p className="text-xl font-bold text-orange-600">{summary.average_score.toFixed(1)}점</p>
                  </div>
                </div>
              )
            })()}
            
            {/* 턴별 상세 평가 - 테스트 모드: RAG 평가, 일반 모드: 대화 턴별 평가 */}
            <div className="space-y-3">
              <h3 className="text-sm font-semibold text-gray-700 mb-2">
                {feedbackData.rag_evaluations && feedbackData.rag_evaluations.length > 0 
                  ? '턴별 상세 평가 (RAG 평가)' 
                  : '대화 턴별 평가'}
              </h3>
              
              {/* 테스트 모드: RAG 평가 결과 표시 (직원 발화만) */}
              {feedbackData.rag_evaluations && feedbackData.rag_evaluations.length > 0 ? (
                feedbackData.rag_evaluations
                  .filter((e: any) => e.role === 'employee')  // 🚫 고객 발화 평가 제외
                  .map((evalItem, idx) => (
                <div 
                  key={idx}
                  className="bg-white rounded-lg p-4 border border-gray-200"
                >
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span className={`px-2 py-1 rounded text-xs font-semibold ${
                        evalItem.role === 'employee' 
                          ? 'bg-blue-100 text-blue-700' 
                          : 'bg-green-100 text-green-700'
                      }`}>
                        {evalItem.role === 'employee' ? '직원' : '고객'}
                      </span>
                      <span className="text-xs text-gray-600">턴 {evalItem.turn_index}</span>
                      {evalItem.expected_product_code && (
                        <span className="px-2 py-1 bg-purple-100 text-purple-700 rounded text-xs font-medium">
                          {evalItem.expected_product_code}
                        </span>
                      )}
                    </div>
                    <span className={`text-lg font-bold ${
                      evalItem.evaluation.score >= 80 ? 'text-green-600' :
                      evalItem.evaluation.score >= 60 ? 'text-yellow-600' : 'text-red-600'
                    }`}>
                      {evalItem.evaluation.score.toFixed(1)}점
                    </span>
                  </div>
                  
                  {/* 발화 내용 표시 */}
                  {evalItem.utterance && (
                    <div className="mb-3 p-3 bg-gray-50 rounded-lg border border-gray-200">
                      <p className="text-xs text-gray-500 mb-1 font-semibold">발화 내용</p>
                      <p className="text-sm text-gray-800">{evalItem.utterance}</p>
                    </div>
                  )}
                  
                  <div className="grid grid-cols-2 gap-3 mt-3">
                    <div className="bg-gray-50 rounded p-2">
                      <p className="text-xs text-gray-600 mb-1">키워드 점수</p>
                      <p className="text-sm font-semibold text-gray-900">
                        {evalItem.evaluation.keyword_score.toFixed(1)}점
                      </p>
                      <div className="mt-2 space-y-2">
                        {/* 발견된 키워드 목록 */}
                        {evalItem.evaluation.found_keywords && evalItem.evaluation.found_keywords.length > 0 && (
                          <div>
                            <p className="text-xs text-green-600 font-semibold mb-1">
                              ✓ 발견된 키워드 ({evalItem.evaluation.found_keywords.length}개)
                            </p>
                            <div className="flex flex-wrap gap-1">
                              {evalItem.evaluation.found_keywords.map((kw: string, idx: number) => (
                                <span
                                  key={idx}
                                  className="px-1.5 py-0.5 bg-green-100 text-green-700 rounded text-[10px]"
                                >
                                  {kw}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}
                        {/* 누락된 키워드 목록 */}
                        {evalItem.evaluation.missing_keywords && evalItem.evaluation.missing_keywords.length > 0 && (
                          <div>
                            <p className="text-xs text-red-600 font-semibold mb-1">
                              ✗ 누락된 키워드 ({evalItem.evaluation.missing_keywords.length}개)
                            </p>
                            <div className="flex flex-wrap gap-1">
                              {evalItem.evaluation.missing_keywords.slice(0, 10).map((kw: string, idx: number) => (
                                <span
                                  key={idx}
                                  className="px-1.5 py-0.5 bg-red-100 text-red-700 rounded text-[10px]"
                                >
                                  {kw}
                                </span>
                              ))}
                              {evalItem.evaluation.missing_keywords.length > 10 && (
                                <span className="px-1.5 py-0.5 text-red-600 text-[10px]">
                                  +{evalItem.evaluation.missing_keywords.length - 10}개 더
                                </span>
                              )}
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                    
                    {evalItem.evaluation.rag_product_info_score !== undefined && (
                      <div className="bg-gray-50 rounded p-2">
                        <p className="text-xs text-gray-600 mb-1">RAG 상품 정보 점수</p>
                        <p className="text-sm font-semibold text-gray-900">
                          {evalItem.evaluation.rag_product_info_score.toFixed(1)}점
                        </p>
                        <div className="mt-2 space-y-2">
                          {/* 25점인 경우 설명 */}
                          {evalItem.evaluation.rag_product_info_score === 25 && (
                            <div className="text-[10px] text-orange-600 bg-orange-50 rounded p-1.5 border border-orange-200">
                              ⚠️ 카테고리만 추출됨 (키워드 매칭 실패 또는 벡터 검색 실패)
                            </div>
                          )}
                          {/* 벡터 검색 실패 표시 */}
                          {evalItem.evaluation.product_evidence?.error && (
                            <div className="text-[10px] text-red-600 bg-red-50 rounded p-1.5 border border-red-200">
                              ⚠️ 벡터 검색 실패: {evalItem.evaluation.product_evidence.error}
                              <br />
                              <span className="text-gray-600">키워드 매칭 fallback 사용</span>
                              <br />
                              <span className="text-gray-500 italic mt-1 block">
                                💡 참고: 피드백의 지식 평가에서는 LLM으로 claim을 개별 추출하여 검증하므로, 벡터 검색 실패 시에도 claim 단위로 정확성 검증이 가능합니다.
                              </span>
                            </div>
                          )}
                          {/* 추출된 카테고리 */}
                          {evalItem.evaluation.extracted_categories && 
                           evalItem.evaluation.extracted_categories.length > 0 && (
                            <div>
                              <p className="text-xs text-purple-600 font-semibold mb-1">
                                카테고리: {evalItem.evaluation.extracted_categories.join(', ')}
                              </p>
                            </div>
                          )}
                          {/* RAG 정보 키워드 */}
                          {evalItem.evaluation.rag_info_keywords_found && 
                           evalItem.evaluation.rag_info_keywords_found.length > 0 && (
                            <div>
                              <p className="text-xs text-purple-600 font-semibold mb-1">
                                추출된 정보 ({evalItem.evaluation.rag_info_keywords_found.length}개)
                              </p>
                              <div className="flex flex-wrap gap-1">
                                {evalItem.evaluation.rag_info_keywords_found.slice(0, 5).map((kw: string, idx: number) => (
                                  <span
                                    key={idx}
                                    className="px-1.5 py-0.5 bg-purple-100 text-purple-700 rounded text-[10px]"
                                  >
                                    {kw.length > 15 ? kw.substring(0, 15) + '...' : kw}
                                  </span>
                                ))}
                                {evalItem.evaluation.rag_info_keywords_found.length > 5 && (
                                  <span className="px-1.5 py-0.5 text-purple-600 text-[10px]">
                                    +{evalItem.evaluation.rag_info_keywords_found.length - 5}개
                                  </span>
                                )}
                              </div>
                            </div>
                          )}
                        </div>
                      </div>
                    )}
                    
                    {evalItem.evaluation.product_extraction_score !== undefined && (
                      <div className="bg-gray-50 rounded p-2">
                        <p className="text-xs text-gray-600 mb-1">상품 추출 점수</p>
                        <p className="text-sm font-semibold text-gray-900">
                          {evalItem.evaluation.product_extraction_score.toFixed(1)}점
                        </p>
                        {evalItem.evaluation.extracted_product_keywords && 
                         evalItem.evaluation.extracted_product_keywords.length > 0 && (
                          <div className="mt-1 text-xs text-gray-600">
                            <span className="text-purple-600">
                              {evalItem.evaluation.extracted_product_keywords.join(', ')}
                            </span>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                  
                  {/* 🆕 Claim 검증 결과 표시 (피드백과 동일한 정보) */}
                  {evalItem.evaluation.claim_verifications && 
                   evalItem.evaluation.claim_verifications.length > 0 && (
                    <div className="mt-4 pt-4 border-t border-gray-200">
                      <h4 className="text-sm font-semibold text-gray-700 mb-2 flex items-center gap-2">
                        <span className="text-blue-600">🔍</span>
                        Claim 검증 결과 (피드백에 표시된 정보)
                      </h4>
                      <div className="space-y-2">
                        {evalItem.evaluation.claim_verifications.map((cv: any, cvIdx: number) => (
                          <div
                            key={cvIdx}
                            className={`p-2 rounded border ${
                              cv.is_accurate 
                                ? 'bg-green-50 border-green-200' 
                                : 'bg-red-50 border-red-200'
                            }`}
                          >
                            <div className="flex items-start gap-2">
                              <span className={`text-sm font-bold ${
                                cv.is_accurate ? 'text-green-600' : 'text-red-600'
                              }`}>
                                {cv.is_accurate ? '✓' : '✗'}
                              </span>
                              <div className="flex-1">
                                <p className="text-xs font-semibold text-gray-800 mb-1">
                                  {cv.claim}
                                </p>
                                {!cv.is_accurate && cv.ground_truth && (
                                  <p className="text-xs text-gray-600 mt-1">
                                    → 실제: {cv.ground_truth}
                                  </p>
                                )}
                                {cv.llm_reasoning && (
                                  <p className="text-xs text-gray-500 mt-1 italic">
                                    💡 {cv.llm_reasoning}
                                  </p>
                                )}
                                {cv.similarity !== undefined && (
                                  <p className="text-xs text-gray-500 mt-1">
                                    유사도: {(cv.similarity * 100).toFixed(1)}% 
                                    ({cv.verification_method || 'unknown'})
                                  </p>
                                )}
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                  
                  {/* 🧪 상품 데이터 근거 표시 */}
                  {evalItem.evaluation.product_evidence && (
                    <div className="mt-4 pt-4 border-t border-gray-200">
                      <h4 className="text-sm font-semibold text-gray-700 mb-2 flex items-center gap-2">
                        <span className="text-blue-600">📚</span>
                        평가 근거 (상품 데이터)
                      </h4>
                      
                      {/* 찾은 핵심 정보 */}
                      {evalItem.evaluation.product_evidence.key_information && 
                       evalItem.evaluation.product_evidence.key_information.length > 0 && (
                        <div className="mb-3">
                          <p className="text-xs text-gray-600 mb-1">✓ 발견된 핵심 정보</p>
                          <div className="flex flex-wrap gap-1">
                            {evalItem.evaluation.product_evidence.key_information.map((info: string, infoIdx: number) => (
                              <span 
                                key={infoIdx}
                                className="px-2 py-1 bg-green-100 text-green-700 rounded text-xs"
                              >
                                {info}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}
                      
                      {/* 누락된 정보 */}
                      {evalItem.evaluation.product_evidence.missing_information && 
                       evalItem.evaluation.product_evidence.missing_information.length > 0 && (
                        <div className="mb-3">
                          <p className="text-xs text-gray-600 mb-1">✗ 누락된 핵심 정보</p>
                          <div className="flex flex-wrap gap-1">
                            {evalItem.evaluation.product_evidence.missing_information.map((info: string, infoIdx: number) => (
                              <span 
                                key={infoIdx}
                                className="px-2 py-1 bg-red-100 text-red-700 rounded text-xs"
                              >
                                {info}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}
                      
                      {/* 매칭된 상품 데이터 청크 - 벡터 검색 결과 표시 */}
                      {evalItem.evaluation.product_evidence.matched_chunks && 
                       evalItem.evaluation.product_evidence.matched_chunks.length > 0 && (
                        <div className="mt-3">
                          <p className="text-xs text-gray-600 mb-2">
                            🔍 벡터 검색 결과 (Top {Math.min(3, evalItem.evaluation.product_evidence.matched_chunks.length)})
                            {evalItem.evaluation.product_evidence.similarity_scores && 
                             evalItem.evaluation.product_evidence.similarity_scores.length > 0 && (
                              <span className="ml-2 text-green-600 font-semibold">
                                평균 유사도: {(evalItem.evaluation.product_evidence.similarity_scores.reduce((a: number, b: number) => a + b, 0) / evalItem.evaluation.product_evidence.similarity_scores.length * 100).toFixed(1)}%
                              </span>
                            )}
                          </p>
                          <div className="grid gap-2 md:grid-cols-3">
                            {evalItem.evaluation.product_evidence.matched_chunks.slice(0, 3).map((chunk: any, chunkIdx: number) => {
                              const similarityScore = typeof chunk.similarity === 'number'
                                ? (chunk.similarity <= 1 ? (chunk.similarity * 100).toFixed(1) : chunk.similarity.toFixed(1))
                                : null
                              
                              return (
                                <div
                                  key={chunkIdx}
                                  className="bg-blue-50 rounded-lg p-3 border border-blue-200 flex flex-col gap-2"
                                >
                                  <div className="flex items-center justify-between text-xs font-semibold text-blue-800">
                                    <span>#{chunkIdx + 1} {chunk.subsection_title || chunk.breadcrumb || '상품 정보'}</span>
                                    {similarityScore && (
                                      <span className="text-blue-600 font-bold">{similarityScore}{similarityScore.includes('.') ? '%' : ''}</span>
                                    )}
                                  </div>
                                  <p className="text-[11px] text-gray-700 leading-relaxed whitespace-pre-wrap">
                                    {chunk.text}
                                  </p>
                                </div>
                              )
                            })}
                          </div>
                        </div>
                      )}
                      
                      {/* 벡터 검색 실패/오류 정보 */}
                      {evalItem.evaluation.product_evidence.error && (
                        <div className="mt-3 text-xs text-red-600 bg-red-50 border border-red-200 rounded p-2">
                          ⚠️ 벡터 검색 실패: {evalItem.evaluation.product_evidence.error_detail || evalItem.evaluation.product_evidence.error}
                          <span className="ml-2 text-gray-600">(키워드 매칭 fallback 사용)</span>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))
              ) : (
                /* 일반 모드: 대화 턴별 평가 표시 */
                feedbackData.conversation_history && feedbackData.conversation_history.length > 0 ? (
                  feedbackData.conversation_history.map((msg, index) => {
                    const isEmployee = msg.role === 'employee' || msg.role === 'user'
                    const turnNumber = Math.floor(index / 2) + 1
                    
                    return (
                      <div 
                        key={index}
                        className="bg-white rounded-lg p-4 border border-gray-200"
                      >
                        <div className="flex items-center justify-between mb-2">
                          <div className="flex items-center gap-2">
                            <span className={`px-2 py-1 rounded text-xs font-semibold ${
                              isEmployee 
                                ? 'bg-blue-100 text-blue-700' 
                                : 'bg-green-100 text-green-700'
                            }`}>
                              {isEmployee ? '직원' : '고객'}
                            </span>
                            <span className="text-xs text-gray-600">턴 {turnNumber}</span>
                          </div>
                        </div>
                        <div className="mt-2">
                          <p className="text-sm text-gray-800 leading-relaxed">
                            {msg.text}
                          </p>
                          {msg.timestamp && (
                            <p className="text-xs text-gray-400 mt-1">
                              {new Date(msg.timestamp).toLocaleTimeString()}
                            </p>
                          )}
                        </div>
                      </div>
                    )
                  })
                ) : (
                  <div className="text-center text-gray-500 py-4">
                    대화 기록이 없습니다.
                  </div>
                )
              )}
            </div>
          </div>
        )}

        {/* 하단 액션 버튼 (히스토리에서 온 경우 표시하지 않음) */}
        {!fromHistory && (
          <div className="flex justify-center gap-3 mt-8 mb-6">
            <button
              onClick={() => navigate('/simulation')}
              className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-semibold shadow-md hover:shadow-lg transition-all"
            >
              새로운 시뮬레이션 시작
            </button>
            <button
              onClick={() => {
                // 🆕 테스트 모드인지 확인 (rag_evaluations가 있으면 테스트 모드)
                const isTestMode = feedbackData.rag_evaluations && feedbackData.rag_evaluations.length > 0
                const { user } = useAuthStore.getState()
                const isAdmin = user?.role === 'admin'
                
                if (isAdmin && isTestMode) {
                  // 관리자이고 테스트 모드면 관리자 대시보드의 "테스트 평가서" 탭으로 이동
                  navigate('/dashboard', { 
                    state: { 
                      adminTab: '테스트 평가서' // 관리자 대시보드 탭
                    } 
                  })
                } else {
                  // 일반 사용자거나 일반 모드면 시뮬레이션 탭으로 이동
                  navigate('/dashboard', { 
                    state: { 
                      activeTab: 'simulation',
                      scrollToTestEvaluations: isTestMode
                    } 
                  })
                }
              }}
              className="px-6 py-3 bg-white text-gray-700 rounded-lg hover:bg-gray-50 font-semibold border border-gray-300 shadow-sm hover:shadow-md transition-all"
            >
              대시보드로 이동
            </button>
          </div>
        )}

        {/* 버그 신고 모달 */}
        {bugReportModalOpen && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
            <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
              <div className="sticky top-0 bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
                <h3 className="text-lg font-bold text-gray-900">STT 버그 신고</h3>
                <button
                  onClick={() => setBugReportModalOpen(false)}
                  className="text-gray-400 hover:text-gray-600 transition-colors"
                >
                  <XMarkIcon className="w-6 h-6" />
                </button>
              </div>
              
              <div className="px-6 py-4 space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    STT가 인식한 텍스트 (오인식된 내용)
                  </label>
                  <div className="bg-gray-50 border border-gray-300 rounded-lg px-4 py-3 text-sm text-gray-700">
                    {bugReportRecognizedText}
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    실제로 말한 내용 <span className="text-red-500">*</span>
                  </label>
                  <textarea
                    value={bugReportOriginalText}
                    onChange={(e) => setBugReportOriginalText(e.target.value)}
                    placeholder="예: 정기요금"
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
                    rows={2}
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    상세 설명 (선택사항)
                  </label>
                  <textarea
                    value={bugReportDescription}
                    onChange={(e) => setBugReportDescription(e.target.value)}
                    placeholder="버그에 대한 추가 설명을 입력해주세요..."
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
                    rows={4}
                  />
                </div>
              </div>

              <div className="sticky bottom-0 bg-gray-50 border-t border-gray-200 px-6 py-4 flex justify-end gap-3">
                <button
                  onClick={() => setBugReportModalOpen(false)}
                  className="px-4 py-2 text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
                  disabled={bugReportSubmitting}
                >
                  취소
                </button>
                <button
                  onClick={submitBugReport}
                  disabled={bugReportSubmitting || !bugReportOriginalText.trim()}
                  className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
                >
                  {bugReportSubmitting ? '제출 중...' : '신고 제출'}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default SimulationFeedback

