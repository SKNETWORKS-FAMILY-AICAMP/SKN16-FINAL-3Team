/**
 * LangGraph 아키텍처 시각화 컴포넌트
 * React Flow를 사용한 인터랙티브 다이어그램
 * 모듈 기반 하이라키 구조 지원 + 명확한 화살표 표시
 */
import { useEffect, useState, useCallback, useMemo } from 'react'
import ReactFlow, {
  Node,
  Edge,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  Panel,
  NodeTypes,
  MarkerType,
} from 'reactflow'
import 'reactflow/dist/style.css'
import dagre from 'dagre'
import api from '../utils/api'
import {
  CpuChipIcon,
  MagnifyingGlassIcon,
  SparklesIcon,
  ShieldCheckIcon,
  ChatBubbleBottomCenterTextIcon,
  BeakerIcon,
  ArrowPathIcon,
  InformationCircleIcon,
  FolderIcon,
  ChevronDownIcon,
  ChevronUpIcon,
} from '@heroicons/react/24/outline'

// 노드 타입별 아이콘 매핑
const nodeTypeIcons: Record<string, any> = {
  module: FolderIcon,
  orchestrator: CpuChipIcon,
  processor: SparklesIcon,
  evaluator: BeakerIcon,
  detector: ShieldCheckIcon,
  generator: ChatBubbleBottomCenterTextIcon,
  retriever: MagnifyingGlassIcon,
}

// 노드 타입별 색상
const nodeTypeColors: Record<string, { bg: string; border: string; text: string }> = {
  module: { bg: 'bg-indigo-100', border: 'border-indigo-600', text: 'text-indigo-800' },
  orchestrator: { bg: 'bg-purple-100', border: 'border-purple-500', text: 'text-purple-700' },
  processor: { bg: 'bg-blue-100', border: 'border-blue-500', text: 'text-blue-700' },
  evaluator: { bg: 'bg-green-100', border: 'border-green-500', text: 'text-green-700' },
  detector: { bg: 'bg-orange-100', border: 'border-orange-500', text: 'text-orange-700' },
  generator: { bg: 'bg-pink-100', border: 'border-pink-500', text: 'text-pink-700' },
  retriever: { bg: 'bg-amber-100', border: 'border-amber-500', text: 'text-amber-700' },
}

// 모듈 노드 컴포넌트
const ModuleNode = ({ data }: any) => {
  const colors = nodeTypeColors.module
  const isExpanded = data.isExpanded || false
  const childrenCount = data.children?.length || 0
  const ChevronIcon = isExpanded ? ChevronUpIcon : ChevronDownIcon

  return (
    <div
      className={`px-6 py-5 rounded-xl border-3 ${colors.bg} ${colors.border} shadow-xl hover:shadow-2xl transition-all cursor-pointer min-w-[280px]`}
      onClick={(e) => {
        e.stopPropagation()
        data.onToggleExpand?.()
      }}
    >
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <FolderIcon className={`w-7 h-7 ${colors.text}`} />
          <div className={`text-base font-bold ${colors.text}`}>{data.label}</div>
        </div>
        {childrenCount > 0 && (
          <div className="flex items-center gap-2">
            <span className="text-xs px-2 py-1 bg-indigo-200 text-indigo-800 rounded-full font-semibold">
              {childrenCount}개
            </span>
            <ChevronIcon className={`w-5 h-5 ${colors.text}`} />
          </div>
        )}
      </div>
      <div className="text-xs text-gray-700 mt-1 leading-relaxed">
        {data.description?.substring(0, 70)}...
      </div>
      <div className="flex gap-2 mt-3 justify-center">
        <span className="text-xs px-3 py-1 bg-white rounded-full border-2 border-indigo-400 text-indigo-700 font-semibold">
          ← {data.inputs?.length || 0} IN
        </span>
        <span className="text-xs px-3 py-1 bg-white rounded-full border-2 border-indigo-400 text-indigo-700 font-semibold">
          {data.outputs?.length || 0} OUT →
        </span>
      </div>
    </div>
  )
}

