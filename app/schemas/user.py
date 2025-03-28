from typing import Optional
from pydantic import BaseModel

class SignupRequest(BaseModel):
  nickname: str
  user_id: str
  profile_img: Optional[str] = None
  password: str


class UserResponse(BaseModel):
  user_idx: int
  nickname: str
  user_id: str
  profile_img: Optional[str] = None

  class Config:
    from_attributes = True 


class SignInRequest(BaseModel):
  user_id: str
  password: str

class FollowRequest(BaseModel):
    user_idx: int
    char_idx: int