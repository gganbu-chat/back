from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Body
from fastapi.security import OAuth2PasswordBearer
from fastapi.responses import FileResponse
from jose import jwt, JWTError
from wordcloud import WordCloud
from collections import Counter
import os
import re
import shutil

from app.core.config import Settings
from app.database.session import get_db
from app.models.models import User, ChatRoom, ChatLog, Friend
from app.schemas.user import SignupRequest, UserResponse, FollowRequest

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
SECRET_KEY = Settings.SECRET_KEY
ALGORITHM = "HS256"
WORDCLOUD_UPLOAD_DIR = "app/uploads/wordcloud"

router = APIRouter()


@router.get("/users/{user_id}", response_model=UserResponse)
def get_user(user_id: int, db: Session = Depends(get_db)):
  try:
    # 사용자 조회
    user = db.query(User).filter(User.user_idx == user_id).first()
    if not user:
      raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다!")
      
    # 사용자 반환
    return user
  except Exception as e:
    print(f"사용자 조회 중 오류: {e}")  # 디버깅용 로그
    raise HTTPException(status_code=500, detail=f"서버 내부 오류: {e}")


@router.put("/users/{user_id}", response_model=UserResponse)
def update_user(user_id: str, user_update: SignupRequest, db: Session = Depends(get_db)):
  try:
    # 사용자 조회
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
      raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다!")

    # 사용자 정보 업데이트
    for key, value in user_update.dict(exclude_unset=True).items():
      setattr(user, key, value)
    
    db.commit()
    db.refresh(user)

    # 업데이트된 사용자 반환
    return user
  except Exception as e:
    print(f"사용자 업데이트 중 오류: {e}")  # 디버깅용 로그
    raise HTTPException(status_code=500, detail=f"서버 내부 오류: {e}")


# 회원 탈퇴 API 
'''
수정 필요 -> 유저를 삭제하는 것이 아닌 상태값 변경하여 관리
'''
@router.delete("/users/{user_id}", response_model=dict)
def delete_user(user_id: str, db: Session = Depends(get_db)):
  try:
    # 사용자 조회
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
      raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다!")

    # 사용자 삭제
    db.delete(user)
    db.commit()

    # 삭제 완료 메시지 반환
    return {"message": f"사용자 ID {user_id}가 삭제되었습니다."}
  except Exception as e:
    print(f"사용자 삭제 중 오류: {e}")  # 디버깅용 로그
    raise HTTPException(status_code=500, detail=f"서버 내부 오류: {e}")




#######################################################
#######################################################
#######################################################
#######################################################
#######################################################
#######################################################
#######################################################
#######################################################
'''
수정 필요 -> 회원정보 가져오는 단계에서 프로필 사진 함께 가져오도록 수정해야 함
'''
@router.get("/get-profile-img/{user_id}/", response_model=dict)
def get_profile_img(user_id: str, db: Session = Depends(get_db)):
  try:
    # 사용자 조회
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
      raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다!")

    # 프로필 사진 확인
    if not user.profile_img:
      raise HTTPException(status_code=404, detail="프로필 사진이 등록되지 않았습니다.")

    # 성공 응답 반환
    return {
      "message": "사용자의 프로필 사진을 조회했습니다.",
      "profile_img": user.profile_img,
    }
  except Exception as e:
    print(f"프로필 사진 조회 중 오류: {e}")  # 디버깅용 로그
    raise HTTPException(status_code=500, detail=f"프로필 사진 조회 실패: {str(e)}")
  
#######################################################
#######################################################
#######################################################
#######################################################
#######################################################
#######################################################
#######################################################
#######################################################



# JWT 토큰 디코딩
def decode_token(token: str):
  try:
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    user_idx: int = payload.get("user_idx")
    if user_idx is None:
      raise HTTPException(status_code=401, detail="Invalid token")
    return user_idx
  except JWTError:
    raise HTTPException(status_code=401, detail="Could not validate token")

def get_current_user(token: str = Depends(oauth2_scheme)):
  return decode_token(token)

# 텍스트 전처리
def preprocess_korean_text(logs_text):
  words = re.findall(r'[가-힣]+', logs_text)
  korean_stopwords = set([
    "은", "는", "이", "가", "을", "를", "에", "의", "와", "과", 
    "도", "로", "에서", "에게", "한", "하다", "있다", "합니다",
    "했다", "하지만", "그리고", "그러나", "때문에", "한다", "것", 
    "같다", "더", "못", "이런", "저런", "그런", "어떻게", "왜",
    "수", "싶어요", "정말", "제가", "있어", "싶어", "같아", "경우", "있습니다"
  ])
  return [word for word in words if word not in korean_stopwords]

# 워드클라우드 이미지 업로드
@router.post("/upload-image/", response_model=dict)
def upload_image(file: UploadFile = File(...)):
  try:
    file_location = f"{WORDCLOUD_UPLOAD_DIR}/{file.filename}"
    with open(file_location, "wb") as f:
      shutil.copyfileobj(file.file, f)
    return {"message": f"파일 '{file.filename}'이 저장되었습니다."}
  except Exception as e:
    print(f"파일 업로드 오류: {e}")
    raise HTTPException(status_code=500, detail=f"서버 오류: {str(e)}")

