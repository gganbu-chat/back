from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Request, Form
from sqlalchemy import select
from sqlalchemy.sql import func
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List, Optional
import os
import uuid
import json

from app.database.session import get_db
from app.schemas.character import CharacterResponseSchema, CreateCharacterSchema
from app.models.models import Character, CharacterPrompt, ChatRoom, Image, ImageMapping, Tag, Friend, Field as DBField
from app.utils.common_function import clean_json_string

router = APIRouter()

UPLOAD_DIR = "app/uploads/characters/"  # 캐릭터 이미지 파일 저장 경로

# ------------------------------POST METHOD------------------------------
# 캐릭터 생성 API
@router.post("/api/characters/", response_model=CharacterResponseSchema)
async def create_character(
  character_image: UploadFile = File(...),
  character_data: str = Form(...),
  db: Session = Depends(get_db)
):
  try:
    with db.begin():
      print("Received character data:", character_data)  # 디버깅용 로그
      character_dict = json.loads(character_data)
      character = CreateCharacterSchema(**character_dict)

      # 새 캐릭터 객체 생성
      new_character = Character(
        character_owner=character.character_owner,
        field_idx=character.field_idx,
        voice_idx=character.voice_idx,
        char_name=character.char_name,
        char_description=character.char_description,
        nicknames=json.dumps(character.nicknames)
      )
      db.add(new_character)
      db.flush()  # `new_character.char_idx`를 사용하기 위해 flush 실행
      
      # 캐릭터 프롬프트 생성
      new_prompt = CharacterPrompt(
        char_idx=new_character.char_idx,
        character_appearance=character.character_appearance,
        character_personality=character.character_personality,
        character_background=character.character_background,
        character_speech_style=character.character_speech_style,
        example_dialogues=(
          [json.dumps(dialogue, ensure_ascii=False) for dialogue in character.example_dialogues]
          if character.example_dialogues else None
        ),
      )

      db.add(new_prompt)

      # 이미지 파일 저장
      file_extension = character_image.filename.split(".")[-1]
      timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
      unique_filename = f"{timestamp}_{uuid.uuid4().hex}.{file_extension}"
      file_path = os.path.join(UPLOAD_DIR, unique_filename)

      # 파일 저장
      with open(file_path, "wb") as f:
        f.write(await character_image.read())

        # 이미지 테이블에 저장
      new_image = Image(file_path=file_path)
      db.add(new_image)
      db.flush()  # `new_image.img_idx` 사용하기 위해 flush 실행
      
      # 이미지와 캐릭터 매핑
      image_mapping = ImageMapping(
        char_idx=new_character.char_idx,
        img_idx=new_image.img_idx
      )
      db.add(image_mapping)

      if character.tags:
        for tag in character.tags:
          new_tag = Tag(
            char_idx=new_character.char_idx,
            tag_name=tag["tag_name"],
            tag_description=tag["tag_description"]
          )
          db.add(new_tag)

    # 트랜잭션 커밋 (with 블록 종료 시 자동으로 커밋됨, 명시적으로 작성)
    db.commit()

    return CharacterResponseSchema(
        char_idx=new_character.char_idx,
        char_name=new_character.char_name,
        char_description=new_character.char_description,
        created_at=new_character.created_at.isoformat(),
        nicknames=json.loads(new_character.nicknames),
        character_appearance=new_prompt.character_appearance,
        character_personality=new_prompt.character_personality,
        character_background=new_prompt.character_background,
        character_speech_style=new_prompt.character_speech_style,
        example_dialogues=[
            json.loads(dialogue) for dialogue in new_prompt.example_dialogues
        ] if new_prompt.example_dialogues else None,
        character_image=file_path
    )
  except Exception as e:
    print(f"Error in create_character: {str(e)}")
    db.rollback() # 트랜잭션 롤백
    raise HTTPException(status_code=500, detail=str(e))















