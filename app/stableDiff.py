from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from database import SessionLocal, Image, ImagePrompt
from diffusers import StableDiffusionPipeline
import torch
from datetime import datetime
from pathlib import Path
import base64
import uuid

router = APIRouter()

# 데이터베이스 세션 의존성
def get_db():
  db = SessionLocal()
  try:
    yield db
  finally:
    db.close()

class GenerateImageRequest(BaseModel):
  prompt: str
  negative_prompt: str
  width: int
  height: int
  guidance_scale: float
  num_inference_steps: int


# 모델 초기화 (앱 시작 시 1회)
pipe = StableDiffusionPipeline.from_pretrained(
  "runwayml/stable-diffusion-v1-5",
  torch_dtype=torch.float32
).to("cpu")

def generate_image(prompt: str) -> str:
  image = pipe(prompt).images[0]
  timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
  output_path = Path("uploads/stableDiff_img") / f"{timestamp}.png"
  output_path.parent.mkdir(parents=True, exist_ok=True)
  image.save(output_path)
  return str(output_path)


@router.post("/generate-stable-img")
def generate_image(req: GenerateImageRequest):
  try:
    # 이미지 생성
    image = pipe(
      prompt=req.prompt,
      negative_prompt=req.negative_prompt,
      width=req.width,
      height=req.height,
      guidance_scale=req.guidance_scale,
      num_inference_steps=req.num_inference_steps
    ).images[0]

    # 이미지 저장 경로
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    file_name = f"character_{timestamp}_{uuid.uuid4().hex[:6]}.png"
    save_dir = Path("uploads/stableDiff_img")
    save_dir.mkdir(parents=True, exist_ok=True)
    file_path = save_dir / file_name
    image.save(file_path)

    # 이미지 base64 인코딩
    with open(file_path, "rb") as f:
      img_bytes = f.read()
      img_base64 = base64.b64encode(img_bytes).decode("utf-8")

    return {"image": img_base64}

  except Exception as e:
    raise HTTPException(status_code=500, detail=f"이미지 생성 중 오류 발생: {str(e)}")