/**
 * 프로젝트 소개 페이지
 * AI 활용 어플리케이션 개발 - 하경은행 스마트 온보딩 플랫폼
 */
import { motion } from 'framer-motion'
import { Link } from 'react-router-dom'
import { useState } from 'react'
import { 
  ChatBubbleLeftRightIcon,
  UserGroupIcon,
  ChartBarIcon,
  LockClosedIcon,
  ServerIcon,
  CircleStackIcon,
  CpuChipIcon,
  GlobeAltIcon,
  ShieldCheckIcon,
  AcademicCapIcon,
  ArrowRightIcon,
  PlayIcon,
  XMarkIcon
} from '@heroicons/react/24/outline'

export default function ProjectIntro() {
  const [selectedTech, setSelectedTech] = useState<string | null>(null)
  const [showCodeModal, setShowCodeModal] = useState(false)

  return (
    <div className="min-h-screen bg-white">
      {/* Navigation */}
      <nav className="fixed top-0 left-0 right-0 bg-white/90 backdrop-blur-md z-50 border-b border-gray-100">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <Link to="/" className="flex items-center space-x-3">
              <img src="/assets/bear.png" alt="하경곰" className="w-10 h-10 rounded-full" />
              <span className="text-xl font-bold text-gray-900">하경은행</span>
            </Link>
            <div className="flex items-center space-x-6">
              <Link to="/" className="text-gray-600 hover:text-primary-600 transition-colors">
                홈으로
              </Link>
              <Link to="/login" className="text-gray-600 hover:text-primary-600 transition-colors">
                로그인
              </Link>
            </div>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="pt-24 pb-16 bg-gradient-to-br from-primary-600 via-primary-500 to-amber-500">
        <div className="max-w-7xl mx-auto px-6">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8 }}
            className="text-center text-white"
          >
            <h1 className="text-6xl font-bold mb-6">
              하경은행 스마트 온보딩 플랫폼
            </h1>
            <p className="text-2xl text-primary-100 max-w-4xl mx-auto mb-12 leading-relaxed">
              RAG 기반 AI 챗봇과 체계적인 멘토링 시스템으로<br />
              신입사원의 성공적인 온보딩을 지원합니다
            </p>

            {/* 프로젝트 개요 카드 */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.8, delay: 0.2 }}
              className="bg-white/90 backdrop-blur-sm rounded-3xl p-8 shadow-2xl border border-white/20 max-w-5xl mx-auto"
            >
              <div className="grid md:grid-cols-2 gap-8">
                <div className="text-center">
                  <div className="w-16 h-16 bg-gradient-to-br from-primary-500 to-primary-600 rounded-2xl flex items-center justify-center mx-auto mb-4">
                    <ChatBubbleLeftRightIcon className="w-8 h-8 text-white" />
                  </div>
                  <h3 className="text-xl font-semibold text-gray-900 mb-2">챗봇</h3>
                  <p className="text-gray-600">RAG 기술과 GPT 모델을<br />활용한 지능형 챗봇</p>
                </div>
                <div className="text-center">
                  <div className="w-16 h-16 bg-gradient-to-br from-amber-500 to-amber-600 rounded-2xl flex items-center justify-center mx-auto mb-4">
                    <UserGroupIcon className="w-8 h-8 text-white" />
                  </div>
                  <h3 className="text-xl font-semibold text-gray-900 mb-2">멘토링 시스템</h3>
                  <p className="text-gray-600">체계적인 멘토-멘티 매칭과<br />성과 관리</p>
                </div>
                <div className="text-center">
                  <div className="w-16 h-16 bg-gradient-to-br from-bank-500 to-bank-600 rounded-2xl flex items-center justify-center mx-auto mb-4">
                    <ShieldCheckIcon className="w-8 h-8 text-white" />
                  </div>
                  <h3 className="text-xl font-semibold text-gray-900 mb-2">은행 특화</h3>
                  <p className="text-gray-600">은행업무에 특화된<br />온보딩 솔루션</p>
                </div>
                <div className="text-center">
                  <div className="w-16 h-16 bg-gradient-to-br from-accent-500 to-accent-600 rounded-2xl flex items-center justify-center mx-auto mb-4">
                    <ChartBarIcon className="w-8 h-8 text-white" />
                  </div>
                  <h3 className="text-xl font-semibold text-gray-900 mb-2">역할별 대시보드</h3>
                  <p className="text-gray-600">멘티, 멘토, 관리자<br />맞춤형 대시보드</p>
                </div>
              </div>
            </motion.div>
          </motion.div>
        </div>
      </section>

      {/* 문제 인식 섹션 */}
      <section className="py-24 bg-gradient-to-br from-gray-50 to-blue-50">
        <div className="max-w-7xl mx-auto px-6">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8 }}
            viewport={{ once: true }}
            className="text-center mb-16"
          >
            <h2 className="text-5xl font-bold text-gray-900 mb-6">
              신입사원의 어려움
            </h2>
            <p className="text-xl text-gray-600 max-w-3xl mx-auto mb-12">
              새로운 직장에서 겪는 기술적, 문화적<br />적응의 어려움을 해결합니다
            </p>
          </motion.div>

          <div className="grid md:grid-cols-2 gap-12">
            {/* 문제점 */}
            <motion.div
              initial={{ opacity: 0, x: -30 }}
              whileInView={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.8 }}
              viewport={{ once: true }}
              className="bg-white rounded-3xl p-8 shadow-xl"
            >
              <h3 className="text-2xl font-bold text-red-600 mb-6">문제점</h3>
              <div className="space-y-4">
                <div className="flex items-start space-x-3">
                  <div className="w-2 h-2 bg-red-500 rounded-full mt-3"></div>
                  <div>
                    <h4 className="font-semibold text-gray-900">기술적 적응 어려움</h4>
                    <p className="text-gray-600">복잡한 은행 시스템과<br />업무 프로세스 이해의 어려움</p>
                  </div>
                </div>
                <div className="flex items-start space-x-3">
                  <div className="w-2 h-2 bg-red-500 rounded-full mt-3"></div>
                  <div>
                    <h4 className="font-semibold text-gray-900">문화적 적응 어려움</h4>
                    <p className="text-gray-600">조직 문화와<br />인간관계 형성의 어려움</p>
                  </div>
                </div>
                <div className="flex items-start space-x-3">
                  <div className="w-2 h-2 bg-red-500 rounded-full mt-3"></div>
                  <div>
                    <h4 className="font-semibold text-gray-900">지속적 지원 부족</h4>
                    <p className="text-gray-600">일시적 교육 후<br />지속적인 도움의 부재</p>
                  </div>
                </div>
              </div>
            </motion.div>

            {/* 해결책 */}
            <motion.div
              initial={{ opacity: 0, x: 30 }}
              whileInView={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.8 }}
              viewport={{ once: true }}
              className="bg-white rounded-3xl p-8 shadow-xl"
            >
              <h3 className="text-2xl font-bold text-green-600 mb-6">우리의 해결책</h3>
              <div className="space-y-4">
                <div className="flex items-start space-x-3">
                  <div className="w-2 h-2 bg-green-500 rounded-full mt-3"></div>
                  <div>
                    <h4 className="font-semibold text-gray-900">RAG 기반 AI 챗봇</h4>
                    <p className="text-gray-600">24/7 기술적 질문에 대한<br />정확한 답변 제공</p>
                  </div>
                </div>
                <div className="flex items-start space-x-3">
                  <div className="w-2 h-2 bg-green-500 rounded-full mt-3"></div>
                  <div>
                    <h4 className="font-semibold text-gray-900">멘토-멘티 시스템</h4>
                    <p className="text-gray-600">개인 맞춤형 멘토링과<br />지속적인 관계 형성</p>
                  </div>
                </div>
                <div className="flex items-start space-x-3">
                  <div className="w-2 h-2 bg-green-500 rounded-full mt-3"></div>
                  <div>
                    <h4 className="font-semibold text-gray-900">대나무숲</h4>
                    <p className="text-gray-600">익명으로 조직 내<br />고민과 정보를 공유</p>
                  </div>
                </div>
              </div>
            </motion.div>
          </div>
        </div>
      </section>

      {/* 기술 스택 */}
      <section className="py-24 bg-gradient-to-br from-blue-50 to-indigo-50">
        <div className="max-w-7xl mx-auto px-6">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8 }}
            viewport={{ once: true }}
            className="text-center mb-16"
          >
            <h2 className="text-5xl font-bold text-gray-900 mb-6">
              기술 스택
            </h2>
            <p className="text-xl text-gray-600 max-w-3xl mx-auto mb-12">
              최신 기술 스택으로 안정적이고<br />확장 가능한 시스템을 구축했습니다
            </p>
          </motion.div>

          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-8">
            <TechStackCard
              icon={GlobeAltIcon}
              title="Frontend"
              description="React, TypeScript, Tailwind CSS"
              color="blue"
              techKey="frontend"
              onClick={() => {
                setSelectedTech('frontend')
                setShowCodeModal(true)
              }}
            />
            <TechStackCard
              icon={ServerIcon}
              title="Backend"
              description="FastAPI, Python, Uvicorn"
              color="green"
              techKey="backend"
              onClick={() => {
                setSelectedTech('backend')
                setShowCodeModal(true)
              }}
            />
            <TechStackCard
              icon={CircleStackIcon}
              title="Database"
              description="PostgreSQL, pgvector, Redis"
              color="purple"
              techKey="database"
              onClick={() => {
                setSelectedTech('database')
                setShowCodeModal(true)
              }}
            />
            <TechStackCard
              icon={CpuChipIcon}
              title="AI/ML"
              description="OpenAI GPT, RAG, Embeddings"
              color="amber"
              techKey="ai"
              onClick={() => {
                setSelectedTech('ai')
                setShowCodeModal(true)
              }}
            />
          </div>
        </div>
      </section>

      {/* 시스템 구조도 */}
      <section className="py-24 bg-gradient-to-br from-indigo-50 to-purple-50">
        <div className="max-w-7xl mx-auto px-6">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8 }}
            viewport={{ once: true }}
            className="text-center mb-16"
          >
            <h2 className="text-5xl font-bold text-gray-900 mb-6">
              시스템 구조도
            </h2>
            <p className="text-xl text-gray-600 max-w-3xl mx-auto mb-12">
              계층형 아키텍처로 구성된<br />안정적이고 확장 가능한 시스템
            </p>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8 }}
            viewport={{ once: true }}
            className="bg-white rounded-3xl p-8 shadow-xl"
          >
            <SystemArchitectureDiagram onTechClick={setSelectedTech} />
          </motion.div>
        </div>
      </section>

      {/* 시스템 아키텍처 */}
      <section className="py-24 bg-gradient-to-br from-purple-50 to-pink-50">
        <div className="max-w-7xl mx-auto px-6">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8 }}
            viewport={{ once: true }}
            className="text-center mb-16"
          >
            <h2 className="text-5xl font-bold text-gray-900 mb-6">
              시스템 아키텍처
            </h2>
            <p className="text-xl text-gray-600 max-w-3xl mx-auto mb-12">
              확장 가능하고 안정적인<br />마이크로서비스 아키텍처
            </p>
          </motion.div>

          <div className="grid md:grid-cols-3 gap-8">
            <motion.div
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.8 }}
              viewport={{ once: true }}
              className="bg-white rounded-3xl p-8 shadow-xl"
            >
              <div className="w-12 h-12 bg-gradient-to-br from-blue-500 to-blue-600 rounded-xl flex items-center justify-center mb-6">
                <CpuChipIcon className="w-6 h-6 text-white" />
              </div>
              <h3 className="text-2xl font-bold text-gray-900 mb-6">AI 서비스</h3>
              <div className="space-y-4">
                <div className="flex items-start space-x-3">
                  <div className="w-2 h-2 bg-blue-500 rounded-full mt-3"></div>
                  <div>
                    <h4 className="font-semibold text-gray-900">RAG 기반 답변 생성</h4>
                    <p className="text-gray-600">도메인 특화 지식 기반<br />정확한 답변</p>
                  </div>
                </div>
                <div className="flex items-start space-x-3">
                  <div className="w-2 h-2 bg-blue-500 rounded-full mt-3"></div>
                  <div>
                    <h4 className="font-semibold text-gray-900">벡터 검색</h4>
                    <p className="text-gray-600">pgvector를 활용한<br />의미적 유사도 검색</p>
                  </div>
                </div>
                <div className="flex items-start space-x-3">
                  <div className="w-2 h-2 bg-blue-500 rounded-full mt-3"></div>
                  <div>
                    <h4 className="font-semibold text-gray-900">컨텍스트 기반 대화</h4>
                    <p className="text-gray-600">이전 대화 맥락을 고려한<br />연속적 대화</p>
                  </div>
                </div>
              </div>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.8, delay: 0.1 }}
              viewport={{ once: true }}
              className="bg-white rounded-3xl p-8 shadow-xl"
            >
              <div className="w-12 h-12 bg-gradient-to-br from-green-500 to-green-600 rounded-xl flex items-center justify-center mb-6">
                <LockClosedIcon className="w-6 h-6 text-white" />
              </div>
              <h3 className="text-2xl font-bold text-gray-900 mb-6">보안 및 인증</h3>
              <div className="space-y-4">
                <div className="flex items-start space-x-3">
                  <div className="w-2 h-2 bg-green-500 rounded-full mt-3"></div>
                  <div>
                    <h4 className="font-semibold text-gray-900">JWT 토큰 기반 인증</h4>
                    <p className="text-gray-600">무상태 인증으로<br />확장성 확보</p>
                  </div>
                </div>
                <div className="flex items-start space-x-3">
                  <div className="w-2 h-2 bg-green-500 rounded-full mt-3"></div>
                  <div>
                    <h4 className="font-semibold text-gray-900">역할 기반 접근 제어</h4>
                    <p className="text-gray-600">멘티, 멘토, 관리자별<br />권한 관리</p>
                  </div>
                </div>
                <div className="flex items-start space-x-3">
                  <div className="w-2 h-2 bg-green-500 rounded-full mt-3"></div>
                  <div>
                    <h4 className="font-semibold text-gray-900">비밀번호 암호화</h4>
                    <p className="text-gray-600">bcrypt를 활용한<br />안전한 비밀번호 저장</p>
                  </div>
                </div>
              </div>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.8, delay: 0.2 }}
              viewport={{ once: true }}
              className="bg-white rounded-3xl p-8 shadow-xl"
            >
              <div className="w-12 h-12 bg-gradient-to-br from-purple-500 to-purple-600 rounded-xl flex items-center justify-center mb-6">
                <ServerIcon className="w-6 h-6 text-white" />
              </div>
              <h3 className="text-2xl font-bold text-gray-900 mb-6">데이터 관리</h3>
              <div className="space-y-4">
                <div className="flex items-start space-x-3">
                  <div className="w-2 h-2 bg-purple-500 rounded-full mt-3"></div>
                  <div>
                    <h4 className="font-semibold text-gray-900">PostgreSQL</h4>
                    <p className="text-gray-600">ACID 준수 관계형<br />데이터베이스</p>
                  </div>
                </div>
                <div className="flex items-start space-x-3">
                  <div className="w-2 h-2 bg-purple-500 rounded-full mt-3"></div>
                  <div>
                    <h4 className="font-semibold text-gray-900">Redis 캐싱</h4>
                    <p className="text-gray-600">고성능 인메모리<br />데이터 저장소</p>
                  </div>
                </div>
                <div className="flex items-start space-x-3">
                  <div className="w-2 h-2 bg-purple-500 rounded-full mt-3"></div>
                  <div>
                    <h4 className="font-semibold text-gray-900">파일 업로드</h4>
                    <p className="text-gray-600">안전한 문서 저장 및<br />관리 시스템</p>
                  </div>
                </div>
              </div>
            </motion.div>
          </div>
        </div>
      </section>

      {/* Docker 컨테이너 아키텍처 */}
      <section className="py-24 bg-gradient-to-br from-pink-50 to-rose-50">
        <div className="max-w-7xl mx-auto px-6">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8 }}
            viewport={{ once: true }}
            className="text-center mb-16"
          >
            <h2 className="text-5xl font-bold text-gray-900 mb-6">
              Docker 컨테이너 아키텍처
            </h2>
            <p className="text-xl text-gray-600 max-w-3xl mx-auto mb-12">
              컨테이너 기반 배포로 일관된<br />개발 환경과 확장성 확보
            </p>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8 }}
            viewport={{ once: true }}
            className="bg-white rounded-3xl p-8 shadow-xl"
          >
            <DockerArchitectureDiagram onTechClick={setSelectedTech} />
          </motion.div>
        </div>
      </section>

      {/* ERD 다이어그램 */}
      <section className="py-24 bg-gradient-to-br from-rose-50 to-orange-50">
        <div className="max-w-7xl mx-auto px-6">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8 }}
            viewport={{ once: true }}
            className="text-center mb-16"
          >
            <h2 className="text-5xl font-bold text-gray-900 mb-6">
              ERD 다이어그램
            </h2>
            <p className="text-xl text-gray-600 max-w-3xl mx-auto mb-12">
              데이터베이스 구조와 테이블 간의 관계
            </p>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8 }}
            viewport={{ once: true }}
            className="bg-white rounded-3xl p-8 shadow-xl"
          >
            <ERDDiagram />
          </motion.div>
        </div>
      </section>

      {/* API 명세서 */}
      <section className="py-24 bg-gradient-to-br from-orange-50 to-amber-50">
        <div className="max-w-7xl mx-auto px-6">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8 }}
            viewport={{ once: true }}
            className="text-center mb-16"
          >
            <h2 className="text-5xl font-bold text-gray-900 mb-6">
              API 명세서
            </h2>
            <p className="text-xl text-gray-600 max-w-3xl mx-auto mb-12">
              RESTful API 설계로 클라이언트와<br />서버 간 효율적인 통신
            </p>
          </motion.div>

          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
            <APISpecCard
              title="인증 API"
              description="사용자 로그인 및 토큰 관리"
              endpoints={[
                "POST /auth/login",
                "POST /auth/register", 
                "POST /auth/refresh",
                "POST /auth/logout"
              ]}
              color="blue"
            />
            <APISpecCard
              title="챗봇 API"
              description="AI 챗봇 상호작용"
              endpoints={[
                "POST /api/chat",
                "GET /api/chat/history",
                "POST /api/chat/upload"
              ]}
              color="green"
            />
            <APISpecCard
              title="문서 API"
              description="학습 자료 관리"
              endpoints={[
                "GET /api/documents/list",
                "POST /api/documents/upload",
                "GET /api/documents/:id"
              ]}
              color="purple"
            />
            <APISpecCard
              title="대나무숲 API"
              description="익명 게시판 관리"
              endpoints={[
                "GET /api/posts",
                "POST /api/posts",
                "PUT /api/posts/:id",
                "DELETE /api/posts/:id"
              ]}
              color="amber"
            />
          </div>
        </div>
      </section>

      {/* 화면 설계 */}
      <section className="py-24 bg-gradient-to-br from-amber-50 to-yellow-50">
        <div className="max-w-7xl mx-auto px-6">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8 }}
            viewport={{ once: true }}
            className="text-center mb-16"
          >
            <h2 className="text-5xl font-bold text-gray-900 mb-6">
              화면 설계
            </h2>
            <p className="text-xl text-gray-600 max-w-3xl mx-auto mb-12">
              사용자 중심의 직관적인 UI/UX 설계
            </p>
          </motion.div>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8">
            <ScreenDesignCard
              title="로그인/회원가입"
              description="간편한 인증 프로세스"
              features={["소셜 로그인", "자동 로그인", "비밀번호 찾기"]}
            />
            <ScreenDesignCard
              title="대시보드"
              description="개인화된 메인 화면"
              features={["학습 진행도", "최근 활동", "빠른 접근"]}
            />
            <ScreenDesignCard
              title="AI 챗봇"
              description="24/7 도움을 주는 AI 어시스턴트"
              features={["실시간 채팅", "파일 업로드", "히스토리"]}
            />
            <ScreenDesignCard
              title="멘토링 시스템"
              description="1:1 맞춤형 멘토링 플랫폼"
              features={["멘토 매칭", "일정 예약 시스템 (추후 추가 예정)", "화상/채팅 멘토링 (추후 추가 예정)", "피드백"]}
            />
            <ScreenDesignCard
              title="자료실"
              description="체계적인 학습 자료 관리"
              features={["카테고리 분류", "검색 기능", "다운로드"]}
            />
            <ScreenDesignCard
              title="대나무숲"
              description="익명 커뮤니티 공간"
              features={["익명 게시", "실시간 댓글", "감정 표현"]}
            />
          </div>
        </div>
      </section>

      {/* 구현 화면 */}
      <section className="py-24 bg-gradient-to-br from-yellow-50 to-green-50">
        <div className="max-w-7xl mx-auto px-6">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8 }}
            viewport={{ once: true }}
            className="text-center mb-16"
          >
            <h2 className="text-5xl font-bold text-gray-900 mb-6">
              구현 화면
            </h2>
            <p className="text-xl text-gray-600 max-w-3xl mx-auto mb-12">
              실제 구현된 시스템의 주요 화면들
            </p>
          </motion.div>

          <div className="space-y-12">
            <ImplementationScreen
              title="메인 대시보드"
              description="신입사원을 위한 맞춤형 온보딩 대시보드"
              features={[
                "학습 진행도 추적",
                "AI 챗봇 빠른 접근",
                "최근 활동 요약",
                "멘토링 일정 확인"
              ]}
            />
            <ImplementationScreen
              title="AI 챗봇 인터페이스"
              description="RAG 기반 지능형 대화 시스템"
              features={[
                "자연어 질문 처리",
                "문서 업로드 및 분석",
                "대화 히스토리 관리",
                "컨텍스트 기반 답변"
              ]}
            />
            <ImplementationScreen
              title="멘토링 시스템"
              description="1:1 멘토링 매칭과 피드백 시스템"
              features={[
                "멘토-멘티 매칭",
                "일정 예약 시스템 (추후 추가 예정)",
                "화상/채팅 멘토링 (추후 추가 예정)",
                "피드백 및 평가"
              ]}
            />
          </div>
        </div>
      </section>

      {/* 주요 성과 */}
      <section className="py-24 bg-gradient-to-br from-green-50 to-teal-50">
        <div className="max-w-7xl mx-auto px-6">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8 }}
            viewport={{ once: true }}
            className="text-center mb-16"
          >
            <h2 className="text-5xl font-bold text-gray-900 mb-6">
              주요 성과
            </h2>
            <p className="text-xl text-gray-600 max-w-3xl mx-auto mb-12">
              프로젝트를 통해 달성한<br />성과와 향후 목표
            </p>
          </motion.div>

          <div className="grid md:grid-cols-3 gap-8">
            <AchievementCard
              number="95%"
              title="사용자 만족도"
              description="신입사원 온보딩 만족도 조사 결과 (가 될 예정...)"
              color="primary"
            />
            <AchievementCard
              number="24/7"
              title="지속적 지원"
              description="AI 챗봇을 통한 언제든지 질문 응답"
              color="bank"
            />
            <AchievementCard
              number="100%"
              title="시스템 안정성"
              description="운영 중 시스템 다운타임 0% 달성 (가 되려고 노력하는 중...)"
              color="accent"
            />
          </div>
        </div>
      </section>

      {/* 프로젝트 팀 */}
      <section className="py-24 bg-gradient-to-br from-teal-50 to-cyan-50">
        <div className="max-w-7xl mx-auto px-6">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8 }}
            viewport={{ once: true }}
            className="text-center mb-16"
          >
            <h2 className="text-5xl font-bold text-gray-900 mb-6">
              프로젝트 팀
            </h2>
            <p className="text-xl text-gray-600 max-w-3xl mx-auto">
              7명의 팀원이 각자의 전문성을 발휘하여<br />
              협업으로 완성한 프로젝트입니다
            </p>
          </motion.div>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8">
            <TeamMemberCard
              name="강동기"
              role="로그인 시스템"
              icon={LockClosedIcon}
              color="primary"
            />
            <TeamMemberCard
              name="김민정"
              role="대나무숲"
              icon={UserGroupIcon}
              color="primary"
            />
            <TeamMemberCard
              name="차하경"
              role="챗봇"
              icon={ChatBubbleLeftRightIcon}
              color="amber"
            />
            <TeamMemberCard
              name="신희정"
              role="대시보드"
              icon={ChartBarIcon}
              color="amber"
            />
            <TeamMemberCard
              name="양승호"
              role="AWS & 자료실"
              icon={ServerIcon}
              color="bank"
            />
            <TeamMemberCard
              name="안주영"
              role="프로젝트 매니저"
              icon={AcademicCapIcon}
              color="bank"
            />
          </div>
        </div>
      </section>

      {/* 마무리 */}
      <section className="py-24 bg-gradient-to-br from-cyan-50 to-blue-50">
        <div className="max-w-7xl mx-auto px-6 text-center">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8 }}
            viewport={{ once: true }}
          >
            <div className="flex justify-center mb-8">
              <img src="/assets/bear.png" alt="하경곰" className="w-24 h-24 rounded-full shadow-lg" />
            </div>
            <h2 className="text-5xl font-bold text-gray-900 mb-6">
              AI로 만드는 더 나은 온보딩 경험
            </h2>
            <p className="text-xl text-gray-700 max-w-3xl mx-auto mb-12">
              하경은행 스마트 온보딩 플랫폼은<br />AI 기술과 인간적 배려가 만나 
              <br />
              신입사원의 성공적인 직장 생활을 지원합니다
            </p>
            
            <div className="flex justify-center space-x-6">
              <Link to="/intro">
                <motion.button
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                  className="px-8 py-4 bg-primary-600 text-white rounded-2xl font-semibold text-lg hover:bg-primary-700 transition-colors shadow-lg flex items-center"
                >
                  프로젝트 상세보기
                  <ArrowRightIcon className="w-5 h-5 ml-2" />
                </motion.button>
              </Link>
              <Link to="/register">
                <motion.button
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                  className="px-8 py-4 bg-amber-500 text-white rounded-2xl font-semibold text-lg hover:bg-amber-600 transition-colors shadow-lg flex items-center"
                >
                  <PlayIcon className="w-5 h-5 mr-2" />
                  데모 체험
                </motion.button>
              </Link>
            </div>
          </motion.div>
        </div>
      </section>

      {/* 코드 모달 */}
      {showCodeModal && selectedTech && (
        <CodeModal
          techKey={selectedTech}
          onClose={() => {
            setShowCodeModal(false)
            setSelectedTech(null)
          }}
        />
      )}
    </div>
  )
}

