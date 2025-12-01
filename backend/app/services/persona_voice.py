from typing import Dict


def get_voice_params(persona: Dict) -> Dict:
    """페르소나 기반 TTS 파라미터(voice/rate/pitch) 계산.
    - gender: 남성/여성
    - age_group: 20대/30대/40대/50대/60대 이상
    - type: 실용형/보수형/불만형/긍정형/급함형
    - style.emotion_level: 1~5
    """
    gender_raw = persona.get("gender", "남성")
    age_group_raw = persona.get("age_group", "40대")
    
    # gender 정규화 (다양한 형식 지원)
    gender = gender_raw
    if isinstance(gender_raw, str):
        gender_lower = gender_raw.lower()
        if "남" in gender_lower or gender_lower in ["male", "m"]:
            gender = "남성"
        elif "여" in gender_lower or gender_lower in ["female", "f"]:
            gender = "여성"
    
    # age_group 정규화 (다양한 형식 지원)
    age_group = age_group_raw
    if isinstance(age_group_raw, str):
        if "60" in age_group_raw and ("이상" in age_group_raw or "이상" not in age_group_raw):
            age_group = "60대 이상"
        elif "50" in age_group_raw:
            age_group = "50대"
        elif "40" in age_group_raw:
            age_group = "40대"
        elif "30" in age_group_raw:
            age_group = "30대"
        elif "20" in age_group_raw:
            age_group = "20대"
    
    print(f"🎤 TTS 파라미터 계산: gender={gender} (원본={gender_raw}), age_group={age_group} (원본={age_group_raw})")
    # customer_style 또는 type 사용
    customer_type = persona.get("customer_style") or persona.get("type", "실용형")
    # speech 객체에서 style 정보 가져오기
    speech_obj = persona.get("speech", {})
    style = speech_obj if isinstance(speech_obj, dict) else (persona.get("style", {}) or {})
    emotion_level = int(style.get("emotion_level", 3))

    # 성별 및 연령대 기반 보이스 선택
    # OpenAI TTS API voice 옵션: alloy, echo, fable, onyx, nova, shimmer
    # - onyx: 깊고 낮은 남성 목소리 (나이든 남성에 적합)
    # - echo: 일반적인 남성 목소리 (젊은~중년 남성)
    # - nova: 밝고 젊은 여성 목소리 (젊은 여성에 적합)
    # - shimmer: 부드럽고 따뜻한 여성 목소리 (중년~나이든 여성에 적합)
    # - alloy: 중성적, 다용도
    # - fable: 영국 억양, 스토리텔링에 적합
    
    # 나이대별 voice 매핑 (성별과 연령대 조합)
    if gender == "남성":
        if age_group in ["60대 이상", "60대이상"]:
            base_voice = "onyx"  # 깊고 낮은 나이든 남성 목소리
        elif age_group == "50대":
            base_voice = "onyx"  # 깊은 중년 남성 목소리
        elif age_group == "40대":
            base_voice = "onyx"  # 깊은 중년 남성 목소리 (echo -> onyx로 변경)
        elif age_group == "30대":
            base_voice = "echo"  # 일반 젊은 남성 목소리
        elif age_group == "20대":
            base_voice = "echo"  # 밝고 젊은 남성 목소리
        else:
            base_voice = "echo"  # 기본값: 일반 남성 목소리
    elif gender == "여성":
        if age_group in ["60대 이상", "60대이상"]:
            base_voice = "shimmer"  # 부드럽고 따뜻한 나이든 여성 목소리
        elif age_group == "50대":
            base_voice = "shimmer"  # 부드러운 중년 여성 목소리
        elif age_group == "40대":
            base_voice = "shimmer"  # 부드러운 중년 여성 목소리
        elif age_group == "30대":
            base_voice = "nova"  # 밝은 젊은 여성 목소리
        elif age_group == "20대":
            base_voice = "nova"  # 밝고 젊은 여성 목소리
        else:
            base_voice = "nova"  # 기본값: 밝은 여성 목소리
    else:
        base_voice = "alloy"  # 기본값 (중성적, 성별 불명확한 경우)

    # 연령대별 기본 속도 (나이든 남성은 더 느리게)
    rate_map = {
        "20대": 1.15,
        "30대": 1.10,
        "40대": 1.00,
        "50대": 0.85,      # 50대: 말속도 더 낮춤 (젊은 느낌 감소)
        "60대 이상": 0.80,  # 60대 이상: 더 느리게
        "60대이상": 0.80,   # 변형 형식 지원
    }

    # 감정 레벨별 피치
    pitch_map = {1: -2, 2: -1, 3: 0, 4: 1, 5: 2}
    
    # 나이대별 추가 피치 조정 (남성은 10대를 제외하고 전체적으로 더 깊게)
    # 기본 pitch_map(감정 레벨)에서 한 번 더 내려주는 구조
    age_pitch_adjust = {
        "20대": -2,  # 20대 남성: 피치를 2단계 낮춤
        "30대": -2,  # 30대 남성: 피치를 2단계 낮춤
        "40대": -3,  # 40대 남성: 피치를 3단계 낮춤 (더 깊게)
        "50대": -5,  # 50대 남성: 피치를 5단계 낮춤 (조금 더 깊게)
        "60대 이상": -6,  # 60대 이상 남성: 피치를 6단계 낮춤 (더 많이 깊게)
        "60대이상": -6,
    }

    # 고객 유형별 미세 조정
    type_adjust = {
        "실용형": {"rate": 0.05, "pitch": 0},
        "보수형": {"rate": -0.05, "pitch": -1},
        "불만형": {"rate": 0.05, "pitch": 1},
        "긍정형": {"rate": 0.10, "pitch": 1},
        "급함형": {"rate": 0.15, "pitch": 2},
    }

    base_rate = rate_map.get(age_group, 1.0)
    base_pitch = pitch_map.get(emotion_level, 0)
    
    # 나이대별 피치 조정 추가 (남성의 경우에만 적용)
    age_pitch = age_pitch_adjust.get(age_group, 0)
    if gender == "남성":
        # 모든 남성의 피치를 나이대에 맞게 낮춤
        base_pitch += age_pitch
    # 50대 / 60대 이상 여성도 기본 피치를 추가로 더 낮춰서 성숙한 느낌 강화
    elif gender == "여성" and age_group in ["50대", "60대 이상", "60대이상"]:
        base_pitch += -3  # 여성 50대 / 60대 이상: 피치 3단계 추가 하향
    
    adj = type_adjust.get(customer_type, {"rate": 0, "pitch": 0})

    rate = round(base_rate + adj["rate"], 2)
    pitch = base_pitch + adj["pitch"]

    # 🚨 나이 든 남성의 경우, 피치가 너무 높아지지 않도록 상한 제한
    #  - 50대/60대 이상 남성은 pitch가 양수(밝은 톤)로 올라가지 않도록 최대 -1로 제한
    if gender == "남성" and age_group in ["50대", "60대 이상", "60대이상"] and pitch > -1:
        pitch = -1

    result = {"voice": base_voice, "rate": rate, "pitch": pitch}
    print(f"🎤 TTS 파라미터 결과: {result}")
    return result


def build_ssml(text: str, rate: float, pitch: int) -> str:
    """간단한 SSML로 말속도/피치 적용.
    OpenAI gpt-4o-mini-tts에서 SSML 입력을 사용할 때 'input_format=ssml'을 함께 전달.

    - 문장 앞에 짧은 무음을 넣어 초반 발화가 잘리지 않도록 함.
    """
    # OpenAI SSML 호환을 위해 rate는 비율, pitch는 semitone로 가정
    # 문장 사이에 짧은 휴지를 넣어 가독성 향상
    safe_text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f"""
<speak>
  <break time="200ms"/>
  <prosody rate="{rate}" pitch="{f"{pitch:+d}"}">
    {safe_text}
  </prosody>
</speak>
""".strip()


