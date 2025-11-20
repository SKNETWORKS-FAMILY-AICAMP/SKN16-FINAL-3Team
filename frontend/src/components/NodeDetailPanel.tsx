/**
 * 노드 상세 정보 패널
 * 선택된 에이전트의 상세 정보, 입출력, 실행 추적 표시
 */
import { useEffect, useState } from 'react'
import api from '../utils/api'
import {
  XMarkIcon,
  ArrowRightIcon,
  ArrowLeftIcon,
  InformationCircleIcon,
  CodeBracketIcon,
  ArrowPathIcon,
  CheckCircleIcon,
  XCircleIcon,
  ClockIcon,
} from '@heroicons/react/24/outline'

interface NodeDetail {
  node: {
    id: string
    name: string
    type: string
    description: string
    inputs: string[]
    outputs: string[]
    dependencies: string[]
    service_file: string
    function_name?: string
    status: string
  }
  incoming_edges: Array<{
    id: string
    source: string
    target: string
    label: string
    data_type: string
  }>
  outgoing_edges: Array<{
    id: string
    source: string
    target: string
    label: string
    data_type: string
  }>
}

interface NodeDetailPanelProps {
  nodeId: string | null
  onClose: () => void
}

const statusIcons: Record<string, any> = {
  idle: ClockIcon,
  running: ArrowPathIcon,
  success: CheckCircleIcon,
  error: XCircleIcon,
  pending: ClockIcon,
}

const statusColors: Record<string, string> = {
  idle: 'text-gray-500',
  running: 'text-blue-500 animate-spin',
  success: 'text-green-500',
  error: 'text-red-500',
  pending: 'text-yellow-500',
}

