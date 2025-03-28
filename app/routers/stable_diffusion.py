from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy.orm import Session
from diffusers import StableDiffusionPipeline
import torch
from datetime import datetime
from pathlib import Path
import base64
import uuid

from app.database.session import get_db
from app.models.models import Image, ImageMapping, ImagePrompt
from app.schemas.stable_diffusion import GenerateImageRequest

router = APIRouter()

# 모델 초기화 (서버 시작 시 1회만)
pipe = StableDiffusionPipeline.from_pretrained(
  "runwayml/stable-diffusion-v1-5",
  torch_dtype=torch.float32
).to("cpu")

UPLOAD_DIR = Path("app/uploads/stableDiff_img")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

def assembly_prompt(prompt, style, background, mood):
  style_options = {
    'anime': 'anime style, vibrant, expressive eyes, detailed hair',
    'realistic': 'photorealistic, ultra-detailed, realistic skin texture, sharp lighting',
    'retro': 'retro illustration, 90s style, warm tones, nostalgic mood',
    'cyberpunk': 'cyberpunk style, neon lights, futuristic city, glowing elements',
  }
  style = style_options.get(style, style_options['anime'])

  background_options = {
    'beach': 'sunny beach with waves, soft sand, blue ocean, gentle breeze',
    'sky': 'clear blue sky with scattered clouds, bright daylight',
    'forest': 'lush green forest with sunlight filtering through leaves, peaceful nature',
    'castle': 'majestic fantasy castle, intricate details, magical atmosphere',
    'classroom': 'bright modern classroom with desks, blackboard, natural light',
    'stage': 'concert stage with spotlight, dynamic lighting, crowd in background',
    'hallway': 'school hallway with lockers, clean floor, ambient light',
    'cafe': 'cozy cafe interior, warm lighting, wooden furniture, relaxed vibe',
  }
  background = background_options.get(background, background_options['sky'])

  mood_options = {
    'natural': 'natural daylight, soft shadows, clear lighting',
    'neon': 'neon lighting, glowing highlights, vibrant colors',
    'cool': 'cool lighting, bluish tones, soft ambient shadows',
    'rainbow': 'rainbow lighting, colorful reflections, dreamy glow',
  }
  mood = mood_options.get(mood, mood_options['natural'])

  full_prompt = f"{prompt}, in {style} style, {background} background, {mood} atmosphere"
  return full_prompt

def generate_and_save_image(req: GenerateImageRequest) -> str:
  prompt = assembly_prompt(req.prompt, req.art_style, req.background, req.mood)
  # print(prompt)

  negative_prompt = '''
    lowres, bad anatomy, bad hands, text, error, missing fingers, extra digit, fewer digits, cropped, worst quality, low quality, normal quality, jpeg artifacts, signature, watermark, username, blurry, disfigured, extra limbs, missing limbs, deformed hands, long neck, poorly drawn face, mutated, bad proportions, low resolution, distorted
  '''

  # 이미지 생성
  image = pipe(
    prompt=prompt,
    negative_prompt=negative_prompt,
    width=req.width,
    height=req.height,
    guidance_scale=req.guidance_scale,
    num_inference_steps=req.num_inference_steps
  ).images[0]

  # 저장 경로 생성
  timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
  filename = f"character_{timestamp}_{uuid.uuid4().hex[:6]}.png"
  file_path = UPLOAD_DIR / filename
  image.save(file_path)
  return str(file_path), prompt

@router.post("/generate-stable-img")
def generate_image_api(req: GenerateImageRequest):
  try:
    file_path, prompt = generate_and_save_image(req)

    # base64 인코딩
    with open(file_path, "rb") as f:
      img_bytes = f.read()
      img_base64 = base64.b64encode(img_bytes).decode("utf-8")

    return {"image": img_base64, "prompt": prompt}

  except Exception as e:
    raise HTTPException(status_code=500, detail=f"이미지 생성 중 오류 발생: {str(e)}")