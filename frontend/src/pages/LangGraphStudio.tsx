import { PlayIcon, ArrowTopRightOnSquareIcon } from '@heroicons/react/24/outline'

export default function LangGraphStudio() {
  const studioUrl = "https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024"

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900 mb-2">LangGraph Studio (LANGGRAPH 2)</h1>
        <p className="text-gray-600">
          LangGraph 에이전트의 실행 흐름을 시각화하고 테스트할 수 있는 도구입니다.
        </p>
      </div>
      
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
        <div className="p-6 border-b border-gray-100 bg-gray-50">
          <h2 className="text-lg font-semibold text-gray-900">Studio 연결 상태</h2>
        </div>
        <div className="p-6">
          <div className="flex items-start space-x-4">
            <div className="flex-shrink-0">
              <div className="p-3 bg-blue-100 rounded-lg">
                <PlayIcon className="w-6 h-6 text-blue-600" />
              </div>
            </div>
            <div className="flex-1">
              <h3 className="text-base font-medium text-gray-900 mb-1">로컬 서버 연결</h3>
              <p className="text-sm text-gray-500 mb-4">
                백엔드에서 실행 중인 LangGraph API 서버(Port 2024)에 연결합니다.<br/>
                아래 버튼을 클릭하면 LangSmith Studio가 새 탭에서 열립니다.
              </p>
              
              <a 
                href={studioUrl} 
                target="_blank" 
                rel="noopener noreferrer"
                className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 transition-colors"
              >
                <ArrowTopRightOnSquareIcon className="w-4 h-4 mr-2" />
                LangGraph Studio 열기
              </a>
            </div>
          </div>
          
          <div className="mt-6 pt-6 border-t border-gray-100">
            <h4 className="text-sm font-medium text-gray-900 mb-3">사용 가능한 그래프</h4>
            <ul className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              {['simulation', 'rag', 'exam'].map((graph) => (
                <li key={graph} className="relative flex items-center space-x-3 rounded-lg border border-gray-300 bg-white px-6 py-5 shadow-sm focus-within:ring-2 focus-within:ring-blue-500 focus-within:ring-offset-2 hover:border-gray-400">
                  <div className="min-w-0 flex-1">
                    <span className="absolute inset-0" aria-hidden="true" />
                    <p className="text-sm font-medium text-gray-900">{graph}</p>
                    <p className="truncate text-sm text-gray-500">Graph Workflow</p>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </div>
  )
}