// 기술 스택 카드 컴포넌트
function TechStackCard({ icon: Icon, title, description, color, onClick }: any) {
  const colorClasses: any = {
    blue: 'from-blue-500 to-blue-600',
    green: 'from-green-500 to-green-600',
    purple: 'from-purple-500 to-purple-600',
    amber: 'from-amber-500 to-amber-600',
  }

  return (
    <motion.div
      whileHover={{ scale: 1.05 }}
      whileTap={{ scale: 0.95 }}
      onClick={onClick}
      className="bg-white rounded-2xl p-6 shadow-lg hover:shadow-xl transition-shadow cursor-pointer"
    >
      <div className={`w-12 h-12 rounded-xl bg-gradient-to-br ${colorClasses[color]} flex items-center justify-center mb-4`}>
        <Icon className="w-6 h-6 text-white" />
      </div>
      <h3 className="text-lg font-bold text-gray-900 mb-2">{title}</h3>
      <p className="text-sm text-gray-600">{description}</p>
    </motion.div>
  )
}

// 시스템 구조도 컴포넌트
function SystemArchitectureDiagram({ onTechClick }: { onTechClick: (tech: string) => void }) {
  return (
    <div className="space-y-8">
      {/* 사용자 레이어 */}
      <div className="text-center">
        <div className="bg-gradient-to-r from-blue-500 to-blue-600 text-white rounded-2xl p-6 inline-block shadow-lg">
          <h3 className="text-xl font-bold mb-2">사용자 (신입사원, 멘토)</h3>
          <p className="text-blue-100">웹 브라우저를 통한 접근</p>
        </div>
      </div>

      {/* 화살표 */}
      <div className="flex justify-center">
        <div className="w-1 h-16 bg-gray-300"></div>
      </div>

      {/* 프론트엔드 레이어 */}
      <div className="grid md:grid-cols-3 gap-6">
        <motion.div 
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          onClick={() => onTechClick('react')}
          className="bg-gradient-to-r from-blue-500 to-blue-600 text-white rounded-xl p-4 text-center shadow-lg cursor-pointer hover:shadow-xl transition-shadow"
        >
          <h4 className="font-bold mb-2">React Frontend</h4>
          <p className="text-sm text-blue-100">사용자 인터페이스</p>
        </motion.div>
        <motion.div 
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          onClick={() => onTechClick('typescript')}
          className="bg-gradient-to-r from-blue-600 to-blue-700 text-white rounded-xl p-4 text-center shadow-lg cursor-pointer hover:shadow-xl transition-shadow"
        >
          <h4 className="font-bold mb-2">TypeScript</h4>
          <p className="text-sm text-blue-100">타입 안전성</p>
        </motion.div>
        <motion.div 
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          onClick={() => onTechClick('tailwind')}
          className="bg-gradient-to-r from-blue-700 to-blue-800 text-white rounded-xl p-4 text-center shadow-lg cursor-pointer hover:shadow-xl transition-shadow"
        >
          <h4 className="font-bold mb-2">Tailwind CSS</h4>
          <p className="text-sm text-blue-100">스타일링</p>
        </motion.div>
      </div>

      {/* 화살표 */}
      <div className="flex justify-center">
        <div className="w-1 h-16 bg-gray-300"></div>
      </div>

      {/* 백엔드 레이어 */}
      <div className="grid md:grid-cols-4 gap-4">
        <motion.div 
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          onClick={() => onTechClick('fastapi')}
          className="bg-gradient-to-r from-green-500 to-green-600 text-white rounded-xl p-4 text-center shadow-lg cursor-pointer hover:shadow-xl transition-shadow"
        >
          <h4 className="font-bold mb-2">FastAPI</h4>
          <p className="text-sm text-green-100">API 서버</p>
        </motion.div>
        <motion.div 
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          onClick={() => onTechClick('jwt')}
          className="bg-gradient-to-r from-green-600 to-green-700 text-white rounded-xl p-4 text-center shadow-lg cursor-pointer hover:shadow-xl transition-shadow"
        >
          <h4 className="font-bold mb-2">JWT Auth</h4>
          <p className="text-sm text-green-100">인증</p>
        </motion.div>
        <motion.div 
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          onClick={() => onTechClick('rag')}
          className="bg-gradient-to-r from-green-700 to-green-800 text-white rounded-xl p-4 text-center shadow-lg cursor-pointer hover:shadow-xl transition-shadow"
        >
          <h4 className="font-bold mb-2">RAG Service</h4>
          <p className="text-sm text-green-100">AI 서비스</p>
        </motion.div>
        <motion.div 
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          onClick={() => onTechClick('fileupload')}
          className="bg-gradient-to-r from-green-800 to-green-900 text-white rounded-xl p-4 text-center shadow-lg cursor-pointer hover:shadow-xl transition-shadow"
        >
          <h4 className="font-bold mb-2">File Upload</h4>
          <p className="text-sm text-green-100">파일 처리</p>
        </motion.div>
      </div>

      {/* 화살표 */}
      <div className="flex justify-center">
        <div className="w-1 h-16 bg-gray-300"></div>
      </div>

      {/* 데이터베이스 레이어 */}
      <div className="grid md:grid-cols-3 gap-6">
        <motion.div 
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          onClick={() => onTechClick('postgresql')}
          className="bg-gradient-to-r from-purple-500 to-purple-600 text-white rounded-xl p-4 text-center shadow-lg cursor-pointer hover:shadow-xl transition-shadow"
        >
          <h4 className="font-bold mb-2">PostgreSQL</h4>
          <p className="text-sm text-purple-100">메인 데이터베이스</p>
        </motion.div>
        <motion.div 
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          onClick={() => onTechClick('pgvector')}
          className="bg-gradient-to-r from-purple-600 to-purple-700 text-white rounded-xl p-4 text-center shadow-lg cursor-pointer hover:shadow-xl transition-shadow"
        >
          <h4 className="font-bold mb-2">pgvector</h4>
          <p className="text-sm text-purple-100">벡터 검색</p>
        </motion.div>
        <motion.div 
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          onClick={() => onTechClick('redis')}
          className="bg-gradient-to-r from-purple-700 to-purple-800 text-white rounded-xl p-4 text-center shadow-lg cursor-pointer hover:shadow-xl transition-shadow"
        >
          <h4 className="font-bold mb-2">Redis</h4>
          <p className="text-sm text-purple-100">캐시 & 세션</p>
        </motion.div>
      </div>
    </div>
  )
}

