import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from './store/authStore'
import Layout from './components/Layout'
import Landing from './pages/Landing'
import Login from './pages/Login'
import Register from './pages/Register'
import FindId from './pages/FindId'
import FindPassword from './pages/FindPassword'

import Home from './pages/Home'
import Documents from './pages/Documents'
import IQStyleSimulation from './pages/IQStyleSimulation'
import RAG from './pages/RAG'
import RAGSimulation from './pages/RAGSimulation'
import AnonymousBoard from './pages/AnonymousBoard'
import PostDetail from './pages/PostDetail'
import Dashboard from './pages/Dashboard'
import MyPage from './pages/MyPage'
import ProjectIntro from './pages/ProjectIntro'
import SimulationFeedback from './pages/SimulationFeedback'
import ChatBot from './components/ChatBot'

// 관리자 전용 라우트 컴포넌트
function AdminOnlyRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, user } = useAuthStore()
  
  if (!isAuthenticated) {
    return <Navigate to="/login" />
  }
  
  if (user?.role !== 'admin') {
    return <Navigate to="/home" />
  }
  
  return <>{children}</>
}

function App() {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated)

  return (
    <>
      <Routes>
        {/* Public routes */}
        <Route path="/" element={!isAuthenticated ? <Landing /> : <Navigate to="/home" />} />
        <Route path="/login" element={!isAuthenticated ? <Login /> : <Navigate to="/home" />} />
        <Route path="/register" element={!isAuthenticated ? <Register /> : <Navigate to="/home" />} />
        <Route path="/find-id" element={!isAuthenticated ? <FindId /> : <Navigate to="/home" />} />
        <Route path="/find-password" element={!isAuthenticated ? <FindPassword /> : <Navigate to="/home" />} />
        <Route path="/intro" element={<ProjectIntro />} />

        {/* Protected routes */}
        <Route element={<Layout />}>
          <Route path="/home" element={isAuthenticated ? <Home /> : <Navigate to="/login" />} />
          <Route path="/documents" element={isAuthenticated ? <Documents /> : <Navigate to="/login" />} />
          <Route path="/simulation" element={isAuthenticated ? <IQStyleSimulation /> : <Navigate to="/login" />} />
          <Route path="/iq-simulation" element={isAuthenticated ? <IQStyleSimulation /> : <Navigate to="/login" />} />
          <Route path="/rag-simulation" element={isAuthenticated ? <RAGSimulation /> : <Navigate to="/login" />} />
          <Route path="/simulation-feedback" element={isAuthenticated ? <SimulationFeedback /> : <Navigate to="/login" />} />
          <Route path="/rag" element={<AdminOnlyRoute><RAG /></AdminOnlyRoute>} />
          <Route path="/board" element={<AnonymousBoard />} />
          <Route path="/board/:postId" element={isAuthenticated ? <PostDetail /> : <Navigate to="/login" />} />
          <Route path="/dashboard" element={isAuthenticated ? <Dashboard /> : <Navigate to="/login" />} />
          <Route path="/mypage" element={isAuthenticated ? <MyPage /> : <Navigate to="/login" />} />
        </Route>

        {/* Fallback */}
        <Route path="*" element={<Navigate to="/" />} />
      </Routes>

      {/* Floating chatbot - only show when authenticated */}
      {isAuthenticated && <ChatBot />}
    </>
  )
}

export default App



