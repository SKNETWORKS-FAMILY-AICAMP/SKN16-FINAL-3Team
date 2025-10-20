import { useState, useRef, useEffect } from 'react';
import { 
  UserCircleIcon, 
  PencilIcon, 
  CheckIcon, 
  XMarkIcon,
  EyeIcon,
  EyeSlashIcon,
  PhoneIcon,
  EnvelopeIcon,
  UserIcon,
  ArrowPathIcon,
  QrCodeIcon,
  CameraIcon
} from '@heroicons/react/24/outline';
import { useAuthStore } from '../store/authStore';
import { authAPI } from '../utils/api';
import { QRCodeSVG } from 'qrcode.react';
import { motion } from 'framer-motion';

export default function MyPage() {
  const { user, updateUser } = useAuthStore();
  const [photoUrl, setPhotoUrl] = useState(user?.photo_url || '');
  const [uploading, setUploading] = useState(false);
  const [showQR, setShowQR] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // 웹캠 촬영 관련 상태
  const [showCamera, setShowCamera] = useState(false);
  const [stream, setStream] = useState<MediaStream | null>(null);
  const [capturedImage, setCapturedImage] = useState<string | null>(null);
  const [currentFilter, setCurrentFilter] = useState('none');
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  
  // 편집 폼 데이터
  const [editForm, setEditForm] = useState({
    name: user?.name || '',
    email: user?.email || '',
    password: '',
    confirmPassword: '',
    phone: user?.phone || '',
    extension: user?.extension || '',
    team: user?.team || '',
    team_number: user?.team_number || '',
    interests: (() => {
      if (!user?.interests) return [];
      if (Array.isArray(user.interests)) return user.interests;
      try {
        return JSON.parse(user.interests);
      } catch {
        return user.interests.split(',').map(s => s.trim()).filter(s => s);
      }
    })(),
    mbti: user?.mbti || ''
  });

  if (!user) return <div>로그인이 필요합니다.</div>;

  const getDisplayPhotoUrl = (url?: string) => {
    if (!url) return ''
    if (/^https?:\/\//i.test(url) || url.startsWith('data:')) return url
    // 핵심: 어떤 경우든 /uploads 경로는 프록시(/api)로 강제
    if (url.includes('/uploads/')) {
      const onlyPath = url.replace(/^https?:\/\/[^/]+/, '')
      return onlyPath.startsWith('/api') ? onlyPath : `/api${onlyPath}`
    }
    return url
  }

  // 이미지 업로드 핸들러
  const handleImageChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      const data = await authAPI.uploadProfilePhoto(file as any);
      if (data?.photo_url) {
        setPhotoUrl(data.photo_url)
        updateUser({ ...user, photo_url: data.photo_url })
        return
      }
    } finally {
      setUploading(false);
    }
    // 실패 시에도 즉시 미리보기 제공 (이전 동작 유지)
    try {
      const reader = new FileReader()
      reader.onload = (ev) => {
        if (ev.target?.result) {
          const preview = ev.target.result as string
          setPhotoUrl(preview)
          updateUser({ ...user, photo_url: preview })
        }
      }
      reader.readAsDataURL(file)
    } catch {}
  };

  // 웹캠 시작
  const startCamera = async () => {
    try {
      const mediaStream = await navigator.mediaDevices.getUserMedia({
        video: {
          width: { ideal: 1280 },
          height: { ideal: 720 },
          facingMode: 'user'
        }
      });
      setStream(mediaStream);
      if (videoRef.current) {
        videoRef.current.srcObject = mediaStream;
      }
    } catch (err) {
      console.error('Camera error:', err);
      alert('카메라에 접근할 수 없습니다. 권한을 확인해주세요.');
      setShowCamera(false);
    }
  };

  // 웹캠 중지
  const stopCamera = () => {
    if (stream) {
      stream.getTracks().forEach(track => track.stop());
      setStream(null);
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
  };

  // 사진 촬영
  const capturePhoto = () => {
    if (!videoRef.current || !canvasRef.current) return;

    const video = videoRef.current;
    const canvas = canvasRef.current;
    
    // Canvas 크기 설정
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // 필터 적용
    ctx.filter = getFilterStyle(currentFilter);
    
    // 좌우 반전 (거울 효과)
    ctx.translate(canvas.width, 0);
    ctx.scale(-1, 1);
    
    // 비디오 프레임 캡처
    ctx.drawImage(video, 0, 0);
    
    // 이미지 데이터 추출
    const imageData = canvas.toDataURL('image/jpeg', 0.9);
    setCapturedImage(imageData);
  };

  // 필터 스타일 반환
  const getFilterStyle = (filter: string) => {
    const filters: Record<string, string> = {
      'none': 'none',
      'grayscale': 'grayscale(100%)',
      'sepia': 'sepia(100%)',
      'bright': 'brightness(1.3)',
      'dark': 'brightness(0.7)',
      'contrast': 'contrast(1.5)',
      'blur': 'blur(2px)',
      'vintage': 'sepia(50%) contrast(1.2) brightness(0.9)',
      'cool': 'hue-rotate(180deg) saturate(1.5)',
      'warm': 'sepia(30%) saturate(1.3)',
    };
    return filters[filter] || 'none';
  };

  // 촬영된 사진 사용
  const useCapturedPhoto = () => {
    if (capturedImage) {
      setPhotoUrl(capturedImage);
      updateUser({ ...user, photo_url: capturedImage });
      handleCloseCamera();
    }
  };

  // 카메라 모달 닫기
  const handleCloseCamera = () => {
    stopCamera();
    setShowCamera(false);
    setCapturedImage(null);
    setCurrentFilter('none');
  };

  // 카메라 모달 열기
  const handleOpenCamera = () => {
    setShowCamera(true);
    setCapturedImage(null);
  };

  // useEffect: 카메라 시작 및 정리
  useEffect(() => {
    if (showCamera && !capturedImage) {
      startCamera();
    }
    
    return () => {
      stopCamera();
    };
  }, [showCamera]);

  // useEffect: 키보드 단축키 (ESC, Space)
  useEffect(() => {
    if (!showCamera) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      // ESC: 모달 닫기
      if (e.key === 'Escape') {
        handleCloseCamera();
      }
      // Space: 사진 촬영 (촬영 전에만)
      if (e.key === ' ' || e.code === 'Space') {
        e.preventDefault(); // 스크롤 방지
        if (!capturedImage) {
          capturePhoto();
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [showCamera, capturedImage]);

  // 편집 모드 토글
  const handleEditToggle = () => {
    if (isEditing) {
      // 편집 취소 - 원래 데이터로 복원
      setEditForm({
        name: user?.name || '',
        email: user?.email || '',
        password: '',
        confirmPassword: '',
        phone: user?.phone || '',
        extension: user?.extension || '',
        team: user?.team || '',
        team_number: user?.team_number || '',
        interests: (() => {
          if (!user?.interests) return [];
          if (Array.isArray(user.interests)) return user.interests;
          try {
            return JSON.parse(user.interests);
          } catch {
            return user.interests.split(',').map(s => s.trim()).filter(s => s);
          }
        })(),
        mbti: user?.mbti || ''
      });
    }
    setIsEditing(!isEditing);
  };

  // 폼 데이터 변경 핸들러
  const handleFormChange = (field: string, value: any) => {
    setEditForm(prev => ({ ...prev, [field]: value }));
  };

  // 저장 핸들러
  const handleSave = async () => {
    try {
      // 비밀번호 확인 검증
      if (editForm.password && editForm.password !== editForm.confirmPassword) {
        alert('비밀번호와 비밀번호 확인이 일치하지 않습니다.');
        return;
      }
      
      // 비밀번호 길이 검증
      if (editForm.password && editForm.password.length < 6) {
        alert('비밀번호는 최소 6자 이상이어야 합니다.');
        return;
      }
      
      // 관심사를 문자열로 변환 (백엔드에서 JSON 문자열로 저장)
      const updateData: any = {
        name: editForm.name,
        email: editForm.email,
        phone: editForm.phone,
        extension: editForm.extension,
        team: editForm.team,
        team_number: editForm.team_number,
        mbti: editForm.mbti,
        interests: Array.isArray(editForm.interests)
          ? JSON.stringify(editForm.interests)
          : editForm.interests,
      };

      if (editForm.password) {
        updateData.password = editForm.password;
      }

      // 변경 사항이 없는 경우 조용히 종료 (API 호출 안 함)
      const serializedUserInterests = (() => {
        if (!user?.interests) return '';
        if (Array.isArray(user.interests)) return JSON.stringify(user.interests);
        try { return JSON.stringify(JSON.parse(user.interests)); } catch { return String(user.interests); }
      })();

      const currentSnapshot = {
        name: user?.name || '',
        email: user?.email || '',
        phone: user?.phone || '',
        extension: user?.extension || '',
        team: user?.team || '',
        team_number: user?.team_number || '',
        mbti: user?.mbti || '',
        interests: serializedUserInterests,
      };

      const nextSnapshot = { ...currentSnapshot, ...updateData, interests: updateData.interests || '' };
      const hasAnyChange = Object.keys(currentSnapshot).some((k) => (currentSnapshot as any)[k] !== (nextSnapshot as any)[k]) || !!editForm.password;

      if (!hasAnyChange) {
        setIsEditing(false);
        return;
      }

      // 실제 API 호출하여 DB 업데이트
      const updatedUser = await authAPI.updateProfile(updateData);
      
      // 로컬 상태도 업데이트
      updateUser(updatedUser);
      setIsEditing(false);
      alert('프로필이 성공적으로 업데이트되었습니다!');
    } catch (error) {
      console.error('프로필 업데이트 실패:', error);
      alert('프로필 업데이트에 실패했습니다.');
    }
  };

  // 관심사 옵션
  const interestOptions = [
    'IT/테크', '주식', '부동산', '디자인/예술', '공연/전시', '마케팅', 
    '스포츠', '음악', '독서', '게임', '사내 소모임', '자기계발'
  ];

  // 부서 옵션
  const teamOptions = [
    '', '영업부', '기업금융 / 기업영업부', '리스크관리부', 
    '여신심사 / 여신관리부', '자금부 / 자금시장부', '재무 / 회계부', 
    '기획 / 전략부', 'IT / 정보기술부', '디지털 / 혁신부서', 
    '마케팅 / 홍보부', '고객지원 / 고객센터 / 민원부', '법무부', 
    '감사 / 내부감사부', '보안 / 정보보호부', '소비자보호부', 
    '상품 / 금융상품개발부', '자산관리 / WM (Wealth Management)부', 
    '외환 / 무역금융부', '투자은행부', '지속가능경영(ESG)부', 
    '인사부', '총무부', 'CRM부'
  ];

  // 팀 옵션
  const teamNumberOptions = [
    '', '1팀', '2팀', '3팀', '4팀', '5팀', 
    '6팀', '7팀', '8팀', '9팀', '10팀'
  ];

  // 휴대폰 번호 포맷팅
  const formatPhoneNumber = (value: string) => {
    const numbers = value.replace(/\D/g, '');
    if (numbers.length <= 3) return numbers;
    if (numbers.length <= 7) return `${numbers.slice(0, 3)}-${numbers.slice(3)}`;
    return `${numbers.slice(0, 3)}-${numbers.slice(3, 7)}-${numbers.slice(7, 11)}`;
  };

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-6">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold text-gray-900">내 정보</h1>
        <div className="flex items-center space-x-3">
          {isEditing && (
            <button
              onClick={handleSave}
              className="flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors shadow-md hover:shadow-lg"
            >
              <CheckIcon className="w-5 h-5" />
              <span>저장</span>
            </button>
          )}
          <button
            onClick={handleEditToggle}
            className={`flex items-center space-x-2 px-4 py-2 rounded-lg transition-colors ${
              isEditing 
                ? 'bg-gray-100 text-gray-700 hover:bg-gray-200' 
                : 'bg-blue-600 text-white hover:bg-blue-700'
            }`}
          >
            {isEditing ? (
              <>
                <XMarkIcon className="w-5 h-5" />
                <span>취소</span>
              </>
            ) : (
              <>
                <PencilIcon className="w-5 h-5" />
                <span>편집</span>
              </>
            )}
          </button>
        </div>
      </div>

      <div className="grid lg:grid-cols-2 gap-8">
        {/* 프로필 섹션 */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-white rounded-xl shadow-md p-6"
        >
          <h2 className="text-xl font-bold text-gray-900 mb-6">프로필</h2>
          
          {/* 프로필 사진 */}
          <div className="flex flex-col items-center mb-6">
            <div className="relative w-32 h-32 mb-4">
              <div className="w-32 h-32 rounded-full overflow-hidden border-4 border-gray-100 bg-gray-50 flex items-center justify-center">
          {photoUrl ? (
                  <img src={getDisplayPhotoUrl(photoUrl)} alt={user.name} className="w-full h-full object-cover" />
          ) : (
                  <UserCircleIcon className="w-20 h-20 text-gray-300" />
          )}
              </div>
          {/* 파일 업로드 버튼 */}
          <button
                className="absolute bottom-2 right-2 bg-blue-500 text-white rounded-full p-2 shadow-lg hover:bg-blue-600 focus:outline-none transition-colors"
            onClick={() => fileInputRef.current?.click()}
            title="파일에서 업로드"
            type="button"
                disabled={uploading}
              >
                {uploading ? (
                  <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                ) : (
                  <PencilIcon className="w-5 h-5" />
                )}
          </button>
          
          {/* 카메라 촬영 버튼 */}
          <button
            className="absolute bottom-2 right-14 bg-green-500 text-white rounded-full p-2 shadow-lg hover:bg-green-600 focus:outline-none transition-colors"
            onClick={handleOpenCamera}
            title="카메라로 촬영"
            type="button"
          >
            <CameraIcon className="w-5 h-5" />
          </button>
          {photoUrl && (
            <button
              className="absolute bottom-2 left-2 z-10 bg-white/95 backdrop-blur text-gray-800 rounded-full p-2 shadow hover:bg-white focus:outline-none transition-all border border-gray-200"
              aria-label="기본 이미지로 되돌리기"
              title="기본 이미지로 되돌리기"
              onClick={async (e) => {
                e.stopPropagation()
                try {
                  await authAPI.resetProfilePhoto()
                  setPhotoUrl('')
                  updateUser({ ...user, photo_url: undefined as any })
                } catch (err) {
                  console.error(err)
                  alert('기본 상태로 되돌리기에 실패했습니다.')
                }
              }}
            type="button"
          >
              <ArrowPathIcon className="w-4 h-4" />
          </button>
          )}
          <input
            type="file"
            accept="image/*"
            ref={fileInputRef}
            className="hidden"
            onChange={handleImageChange}
            disabled={uploading}
          />
        </div>
            
            {/* 이름과 역할 */}
            <div className="text-center">
              {isEditing ? (
                <input
                  type="text"
                  value={editForm.name}
                  onChange={(e) => handleFormChange('name', e.target.value)}
                  className="text-2xl font-bold text-center bg-transparent border-b-2 border-blue-500 focus:outline-none"
                />
              ) : (
                <h3 className="text-2xl font-bold text-gray-900">{user.name}</h3>
              )}
              <div className="text-blue-600 text-sm font-medium mt-1">
                {user.role === 'mentee' ? '멘티' : user.role === 'mentor' ? '멘토' : '관리자'}
              </div>
            </div>
          </div>
        </motion.div>

        {/* 기본 정보 섹션 */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="bg-white rounded-xl shadow-md p-6"
        >
          <h2 className="text-xl font-bold text-gray-900 mb-6">기본 정보</h2>
          
          <div className="space-y-4">
            {/* 이메일 */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                <EnvelopeIcon className="w-4 h-4 inline mr-1" />
                이메일
              </label>
              {isEditing ? (
                <input
                  type="email"
                  value={editForm.email}
                  onChange={(e) => handleFormChange('email', e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              ) : (
                <div className="text-gray-900">{user.email}</div>
              )}
            </div>

            {/* 비밀번호 */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                <UserIcon className="w-4 h-4 inline mr-1" />
                비밀번호
              </label>
              {isEditing ? (
                <div className="space-y-3">
                  <div className="relative">
                    <input
                      type={showPassword ? 'text' : 'password'}
                      value={editForm.password}
                      onChange={(e) => handleFormChange('password', e.target.value)}
                      placeholder="새 비밀번호 (선택사항)"
                      className="w-full px-3 py-2 pr-10 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-400 hover:text-gray-600"
                    >
                      {showPassword ? <EyeSlashIcon className="w-5 h-5" /> : <EyeIcon className="w-5 h-5" />}
                    </button>
                  </div>
                  
                  {/* 비밀번호 확인 */}
                  {editForm.password && (
                    <div className="relative">
                      <input
                        type={showConfirmPassword ? 'text' : 'password'}
                        value={editForm.confirmPassword}
                        onChange={(e) => handleFormChange('confirmPassword', e.target.value)}
                        placeholder="비밀번호 확인"
                        className={`w-full px-3 py-2 pr-10 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent ${
                          editForm.confirmPassword && editForm.password !== editForm.confirmPassword
                            ? 'border-red-300 bg-red-50'
                            : editForm.confirmPassword && editForm.password === editForm.confirmPassword
                            ? 'border-green-300 bg-green-50'
                            : 'border-gray-300'
                        }`}
                      />
                      <button
                        type="button"
                        onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                        className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-400 hover:text-gray-600"
                      >
                        {showConfirmPassword ? <EyeSlashIcon className="w-5 h-5" /> : <EyeIcon className="w-5 h-5" />}
                      </button>
                      
                      {/* 비밀번호 일치 여부 표시 */}
                      {editForm.confirmPassword && (
                        <div className="mt-1 text-xs">
                          {editForm.password === editForm.confirmPassword ? (
                            <span className="text-green-600 flex items-center">
                              <svg className="w-3 h-3 mr-1" fill="currentColor" viewBox="0 0 20 20">
                                <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                              </svg>
                              비밀번호가 일치합니다
                            </span>
                          ) : (
                            <span className="text-red-600 flex items-center">
                              <svg className="w-3 h-3 mr-1" fill="currentColor" viewBox="0 0 20 20">
                                <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
                              </svg>
                              비밀번호가 일치하지 않습니다
                            </span>
                          )}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ) : (
                <div className="text-gray-500">••••••••</div>
              )}
            </div>

            {/* 사원번호 */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                사원번호
              </label>
              <div className="text-gray-900">{user.employee_number || '-'}</div>
            </div>

            {/* MBTI */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                MBTI
              </label>
              {isEditing ? (
                <input
                  type="text"
                  value={editForm.mbti}
                  onChange={(e) => handleFormChange('mbti', e.target.value)}
                  placeholder="예: ENFP"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              ) : (
                <div className="text-gray-900">{user.mbti || '-'}</div>
              )}
            </div>
          </div>
        </motion.div>

        {/* 연락처 정보 섹션 */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="bg-white rounded-xl shadow-md p-6"
        >
          <h2 className="text-xl font-bold text-gray-900 mb-6">연락처 정보</h2>
          
          <div className="space-y-4">
            {/* 휴대폰 번호 */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                <PhoneIcon className="w-4 h-4 inline mr-1" />
                휴대폰 번호
              </label>
              {isEditing ? (
                <input
                  type="tel"
                  value={editForm.phone}
                  onChange={(e) => handleFormChange('phone', formatPhoneNumber(e.target.value))}
                  placeholder="010-1234-5678"
                  maxLength={13}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              ) : (
                <div className="text-gray-900">{user.phone || '-'}</div>
              )}
      </div>

            {/* 내선 번호 */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                내선 번호
              </label>
              {isEditing ? (
                <input
                  type="text"
                  value={editForm.extension}
                  onChange={(e) => handleFormChange('extension', e.target.value)}
                  placeholder="1234"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              ) : (
                <div className="text-gray-900">{user.extension || '-'}</div>
              )}
            </div>
          </div>
        </motion.div>

        {/* 부서 및 관심사 섹션 */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="bg-white rounded-xl shadow-md p-6"
        >
          <h2 className="text-xl font-bold text-gray-900 mb-6">부서 및 관심사</h2>
          
          <div className="space-y-4">
            {/* 부서/팀 */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                부서/팀
              </label>
              {isEditing ? (
                <div className="grid grid-cols-2 gap-2">
                  <select
                    value={editForm.team}
                    onChange={(e) => handleFormChange('team', e.target.value)}
                    className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  >
                    {teamOptions.map((option) => (
                      <option key={option} value={option}>
                        {option || '부서 선택'}
                      </option>
                    ))}
                  </select>
                  <select
                    value={editForm.team_number}
                    onChange={(e) => handleFormChange('team_number', e.target.value)}
                    className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  >
                    {teamNumberOptions.map((option) => (
                      <option key={option} value={option}>
                        {option || '팀 선택'}
                      </option>
                    ))}
                  </select>
        </div>
              ) : (
                <div className="text-gray-900">
            {user.team && user.team_number
              ? `${user.team} ${user.team_number}`
              : user.team || user.team_number || '-'}
                </div>
              )}
            </div>

            {/* 관심사 */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                관심사
              </label>
              {isEditing ? (
                <div className="space-y-2">
                  <div className="grid grid-cols-3 gap-2">
                    {interestOptions.map((interest) => (
                      <label key={interest} className="flex items-center space-x-2">
                        <input
                          type="checkbox"
                          checked={editForm.interests.includes(interest)}
                          onChange={(e) => {
                            if (e.target.checked) {
                              handleFormChange('interests', [...editForm.interests, interest]);
                            } else {
                              handleFormChange('interests', editForm.interests.filter((i: string) => i !== interest));
                            }
                          }}
                          className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                        />
                        <span className="text-sm text-gray-700">{interest}</span>
                      </label>
                    ))}
                  </div>
        </div>
              ) : (
                <div className="text-gray-900">
            {user.interests
              ? (Array.isArray(user.interests)
                  ? user.interests.join(', ')
                  : String(user.interests).replace(/\[|\]|"/g, '').split(',').map(s => s.trim()).join(', '))
              : '-'}
                </div>
              )}
            </div>
        </div>
        </motion.div>
      </div>

      {/* QR 코드 섹션 */}
      <div className="w-full mt-8 pt-8 border-t border-gray-200">
        <button
          onClick={() => setShowQR(!showQR)}
          className="w-full flex items-center justify-center gap-2 py-3 bg-primary-600 text-white rounded-lg font-semibold hover:bg-primary-700 transition-colors"
        >
          <QrCodeIcon className="w-5 h-5" />
          {showQR ? '사원증 QR 코드 숨기기' : '내 사원증 QR 코드 보기'}
        </button>

        {showQR && (
          <div className="mt-6">
            {/* 사원증 카드 스타일 */}
            <div className="relative bg-gradient-to-br from-blue-900 via-blue-800 to-blue-900 rounded-2xl shadow-2xl overflow-hidden">
              {/* 배경 패턴 */}
              <div className="absolute inset-0 opacity-10">
                <div className="absolute top-0 left-0 w-32 h-32 bg-white rounded-full -translate-x-16 -translate-y-16"></div>
                <div className="absolute bottom-0 right-0 w-40 h-40 bg-white rounded-full translate-x-20 translate-y-20"></div>
              </div>
              
              {/* 카드 내용 */}
              <div className="relative p-8">
                {/* 헤더 */}
                <div className="text-center mb-6">
                  <div className="inline-flex items-center justify-center w-16 h-16 bg-white/20 backdrop-blur-sm rounded-full mb-3">
                    <img src="/assets/bear.png" alt="하경은행" className="w-10 h-10" />
                  </div>
                  <h3 className="text-xl font-bold text-white mb-1">하경은행 사원증</h3>
                  <p className="text-blue-200 text-sm">Hakyung Bank Employee ID</p>
                </div>

                {/* QR 코드 */}
                <div className="flex justify-center mb-6">
                  <div className="bg-white p-6 rounded-2xl shadow-lg">
                    <QRCodeSVG 
                      value={`qr-login:${user.email}`}
                      size={180}
                      level="H"
                      includeMargin={false}
                    />
                  </div>
                </div>

                {/* 사용자 정보 */}
                <div className="bg-white/10 backdrop-blur-sm rounded-xl p-4 mb-4">
                  <div className="flex items-center justify-between text-white">
                    <div className="text-left">
                      <p className="text-xs text-blue-200 mb-1">이름 / Name</p>
                      <p className="font-semibold text-lg">{user.name}</p>
                    </div>
                    <div className="text-right">
                      <p className="text-xs text-blue-200 mb-1">사원번호 / ID</p>
                      <p className="font-mono font-semibold">{user.employee_number}</p>
                    </div>
                  </div>
                </div>

                {/* 안내 메시지 */}
                <div className="text-center">
                  <p className="text-blue-100 text-sm mb-2">
                    로그인 시 이 QR 코드를 스캔하세요
                  </p>
                  <div className="inline-flex items-center gap-2 px-4 py-2 bg-green-500/20 border border-green-400/30 rounded-full">
                    <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
                    <p className="text-xs text-green-100 font-medium">유효한 사원증</p>
        </div>
      </div>
              </div>

              {/* 하단 장식 바 */}
              <div className="h-2 bg-gradient-to-r from-blue-400 via-blue-300 to-blue-400"></div>
            </div>
          </div>
        )}
      </div>

      {/* 웹캠 촬영 모달 */}
      {showCamera && (
        <div className="fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl max-w-2xl w-full overflow-hidden">
            {/* 모달 헤더 */}
            <div className="bg-gradient-to-r from-green-600 to-green-700 p-4 text-white">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <CameraIcon className="w-6 h-6" />
                  <div>
                    <h3 className="text-xl font-bold">프로필 사진 촬영</h3>
                    <p className="text-xs text-green-100 mt-0.5">
                      {capturedImage ? '촬영 완료! 사진을 확인하세요' : 'Space: 촬영 | ESC: 닫기'}
                    </p>
                  </div>
                </div>
                <button
                  onClick={handleCloseCamera}
                  className="p-1.5 hover:bg-white/20 rounded-lg transition-colors"
                  title="닫기 (ESC)"
                >
                  <XMarkIcon className="w-5 h-5" />
                </button>
              </div>
            </div>

            {/* 모달 본문 */}
            <div className="p-4">
              {!capturedImage ? (
                <>
                  {/* 웹캠 미리보기 */}
                  <div className="relative bg-black rounded-xl overflow-hidden mb-4">
                    <video
                      ref={videoRef}
                      autoPlay
                      playsInline
                      muted
                      className="w-full aspect-video object-cover"
                      style={{ 
                        filter: getFilterStyle(currentFilter),
                        transform: 'scaleX(-1)' // 거울 효과
                      }}
                    />
                    {/* 원형 가이드라인 */}
                    <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                      <div className="w-48 h-48 rounded-full border-4 border-white border-dashed opacity-50"></div>
                    </div>
                    <div className="absolute bottom-3 left-3 bg-black/50 backdrop-blur-sm text-white px-3 py-1.5 rounded-lg text-xs">
                      <p>얼굴을 원 안에 맞춰주세요</p>
                    </div>
                  </div>

                  {/* 필터 선택 */}
                  <div className="mb-4">
                    <h4 className="text-xs font-semibold text-gray-700 mb-2">필터 효과</h4>
                    <div className="grid grid-cols-5 gap-1.5">
                      {[
                        { id: 'none', label: '원본', icon: '🌈' },
                        { id: 'grayscale', label: '흑백', icon: '⬛' },
                        { id: 'sepia', label: '세피아', icon: '📜' },
                        { id: 'bright', label: '밝게', icon: '☀️' },
                        { id: 'dark', label: '어둡게', icon: '🌙' },
                        { id: 'contrast', label: '대비', icon: '⚡' },
                        { id: 'blur', label: '부드럽게', icon: '💫' },
                        { id: 'vintage', label: '빈티지', icon: '📷' },
                        { id: 'cool', label: '쿨톤', icon: '❄️' },
                        { id: 'warm', label: '따뜻하게', icon: '🔥' },
                      ].map((filter) => (
                        <button
                          key={filter.id}
                          onClick={() => setCurrentFilter(filter.id)}
                          className={`p-2 rounded-lg border-2 transition-all ${
                            currentFilter === filter.id
                              ? 'border-green-500 bg-green-50 shadow-md'
                              : 'border-gray-200 hover:border-green-300 hover:bg-gray-50'
                          }`}
                        >
                          <div className="text-xl mb-0.5">{filter.icon}</div>
                          <div className="text-[10px] font-medium text-gray-700">{filter.label}</div>
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* 촬영 및 취소 버튼 */}
                  <div className="flex gap-2">
                    <button
                      onClick={handleCloseCamera}
                      className="flex-1 py-3 bg-gray-100 text-gray-700 rounded-lg font-semibold hover:bg-gray-200 transition-colors flex items-center justify-center gap-2"
                      title="취소 (ESC)"
                    >
                      <XMarkIcon className="w-5 h-5" />
                      취소
                    </button>
                    <button
                      onClick={capturePhoto}
                      className="flex-[2] py-3 bg-green-600 text-white rounded-lg font-semibold hover:bg-green-700 transition-colors flex items-center justify-center gap-2 shadow-lg"
                      title="촬영 (Space)"
                    >
                      <CameraIcon className="w-5 h-5" />
                      📸 촬영
                    </button>
                  </div>
                </>
              ) : (
                <>
                  {/* 촬영된 사진 미리보기 */}
                  <div className="mb-4">
                    <img
                      src={capturedImage}
                      alt="촬영된 사진"
                      className="w-full rounded-xl shadow-lg"
                    />
                  </div>

                  {/* 버튼들 */}
                  <div className="flex gap-2">
                    <button
                      onClick={() => setCapturedImage(null)}
                      className="flex-1 py-3 bg-gray-100 text-gray-700 rounded-lg font-semibold hover:bg-gray-200 transition-colors"
                    >
                      다시 촬영
                    </button>
                    <button
                      onClick={useCapturedPhoto}
                      className="flex-1 py-3 bg-green-600 text-white rounded-lg font-semibold hover:bg-green-700 transition-colors"
                    >
                      사용하기
                    </button>
                  </div>
                </>
              )}
            </div>
          </div>
          
          {/* 숨겨진 Canvas (캡처용) */}
          <canvas ref={canvasRef} className="hidden" />
        </div>
      )}
    </div>
  );
}
