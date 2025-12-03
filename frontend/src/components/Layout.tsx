/**
 * 레이아웃 컴포넌트
 * 네비게이션 바 및 전체 레이아웃
 */
import { Outlet, Link, useNavigate, useLocation } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'
import { 
  HomeIcon, 
  DocumentTextIcon, 
  ChatBubbleBottomCenterIcon,
  ChartBarIcon,
  ArrowRightOnRectangleIcon,
  UserCircleIcon,
  CpuChipIcon,
  UserGroupIcon,
  PlayIcon,
  SpeakerWaveIcon,
  BookOpenIcon
} from '@heroicons/react/24/outline'

export default function Layout() {
  const { user, logout } = useAuthStore()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-secondary-50 to-primary-50">
      {/* Navigation Bar */}
      <nav className="bg-white/80 backdrop-blur-md shadow-lg border-b border-primary-100">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16">
            {/* Logo */}
            <div className="flex items-center">
              <Link to="/home" className="flex items-center space-x-3 group">
                <img src="/assets/bear.png" alt="하경은행" className="w-10 h-10 rounded-full shadow-md group-hover:shadow-lg transition-shadow" />
                <div className="flex flex-col">
                  <span className="text-xl font-bold text-bank-800 group-hover:text-primary-700 transition-colors">하경은행</span>
                  <span className="text-sm text-primary-600 -mt-1 font-medium">온보딩 플랫폼</span>
                </div>
              </Link>
            </div>

            {/* Navigation Links */}
            <div className="flex items-center space-x-1">
              <NavLink to="/home" icon={HomeIcon} text="홈" paths={['/home']} />
              <NavLink to="/iq-simulation" icon={PlayIcon} text="시뮬레이션" paths={['/iq-simulation', '/rag-simulation', '/simulation', '/voice-simulation']} />
              <NavLink to="/learning" icon={BookOpenIcon} text="학습 관리" paths={['/learning']} />
              {user?.role === 'admin' && <NavLink to="/rag" icon={CpuChipIcon} text="AI 관리" paths={['/rag']} />}
              <NavLink to="/board" icon={ChatBubbleBottomCenterIcon} text="동아리" paths={['/board']} />
              <NavLink to="/dashboard" icon={ChartBarIcon} text="대시보드" paths={['/dashboard', '/simulation-feedback']} />
            </div>

            {/* User Menu */}
            <div className="flex items-center space-x-4">

              <button
                className="flex items-center space-x-2 focus:outline-none group"
                onClick={() => navigate('/mypage')}
                title="마이페이지로 이동"
              >
                {user?.photo_url ? (
                  <img
                    src={user.photo_url.startsWith('/uploads') ? `/api${user.photo_url}` : user.photo_url}
                    alt={user.name}
                    className="w-8 h-8 rounded-full object-cover"
                  />
                ) : (
                  <UserCircleIcon className="w-8 h-8 text-primary-400 group-hover:text-primary-600 transition-colors" />
                )}
                <div className="hidden md:block text-sm text-left">
                  <div className="font-medium text-bank-800 group-hover:text-primary-700 transition-colors">{user?.name}</div>
                  <div className="text-primary-500 text-xs">
                    {user?.role === 'admin' && '관리자'}
                    {user?.role === 'mentor' && '멘토'}
                    {user?.role === 'mentee' && '신입사원'}
                  </div>
                </div>
              </button>
              
              <button
                onClick={handleLogout}
                className="flex items-center space-x-1 px-3 py-2 rounded-lg text-bank-700 hover:bg-primary-50 hover:text-primary-700 transition-all duration-200 border border-transparent hover:border-primary-200"
              >
                <ArrowRightOnRectangleIcon className="w-5 h-5" />
                <span className="hidden md:inline text-sm font-medium">로그아웃</span>
              </button>
            </div>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <Outlet />
      </main>
    </div>
  )
}

function NavLink({ to, icon: Icon, text, paths }: { to: string; icon: any; text: string; paths?: string[] }) {
  const location = useLocation()
  const currentPath = location.pathname
  const locationState = location.state as any
  
  // 현재 경로가 이 탭과 관련된 경로인지 확인
  let isActive = paths ? paths.some(path => currentPath.startsWith(path)) : currentPath === to
  
  // /simulation-feedback 경로의 경우, 어디서 왔는지에 따라 탭 활성화 결정
  if (currentPath === '/simulation-feedback') {
    if (text === '시뮬레이션') {
      // 대시보드에서 온 경우가 아니면 시뮬레이션 탭 활성화
      isActive = !locationState?.fromHistory
    } else if (text === '대시보드') {
      // 대시보드에서 온 경우에만 대시보드 탭 활성화
      isActive = locationState?.fromHistory === true
    }
  }
  
  return (
    <Link
      to={to}
      className={`flex items-center space-x-2 px-4 py-2 rounded-xl transition-all duration-200 group ${
        isActive
          ? 'bg-primary-50 text-primary-700'
          : 'text-bank-700 hover:bg-primary-50 hover:text-primary-700'
      }`}
    >
      <Icon className="w-5 h-5 group-hover:scale-110 transition-transform" />
      <span className="hidden md:inline text-sm font-medium">{text}</span>
    </Link>
  )
}