# ------------------------------GET METHOD------------------------------
# 모든 캐릭터 목록 조회 API
@router.get("/api/characters", response_model=List[dict])
def get_characters(db: Session = Depends(get_db), request: Request = None):
  # 각 캐릭터에 대한 최신 char_prompt_id를 가져오는 subquery
  subquery = (
    select(
      CharacterPrompt.char_idx,
      func.max(CharacterPrompt.created_at).label("latest_created_at")
    )
    .group_by(CharacterPrompt.char_idx)
    .subquery()
  )

  # 캐릭터를 최신 프롬프트와 join하고 이미지 정보를 포함하는 query
  query = (
    db.query(Character, CharacterPrompt, Image.file_path)
    .join(subquery, subquery.c.char_idx == Character.char_idx)
    .join(
      CharacterPrompt,
      (CharacterPrompt.char_idx == subquery.c.char_idx) &
      (CharacterPrompt.created_at == subquery.c.latest_created_at)
    )
    .outerjoin(ImageMapping, ImageMapping.char_idx == Character.char_idx)
    .outerjoin(Image, Image.img_idx == ImageMapping.img_idx)
    .filter(Character.is_active == True)  # is_active가 True인 캐릭터만 가져오기
  )

  characters_info = query.all()
  base_url = f"{request.base_url.scheme}://{request.base_url.netloc}" if request else ""
  results = []

  for char, prompt, image_path in characters_info:
    # 팔로워 수 구하기
    follower_count = (
      db.query(func.count(Friend.friend_idx))
      .filter(Friend.char_idx == char.char_idx, Friend.is_active == True)
      .scalar()
    )
    print(f"Character: {char.char_name}, field_idx: {char.field_idx}, type: {type(char.field_idx)}")
    if prompt:
      example_dialogues = [json.loads(clean_json_string(dialogue)) if dialogue else {} for dialogue in prompt.example_dialogues] if prompt.example_dialogues else []
      nicknames = json.loads(char.nicknames) if char.nicknames else {'30': '', '70': '', '100': ''}
    else:
      # 기본값 설정
      example_dialogues = []
      nicknames = {'30': '', '70': '', '100': ''}

    # 이미지 URL 생성
    image_url = f"{base_url}/static/{os.path.basename(image_path)}" if image_path else None

    tags = db.query(Tag).filter(
      Tag.char_idx == char.char_idx,
      Tag.is_deleted == False
    ).all()
    
    tag_list = [{"tag_name": tag.tag_name, "tag_description": tag.tag_description} for tag in tags]

    results.append({
      "char_idx": char.char_idx,
      "char_name": char.char_name,
      "char_description": char.char_description,
      "created_at": char.created_at.isoformat(),
      "nicknames": nicknames,
      "character_appearance": prompt.character_appearance if prompt else "",
      "character_personality": prompt.character_personality if prompt else "",
      "character_background": prompt.character_background if prompt else "",
      "character_speech_style": prompt.character_speech_style if prompt else "",
      "example_dialogues": example_dialogues,
      "tags": tag_list,
      "character_image": image_url,
      "field_idx": char.field_idx,
      "follower_count": follower_count
    })

  return results


# 특정 캐릭터 조회
@router.get("/api/characters/{char_idx}", response_model=dict)
def get_character_by_id(char_idx: int, db: Session = Depends(get_db), request: Request = None):
    character_data = (
        db.query(Character, CharacterPrompt, Image.file_path, DBField.field_category)
        .join(CharacterPrompt, Character.char_idx == CharacterPrompt.char_idx)
        .outerjoin(ImageMapping, ImageMapping.char_idx == Character.char_idx)
        .outerjoin(Image, Image.img_idx == ImageMapping.img_idx)
        .join(DBField, DBField.field_idx == Character.field_idx)
        .filter(Character.char_idx == char_idx, Character.is_active == True)
        .first()
    )

    follower_count = db.query(Friend).filter(Friend.char_idx == char_idx, Friend.is_active == True).count()

    if not character_data:
        raise HTTPException(status_code=404, detail="해당 캐릭터를 찾을 수 없습니다.")
    
    character, prompt, image_path, field_category = character_data

    # 이미지 URL 생성
    base_url = f"{request.base_url.scheme}://{request.base_url.netloc}" if request else ""
    image_url = f"{base_url}/static/{os.path.basename(image_path)}" if image_path else None

    # JSON으로 저장된 호칭을 파싱
    nicknames = json.loads(character.nicknames) if character.nicknames else {}

    return {
        "char_idx": character.char_idx,
        "char_name": character.char_name,
        "char_description": character.char_description,
        "created_at": character.created_at.isoformat(),
        "character_appearance": prompt.character_appearance,
        "character_personality": prompt.character_personality,
        "character_background": prompt.character_background,
        "character_speech_style": prompt.character_speech_style,
        "example_dialogues": prompt.example_dialogues,
        "tags": [
            {"tag_name": tag.tag_name, "tag_description": tag.tag_description}
            for tag in db.query(Tag).filter(Tag.char_idx == character.char_idx, Tag.is_deleted == False).all()
        ],
        "character_image": image_url,
        "field_idx": character.field_idx,  # 필드 카테고리 추가
        "nicknames": nicknames,  # 호칭 정보 추가
        "follower_count": follower_count
    }