// 성과 카드 컴포넌트
function AchievementCard({ number, title, description, color }: any) {
  const colorClasses: any = {
    primary: 'from-primary-500 to-primary-600',
    amber: 'from-amber-500 to-amber-600',
    bank: 'from-bank-500 to-bank-600',
    accent: 'from-accent-500 to-accent-600',
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      viewport={{ once: true }}
      className="bg-white p-8 rounded-2xl shadow-lg hover:shadow-xl transition-shadow text-center"
    >
      <div className={`text-4xl font-bold bg-gradient-to-br ${colorClasses[color]} bg-clip-text text-transparent mb-4`}>
        {number}
      </div>
      <h3 className="text-xl font-bold text-gray-900 mb-2">{title}</h3>
      <p className="text-gray-600">{description}</p>
    </motion.div>
  )
}

// 팀원 카드 컴포넌트
function TeamMemberCard({ name, role, icon: Icon, color }: any) {
  const colorClasses: any = {
    primary: 'from-primary-500 to-primary-600',
    amber: 'from-amber-500 to-amber-600',
    bank: 'from-bank-500 to-bank-600',
    accent: 'from-accent-500 to-accent-600',
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      viewport={{ once: true }}
      className="bg-white p-6 rounded-2xl shadow-lg hover:shadow-xl transition-shadow text-center"
    >
      <div className={`w-16 h-16 rounded-full bg-gradient-to-br ${colorClasses[color]} mx-auto mb-4 flex items-center justify-center`}>
        <Icon className="w-8 h-8 text-white" />
      </div>
      <h3 className="text-lg font-bold text-gray-900 mb-1">{name}</h3>
      <p className="text-sm text-gray-600">{role}</p>
    </motion.div>
  )
}

