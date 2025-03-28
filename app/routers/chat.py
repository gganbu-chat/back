from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.sql import func
from sqlalchemy.orm import Session
from typing import List
import os
import uuid
import json
import asyncio
import websockets

from app.core.config import settings
from app.database.session import get_db
from app.schemas.chat import CreateRoomSchema, MessageSchema
from app.models.models import ChatRoom, ChatLog, Character, CharacterPrompt, Image, ImageMapping
from app.utils.common_function import clean_json_string

router = APIRouter()

WS_SERVER_DOMAIN = settings.WS_SERVER_DOMAIN
UPLOAD_DIR = "app/uploads/characters/"  # 캐릭터 이미지 파일 저장 경로
os.makedirs(UPLOAD_DIR, exist_ok=True) # 디렉토리 생성

# 최근 10개의 대화내역 가져오는 함수
def get_chat_history(db: Session, room_id: str, limit: int = 10) -> str:
  """
  채팅방의 최근 대화 내역을 가져옵니다.
  """
  logs = db.query(ChatLog).filter(
    ChatLog.chat_id == room_id
  ).order_by(ChatLog.end_time.desc()).limit(limit).all()
  
  # 시간순으로 정렬
  logs = logs[::-1]
  
  # 대화 내역을 문자열로 포맷팅
  history = ""
  for log in logs:
    # ChatLog의 log 필드에서 대화 내용 파싱
    log_lines = log.log.split('\n')
    for line in log_lines:
      if 'user:' in line or 'chatbot:' in line:
        history += line + '\n'
  
  return history

# LangChain WebSocket 서버에 데이터를 전송하고 응답을 반환하는 함수
async def send_to_langchain(request_data: dict, room_id: str):
  try:
    uri = f"{WS_SERVER_DOMAIN}/ws/generate/?room_id={room_id}"
    async with websockets.connect(uri) as websocket:
      # 요청 데이터 전송
      await websocket.send(json.dumps(request_data))
      
      # 서버 응답 수신
      response = await websocket.recv()
      return json.loads(response)
  except asyncio.TimeoutError:
    print("WebSocket 응답 시간이 초과되었습니다.")
    raise HTTPException(status_code=504, detail="LangChain 서버 응답 시간 초과.")
  except websockets.exceptions.ConnectionClosedError as e:
    print(f"WebSocket closed with error: {str(e)}")
    raise HTTPException(status_code=500, detail="WebSocket 연결이 닫혔습니다.")
  except Exception as e:
    print(f"Error in send_to_langchain: {str(e)}")
    raise HTTPException(status_code=500, detail="LangChain 서버와 통신 중 오류가 발생했습니다.")







# ------------------------------POST METHOD------------------------------
# 채팅방 생성 API
@router.post("/api/chat-room/", response_model=dict)
def create_chat_room(room: CreateRoomSchema, db: Session = Depends(get_db)):
  try:
    # 트랜잭션 시작
    with db.begin():
      # 각 캐릭터에 대한 최신 char_prompt_id를 가져오는 subquery
      subquery = (
        select(
          CharacterPrompt.char_idx,
          func.max(CharacterPrompt.created_at).label("latest_created_at")
        )
        .group_by(CharacterPrompt.char_idx)
        .subquery()
      )
      # 캐릭터 정보 가져오기
      character_data = (
        db.query(Character, CharacterPrompt)
        .join(subquery, subquery.c.char_idx == Character.char_idx)
        .join(
          CharacterPrompt,
          (CharacterPrompt.char_idx == subquery.c.char_idx) &
          (CharacterPrompt.created_at == subquery.c.latest_created_at)
        )
        .filter(
          Character.char_idx == room.character_id, 
          Character.is_active == True
        )
        .first()
      )
      
      if not character_data:
        raise HTTPException(status_code=404, detail="해당 캐릭터를 찾을 수 없습니다.")
      
      character, prompt = character_data

      # 기존 대화방이 있는지 확인
      existing_room = (
        db.query(ChatRoom)
        .filter(
          ChatRoom.user_idx == room.user_idx,
          ChatRoom.char_prompt_id == prompt.char_prompt_id,
          ChatRoom.is_active == True
        )
        .first()
      )
      
      if existing_room:
        return {
          "room_id": existing_room.chat_id,
          "user_idx": existing_room.user_idx,
          "character_idx": character.char_idx,
          "char_prompt_id": existing_room.char_prompt_id,
          "created_at": existing_room.created_at,
          "user_unique_name": existing_room.user_unique_name,
          "user_introduction": existing_room.user_introduction,
          "chat_exists": True
        }
      
      # 채팅방 ID 생성
      room_id = str(uuid.uuid4())

      # 채팅방 생성
      new_room = ChatRoom(
        chat_id=room_id,
        user_idx=room.user_idx,
        char_prompt_id=prompt.char_prompt_id,
        user_unique_name=room.user_unique_name,
        user_introduction=room.user_introduction,
      )
      
      db.add(new_room)
    
    # 트랜잭션 커밋 (with 블록 종료 시 자동으로 커밋됨)
    db.commit()

    return {
      "room_id": new_room.chat_id,
      "user_idx": new_room.user_idx,
      "character_idx": character.char_idx,
      "char_prompt_id": new_room.char_prompt_id,
      "created_at": new_room.created_at,
      "user_unique_name": new_room.user_unique_name,
      "user_introduction": new_room.user_introduction,
      "chat_exists": False
    }
  except Exception as e:
    print(f"Error creating chat room: {str(e)}")  # 에러 로깅
    db.rollback()  # 트랜잭션 롤백
    raise HTTPException(status_code=500, detail=f"채팅방 생성 중 오류가 발생했습니다: {str(e)}")