# 특정 유저가 생성한 캐릭터 목록 조회 API
@router.get("/api/characters/user/{user_id}", response_model=List[dict])
def get_characters(user_id: int, db: Session = Depends(get_db), request: Request = None):
  # 각 캐릭터에 대한 최신 char_prompt_id를 가져오는 subquery
  subquery = (
    select(
      CharacterPrompt.char_idx,
      func.max(CharacterPrompt.created_at).label("latest_created_at")
    )
    .group_by(CharacterPrompt.char_idx)
    .subquery()
  )

  # 캐릭터를 최신 프롬프트와 join하고 이미지 정보를 포함하는 query
  query = (
    db.query(Character, CharacterPrompt, Image.file_path)
    .join(subquery, subquery.c.char_idx == Character.char_idx)
    .join(
      CharacterPrompt,
      (CharacterPrompt.char_idx == subquery.c.char_idx) &
      (CharacterPrompt.created_at == subquery.c.latest_created_at)
    )
    .outerjoin(ImageMapping, ImageMapping.char_idx == Character.char_idx)
    .outerjoin(Image, Image.img_idx == ImageMapping.img_idx)
    .filter(
      Character.is_active == True,
      Character.character_owner == user_id
    )
  )

  characters_info = query.all()

  base_url = f"{request.base_url.scheme}://{request.base_url.netloc}" if request else ""
  results = []
  for char, prompt, image_path in characters_info:
    if prompt:
      example_dialogues = [json.loads(clean_json_string(dialogue)) if dialogue else {} for dialogue in prompt.example_dialogues] if prompt.example_dialogues else []
      nicknames = json.loads(char.nicknames) if char.nicknames else {'30': '', '70': '', '100': ''}
    else:
      # 기본값 설정
      example_dialogues = []
      nicknames = {'30': '', '70': '', '100': ''}

    # 이미지 URL 생성
    image_url = f"{base_url}/static/{os.path.basename(image_path)}" if image_path else None

    results.append({
      "char_idx": char.char_idx,
      "char_name": char.char_name,
      "char_description": char.char_description,
      "created_at": char.created_at.isoformat(),
      "nicknames": nicknames,
      "character_appearance": prompt.character_appearance if prompt else "",
      "character_personality": prompt.character_personality if prompt else "",
      "character_background": prompt.character_background if prompt else "",
      "character_speech_style": prompt.character_speech_style if prompt else "",
      "example_dialogues": example_dialogues,
      "character_image": image_url,
    })
  return results


# 특정 채팅방의 캐릭터 정보 조회 API
@router.get("/api/chat-room-info/{room_id}")
def get_chat_room_info(room_id: str, db: Session = Depends(get_db)):
  """
  특정 채팅방에 연결된 캐릭터 및 Voice 정보를 반환하는 API 엔드포인트.
  """
  try:
    chat_data = (
      db.query(ChatRoom, CharacterPrompt, Character)
      # db.query(ChatRoom, CharacterPrompt, Character, Voice)
      .join(CharacterPrompt, ChatRoom.char_prompt_id == CharacterPrompt.char_prompt_id)
      .join(Character, CharacterPrompt.char_idx == Character.char_idx)
      # .outerjoin(Voice, Character.voice_idx == Voice.voice_idx)
      .filter(ChatRoom.chat_id == room_id, ChatRoom.is_active == True)
      .first()
    )

    if not chat_data:
      raise HTTPException(status_code=404, detail="해당 채팅방 정보를 찾을 수 없습니다.")
    
    chat, prompt, character = chat_data
    # chat, prompt, character, voice = chat_data

    return {
      "chat_id" : chat.chat_id,
      "user_idx": chat.user_idx,
      "favorability": chat.favorability,
      "user_unique_name": chat.user_unique_name,
      "user_introduction": chat.user_introduction,
      "room_created_at": chat.created_at.isoformat(),
      "char_idx": character.char_idx,
      "char_name": character.char_name,
      "char_description": character.char_description,
      "character_appearance": prompt.character_appearance,
      "character_personality": prompt.character_personality,
      "character_background": prompt.character_background,
      "character_speech_style": prompt.character_speech_style,
      "example_dialogues": prompt.example_dialogues,
      # "voice_path": voice.voice_path,
      # "voice_speaker": voice.voice_speaker,
    }
  except Exception as e:
    print(f"Error fetching chat room info: {str(e)}")
    raise HTTPException(status_code=500, detail=f"채팅방 정보를 가져오는 중 오류가 발생했습니다: {str(e)}")


