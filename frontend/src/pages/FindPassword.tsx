/**
 * 비밀번호 찾기 페이지
 */
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { authAPI } from '../utils/api'
import { EyeIcon, EyeSlashIcon } from '@heroicons/react/24/outline'
import FloatingInput from '../components/FloatingInput'

export default function FindPassword() {
  const [step, setStep] = useState<'verify' | 'reset' | 'success'>('verify')
  
  // Step 1: 본인 확인
  const [email, setEmail] = useState('')
  const [employeeNumber, setEmployeeNumber] = useState('')
  
  // Step 2: 새 비밀번호 설정
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [showConfirmPassword, setShowConfirmPassword] = useState(false)
  
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleVerify = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    
    if (!email || !employeeNumber) {
      setError('이메일과 사원번호를 모두 입력해주세요.')
      return
    }
    
    // 다음 단계로 이동 (본인 확인은 비밀번호 재설정 시 함께 처리)
    setStep('reset')
  }

  const handleResetPassword = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    // 비밀번호 검증
    if (newPassword.length < 6) {
      setError('비밀번호는 최소 6자 이상이어야 합니다.')
      setLoading(false)
      return
    }

    if (newPassword !== confirmPassword) {
      setError('비밀번호가 일치하지 않습니다.')
      setLoading(false)
      return
    }

    try {
      await authAPI.resetPassword(email, employeeNumber, newPassword)
      setStep('success')
    } catch (err: any) {
      console.error('Reset password error:', err)
      let errorMessage = '비밀번호 재설정에 실패했습니다.'
      
      if (err.response?.data?.detail) {
        if (err.response.data.detail === 'User not found with provided information') {
          errorMessage = '입력하신 정보와 일치하는 사용자를 찾을 수 없습니다.'
        } else {
          errorMessage = err.response.data.detail
        }
      } else if (err.message) {
        errorMessage = err.message
      }
      
      setError(errorMessage)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-primary-50 via-secondary-50 to-amber-50 px-4 py-8">
      <div className="max-w-md w-full">
        <div className="mb-8" />

        {/* Form */}
        <div className="bg-white rounded-2xl shadow-xl p-8">
          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-600 text-sm">
              {error}
            </div>
          )}

          {/* Step 1: 본인 확인 */}
          {step === 'verify' && (
            <form onSubmit={handleVerify} className="space-y-6">
              <FloatingInput
                label="이메일"
                id="email"
                name="email"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />

              <FloatingInput
                label="사원번호"
                id="employee_number"
                name="employee_number"
                type="text"
                required
                value={employeeNumber}
                onChange={(e) => setEmployeeNumber(e.target.value)}
              />

              <button
                type="submit"
                className="w-full py-3 bg-primary-600 text-white rounded-lg font-semibold hover:bg-primary-700 transition-colors"
              >
                비밀번호 찾기
              </button>
            </form>
          )}

          {/* Step 2: 새 비밀번호 설정 */}
          {step === 'reset' && (
            <form onSubmit={handleResetPassword} className="space-y-6">
              <FloatingInput
                label="새 비밀번호"
                id="new_password"
                name="new_password"
                type={showPassword ? 'text' : 'password'}
                required
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                helperText="최소 6자 이상 입력하세요."
                rightElement={
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="rounded-lg p-2 text-gray-500 hover:bg-gray-100 hover:text-primary-600 transition-colors"
                  >
                    {showPassword ? (
                      <EyeSlashIcon className="w-5 h-5" />
                    ) : (
                      <EyeIcon className="w-5 h-5" />
                    )}
                  </button>
                }
              />

              <FloatingInput
                label="비밀번호 확인"
                id="confirm_password"
                name="confirm_password"
                type={showConfirmPassword ? 'text' : 'password'}
                required
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                rightElement={
                  <button
                    type="button"
                    onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                    className="rounded-lg p-2 text-gray-500 hover:bg-gray-100 hover:text-primary-600 transition-colors"
                  >
                    {showConfirmPassword ? (
                      <EyeSlashIcon className="w-5 h-5" />
                    ) : (
                      <EyeIcon className="w-5 h-5" />
                    )}
                  </button>
                }
              />

              <div className="flex gap-3">
                <button
                  type="button"
                  onClick={() => setStep('verify')}
                  className="flex-1 py-3 bg-gray-100 text-gray-700 rounded-lg font-semibold hover:bg-gray-200 transition-colors"
                >
                  이전
                </button>
                <button
                  type="submit"
                  disabled={loading}
                  className="flex-1 py-3 bg-primary-600 text-white rounded-lg font-semibold hover:bg-primary-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {loading ? '처리 중...' : '비밀번호 변경'}
                </button>
              </div>
            </form>
          )}

          {/* Success Message */}
          {step === 'success' && (
            <div className="space-y-4">
              <div className="p-4 bg-green-50 border border-green-200 rounded-lg text-center">
                <p className="text-green-800 font-semibold mb-2">✓ 비밀번호가 변경되었습니다!</p>
                <p className="text-sm text-gray-600">새 비밀번호로 로그인해주세요.</p>
              </div>
              
              <Link
                to="/login"
                className="block w-full py-3 bg-primary-600 text-white rounded-lg font-semibold text-center hover:bg-primary-700 transition-colors"
              >
                로그인하기
              </Link>
            </div>
          )}

          {step !== 'success' && (
            <div className="mt-6 space-y-3">
              <Link
                to="/login"
                className="block w-full py-3 text-sm font-semibold text-gray-700 bg-gray-50 border border-gray-200 rounded-lg text-center hover:bg-gray-100 hover:text-primary-600 transition-colors"
              >
                로그인으로 돌아가기
              </Link>
              <Link
                to="/find-id"
                className="block w-full py-3 text-sm font-semibold text-gray-700 bg-gray-50 border border-gray-200 rounded-lg text-center hover:bg-gray-100 hover:text-primary-600 transition-colors"
              >
                아이디 찾기
              </Link>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
