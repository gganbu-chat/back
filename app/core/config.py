import os
from dotenv import load_dotenv

load_dotenv()  # .env 파일 로딩

class Settings:
  CLIENT_DOMAIN: str = os.getenv("CLIENT_DOMAIN", "http://localhost:3000")
  WS_SERVER_DOMAIN = os.getenv("WS_SERVER_DOMAIN", "ws://localhost:8001")
  DB_HOST = os.getenv("DB_HOST")
  DB_USER = os.getenv("DB_USER")
  DB_PASS = os.getenv("DB_PASS")
  DB_PORT = os.getenv("DB_PORT")
  DB_NAME = os.getenv("DB_NAME")
  DATABASE_URL=f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
  SECRET_KEY = os.getenv("SECRET_KEY", "default_key")

settings = Settings()
