/**
 * 동아리 게시판 (멘토-멘티 커뮤니티) 페이지
 */
import { useState, useEffect } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { postAPI } from '../utils/api'
import { 
  PlusIcon, 
  ChatBubbleLeftIcon,
  EyeIcon,
  ClockIcon
} from '@heroicons/react/24/outline'
import { motion } from 'framer-motion'

const CATEGORY_OPTIONS = ['스포츠', '영화', '맛집', '음악', '게임', '여행', '독서', '예술', '기타'] as const

export default function AnonymousBoard() {
  const [searchParams] = useSearchParams()
  const [posts, setPosts] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [createModalOpen, setCreateModalOpen] = useState(false)
  const [selectedCategory, setSelectedCategory] = useState<string>('전체')

  useEffect(() => {
    loadPosts()
    
    // URL 파라미터에서 category 읽기
    const categoryFromUrl = searchParams.get('category')
    if (categoryFromUrl && CATEGORY_OPTIONS.includes(categoryFromUrl as any)) {
      setSelectedCategory(categoryFromUrl)
    }
  }, [searchParams])

  const loadPosts = async () => {
    try {
      setLoading(true)
      setError(null)
      console.log('Loading posts...')
      const data = await postAPI.getPosts()
      console.log('Posts loaded successfully:', data)
      setPosts(data)
    } catch (error) {
      console.error('Failed to load posts:', error)
      console.error('Error details:', {
        message: error.message,
        status: error.response?.status,
        statusText: error.response?.statusText,
        data: error.response?.data
      })
      setError(`게시글을 불러올 수 없습니다. (${error.response?.status || 'Unknown'}) 로그인 상태를 확인해주세요.`)
    } finally {
      setLoading(false)
    }
  }

  const formatDate = (dateString: string) => {
    // UTC 시간 문자열을 로컬 시간으로 변환
    const date = new Date(dateString + (dateString.includes('Z') ? '' : 'Z'))
    const now = new Date()
    const diff = now.getTime() - date.getTime()
    const minutes = Math.floor(diff / 60000)
    const hours = Math.floor(minutes / 60)
    const days = Math.floor(hours / 24)

    if (minutes < 1) return '방금 전'
    if (minutes < 60) return `${minutes}분 전`
    if (hours < 24) return `${hours}시간 전`
    if (days < 7) return `${days}일 전`
    return date.toLocaleDateString('ko-KR')
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">동아리 라운지 🎉</h1>
          <p className="text-gray-600 mt-1">멘토·멘티가 취미를 공유하며 친해지는 커뮤니티 공간입니다</p>
        </div>
        <button
          onClick={() => setCreateModalOpen(true)}
          className="flex items-center space-x-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors"
        >
          <PlusIcon className="w-5 h-5" />
          <span>글쓰기</span>
        </button>
      </div>

      {/* Notice */}
      <div className="bg-indigo-50 border border-indigo-200 rounded-xl p-4">
        <p className="text-indigo-900 text-sm">
          ✨ 취미와 관심사를 공유하며 서로를 알아가 보세요. 멘토·멘티 모두가 편안하게 참여할 수 있도록 따뜻한 피드백을 남겨주세요.
        </p>
      </div>

      {/* Posts List */}
      {loading ? (
        <div className="flex justify-center items-center h-64">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-green-600"></div>
        </div>
      ) : error ? (
        <div className="text-center py-12 bg-red-50 border border-red-200 rounded-xl">
          <p className="text-red-600 mb-4">{error}</p>
          <button
            onClick={loadPosts}
            className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
          >
            다시 시도
          </button>
        </div>
      ) : posts.length === 0 ? (
        <div className="text-center py-12 bg-white rounded-xl">
          <p className="text-gray-600">아직 게시글이 없습니다. 첫 글을 작성해보세요!</p>
        </div>
      ) : (
        <>
          {/* Category Filter */}
          <div className="flex flex-wrap gap-2 mb-4">
            <button
              onClick={() => setSelectedCategory('전체')}
              className={`px-4 py-2 rounded-lg transition-colors ${
                selectedCategory === '전체'
                  ? 'bg-indigo-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              전체
            </button>
            {CATEGORY_OPTIONS.map((category) => (
              <button
                key={category}
                onClick={() => setSelectedCategory(category)}
                className={`px-4 py-2 rounded-lg transition-colors ${
                  selectedCategory === category
                    ? 'bg-indigo-600 text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                {category}
              </button>
            ))}
          </div>

          <div className="grid gap-6 sm:grid-cols-2 xl:grid-cols-4">
            {posts
              .filter((post) => selectedCategory === '전체' || post.category === selectedCategory)
              .map((post, index) => (
                <PostCard key={post.id} post={post} formatDate={formatDate} index={index} />
              ))}
          </div>
        </>
      )}

      {/* Create Modal */}
      {createModalOpen && (
        <CreatePostModal
          onClose={() => setCreateModalOpen(false)}
          onSuccess={() => {
            setCreateModalOpen(false)
            loadPosts()
          }}
        />
      )}
    </div>
  )
}