// 코드 모달 컴포넌트
function CodeModal({ techKey, onClose }: { techKey: string, onClose: () => void }) {
  const getCodeExamples = (techKey: string) => {
    switch (techKey) {
      case 'frontend':
        return {
          title: 'Frontend 코드 예시',
          description: 'React + TypeScript + Tailwind CSS로 구현된 컴포넌트',
          code: `// 실제 프로젝트 코드: frontend/src/components/ChatBot.tsx
import { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

interface ChatBotProps {
  forceOpen?: boolean
  onClose?: () => void
}

export default function ChatBot({ forceOpen = false, onClose }: ChatBotProps = {}) {
  const [isOpen, setIsOpen] = useState(false)
  const [messages, setMessages] = useState([])
  
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.8 }}
      animate={{ opacity: 1, scale: 1 }}
      className="fixed bottom-4 right-4 z-50"
    >
      {/* 챗봇 UI */}
    </motion.div>
  )
}

// 📁 실제 파일 위치: frontend/src/components/ChatBot.tsx`
        }
      case 'backend':
        return {
          title: 'Backend 코드 예시',
          description: 'FastAPI + Python으로 구현된 API 엔드포인트',
          code: `# 실제 프로젝트 코드: backend/app/main.py
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Bank Mentor System API",
    description="하경은행 스마트 온보딩 플랫폼",
    version="1.0.0"
)

@app.get("/")
async def root():
    return {
        "message": "Welcome to Bank Mentor System API",
        "version": "1.0.0",
        "status": "running"
    }

# 📁 실제 파일 위치: backend/app/main.py`
        }
      case 'database':
        return {
          title: 'Database 모델 예시',
          description: 'SQLModel을 사용한 데이터베이스 모델 정의',
          code: `# 실제 프로젝트 코드: backend/app/models/user.py
from sqlmodel import SQLModel, Field
from typing import Optional

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True)
    email: str = Field(unique=True, index=True)
    role: str = Field(default="mentee")
    is_active: bool = Field(default=True)

# 📁 실제 파일 위치: backend/app/models/user.py`
        }
      case 'ai':
        return {
          title: 'AI 서비스 코드 예시',
          description: 'RAG 기반 AI 챗봇 서비스 구현',
          code: `# 실제 프로젝트 코드: backend/app/services/rag_service.py
class RAGService:
    def __init__(self):
        self.embeddings = OpenAIEmbeddings()
        self.vector_store = PGVector.from_existing_index(...)
    
    async def generate_answer(self, question: str, user_id: int):
        query_vector = await self.get_embedding(question)
        context_docs = self.vector_store.similarity_search(query_vector, k=3)
        answer = await self.generate_with_context(question, context_docs)
        
        return {"answer": answer, "sources": context_docs}

# 📁 실제 파일 위치: backend/app/services/rag_service.py`
        }
      case 'react':
        return {
          title: 'React 사용 이유',
          description: '컴포넌트 기반 UI 개발과 상태 관리',
          code: `// React를 선택한 이유:
// 1. 컴포넌트 재사용성 - UI 요소를 독립적으로 관리
// 2. 가상 DOM - 성능 최적화
// 3. 풍부한 생태계 - 다양한 라이브러리 지원
// 4. 개발자 경험 - Hot Reload, DevTools

// 실제 사용 예시: frontend/src/components/ChatBot.tsx
import { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

export default function ChatBot() {
  const [isOpen, setIsOpen] = useState(false)
  const [messages, setMessages] = useState([])
  
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.8 }}
      animate={{ opacity: 1, scale: 1 }}
      className="fixed bottom-4 right-4 z-50"
    >
      {/* 챗봇 UI */}
    </motion.div>
  )
}

// 📁 실제 파일 위치: frontend/src/components/ChatBot.tsx`
        }
      case 'typescript':
        return {
          title: 'TypeScript 사용 이유',
          description: '타입 안전성과 개발 생산성 향상',
          code: `// TypeScript를 선택한 이유:
// 1. 타입 안전성 - 컴파일 타임 에러 검출
// 2. 자동완성 - IDE 지원 강화
// 3. 리팩토링 안전성 - 코드 변경 시 영향 범위 파악
// 4. 팀 협업 - 명확한 인터페이스 정의

// 실제 사용 예시: frontend/src/store/authStore.ts
interface User {
  id: number
  username: string
  email: string
  role: 'mentee' | 'mentor' | 'admin'
}

interface AuthState {
  user: User | null
  isAuthenticated: boolean
  token: string | null
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isAuthenticated: false,
  token: null,
  login: (user: User, token: string) => set({ user, token, isAuthenticated: true }),
  logout: () => set({ user: null, token: null, isAuthenticated: false })
}))

// 📁 실제 파일 위치: frontend/src/store/authStore.ts`
        }
      case 'tailwind':
        return {
          title: 'Tailwind CSS 사용 이유',
          description: '유틸리티 기반 스타일링과 일관된 디자인',
          code: `// Tailwind CSS를 선택한 이유:
// 1. 유틸리티 클래스 - 빠른 스타일링
// 2. 일관된 디자인 시스템 - spacing, color 체계
// 3. 반응형 디자인 - 모바일 우선 접근
// 4. 번들 크기 최적화 - 사용하지 않는 CSS 제거

// 실제 사용 예시: frontend/src/pages/ProjectIntro.tsx
<div className="bg-gradient-to-br from-primary-600 to-amber-500 rounded-3xl p-12 text-white">
  <h1 className="text-5xl font-bold mb-6">하경은행 스마트 온보딩</h1>
  <p className="text-xl text-primary-100 max-w-3xl mx-auto">
    RAG 기반 AI 챗봇과 체계적인 멘토링 시스템으로<br />
    신입사원의 성공적인 온보딩을 지원합니다
  </p>
</div>

// 📁 실제 파일 위치: frontend/src/pages/ProjectIntro.tsx`
        }
      case 'fastapi':
        return {
          title: 'FastAPI 사용 이유',
          description: '고성능 Python 웹 프레임워크',
          code: `// FastAPI를 선택한 이유:
// 1. 고성능 - Starlette와 Pydantic 기반
// 2. 자동 API 문서화 - Swagger UI 자동 생성
// 3. 타입 힌트 지원 - Python 3.6+ 타입 시스템
// 4. 비동기 지원 - async/await 네이티브 지원

// 실제 사용 예시: backend/app/main.py
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Bank Mentor System API",
    description="하경은행 스마트 온보딩 플랫폼",
    version="1.0.0"
)

@app.get("/")
async def root():
    return {
        "message": "Welcome to Bank Mentor System API",
        "version": "1.0.0",
        "status": "running"
    }

# 📁 실제 파일 위치: backend/app/main.py`
        }
      case 'jwt':
        return {
          title: 'JWT 인증 사용 이유',
          description: '무상태 인증과 보안성',
          code: `// JWT를 선택한 이유:
// 1. 무상태 인증 - 서버에 세션 저장 불필요
// 2. 확장성 - 마이크로서비스 아키텍처에 적합
// 3. 보안성 - 서명을 통한 토큰 무결성 검증
// 4. 표준화 - RFC 7519 표준 준수

// 실제 사용 예시: backend/app/utils/auth.py
import jwt
from datetime import datetime, timedelta
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# 📁 실제 파일 위치: backend/app/utils/auth.py`
        }
      case 'rag':
        return {
          title: 'RAG 기술 사용 이유',
          description: '검색 증강 생성으로 정확한 답변 제공',
          code: `// RAG를 선택한 이유:
// 1. 정확성 - 도메인 특화 지식 기반 답변
// 2. 최신성 - 실시간 정보 반영 가능
// 3. 투명성 - 답변 근거 제시
// 4. 비용 효율성 - GPT API 호출 최적화

// 실제 사용 예시: backend/app/services/rag_service.py
class RAGService:
    def __init__(self):
        self.embeddings = OpenAIEmbeddings()
        self.vector_store = PGVector.from_existing_index(...)
    
    async def generate_answer(self, question: str, user_id: int):
        # 1. 질문을 벡터로 변환
        query_vector = await self.get_embedding(question)
        
        # 2. 관련 문서 검색
        context_docs = self.vector_store.similarity_search(query_vector, k=3)
        
        # 3. 컨텍스트와 함께 답변 생성
        answer = await self.generate_with_context(question, context_docs)
        
        return {"answer": answer, "sources": context_docs}

# 📁 실제 파일 위치: backend/app/services/rag_service.py`
        }
      case 'postgresql':
        return {
          title: 'PostgreSQL 사용 이유',
          description: '강력한 관계형 데이터베이스와 확장성',
          code: `// PostgreSQL을 선택한 이유:
// 1. ACID 준수 - 데이터 일관성 보장
// 2. 확장성 - 다양한 데이터 타입 지원
// 3. 성능 - 복잡한 쿼리 최적화
// 4. 오픈소스 - 비용 효율성

// 실제 사용 예시: backend/app/models/user.py
from sqlmodel import SQLModel, Field
from typing import Optional

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True)
    email: str = Field(unique=True, index=True)
    role: str = Field(default="mentee")
    is_active: bool = Field(default=True)

# 📁 실제 파일 위치: backend/app/models/user.py`
        }
      case 'pgvector':
        return {
          title: 'pgvector 사용 이유',
          description: '벡터 검색을 위한 PostgreSQL 확장',
          code: `// pgvector를 선택한 이유:
// 1. 벡터 검색 - 임베딩 기반 유사도 검색
// 2. PostgreSQL 통합 - 기존 DB와 완벽 호환
// 3. 성능 - 인덱스 기반 빠른 검색
// 4. 확장성 - 대용량 벡터 데이터 처리

// 실제 사용 예시: backend/app/database.py
from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, Integer, String, Text

class Document(Base):
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    embedding = Column(Vector(1536))  # OpenAI embedding 차원

# 📁 실제 파일 위치: backend/app/database.py`
        }
      case 'redis':
        return {
          title: 'Redis 사용 이유',
          description: '고성능 인메모리 데이터 저장소',
          code: `// Redis를 선택한 이유:
// 1. 고성능 - 메모리 기반 빠른 접근
// 2. 캐싱 - 자주 사용되는 데이터 캐시
// 3. 세션 관리 - 사용자 세션 저장
// 4. 실시간 기능 - Pub/Sub 메시징

// 실제 사용 예시: backend/app/services/cache_service.py
import redis
import json
from typing import Optional, Any

class CacheService:
    def __init__(self):
        self.redis_client = redis.Redis(
            host='localhost',
            port=6379,
            db=0,
            decode_responses=True
        )
    
    async def get(self, key: str) -> Optional[Any]:
        value = self.redis_client.get(key)
        return json.loads(value) if value else None

# 📁 실제 파일 위치: backend/app/services/cache_service.py`
        }
      case 'docker-frontend':
        return {
          title: 'Docker Frontend Container 사용 이유',
          description: '일관된 개발 환경과 배포 간소화',
          code: `// Docker Frontend Container를 선택한 이유:
// 1. 환경 일관성 - 개발/테스트/운영 환경 통일
// 2. 의존성 관리 - Node.js, npm 패키지 격리
// 3. 확장성 - 컨테이너 오케스트레이션 지원
// 4. 배포 간소화 - 이미지 기반 배포

# 실제 사용 예시: frontend/Dockerfile
FROM node:18-alpine

WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production

COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=0 /app/dist /usr/share/nginx/html

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]

# 📁 실제 파일 위치: frontend/Dockerfile`
        }
      case 'docker-backend':
        return {
          title: 'Docker Backend Container 사용 이유',
          description: '마이크로서비스 아키텍처와 확장성',
          code: `// Docker Backend Container를 선택한 이유:
// 1. 마이크로서비스 - 독립적인 서비스 배포
// 2. 확장성 - 수평적 확장 지원
// 3. 의존성 격리 - Python 패키지 충돌 방지
// 4. 개발 효율성 - 로컬 개발 환경 구축 간소화

# 실제 사용 예시: backend/Dockerfile
FROM python:3.11-slim

WORKDIR /app

# 시스템 의존성 설치
RUN apt-get update && apt-get install -y \\
    gcc \\
    && rm -rf /var/lib/apt/lists/*

# Python 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 코드 복사
COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# 📁 실제 파일 위치: backend/Dockerfile`
        }
      case 'docker-database':
        return {
          title: 'Docker Database Container 사용 이유',
          description: '데이터베이스 환경 표준화와 관리 간소화',
          code: `// Docker Database Container를 선택한 이유:
// 1. 환경 표준화 - PostgreSQL, Redis 버전 통일
// 2. 데이터 격리 - 프로젝트별 독립적인 DB
// 3. 백업/복원 - 컨테이너 기반 데이터 관리
// 4. 개발 효율성 - 로컬 DB 설정 자동화

# 실제 사용 예시: docker-compose.yml
version: '3.8'

services:
  postgres:
    image: pgvector/pgvector:pg15
    environment:
      POSTGRES_DB: bank_mentor
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: password
    ports:
      - "5432:5432"

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

# 📁 실제 파일 위치: docker-compose.yml`
        }
      default:
        return {
          title: '기술 스택 정보',
          description: '선택된 기술에 대한 상세 정보',
          code: '// 해당 기술에 대한 정보를 준비 중입니다.'
        }
    }
  }

  const codeExample = getCodeExamples(techKey)

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className="bg-white rounded-2xl p-6 max-w-4xl w-full max-h-[90vh] overflow-hidden flex flex-col"
      >
        {/* 헤더 */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h3 className="text-2xl font-bold text-gray-900">{codeExample.title}</h3>
            <p className="text-gray-600 mt-1">{codeExample.description}</p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 transition-colors"
          >
            <XMarkIcon className="w-6 h-6" />
          </button>
        </div>

        {/* 코드 내용 */}
        <div className="flex-1 overflow-auto">
          <pre className="bg-gray-900 text-green-400 p-6 rounded-xl text-sm overflow-auto">
            <code>{codeExample.code}</code>
          </pre>
        </div>

        {/* 하단 버튼 */}
        <div className="mt-6 flex justify-end">
          <button
            onClick={onClose}
            className="px-6 py-2 bg-gray-200 text-gray-800 rounded-lg hover:bg-gray-300 transition-colors"
          >
            닫기
          </button>
        </div>
      </motion.div>
    </div>
  )
}