// 커스텀 노드 컴포넌트
const CustomNode = ({ data }: any) => {
  const Icon = nodeTypeIcons[data.type] || CpuChipIcon
  const colors = nodeTypeColors[data.type] || nodeTypeColors.processor

  return (
    <div
      className={`px-5 py-4 rounded-xl border-3 ${colors.bg} ${colors.border} shadow-xl hover:shadow-2xl hover:scale-105 transition-all cursor-pointer min-w-[220px]`}
      onClick={(e) => {
        e.stopPropagation()
        data.onClick?.()
      }}
    >
      <div className="flex items-center gap-2 mb-2">
        <Icon className={`w-6 h-6 ${colors.text}`} />
        <div className={`text-sm font-bold ${colors.text}`}>{data.label}</div>
      </div>
      <div className="text-xs text-gray-700 mt-1 leading-relaxed">
        {data.description?.substring(0, 60)}...
      </div>
      <div className="flex gap-2 mt-3 justify-center">
        <span className="text-xs px-3 py-1 bg-white rounded-full border-2 border-blue-400 text-blue-700 font-semibold">
          ← {data.inputs?.length || 0} IN
        </span>
        <span className="text-xs px-3 py-1 bg-white rounded-full border-2 border-green-400 text-green-700 font-semibold">
          {data.outputs?.length || 0} OUT →
        </span>
      </div>
    </div>
  )
}

const nodeTypes: NodeTypes = {
  custom: CustomNode,
  module: ModuleNode,
}

// Dagre 레이아웃 계산
const getLayoutedElements = (nodes: Node[], edges: Edge[], direction = 'TB') => {
  const dagreGraph = new dagre.graphlib.Graph()
  dagreGraph.setDefaultEdgeLabel(() => ({}))
  dagreGraph.setGraph({ 
    rankdir: direction, 
    ranksep: direction === 'TB' ? 180 : 250, 
    nodesep: direction === 'TB' ? 150 : 200,
    edgesep: 50,
    align: 'UL'
  })

  nodes.forEach((node) => {
    const isModule = node.type === 'module'
    dagreGraph.setNode(node.id, { 
      width: isModule ? 320 : 250, 
      height: isModule ? 130 : 110 
    })
  })

  edges.forEach((edge) => {
    if (edge.source && edge.target && edge.source !== edge.target) {
      dagreGraph.setEdge(edge.source, edge.target)
    }
  })

  dagre.layout(dagreGraph)

  const layoutedNodes = nodes.map((node) => {
    const nodeWithPosition = dagreGraph.node(node.id)
    const isModule = node.type === 'module'
    return {
      ...node,
      position: {
        x: nodeWithPosition.x - (isModule ? 160 : 125),
        y: nodeWithPosition.y - (isModule ? 65 : 55),
      },
    }
  })

  return { nodes: layoutedNodes, edges }
}

interface LangGraphViewProps {
  onNodeClick?: (nodeId: string) => void
}