# 채팅 전송 및 캐릭터 응답 - LangChain 서버 이용
@router.post("/api/chat/{room_id}")
async def query_langchain(room_id: str, message: MessageSchema, db: Session = Depends(get_db)):
  """
  LangChain 서버에 요청을 보내고 응답을 처리합니다.
  """
  try:
    chat_data = (
      db.query(ChatRoom, CharacterPrompt, Character)
      .join(CharacterPrompt, ChatRoom.char_prompt_id == CharacterPrompt.char_prompt_id)
      .join(Character, CharacterPrompt.char_idx == Character.char_idx)
      .filter(ChatRoom.chat_id == room_id, ChatRoom.is_active == True)
      .first()
    )

    if not chat_data:
      raise HTTPException(status_code=404, detail="해당 채팅방 정보를 찾을 수 없습니다.")
    
    chat, prompt, character = chat_data

    if prompt:
      example_dialogues = [json.loads(clean_json_string(dialogue)) if dialogue else {} for dialogue in prompt.example_dialogues] if prompt.example_dialogues else []
      nicknames = json.loads(character.nicknames) if character.nicknames else {'30': '', '70': '', '100': ''}
    else:
      # 기본값 설정
      example_dialogues = []
      nicknames = {'30': '', '70': '', '100': ''}

    # --------------------대화 내역 가져오기--------------------
    chat_history = get_chat_history(db, room_id)
    # print("Chat History being sent to LangChain:", chat_history)

    # LangChain 서버로 보낼 요청 데이터 준비
    request_data = {
      "user_message": message.content,
      "character_name": character.char_name, # 캐릭터 이름
      "nickname": nicknames, # 호감도에 따른 호칭 명
      "user_unique_name": chat.user_unique_name, # 캐릭터가 사용자에게 부르는 이름 (nickname보다 우선순위)
      "user_introduction": chat.user_introduction, # 캐릭터한테 사용자를 소개하는 글
      "favorability": chat.favorability, # 호감도
      "character_appearance": prompt.character_appearance, # 캐릭터 외형
      "character_personality": prompt.character_personality, # 캐릭터 성격
      "character_background": prompt.character_background, # 캐릭터 배경
      "character_speech_style": prompt.character_speech_style, # 캐릭터 말투
      "example_dialogues": example_dialogues, # 예시 대화
      "chat_history": chat_history # 채팅 기록
    }

    # print("Sending request to LangChain:", request_data)  # 디버깅용

    # LangChain 서버와 WebSocket 통신
    response_data = await send_to_langchain(request_data, room_id)

    bot_response_text = response_data.get("text", "openai_api 에러가 발생했습니다.")
    predicted_emotion = response_data.get("emotion", "Neutral")
    updated_favorability = response_data.get("favorability", chat.favorability)

    # 캐릭터 상태 업데이트
    chat.favorability = updated_favorability
    # 데이터베이스에 업데이트된 호감도 반영
    db.commit()
    # room.character_emotion = predicted_emotion (기분은 어떻게???)

    return {
      "user": message.content,
      "bot": bot_response_text,
      "updated_favorability": updated_favorability,
      "emotion": predicted_emotion
    }

  except Exception as e:
    print(f"Error in query_langchain: {str(e)}")  # 디버깅용
    raise HTTPException(status_code=500, detail=str(e))