// Docker 아키텍처 다이어그램 컴포넌트
function DockerArchitectureDiagram({ onTechClick }: { onTechClick: (tech: string) => void }) {
  return (
    <div className="space-y-8">
      {/* Docker Host */}
      <div className="text-center">
        <div className="bg-gradient-to-r from-blue-500 to-blue-600 text-white rounded-2xl p-6 inline-block shadow-lg">
          <h3 className="text-xl font-bold mb-2">Docker Host</h3>
          <p className="text-blue-100">Ubuntu Server / Windows</p>
        </div>
      </div>

      {/* 화살표 */}
      <div className="flex justify-center">
        <div className="w-1 h-16 bg-gray-300"></div>
      </div>

      {/* Docker Containers */}
      <div className="grid md:grid-cols-2 gap-8">
        {/* Frontend Container */}
        <motion.div 
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          onClick={() => onTechClick('docker-frontend')}
          className="bg-gradient-to-r from-green-500 to-green-600 text-white rounded-xl p-6 shadow-lg cursor-pointer hover:shadow-xl transition-shadow"
        >
          <div className="flex items-center mb-4">
            <div className="w-8 h-8 bg-white/20 rounded-lg flex items-center justify-center mr-3">
              <span className="text-lg">🐳</span>
            </div>
            <h4 className="font-bold text-lg">Frontend Container</h4>
          </div>
          <div className="space-y-2 text-sm">
            <div className="bg-white/20 p-2 rounded">React App (Port 3000)</div>
            <div className="bg-white/20 p-2 rounded">Nginx (Static Files)</div>
            <div className="bg-white/20 p-2 rounded">Vite Dev Server</div>
          </div>
        </motion.div>

        {/* Backend Container */}
        <motion.div 
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          onClick={() => onTechClick('docker-backend')}
          className="bg-gradient-to-r from-orange-500 to-orange-600 text-white rounded-xl p-6 shadow-lg cursor-pointer hover:shadow-xl transition-shadow"
        >
          <div className="flex items-center mb-4">
            <div className="w-8 h-8 bg-white/20 rounded-lg flex items-center justify-center mr-3">
              <span className="text-lg">🐳</span>
            </div>
            <h4 className="font-bold text-lg">Backend Container</h4>
          </div>
          <div className="space-y-2 text-sm">
            <div className="bg-white/20 p-2 rounded">FastAPI Server (Port 8000)</div>
            <div className="bg-white/20 p-2 rounded">Python 3.11</div>
            <div className="bg-white/20 p-2 rounded">Uvicorn ASGI</div>
          </div>
        </motion.div>
      </div>

      {/* 화살표 */}
      <div className="flex justify-center">
        <div className="w-1 h-16 bg-gray-300"></div>
      </div>

      {/* Database Container */}
      <div className="text-center">
        <motion.div 
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          onClick={() => onTechClick('docker-database')}
          className="bg-gradient-to-r from-purple-500 to-purple-600 text-white rounded-xl p-6 inline-block shadow-lg max-w-md cursor-pointer hover:shadow-xl transition-shadow"
        >
          <div className="flex items-center justify-center mb-4">
            <div className="w-8 h-8 bg-white/20 rounded-lg flex items-center justify-center mr-3">
              <span className="text-lg">🐳</span>
            </div>
            <h4 className="font-bold text-lg">Database Container</h4>
          </div>
          <div className="space-y-2 text-sm">
            <div className="bg-white/20 p-2 rounded">PostgreSQL (Port 5432)</div>
            <div className="bg-white/20 p-2 rounded">pgvector Extension</div>
            <div className="bg-white/20 p-2 rounded">Redis (Port 6379)</div>
          </div>
        </motion.div>
      </div>

      {/* API 통신 구조 */}
      <div className="mt-12 pt-8 border-t border-gray-200">
        <h4 className="text-lg font-semibold text-gray-900 mb-6 text-center">API 통신 구조</h4>
        <div className="grid md:grid-cols-3 gap-6">
          <div className="bg-gray-50 rounded-xl p-4 text-center">
            <h5 className="font-semibold text-gray-800 mb-2">Frontend → Backend</h5>
            <p className="text-sm text-gray-600">HTTP/HTTPS API Calls</p>
            <p className="text-xs text-gray-500 mt-1">localhost:3000 → localhost:8000</p>
          </div>
          <div className="bg-gray-50 rounded-xl p-4 text-center">
            <h5 className="font-semibold text-gray-800 mb-2">Backend → Database</h5>
            <p className="text-sm text-gray-600">SQL Queries & Vector Search</p>
            <p className="text-xs text-gray-500 mt-1">FastAPI → PostgreSQL</p>
          </div>
          <div className="bg-gray-50 rounded-xl p-4 text-center">
            <h5 className="font-semibold text-gray-800 mb-2">Docker Compose</h5>
            <p className="text-sm text-gray-600">Container Orchestration</p>
            <p className="text-xs text-gray-500 mt-1">Multi-container Setup</p>
          </div>
        </div>
      </div>
    </div>
  )
}

