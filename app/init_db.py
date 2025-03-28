from app.models import models
from app.database.session import engine

def init():
  print("Creating tables...")
  models.Base.metadata.create_all(bind=engine)

if __name__ == "__main__":
  init()
