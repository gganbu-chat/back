from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

# 캐릭터 생성 스키마
class CreateCharacterSchema(BaseModel):
  """
  캐릭터 등록을 위한 Pydantic 스키마.
  """
  character_owner: int
  field_idx: int
  voice_idx: Optional[str] = None
  char_name: str
  char_description: str
  nicknames: Optional[dict] = {30: "stranger", 70: "friend", 100: "best friend"}
  character_appearance: str
  character_personality: str
  character_background: str
  character_speech_style: str
  example_dialogues: Optional[List[dict]] = None
  tags: Optional[List[dict]] = None

# 캐릭터 응답 스키마
class CharacterResponseSchema(BaseModel):
  """
  클라이언트에 반환되는 캐릭터 정보 스키마.
  """
  char_idx: int
  char_name: str
  char_description: str
  created_at: str
  nicknames: dict
  character_appearance: str
  character_personality: str
  character_background: str
  character_speech_style: str
  example_dialogues: Optional[List[dict]] = None

  class Config:
    orm_mode = True  # SQLAlchemy 객체 변환 지원
    json_encoders = {
      datetime: lambda v: v.isoformat()  # datetime 문자열로 변환
    }

# 캐릭터 카드 응답 스키마
class CharacterCardResponseSchema(BaseModel):
  """
  클라이언트에 반환되는 캐릭터 정보 스키마.
  """
  char_idx: int
  char_name: str
  character_owner: int
  char_description: str
  character_image: str
  created_at: datetime  # datetime으로 선언 (Pydantic이 자동으로 변환)

  class Config:
    orm_mode = True  # SQLAlchemy 객체 변환 지원
    json_encoders = {
      datetime: lambda v: v.isoformat()  # datetime 문자열로 변환
    }