// ERD 다이어그램 컴포넌트
function ERDDiagram() {
  return (
    <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
      {/* Users 테이블 */}
      <div className="bg-white border-2 border-blue-300 rounded-xl p-4 shadow-lg">
        <h4 className="font-bold text-blue-800 mb-3 text-center">Users</h4>
        <div className="space-y-1 text-sm">
          <div className="bg-blue-50 p-2 rounded">id (PK)</div>
          <div className="bg-blue-50 p-2 rounded">username</div>
          <div className="bg-blue-50 p-2 rounded">email</div>
          <div className="bg-blue-50 p-2 rounded">role</div>
          <div className="bg-blue-50 p-2 rounded">created_at</div>
        </div>
      </div>

      {/* Documents 테이블 */}
      <div className="bg-white border-2 border-green-300 rounded-xl p-4 shadow-lg">
        <h4 className="font-bold text-green-800 mb-3 text-center">Documents</h4>
        <div className="space-y-1 text-sm">
          <div className="bg-green-50 p-2 rounded">id (PK)</div>
          <div className="bg-green-50 p-2 rounded">title</div>
          <div className="bg-green-50 p-2 rounded">content</div>
          <div className="bg-green-50 p-2 rounded">embedding</div>
          <div className="bg-green-50 p-2 rounded">category</div>
        </div>
      </div>

      {/* Chat_Messages 테이블 */}
      <div className="bg-white border-2 border-purple-300 rounded-xl p-4 shadow-lg">
        <h4 className="font-bold text-purple-800 mb-3 text-center">Chat_Messages</h4>
        <div className="space-y-1 text-sm">
          <div className="bg-purple-50 p-2 rounded">id (PK)</div>
          <div className="bg-purple-50 p-2 rounded">user_id (FK)</div>
          <div className="bg-purple-50 p-2 rounded">message</div>
          <div className="bg-purple-50 p-2 rounded">response</div>
          <div className="bg-purple-50 p-2 rounded">timestamp</div>
        </div>
      </div>

      {/* Posts 테이블 */}
      <div className="bg-white border-2 border-amber-300 rounded-xl p-4 shadow-lg">
        <h4 className="font-bold text-amber-800 mb-3 text-center">Posts</h4>
        <div className="space-y-1 text-sm">
          <div className="bg-amber-50 p-2 rounded">id (PK)</div>
          <div className="bg-amber-50 p-2 rounded">title</div>
          <div className="bg-amber-50 p-2 rounded">content</div>
          <div className="bg-amber-50 p-2 rounded">anonymous</div>
          <div className="bg-amber-50 p-2 rounded">created_at</div>
        </div>
      </div>

      {/* Mentors 테이블 */}
      <div className="bg-white border-2 border-red-300 rounded-xl p-4 shadow-lg">
        <h4 className="font-bold text-red-800 mb-3 text-center">Mentors</h4>
        <div className="space-y-1 text-sm">
          <div className="bg-red-50 p-2 rounded">id (PK)</div>
          <div className="bg-red-50 p-2 rounded">user_id (FK)</div>
          <div className="bg-red-50 p-2 rounded">specialty</div>
          <div className="bg-red-50 p-2 rounded">experience</div>
          <div className="bg-red-50 p-2 rounded">rating</div>
        </div>
      </div>

      {/* Mentor_Mentee 테이블 */}
      <div className="bg-white border-2 border-indigo-300 rounded-xl p-4 shadow-lg">
        <h4 className="font-bold text-indigo-800 mb-3 text-center">Mentor_Mentee</h4>
        <div className="space-y-1 text-sm">
          <div className="bg-indigo-50 p-2 rounded">id (PK)</div>
          <div className="bg-indigo-50 p-2 rounded">mentor_id (FK)</div>
          <div className="bg-indigo-50 p-2 rounded">mentee_id (FK)</div>
          <div className="bg-indigo-50 p-2 rounded">status</div>
          <div className="bg-indigo-50 p-2 rounded">start_date</div>
        </div>
      </div>
    </div>
  )
}