# 캐릭터 이름과 설명으로 검색해서 목록을 반환하는 API
@router.get("/api/characters/search", response_model=list)
def search_characters(query: str, db: Session = Depends(get_db)):

  characters = db.query(Character).filter(
    (Character.char_name.like(f"%{query}%")) | 
    (Character.char_description.like(f"%{query}%"))
  ).all()

  if not characters:
    raise HTTPException(status_code=404, detail="검색 결과가 없습니다.")

  return [
    {"id": char.char_idx, "name": char.char_name, "description": char.char_description}
    for char in characters
  ]


# 특정 유저가 팔로우한 캐릭터 목록 반환하는 API
@router.get("/api/friends/{user_idx}/characters", response_model=List[dict])
def get_followed_characters(user_idx: int, db: Session = Depends(get_db), request: Request = None):
  subquery = (
    select(
      CharacterPrompt.char_idx,
      func.max(CharacterPrompt.created_at).label("latest_created_at")
    )
    .group_by(CharacterPrompt.char_idx)
    .subquery()
  )

  # Friend 테이블을 사용하여 특정 사용자가 팔로우한 캐릭터 조회
  query = (
    db.query(Character, CharacterPrompt, Image.file_path)
    .join(subquery, subquery.c.char_idx == Character.char_idx)
    .join(
      CharacterPrompt,
      (CharacterPrompt.char_idx == subquery.c.char_idx) &
      (CharacterPrompt.created_at == subquery.c.latest_created_at)
    )
    .outerjoin(ImageMapping, ImageMapping.char_idx == Character.char_idx)
    .outerjoin(Image, Image.img_idx == ImageMapping.img_idx)
    .join(Friend, Friend.char_idx == Character.char_idx)
    .filter(
      Friend.user_idx == user_idx,
      Friend.is_active == True,
      Character.is_active == True
    )
  )

  followed_characters = query.all()
  base_url = f"{request.base_url.scheme}://{request.base_url.netloc}" if request else ""
  results = []

  for char, prompt, image_path in followed_characters:
    image_url = f"{base_url}/static/{os.path.basename(image_path)}" if image_path else None

    results.append({
      "char_idx": char.char_idx,
      "character_owner": char.character_owner,
      "char_name": char.char_name,
      "char_description": char.char_description,
      "created_at": char.created_at.isoformat(),
      "character_appearance": prompt.character_appearance if prompt else "",
      "character_personality": prompt.character_personality if prompt else "",
      "character_background": prompt.character_background if prompt else "",
      "character_speech_style": prompt.character_speech_style if prompt else "",
      "character_image": image_url,
    })

  return results
















