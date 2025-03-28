from pydantic import BaseModel

# TTS 생성 요청 스키마
class TTSRequest(BaseModel):
  # TTS 관련 파라미터들
  # id: str
  text: str
  speaker: str = "paimon"
  language: str
  speed: float = 1.0
