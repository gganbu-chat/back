from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import os

from app.routers import character, chat, auth, user, stable_diffusion, tts, rank

app = FastAPI()

# 이미지 경로 - OS 따라 경로 변하는 이슈로 인해 os 패키지 사용
UPLOAD_DIR = "app/uploads/characters"
app.mount("/images", StaticFiles(directory=UPLOAD_DIR), name="images")
app.mount("/static", StaticFiles(directory=UPLOAD_DIR), name="static")

CLIENT_DOMAIN = os.getenv("CLIENT_DOMAIN")
WS_SERVER_DOMAIN = os.getenv("WS_SERVER_DOMAIN")

# CORS 설정: 모든 도메인, 메서드, 헤더를 허용
app.add_middleware(
  CORSMiddleware,
  allow_origins=[
    CLIENT_DOMAIN
  ],  # 도메인 허용
  allow_credentials=True, # 자격 증명 허용 (쿠키 등)
  allow_methods=["*"], # 모든 HTTP 메서드 허용 (GET, POST 등)
  allow_headers=["*"], # 모든 HTTP 헤더 허용
  expose_headers=["*"]
)

# 라우터 등록
app.include_router(character.router, tags=["Characters"])
app.include_router(chat.router, tags=["Chat"])
app.include_router(auth.router, tags=["Auth"])
app.include_router(user.router, tags=["Users"])
app.include_router(stable_diffusion.router, tags=["Stable_Diffusion"])
app.include_router(tts.router, tags=["TTS"])
app.include_router(rank.router, tags=["Rank"])

@app.get("/")
async def root():
  return {"message": "Hello World"}

# uvicorn app.main:app --reload --log-level debug --port 8000