function PostCard({ post, formatDate, index }: any) {
  return (
    <Link to={`/board/${post.id}`}>
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: index * 0.03 }}
        whileHover={{ translateY: -4 }}
        className="bg-white rounded-2xl shadow-md p-6 hover:shadow-xl transition-all cursor-pointer flex flex-col h-full"
      >
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center px-3 py-1 rounded-full bg-indigo-100 text-indigo-700 text-xs font-semibold">
              {post.category || '기타'}
            </span>
            {post.subcategory && (
              <span className="inline-flex items-center px-3 py-1 rounded-full bg-indigo-50 text-indigo-500 text-xs font-semibold border border-indigo-100">
                #{post.subcategory}
              </span>
            )}
          </div>
          <span className="text-xs text-gray-500">{formatDate(post.created_at)}</span>
        </div>

        <div className="flex-1">
          <h3 className="text-lg font-semibold text-gray-900 mb-2 line-clamp-2 min-h-[3.5rem]">
            {post.title}
          </h3>
          <p className="text-gray-600 mb-4 line-clamp-3 leading-relaxed">
            {post.content}
          </p>
        </div>

        <div className="flex items-center justify-between text-sm text-gray-500 mt-auto pt-2 border-t border-gray-100">
          <div className="text-indigo-600 font-medium">
            {post.comment_count}
          </div>
          <div className="flex items-center space-x-2">
            <div className="inline-flex items-center px-3 py-1 rounded-full bg-gray-100 text-gray-600 text-xs font-medium border border-gray-200">
              {post.author_name || post.author_alias?.split(' • ')[0] || '알 수 없음'}
            </div>
            <div className="inline-flex items-center px-3 py-1 rounded-full bg-gray-100 text-gray-600 text-xs font-medium border border-gray-200">
              {post.author_role_label || post.author_alias?.split(' • ')[1] || '역할 미정'}
            </div>
            <span className="h-1 w-1 rounded-full bg-gray-300" />
            <div className="flex items-center space-x-1">
              <EyeIcon className="w-4 h-4 text-gray-400" />
              <span>{post.view_count}</span>
            </div>
          </div>
        </div>
      </motion.div>
    </Link>
  )
}

function CreatePostModal({ onClose, onSuccess }: any) {
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const [category, setCategory] = useState<string>(CATEGORY_OPTIONS[0])
  const [subcategory, setSubcategory] = useState<string>('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!title.trim() || !content.trim()) return

    setLoading(true)
    try {
      await postAPI.createPost(title, content, category, subcategory)
      onSuccess()
    } catch (error) {
      console.error('Failed to create post:', error)
      alert('글 작성에 실패했습니다.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className="bg-white rounded-2xl p-8 max-w-2xl w-full"
      >
        <h2 className="text-2xl font-bold text-gray-900 mb-6">글쓰기 (익명)</h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <input
              type="text"
              required
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="제목을 입력하세요"
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent text-lg font-medium"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              카테고리
            </label>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent text-sm font-medium bg-white"
            >
              {CATEGORY_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              세부 카테고리 (예: #테니스)
            </label>
            <input
              type="text"
              value={subcategory}
              onChange={(e) => setSubcategory(e.target.value)}
              placeholder="#테니스"
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent text-sm"
              maxLength={50}
            />
          </div>
          <div>
            <textarea
              required
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder="내용을 입력하세요"
              rows={10}
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent resize-none"
            />
          </div>
          <div className="flex space-x-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-6 py-3 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors font-medium"
            >
              취소
            </button>
            <button
              type="submit"
              disabled={loading}
              className="flex-1 px-6 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors disabled:opacity-50 font-medium"
            >
              {loading ? '작성 중...' : '작성하기'}
            </button>
          </div>
        </form>
      </motion.div>
    </div>
  )
}



