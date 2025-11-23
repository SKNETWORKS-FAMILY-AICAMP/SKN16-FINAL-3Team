/**
 * 로그인 페이지
 */
import { useState, useEffect, useRef } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'
import { authAPI } from '../utils/api'
import { LockClosedIcon, QrCodeIcon } from '@heroicons/react/24/solid'
import { Html5Qrcode } from 'html5-qrcode'

export default function Login() {
  const [loginMode, setLoginMode] = useState<'normal' | 'qr'>('normal')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [qrScanning, setQrScanning] = useState(false)
  const [qrScanned, setQrScanned] = useState(false)
  const [showCapsWarning, setShowCapsWarning] = useState(false)
  const qrCodeRef = useRef<Html5Qrcode | null>(null)
  
  const { login } = useAuthStore()
  const navigate = useNavigate()

  // Caps Lock 감지 함수
  const checkCapsLock = (e: React.KeyboardEvent) => {
    const capsLockOn = e.getModifierState && e.getModifierState('CapsLock')
    setShowCapsWarning(capsLockOn)
  }

  useEffect(() => {
    if (loginMode === 'qr' && !qrScanned && !qrScanning) {
      setQrScanning(true)
      
      // DOM이 렌더링될 때까지 대기
      setTimeout(() => {
        const element = document.getElementById("qr-reader")
        if (!element) {
          console.error("qr-reader element not found")
          setQrScanning(false)
          return
        }
        
        const html5QrCode = new Html5Qrcode("qr-reader")
        qrCodeRef.current = html5QrCode
        
        html5QrCode.start(
          { facingMode: "environment" },
          {
            fps: 10,
            qrbox: { width: 250, height: 250 }
          },
          async (decodedText) => {
            // QR 코드 스캔 성공 - 바로 로그인 시도
            setQrScanning(false)
            setLoading(true)
            
            // 스캐너 중지
            if (qrCodeRef.current) {
              await qrCodeRef.current.stop().catch(() => {})
              qrCodeRef.current = null
            }
            
            try {
              // 1. QR 로그인 API 호출하여 토큰 받기
              const data = await authAPI.qrLogin(decodedText)
              
              // 2. 이메일 추출 (qr-login:email)
              const parts = decodedText.split(':', 2)
              const email = parts.length >= 2 ? parts[1] : ''
              
              // 3. 토큰을 먼저 임시로 스토어에 저장
              login(data.access_token, data.refresh_token, {
                id: 0,
                email: email,
                name: '',
                role: 'mentee' as any,
              })
              
              // 4. 사용자 정보 가져오기
              const userData = await authAPI.getCurrentUser()
              
              // 5. 완전한 사용자 정보로 업데이트
              login(data.access_token, data.refresh_token, userData)
              
              // 6. 홈으로 이동
              navigate('/home')
            } catch (err: any) {
              console.error('QR Login error:', err)
              let errorMessage = 'QR 로그인에 실패했습니다.'
              
              if (err.response?.data?.detail) {
                errorMessage = err.response.data.detail
              } else if (err.message) {
                errorMessage = err.message
              }
              
              setError(errorMessage)
              setLoading(false)
              setQrScanned(false)
            }
          },
          (errorMessage) => {
            // 스캔 실패는 무시 (계속 시도)
          }
        ).catch((err) => {
          console.error("QR Scanner error:", err)
          setError('카메라에 접근할 수 없습니다. 권한을 확인해주세요.')
          setQrScanning(false)
          qrCodeRef.current = null
        })
      }, 100) // DOM 렌더링 대기
    }

    return () => {
      // cleanup: 스캐너가 실행 중인 경우에만 중지
      if (qrCodeRef.current) {
        qrCodeRef.current.stop().catch(() => {})
        qrCodeRef.current = null
      }
    }
  }, [loginMode, qrScanned, qrScanning, login, navigate])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      // QR 스캐너가 실행 중이면 먼저 정리
      if (qrCodeRef.current && qrScanning) {
        await qrCodeRef.current.stop().catch(() => {})
        qrCodeRef.current = null
        setQrScanning(false)
      }

      // 1. 로그인 API 호출하여 토큰 받기
      const data = await authAPI.login(email, password)
      
      // 2. 토큰을 먼저 임시로 스토어에 저장 (API 인터셉터가 사용할 수 있도록)
      login(data.access_token, data.refresh_token, {
        id: 0,
        email: email,
        name: '',
        role: 'mentee' as any,
      })
      
      // 3. 이제 토큰이 저장되었으므로 사용자 정보 가져오기
      const userData = await authAPI.getCurrentUser()
      
      // 4. 완전한 사용자 정보로 업데이트
      login(data.access_token, data.refresh_token, userData)
      
      // 5. 홈으로 이동
      navigate('/home')
    } catch (err: any) {
      console.error('Login error:', err)
      let errorMessage = '로그인에 실패했습니다.'
      
      if (err.response?.status === 500) {
        // 500 에러인 경우 상세 메시지 표시
        if (err.response?.data?.detail) {
          errorMessage = `서버 오류: ${err.response.data.detail}`
        } else {
          errorMessage = '서버 내부 오류가 발생했습니다. 백엔드 로그를 확인해주세요.'
        }
      } else if (err.response?.data?.detail) {
        errorMessage = err.response.data.detail
      } else if (err.message) {
        errorMessage = err.message
      } else if (err.code === 'NETWORK_ERROR' || err.code === 'ECONNREFUSED') {
        errorMessage = '서버에 연결할 수 없습니다. 서버가 실행 중인지 확인해주세요.'
      }
      
      setError(errorMessage)
    } finally {
      setLoading(false)
    }
  }

  const switchToNormalLogin = () => {
    // QR 스캐너 정리
    if (qrCodeRef.current && qrScanning) {
      qrCodeRef.current.stop().catch(() => {})
      qrCodeRef.current = null
    }
    setLoginMode('normal')
    setEmail('')
    setPassword('')
    setQrScanned(false)
    setQrScanning(false)
    setError('')
  }

  const switchToQRLogin = () => {
    setLoginMode('qr')
    setEmail('')
    setPassword('')
    setQrScanned(false)
    setQrScanning(false)
    setError('')
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-primary-50 via-secondary-50 to-amber-50 px-4 py-8">
      <div className="max-w-md w-full">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="flex items-center justify-center mb-4">
            <img src="/assets/bear.png" alt="하경은행" className="w-16 h-16 mr-3 rounded-full shadow-lg" />
            <div className="text-left">
              <h2 className="text-3xl font-bold text-bank-800">하경은행</h2>
              <p className="text-primary-600 text-sm font-medium">온보딩 플랫폼</p>
            </div>
          </div>
          <h3 className="text-2xl font-semibold text-bank-800 mb-2">
            {loginMode === 'normal' ? '로그인' : 'QR 로그인'}
          </h3>
          <p className="text-primary-700">
            {loginMode === 'normal' ? '하경은행 온보딩 플랫폼에 오신 것을 환영합니다' : '사원증 QR 코드로 빠르게 로그인하세요'}
          </p>
        </div>

        {/* Login Mode Tabs */}
        <div className="flex gap-2 mb-6">
          <button
            onClick={switchToNormalLogin}
            className={`flex-1 py-3 rounded-xl font-semibold transition-all duration-200 ${
              loginMode === 'normal'
                ? 'bg-white text-primary-600 shadow-lg border-2 border-primary-200'
                : 'bg-white/50 text-primary-600 hover:bg-white/70 border-2 border-transparent'
            }`}
          >
            <LockClosedIcon className="w-5 h-5 inline mr-2" />
            일반 로그인
          </button>
          <button
            onClick={switchToQRLogin}
            className={`flex-1 py-3 rounded-xl font-semibold transition-all duration-200 ${
              loginMode === 'qr'
                ? 'bg-white text-primary-600 shadow-lg border-2 border-primary-200'
                : 'bg-white/50 text-primary-600 hover:bg-white/70 border-2 border-transparent'
            }`}
          >
            <QrCodeIcon className="w-5 h-5 inline mr-2" />
            사원증 QR 로그인
          </button>
        </div>

        {/* Login Form */}
        <div className="bg-white rounded-2xl shadow-xl p-8 border border-primary-100">
          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-600 text-sm">
              {error}
            </div>
          )}

          {loginMode === 'normal' ? (
            // 일반 로그인 폼
          <form onSubmit={handleSubmit} className="space-y-6">
            <div>
              <label htmlFor="username" className="block text-sm font-medium text-gray-700 mb-2">
                아이디 (이메일 또는 사번)
              </label>
              <input
                id="username"
                name="username"
                type="text"
                autoComplete="username"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full px-4 py-3 border border-primary-200 rounded-xl focus:ring-2 focus:ring-primary-500 focus:border-transparent bg-white/50"
                placeholder="your@email.com 또는 2023001"
              />
            </div>

            <div>
              <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-2">
                비밀번호
              </label>
              <input
                id="password"
                name="password"
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                onKeyDown={checkCapsLock}
                onKeyUp={checkCapsLock}
                className="w-full px-4 py-3 border border-primary-200 rounded-xl focus:ring-2 focus:ring-primary-500 focus:border-transparent bg-white/50"
                placeholder="••••••••"
              />
              {showCapsWarning && (
                <div className="mt-2 p-3 bg-amber-50 border border-amber-200 rounded-lg flex items-center space-x-2">
                  <div className="flex-shrink-0">
                    <svg className="w-5 h-5 text-amber-600" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                    </svg>
                  </div>
                  <div className="text-sm text-amber-800">
                    <strong>Caps Lock이 켜져 있습니다.</strong> 비밀번호가 대문자로 입력되고 있습니다.
                  </div>
                </div>
              )}
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 bg-gradient-to-r from-primary-600 to-primary-500 text-white rounded-xl font-semibold hover:from-primary-700 hover:to-primary-600 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed shadow-lg hover:shadow-xl"
            >
              {loading ? '로그인 중...' : '로그인'}
            </button>
          </form>
          ) : (
            // QR 로그인 폼
            <div className="space-y-6">
              {qrScanning && (
                <div>
                  <div className="text-center mb-4">
                    <p className="text-sm text-gray-600">
                      마이페이지에서 생성한 사원증 QR 코드를 스캔하세요
                    </p>
                    <p className="text-xs text-primary-600 mt-1 font-medium">
                      스캔 후 자동으로 로그인됩니다
                    </p>
                  </div>
                  <div id="qr-reader" className="rounded-lg overflow-hidden border-2 border-gray-200"></div>
                  <p className="text-center text-sm text-gray-500 mt-3">
                    카메라로 사원증 QR 코드를 비춰주세요...
                  </p>
                </div>
              )}

              {loading && !qrScanning && (
                <div className="flex flex-col items-center justify-center py-12">
                  <div className="animate-spin rounded-full h-16 w-16 border-b-2 border-primary-600 mb-4"></div>
                  <p className="text-primary-700 font-medium">로그인 중...</p>
                </div>
              )}
            </div>
          )}

          <div className="mt-6 text-center space-y-3">
            <div className="flex justify-center gap-4 text-sm">
              <Link to="/find-id" className="text-primary-600 hover:text-primary-700 font-medium">
                아이디 찾기
              </Link>
              <span className="text-primary-300">|</span>
              <Link to="/find-password" className="text-primary-600 hover:text-primary-700 font-medium">
                비밀번호 찾기
              </Link>
            </div>
            <p className="text-primary-700">
              계정이 없으신가요?{' '}
              <Link to="/register" className="text-primary-600 font-semibold hover:text-primary-700">
                회원가입
              </Link>
            </p>
          </div>
        </div>

      </div>
    </div>
  )
}
