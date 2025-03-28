from typing import Optional
from pydantic import BaseModel

# 채팅방 생성 요청 스키마
class CreateRoomSchema(BaseModel):
  """
  채팅방 생성을 위한 Pydantic 스키마
  """
  user_idx: int
  character_id: int
  user_unique_name: Optional[str] = None
  user_introduction: Optional[str] = None

  class Config:
    orm_mode = True


# 메시지 전송 스키마
class MessageSchema(BaseModel):
  """
  메시지 전송을 위한 Pydantic 스키마.
  클라이언트가 전송해야 하는 필드를 정의
  """
  sender: str # 메세지 전송자 ( user 또는 캐릭터 이름 )
  content: str # 메세지 내용