# ------------------------------PUT METHOD------------------------------
# 특정 캐릭터 수정
'''
user_idx 확인해야 하는 로직 추가해야 함
'''
@router.put("/api/characters/{char_idx}")
async def update_character(
  char_idx: int,
  character_image: Optional[UploadFile] = None,
  character_data: str = Form(...),
  db: Session = Depends(get_db)
):
  try:
    print(f"Received character data for update: {character_data}")  # 로깅 추가
    with db.begin():
      character_dict = json.loads(character_data)
      print(f"Parsed character dict: {character_dict}")  # 로깅 추가
      
      # 필수 필드 확인
      required_fields = ['character_owner', 'field_idx', 'voice_idx', 'char_name', 'char_description']
      for field in required_fields:
        if field not in character_dict:
          raise ValueError(f"Missing required field: {field}")
      
      # Pydantic 스키마 검증
      character = CreateCharacterSchema(**character_dict)
      print(f"Created schema object: {character}")  # 로깅 추가

      # 기존 캐릭터 조회
      existing_character = db.query(Character).filter(Character.char_idx == char_idx).first()
      if not existing_character:
        raise HTTPException(status_code=404, detail="캐릭터를 찾을 수 없습니다.")

      print(f"Found existing character: {existing_character.char_idx}")  # 로깅 추가

      # 캐릭터 기본 정보 업데이트
      existing_character.field_idx = character.field_idx
      existing_character.voice_idx = character.voice_idx
      existing_character.char_name = character.char_name
      existing_character.char_description = character.char_description
      existing_character.nicknames = json.dumps(character.nicknames)

      # 새로운 프롬프트 생성
      new_prompt = CharacterPrompt(
        char_idx=char_idx,
        character_appearance=character.character_appearance,
        character_personality=character.character_personality,
        character_background=character.character_background,
        character_speech_style=character.character_speech_style,
        example_dialogues=(
          [json.dumps(dialogue, ensure_ascii=False) for dialogue in character.example_dialogues]
          if character.example_dialogues else None
        ),
      )
      db.add(new_prompt)
      print("Added new prompt")  # 로깅 추가

      # 이미지 업데이트 로직
      if character_image:
        print("Updating character image...")  # 로깅 추가

        # 기존 이미지 매핑 및 이미지 가져오기
        existing_image_mapping = db.query(ImageMapping).filter(
          ImageMapping.char_idx == char_idx,
          ImageMapping.is_active == True
        ).first()

        if existing_image_mapping:
          # 기존 이미지 레코드를 가져옴
          existing_image = db.query(Image).filter(
            Image.img_idx == existing_image_mapping.img_idx
          ).first()

          if existing_image:
            # 새 이미지 파일 저장
            file_extension = character_image.filename.split(".")[-1]
            timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
            unique_filename = f"{timestamp}_{uuid.uuid4().hex}.{file_extension}"
            file_path = os.path.join(UPLOAD_DIR, unique_filename)

            # 파일 저장
            with open(file_path, "wb") as f:
                f.write(await character_image.read())

            # 기존 이미지 경로 교체
            existing_image.file_path = file_path
            print("Image file path updated successfully.")  # 로깅 추가

        else:
          # 기존 이미지가 없는 경우 새 이미지 레코드를 생성
          file_extension = character_image.filename.split(".")[-1]
          timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
          unique_filename = f"{timestamp}_{uuid.uuid4().hex}.{file_extension}"
          file_path = os.path.join(UPLOAD_DIR, unique_filename)

          # 파일 저장
          with open(file_path, "wb") as f:
              f.write(await character_image.read())

          new_image = Image(file_path=file_path)
          db.add(new_image)
          db.flush()

          # 새로운 이미지 매핑 추가
          new_mapping = ImageMapping(
              char_idx=char_idx,
              img_idx=new_image.img_idx,
              is_active=True
          )
          db.add(new_mapping)

      # 태그 업데이트
      if character.tags:
        print("Updating tags")  # 로깅 추가

        # 기존 태그 비활성화
        existing_tags = db.query(Tag).filter(Tag.char_idx == char_idx).all()
        for tag in existing_tags:
          tag.is_deleted = True

        # 새로운 태그 추가
        for tag in character.tags:
          new_tag = Tag(
            char_idx=char_idx,
            tag_name=tag["tag_name"],
            tag_description=tag["tag_description"]
          )
          db.add(new_tag)
        print("Successfully updated tags")  # 로깅 추가

    db.commit()
    return {"message": "캐릭터가 성공적으로 업데이트되었습니다."}

  except Exception as e:
    print(f"Detailed error in update_character: {str(e)}")  # 상세 에러 로깅
    print(f"Error type: {type(e)}")  # 에러 타입 출력
    import traceback
    print(f"Full traceback: {traceback.format_exc()}")  # 전체 스택 트레이스 출력
    db.rollback()
    raise HTTPException(status_code=500, detail=str(e))
















# ------------------------------DELETE METHOD------------------------------
# 캐릭터 삭제 API
@router.delete("/api/characters/{char_idx}")
def delete_character(char_idx: int, db: Session = Depends(get_db)):
    """
    특정 캐릭터를 삭제(숨김처리)하는 API 엔드포인트.
    캐릭터의 is_active 필드를 False로 변경합니다.
    """
    # 캐릭터 인덱스를 기준으로 데이터베이스에서 검색
    character = db.query(Character).filter(Character.char_idx == char_idx).first()
    if not character:
        raise HTTPException(status_code=404, detail="해당 캐릭터를 찾을 수 없습니다.")

    # 캐릭터 숨김 처리
    character.is_active = False
    db.commit()
    return {"message": f"캐릭터 {char_idx}이(가) 성공적으로 삭제되었습니다."}


