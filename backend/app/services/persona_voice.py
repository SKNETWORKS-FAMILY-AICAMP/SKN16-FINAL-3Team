from typing import Dict


def get_voice_params(persona: Dict) -> Dict:
    """페르소나 기반 TTS 파라미터(voice/rate/pitch) 계산.
    - gender: 남성/여성
    - age_group: 20대/30대/40대/50대/60대 이상
    - type: 실용형/보수형/불만형/긍정형/급함형
    - style.emotion_level: 1~5
    """
    gender = persona.get("gender", "남성")
    age_group = persona.get("age_group", "40대")
    # customer_style 또는 type 사용
    customer_type = persona.get("customer_style") or persona.get("type", "실용형")
    # speech 객체에서 style 정보 가져오기
    speech_obj = persona.get("speech", {})
    style = speech_obj if isinstance(speech_obj, dict) else (persona.get("style", {}) or {})
    emotion_level = int(style.get("emotion_level", 3))

    # 성별 판단
    is_female = (gender == "여성" or gender == "female")
    
    # 고객 타입별 음성 톤 매핑
    tone_map = {
        "실용형": "direct",
        "보수형": "calm",
        "불만형": "tense",
        "긍정형": "cheerful",
        "급함형": "urgent"
    }
    tone = tone_map.get(customer_type, "neutral")
    
    # 성별 + 나이대 + 톤별 음성 선택 (더 세밀한 매핑)
    if is_female:
        # 여성 음성: nova(차분), shimmer(밝음)
        if age_group in ["20대", "30대"]:
            voice_map = {
                "direct": "shimmer",    # 젊고 직설적
                "calm": "nova",         # 차분하고 신중
                "tense": "shimmer",     # 약간 날카로운 톤
                "cheerful": "shimmer",  # 밝고 긍정적
                "urgent": "shimmer",    # 빠르고 급한
                "neutral": "nova"
            }
        elif age_group in ["40대", "50대"]:
            voice_map = {
                "direct": "nova",       # 성숙하고 직설적
                "calm": "nova",         # 차분하고 신중
                "tense": "nova",        # 차분하지만 불만
                "cheerful": "nova",     # 따뜻하고 긍정적
                "urgent": "shimmer",    # 급한 상황
                "neutral": "nova"
            }
        else:  # 60대 이상 - 노인 여성 목소리
            voice_map = {
                "direct": "nova",       # 깊고 성숙한 목소리
                "calm": "nova",         # 차분하고 깊은 목소리
                "tense": "nova",        # 깊지만 불만스러운 톤
                "cheerful": "nova",     # 따뜻하고 깊은 목소리
                "urgent": "nova",       # 깊은 목소리
                "neutral": "nova"      # 깊고 차분한 노인 목소리
            }
    else:
        # 남성 음성: alloy(중성적), echo(깊음), fable(따뜻함), onyx(강하고 깊음)
        if age_group in ["20대", "30대"]:
            voice_map = {
                "direct": "alloy",      # 젊고 직설적
                "calm": "echo",         # 차분하고 깊은
                "tense": "fable",       # 약간 거친 톤
                "cheerful": "fable",    # 밝고 친근한
                "urgent": "alloy",      # 빠르고 급한
                "neutral": "alloy"
            }
        elif age_group in ["40대", "50대"]:
            voice_map = {
                "direct": "echo",       # 성숙하고 직설적
                "calm": "echo",         # 차분하고 신중
                "tense": "fable",       # 불만스러운 톤
                "cheerful": "fable",    # 따뜻하고 긍정적
                "urgent": "alloy",      # 급한 상황
                "neutral": "echo"
            }
        else:  # 60대 이상 - 노인 남성 목소리 (더 깊고 낮은 목소리)
            voice_map = {
                "direct": "onyx",       # 깊고 강한 노인 목소리
                "calm": "onyx",         # 깊고 차분한 노인 목소리
                "tense": "onyx",        # 깊고 불만스러운 노인 목소리
                "cheerful": "echo",     # 따뜻하고 깊은 노인 목소리
                "urgent": "onyx",       # 깊고 강한 노인 목소리
                "neutral": "onyx"       # 깊고 낮은 노인 목소리
            }
    
    # 연령대별 기본 속도 (60대 이상은 더 느리게)
    rate_map = {
        "20대": 1.15,
        "30대": 1.10,
        "40대": 1.00,
        "50대": 0.95,
        "60대 이상": 0.75,  # 노인은 더 느리게
    }

    # 고객 타입별 말하기 속도 조정 (60대 이상은 조정 폭을 줄임)
    if age_group == "60대 이상":
        # 노인은 급함형이어도 너무 빠르지 않게
        type_speed_adjust = {
            "실용형": 0.0,      # 보통
            "보수형": -0.1,     # 천천히
            "불만형": 0.0,      # 보통
            "긍정형": 0.05,     # 약간 빠르게
            "급함형": 0.1,      # 약간 빠르게 (노인은 너무 빠르지 않게)
        }
    else:
        type_speed_adjust = {
            "실용형": 0.1,      # 빠르게
            "보수형": -0.1,     # 천천히
            "불만형": 0.0,      # 보통
            "긍정형": 0.1,      # 밝게 빠르게
            "급함형": 0.3,      # 매우 빠르게
        }

    base_rate = rate_map.get(age_group, 1.0)
    speed_adjust = type_speed_adjust.get(customer_type, 0.0)
    rate = round(base_rate + speed_adjust, 2)
    
    # 60대 이상은 최소 속도 제한 (너무 느리지 않게)
    if age_group == "60대 이상" and rate < 0.7:
        rate = 0.7
    
    # 음성 선택
    voice = voice_map.get(tone, "alloy" if not is_female else "nova")

    return {"voice": voice, "rate": rate, "pitch": 0}  # pitch는 OpenAI TTS에서 직접 지원하지 않으므로 0으로 설정


def build_ssml(text: str, rate: float, pitch: int) -> str:
    """간단한 SSML로 말속도/피치 적용.
    OpenAI gpt-4o-mini-tts에서 SSML 입력을 사용할 때 'input_format=ssml'을 함께 전달.
    """
    # OpenAI SSML 호환을 위해 rate는 비율, pitch는 semitone로 가정
    # 문장 사이에 짧은 휴지를 넣어 가독성 향상
    safe_text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f"""
<speak>
  <prosody rate="{rate}" pitch="{f"{pitch:+d}"}">
    {safe_text}
  </prosody>
</speak>
""".strip()


