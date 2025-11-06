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
    customer_type = persona.get("type", "실용형")
    style = persona.get("style", {}) or {}
    emotion_level = int(style.get("emotion_level", 3))

    # 성별 기반 기본 보이스
    base_voice = {"남성": "alloy", "여성": "verse"}.get(gender, "alloy")

    # 연령대별 기본 속도
    rate_map = {
        "20대": 1.15,
        "30대": 1.10,
        "40대": 1.00,
        "50대": 0.95,
        "60대 이상": 0.90,
    }

    # 감정 레벨별 피치
    pitch_map = {1: -2, 2: -1, 3: 0, 4: 1, 5: 2}

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
    adj = type_adjust.get(customer_type, {"rate": 0, "pitch": 0})

    rate = round(base_rate + adj["rate"], 2)
    pitch = base_pitch + adj["pitch"]

    return {"voice": base_voice, "rate": rate, "pitch": pitch}


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


