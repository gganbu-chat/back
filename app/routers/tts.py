from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.models import Character, ChatRoom, Voice
from app.utils.common_function import clean_json_string

router = APIRouter()

UPLOAD_DIR = "app/uploads/characters/"  # 캐릭터 이미지 파일 저장 경로

# TTS 모델 정보 조회 API
@router.get("/api/ttsmodel/{room_id}")
def get_tts_model(room_id: str, db: Session = Depends(get_db)):
  """
  특정 채팅방에 연결된 캐릭터 및 TTS 모델 정보를 반환하는 API 엔드포인트.
  """
  # 채팅방 ID를 기준으로 데이터베이스에서 채팅방 검색
  room = db.query(ChatRoom).filter(ChatRoom.id == room_id, ChatRoom.is_active == True).first()
  if not room:
    raise HTTPException(status_code=404, detail="채팅방을 찾을 수 없습니다.")
  
  # 채팅방에 연결된 캐릭터 검색
  character = db.query(Character).filter(Character.character_index == room.character_id).first()
  if not character:
    raise HTTPException(status_code=404, detail="캐릭터를 찾을 수 없습니다.")
  
  # `voice` 테이블에서 character_id와 연결된 TTS 정보 검색
  voice_info = db.query(Voice).filter(Voice.voice_idx == room.character_voice).first()
  if not voice_info:
    raise HTTPException(status_code=404, detail="TTS 정보를 찾을 수 없습니다.")
  
  # 캐릭터 및 TTS 정보를 반환
  return {
    "character_name": character.character_name,
    "character_prompt": character.character_prompt,
    "character_image": character.character_image,
    "voice_path": voice_info.voice_path,
    "voice_speaker": voice_info.voice_speaker,
  }

@router.get("/api/voices/")
def get_voices(db: Session = Depends(get_db)):
  voices = db.query(Voice).all()
  return [{"voice_idx": str(voice.voice_idx), "voice_speaker": voice.voice_speaker} for voice in voices]