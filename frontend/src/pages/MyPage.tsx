import { useState, useRef } from 'react';
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
  QrCodeIcon
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
              <h3 className="text-2xl font-bold text-gray-900">{user.name}</h3>
              {isEditing && (
                <p className="mt-1 text-xs text-gray-400">이름은 관리자만 수정 가능합니다.</p>
              )}
              <div className="text-blue-600 text-sm font-medium mt-2">
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
              <div className="text-gray-900">{user.email}</div>
              {isEditing && (
                <p className="mt-1 text-xs text-gray-400">이메일은 관리자만 수정 가능합니다.</p>
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
              <div className="text-gray-900">
                {user.team && user.team_number
                  ? `${user.team} ${user.team_number}`
                  : user.team || user.team_number || '-'}
              </div>
              {isEditing && (
                <p className="mt-1 text-xs text-gray-400">
                  부서와 팀 정보는 관리자만 수정 가능합니다.
                </p>
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

    </div>
  );
}
