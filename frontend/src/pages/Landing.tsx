/**
 * 랜딩 페이지
 * 로그인 전 프로젝트 소개
 */
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { 
  ChatBubbleLeftRightIcon, 
  DocumentTextIcon, 
  UserGroupIcon,
  ChartBarIcon,
  SparklesIcon,
  LockClosedIcon
} from '@heroicons/react/24/outline'

export default function Landing() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-primary-50 via-secondary-50 to-amber-50">
      {/* Hero Section */}
      <div className="relative overflow-hidden">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8 }}
            className="text-center"
          >
            {/* 하경은행 로고와 곰 캐릭터 */}
            <div className="flex justify-center items-center mb-8">
              <img 
                src="/assets/bear.png" 
                alt="하경은행 곰 캐릭터" 
                className="w-20 h-20 mr-4 rounded-full shadow-lg"
              />
              <div className="text-left">
                <h2 className="text-2xl font-bold text-bank-800">하경은행</h2>
                <p className="text-bank-600">Hakyung Bank</p>
              </div>
            </div>
            
            <h1 className="text-5xl md:text-6xl font-bold text-gray-900 mb-6">
              신입사원을 위한
              <br />
              <span className="bg-gradient-to-r from-primary-600 to-amber-500 bg-clip-text text-transparent">
                스마트 온보딩 플랫폼
              </span>
            </h1>
            <p className="text-xl text-gray-600 mb-8 max-w-2xl mx-auto">
              AI 기반 지능형 온보딩 시스템으로 빠르게 적응하세요.
              <br />
              체계적인 교육과 온보딩으로 성공적인 은행원의 첫걸음을 시작하세요.
            </p>
            <div className="flex justify-center space-x-4">
              <Link
                to="/register"
                className="px-8 py-3 bg-gradient-to-r from-primary-600 to-primary-500 text-white rounded-xl font-semibold hover:from-primary-700 hover:to-primary-600 transition-all duration-300 shadow-lg hover:shadow-xl transform hover:-translate-y-1"
              >
                온보딩 시작하기
              </Link>
              <Link
                to="/intro"
                className="px-8 py-3 bg-white text-primary-600 rounded-xl font-semibold hover:bg-primary-50 transition-all duration-300 border-2 border-primary-600 hover:border-primary-700 shadow-lg hover:shadow-xl"
              >
                프로젝트 소개
              </Link>
              <Link
                to="/login"
                className="px-8 py-3 bg-white text-primary-600 rounded-xl font-semibold hover:bg-primary-50 transition-all duration-300 border-2 border-primary-600 hover:border-primary-700 shadow-lg hover:shadow-xl"
              >
                로그인
              </Link>
            </div>
          </motion.div>

          {/* Floating Animation with Bear Character */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.5, duration: 1 }}
            className="mt-16 relative"
          >
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="w-96 h-96 bg-gradient-to-r from-primary-200 to-amber-200 rounded-full filter blur-3xl opacity-30 animate-pulse"></div>
            </div>
            <div className="relative bg-white rounded-3xl shadow-2xl p-8 max-w-4xl mx-auto border border-primary-100">
              <div className="flex items-center justify-center space-x-8">
                <div className="text-center">
                  <img
                    src="/assets/bear.png"
                    alt="하경은행 곰 캐릭터"
                    className="w-32 h-32 mx-auto mb-4 rounded-full shadow-lg"
                  />
                  <h3 className="text-xl font-bold text-primary-800">하경곰</h3>
                  <p className="text-primary-600">당신의 온보딩 파트너</p>
                </div>
                <div className="hidden md:block w-px h-32 bg-gradient-to-b from-primary-200 to-transparent"></div>
                <div className="text-center">
                  <div className="w-32 h-32 mx-auto mb-4 bg-gradient-to-br from-primary-100 to-amber-100 rounded-full flex items-center justify-center">
                    <span className="text-4xl">🏦</span>
                  </div>
                  <h3 className="text-xl font-bold text-bank-800">하경은행</h3>
                  <p className="text-bank-600">신뢰와 혁신의 은행</p>
                </div>
              </div>
            </div>
          </motion.div>
        </div>
      </div>

      {/* Features Section */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
        <div className="text-center mb-16">
          <h2 className="text-4xl font-bold text-gray-900 mb-4">
            스마트 온보딩 플랫폼의
            <span className="bg-gradient-to-r from-primary-600 to-amber-500 bg-clip-text text-transparent"> 핵심 기능</span>
          </h2>
          <p className="text-xl text-gray-600 max-w-2xl mx-auto">
            하경곰과 함께하는 체계적이고 효율적인 온보딩 경험을 제공합니다
          </p>
        </div>
        <div className="grid md:grid-cols-3 gap-8">
          <FeatureCard
            icon={ChatBubbleLeftRightIcon}
            title="AI 온보딩 어시스턴트"
            description="하경곰 AI가 24/7 궁금한 점을 해결하고 업무 가이드를 제공합니다."
            color="primary"
          />
          <FeatureCard
            icon={DocumentTextIcon}
            title="스마트 자료실"
            description="은행업무 관련 모든 문서와 학습 자료를 체계적으로 관리합니다."
            color="bank"
          />
          <FeatureCard
            icon={UserGroupIcon}
            title="개인별 온보딩 시스템"
            description="개인별 특성에 맞는 전담 가이드가 배정되어 맞춤형 온보딩을 지원합니다."
            color="amber"
          />
          <FeatureCard
            icon={LockClosedIcon}
            title="익명 소통 공간"
            description="부담 없이 질문하고 동료들과 소통할 수 있는 안전한 공간을 제공합니다."
            color="secondary"
          />
          <FeatureCard
            icon={ChartBarIcon}
            title="성장 트래킹"
            description="학습 진행도와 성과를 시각화하여 개인 성장을 체계적으로 관리합니다."
            color="accent"
          />
          <FeatureCard
            icon={SparklesIcon}
            title="맞춤형 학습 경로"
            description="개인별 학습 패턴을 분석하여 최적의 온보딩 경로를 제안합니다."
            color="primary"
          />
        </div>
      </div>

      {/* CTA Section */}
      <div className="bg-gradient-to-r from-primary-600 via-primary-500 to-amber-500 py-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <div className="flex justify-center mb-8">
            <img 
              src="/assets/bear.png" 
              alt="하경곰" 
              className="w-16 h-16 rounded-full shadow-lg"
            />
          </div>
          <h2 className="text-4xl font-bold text-white mb-4">
            하경곰과 함께 시작하는
            <br />
            성공적인 온보딩 여정
          </h2>
          <p className="text-white/90 mb-8 text-lg max-w-2xl mx-auto">
            하경은행 신입사원의 성공적인 시작을 위한 스마트 온보딩 플랫폼에 지금 참여하세요.
          </p>
          <Link
            to="/register"
            className="inline-block px-10 py-4 bg-white text-primary-600 rounded-xl font-bold hover:bg-gray-50 transition-all duration-300 shadow-xl hover:shadow-2xl transform hover:-translate-y-1"
          >
            🚀 온보딩 플랫폼 시작하기
          </Link>
        </div>
      </div>

      {/* Footer */}
      <footer className="bg-gradient-to-r from-bank-900 to-bank-800 text-white py-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col md:flex-row items-center justify-between">
            <div className="flex items-center mb-4 md:mb-0">
              <img 
                src="/assets/bear.png" 
                alt="하경은행 곰 캐릭터" 
                className="w-12 h-12 mr-3 rounded-full"
              />
              <div>
                <h3 className="text-xl font-bold">하경은행</h3>
                <p className="text-bank-300">스마트 온보딩 플랫폼</p>
              </div>
            </div>
            <div className="text-center md:text-right">
              <p className="text-bank-300 mb-2">© 2024 Hakyung Bank. All rights reserved.</p>
              <p className="text-bank-400 text-sm">신뢰와 혁신으로 함께하는 은행</p>
            </div>
          </div>
        </div>
      </footer>
    </div>
  )
}

function FeatureCard({ icon: Icon, title, description, color }: any) {
  const colorClasses: any = {
    primary: 'bg-primary-100 text-primary-600',
    bank: 'bg-bank-100 text-bank-600',
    amber: 'bg-amber-100 text-amber-600',
    secondary: 'bg-secondary-100 text-secondary-600',
    accent: 'bg-accent-100 text-accent-600',
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      viewport={{ once: true }}
      className="bg-white p-8 rounded-2xl shadow-lg hover:shadow-xl transition-all duration-300 border border-gray-100 hover:border-primary-200 group"
    >
      <div className={`w-14 h-14 rounded-xl ${colorClasses[color]} flex items-center justify-center mb-6 group-hover:scale-110 transition-transform duration-300`}>
        <Icon className="w-7 h-7" />
      </div>
      <h3 className="text-xl font-bold text-gray-900 mb-3 group-hover:text-primary-700 transition-colors">{title}</h3>
      <p className="text-gray-600 leading-relaxed">{description}</p>
    </motion.div>
  )
}



