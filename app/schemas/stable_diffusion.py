from pydantic import BaseModel

class GenerateImageRequest(BaseModel):
  prompt: str
  negative_prompt: str
  width: int
  height: int
  guidance_scale: float
  num_inference_steps: int