'''
뭘 검색하는지 모르겠음 (일단 주석)
'''
# @router.get("/api/characters/search/{character_idx}", response_model=dict)
# def get_character_by_index(character_idx: int, db: Session = Depends(get_db)):
#   print(f"Requested character_idx: {character_idx}")
#   character = db.query(
#     Character.char_idx, Character.char_name, Character.char_description
#   ).filter(Character.char_idx == character_idx).first()

#   if not character:
#     raise HTTPException(status_code=404, detail=f"캐릭터 '{character_idx}'를 찾을 수 없습니다.")

#   return {"id": character[0], "name": character[1], "description": character[2]}



'''
필요 없어 보이는 API
'''
# # 캐릭터 목록 조회 API - 필드 기준 조회
# @router.get("/api/characters/field", response_model=List[CharacterCardResponseSchema])
# def get_characters_by_field(
#     fields: Optional[List[int]] = Depends(parse_fields),
#     limit: int = Query(default=10),
#     db: Session = Depends(get_db),
#     request: Request = None
# ):
#     """
#     필드 컬럼 값이 없으면 전체 데이터를 반환합니다.
#     fields가 주어지면 해당 필드에 해당하는 캐릭터만 반환합니다.
#     limit 값은 기본적으로 10개입니다.
#     """
#     # 기본 쿼리 작성
#     query = (
#         db.query(Character, Image.file_path)
#         .outerjoin(ImageMapping, ImageMapping.char_idx == Character.char_idx)
#         .outerjoin(Image, Image.img_idx == ImageMapping.img_idx)
#         .filter(Character.is_active == True)
#     )

#     # fields 필터링 적용
#     if fields:
#         query = query.filter(Character.field_idx.in_(fields))

#     # limit 적용 및 데이터 가져오기
#     characters_info = query.limit(limit).all()

#     # 요청 URL로부터 base URL 생성
#     base_url = f"{request.base_url.scheme}://{request.base_url.netloc}" if request else ""

#     # 결과 리스트 생성
#     results = []
#     for char, image_path in characters_info:
#         # 이미지 URL 생성
#         image_url = f"{base_url}/static/{os.path.basename(image_path)}" if image_path else None

#         # 결과에 추가
#         results.append({
#             "char_idx": char.char_idx,
#             "char_name": char.char_name,
#             "char_description": char.char_description,
#             "created_at": char.created_at.isoformat(),
#             "field_idx": char.field_idx,
#             "character_owner": char.character_owner,
#             "character_image": image_url,
#         })

#     return results


# # 캐릭터 목록 조회 API - 태그 기준 조회
# @router.get("/api/characters/tag", response_model=List[CharacterCardResponseSchema])
# def get_characters_by_tag(
#     tags: Optional[List[str]] = Depends(parse_fields), 
#     limit: int = Query(default=10),
#     db: Session = Depends(get_db)):
#     """
#     태그 값이 없으면 전체 데이터를 반환합니다.
#     """
#     query = db.query(Character).filter(Character.is_active == True)
#     if tags:  # 태그 값이 주어지면 필터링
#         query = query.join(Character.tags).filter(Tag.name.in_(tags))
#     characters = query.limit(limit).all()  # limit 적용

#     return characters

# # 캐릭터 목록 조회 API - 최근 생성 순 조회
# @router.get("/api/characters/new", response_model=List[CharacterCardResponseSchema])
# def get_new_characters(limit: Optional[int] = 10, db: Session = Depends(get_db)):
#     """
#     최근 생성된 캐릭터를 조회합니다.
#     limit 값이 없으면 기본적으로 10개의 데이터를 반환합니다.
#     """
#     characters = db.query(Character).filter(Character.is_active == True).order_by(Character.created_at.desc()).limit(limit).all()
    
#     return characters




# 필드 항목 가져오기 API
@router.get("/api/fields/")
def get_fields(db: Session = Depends(get_db)):
  """
  필드 항목을 반환하는 API 엔드포인트.
  """
  try:
    fields = db.query(DBField).all()  # DBField로 변경
    return [{"field_idx": field.field_idx, "field_category": field.field_category} for field in fields]
  except Exception as e:
    print(f"Error in get_fields: {str(e)}")  # 에러 로깅 추가
    raise HTTPException(status_code=500, detail=str(e))

# 태그 항목 가져오기 API
@router.get("/api/tags")
def get_tags(db: Session = Depends(get_db)):
  tags = db.query(Tag).distinct(Tag.tag_name).all()
  return [{"tag_idx": tag.tag_idx, "tag_name": tag.tag_name} for tag in tags]