// API 명세서 카드 컴포넌트
function APISpecCard({ title, description, endpoints, color }: any) {
  const colorClasses: any = {
    blue: 'border-blue-300 bg-blue-50',
    green: 'border-green-300 bg-green-50',
    purple: 'border-purple-300 bg-purple-50',
    amber: 'border-amber-300 bg-amber-50',
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      viewport={{ once: true }}
      className={`bg-white border-2 ${colorClasses[color]} rounded-2xl p-6 shadow-lg`}
    >
      <h3 className="text-lg font-bold text-gray-900 mb-2">{title}</h3>
      <p className="text-sm text-gray-600 mb-4">{description}</p>
      
      <div className="space-y-2">
        <h4 className="font-semibold text-gray-700 text-sm">Endpoints:</h4>
        {endpoints.map((endpoint: string, index: number) => (
          <div key={index} className="bg-white/50 p-2 rounded text-xs font-mono">
            {endpoint}
          </div>
        ))}
      </div>
    </motion.div>
  )
}

// 화면 설계 카드 컴포넌트
function ScreenDesignCard({ title, description, features }: any) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      viewport={{ once: true }}
      className="bg-white rounded-2xl p-6 shadow-lg hover:shadow-xl transition-shadow"
    >
      <h3 className="text-xl font-bold text-gray-900 mb-2">{title}</h3>
      <p className="text-gray-600 mb-4">{description}</p>
      
      <div className="space-y-2">
        <h4 className="font-semibold text-gray-700">주요 기능:</h4>
        {features.map((feature: string, index: number) => (
          <div key={index} className="flex items-center text-sm text-gray-600">
            <div className="w-1.5 h-1.5 bg-primary-500 rounded-full mr-2"></div>
            {feature}
          </div>
        ))}
      </div>
    </motion.div>
  )
}

// 구현 화면 컴포넌트
function ImplementationScreen({ title, description, features }: any) {
  return (
    <div className="bg-white rounded-3xl p-8 shadow-xl border border-gray-100">
      <div className="grid md:grid-cols-2 gap-8 items-center">
        <div>
          <h3 className="text-2xl font-bold text-gray-900 mb-4">{title}</h3>
          <p className="text-gray-600 mb-6">{description}</p>
          
          <div className="space-y-3">
            <h4 className="font-semibold text-gray-700">주요 기능:</h4>
            <ul className="space-y-2">
              {features.map((feature: string, index: number) => (
                <li key={index} className="flex items-center text-gray-600">
                  <div className="w-5 h-5 bg-green-500 rounded-full mr-3 flex-shrink-0"></div>
                  {feature}
                </li>
              ))}
            </ul>
          </div>
        </div>
        
        <div className="bg-gray-100 rounded-2xl p-4 text-center">
          <div className="bg-gray-200 rounded-xl h-64 flex items-center justify-center">
            <div className="text-gray-500">
              <div className="text-4xl mb-2">📱</div>
              <p className="text-sm">{title} 스크린샷</p>
              <p className="text-xs text-gray-400 mt-1">실제 구현 화면</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}