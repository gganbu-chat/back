## 백엔드 시작하는 방법

- 1. venv 가상환경 생성
python3 -m venv gganbu

- 2. 가상환경 활성화
source gganbu/bin/activate

- 3. .env 파일 설정

- 4. 필수 라이브러리 설치  
pip install -r requirements.txt

- 5. app 디렉토리로 이동  
cd app

- 6. DB 생성  
python database.py

- 7. 백엔드 실행(uvicorn 이용)
uvicorn main:app --reload