# 워드클라우드 생성
@router.get("api/user-wordcloud/{user_idx}", response_class=FileResponse)
def generate_user_wordcloud(user_idx: int, db: Session = Depends(get_db)):
  try:
    chat_ids = db.query(ChatRoom.chat_id).filter(ChatRoom.user_idx == user_idx).all()
    if not chat_ids:
      raise HTTPException(status_code=404, detail="채팅 데이터 없음.")
    chat_ids = [chat_id[0] for chat_id in chat_ids]

    logs = db.query(ChatLog.log).filter(ChatLog.chat_id.in_(chat_ids)).all()
    if not logs:
      raise HTTPException(status_code=404, detail="로그 데이터 없음.")
    logs_text = " ".join([log[0] for log in logs])

    words = preprocess_korean_text(logs_text)
    word_frequencies = Counter(words)

    font_path = "C:\\Windows\\Fonts\\malgun.ttf"
    if not os.path.exists(font_path):
      font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    if not os.path.exists(font_path):
      raise HTTPException(status_code=500, detail="폰트 파일 없음.")

    wordcloud = WordCloud(
      width=800,
      height=400,
      background_color="white",
      font_path=font_path,
      max_words=200
    ).generate_from_frequencies(word_frequencies)

    output_path = "user_wordcloud.png"
    wordcloud.to_file(output_path)
    return FileResponse(output_path, media_type="image/png", filename="user_wordcloud.png")
  except Exception as e:
    print(f"Error in generate_user_wordcloud: {e}")
    raise HTTPException(status_code=500, detail=f"서버 오류: {str(e)}")
  
# 팔로우 요청 API
@router.post("/users/{user_idx}/follow", response_model=dict)
async def add_character_to_user(
  user_idx: int,
  request: FollowRequest = Body(...),
  db: Session = Depends(get_db)
):
  if user_idx != request.user_idx:
    raise HTTPException(
      status_code=400,
      detail=f"경로의 user_idx({user_idx})와 본문의 user_idx({request.user_idx})가 일치하지 않습니다."
    )

  try:
    existing_entry = db.query(Friend).filter(
      Friend.user_idx == request.user_idx,
      Friend.char_idx == request.char_idx
    ).first()

    if existing_entry:
      raise HTTPException(status_code=400, detail="이미 추가된 캐릭터입니다.")

    new_follow = Friend(user_idx=request.user_idx, char_idx=request.char_idx)
    db.add(new_follow)
    db.commit()
    return {"message": f"캐릭터 {request.char_idx}가 유저 {request.user_idx}에게 추가되었습니다."}

  except Exception as e:
    db.rollback()
    raise HTTPException(status_code=500, detail=f"서버 내부 오류: {str(e)}")

'''
팔로우 요청 API 중복인거 같음 206번째 줄
'''
@router.post("/api/friends/follow", response_model=dict)
def follow_character(
  user_idx: int = Body(...),
  char_idx: int = Body(...),
  db: Session = Depends(get_db)
):
  try:
    # 이미 팔로우 중인지 확인
    existing_follow = db.query(Friend).filter(
      Friend.user_idx == user_idx,
      Friend.char_idx == char_idx,
      Friend.is_active == True
    ).first()

    if existing_follow:
      raise HTTPException(status_code=400, detail="이미 팔로우한 캐릭터입니다.")

    # 새로운 팔로우 관계 생성
    new_follow = Friend(
      user_idx=user_idx,
      char_idx=char_idx
    )
    db.add(new_follow)
    db.commit()
    return {"message": "성공적으로 팔로우했습니다."}
  except Exception as e:
    db.rollback()
    raise HTTPException(status_code=500, detail=str(e))

# 언팔로우 요청 API
@router.delete("/api/friends/unfollow/{user_idx}/{char_idx}", response_model=dict)
def unfollow_character(
  user_idx: int,
  char_idx: int,
  db: Session = Depends(get_db)
):
  try:
    follow = db.query(Friend).filter(
      Friend.user_idx == user_idx,
      Friend.char_idx == char_idx,
      Friend.is_active == True
    ).first()

    if not follow:
      raise HTTPException(status_code=404, detail="팔로우 관계를 찾을 수 없습니다.")

    follow.is_active = False
    db.commit()
    return {"message": "성공적으로 언팔로우했습니다."}
  except Exception as e:
    db.rollback()
    raise HTTPException(status_code=500, detail=str(e))

# 팔로우 여부 확인 API
@router.get("/api/friends/check/{user_idx}/{char_idx}")
def check_follow(user_idx: int, char_idx: int, db: Session = Depends(get_db)):
  follow = db.query(Friend).filter(
    Friend.user_idx == user_idx,
    Friend.char_idx == char_idx,
    Friend.is_active == True
  ).first()
  return {"is_following": bool(follow)}

