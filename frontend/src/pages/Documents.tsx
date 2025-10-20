/**
 * 자료실 페이지
 */
import { useState, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'
import { documentAPI } from '../utils/api'
import { 
  DocumentTextIcon, 
  ArrowDownTrayIcon, 
  PlusIcon,
  MagnifyingGlassIcon,
  FolderIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  TrashIcon,
  ExclamationTriangleIcon
} from '@heroicons/react/24/outline'
import { motion } from 'framer-motion'

// 카테고리별 배지 색상 클래스 맵
const categoryBadgeClasses: Record<string, { dot: string; text: string; bg: string }> = {
  '일반': { dot: 'bg-gray-400', text: 'text-gray-700', bg: 'bg-gray-100' },
  '법규': { dot: 'bg-red-500', text: 'text-red-700', bg: 'bg-red-50' },
  '상품설명서': { dot: 'bg-amber-500', text: 'text-amber-700', bg: 'bg-amber-50' },
  '서식': { dot: 'bg-indigo-500', text: 'text-indigo-700', bg: 'bg-indigo-50' },
  '약관': { dot: 'bg-emerald-500', text: 'text-emerald-700', bg: 'bg-emerald-50' },
  'FAQ': { dot: 'bg-blue-500', text: 'text-blue-700', bg: 'bg-blue-50' },
  'RAG': { dot: 'bg-purple-500', text: 'text-purple-700', bg: 'bg-purple-50' },
}

function getCategoryStyles(category: string) {
  return categoryBadgeClasses[category] || { dot: 'bg-gray-300', text: 'text-gray-700', bg: 'bg-gray-100' }
}

export default function Documents() {
  const { user } = useAuthStore()
  const [searchParams] = useSearchParams()
  const [documents, setDocuments] = useState<any[]>([])
  const [categories, setCategories] = useState<string[]>([])
  const [selectedCategory, setSelectedCategory] = useState<string>('')
  const [searchTerm, setSearchTerm] = useState('')
  const [loading, setLoading] = useState(true)
  const [uploadModalOpen, setUploadModalOpen] = useState(false)
  const [currentPage, setCurrentPage] = useState(1)
  const itemsPerPage = 10
  const [deleteModalOpen, setDeleteModalOpen] = useState(false)
  const [documentToDelete, setDocumentToDelete] = useState<any>(null)
  const [deleting, setDeleting] = useState(false)

  // URL 파라미터에서 검색어 읽기
  useEffect(() => {
    const searchQuery = searchParams.get('search')
    if (searchQuery) {
      setSearchTerm(searchQuery)
    }
  }, [searchParams])

  useEffect(() => {
    loadDocuments()
    loadCategories()
    setCurrentPage(1) // 카테고리 변경 시 첫 페이지로 리셋
  }, [selectedCategory])

  useEffect(() => {
    setCurrentPage(1) // 검색어 변경 시 첫 페이지로 리셋
  }, [searchTerm])

  const loadDocuments = async () => {
    try {
      setLoading(true)
      const data = await documentAPI.getDocuments(selectedCategory || undefined)
      setDocuments(data)
    } catch (error) {
      console.error('Failed to load documents:', error)
    } finally {
      setLoading(false)
    }
  }

  const loadCategories = async () => {
    try {
      const data = await documentAPI.getCategories()
      setCategories(data.categories)
    } catch (error) {
      console.error('Failed to load categories:', error)
    }
  }

  const handleDownload = async (id: number, title: string) => {
    try {
      const blob = await documentAPI.downloadDocument(id)
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = title
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
    } catch (error) {
      console.error('Download failed:', error)
      alert('다운로드에 실패했습니다.')
    }
  }

  const handlePageChange = (page: number) => {
    setCurrentPage(page)
  }

  const handleDelete = (document: any) => {
    setDocumentToDelete(document)
    setDeleteModalOpen(true)
  }

  const confirmDelete = async () => {
    if (!documentToDelete) return

    setDeleting(true)
    try {
      await documentAPI.deleteDocument(documentToDelete.id)
      setDeleteModalOpen(false)
      setDocumentToDelete(null)
      loadDocuments() // 문서 목록 새로고침
    } catch (error) {
      console.error('Delete failed:', error)
      alert('삭제에 실패했습니다.')
    } finally {
      setDeleting(false)
    }
  }

  const filteredDocuments = documents.filter((doc) =>
    doc.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
    doc.description?.toLowerCase().includes(searchTerm.toLowerCase())
  )

  // 페이지네이션 계산
  const totalPages = Math.ceil(filteredDocuments.length / itemsPerPage)
  const startIndex = (currentPage - 1) * itemsPerPage
  const endIndex = startIndex + itemsPerPage
  const currentDocuments = filteredDocuments.slice(startIndex, endIndex)

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">자료실</h1>
          <p className="text-gray-600 mt-1">업무에 필요한 모든 자료를 찾아보세요</p>
        </div>
        {user?.role === 'admin' && (
          <button
            onClick={() => setUploadModalOpen(true)}
            className="flex items-center space-x-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors"
          >
            <PlusIcon className="w-5 h-5" />
            <span>문서 업로드</span>
          </button>
        )}
      </div>

      {/* Search and Filter */}
      <div className="bg-white rounded-xl shadow-md p-6">
        <div className="grid md:grid-cols-2 gap-4">
          {/* Search */}
          <div className="relative">
            <MagnifyingGlassIcon className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
            <input
              type="text"
              placeholder="문서 검색..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            />
          </div>

          {/* Category Filter */}
          <select
            value={selectedCategory}
            onChange={(e) => setSelectedCategory(e.target.value)}
            className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
          >
            <option value="">전체 카테고리</option>
            {categories.map((cat) => (
              <option key={cat} value={cat}>
                {cat}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Documents List */}
      {loading ? (
        <div className="flex justify-center items-center h-64">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
        </div>
      ) : (
        <div className="bg-white rounded-xl shadow-md overflow-hidden">
          {filteredDocuments.length === 0 ? (
            <div className="text-center py-12">
              <FolderIcon className="w-16 h-16 mx-auto text-gray-400 mb-4" />
              <p className="text-gray-600">문서가 없습니다</p>
            </div>
          ) : (
            <div className="divide-y divide-gray-200">
              {currentDocuments.map((doc) => (
                <DocumentListItem
                  key={doc.id}
                  document={doc}
                  onDownload={handleDownload}
                  onDelete={handleDelete}
                  user={user}
                />
              ))}
            </div>
          )}
        </div>
      )}

      {/* Pagination */}
      {filteredDocuments.length > itemsPerPage && (
        <Pagination
          currentPage={currentPage}
          totalPages={totalPages}
          onPageChange={handlePageChange}
        />
      )}

      {/* Upload Modal */}
      {uploadModalOpen && (
        <UploadModal
          categories={categories}
          onClose={() => setUploadModalOpen(false)}
          onSuccess={() => {
            setUploadModalOpen(false)
            loadDocuments()
          }}
        />
      )}

      {/* Delete Confirmation Modal */}
      {deleteModalOpen && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="bg-white rounded-xl p-6 max-w-md w-full"
          >
            <div className="flex items-center space-x-3 mb-4">
              <div className="flex-shrink-0">
                <ExclamationTriangleIcon className="w-8 h-8 text-red-600" />
              </div>
              <div>
                <h3 className="text-lg font-semibold text-gray-900">문서 삭제 확인</h3>
                <p className="text-sm text-gray-500">이 작업은 되돌릴 수 없습니다</p>
              </div>
            </div>
            
            <div className="mb-6">
              <p className="text-gray-700 mb-2">
                정말로 <span className="font-semibold text-red-600">"{documentToDelete?.title}"</span> 문서를 삭제하시겠습니까?
              </p>
              <p className="text-sm text-red-600 font-medium">
                ⚠️ 파일과 관련 데이터가 영구적으로 삭제됩니다.
              </p>
            </div>
            
            <div className="flex space-x-3">
              <button
                onClick={() => {
                  setDeleteModalOpen(false)
                  setDocumentToDelete(null)
                }}
                className="flex-1 px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors"
              >
                취소
              </button>
              <button
                onClick={confirmDelete}
                disabled={deleting}
                className="flex-1 px-4 py-2 text-sm font-medium text-white bg-red-600 rounded-lg hover:bg-red-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {deleting ? '삭제 중...' : '삭제하기'}
              </button>
            </div>
          </motion.div>
        </div>
      )}
    </div>
  )
}

function DocumentListItem({ document, onDownload, onDelete, user }: any) {
  const styles = getCategoryStyles(document.category)
  return (
    <motion.div
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      className="p-6 hover:bg-gray-50 transition-colors"
    >
      <div className="flex items-center space-x-6">
        {/* 문서 아이콘 */}
        <div className="w-10 h-10 bg-primary-100 rounded-lg flex items-center justify-center flex-shrink-0">
          <DocumentTextIcon className="w-5 h-5 text-primary-600" />
        </div>
        
        {/* 제목 */}
        <div className="flex-shrink-0 w-48">
          <h3 className="font-semibold text-gray-900 truncate">{document.title}</h3>
        </div>
        
        {/* 설명 */}
        <div className="flex-1 min-w-0">
          {document.description ? (
            <p className="text-sm text-gray-500 truncate">{document.description}</p>
          ) : (
            <p className="text-sm text-gray-400">설명 없음</p>
          )}
        </div>
        
        {/* 카테고리 */}
        <div className="flex-shrink-0 w-36">
          <span className={`inline-flex items-center space-x-2 text-sm px-2.5 py-1 rounded-full ${styles.bg} ${styles.text}`}>
            <span className={`w-2 h-2 rounded-full ${styles.dot}`}></span>
            <span className="truncate">{document.category}</span>
          </span>
        </div>
        
        {/* 다운로드 수 */}
        <div className="flex-shrink-0 w-20 text-center">
          <span className="text-sm text-gray-600">{document.download_count}</span>
        </div>
        
        {/* 버튼들 */}
        <div className="flex-shrink-0 flex items-center space-x-2">
          {/* 다운로드 버튼 */}
          <button
            onClick={() => onDownload(document.id, document.title + document.file_type)}
            className="flex items-center space-x-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors"
          >
            <ArrowDownTrayIcon className="w-4 h-4" />
            <span>다운로드</span>
          </button>
          
          {/* 삭제 버튼 (관리자만) */}
          {user?.role === 'admin' && (
            <button
              onClick={() => onDelete(document)}
              className="flex items-center space-x-2 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
              title="문서 삭제"
            >
              <TrashIcon className="w-4 h-4" />
              <span>삭제</span>
            </button>
          )}
        </div>
      </div>
    </motion.div>
  )
}

function UploadModal({ categories, onClose, onSuccess }: any) {
  const [files, setFiles] = useState<File[]>([])
  const [file, setFile] = useState<File | null>(null)
  const [title, setTitle] = useState('')
  const [category, setCategory] = useState('')
  const [description, setDescription] = useState('')
  const [loading, setLoading] = useState(false)

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = Array.from(e.target.files || [])
    setFiles(selected)
    setFile(selected[0] || null)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!category) return

    setLoading(true)
    try {
      if (files.length > 1) {
        // 다중 업로드 (제목은 파일명 자동 사용)
        await documentAPI.uploadDocumentsBulk(files, category, description)
      } else {
        // 단일 업로드 (기존과 동일)
        if (!file || !title) return
        await documentAPI.uploadDocument(file, title, category, description)
      }
      onSuccess()
    } catch (error) {
      console.error('Upload failed:', error)
      alert('업로드에 실패했습니다.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className="bg-white rounded-2xl p-8 max-w-md w-full"
      >
        <h2 className="text-2xl font-bold text-gray-900 mb-6">문서 업로드</h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          {/* 단일 업로드 시에만 제목 입력 */}
          {files.length <= 1 && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">제목 *</label>
              <input
                type="text"
                required
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
              />
            </div>
          )}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">카테고리 *</label>
            <select
              required
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            >
              <option value="">선택하세요</option>
              {categories.map((cat: string) => (
                <option key={cat} value={cat}>{cat}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">설명</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">파일 {files.length > 1 ? `(${files.length}개 선택됨)` : '*'} </label>
            <input
              type="file"
              required={files.length === 0}
              onChange={handleFileChange}
              multiple
              accept=".pdf,.txt,.docx,.doc,.xlsx,.xls,.pptx,.ppt"
              className="w-full px-4 py-2 border border-gray-300 rounded-lg"
            />
            {files.length > 1 && (
              <p className="mt-2 text-xs text-gray-500">여러 파일 선택 시 제목은 각 파일명으로 자동 설정됩니다.</p>
            )}
          </div>
          <div className="flex space-x-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors"
            >
              취소
            </button>
            <button
              type="submit"
              disabled={loading}
              className="flex-1 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors disabled:opacity-50"
            >
              {loading ? '업로드 중...' : (files.length > 1 ? `${files.length}개 업로드` : '업로드')}
            </button>
          </div>
        </form>
      </motion.div>
    </div>
  )
}

function Pagination({ currentPage, totalPages, onPageChange }: any) {
  const getVisiblePages = () => {
    const delta = 2
    const range = []
    const rangeWithDots = []

    for (
      let i = Math.max(2, currentPage - delta);
      i <= Math.min(totalPages - 1, currentPage + delta);
      i++
    ) {
      range.push(i)
    }

    if (currentPage - delta > 2) {
      rangeWithDots.push(1, '...')
    } else {
      rangeWithDots.push(1)
    }

    rangeWithDots.push(...range)

    if (currentPage + delta < totalPages - 1) {
      rangeWithDots.push('...', totalPages)
    } else if (totalPages > 1) {
      rangeWithDots.push(totalPages)
    }

    return rangeWithDots
  }

  const visiblePages = getVisiblePages()

  return (
    <div className="flex items-center justify-center space-x-2 py-6">
      {/* 이전 버튼 */}
      <button
        onClick={() => onPageChange(currentPage - 1)}
        disabled={currentPage === 1}
        className="flex items-center space-x-1 px-3 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        <ChevronLeftIcon className="w-4 h-4" />
        <span>이전</span>
      </button>

      {/* 페이지 번호들 */}
      <div className="flex space-x-1">
        {visiblePages.map((page, index) => (
          <button
            key={index}
            onClick={() => typeof page === 'number' && onPageChange(page)}
            disabled={page === '...'}
            className={`px-3 py-2 text-sm font-medium rounded-lg ${
              page === currentPage
                ? 'bg-primary-600 text-white'
                : page === '...'
                ? 'text-gray-500 cursor-default'
                : 'text-gray-700 bg-white border border-gray-300 hover:bg-gray-50'
            }`}
          >
            {page}
          </button>
        ))}
      </div>

      {/* 다음 버튼 */}
      <button
        onClick={() => onPageChange(currentPage + 1)}
        disabled={currentPage === totalPages}
        className="flex items-center space-x-1 px-3 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        <span>다음</span>
        <ChevronRightIcon className="w-4 h-4" />
      </button>
    </div>
  )
}





