/**
 * 게시글 상세 페이지
 */
import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { postAPI } from '../utils/api'
import { useAuthStore } from '../store/authStore'
import { 
  ArrowLeftIcon,
  ChatBubbleLeftIcon,
  EyeIcon,
  ClockIcon,
  TrashIcon,
  PencilIcon,
  HandThumbUpIcon,
  HandThumbDownIcon
} from '@heroicons/react/24/outline'
import { 
  HandThumbUpIcon as HandThumbUpSolidIcon,
  HandThumbDownIcon as HandThumbDownSolidIcon
} from '@heroicons/react/24/solid'
import { motion } from 'framer-motion'

export default function PostDetail() {
  const { postId } = useParams<{ postId: string }>()
  const navigate = useNavigate()
  const { user } = useAuthStore()
  const [post, setPost] = useState<any>(null)
  const [comments, setComments] = useState<any[]>([])
  const [commentText, setCommentText] = useState('')
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [isAuthor, setIsAuthor] = useState(false)
  const [isAdmin, setIsAdmin] = useState(false)
  
  // 게시글 꿀추/꿀통 상태
  const [postLiked, setPostLiked] = useState(false)
  const [postDisliked, setPostDisliked] = useState(false)
  const [postLikeCount, setPostLikeCount] = useState(0)
  const [postDislikeCount, setPostDislikeCount] = useState(0)
  
  // 게시글 수정 모달
  const [isEditing, setIsEditing] = useState(false)
  const [editTitle, setEditTitle] = useState('')
  const [editContent, setEditContent] = useState('')
  
  // 댓글 수정
  const [editingCommentId, setEditingCommentId] = useState<number | null>(null)
  const [editCommentText, setEditCommentText] = useState('')
  
  // 조회수 중복 증가 방지
  const hasLoadedRef = useRef(false)

  useEffect(() => {
    if (postId && !hasLoadedRef.current) {
      hasLoadedRef.current = true
      loadPost()
    }
  }, [postId])

  const loadPost = async () => {
    try {
      setLoading(true)
      const data = await postAPI.getPost(Number(postId))
      console.log('Post data:', data) // 디버깅용 로그
      console.log('is_author:', data.is_author)
      console.log('is_admin:', data.is_admin)
      console.log('user role:', user?.role)
      setPost(data.post)
      setComments(data.comments || [])
      setIsAuthor(data.is_author || false)
      setIsAdmin(data.is_admin || false)
      
      // 게시글 꿀추/꿀통 상태 설정
      setPostLiked(data.post.user_liked || false)
      setPostDisliked(data.post.user_disliked || false)
      setPostLikeCount(data.post.like_count || 0)
      setPostDislikeCount(data.post.dislike_count || 0)
    } catch (error) {
      console.error('Failed to load post:', error)
      alert('게시글을 불러올 수 없습니다.')
      navigate('/board')
    } finally {
      setLoading(false)
    }
  }

  const handleSubmitComment = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!commentText.trim() || submitting) return

    setSubmitting(true)
    try {
      await postAPI.createComment(Number(postId), commentText)
      setCommentText('')
      loadPost()
    } catch (error) {
      console.error('Failed to create comment:', error)
      alert('댓글 작성에 실패했습니다.')
    } finally {
      setSubmitting(false)
    }
  }

  const handleKeyPress = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      e.stopPropagation()
      e.nativeEvent.stopImmediatePropagation()
      
      // 엔터키로 댓글 전송
      if (!submitting && commentText.trim()) {
        handleSubmitComment(e as any)
      }
      return false
    }
  }

  const handleDeletePost = async () => {
    if (!postId) return
    
    if (!window.confirm('정말로 이 글을 삭제하시겠습니까?')) {
      return
    }

    try {
      await postAPI.deletePost(Number(postId))
      alert('글이 삭제되었습니다.')
      navigate('/board')
    } catch (error) {
      console.error('Failed to delete post:', error)
      alert('글 삭제에 실패했습니다.')
    }
  }

  // 게시글 수정
  const handleEditPost = () => {
    setEditTitle(post.title)
    setEditContent(post.content)
    setIsEditing(true)
  }

  const handleSaveEdit = async () => {
    if (!editTitle.trim() || !editContent.trim()) {
      alert('제목과 내용을 입력해주세요.')
      return
    }

    try {
      await postAPI.updatePost(Number(postId), editTitle, editContent)
      alert('글이 수정되었습니다.')
      setIsEditing(false)
      loadPost() // 수정된 내용 다시 불러오기
    } catch (error) {
      console.error('Failed to update post:', error)
      alert('글 수정에 실패했습니다.')
    }
  }

  // 게시글 꿀추/꿀통
  const handlePostLike = async () => {
    try {
      if (postLiked) {
        await postAPI.unlikePost(Number(postId))
        setPostLiked(false)
        setPostLikeCount(prev => prev - 1)
      } else {
        await postAPI.likePost(Number(postId))
        setPostLiked(true)
        setPostLikeCount(prev => prev + 1)
        
        if (postDisliked) {
          setPostDisliked(false)
          setPostDislikeCount(prev => prev - 1)
        }
      }
    } catch (error) {
      console.error('Failed to toggle post like:', error)
    }
  }

  const handlePostDislike = async () => {
    try {
      if (postDisliked) {
        await postAPI.undislikePost(Number(postId))
        setPostDisliked(false)
        setPostDislikeCount(prev => prev - 1)
      } else {
        await postAPI.dislikePost(Number(postId))
        setPostDisliked(true)
        setPostDislikeCount(prev => prev + 1)
        
        if (postLiked) {
          setPostLiked(false)
          setPostLikeCount(prev => prev - 1)
        }
      }
    } catch (error) {
      console.error('Failed to toggle post dislike:', error)
    }
  }

  const handleDeleteComment = async (commentId: number) => {
    if (!window.confirm('정말로 이 댓글을 삭제하시겠습니까?')) {
      return
    }

    try {
      await postAPI.deleteComment(commentId)
      loadPost() // 댓글 목록 새로고침
    } catch (error) {
      console.error('Failed to delete comment:', error)
      alert('댓글 삭제에 실패했습니다.')
    }
  }

  // 댓글 수정 시작
  const handleEditComment = (comment: any) => {
    setEditingCommentId(comment.id)
    setEditCommentText(comment.content)
  }

  // 댓글 수정 저장
  const handleSaveCommentEdit = async (commentId: number) => {
    if (!editCommentText.trim()) {
      alert('댓글 내용을 입력해주세요.')
      return
    }

    try {
      await postAPI.updateComment(commentId, editCommentText)
      setEditingCommentId(null)
      setEditCommentText('')
      loadPost() // 댓글 목록 새로고침
    } catch (error) {
      console.error('Failed to update comment:', error)
      alert('댓글 수정에 실패했습니다.')
    }
  }

  // 댓글 수정 취소
  const handleCancelCommentEdit = () => {
    setEditingCommentId(null)
    setEditCommentText('')
  }

  const formatDate = (dateString: string) => {
    // UTC 시간 문자열을 로컬 시간으로 변환
    const date = new Date(dateString + (dateString.includes('Z') ? '' : 'Z'))
    return date.toLocaleString('ko-KR', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-green-600"></div>
      </div>
    )
  }

  if (!post) return null

  return (
    <div className="space-y-6">
      {/* Back Button */}
      <button
        onClick={() => navigate('/board')}
        className="flex items-center space-x-2 text-gray-600 hover:text-gray-900 transition-colors"
      >
        <ArrowLeftIcon className="w-5 h-5" />
        <span>목록으로</span>
      </button>

      {/* Post */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="bg-white rounded-xl shadow-md p-8"
      >
        <h1 className="text-3xl font-bold text-gray-900 mb-4">{post.title}</h1>
        
        <div className="flex items-center justify-between mb-6 pb-6 border-b">
          <div className="flex items-center space-x-4 text-sm text-gray-500">
          <span className="font-medium text-green-600">{post.author_alias}</span>
          <div className="flex items-center space-x-1">
            <ClockIcon className="w-4 h-4" />
            <span>{formatDate(post.created_at)}</span>
          </div>
          <div className="flex items-center space-x-1">
            <EyeIcon className="w-4 h-4" />
            <span>{post.view_count}</span>
          </div>
          <div className="flex items-center space-x-1">
            <ChatBubbleLeftIcon className="w-4 h-4" />
            <span>{post.comment_count}</span>
          </div>
        </div>

          {/* 수정/삭제 버튼 - 작성자 또는 관리자만 표시 */}
          {(isAuthor || isAdmin) && (
            <div className="flex items-center space-x-2">
              <button
                onClick={handleEditPost}
                className="flex items-center space-x-1 px-3 py-1 text-blue-600 hover:text-blue-700 hover:bg-blue-50 rounded-lg transition-colors"
                title="글 수정"
              >
                <PencilIcon className="w-4 h-4" />
                <span className="text-sm">수정</span>
              </button>
              <button
                onClick={handleDeletePost}
                className="flex items-center space-x-1 px-3 py-1 text-red-600 hover:text-red-700 hover:bg-red-50 rounded-lg transition-colors"
                title="글 삭제"
              >
                <TrashIcon className="w-4 h-4" />
                <span className="text-sm">삭제</span>
              </button>
            </div>
          )}
        </div>

        <div className="prose max-w-none mb-6">
          <p className="text-gray-700 whitespace-pre-wrap">{post.content}</p>
        </div>

        {/* 게시글 꿀추/꿀통 버튼 */}
        <div className="flex items-center space-x-4 pt-6 border-t border-gray-200">
          <button
            onClick={handlePostLike}
            className={`flex items-center space-x-1 px-4 py-2 rounded-full text-sm font-medium transition-all ${
              postLiked 
                ? 'bg-amber-100 text-amber-700 border border-amber-200' 
                : 'bg-gray-100 text-gray-600 hover:bg-amber-50 hover:text-amber-600'
            }`}
          >
            {postLiked ? (
              <HandThumbUpSolidIcon className="w-5 h-5" />
            ) : (
              <HandThumbUpIcon className="w-5 h-5" />
            )}
            <span>꿀추</span>
            <span className="text-xs">{postLikeCount}</span>
          </button>
          
          <button
            onClick={handlePostDislike}
            className={`flex items-center space-x-1 px-4 py-2 rounded-full text-sm font-medium transition-all ${
              postDisliked 
                ? 'bg-red-100 text-red-700 border border-red-200' 
                : 'bg-gray-100 text-gray-600 hover:bg-red-50 hover:text-red-600'
            }`}
          >
            {postDisliked ? (
              <HandThumbDownSolidIcon className="w-5 h-5" />
            ) : (
              <HandThumbDownIcon className="w-5 h-5" />
            )}
            <span>꿀통</span>
            <span className="text-xs">{postDislikeCount}</span>
          </button>
        </div>
      </motion.div>

      {/* 게시글 수정 모달 */}
      {isEditing && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="bg-white rounded-2xl p-8 max-w-2xl w-full"
          >
            <h2 className="text-2xl font-bold text-gray-900 mb-6">글 수정</h2>
            <div className="space-y-4">
              <div>
                <input
                  type="text"
                  value={editTitle}
                  onChange={(e) => setEditTitle(e.target.value)}
                  placeholder="제목을 입력하세요"
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent text-lg font-medium"
                />
              </div>
              <div>
                <textarea
                  value={editContent}
                  onChange={(e) => setEditContent(e.target.value)}
                  placeholder="내용을 입력하세요"
                  rows={10}
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent resize-none"
                />
              </div>
              <div className="flex space-x-3 pt-4">
                <button
                  type="button"
                  onClick={() => setIsEditing(false)}
                  className="flex-1 px-6 py-3 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors font-medium"
                >
                  취소
                </button>
                <button
                  onClick={handleSaveEdit}
                  className="flex-1 px-6 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors font-medium"
                >
                  수정하기
                </button>
              </div>
            </div>
          </motion.div>
        </div>
      )}

      {/* Comments */}
      <div className="bg-white rounded-xl shadow-md p-8">
        <h2 className="text-xl font-bold text-gray-900 mb-6">
          댓글 {comments.length}
        </h2>

        {/* Comment List */}
        <div className="space-y-4 mb-6">
          {comments.map((comment) => (
            <CommentItem 
              key={comment.id}
              comment={comment} 
              formatDate={formatDate}
              onDelete={handleDeleteComment}
              onEdit={handleEditComment}
              onSave={handleSaveCommentEdit}
              onCancel={handleCancelCommentEdit}
              isEditing={editingCommentId === comment.id}
              editText={editCommentText}
              onEditTextChange={setEditCommentText}
            />
          ))}
          {comments.length === 0 && (
            <p className="text-center text-gray-500 py-8">
              첫 댓글을 작성해보세요!
            </p>
          )}
        </div>

        {/* Comment Form */}
        <form onSubmit={handleSubmitComment} className="space-y-4">
          <textarea
            value={commentText}
            onChange={(e) => setCommentText(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="댓글을 입력하세요... (엔터로 전송, Shift+엔터로 줄바꿈)"
            rows={4}
            className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent resize-none"
          />
          <div className="flex justify-end">
            <button
              type="submit"
              disabled={submitting || !commentText.trim()}
              className="px-6 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {submitting ? '작성 중...' : '댓글 작성'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// 댓글 아이템 컴포넌트
function CommentItem({ 
  comment, 
  formatDate, 
  onDelete, 
  onEdit, 
  onSave, 
  onCancel,
  isEditing,
  editText,
  onEditTextChange 
}: any) {
  const [liked, setLiked] = useState(comment.user_liked || false)
  const [disliked, setDisliked] = useState(comment.user_disliked || false)
  const [likeCount, setLikeCount] = useState(comment.like_count || 0)
  const [dislikeCount, setDislikeCount] = useState(comment.dislike_count || 0)

  const handleLike = async (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    
    try {
      if (liked) {
        await postAPI.unlikeComment(comment.id)
        setLiked(false)
        setLikeCount(prev => prev - 1)
      } else {
        await postAPI.likeComment(comment.id)
        setLiked(true)
        setLikeCount(prev => prev + 1)
        
        if (disliked) {
          setDisliked(false)
          setDislikeCount(prev => prev - 1)
        }
      }
    } catch (error) {
      console.error('Failed to toggle comment like:', error)
    }
  }

  const handleDislike = async (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    
    try {
      if (disliked) {
        await postAPI.undislikeComment(comment.id)
        setDisliked(false)
        setDislikeCount(prev => prev - 1)
      } else {
        await postAPI.dislikeComment(comment.id)
        setDisliked(true)
        setDislikeCount(prev => prev + 1)
        
        if (liked) {
          setLiked(false)
          setLikeCount(prev => prev - 1)
        }
      }
    } catch (error) {
      console.error('Failed to toggle comment dislike:', error)
    }
  }

  return (
    <div className="p-4 bg-gray-50 rounded-lg">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center space-x-2">
          <span className="font-medium text-green-600">{comment.author_alias}</span>
          <span className="text-xs text-gray-500">{formatDate(comment.created_at)}</span>
        </div>
        
        {/* 댓글 수정/삭제 버튼 - 작성자 또는 관리자만 표시 */}
        {(comment.is_author || comment.is_admin) && !isEditing && (
          <div className="flex items-center space-x-1">
            <button
              onClick={() => onEdit(comment)}
              className="flex items-center space-x-1 px-2 py-1 text-blue-600 hover:text-blue-700 hover:bg-blue-50 rounded transition-colors"
              title="댓글 수정"
            >
              <PencilIcon className="w-3 h-3" />
              <span className="text-xs">수정</span>
            </button>
            <button
              onClick={() => onDelete(comment.id)}
              className="flex items-center space-x-1 px-2 py-1 text-red-600 hover:text-red-700 hover:bg-red-50 rounded transition-colors"
              title="댓글 삭제"
            >
              <TrashIcon className="w-3 h-3" />
              <span className="text-xs">삭제</span>
            </button>
          </div>
        )}
      </div>
      
      {isEditing ? (
        <div className="space-y-2">
          <textarea
            value={editText}
            onChange={(e) => onEditTextChange(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent resize-none"
            rows={3}
          />
          <div className="flex justify-end space-x-2">
            <button
              onClick={onCancel}
              className="px-3 py-1 text-sm text-gray-600 hover:text-gray-700 hover:bg-gray-100 rounded transition-colors"
            >
              취소
            </button>
            <button
              onClick={() => onSave(comment.id)}
              className="px-3 py-1 text-sm bg-green-600 text-white rounded hover:bg-green-700 transition-colors"
            >
              저장
            </button>
          </div>
        </div>
      ) : (
        <p className="text-gray-700 whitespace-pre-wrap mb-3">{comment.content}</p>
      )}
      
      {/* 댓글 꿀추/꿀통 버튼 */}
      <div className="flex items-center space-x-3">
        <button
          onClick={handleLike}
          className={`flex items-center space-x-1 px-2 py-1 rounded-full text-xs font-medium transition-all ${
            liked 
              ? 'bg-amber-100 text-amber-700 border border-amber-200' 
              : 'bg-gray-100 text-gray-600 hover:bg-amber-50 hover:text-amber-600'
          }`}
        >
          {liked ? (
            <HandThumbUpSolidIcon className="w-3 h-3" />
          ) : (
            <HandThumbUpIcon className="w-3 h-3" />
          )}
          <span>꿀추</span>
          <span className="text-xs">{likeCount}</span>
        </button>
        
        <button
          onClick={handleDislike}
          className={`flex items-center space-x-1 px-2 py-1 rounded-full text-xs font-medium transition-all ${
            disliked 
              ? 'bg-red-100 text-red-700 border border-red-200' 
              : 'bg-gray-100 text-gray-600 hover:bg-red-50 hover:text-red-600'
          }`}
        >
          {disliked ? (
            <HandThumbDownSolidIcon className="w-3 h-3" />
          ) : (
            <HandThumbDownIcon className="w-3 h-3" />
          )}
          <span>꿀통</span>
          <span className="text-xs">{dislikeCount}</span>
        </button>
      </div>
    </div>
  )
}