# ------------------------------GET METHOD------------------------------
# 모든 채팅방 목록 조회 API
@router.get("/api/chat-room/", response_model=List[dict])
def get_all_chat_rooms(request: Request, db: Session = Depends(get_db)):
  """
  모든 채팅방 목록을 반환하는 API 엔드포인트.
  각 채팅방에 연결된 캐릭터 정보 및 이미지를 포함.
  """
  rooms = (
    db.query(ChatRoom, Character, CharacterPrompt, Image.file_path)
    .join(CharacterPrompt, CharacterPrompt.char_prompt_id == ChatRoom.char_prompt_id)
    .join(Character, Character.char_idx == CharacterPrompt.char_idx)
    .outerjoin(ImageMapping, ImageMapping.char_idx == Character.char_idx)
    .outerjoin(Image, Image.img_idx == ImageMapping.img_idx)
    .filter(Character.is_active == True, ChatRoom.is_active == True)
    .all()
  )

  base_url = f"{request.base_url.scheme}://{request.base_url.netloc}"
  result = []
  for room, character, prompt, image_path in rooms:
    # 이미지 경로를 URL로 변환
    image_url = f"{base_url}/static/{os.path.basename(image_path)}" if image_path else None
    result.append({
      "room_id": room.chat_id,
      "character_name": character.char_name,
      "char_description": character.char_description,
      "character_appearance": prompt.character_appearance,
      "character_personality": prompt.character_personality,
      "character_background": prompt.character_background,
      "character_speech_style": prompt.character_speech_style,
      "room_created_at": room.created_at,
      "character_image": image_url,  # 전체 URL 반환
    })
  return result


# 특정 유저가 생성한 채팅방 목록 조회 API
@router.get("/api/chat-room/user/{user_idx}", response_model=List[dict])
def get_user_chat_rooms(user_idx: int, request: Request, db: Session = Depends(get_db)):
  """
  특정 사용자가 생성한 채팅방 목록을 반환하는 API 엔드포인트.
  각 채팅방에 연결된 캐릭터 정보 및 이미지를 포함.
  """
  rooms = (
    db.query(ChatRoom, Character, CharacterPrompt, Image.file_path)
    .join(CharacterPrompt, CharacterPrompt.char_prompt_id == ChatRoom.char_prompt_id)
    .join(Character, Character.char_idx == CharacterPrompt.char_idx)
    .outerjoin(ImageMapping, ImageMapping.char_idx == Character.char_idx)
    .outerjoin(Image, Image.img_idx == ImageMapping.img_idx)
    .filter(ChatRoom.user_idx == user_idx, Character.is_active == True, ChatRoom.is_active == True)
    .all()
  )

  base_url = f"{request.base_url.scheme}://{request.base_url.netloc}"
  result = []
  for room, character, prompt, image_path in rooms:
    # 이미지 경로를 URL로 변환
    image_url = f"{base_url}/static/{os.path.basename(image_path)}" if image_path else None
    result.append({
      "room_id": room.chat_id,
      "character_name": character.char_name,
      "char_description": character.char_description,
      "character_appearance": prompt.character_appearance,
      "character_personality": prompt.character_personality,
      "character_background": prompt.character_background,
      "character_speech_style": prompt.character_speech_style,
      "room_created_at": room.created_at,
      "character_image": image_url,  # 이미지 URL 반환
    })
  return result


# 채팅 로그 반환 API
@router.get("/api/chat/{room_id}")
def get_chat_logs(room_id: str, db: Session = Depends(get_db)):
  """
  특정 채팅방의 메시지 로그를 반환하는 API 엔드포인트.
  """
  logs = (
    db.query(ChatLog)
    .filter(ChatLog.chat_id == room_id)
    .order_by(ChatLog.start_time)
    .all()
  )
  return [
    {
      "session_id": log.session_id,
      "log": log.log,
      "start_time": log.start_time,
      "end_time": log.end_time,
    }
    for log in logs
  ]



  




# ------------------------------DELETE METHOD------------------------------
# 채팅방 삭제 API
@router.delete("/api/chat-room/{room_id}")
def delete_chat_room(room_id: str, db: Session = Depends(get_db)):
  try:
    # ChatRoom 상태값 변경
    room = db.query(ChatRoom).filter(ChatRoom.chat_id == room_id).first()
    if not room:
      raise HTTPException(status_code=404, detail="해당 채팅방을 찾을 수 없습니다.")
    
    # is_active 업데이트
    room.is_active = False
    db.commit()
    return {"message": "채팅방이 성공적으로 비활성화되었습니다."}
  except Exception as e:
    db.rollback()
    print(f"Error deleting chat room: {str(e)}")
    raise HTTPException(status_code=500, detail=f"채팅방 삭제 중 오류: {str(e)}")