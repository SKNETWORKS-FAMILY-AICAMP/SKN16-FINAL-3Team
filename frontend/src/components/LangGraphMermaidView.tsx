/**
 * LangGraph 아키텍처 시각화 컴포넌트 (Mermaid 기반)
 * 모듈 간 연결을 명확하게 표시하고, 모듈 클릭 시 내부 구조 확인 가능
 * 큰 화면으로 최적화
 */
import { useEffect, useState } from 'react'
import mermaid from 'mermaid'
import api from '../utils/api'
import {
  ArrowPathIcon,
  InformationCircleIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline'

// Mermaid 초기화
mermaid.initialize({
  startOnLoad: false,
  theme: 'default',
  securityLevel: 'loose',
  flowchart: {
    useMaxWidth: true,
    htmlLabels: true,
    curve: 'basis',
  },
})

interface ModuleNode {
  id: string
  name: string
  type: string
  description: string
  children: string[]
}

interface AgentNode {
  id: string
  name: string
  type: string
  description: string
  module_id?: string
}

interface GraphData {
  nodes: any[]
  edges: any[]
  modules: Record<string, string[]>
}

export default function LangGraphMermaidView() {
  const [graphData, setGraphData] = useState<GraphData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [statistics, setStatistics] = useState<any>(null)
  const [selectedModule, setSelectedModule] = useState<string | null>(null)
  const [viewMode, setViewMode] = useState<'overview' | 'detail'>('overview')

  useEffect(() => {
    loadGraphData()
    loadStatistics()
  }, [])

  useEffect(() => {
    if (graphData) {
      // 약간의 지연을 두고 렌더링 (DOM이 완전히 준비되도록)
      setTimeout(() => {
        renderMermaidDiagram()
      }, 100)
    }
  }, [graphData, viewMode, selectedModule])

  const loadGraphData = async () => {
    try {
      setLoading(true)
      const response = await api.get('/langgraph/graph')
      const data = response.data.data
      
      console.log('📥 그래프 데이터 로드:', {
        nodes: data.nodes?.length,
        edges: data.edges?.length,
      })
      
      setGraphData(data)
      setError('')
    } catch (err: any) {
      console.error('그래프 로드 실패:', err)
      setError(err.response?.data?.detail || '그래프를 불러오는데 실패했습니다')
    } finally {
      setLoading(false)
    }
  }

  const loadStatistics = async () => {
    try {
      const response = await api.get('/langgraph/statistics')
      setStatistics(response.data.data)
    } catch (err) {
      console.error('통계 로드 실패:', err)
    }
  }

  const generateOverviewMermaid = (): string => {
    if (!graphData) return ''

    const moduleNodes = graphData.nodes.filter((n: any) => n.type === 'module')
    const moduleEdges = graphData.edges.filter((e: any) => {
      const sourceIsModule = moduleNodes.some((m: any) => m.id === e.source)
      const targetIsModule = moduleNodes.some((m: any) => m.id === e.target)
      return sourceIsModule && targetIsModule
    })

    let mermaidCode = 'graph TB\n'
    mermaidCode += '  classDef moduleStyle fill:#e0e7ff,stroke:#4f46e5,stroke-width:4px,color:#1e1b4b,font-size:16px\n\n'

    // 모듈 노드 정의
    moduleNodes.forEach((module: ModuleNode) => {
      const cleanName = module.name.replace(/"/g, '')
      const cleanDesc = module.description.substring(0, 50).replace(/"/g, '')
      mermaidCode += `  ${module.id}["<b style='font-size:18px'>${cleanName}</b><br/><span style='font-size:14px'>${cleanDesc}...</span><br/><span style='font-size:14px'>📦 ${module.children?.length || 0}개 에이전트</span>"]:::moduleStyle\n`
    })

    mermaidCode += '\n'

    // 모듈 간 엣지
    moduleEdges.forEach((edge: any) => {
      const label = edge.label || edge.data_type || ''
      mermaidCode += `  ${edge.source} -->|"<b>${label}</b>"| ${edge.target}\n`
    })

    // 클릭 이벤트
    moduleNodes.forEach((module: ModuleNode) => {
      mermaidCode += `  click ${module.id} call handleModuleClick("${module.id}")\n`
    })

    return mermaidCode
  }

  const generateModuleDetailMermaid = (moduleId: string): string => {
    if (!graphData) return ''

    const module = graphData.nodes.find((n: any) => n.id === moduleId)
    if (!module) return ''

    const agentNodes = graphData.nodes.filter((n: any) => 
      n.module_id === moduleId || module.children?.includes(n.id)
    )

    const internalEdges = graphData.edges.filter((e: any) => {
      const sourceIsInternal = agentNodes.some((a: any) => a.id === e.source)
      const targetIsInternal = agentNodes.some((a: any) => a.id === e.target)
      return sourceIsInternal && targetIsInternal
    })

    let mermaidCode = 'graph TB\n'
    mermaidCode += '  classDef orchestratorStyle fill:#f3e8ff,stroke:#9333ea,stroke-width:3px,font-size:14px\n'
    mermaidCode += '  classDef processorStyle fill:#dbeafe,stroke:#2563eb,stroke-width:3px,font-size:14px\n'
    mermaidCode += '  classDef evaluatorStyle fill:#d1fae5,stroke:#059669,stroke-width:3px,font-size:14px\n'
    mermaidCode += '  classDef detectorStyle fill:#fed7aa,stroke:#ea580c,stroke-width:3px,font-size:14px\n'
    mermaidCode += '  classDef generatorStyle fill:#fce7f3,stroke:#db2777,stroke-width:3px,font-size:14px\n'
    mermaidCode += '  classDef retrieverStyle fill:#fef3c7,stroke:#d97706,stroke-width:3px,font-size:14px\n\n'

    // 에이전트 노드 정의
    agentNodes.forEach((agent: AgentNode) => {
      const cleanName = agent.name.replace(/"/g, '').substring(0, 40)
      const typeClass = `${agent.type}Style`
      mermaidCode += `  ${agent.id}["<b>${cleanName}</b>"]:::${typeClass}\n`
    })

    mermaidCode += '\n'

    // 내부 엣지
    internalEdges.forEach((edge: any) => {
      const label = edge.label || edge.data_type || ''
      mermaidCode += `  ${edge.source} -->|"${label}"| ${edge.target}\n`
    })

    return mermaidCode
  }

  const renderMermaidDiagram = () => {
    const container = document.getElementById('mermaid-container')
    if (!container) {
      console.error('❌ mermaid-container를 찾을 수 없습니다')
      return
    }

    try {
      let mermaidCode = ''
      
      if (viewMode === 'overview') {
        mermaidCode = generateOverviewMermaid()
      } else if (selectedModule) {
        mermaidCode = generateModuleDetailMermaid(selectedModule)
      }

      if (!mermaidCode) {
        console.warn('⚠️ Mermaid 코드가 비어있습니다')
        return
      }

      console.log('🎨 Mermaid 코드:', mermaidCode)

      // 클릭 이벤트 핸들러 등록 (전역)
      ;(window as any).handleModuleClick = (moduleId: string) => {
        console.log('🖱️ 모듈 클릭:', moduleId)
        setSelectedModule(moduleId)
        setViewMode('detail')
      }

      // <pre class="mermaid"> 방식으로 렌더링
      container.innerHTML = `<pre class="mermaid">${mermaidCode}</pre>`

      // Mermaid 초기화 및 렌더링
      mermaid.initialize({
        startOnLoad: false,
        theme: 'default',
        securityLevel: 'loose',
        flowchart: {
          useMaxWidth: true,
          htmlLabels: true,
          curve: 'basis',
        },
      })

      // mermaid.run()을 사용하여 렌더링
      setTimeout(() => {
        mermaid.run({
          querySelector: '.mermaid',
        }).then(() => {
          console.log('✅ 다이어그램 렌더링 완료')
        }).catch((err: any) => {
          console.error('❌ mermaid.run() 실패:', err)
        })
      }, 50)

      console.log('✅ 다이어그램 렌더링 요청 완료')
    } catch (err: any) {
      console.error('❌ Mermaid 렌더링 실패:', err)
      if (container) {
        container.innerHTML = `
          <div class="text-red-600 text-center py-8">
            <p class="font-semibold mb-2">다이어그램 렌더링 실패</p>
            <p class="text-sm">${err.message || '알 수 없는 오류'}</p>
          </div>
        `
      }
    }
  }

  const handleBackToOverview = () => {
    setSelectedModule(null)
    setViewMode('overview')
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-center">
          <ArrowPathIcon className="w-12 h-12 animate-spin mx-auto text-primary-600" />
          <p className="mt-4 text-lg text-gray-600">LangGraph 구조를 불러오는 중...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="h-screen flex items-center justify-center p-8">
        <div className="bg-red-50 border border-red-200 rounded-xl p-8 max-w-2xl">
          <div className="flex items-center gap-3 text-red-700">
            <InformationCircleIcon className="w-8 h-8" />
            <span className="font-semibold text-xl">오류 발생</span>
          </div>
          <p className="mt-3 text-red-600 text-lg">{error}</p>
        </div>
      </div>
    )
  }

  const selectedModuleData = selectedModule 
    ? graphData?.nodes.find((n: any) => n.id === selectedModule)
    : null

  return (
    <div className="h-screen flex flex-col bg-gray-50">
      {/* 헤더 - 고정 */}
      <div className="bg-white shadow-md border-b border-gray-200 p-6 flex-shrink-0">
        <div className="flex items-center justify-between">
          <div className="flex-1">
            <h2 className="text-3xl font-bold text-gray-900">LangGraph 아키텍처</h2>
            <p className="text-base text-gray-600 mt-2">
              {viewMode === 'overview' 
                ? '모듈을 클릭하면 내부 에이전트를 확인할 수 있습니다' 
                : `${selectedModuleData?.name} 모듈의 내부 구조 (총 ${selectedModuleData?.children?.length || 0}개 에이전트)`}
            </p>
          </div>

          {/* 통계 및 버튼 */}
          <div className="flex items-center gap-4">
            {statistics && viewMode === 'overview' && (
              <div className="flex gap-3">
                <div className="bg-indigo-50 rounded-lg px-4 py-2 border border-indigo-200">
                  <div className="text-xs text-indigo-600 font-medium">모듈</div>
                  <div className="text-2xl font-bold text-indigo-900">{statistics.total_modules || 0}</div>
                </div>
                <div className="bg-blue-50 rounded-lg px-4 py-2 border border-blue-200">
                  <div className="text-xs text-blue-600 font-medium">에이전트</div>
                  <div className="text-2xl font-bold text-blue-900">{statistics.total_nodes}</div>
                </div>
                <div className="bg-green-50 rounded-lg px-4 py-2 border border-green-200">
                  <div className="text-xs text-green-600 font-medium">연결</div>
                  <div className="text-2xl font-bold text-green-900">{statistics.total_edges}</div>
                </div>
              </div>
            )}

            {viewMode === 'detail' && (
              <button
                onClick={handleBackToOverview}
                className="flex items-center gap-2 px-6 py-3 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors shadow-lg text-base font-semibold"
              >
                <XMarkIcon className="w-5 h-5" />
                전체 보기
              </button>
            )}
          </div>
        </div>
      </div>

      {/* 다이어그램 영역 - 남은 공간 전체 사용 */}
      <div className="flex-1 overflow-hidden p-6">
        <div className="bg-white rounded-xl shadow-lg border border-gray-200 h-full flex items-center justify-center overflow-auto">
          <div 
            id="mermaid-container" 
            className="w-full h-full flex items-center justify-center p-8"
          />
        </div>
      </div>

      {/* 범례 - 하단 고정 (상세 보기일 때만) */}
      {viewMode === 'detail' && (
        <div className="bg-white border-t border-gray-200 p-4 flex-shrink-0">
          <div className="flex items-center justify-center gap-6">
            <div className="flex items-center gap-2">
              <div className="w-5 h-5 rounded bg-purple-100 border-2 border-purple-500"></div>
              <span className="text-sm font-medium">Orchestrator</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-5 h-5 rounded bg-blue-100 border-2 border-blue-500"></div>
              <span className="text-sm font-medium">Processor</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-5 h-5 rounded bg-green-100 border-2 border-green-500"></div>
              <span className="text-sm font-medium">Evaluator</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-5 h-5 rounded bg-orange-100 border-2 border-orange-500"></div>
              <span className="text-sm font-medium">Detector</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-5 h-5 rounded bg-pink-100 border-2 border-pink-500"></div>
              <span className="text-sm font-medium">Generator</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-5 h-5 rounded bg-amber-100 border-2 border-amber-500"></div>
              <span className="text-sm font-medium">Retriever</span>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