export default function LangGraphView({ onNodeClick }: LangGraphViewProps) {
  const [nodes, setNodes, onNodesChange] = useNodesState([])
  const [edges, setEdges, onEdgesChange] = useEdgesState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [statistics, setStatistics] = useState<any>(null)
  const [expandedModules, setExpandedModules] = useState<Set<string>>(new Set(['simulation_module']))
  const [rawGraphData, setRawGraphData] = useState<any>(null)

  // 그래프 데이터 로드
  useEffect(() => {
    loadGraphData()
    loadStatistics()
  }, [])

  // 모듈 확장/축소에 따라 노드와 엣지 업데이트 - 단순화된 로직
  const processedGraphData = useMemo(() => {
    if (!rawGraphData) return { nodes: [], edges: [] }

    const moduleNodes = rawGraphData.nodes.filter((n: any) => n.type === 'module')
    const agentNodes = rawGraphData.nodes.filter((n: any) => n.type !== 'module')
    const allNodes: any[] = []
    const allEdges: Edge[] = []
    const visibleNodeIds = new Set<string>()

    // 노드 ID로 모듈 찾기 헬퍼 함수
    const findModuleForNode = (nodeId: string): any => {
      const directModule = moduleNodes.find((m: any) => m.id === nodeId)
      if (directModule) return directModule
      
      const agent = agentNodes.find((a: any) => a.id === nodeId)
      if (agent?.module_id) {
        return moduleNodes.find((m: any) => m.id === agent.module_id)
      }
      
      for (const module of moduleNodes) {
        if (module.children?.includes(nodeId)) {
          return module
        }
      }
      
      return null
    }

    // 1단계: 모듈 노드 추가
    moduleNodes.forEach((moduleNode: any) => {
      allNodes.push({
        ...moduleNode,
        isExpanded: expandedModules.has(moduleNode.id),
        childrenCount: moduleNode.children?.length || 0,
      })
      visibleNodeIds.add(moduleNode.id)
    })

    // 2단계: 확장된 모듈의 하위 에이전트 추가
    moduleNodes.forEach((moduleNode: any) => {
      if (expandedModules.has(moduleNode.id)) {
        const childrenIds = moduleNode.children || []
        const childrenAgents = agentNodes.filter((a: any) => 
          a.module_id === moduleNode.id || childrenIds.includes(a.id)
        )
        childrenAgents.forEach(agent => {
          allNodes.push(agent)
          visibleNodeIds.add(agent.id)
        })
      }
    })

    // 3단계: 독립 에이전트 추가
    const standaloneAgents = agentNodes.filter((a: any) => !a.module_id && !moduleNodes.some((m: any) => m.children?.includes(a.id)))
    standaloneAgents.forEach(agent => {
      allNodes.push(agent)
      visibleNodeIds.add(agent.id)
    })

    // 4단계: 엣지 처리 - 단순화된 명확한 로직
    console.log('🔍 엣지 처리 시작:', {
      totalEdges: rawGraphData.edges.length,
      moduleNodeIds: moduleNodes.map((m: any) => m.id),
      visibleNodeIds: Array.from(visibleNodeIds),
    })

    rawGraphData.edges.forEach((edge: any) => {
      // 소스와 타겟이 모듈인지 확인
      const sourceIsModule = moduleNodes.some((m: any) => m.id === edge.source)
      const targetIsModule = moduleNodes.some((m: any) => m.id === edge.target)

      console.log(`🔍 엣지 검사: ${edge.id}`, {
        source: edge.source,
        target: edge.target,
        sourceIsModule,
        targetIsModule,
        label: edge.label,
      })

      // ⭐ 케이스 1: 모듈 → 모듈 (항상 표시!)
      if (sourceIsModule && targetIsModule) {
        const newEdge = {
          id: edge.id || `edge-${edge.source}-${edge.target}`,
          source: edge.source,
          target: edge.target,
          label: edge.label || edge.data_type || '',
          data: {
            originalSource: edge.source,
            originalTarget: edge.target,
            dataType: edge.data_type,
            isModuleEdge: true,
            isInternalEdge: false,
          },
        }
        allEdges.push(newEdge)
        console.log('✅ 모듈 간 엣지 추가:', newEdge)
        return // 다음 엣지로
      }

      // 케이스 2: 내부 에이전트 엣지 (모듈이 확장된 경우만)
      const sourceModule = findModuleForNode(edge.source)
      const targetModule = findModuleForNode(edge.target)
      const sameModule = sourceModule && targetModule && sourceModule.id === targetModule.id

      if (sameModule && expandedModules.has(sourceModule.id)) {
        // 같은 모듈 내부 에이전트 간 연결
        if (visibleNodeIds.has(edge.source) && visibleNodeIds.has(edge.target)) {
          const newEdge = {
            id: edge.id || `edge-${edge.source}-${edge.target}`,
            source: edge.source,
            target: edge.target,
            label: edge.label || edge.data_type || '',
            data: {
              originalSource: edge.source,
              originalTarget: edge.target,
              dataType: edge.data_type,
              isModuleEdge: false,
              isInternalEdge: true,
            },
          }
          allEdges.push(newEdge)
          console.log('✅ 내부 엣지 추가:', newEdge)
        }
      }

      // 케이스 3: 서로 다른 모듈의 에이전트 간 연결
      // (모듈이 축소되어 있으면 모듈 레벨로 리디렉션)
      else if (sourceModule && targetModule && sourceModule.id !== targetModule.id) {
        let finalSource = edge.source
        let finalTarget = edge.target

        // 소스 모듈이 축소되어 있으면 모듈로 리디렉션
        if (!expandedModules.has(sourceModule.id)) {
          finalSource = sourceModule.id
        }

        // 타겟 모듈이 축소되어 있으면 모듈로 리디렉션
        if (!expandedModules.has(targetModule.id)) {
          finalTarget = targetModule.id
        }

        // 최종 노드가 표시되고 있는지 확인
        if (visibleNodeIds.has(finalSource) && visibleNodeIds.has(finalTarget) && finalSource !== finalTarget) {
          // 중복 체크
          const exists = allEdges.some(e => e.source === finalSource && e.target === finalTarget)
          if (!exists) {
            const newEdge = {
              id: edge.id || `edge-${finalSource}-${finalTarget}`,
              source: finalSource,
              target: finalTarget,
              label: edge.label || edge.data_type || '',
              data: {
                originalSource: edge.source,
                originalTarget: edge.target,
                dataType: edge.data_type,
                isModuleEdge: false,
                isInternalEdge: false,
              },
            }
            allEdges.push(newEdge)
            console.log('✅ 크로스 모듈 엣지 추가:', newEdge)
          }
        }
      }
    })

    console.log('📊 그래프 처리 결과:', {
      nodes: allNodes.length,
      edges: allEdges.length,
      moduleEdges: allEdges.filter(e => e.data?.isModuleEdge).length,
      internalEdges: allEdges.filter(e => e.data?.isInternalEdge).length,
      expandedModules: Array.from(expandedModules),
    })

    return { nodes: allNodes, edges: allEdges }
  }, [rawGraphData, expandedModules])

  // 그래프 데이터 로드 및 처리
  useEffect(() => {
    if (processedGraphData.nodes.length > 0) {
      const { nodes: flowNodes, edges: flowEdges } = processedGraphData

      console.log('🔄 노드/엣지 변환 시작:', {
        nodes: flowNodes.length,
        edges: flowEdges.length,
      })

      // 노드 변환
      const convertedNodes: Node[] = flowNodes.map((node: any) => ({
        id: node.id,
        type: node.type === 'module' ? 'module' : 'custom',
        data: {
          label: node.name,
          type: node.type,
          description: node.description,
          inputs: node.inputs,
          outputs: node.outputs,
          children: node.children,
          childrenCount: node.childrenCount,
          isExpanded: node.isExpanded,
          onClick: () => handleNodeClick(node.id),
          onToggleExpand: () => handleModuleToggle(node.id),
        },
        position: { x: 0, y: 0 },
      }))

      // 엣지 변환 - 더 명확하고 큰 화살표 (유효성 검증 포함)
      const convertedEdges: Edge[] = flowEdges
        .filter((edge: any) => {
          // source와 target이 모두 유효한지 확인
          const isValid = edge.source && 
                 edge.target && 
                 edge.source !== edge.target &&
                 convertedNodes.some(n => n.id === edge.source) &&
                 convertedNodes.some(n => n.id === edge.target)
          
          if (!isValid && edge.data?.isModuleEdge) {
            console.warn('❌ 모듈 간 엣지가 필터링됨:', {
              edge: edge.id,
              source: edge.source,
              target: edge.target,
              sourceExists: convertedNodes.some(n => n.id === edge.source),
              targetExists: convertedNodes.some(n => n.id === edge.target),
            })
          }
          
          return isValid
        })
        .map((edge: any) => {
          const isModuleEdge = edge.data?.isModuleEdge || false
          const isInternalEdge = edge.data?.isInternalEdge || false
          
          // 화살표 크기와 스타일 결정
          const strokeWidth = isModuleEdge ? 5 : isInternalEdge ? 4 : 3.5
          const strokeColor = isModuleEdge ? '#6366f1' : isInternalEdge ? '#3b82f6' : '#60a5fa'
          const arrowSize = isModuleEdge ? 35 : isInternalEdge ? 30 : 28

          const convertedEdge = {
            id: edge.id || `edge-${edge.source}-${edge.target}`,
            source: edge.source,
            target: edge.target,
            label: edge.label || '',
            type: 'smoothstep',
            animated: true,
            markerEnd: {
              type: MarkerType.ArrowClosed,
              width: arrowSize,
              height: arrowSize,
              color: strokeColor,
            },
            style: {
              strokeWidth,
              stroke: strokeColor,
            },
            labelStyle: {
              fill: isModuleEdge ? '#4338ca' : '#1e40af',
              fontSize: isModuleEdge ? 14 : 13,
              fontWeight: 800,
            },
            labelBgStyle: {
              fill: '#ffffff',
              fillOpacity: 1,
              rx: 5,
              ry: 5,
              stroke: strokeColor,
              strokeWidth: 2,
            },
            labelBgPadding: [10, 6] as [number, number],
            labelBgBorderRadius: 5,
          }
          
          if (isModuleEdge) {
            console.log('✅ 모듈 간 엣지 변환:', {
              id: convertedEdge.id,
              source: convertedEdge.source,
              target: convertedEdge.target,
              label: convertedEdge.label,
            })
          }
          
          return convertedEdge
        })

      console.log('✅ 변환 완료:', {
        nodes: convertedNodes.length,
        edges: convertedEdges.length,
        moduleEdges: convertedEdges.filter(e => {
          const originalEdge = flowEdges.find((fe: any) => fe.id === e.id)
          return originalEdge?.data?.isModuleEdge
        }).length,
        edgeIds: convertedEdges.map(e => e.id).slice(0, 10),
      })

      // 레이아웃 적용
      const { nodes: layoutedNodes, edges: layoutedEdges } = getLayoutedElements(
        convertedNodes,
        convertedEdges,
        'TB'
      )

      console.log('📐 레이아웃 적용 완료:', {
        nodes: layoutedNodes.length,
        edges: layoutedEdges.length,
      })

      setNodes(layoutedNodes)
      setEdges(layoutedEdges)
    }
  }, [processedGraphData])

  const loadGraphData = async () => {
    try {
      setLoading(true)
      const response = await api.get('/langgraph/graph')
      const graphData = response.data.data
      
      // 상세한 로깅
      console.log('📥 그래프 데이터 로드 (전체):', {
        totalNodes: graphData.nodes?.length,
        totalEdges: graphData.edges?.length,
        modules: Object.keys(graphData.modules || {}).length,
      })
      
      // 모듈 노드 확인
      const moduleNodes = graphData.nodes?.filter((n: any) => n.type === 'module') || []
      console.log('📦 모듈 노드:', moduleNodes.map((m: any) => ({
        id: m.id,
        name: m.name,
        children: m.children?.length || 0,
      })))
      
      // 모듈 간 엣지 확인
      const moduleEdges = graphData.edges?.filter((e: any) => {
        const sourceIsModule = moduleNodes.some((m: any) => m.id === e.source)
        const targetIsModule = moduleNodes.some((m: any) => m.id === e.target)
        return sourceIsModule && targetIsModule
      }) || []
      console.log('🔗 모듈 간 엣지:', moduleEdges.map((e: any) => ({
        id: e.id,
        source: e.source,
        target: e.target,
        label: e.label,
      })))
      
      setRawGraphData(graphData)
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

  const handleNodeClick = (nodeId: string) => {
    if (onNodeClick) {
      onNodeClick(nodeId)
    }
  }

  const handleModuleToggle = useCallback((moduleId: string) => {
    setExpandedModules((prev) => {
      const newSet = new Set(prev)
      if (newSet.has(moduleId)) {
        newSet.delete(moduleId)
      } else {
        newSet.add(moduleId)
      }
      console.log('🔄 모듈 확장/축소:', moduleId, newSet.has(moduleId))
      return newSet
    })
  }, [])

  const handleLayoutChange = useCallback(
    (direction: 'TB' | 'LR') => {
      if (processedGraphData.nodes.length === 0) return
      
      const { nodes: flowNodes, edges: flowEdges } = processedGraphData
      
      const convertedNodes: Node[] = flowNodes.map((node: any) => ({
        id: node.id,
        type: node.type === 'module' ? 'module' : 'custom',
        data: {
          label: node.name,
          type: node.type,
          description: node.description,
          inputs: node.inputs,
          outputs: node.outputs,
          children: node.children,
          childrenCount: node.childrenCount,
          isExpanded: node.isExpanded,
          onClick: () => handleNodeClick(node.id),
          onToggleExpand: () => handleModuleToggle(node.id),
        },
        position: { x: 0, y: 0 },
      }))

      const convertedEdges: Edge[] = flowEdges.map((edge: any) => {
        const isModuleEdge = edge.data?.isModuleEdge || false
        const isInternalEdge = edge.data?.isInternalEdge || false
        const strokeWidth = isModuleEdge ? 5 : isInternalEdge ? 4 : 3.5
        const strokeColor = isModuleEdge ? '#6366f1' : isInternalEdge ? '#3b82f6' : '#60a5fa'
        const arrowSize = isModuleEdge ? 35 : isInternalEdge ? 30 : 28

        return {
          id: edge.id,
          source: edge.source,
          target: edge.target,
          label: edge.label || '',
          type: 'smoothstep',
          animated: true,
          markerEnd: {
            type: MarkerType.ArrowClosed,
            width: arrowSize,
            height: arrowSize,
            color: strokeColor,
          },
          style: {
            strokeWidth,
            stroke: strokeColor,
          },
          labelStyle: {
            fill: isModuleEdge ? '#4338ca' : '#1e40af',
            fontSize: isModuleEdge ? 14 : 13,
            fontWeight: 800,
          },
          labelBgStyle: {
            fill: '#ffffff',
            fillOpacity: 1,
            rx: 5,
            ry: 5,
            stroke: strokeColor,
            strokeWidth: 2,
          },
          labelBgPadding: [10, 6] as [number, number],
          labelBgBorderRadius: 5,
        }
      })

      const { nodes: layoutedNodes, edges: layoutedEdges } = getLayoutedElements(
        convertedNodes,
        convertedEdges,
        direction
      )

      setNodes(layoutedNodes)
      setEdges(layoutedEdges)
    },
    [processedGraphData, handleModuleToggle]
  )

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center">
          <ArrowPathIcon className="w-8 h-8 animate-spin mx-auto text-primary-600" />
          <p className="mt-2 text-gray-600">LangGraph 구조를 불러오는 중...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-xl p-6">
        <div className="flex items-center gap-2 text-red-700">
          <InformationCircleIcon className="w-6 h-6" />
          <span className="font-semibold">오류 발생</span>
        </div>
        <p className="mt-2 text-red-600">{error}</p>
      </div>
    )
  }

  return (
    <div className="h-[800px] bg-gray-50 rounded-xl border border-gray-200 overflow-hidden">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.2, maxZoom: 1.0 }}
        attributionPosition="bottom-left"
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={true}
        zoomOnScroll={true}
        panOnScroll={false}
        preventScrolling={true}
        minZoom={0.1}
        maxZoom={3.0}
        defaultViewport={{ x: 0, y: 0, zoom: 0.8 }}
      >
        <Background color="#e2e8f0" gap={16} />
        <Controls />
        <MiniMap
          nodeColor={(node) => {
            const colors = nodeTypeColors[node.data.type] || nodeTypeColors.processor
            return colors.border.replace('border-', '#')
          }}
          maskColor="rgba(0, 0, 0, 0.1)"
        />

        <Panel position="top-left" className="bg-white p-4 rounded-xl shadow-lg border border-gray-200 max-w-xs">
          <h3 className="text-lg font-bold text-gray-900 mb-3">LangGraph 아키텍처</h3>

          {statistics && (
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-600">총 모듈:</span>
                <span className="font-semibold text-gray-900">{statistics.total_modules || 0}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">총 에이전트:</span>
                <span className="font-semibold text-gray-900">{statistics.total_nodes}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">연결:</span>
                <span className="font-semibold text-gray-900">{statistics.total_edges}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">표시된 엣지:</span>
                <span className="font-semibold text-gray-900">{edges.length}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">구조:</span>
                <span className="font-semibold text-gray-900">{statistics.architecture}</span>
              </div>
            </div>
          )}

          <div className="mt-4 pt-4 border-t border-gray-200">
            <p className="text-xs text-gray-500 mb-2">레이아웃:</p>
            <div className="flex gap-2">
              <button
                onClick={() => handleLayoutChange('TB')}
                className="px-3 py-1 text-xs bg-primary-100 text-primary-700 rounded-lg hover:bg-primary-200 transition-colors"
              >
                세로
              </button>
              <button
                onClick={() => handleLayoutChange('LR')}
                className="px-3 py-1 text-xs bg-primary-100 text-primary-700 rounded-lg hover:bg-primary-200 transition-colors"
              >
                가로
              </button>
            </div>
          </div>

          <div className="mt-4 pt-4 border-t border-gray-200">
            <p className="text-xs text-gray-500 mb-2">사용법:</p>
            <p className="text-xs text-gray-600">
              모듈을 클릭하면 내부 에이전트들이 표시됩니다.
            </p>
          </div>
        </Panel>

        <Panel position="top-right" className="bg-white p-4 rounded-xl shadow-lg border border-gray-200 max-w-xs">
          <h4 className="text-sm font-bold text-gray-900 mb-3">에이전트 타입</h4>
          <div className="space-y-2 text-xs">
            {Object.entries(nodeTypeColors).map(([type, colors]) => (
              <div key={type} className="flex items-center gap-2">
                <div className={`w-4 h-4 rounded ${colors.bg} ${colors.border} border-2`} />
                <span className="text-gray-700 capitalize font-medium">{type}</span>
              </div>
            ))}
          </div>
          
          <div className="mt-4 pt-4 border-t border-gray-200">
            <h4 className="text-sm font-bold text-gray-900 mb-2">화살표 의미</h4>
            <div className="space-y-2 text-xs">
              <div className="flex items-center gap-2">
                <div className="w-10 h-1 bg-indigo-600 relative">
                  <div className="absolute right-0 top-1/2 -translate-y-1/2 w-0 h-0 border-l-[10px] border-l-indigo-600 border-t-[6px] border-t-transparent border-b-[6px] border-b-transparent"></div>
                </div>
                <span className="text-gray-700">모듈 간 연결</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-10 h-1 bg-blue-500 relative">
                  <div className="absolute right-0 top-1/2 -translate-y-1/2 w-0 h-0 border-l-[8px] border-l-blue-500 border-t-[5px] border-t-transparent border-b-[5px] border-b-transparent"></div>
                </div>
                <span className="text-gray-700">내부 에이전트 연결</span>
              </div>
            </div>
          </div>
        </Panel>
      </ReactFlow>
    </div>
  )
}