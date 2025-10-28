import React, { useState, useRef, useEffect } from 'react'
import { useAuthStore } from '../store/authStore'
import api from '../utils/api'
import { playFromAnyAudioPayload } from '../utils/audio'
import { AudioVisualizer } from '../components/AudioVisualizer'
import {
  MicrophoneIcon,
  StopIcon,
  PlayIcon,
  SpeakerWaveIcon,
  ArrowPathIcon,
  ArrowLeftIcon
} from '@heroicons/react/24/outline'

interface VoiceSimulationProps {
  simulationData: any
  onBack: () => void
}

// 대화 메시지 타입
interface ChatMessage {
  id: string
  role: 'user' | 'customer'
  text: string
  audio?: string
  timestamp: Date
}

const VoiceSimulation: React.FC<VoiceSimulationProps> = ({ simulationData, onBack }) => {
  const { user } = useAuthStore()
  const [isRecording, setIsRecording] = useState(false)
  const [isPlaying, setIsPlaying] = useState(false)
  const [userMessage, setUserMessage] = useState('')
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]) // 대화 히스토리
  const [subtitle, setSubtitle] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [stream, setStream] = useState<MediaStream | null>(null) // 오디오 스트림 추가

  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const audioChunksRef = useRef<Blob[]>([])
  const audioRef = useRef<HTMLAudioElement>(null)
  const chatEndRef = useRef<HTMLDivElement>(null) // 스크롤 자동 이동용

  // 새 메시지 추가 시 스크롤
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [chatHistory])

  // 음성 녹음 시작
  const startRecording = async () => {
    try {
      const audioStream = await navigator.mediaDevices.getUserMedia({ 
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          sampleRate: 44100
        }
      })
      
      // 스트림을 state에 저장 (시각화용)
      setStream(audioStream)
      
      mediaRecorderRef.current = new MediaRecorder(audioStream, {
        mimeType: 'audio/webm;codecs=opus'
      })
      audioChunksRef.current = []

      mediaRecorderRef.current.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data)
        }
      }

      mediaRecorderRef.current.onstop = () => {
        const audioBlob = new Blob(audioChunksRef.current, { 
          type: mediaRecorderRef.current?.mimeType || 'audio/webm'
        })
        console.log('녹음된 오디오 Blob:', audioBlob)
        console.log('Blob 크기:', audioBlob.size)
        
        // 스트림 정리
        audioStream.getTracks().forEach(track => track.stop())
        setStream(null)
        
        processAudio(audioBlob)
      }

      mediaRecorderRef.current.start()
      setIsRecording(true)
      setSubtitle('말씀해주세요...')
    } catch (error) {
      console.error('녹음 시작 실패:', error)
      setError('마이크 접근 권한이 필요합니다.')
    }
  }

  // 음성 녹음 중지
  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop()
      setIsRecording(false)
      setSubtitle('음성을 처리 중입니다...')
    }
  }

  // 음성 처리 및 STT - 상세 로그 + 방탄 분기
  const processAudio = async (audioBlob: Blob) => {
    console.groupCollapsed('🚀 음성 인터랙션 요청');
    console.log('보내는 파일:', audioBlob?.type, audioBlob?.size, 'bytes');
    
    try {
      setLoading(true)
      setError('')

      const formData = new FormData()
      formData.append('audio_file', audioBlob, 'recording.webm')  // 서버가 audio_file을 기대
      formData.append('session_data', JSON.stringify(simulationData))

      console.log('FormData 준비 완료, 전송 시작...');

      const response = await api.post('/rag-simulation/process-voice-interaction', formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      })

      console.log('✅ 응답 원본:', response.data);
      const { transcribed_text, customer_response, customer_audio } = response.data
      
      // 오디오 페이로드 디버깅
      console.log('오디오 페이로드 타입:', typeof customer_audio);
      console.log('오디오 페이로드 미리보기:', typeof customer_audio === 'string' ? customer_audio.substring(0, 100) : customer_audio);

      console.log('API 응답 데이터:', { transcribed_text, customer_response, customer_audio: customer_audio ? customer_audio.substring(0, 100) + '...' : null })

      // 대화 히스토리에 사용자 메시지 추가
      if (transcribed_text) {
        setChatHistory((prev: ChatMessage[]) => [...prev, {
          id: Date.now().toString(),
          role: 'user',
          text: transcribed_text,
          timestamp: new Date()
        }])
      }

      // 대화 히스토리에 고객 메시지 추가
      if (customer_response) {
        setChatHistory((prev: ChatMessage[]) => [...prev, {
          id: (Date.now() + 1).toString(),
          role: 'customer',
          text: customer_response,
          audio: customer_audio,
          timestamp: new Date()
        }])
      }

      // 사용자 입력 필드 초기화
      setUserMessage('')

      // 고객 음성 재생 - 새로운 유틸 사용
      if (customer_audio) {
        try {
          console.log('🎵 오디오 재생 시도...');
          await playFromAnyAudioPayload(customer_audio, 'audio/mpeg');
          setIsPlaying(true);
          setError('');
        } catch (audioError) {
          console.error('오디오 재생 실패:', audioError);
          setError('오디오 재생에 실패했습니다.');
        }
      } else {
        console.log('오디오 데이터가 없습니다. 텍스트만 표시됩니다.')
      }

      setSubtitle('')

    } catch (error: any) {
      console.error('❌ 음성 처리 실패:', error)
      setError('음성 처리를 실패했습니다. 다시 시도해주세요.')
    } finally {
      setLoading(false)
      console.groupEnd();
    }
  }

  // (기존 atob 기반 함수들은 제거되고 playFromAnyAudioPayload로 대체됨)

  // 텍스트 입력으로도 시뮬레이션 가능
  const handleTextSubmit = async () => {
    if (!userMessage.trim()) return

    console.groupCollapsed('💬 텍스트 인터랙션 요청');

    try {
      setLoading(true)
      setError('')

      console.log('전송할 메시지:', userMessage);
      console.log('세션 데이터:', simulationData);
      console.log('세션 데이터 키:', Object.keys(simulationData || {}));

      // JSON으로 전송
      const requestData = {
        session_data: simulationData,
        user_message: userMessage
      };

      console.log('요청 데이터 구조:', {
        session_data_keys: Object.keys(requestData.session_data || {}),
        user_message: requestData.user_message
      });

      // JSON으로 직접 전송 (Axios가 자동으로 Content-Type 설정)
      const response = await api.post('/rag-simulation/process-voice-interaction', requestData)

      console.log('✅ 응답 원본:', response.data);
      
      if (!response.data) {
        console.error('응답 데이터가 없습니다');
        setError('서버 응답이 비어있습니다.');
        return;
      }

      const { customer_response, customer_audio } = response.data

      console.log('고객 응답:', customer_response);
      console.log('고객 오디오 있음:', !!customer_audio);

      // 대화 히스토리에 사용자 메시지 추가
      setChatHistory((prev: ChatMessage[]) => [...prev, {
        id: Date.now().toString(),
        role: 'user',
        text: userMessage,
        timestamp: new Date()
      }])

      // 대화 히스토리에 고객 메시지 추가
      if (customer_response) {
        setChatHistory((prev: ChatMessage[]) => [...prev, {
          id: (Date.now() + 1).toString(),
          role: 'customer',
          text: customer_response,
          audio: customer_audio,
          timestamp: new Date()
        }])
      }

      // 사용자 입력 필드 초기화
      setUserMessage('')

      // 오디오 재생 - 새로운 유틸 사용
      if (customer_audio) {
        try {
          console.log('🎵 오디오 재생 시도...');
          await playFromAnyAudioPayload(customer_audio, 'audio/mpeg');
          setIsPlaying(true);
          setError('');
        } catch (audioError) {
          console.error('오디오 재생 실패:', audioError);
          setError('오디오 재생에 실패했습니다.');
        }
      } else {
        console.log('오디오 데이터가 없습니다. 텍스트만 표시됩니다.');
      }

    } catch (error: any) {
      console.error('❌ 텍스트 처리 실패:', error)
      console.error('에러 상세:', error?.response?.data || error?.message)
      setError(`메시지 처리를 실패했습니다: ${error?.response?.data?.detail || error?.message || '알 수 없는 오류'}`)
    } finally {
      setLoading(false)
      console.groupEnd();
    }
  }

  // 오디오 재생 완료 처리 및 자동 재생 준비
  useEffect(() => {
    if (audioRef.current) {
      audioRef.current.onended = () => {
        setIsPlaying(false)
        // URL 객체 정리
        if (audioRef.current?.src && audioRef.current.src.startsWith('blob:')) {
          URL.revokeObjectURL(audioRef.current.src)
        }
      }
      
      audioRef.current.onerror = () => {
        setIsPlaying(false)
        setError('오디오 재생 중 오류가 발생했습니다.')
      }
    }
  }, [])

  return (
    <div className="min-h-screen bg-gradient-to-br from-purple-50 to-blue-100 p-6">
      <div className="max-w-4xl mx-auto">
        {/* 헤더 */}
        <div className="flex items-center justify-between mb-8">
          <button
            onClick={onBack}
            className="flex items-center text-gray-600 hover:text-gray-800 transition-colors"
          >
            <ArrowLeftIcon className="w-5 h-5 mr-2" />
            뒤로가기
          </button>
          <h1 className="text-2xl font-bold text-gray-900">음성 시뮬레이션</h1>
          <div></div>
        </div>

        {/* 시뮬레이션 정보 */}
        <div className="bg-white rounded-lg shadow-lg p-6 mb-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">시뮬레이션 정보</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <h3 className="font-medium text-gray-700">고객 정보</h3>
              <p className="text-gray-600">
                {simulationData?.persona?.age_group} | {simulationData?.persona?.occupation} | {simulationData?.persona?.type}
              </p>
            </div>
            <div>
              <h3 className="font-medium text-gray-700">시나리오</h3>
              <p className="text-gray-600">{simulationData?.scenario?.title}</p>
            </div>
          </div>
        </div>

        {/* 대화 영역 */}
        <div className="bg-white rounded-lg shadow-lg p-6 mb-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">대화</h2>
          
          {/* 대화 히스토리 */}
          <div className="space-y-4 max-h-96 overflow-y-auto" style={{ scrollBehavior: 'smooth' }}>
            {chatHistory.length === 0 ? (
              <div className="text-center text-gray-500 py-8">
                대화를 시작하세요. 녹음 버튼을 누르거나 텍스트를 입력하세요.
              </div>
            ) : (
              chatHistory.map((message) => (
                <div
                  key={message.id}
                  className={`p-4 rounded-lg ${
                    message.role === 'user' ? 'bg-blue-50 ml-8' : 'bg-green-50 mr-8'
                  }`}
                >
                  <div className="flex items-center mb-2">
                    <span className={`font-medium ${
                      message.role === 'user' ? 'text-blue-800' : 'text-green-800'
                    }`}>
                      {message.role === 'user' ? '신입사원 (나)' : '고객'}
                    </span>
                    <span className="text-xs text-gray-500 ml-2">
                      {message.timestamp.toLocaleTimeString()}
                    </span>
                  </div>
                  <p className={message.role === 'user' ? 'text-blue-700' : 'text-green-700'}>
                    {message.text}
                  </p>
                  {message.role === 'customer' && message.audio && (
                    <button
                      onClick={() => {
                        if (message.audio) {
                          playFromAnyAudioPayload(message.audio, 'audio/mpeg')
                        }
                      }}
                      className="mt-2 flex items-center px-3 py-1 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors text-sm"
                    >
                      <SpeakerWaveIcon className="w-3 h-3 mr-1" />
                      다시 듣기
                    </button>
                  )}
                </div>
              ))
            )}
            <div ref={chatEndRef} />
          </div>
        </div>

        {/* 실시간 자막 */}
        {subtitle && (
          <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 mb-6">
            <div className="flex items-center">
              <span className="font-medium text-yellow-800 mr-2">실시간 자막:</span>
              <span className="text-yellow-700">{subtitle}</span>
            </div>
          </div>
        )}

        {/* 오디오 파형 시각화 */}
        <div className="bg-white rounded-lg shadow-lg p-6 mb-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">오디오 파형</h2>
          <AudioVisualizer isRecording={isRecording} stream={stream} />
        </div>

        {/* 음성 제어 */}
        <div className="bg-white rounded-lg shadow-lg p-6 mb-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">음성 제어</h2>
          
          <div className="flex items-center justify-center space-x-4 mb-6">
            {!isRecording ? (
              <button
                onClick={startRecording}
                disabled={loading}
                className="flex items-center px-6 py-3 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
              >
                <MicrophoneIcon className="w-5 h-5 mr-2" />
                녹음 시작
              </button>
            ) : (
              <button
                onClick={stopRecording}
                className="flex items-center px-6 py-3 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
              >
                <StopIcon className="w-5 h-5 mr-2" />
                녹음 중지
              </button>
            )}
          </div>

          {/* 텍스트 입력 (대안) */}
          <div className="border-t pt-4">
            <h3 className="font-medium text-gray-700 mb-2">또는 텍스트로 입력</h3>
            <div className="flex space-x-2">
              <input
                type="text"
                value={userMessage}
                onChange={(e) => setUserMessage(e.target.value)}
                placeholder="메시지를 입력하세요..."
                className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <button
                onClick={handleTextSubmit}
                disabled={loading || !userMessage.trim()}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
              >
                전송
              </button>
            </div>
          </div>
        </div>

        {/* 오류 메시지 */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4">
            <p className="text-red-600">{error}</p>
          </div>
        )}

        {/* 오디오 엘리먼트 */}
        <audio ref={audioRef} />
      </div>
    </div>
  )
}

export default VoiceSimulation
