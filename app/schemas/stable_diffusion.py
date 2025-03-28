from pydantic import BaseModel

class GenerateImageRequest(BaseModel):
  prompt: str
  art_style: str
  background: str
  mood: str
  width: int
  height: int
  guidance_scale: float
  num_inference_steps: int
