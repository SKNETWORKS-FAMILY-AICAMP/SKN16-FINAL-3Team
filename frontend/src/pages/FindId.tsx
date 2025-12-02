/**
 * 아이디(이메일) 찾기 페이지
 */
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { authAPI } from '../utils/api'
import { UserIcon, IdentificationIcon } from '@heroicons/react/24/outline'
import FloatingInput from '../components/FloatingInput'
import AuthLinkGroup from '../components/AuthLinkGroup'

export default function FindId() {
  const [name, setName] = useState('')
  const [employeeNumber, setEmployeeNumber] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [foundEmail, setFoundEmail] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    setFoundEmail(null)

    try {
      const data = await authAPI.findId(name, employeeNumber)
      setFoundEmail(data.email)
    } catch (err: any) {
      console.error('Find ID error:', err)
      let errorMessage = '아이디 찾기에 실패했습니다.'
      
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

        {/* Find ID Form */}
        <div className="bg-white rounded-2xl shadow-xl p-8">
          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-600 text-sm">
              {error}
            </div>
          )}

          {foundEmail ? (
            <div className="space-y-4">
              <div className="p-4 bg-green-50 border border-green-200 rounded-lg">
                <p className="text-green-800 font-semibold mb-3">아이디를 찾았습니다!</p>
                <p className="text-xl font-mono font-semibold text-gray-900">{foundEmail}</p>
              </div>
              
              <div className="flex gap-3">
                <Link
                  to="/login"
                  className="flex-1 py-3 bg-primary-600 text-white rounded-lg font-semibold text-center hover:bg-primary-700 transition-colors"
                >
                  로그인하기
                </Link>
                <Link
                  to="/find-password"
                  className="flex-1 py-3 bg-gray-100 text-gray-700 rounded-lg font-semibold text-center hover:bg-gray-200 transition-colors"
                >
                  비밀번호 찾기
                </Link>
              </div>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-6">
              <FloatingInput
                label="이름"
                id="name"
                name="name"
                type="text"
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
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
                disabled={loading}
                className="w-full py-3 bg-primary-600 text-white rounded-lg font-semibold hover:bg-primary-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {loading ? '검색 중...' : '아이디 찾기'}
              </button>
            </form>
          )}

          <AuthLinkGroup
            className="mt-8"
            links={[
              { to: '/login', label: '로그인' },
              { to: '/find-password', label: '비밀번호 찾기' },
            ]}
          />
        </div>
      </div>
    </div>
  )
}