export default function NodeDetailPanel({ nodeId, onClose }: NodeDetailPanelProps) {
  const [detail, setDetail] = useState<NodeDetail | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (nodeId) {
      loadNodeDetail(nodeId)
    }
  }, [nodeId])

  const loadNodeDetail = async (id: string) => {
    try {
      setLoading(true)
      setError('')
      const response = await api.get(`/langgraph/nodes/${id}`)
      setDetail(response.data.data)
    } catch (err: any) {
      console.error('노드 상세 정보 로드 실패:', err)
      setError(err.response?.data?.detail || '노드 정보를 불러오는데 실패했습니다')
    } finally {
      setLoading(false)
    }
  }

  if (!nodeId) return null

  const StatusIcon = detail?.node.status ? statusIcons[detail.node.status] : ClockIcon
  const statusColor = detail?.node.status ? statusColors[detail.node.status] : 'text-gray-500'

  return (
    <div className="fixed inset-y-0 right-0 w-[500px] bg-white shadow-2xl border-l border-gray-200 z-50 overflow-y-auto">
      {/* 헤더 */}
      <div className="sticky top-0 bg-gradient-to-r from-primary-600 to-primary-700 text-white p-6 shadow-lg">
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-2">
              {StatusIcon && <StatusIcon className={`w-5 h-5 ${statusColor}`} />}
              <h2 className="text-xl font-bold">{detail?.node.name || '로딩 중...'}</h2>
            </div>
            <p className="text-sm text-primary-100">
              {detail?.node.type ? (
                <span className="px-2 py-1 bg-white/20 rounded-lg capitalize">
                  {detail.node.type}
                </span>
              ) : (
                '...'
              )}
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-white hover:bg-white/20 p-2 rounded-lg transition-colors"
          >
            <XMarkIcon className="w-6 h-6" />
          </button>
        </div>
      </div>

      {/* 컨텐츠 */}
      <div className="p-6 space-y-6">
        {loading && (
          <div className="flex items-center justify-center py-12">
            <ArrowPathIcon className="w-8 h-8 animate-spin text-primary-600" />
          </div>
        )}

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-xl p-4">
            <div className="flex items-center gap-2 text-red-700">
              <InformationCircleIcon className="w-5 h-5" />
              <span className="font-semibold">오류</span>
            </div>
            <p className="mt-1 text-sm text-red-600">{error}</p>
          </div>
        )}

        {detail && !loading && (
          <>
            {/* 설명 */}
            <section>
              <h3 className="text-sm font-semibold text-gray-700 mb-2 flex items-center gap-2">
                <InformationCircleIcon className="w-4 h-4" />
                설명
              </h3>
              <p className="text-sm text-gray-600 leading-relaxed bg-gray-50 p-4 rounded-lg">
                {detail.node.description}
              </p>
            </section>

            {/* 서비스 정보 */}
            <section>
              <h3 className="text-sm font-semibold text-gray-700 mb-2 flex items-center gap-2">
                <CodeBracketIcon className="w-4 h-4" />
                서비스 정보
              </h3>
              <div className="bg-gray-50 p-4 rounded-lg space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-600">파일:</span>
                  <code className="text-primary-600 font-mono text-xs">
                    {detail.node.service_file}
                  </code>
                </div>
                {detail.node.function_name && (
                  <div className="flex justify-between">
                    <span className="text-gray-600">함수:</span>
                    <code className="text-primary-600 font-mono text-xs">
                      {detail.node.function_name}()
                    </code>
                  </div>
                )}
                <div className="flex justify-between">
                  <span className="text-gray-600">상태:</span>
                  <span className={`font-semibold capitalize ${statusColor.replace('animate-spin', '')}`}>
                    {detail.node.status}
                  </span>
                </div>
              </div>
            </section>

            {/* 입력 파라미터 */}
            <section>
              <h3 className="text-sm font-semibold text-gray-700 mb-2 flex items-center gap-2">
                <ArrowRightIcon className="w-4 h-4" />
                입력 (Inputs)
              </h3>
              <div className="space-y-2">
                {detail.node.inputs.map((input, idx) => (
                  <div key={idx} className="bg-blue-50 border border-blue-200 rounded-lg p-3">
                    <code className="text-sm text-blue-700 font-mono">{input}</code>
                  </div>
                ))}
                {detail.node.inputs.length === 0 && (
                  <p className="text-sm text-gray-500 italic">입력 파라미터 없음</p>
                )}
              </div>
            </section>

            {/* 출력 */}
            <section>
              <h3 className="text-sm font-semibold text-gray-700 mb-2 flex items-center gap-2">
                <ArrowLeftIcon className="w-4 h-4 rotate-180" />
                출력 (Outputs)
              </h3>
              <div className="space-y-2">
                {detail.node.outputs.map((output, idx) => (
                  <div key={idx} className="bg-green-50 border border-green-200 rounded-lg p-3">
                    <code className="text-sm text-green-700 font-mono">{output}</code>
                  </div>
                ))}
                {detail.node.outputs.length === 0 && (
                  <p className="text-sm text-gray-500 italic">출력 없음</p>
                )}
              </div>
            </section>

            {/* 의존성 */}
            {detail.node.dependencies.length > 0 && (
              <section>
                <h3 className="text-sm font-semibold text-gray-700 mb-2">의존성</h3>
                <div className="space-y-2">
                  {detail.node.dependencies.map((dep, idx) => (
                    <div key={idx} className="bg-purple-50 border border-purple-200 rounded-lg p-3">
                      <code className="text-sm text-purple-700 font-mono">{dep}</code>
                    </div>
                  ))}
                </div>
              </section>
            )}

            {/* 들어오는 연결 */}
            {detail.incoming_edges.length > 0 && (
              <section>
                <h3 className="text-sm font-semibold text-gray-700 mb-2">
                  들어오는 연결 ({detail.incoming_edges.length})
                </h3>
                <div className="space-y-2">
                  {detail.incoming_edges.map((edge, idx) => (
                    <div key={idx} className="bg-amber-50 border border-amber-200 rounded-lg p-3">
                      <div className="flex items-center gap-2 text-sm">
                        <span className="font-mono text-amber-700">{edge.source}</span>
                        <ArrowRightIcon className="w-4 h-4 text-amber-600" />
                        <span className="text-gray-600 text-xs">{edge.label}</span>
                      </div>
                      <div className="mt-1 text-xs text-gray-500">
                        데이터 타입: <code>{edge.data_type}</code>
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            )}

            {/* 나가는 연결 */}
            {detail.outgoing_edges.length > 0 && (
              <section>
                <h3 className="text-sm font-semibold text-gray-700 mb-2">
                  나가는 연결 ({detail.outgoing_edges.length})
                </h3>
                <div className="space-y-2">
                  {detail.outgoing_edges.map((edge, idx) => (
                    <div key={idx} className="bg-teal-50 border border-teal-200 rounded-lg p-3">
                      <div className="flex items-center gap-2 text-sm">
                        <span className="text-gray-600 text-xs">{edge.label}</span>
                        <ArrowRightIcon className="w-4 h-4 text-teal-600" />
                        <span className="font-mono text-teal-700">{edge.target}</span>
                      </div>
                      <div className="mt-1 text-xs text-gray-500">
                        데이터 타입: <code>{edge.data_type}</code>
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            )}
          </>
        )}
      </div>
    </div>
  )
}

