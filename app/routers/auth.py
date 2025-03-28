from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from jose import jwt, JWTError
from fastapi.security import OAuth2PasswordBearer
from datetime import datetime, timedelta
import os
import shutil

from app.core.config import Settings
from app.database.session import get_db
from app.models.models import User
from app.schemas.user import SignInRequest, SignupRequest

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="signin")
SECRET_KEY = Settings.SECRET_KEY
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 720
UPLOAD_DIR = "app.uploads/user_profiles" # 유저 프로필 사진 저장 위치

'''
수정사항
토큰 유효기간 및 비밀번호 해시 처리 해야 함
'''

# 토큰 생성 함수
def create_access_token(data: dict, expires_delta: timedelta = None):
  to_encode = data.copy()
  if expires_delta:
    expire = datetime.utcnow() + expires_delta
  else:
    expire = datetime.utcnow() + timedelta(minutes=15)
  to_encode.update({"exp": expire})
  encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
  return encoded_jwt

router = APIRouter()

# 회원가입 API
@router.post("/signup", response_model=dict)
def signup(signup_request: SignupRequest, db: Session = Depends(get_db)):
  try:
    # 기존 사용자 확인
    existing_user = db.query(User).filter(User.user_id == signup_request.user_id).first()

    if existing_user:
      raise HTTPException(status_code=400, detail="ID가 이미 존재합니다!")

    # 새 사용자 생성
    new_user = User(**signup_request.dict())
    db.add(new_user)
    db.commit()
    return {"message": "회원가입 성공"}
  except Exception as e:
    print(f"회원가입 처리 중 오류: {e}")  # 상세 오류 출력
    raise HTTPException(status_code=500, detail=f"서버 내부 오류: {e}")

# 로그인 API
@router.post("/signin", response_model=dict)
def signin(signin_request: SignInRequest, db: Session = Depends(get_db)):
  try:
    # 사용자 조회
    user = db.query(User).filter(User.user_id == signin_request.user_id).first()
    if not user or user.password != signin_request.password:
      raise HTTPException(status_code=400, detail="잘못된 사용자 ID 또는 비밀번호입니다.")

      # 액세스 토큰 생성 (user_id와 user_idx 포함)
    token = create_access_token(data={"sub": user.user_id, "user_idx": user.user_idx})
    return {"message": "로그인 성공", "token": token}
  except Exception as e:
    print(f"로그인 처리 중 오류: {e}")  # 상세 오류 출력
    raise HTTPException(status_code=500, detail=f"서버 내부 오류: {e}")

# 토큰 확인 API
@router.get("/verify-token", response_model=dict)
def verify_token(token: str = Depends(oauth2_scheme)):
  try:
    # JWT 토큰 디코딩
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    user_id: str = payload.get("sub")
    user_idx: int = payload.get("user_idx")  # user_idx 추출
    
    if not user_id or not user_idx:
      raise HTTPException(status_code=401, detail="유효하지 않은 토큰")
    
    # 토큰이 유효한 경우 user_idx 반환
    return {"message": "토큰이 유효합니다", "user_idx": user_idx}
  except JWTError as e:
    print(f"토큰 검증 오류: {e}")  # 디버깅용 오류 출력
    raise HTTPException(status_code=401, detail="유효하지 않은 토큰")
  




'''
수정 필요 -> 회원가입 단계에서 이미지 저장 하도록 수정해야 함
'''
@router.post("/upload-profile-img/{user_id}/", response_model=dict)
def upload_profile_img(
  user_id: str,
  file: UploadFile = File(...),
  db: Session = Depends(get_db),
):
  try:
    # 업로드 디렉토리 생성
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    # 파일 저장 경로 설정
    file_location = f"{UPLOAD_DIR}/{file.filename}"
    with open(file_location, "wb") as f:
      shutil.copyfileobj(file.file, f)

    # 사용자 조회
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
      raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다!")

    # 사용자 프로필 사진 업데이트
    user.profile_img = file_location
    db.commit()
    db.refresh(user)

    # 성공 메시지 반환
    return {"message": f"사용자의 프로필 사진이 저장되었습니다.", "profile_img": file_location}
  except Exception as e:
    print(f"파일 업로드 중 오류: {e}")  # 디버깅용 로그
    raise HTTPException(status_code=500, detail=f"파일 업로드 실패: {str(e)}")